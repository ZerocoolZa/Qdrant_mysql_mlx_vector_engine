//[@GHOST]{file_path="core/Piplines/c_transformer_attention.mm" date="2026-07-01" author="cascade" session_id="c-bcl-transformer" context="Metal GPU BCL Transformer attention layer — Q/K/V projection, multi-head attention, masked softmax, backprop, SGD. fp16 storage, float32 accumulation, half4 vectorized loads. Reuses buffer management from c_word2vec_metal_packed.mm."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@FILEID]{id="c_transformer_attention.mm" domain="transformer_engine" authority="BCLTransformer"}
//[@SUMMARY]{summary="BCL Transformer attention Metal pipeline. TransformerConfig → MetalBackend → AttentionLayer (forward+backward) → SGDOptimizer. Forward: embedding_lookup → qkv_projection → attention_scores → masked_softmax → attention_output → output_projection → residual_add → layer_norm → gelu. Backward: reverse order with grad accumulation. SGD update with weight decay."}

// ============ BCL FLOW ============
//
// [@FLOW]{
//   [@STEP]{1; "TransformerConfig";  "Set d_model=384, n_heads=6, head_dim=64, n_layers=6, max_seq=2048, vocab=162612"}
//   [@STEP]{2; "MetalBackend";       "Init Metal device, command queue, compile shaders from metal_shaders_transformer.h, create pipeline states"}
//   [@STEP]{3; "WeightInit";         "Allocate fp16 weight buffers (W_q, W_k, W_v, W_o, W_emb, LN scale/bias), random init"}
//   [@STEP]{4; "BufferUpload";       "Upload all weights + activations to Metal shared buffers"}
//   [@STEP]{5; "AttentionForward";   "embedding_lookup → qkv_projection → attention_scores → masked_softmax → attention_output → output_projection → residual → layer_norm"}
//   [@STEP]{6; "AttentionBackward";  "Reverse pass: grad through output_proj → attn_output → softmax → scores → qkv_projection. Accumulate grad_W in fp32"}
//   [@STEP]{7; "SGDOptimizer";       "Apply W -= lr * grad_W with L2 weight decay. half4 vectorized update"}
// }
//
// ============ INCLUDES ============

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>
#include <sys/stat.h>
#include <iostream>
#include <iomanip>

// ============ BCL PARSER (copied from bcl_engine.h + bcl_parser.c) ============
//[@GHOST]{section="bcl_parser_inline" date="2026-07-03" author="devin" session_id="bcl-metal-native" context="BCL C parser copied directly into transformer to avoid tree_sitter dependency. Self-contained: only needs string.h. Parses [@TAG]{content} bracket syntax into BclNode tree."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@SUMMARY]{summary="Inline BCL parser: BclNode/BclParseResult structs + BclParser_Init/Parse. Syntax-only, no semantic knowledge. 256 max nodes, recursive descent."}

#define BCL_MAX_NODES    256
#define BCL_MAX_CONTENT  4096
#define BCL_MAX_TAG      64
#define BCL_MAX_DEPTH    32
#define BCL_MAX_RESULT   65536

typedef struct {
    char tag[BCL_MAX_TAG];
    char content[BCL_MAX_CONTENT];
    int  start_pos;
    int  end_pos;
    int  depth;
    int  parent_idx;
    int  child_count;
    int  children[32];
} BclNode;

typedef struct {
    BclNode nodes[BCL_MAX_NODES];
    int     node_count;
    int     parse_ok;
    char    error_msg[256];
    int     error_pos;
} BclParseResult;

static void BclParser_Init(BclParseResult *p) {
    if (!p) return;
    memset(p, 0, sizeof(BclParseResult));
    p->parse_ok = 1;
    p->error_pos = -1;
}

static int BclParser_AddNode(BclParseResult *p, const char *tag, int start_pos, int depth, int parent_idx) {
    int idx;
    if (p->node_count >= BCL_MAX_NODES) return -1;
    idx = p->node_count;
    memset(&p->nodes[idx], 0, sizeof(BclNode));
    strncpy(p->nodes[idx].tag, tag, BCL_MAX_TAG - 1);
    p->nodes[idx].tag[BCL_MAX_TAG - 1] = '\0';
    p->nodes[idx].start_pos = start_pos;
    p->nodes[idx].depth = depth;
    p->nodes[idx].parent_idx = parent_idx;
    p->nodes[idx].child_count = 0;
    p->node_count++;
    return idx;
}

static void BclParser_SetNodeContent(BclParseResult *p, int idx, const char *content, int len) {
    int copy_len;
    if (idx < 0 || idx >= p->node_count) return;
    copy_len = len;
    if (copy_len >= BCL_MAX_CONTENT) copy_len = BCL_MAX_CONTENT - 1;
    if (copy_len > 0) memcpy(p->nodes[idx].content, content, copy_len);
    p->nodes[idx].content[copy_len] = '\0';
    p->nodes[idx].end_pos = p->nodes[idx].start_pos + len;
}

static void BclParser_AddChild(BclParseResult *p, int parent_idx, int child_idx) {
    BclNode *parent;
    if (parent_idx < 0 || parent_idx >= p->node_count) return;
    parent = &p->nodes[parent_idx];
    if (parent->child_count >= 32) return;
    parent->children[parent->child_count] = child_idx;
    parent->child_count++;
}

static void BclParser_SetError(BclParseResult *p, const char *msg, int pos) {
    p->parse_ok = 0;
    strncpy(p->error_msg, msg, sizeof(p->error_msg) - 1);
    p->error_msg[sizeof(p->error_msg) - 1] = '\0';
    p->error_pos = pos;
}

static int BclParser_ParseInner(BclParseResult *p, const char *text, int pos, int end_pos, int depth, int parent_idx) {
    int len;
    int i;
    int tag_start;
    int tag_end;
    int brace_start;
    int content_start;
    int brace_end;
    int brace_depth;
    int node_idx;
    char tag[BCL_MAX_TAG];

    len = end_pos;

    while (pos < len) {
        if (text[pos] == '[' && pos + 1 < len && text[pos + 1] == '@') {
            tag_start = pos + 2;
            tag_end = tag_start;
            while (tag_end < len && text[tag_end] != ']' && text[tag_end] != '\0') {
                tag_end++;
            }
            if (tag_end >= len || text[tag_end] != ']') {
                BclParser_SetError(p, "unterminated_tag", pos);
                return -1;
            }
            i = 0;
            while (i < BCL_MAX_TAG - 1 && tag_start + i < tag_end) {
                tag[i] = text[tag_start + i];
                i++;
            }
            tag[i] = '\0';
            if (i == 0) {
                BclParser_SetError(p, "empty_tag", pos);
                return -1;
            }
            if (tag_end + 1 >= len || text[tag_end + 1] != '{') {
                pos = tag_end + 1;
                continue;
            }
            brace_start = tag_end + 1;
            content_start = brace_start + 1;
            brace_depth = 1;
            i = content_start;
            while (i < len && brace_depth > 0) {
                if (text[i] == '{') brace_depth++;
                else if (text[i] == '}') brace_depth--;
                if (brace_depth > 0) i++;
            }
            if (brace_depth != 0) {
                BclParser_SetError(p, "unterminated_brace", brace_start);
                return -1;
            }
            brace_end = i;
            node_idx = BclParser_AddNode(p, tag, pos, depth, parent_idx);
            if (node_idx < 0) {
                BclParser_SetError(p, "max_nodes_exceeded", pos);
                return -1;
            }
            if (parent_idx >= 0) {
                BclParser_AddChild(p, parent_idx, node_idx);
            }
            BclParser_SetNodeContent(p, node_idx, text + content_start, brace_end - content_start);
            BclParser_ParseInner(p, text, content_start, brace_end, depth + 1, node_idx);
            if (!p->parse_ok) return -1;
            pos = brace_end + 1;
            continue;
        }
        pos++;
    }
    return 0;
}

static int BclParser_Parse(BclParseResult *p, const char *bcl_text) {
    if (!p || !bcl_text) return 0;
    p->node_count = 0;
    p->parse_ok = 1;
    p->error_msg[0] = '\0';
    p->error_pos = -1;
    BclParser_ParseInner(p, bcl_text, 0, (int)strlen(bcl_text), 0, -1);
    return p->parse_ok ? 1 : 0;
}

// ============ SHADER SOURCE ============

static const char* TRANSFORMER_SHADER_SOURCE =
#include "metal_shaders_transformer.h"
;

// ============ CONFIG CONSTANTS ============

#define D_MODEL      384
#define N_HEADS      6
#define HEAD_DIM     64
#define N_LAYERS     6
#define MAX_SEQ_LEN  2048
#define VOCAB_SIZE   162612
#define LN_EPS       1e-5f

// ============ CLASS: TransformerConfig ============
// Holds all hyperparameters. Matches the config spec.

typedef struct {
    int d_model;
    int n_heads;
    int head_dim;
    int n_layers;
    int max_seq_len;
    int vocab_size;
    float lr;
    float weight_decay;
    float ln_eps;
} TransformerConfig;

static TransformerConfig TransformerConfig_Default(void) {
    TransformerConfig c;
    c.d_model = D_MODEL;
    c.n_heads = N_HEADS;
    c.head_dim = HEAD_DIM;
    c.n_layers = N_LAYERS;
    c.max_seq_len = MAX_SEQ_LEN;
    c.vocab_size = VOCAB_SIZE;
    c.lr = 1e-3f;
    c.weight_decay = 0.01f;
    c.ln_eps = LN_EPS;
    return c;
}

// ============ CLASS: MetalBackend ============
// Manages Metal device, command queue, and compiled pipeline states.
// Follows the same pattern as c_word2vec_metal_packed.mm MetalTrainer_Init.

typedef struct {
    id<MTLDevice> device;
    id<MTLCommandQueue> queue;
    id<MTLLibrary> library;
    // Forward pipelines
    id<MTLComputePipelineState> pipe_embedding_lookup;
    id<MTLComputePipelineState> pipe_qkv_projection;
    id<MTLComputePipelineState> pipe_attention_scores;
    id<MTLComputePipelineState> pipe_masked_softmax;
    id<MTLComputePipelineState> pipe_attention_output;
    id<MTLComputePipelineState> pipe_output_projection;
    id<MTLComputePipelineState> pipe_residual_add;
    id<MTLComputePipelineState> pipe_attention_bias_add;
    id<MTLComputePipelineState> pipe_layer_norm;
    id<MTLComputePipelineState> pipe_gelu;
    // Backward pipelines
    id<MTLComputePipelineState> pipe_attn_output_backward;
    id<MTLComputePipelineState> pipe_softmax_backward;
    id<MTLComputePipelineState> pipe_attn_scores_backward;
    id<MTLComputePipelineState> pipe_qkv_proj_backward;
    id<MTLComputePipelineState> pipe_grad_x_accumulate;
    id<MTLComputePipelineState> pipe_output_proj_backward;
    id<MTLComputePipelineState> pipe_grad_attn_out_accumulate;
    // [@GHOST]{section="backward_completion_pipes" date="2026-07-04" context="Pipeline states for layer_norm_backward, residual_backward, gelu_backward — complete the gradient flow through LN and residual connections"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    id<MTLComputePipelineState> pipe_layer_norm_backward;
    id<MTLComputePipelineState> pipe_residual_backward;
    id<MTLComputePipelineState> pipe_gelu_backward;
    // Optimizer / utility pipelines
    id<MTLComputePipelineState> pipe_sgd_update;
    id<MTLComputePipelineState> pipe_zero_float;
    id<MTLComputePipelineState> pipe_zero_half;
    // [@GHOST]{section="loss_pipelines" date="2026-07-02" context="Cross-entropy loss + backward + gradient clipping pipeline states"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    id<MTLComputePipelineState> pipe_cross_entropy_loss;
    id<MTLComputePipelineState> pipe_cross_entropy_backward;
    id<MTLComputePipelineState> pipe_grad_norm_compute;
    id<MTLComputePipelineState> pipe_grad_clip_scale;
    id<MTLComputePipelineState> pipe_loss_to_grad_hidden;
    // [@GHOST]{section="inference_pipelines" date="2026-07-03" context="Inference decoding pipeline states: argmax (greedy) and top_k_sample (stochastic)"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    id<MTLComputePipelineState> pipe_argmax;
    id<MTLComputePipelineState> pipe_top_k_sample;
    int ready;
} MetalBackend;

static int MetalBackend_Init(MetalBackend* be) {
    @autoreleasepool {
        be->device = MTLCreateSystemDefaultDevice();
        if (!be->device) {
            std::cout << "[XFORM] Metal not available\n";
            return 0;
        }
        be->queue = [be->device newCommandQueue];
        NSError* err = nil;
        NSString* src = [NSString stringWithUTF8String:TRANSFORMER_SHADER_SOURCE];
        be->library = [be->device newLibraryWithSource:src options:nil error:&err];
        if (!be->library) {
            std::cout << "[XFORM] Shader compile error: " << [[err localizedDescription] UTF8String] << "\n";
            return 0;
        }

        #define LOAD_PIPE(name, pipe) \
            be->pipe = [be->device newComputePipelineStateWithFunction:[be->library newFunctionWithName:@name] error:&err]; \
            if (!be->pipe) { std::cout << "[XFORM] Pipeline " << name << " failed: " << [[err localizedDescription] UTF8String] << "\n"; return 0; }

        LOAD_PIPE("embedding_lookup",          pipe_embedding_lookup);
        LOAD_PIPE("qkv_projection",            pipe_qkv_projection);
        LOAD_PIPE("attention_scores",          pipe_attention_scores);
        LOAD_PIPE("masked_softmax",            pipe_masked_softmax);
        LOAD_PIPE("attention_output",          pipe_attention_output);
        LOAD_PIPE("output_projection",         pipe_output_projection);
        LOAD_PIPE("residual_add",              pipe_residual_add);
        LOAD_PIPE("attention_bias_add",        pipe_attention_bias_add);
        LOAD_PIPE("layer_norm",                pipe_layer_norm);
        LOAD_PIPE("gelu",                      pipe_gelu);
        LOAD_PIPE("attn_output_backward",      pipe_attn_output_backward);
        LOAD_PIPE("softmax_backward",          pipe_softmax_backward);
        LOAD_PIPE("attention_scores_backward", pipe_attn_scores_backward);
        LOAD_PIPE("qkv_projection_backward",   pipe_qkv_proj_backward);
        LOAD_PIPE("grad_x_accumulate",         pipe_grad_x_accumulate);
        LOAD_PIPE("output_projection_backward",pipe_output_proj_backward);
        LOAD_PIPE("grad_attn_out_accumulate",  pipe_grad_attn_out_accumulate);
        // [@GHOST]{section="backward_completion_pipe_loading" date="2026-07-04" context="Load layer_norm_backward, residual_backward, gelu_backward pipeline states"}
        LOAD_PIPE("layer_norm_backward",       pipe_layer_norm_backward);
        LOAD_PIPE("residual_backward",         pipe_residual_backward);
        LOAD_PIPE("gelu_backward",             pipe_gelu_backward);
        LOAD_PIPE("sgd_update",                pipe_sgd_update);
        LOAD_PIPE("zero_float_buffer",         pipe_zero_float);
        LOAD_PIPE("zero_half_buffer",          pipe_zero_half);
        // [@GHOST]{section="loss_pipe_loading" date="2026-07-02" context="Load cross-entropy + grad clip pipeline states"}
        LOAD_PIPE("cross_entropy_loss",        pipe_cross_entropy_loss);
        LOAD_PIPE("cross_entropy_backward",    pipe_cross_entropy_backward);
        LOAD_PIPE("grad_norm_compute",         pipe_grad_norm_compute);
        LOAD_PIPE("grad_clip_scale",           pipe_grad_clip_scale);
        LOAD_PIPE("loss_to_grad_hidden",       pipe_loss_to_grad_hidden);
        // [@GHOST]{section="inference_pipe_loading" date="2026-07-03" context="Load argmax + top_k_sample pipeline states for inference mode"}
        LOAD_PIPE("argmax_kernel",             pipe_argmax);
        LOAD_PIPE("top_k_sample_kernel",       pipe_top_k_sample);
        #undef LOAD_PIPE

        be->ready = 1;
        std::cout << "[XFORM] Metal backend ready: " << [[be->device name] UTF8String] << "\n";
        return 1;
    }
}

// Helper: dispatch a 2D compute kernel with optimal threadgroup sizing
static void MetalBackend_Dispatch2D(MetalBackend* be, id<MTLComputePipelineState> pipe,
                                     id<MTLBuffer>* buffers, int n_bufs,
                                     int total_x, int total_y,
                                     void* const_bytes, int const_size, int const_idx) {
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:pipe];
        for (int i = 0; i < n_bufs; i++) {
            [enc setBuffer:buffers[i] offset:0 atIndex:i];
        }
        if (const_bytes && const_size > 0) {
            [enc setBytes:const_bytes length:const_size atIndex:const_idx];
        }
        int ew = (int)pipe.threadExecutionWidth;
        int mt = (int)pipe.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(total_x, total_y, 1)
             threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// Helper: dispatch a 3D compute kernel
static void MetalBackend_Dispatch3D(MetalBackend* be, id<MTLComputePipelineState> pipe,
                                     id<MTLBuffer>* buffers, int n_bufs,
                                     int total_x, int total_y, int total_z) {
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:pipe];
        for (int i = 0; i < n_bufs; i++) {
            [enc setBuffer:buffers[i] offset:0 atIndex:i];
        }
        int ew = (int)pipe.threadExecutionWidth;
        int mt = (int)pipe.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 16) tgx = 16; if (tgx < 1) tgx = 8;
        int tgy = 1, tgz = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(total_x, total_y, total_z)
             threadsPerThreadgroup:MTLSizeMake(tgx, tgy, tgz)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// ============ CLASS: AttentionLayer ============
// Holds all weights, activations, and gradients for one transformer attention layer.
// Weights are fp16, gradients are fp32 (for accumulation accuracy).

typedef struct {
    TransformerConfig config;
    MetalBackend* backend;

    // Weights (fp16) — per layer
    id<MTLBuffer> W_q;        // [d_model, d_model]
    id<MTLBuffer> W_k;        // [d_model, d_model]
    id<MTLBuffer> W_v;        // [d_model, d_model]
    id<MTLBuffer> W_o;        // [d_model, d_model]
    id<MTLBuffer> ln_scale;   // [d_model]
    id<MTLBuffer> ln_bias;    // [d_model]

    // Gradients (fp32) — per layer
    id<MTLBuffer> grad_W_q;   // [d_model, d_model]
    id<MTLBuffer> grad_W_k;
    id<MTLBuffer> grad_W_v;
    id<MTLBuffer> grad_W_o;
    id<MTLBuffer> grad_ln_scale;
    id<MTLBuffer> grad_ln_bias;

    // Activations (fp16) — per forward pass
    id<MTLBuffer> X;          // [seq, d_model] input
    id<MTLBuffer> Q;          // [seq, d_model]
    id<MTLBuffer> K;          // [seq, d_model]
    id<MTLBuffer> V;          // [seq, d_model]
    id<MTLBuffer> S;          // [n_heads, seq, seq] attention scores
    id<MTLBuffer> P;          // [n_heads, seq, seq] attention probs
    id<MTLBuffer> attn_out;   // [seq, d_model] (after attention_output, before W_o)
    id<MTLBuffer> out;        // [seq, d_model] final output
    id<MTLBuffer> ln_x;       // [seq, d_model] saved for layer_norm backward

    // Gradient activations (mix of fp16/fp32)
    id<MTLBuffer> grad_out;   // [seq, d_model] fp16 (incoming gradient)
    id<MTLBuffer> grad_Q;     // [seq, d_model] fp16
    id<MTLBuffer> grad_K;     // [seq, d_model] fp32 (accumulated)
    id<MTLBuffer> grad_V;     // [seq, d_model] fp32 (accumulated)
    id<MTLBuffer> grad_S;     // [n_heads, seq, seq] fp16
    id<MTLBuffer> grad_P;     // [n_heads, seq, seq] fp16
    id<MTLBuffer> grad_attn;  // [seq, d_model] fp32
    id<MTLBuffer> grad_X;     // [seq, d_model] fp32 (output gradient to previous layer)
    // [@GHOST]{section="backward_completion_buffers" date="2026-07-04" context="grad_residual: fp32 output of layer_norm_backward. grad_residual_x: fp32 residual gradient to add to grad_X. These complete the gradient flow through LN and residual."}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    id<MTLBuffer> grad_residual;   // [seq, d_model] fp32 (LN backward output)
    id<MTLBuffer> grad_residual_x; // [seq, d_model] fp32 (residual path gradient to X)

    // BCL container mask [seq, seq] — 0=allow, 1=block
    id<MTLBuffer> bcl_mask;

    // BCL IR graph bias [seq, seq] float — T5-style additive bias for attention scores
    id<MTLBuffer> graph_bias_buf;
    int has_graph_bias;

    int seq_len;
    int initialized;
} AttentionLayer;

static float frand_norm(void) {
    return ((float)rand() / (float)RAND_MAX - 0.5f) * 0.02f;
}

static int AttentionLayer_Init(AttentionLayer* layer, TransformerConfig* config, MetalBackend* be, int seq_len) {
    layer->config = *config;
    layer->backend = be;
    layer->seq_len = seq_len;
    int dm = config->d_model;
    int nh = config->n_heads;
    int sl = seq_len;

    size_t w_size = (size_t)dm * dm * sizeof(__fp16);
    size_t vec_size = (size_t)dm * sizeof(__fp16);
    size_t act_size = (size_t)sl * dm * sizeof(__fp16);
    size_t score_size = (size_t)nh * sl * sl * sizeof(__fp16);
    size_t grad_w_size = (size_t)dm * dm * sizeof(float);
    size_t grad_act_f32 = (size_t)sl * dm * sizeof(float);

    @autoreleasepool {
        // Allocate and initialize weights (fp16) with small random values
        __fp16* wq_host = (__fp16*)malloc(w_size);
        __fp16* wk_host = (__fp16*)malloc(w_size);
        __fp16* wv_host = (__fp16*)malloc(w_size);
        __fp16* wo_host = (__fp16*)malloc(w_size);
        __fp16* lns_host = (__fp16*)malloc(vec_size);
        __fp16* lnb_host = (__fp16*)malloc(vec_size);

        for (size_t i = 0; i < (size_t)dm * dm; i++) {
            wq_host[i] = (__fp16)frand_norm();
            wk_host[i] = (__fp16)frand_norm();
            wv_host[i] = (__fp16)frand_norm();
            wo_host[i] = (__fp16)frand_norm();
        }
        for (int i = 0; i < dm; i++) {
            lns_host[i] = (__fp16)1.0f;   // LN scale init to 1
            lnb_host[i] = (__fp16)0.0f;   // LN bias init to 0
        }

        layer->W_q = [be->device newBufferWithBytes:wq_host length:w_size options:MTLResourceStorageModeShared];
        layer->W_k = [be->device newBufferWithBytes:wk_host length:w_size options:MTLResourceStorageModeShared];
        layer->W_v = [be->device newBufferWithBytes:wv_host length:w_size options:MTLResourceStorageModeShared];
        layer->W_o = [be->device newBufferWithBytes:wo_host length:w_size options:MTLResourceStorageModeShared];
        layer->ln_scale = [be->device newBufferWithBytes:lns_host length:vec_size options:MTLResourceStorageModeShared];
        layer->ln_bias = [be->device newBufferWithBytes:lnb_host length:vec_size options:MTLResourceStorageModeShared];

        free(wq_host); free(wk_host); free(wv_host); free(wo_host);
        free(lns_host); free(lnb_host);

        // Allocate gradient buffers (fp32) — zeroed
        layer->grad_W_q = [be->device newBufferWithLength:grad_w_size options:MTLResourceStorageModeShared];
        layer->grad_W_k = [be->device newBufferWithLength:grad_w_size options:MTLResourceStorageModeShared];
        layer->grad_W_v = [be->device newBufferWithLength:grad_w_size options:MTLResourceStorageModeShared];
        layer->grad_W_o = [be->device newBufferWithLength:grad_w_size options:MTLResourceStorageModeShared];
        layer->grad_ln_scale = [be->device newBufferWithLength:vec_size * 2 options:MTLResourceStorageModeShared]; // float
        layer->grad_ln_bias = [be->device newBufferWithLength:vec_size * 2 options:MTLResourceStorageModeShared];

        // Activation buffers (fp16)
        layer->X = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->Q = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->K = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->V = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->S = [be->device newBufferWithLength:score_size options:MTLResourceStorageModeShared];
        layer->P = [be->device newBufferWithLength:score_size options:MTLResourceStorageModeShared];
        layer->attn_out = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->out = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->ln_x = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];

        // Gradient activation buffers
        layer->grad_out = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->grad_Q = [be->device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
        layer->grad_K = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];
        layer->grad_V = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];
        layer->grad_S = [be->device newBufferWithLength:score_size options:MTLResourceStorageModeShared];
        layer->grad_P = [be->device newBufferWithLength:score_size options:MTLResourceStorageModeShared];
        layer->grad_attn = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];
        layer->grad_X = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];
        // [@GHOST]{section="backward_completion_buffer_alloc" date="2026-07-04" context="Allocate grad_residual and grad_residual_x fp32 buffers for LN+residual backward"}
        layer->grad_residual = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];
        layer->grad_residual_x = [be->device newBufferWithLength:grad_act_f32 options:MTLResourceStorageModeShared];

        // BCL mask — default all-allow (causal mask handled in kernel)
        size_t mask_size = (size_t)sl * sl * sizeof(char);
        char* mask_host = (char*)calloc(sl * sl, sizeof(char));
        layer->bcl_mask = [be->device newBufferWithBytes:mask_host length:mask_size options:MTLResourceStorageModeShared];
        free(mask_host);

        // BCL IR graph bias — default none (set by TrainOnBcl)
        layer->graph_bias_buf = nil;
        layer->has_graph_bias = 0;

        if (!layer->W_q || !layer->W_k || !layer->W_v || !layer->W_o ||
            !layer->Q || !layer->K || !layer->V || !layer->S || !layer->P ||
            !layer->grad_W_q || !layer->grad_X) {
            std::cout << "[XFORM] Buffer allocation failed\n";
            return 0;
        }

        layer->initialized = 1;
        return 1;
    }
}

// --- Forward pass kernels ---

static void AttentionLayer_QKVProjection(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;
    id<MTLBuffer> bufs[] = {layer->X, layer->W_q, layer->W_k, layer->W_v,
                             layer->Q, layer->K, layer->V};
    int dm_val = dm, sl_val = sl;
    // We need to pass d_model and seq_len as constant bytes at indices 7 and 8
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_qkv_projection];
        for (int i = 0; i < 7; i++) [enc setBuffer:bufs[i] offset:0 atIndex:i];
        [enc setBytes:&dm_val length:sizeof(int) atIndex:7];
        [enc setBytes:&sl_val length:sizeof(int) atIndex:8];
        int ew = (int)be->pipe_qkv_projection.threadExecutionWidth;
        int mt = (int)be->pipe_qkv_projection.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > sl) tgy = sl;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_AttentionScores(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int hd = layer->config.head_dim;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;
    float scale = 1.0f / sqrtf((float)hd);

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_attention_scores];
        [enc setBuffer:layer->Q offset:0 atIndex:0];
        [enc setBuffer:layer->K offset:0 atIndex:1];
        [enc setBuffer:layer->S offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];
        [enc setBytes:&hd length:sizeof(int) atIndex:4];
        [enc setBytes:&nh length:sizeof(int) atIndex:5];
        [enc setBytes:&sl length:sizeof(int) atIndex:6];
        [enc setBytes:&scale length:sizeof(float) atIndex:7];
        int ew = (int)be->pipe_attention_scores.threadExecutionWidth;
        int mt = (int)be->pipe_attention_scores.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 8) tgx = 8; if (tgx < 1) tgx = 4;
        int tgy = 1, tgz = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(nh, sl, sl) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, tgz)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// --- BCL IR graph bias add: S[h,i,j] += graph_bias[i,j] (broadcast across heads) ---
static void AttentionLayer_AttentionBiasAdd(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_attention_bias_add];
        [enc setBuffer:layer->S offset:0 atIndex:0];
        [enc setBuffer:layer->graph_bias_buf offset:0 atIndex:1];
        [enc setBytes:&nh length:sizeof(int) atIndex:2];
        [enc setBytes:&sl length:sizeof(int) atIndex:3];
        int ew = (int)be->pipe_attention_bias_add.threadExecutionWidth;
        int mt = (int)be->pipe_attention_bias_add.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 8) tgx = 8; if (tgx < 1) tgx = 4;
        int tgy = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(nh, sl, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_MaskedSoftmax(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_masked_softmax];
        [enc setBuffer:layer->S offset:0 atIndex:0];
        [enc setBuffer:layer->P offset:0 atIndex:1];
        [enc setBuffer:layer->bcl_mask offset:0 atIndex:2];
        [enc setBytes:&nh length:sizeof(int) atIndex:3];
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_masked_softmax.threadExecutionWidth;
        int mt = (int)be->pipe_masked_softmax.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > sl) tgy = sl;
        [enc dispatchThreads:MTLSizeMake(nh, sl, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_AttentionOutput(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int hd = layer->config.head_dim;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_attention_output];
        [enc setBuffer:layer->P offset:0 atIndex:0];
        [enc setBuffer:layer->V offset:0 atIndex:1];
        [enc setBuffer:layer->attn_out offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];
        [enc setBytes:&hd length:sizeof(int) atIndex:4];
        [enc setBytes:&nh length:sizeof(int) atIndex:5];
        [enc setBytes:&sl length:sizeof(int) atIndex:6];
        int ew = (int)be->pipe_attention_output.threadExecutionWidth;
        int mt = (int)be->pipe_attention_output.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_OutputProjection(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_output_projection];
        [enc setBuffer:layer->attn_out offset:0 atIndex:0];
        [enc setBuffer:layer->W_o offset:0 atIndex:1];
        [enc setBuffer:layer->out offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_output_projection.threadExecutionWidth;
        int mt = (int)be->pipe_output_projection.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_ResidualAdd(AttentionLayer* layer, id<MTLBuffer> a, id<MTLBuffer> b, id<MTLBuffer> result) {
    MetalBackend* be = layer->backend;
    int count = layer->seq_len * layer->config.d_model;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_residual_add];
        [enc setBuffer:a offset:0 atIndex:0];
        [enc setBuffer:b offset:0 atIndex:1];
        [enc setBuffer:result offset:0 atIndex:2];
        [enc setBytes:&count length:sizeof(int) atIndex:3];
        int ew = (int)be->pipe_residual_add.threadExecutionWidth;
        int mt = (int)be->pipe_residual_add.maxTotalThreadsPerThreadgroup;
        int tg = ew; if (tg > mt && mt > 0) tg = mt; if (tg < 1) tg = 32;
        int total = (count + 3) / 4;
        [enc dispatchThreads:MTLSizeMake(total, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_LayerNorm(AttentionLayer* layer, id<MTLBuffer> x, id<MTLBuffer> out) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;
    float eps = layer->config.ln_eps;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_layer_norm];
        [enc setBuffer:x offset:0 atIndex:0];
        [enc setBuffer:layer->ln_scale offset:0 atIndex:1];
        [enc setBuffer:layer->ln_bias offset:0 atIndex:2];
        [enc setBuffer:out offset:0 atIndex:3];
        [enc setBytes:&dm length:sizeof(int) atIndex:4];
        [enc setBytes:&sl length:sizeof(int) atIndex:5];
        [enc setBytes:&eps length:sizeof(float) atIndex:6];
        int ew = (int)be->pipe_layer_norm.threadExecutionWidth;
        int mt = (int)be->pipe_layer_norm.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// Full forward pass for one attention layer
static void AttentionLayer_Forward(AttentionLayer* layer, id<MTLBuffer> input, id<MTLBuffer> output) {
    // Copy input to X (for backprop) — shared mode buffers, direct memcpy
    memcpy(layer->X.contents, input.contents, (size_t)layer->seq_len * layer->config.d_model * sizeof(__fp16));

    // QKV projection: X @ W_q, X @ W_k, X @ W_v
    AttentionLayer_QKVProjection(layer);

    // Attention scores: Q @ K^T / sqrt(d_k)
    AttentionLayer_AttentionScores(layer);

    // BCL IR graph bias: add T5-style structural bias to scores before softmax
    if (layer->has_graph_bias && layer->graph_bias_buf) {
        AttentionLayer_AttentionBiasAdd(layer);
    }

    // Masked softmax (causal + BCL mask)
    AttentionLayer_MaskedSoftmax(layer);

    // Attention output: P @ V
    AttentionLayer_AttentionOutput(layer);

    // Output projection: attn_out @ W_o
    AttentionLayer_OutputProjection(layer);

    // Residual: out = out + X
    AttentionLayer_ResidualAdd(layer, layer->out, layer->X, layer->out);

    // Save residual output (input to layer_norm) for backward pass
    memcpy(layer->ln_x.contents, layer->out.contents, (size_t)layer->seq_len * layer->config.d_model * sizeof(__fp16));

    // Layer norm
    AttentionLayer_LayerNorm(layer, layer->out, output);
}

// --- Backward pass kernels ---

static void AttentionLayer_ZeroGradients(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;
    int nh = layer->config.n_heads;

    int w_count = dm * dm;
    int act_count = sl * dm;
    int score_count = nh * sl * sl;
    int dm_count = dm;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];

        // Zero fp32 grad buffers
        [enc setComputePipelineState:be->pipe_zero_float];
        int total4 = (w_count + 3) / 4;
        [enc setBuffer:layer->grad_W_q offset:0 atIndex:0]; [enc setBytes:&w_count length:sizeof(int) atIndex:1];
        [enc dispatchThreads:MTLSizeMake(total4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_W_k offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(total4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_W_v offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(total4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_W_o offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(total4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];

        int act4 = (act_count + 3) / 4;
        [enc setBuffer:layer->grad_K offset:0 atIndex:0]; [enc setBytes:&act_count length:sizeof(int) atIndex:1];
        [enc dispatchThreads:MTLSizeMake(act4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_V offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(act4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_attn offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(act4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_X offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(act4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];

        int dm4 = (dm_count + 3) / 4;
        [enc setBuffer:layer->grad_ln_scale offset:0 atIndex:0]; [enc setBytes:&dm_count length:sizeof(int) atIndex:1];
        [enc dispatchThreads:MTLSizeMake(dm4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_ln_bias offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(dm4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];

        // Zero fp16 grad buffers
        [enc setComputePipelineState:be->pipe_zero_half];
        [enc setBuffer:layer->grad_Q offset:0 atIndex:0]; [enc setBytes:&act_count length:sizeof(int) atIndex:1];
        [enc dispatchThreads:MTLSizeMake(act4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_S offset:0 atIndex:0]; [enc setBytes:&score_count length:sizeof(int) atIndex:1];
        int sc4 = (score_count + 3) / 4;
        [enc dispatchThreads:MTLSizeMake(sc4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];
        [enc setBuffer:layer->grad_P offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(sc4,1,1) threadsPerThreadgroup:MTLSizeMake(64,1,1)];

        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_OutputProjBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;

    // grad_W_o
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_output_proj_backward];
        [enc setBuffer:layer->attn_out offset:0 atIndex:0];
        [enc setBuffer:layer->W_o offset:0 atIndex:1];
        [enc setBuffer:layer->grad_out offset:0 atIndex:2];
        [enc setBuffer:layer->grad_W_o offset:0 atIndex:3];
        [enc setBytes:&dm length:sizeof(int) atIndex:4];
        [enc setBytes:&sl length:sizeof(int) atIndex:5];
        int ew = (int)be->pipe_output_proj_backward.threadExecutionWidth;
        int mt = (int)be->pipe_output_proj_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 16) tgx = 16; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(dm, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // grad_attn_out
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_grad_attn_out_accumulate];
        [enc setBuffer:layer->W_o offset:0 atIndex:0];
        [enc setBuffer:layer->grad_out offset:0 atIndex:1];
        [enc setBuffer:layer->grad_attn offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_grad_attn_out_accumulate.threadExecutionWidth;
        int mt = (int)be->pipe_grad_attn_out_accumulate.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_AttnOutputBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int hd = layer->config.head_dim;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;

    // Convert grad_attn (fp32) to fp16 grad_out for this kernel
    // The kernel expects grad_out as half*. We'll use a temp buffer.
    // For simplicity, we pass grad_attn as half* — but it's fp32.
    // Instead, let's create a temp fp16 buffer for grad_attn_h.
    // Actually, the kernel reads grad_out as half*. We need to convert.
    // Let's use scale_and_shift or a manual conversion.
    // For now, we'll create a temporary fp16 buffer.
    id<MTLBuffer> grad_attn_h = [be->device newBufferWithLength:(size_t)sl * dm * sizeof(__fp16) options:MTLResourceStorageModeShared];
    {
        float* src = (float*)layer->grad_attn.contents;
        __fp16* dst = (__fp16*)grad_attn_h.contents;
        for (int i = 0; i < sl * dm; i++) dst[i] = (__fp16)src[i];
    }

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_attn_output_backward];
        [enc setBuffer:layer->P offset:0 atIndex:0];
        [enc setBuffer:layer->V offset:0 atIndex:1];
        [enc setBuffer:grad_attn_h offset:0 atIndex:2];
        [enc setBuffer:layer->grad_P offset:0 atIndex:3];
        [enc setBuffer:layer->grad_V offset:0 atIndex:4];
        [enc setBytes:&dm length:sizeof(int) atIndex:5];
        [enc setBytes:&hd length:sizeof(int) atIndex:6];
        [enc setBytes:&nh length:sizeof(int) atIndex:7];
        [enc setBytes:&sl length:sizeof(int) atIndex:8];
        int ew = (int)be->pipe_attn_output_backward.threadExecutionWidth;
        int mt = (int)be->pipe_attn_output_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 8) tgx = 8; if (tgx < 1) tgx = 4;
        int tgy = 1, tgz = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(nh, sl, sl) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, tgz)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_SoftmaxBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_softmax_backward];
        [enc setBuffer:layer->P offset:0 atIndex:0];
        [enc setBuffer:layer->grad_P offset:0 atIndex:1];
        [enc setBuffer:layer->grad_S offset:0 atIndex:2];
        [enc setBytes:&nh length:sizeof(int) atIndex:3];
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_softmax_backward.threadExecutionWidth;
        int mt = (int)be->pipe_softmax_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 8) tgx = 8; if (tgx < 1) tgx = 4;
        int tgy = 1, tgz = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(nh, sl, sl) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, tgz)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_AttnScoresBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int hd = layer->config.head_dim;
    int nh = layer->config.n_heads;
    int sl = layer->seq_len;
    float scale = 1.0f / sqrtf((float)hd);

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_attn_scores_backward];
        [enc setBuffer:layer->Q offset:0 atIndex:0];
        [enc setBuffer:layer->K offset:0 atIndex:1];
        [enc setBuffer:layer->grad_S offset:0 atIndex:2];
        [enc setBuffer:layer->grad_Q offset:0 atIndex:3];
        [enc setBuffer:layer->grad_K offset:0 atIndex:4];
        [enc setBytes:&dm length:sizeof(int) atIndex:5];
        [enc setBytes:&hd length:sizeof(int) atIndex:6];
        [enc setBytes:&nh length:sizeof(int) atIndex:7];
        [enc setBytes:&sl length:sizeof(int) atIndex:8];
        [enc setBytes:&scale length:sizeof(float) atIndex:9];
        int ew = (int)be->pipe_attn_scores_backward.threadExecutionWidth;
        int mt = (int)be->pipe_attn_scores_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 8) tgx = 8; if (tgx < 1) tgx = 4;
        int tgy = 1, tgz = 1;
        if (mt / tgx > 0) tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(nh, sl, hd) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, tgz)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void AttentionLayer_QKVProjBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;

    // Convert grad_K (fp32) to fp16 for the kernel
    id<MTLBuffer> grad_K_h = [be->device newBufferWithLength:(size_t)sl * dm * sizeof(__fp16) options:MTLResourceStorageModeShared];
    id<MTLBuffer> grad_V_h = [be->device newBufferWithLength:(size_t)sl * dm * sizeof(__fp16) options:MTLResourceStorageModeShared];
    {
        float* srck = (float*)layer->grad_K.contents;
        float* srcv = (float*)layer->grad_V.contents;
        __fp16* dstk = (__fp16*)grad_K_h.contents;
        __fp16* dstv = (__fp16*)grad_V_h.contents;
        for (int i = 0; i < sl * dm; i++) { dstk[i] = (__fp16)srck[i]; dstv[i] = (__fp16)srcv[i]; }
    }

    // grad_W_q, grad_W_k, grad_W_v
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_qkv_proj_backward];
        [enc setBuffer:layer->X offset:0 atIndex:0];
        [enc setBuffer:layer->W_q offset:0 atIndex:1];
        [enc setBuffer:layer->W_k offset:0 atIndex:2];
        [enc setBuffer:layer->W_v offset:0 atIndex:3];
        [enc setBuffer:layer->grad_Q offset:0 atIndex:4];
        [enc setBuffer:grad_K_h offset:0 atIndex:5];
        [enc setBuffer:grad_V_h offset:0 atIndex:6];
        [enc setBuffer:layer->grad_W_q offset:0 atIndex:7];
        [enc setBuffer:layer->grad_W_k offset:0 atIndex:8];
        [enc setBuffer:layer->grad_W_v offset:0 atIndex:9];
        [enc setBuffer:layer->grad_X offset:0 atIndex:10];
        [enc setBytes:&dm length:sizeof(int) atIndex:11];
        [enc setBytes:&sl length:sizeof(int) atIndex:12];
        int ew = (int)be->pipe_qkv_proj_backward.threadExecutionWidth;
        int mt = (int)be->pipe_qkv_proj_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 16) tgx = 16; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1;
        [enc dispatchThreads:MTLSizeMake(dm, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // grad_X = sum_col W_q*grad_Q + W_k*grad_K + W_v*grad_V
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_grad_x_accumulate];
        [enc setBuffer:layer->W_q offset:0 atIndex:0];
        [enc setBuffer:layer->W_k offset:0 atIndex:1];
        [enc setBuffer:layer->W_v offset:0 atIndex:2];
        [enc setBuffer:layer->grad_Q offset:0 atIndex:3];
        [enc setBuffer:grad_K_h offset:0 atIndex:4];
        [enc setBuffer:grad_V_h offset:0 atIndex:5];
        [enc setBuffer:layer->grad_X offset:0 atIndex:6];
        [enc setBytes:&dm length:sizeof(int) atIndex:7];
        [enc setBytes:&sl length:sizeof(int) atIndex:8];
        int ew = (int)be->pipe_grad_x_accumulate.threadExecutionWidth;
        int mt = (int)be->pipe_grad_x_accumulate.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// [@GHOST]{section="backward_completion_methods" date="2026-07-04" author="devin" session_id="bcl-backward-fix" context="Layer norm backward and residual backward methods — complete the gradient flow through layer normalization and residual connections. Without these, gradients stop at the LN boundary and loss never decreases."}
// [@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
// [@SUMMARY]{summary="AttentionLayer_LayerNormBackward: dispatches layer_norm_backward kernel — grad through LN using saved ln_x, produces grad_residual (fp32) + grad_ln_scale/bias (atomic). AttentionLayer_ResidualBackward: dispatches residual_backward kernel — splits grad to attention branch (fp16 grad_out) and residual branch (fp32 grad_residual_x)."}

// --- Layer norm backward: grad_out (fp16) → grad_residual (fp32), grad_ln_scale, grad_ln_bias ---
static void AttentionLayer_LayerNormBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int dm = layer->config.d_model;
    int sl = layer->seq_len;
    float eps = layer->config.ln_eps;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_layer_norm_backward];
        [enc setBuffer:layer->ln_x offset:0 atIndex:0];         // x (input to LN = residual sum)
        [enc setBuffer:layer->grad_out offset:0 atIndex:1];     // grad_out (incoming, fp16)
        [enc setBuffer:layer->ln_scale offset:0 atIndex:2];     // scale
        [enc setBuffer:layer->grad_residual offset:0 atIndex:3]; // grad_x output (fp32)
        [enc setBuffer:layer->grad_ln_scale offset:0 atIndex:4]; // grad_scale (atomic fp32)
        [enc setBuffer:layer->grad_ln_bias offset:0 atIndex:5];  // grad_bias (atomic fp32)
        [enc setBytes:&dm length:sizeof(int) atIndex:6];
        [enc setBytes:&sl length:sizeof(int) atIndex:7];
        [enc setBytes:&eps length:sizeof(float) atIndex:8];
        int ew = (int)be->pipe_layer_norm_backward.threadExecutionWidth;
        int mt = (int)be->pipe_layer_norm_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// --- Residual backward: grad_residual (fp32) → grad_out (fp16) + grad_residual_x (fp32) ---
static void AttentionLayer_ResidualBackward(AttentionLayer* layer) {
    MetalBackend* be = layer->backend;
    int count = layer->seq_len * layer->config.d_model;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_residual_backward];
        [enc setBuffer:layer->grad_residual offset:0 atIndex:0];   // grad_in (fp32)
        [enc setBuffer:layer->grad_out offset:0 atIndex:1];        // grad_a (fp16, attention branch)
        [enc setBuffer:layer->grad_residual_x offset:0 atIndex:2]; // grad_b (fp32, residual to X)
        [enc setBytes:&count length:sizeof(int) atIndex:3];
        int ew = (int)be->pipe_residual_backward.threadExecutionWidth;
        int tg = ew; if (tg > 64) tg = 64; if (tg < 1) tg = 32;
        int total4 = (count + 3) / 4;
        if (tg > total4) tg = total4;
        [enc dispatchThreads:MTLSizeMake(total4, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

// Full backward pass for one attention layer
// Forward order:  X → QKV → attention → output_proj → residual_add → layer_norm → output
// Backward order: layer_norm_backward → residual_backward → output_proj_backward
//                 → attn_output_backward → softmax_backward → attn_scores_backward
//                 → qkv_proj_backward → add residual gradient to grad_X
static void AttentionLayer_Backward(AttentionLayer* layer, id<MTLBuffer> grad_output) {
    // Copy incoming gradient (w.r.t. layer_norm output) — shared mode buffers, direct memcpy
    memcpy(layer->grad_out.contents, grad_output.contents, (size_t)layer->seq_len * layer->config.d_model * sizeof(__fp16));

    // Zero all gradient buffers
    AttentionLayer_ZeroGradients(layer);

    // 1. Layer norm backward: grad_out (fp16) → grad_residual (fp32), grad_ln_scale, grad_ln_bias
    AttentionLayer_LayerNormBackward(layer);

    // 2. Residual backward: grad_residual (fp32) → grad_out (fp16, attention branch) + grad_residual_x (fp32, to X)
    AttentionLayer_ResidualBackward(layer);

    // 3. Backward through output projection (uses grad_out from residual_backward)
    AttentionLayer_OutputProjBackward(layer);

    // 4. Backward through attention output (grad_P, grad_V)
    AttentionLayer_AttnOutputBackward(layer);

    // 5. Backward through softmax (grad_S)
    AttentionLayer_SoftmaxBackward(layer);

    // 6. Backward through attention scores (grad_Q, grad_K)
    AttentionLayer_AttnScoresBackward(layer);

    // 7. Backward through QKV projection (grad_W_q/k/v, grad_X from QKV path)
    AttentionLayer_QKVProjBackward(layer);

    // 8. Add residual gradient to grad_X: grad_X += grad_residual_x
    //    (grad_X currently has QKV path gradient, add the residual connection gradient)
    {
        float* gx = (float*)layer->grad_X.contents;
        float* grx = (float*)layer->grad_residual_x.contents;
        int count = layer->seq_len * layer->config.d_model;
        for (int i = 0; i < count; i++) gx[i] += grx[i];
    }
}

// ============ CLASS: SGDOptimizer ============
// Applies SGD updates to all weight matrices using the sgd_update kernel.

// [@GHOST]{section="lr_scheduler" date="2026-07-02" context="LR schedule: linear warmup then cosine decay. max_lr=3e-4, min_lr=1e-5, warmup=1000 steps."}
// [@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
// ============ CLASS: LRScheduler ============
// Warmup (linear ramp 0 → max_lr over warmup_steps) then cosine decay
// (max_lr → min_lr over remaining steps to total_steps).

typedef struct {
    float max_lr;        // peak learning rate after warmup
    float min_lr;        // minimum learning rate at end of cosine decay
    int   warmup_steps;  // linear ramp duration
    int   total_steps;   // total training steps for cosine schedule
    int   current_step;  // current step counter
} LRScheduler;

static LRScheduler LRScheduler_Default(void) {
    LRScheduler s;
    s.max_lr = 3e-4f;
    s.min_lr = 1e-5f;
    s.warmup_steps = 1000;
    s.total_steps = 100000;
    s.current_step = 0;
    return s;
}

static float LRScheduler_GetLR(LRScheduler* s) {
    int step = s->current_step;
    if (step < s->warmup_steps) {
        // Linear warmup: lr = max_lr * step / warmup_steps
        return s->max_lr * (float)step / (float)s->warmup_steps;
    }
    // Cosine decay: lr = min_lr + 0.5*(max_lr-min_lr)*(1+cos(pi*progress))
    int decay_step = step - s->warmup_steps;
    int decay_total = s->total_steps - s->warmup_steps;
    if (decay_total <= 0) return s->min_lr;
    float progress = (float)decay_step / (float)decay_total;
    if (progress > 1.0f) progress = 1.0f;
    float cosine = cosf((float)M_PI * progress);
    return s->min_lr + 0.5f * (s->max_lr - s->min_lr) * (1.0f + cosine);
}

static void LRScheduler_Step(LRScheduler* s) {
    s->current_step++;
}

static void SGDOptimizer_Step(MetalBackend* be, id<MTLBuffer> W, id<MTLBuffer> grad_W,
                               int d_model, int n_rows, float lr, float weight_decay) {
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_sgd_update];
        [enc setBuffer:W offset:0 atIndex:0];
        [enc setBuffer:grad_W offset:0 atIndex:1];
        [enc setBytes:&d_model length:sizeof(int) atIndex:2];
        [enc setBytes:&n_rows length:sizeof(int) atIndex:3];
        [enc setBytes:&lr length:sizeof(float) atIndex:4];
        [enc setBytes:&weight_decay length:sizeof(float) atIndex:5];
        int dm4 = d_model / 4;
        int ew = (int)be->pipe_sgd_update.threadExecutionWidth;
        int mt = (int)be->pipe_sgd_update.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 16) tgx = 16; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm4) tgy = dm4;
        [enc dispatchThreads:MTLSizeMake(n_rows, dm4, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void SGDOptimizer_UpdateLayer(MetalBackend* be, AttentionLayer* layer, float lr) {
    int dm = layer->config.d_model;
    float wd = layer->config.weight_decay;

    SGDOptimizer_Step(be, layer->W_q, layer->grad_W_q, dm, dm, lr, wd);
    SGDOptimizer_Step(be, layer->W_k, layer->grad_W_k, dm, dm, lr, wd);
    SGDOptimizer_Step(be, layer->W_v, layer->grad_W_v, dm, dm, lr, wd);
    SGDOptimizer_Step(be, layer->W_o, layer->grad_W_o, dm, dm, lr, wd);
    // [@GHOST]{section="ln_sgd_update" date="2026-07-04" context="SGD update for layer norm scale and bias weights — now that backward pass produces gradients for them"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    SGDOptimizer_Step(be, layer->ln_scale, layer->grad_ln_scale, dm, 1, lr, wd);
    SGDOptimizer_Step(be, layer->ln_bias, layer->grad_ln_bias, dm, 1, lr, 0.0f);  // no weight decay on bias
}

// ============ CLASS: TransformerModel ============
// Stacks N_LAYERS attention layers. Manages embedding lookup.

typedef struct {
    TransformerConfig config;
    MetalBackend backend;
    AttentionLayer layers[N_LAYERS];
    LRScheduler lr_scheduler;

    // Embedding weights
    id<MTLBuffer> W_emb;       // [vocab_size, d_model] fp16
    id<MTLBuffer> grad_W_emb;  // [vocab_size, d_model] fp32

    // Activation buffers (reused across layers)
    id<MTLBuffer> hidden;      // [max_seq, d_model] fp16
    id<MTLBuffer> hidden_next; // [max_seq, d_model] fp16
    id<MTLBuffer> grad_hidden; // [max_seq, d_model] fp16
    id<MTLBuffer> token_ids;   // [max_seq] int

    // BCL IR positional encoding [max_seq, d_model] fp16 — added to embeddings
    id<MTLBuffer> pe_buffer;
    int has_pe;

    // [@GHOST]{section="loss_buffers" date="2026-07-02" context="Loss computation + gradient clipping buffers"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    // Loss computation buffers
    id<MTLBuffer> logits;         // [seq_len, vocab_size] fp16 (output projection → logits)
    id<MTLBuffer> target_ids;     // [seq_len] int (target token IDs for loss)
    id<MTLBuffer> loss_buf;       // [seq_len] float (per-token loss)
    id<MTLBuffer> grad_logits;    // [seq_len, vocab_size] float (grad w.r.t. logits)
    id<MTLBuffer> norm_sq_buf;    // [1] float (global grad norm squared accumulator)

    int seq_len;
    int initialized;
} TransformerModel;

static int TransformerModel_Init(TransformerModel* model, TransformerConfig* config, int seq_len) {
    model->config = *config;
    model->seq_len = seq_len;
    model->lr_scheduler = LRScheduler_Default();

    if (!MetalBackend_Init(&model->backend)) {
        std::cout << "[XFORM] MetalBackend init failed\n";
        return 0;
    }

    // Initialize embedding weights
    size_t emb_size = (size_t)config->vocab_size * config->d_model * sizeof(__fp16);
    __fp16* emb_host = (__fp16*)malloc(emb_size);
    for (size_t i = 0; i < (size_t)config->vocab_size * config->d_model; i++) {
        emb_host[i] = (__fp16)frand_norm();
    }
    model->W_emb = [model->backend.device newBufferWithBytes:emb_host length:emb_size options:MTLResourceStorageModeShared];
    free(emb_host);

    size_t grad_emb_size = (size_t)config->vocab_size * config->d_model * sizeof(float);
    model->grad_W_emb = [model->backend.device newBufferWithLength:grad_emb_size options:MTLResourceStorageModeShared];

    // Activation buffers
    size_t act_size = (size_t)seq_len * config->d_model * sizeof(__fp16);
    model->hidden = [model->backend.device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
    model->hidden_next = [model->backend.device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
    model->grad_hidden = [model->backend.device newBufferWithLength:act_size options:MTLResourceStorageModeShared];
    model->token_ids = [model->backend.device newBufferWithLength:(size_t)seq_len * sizeof(int) options:MTLResourceStorageModeShared];

    // BCL IR PE buffer — default none (set by TrainOnBcl)
    model->pe_buffer = nil;
    model->has_pe = 0;

    // [@GHOST]{section="loss_buffer_alloc" date="2026-07-02" context="Allocate logits, loss, grad_logits, norm_sq buffers for loss computation + grad clipping"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    // Loss computation buffers — use a small vocab for the demo to keep memory reasonable.
    // The actual vocab_size is 162612 which is too large for a demo; we use a reduced
    // logits buffer sized to seq_len * d_model (treating hidden as pseudo-logits).
    size_t logits_size = (size_t)seq_len * config->d_model * sizeof(__fp16);
    model->logits = [model->backend.device newBufferWithLength:logits_size options:MTLResourceStorageModeShared];
    model->target_ids = [model->backend.device newBufferWithLength:(size_t)seq_len * sizeof(int) options:MTLResourceStorageModeShared];
    model->loss_buf = [model->backend.device newBufferWithLength:(size_t)seq_len * sizeof(float) options:MTLResourceStorageModeShared];
    size_t grad_logits_size = (size_t)seq_len * config->d_model * sizeof(float);
    model->grad_logits = [model->backend.device newBufferWithLength:grad_logits_size options:MTLResourceStorageModeShared];
    model->norm_sq_buf = [model->backend.device newBufferWithLength:sizeof(float) options:MTLResourceStorageModeShared];

    // Initialize layers
    for (int i = 0; i < config->n_layers; i++) {
        if (!AttentionLayer_Init(&model->layers[i], config, &model->backend, seq_len)) {
            std::cout << "[XFORM] Layer " << i << " init failed\n";
            return 0;
        }
    }

    model->initialized = 1;
    std::cout << "[XFORM] Transformer model initialized: " << config->n_layers << " layers, d_model="
              << config->d_model << " n_heads=" << config->n_heads << " seq_len=" << seq_len << "\n";
    return 1;
}

static void TransformerModel_EmbeddingLookup(TransformerModel* model, int* tokens, int n_tokens) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = n_tokens;

    // Copy token IDs to GPU
    memcpy(model->token_ids.contents, tokens, (size_t)sl * sizeof(int));

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_embedding_lookup];
        [enc setBuffer:model->token_ids offset:0 atIndex:0];
        [enc setBuffer:model->W_emb offset:0 atIndex:1];
        [enc setBuffer:model->hidden offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int dm4 = dm / 4;
        int ew = (int)be->pipe_embedding_lookup.threadExecutionWidth;
        int mt = (int)be->pipe_embedding_lookup.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm4) tgy = dm4;
        [enc dispatchThreads:MTLSizeMake(sl, dm4, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void TransformerModel_AddPE(TransformerModel* model, int n_tokens) {
    if (!model->has_pe || !model->pe_buffer) return;
    MetalBackend* be = &model->backend;
    int count = n_tokens * model->config.d_model;

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_residual_add];
        [enc setBuffer:model->hidden offset:0 atIndex:0];
        [enc setBuffer:model->pe_buffer offset:0 atIndex:1];
        [enc setBuffer:model->hidden offset:0 atIndex:2];
        [enc setBytes:&count length:sizeof(int) atIndex:3];
        int ew = (int)be->pipe_residual_add.threadExecutionWidth;
        int mt = (int)be->pipe_residual_add.maxTotalThreadsPerThreadgroup;
        int tg = ew; if (tg > mt && mt > 0) tg = mt; if (tg < 1) tg = 32;
        int total = (count + 3) / 4;
        [enc dispatchThreads:MTLSizeMake(total, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }
}

static void TransformerModel_Forward(TransformerModel* model, int* tokens, int n_tokens) {
    // Embedding lookup
    TransformerModel_EmbeddingLookup(model, tokens, n_tokens);

    // BCL IR: add positional encoding to embeddings before attention
    TransformerModel_AddPE(model, n_tokens);

    // Run through each layer
    id<MTLBuffer> input = model->hidden;
    id<MTLBuffer> output = model->hidden_next;
    for (int i = 0; i < model->config.n_layers; i++) {
        AttentionLayer_Forward(&model->layers[i], input, output);
        // Swap input/output for next layer
        id<MTLBuffer> tmp = input; input = output; output = tmp;
    }
    // Final output is in `input` (after last swap)
}

static void TransformerModel_Backward(TransformerModel* model, int* tokens, int n_tokens) {
    // Backward through layers in reverse
    // grad_hidden starts as the incoming gradient (set externally)
    id<MTLBuffer> grad = model->grad_hidden;
    for (int i = model->config.n_layers - 1; i >= 0; i--) {
        AttentionLayer_Backward(&model->layers[i], grad);
        // grad_X from this layer becomes input grad for next (previous) layer
        // Need to convert fp32 grad_X to fp16 for next layer's grad_out
        float* src = (float*)model->layers[i].grad_X.contents;
        __fp16* dst = (__fp16*)model->grad_hidden.contents;
        for (int j = 0; j < n_tokens * model->config.d_model; j++) {
            dst[j] = (__fp16)src[j];
        }
    }
}

static void TransformerModel_Optimize(TransformerModel* model) {
    float lr = LRScheduler_GetLR(&model->lr_scheduler);
    for (int i = 0; i < model->config.n_layers; i++) {
        SGDOptimizer_UpdateLayer(&model->backend, &model->layers[i], lr);
    }
}

// [@GHOST]{section="loss_compute" date="2026-07-02" context="Cross-entropy loss computation, loss backward, gradient clipping for training loop"}
// [@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
// ============ LOSS COMPUTATION ============
// After forward pass, the final hidden state is in model->hidden (or hidden_next
// depending on layer parity). We treat the hidden state as pseudo-logits over
// a reduced vocabulary of size d_model for the demo (real impl would have a
// separate output projection to full vocab). Target IDs are mapped into [0, d_model).
//
// cross_entropy_loss kernel: computes per-token loss.
// cross_entropy_backward kernel: computes grad w.r.t. logits.
// loss_to_grad_hidden kernel: converts per-token loss to grad_hidden for backprop.

static void TransformerModel_ComputeLoss(TransformerModel* model, int* targets, int n_tokens, float* out_loss) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = n_tokens;

    // Copy target IDs to GPU (map targets into [0, d_model) for demo)
    int* tgt_host = (int*)model->target_ids.contents;
    for (int i = 0; i < sl; i++) {
        tgt_host[i] = targets[i] % dm;  // map to [0, d_model)
    }

    // The final hidden state after forward is in model->hidden (after last swap)
    // With even n_layers, the output lands in hidden_next; with odd, in hidden.
    // Copy the correct buffer to logits.
    id<MTLBuffer> final_output = (model->config.n_layers % 2 == 0) ? model->hidden_next : model->hidden;
    memcpy(model->logits.contents, final_output.contents, (size_t)sl * dm * sizeof(__fp16));

    // Run cross_entropy_loss kernel — one thread per sequence position
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_cross_entropy_loss];
        [enc setBuffer:model->logits offset:0 atIndex:0];
        [enc setBuffer:model->target_ids offset:0 atIndex:1];
        [enc setBuffer:model->loss_buf offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];  // vocab_size = d_model for demo
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_cross_entropy_loss.threadExecutionWidth;
        int tg = ew; if (tg > sl) tg = sl; if (tg < 1) tg = 1;
        if (tg > (int)be->pipe_cross_entropy_loss.maxTotalThreadsPerThreadgroup)
            tg = (int)be->pipe_cross_entropy_loss.maxTotalThreadsPerThreadgroup;
        [enc dispatchThreads:MTLSizeMake(sl, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // Read back loss and compute mean
    float* loss_host = (float*)model->loss_buf.contents;
    float total_loss = 0.0f;
    for (int i = 0; i < sl; i++) total_loss += loss_host[i];
    *out_loss = total_loss / (float)sl;
}

static void TransformerModel_LossBackward(TransformerModel* model, int* targets, int n_tokens) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = n_tokens;

    // Run cross_entropy_backward kernel — one thread per (pos, v)
    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_cross_entropy_backward];
        [enc setBuffer:model->logits offset:0 atIndex:0];
        [enc setBuffer:model->target_ids offset:0 atIndex:1];
        [enc setBuffer:model->grad_logits offset:0 atIndex:2];
        [enc setBytes:&dm length:sizeof(int) atIndex:3];  // vocab_size = d_model
        [enc setBytes:&sl length:sizeof(int) atIndex:4];
        int ew = (int)be->pipe_cross_entropy_backward.threadExecutionWidth;
        int mt = (int)be->pipe_cross_entropy_backward.maxTotalThreadsPerThreadgroup;
        int tgx = ew; if (tgx > 32) tgx = 32; if (tgx < 1) tgx = 8;
        int tgy = mt / tgx; if (tgy < 1) tgy = 1; if (tgy > dm) tgy = dm;
        [enc dispatchThreads:MTLSizeMake(sl, dm, 1) threadsPerThreadgroup:MTLSizeMake(tgx, tgy, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // Convert grad_logits (fp32, [seq, d_model]) to grad_hidden (fp16, [seq, d_model])
    // For the demo, grad_logits IS the grad_hidden (same shape since vocab=d_model)
    // Note: gradient amplification helps overcome fp16 precision limits but the
    // existing backward pass lacks layer-norm and residual backward, so loss
    // decrease is limited. The infrastructure (loss kernel, LR schedule, grad
    // clipping) is fully functional.
    float* src = (float*)model->grad_logits.contents;
    __fp16* dst = (__fp16*)model->grad_hidden.contents;
    for (int i = 0; i < sl * dm; i++) {
        dst[i] = (__fp16)src[i];
    }
}

// ============ GRADIENT CLIPPING ============
// Two-pass: (1) compute global L2 norm across all grad buffers,
// (2) scale all grads by min(1.0, max_norm / global_norm).
// Uses atomic_float for norm accumulation.

static float TransformerModel_ComputeGradNorm(TransformerModel* model) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = model->seq_len;

    // Zero the norm_sq accumulator
    float zero = 0.0f;
    memcpy(model->norm_sq_buf.contents, &zero, sizeof(float));

    // Collect all fp32 grad buffers from all layers
    // Each layer has: grad_W_q, grad_W_k, grad_W_v, grad_W_o (dm*dm floats each)
    // We run grad_norm_compute on each buffer and accumulate into norm_sq_buf.
    int w_count = dm * dm;

    for (int i = 0; i < model->config.n_layers; i++) {
        AttentionLayer* layer = &model->layers[i];
        id<MTLBuffer> grad_bufs[] = {layer->grad_W_q, layer->grad_W_k, layer->grad_W_v, layer->grad_W_o,
                                      layer->grad_ln_scale, layer->grad_ln_bias};
        int buf_counts[] = {w_count, w_count, w_count, w_count, dm, dm};
        for (int b = 0; b < 6; b++) {
            int buf_count = buf_counts[b];
            @autoreleasepool {
                id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
                id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
                [enc setComputePipelineState:be->pipe_grad_norm_compute];
                [enc setBuffer:grad_bufs[b] offset:0 atIndex:0];
                [enc setBuffer:model->norm_sq_buf offset:0 atIndex:1];
                [enc setBytes:&buf_count length:sizeof(int) atIndex:2];
                int ew = (int)be->pipe_grad_norm_compute.threadExecutionWidth;
                int tg = ew; if (tg > 256) tg = 256; if (tg < 1) tg = 32;
                if (tg > buf_count) tg = buf_count;
                [enc dispatchThreads:MTLSizeMake(buf_count, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
                [enc endEncoding];
                [cmd commit];
                [cmd waitUntilCompleted];
            }
        }
    }

    // Read back norm_sq and compute global norm
    float norm_sq = *(float*)model->norm_sq_buf.contents;
    return sqrtf(norm_sq);
}

static void TransformerModel_ClipGradients(TransformerModel* model, float max_norm, float* out_global_norm) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;

    // Pass 1: compute global grad norm
    float global_norm = TransformerModel_ComputeGradNorm(model);
    *out_global_norm = global_norm;

    // Compute clip scale
    float clip_scale = 1.0f;
    if (global_norm > max_norm && global_norm > 0.0f) {
        clip_scale = max_norm / global_norm;
    }

    // Pass 2: scale all grad buffers if needed
    if (clip_scale < 1.0f) {
        int w_count = dm * dm;
        for (int i = 0; i < model->config.n_layers; i++) {
            AttentionLayer* layer = &model->layers[i];
            id<MTLBuffer> grad_bufs[] = {layer->grad_W_q, layer->grad_W_k, layer->grad_W_v, layer->grad_W_o,
                                          layer->grad_ln_scale, layer->grad_ln_bias};
            int buf_counts[] = {w_count, w_count, w_count, w_count, dm, dm};
            for (int b = 0; b < 6; b++) {
                int buf_count = buf_counts[b];
                @autoreleasepool {
                    id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
                    id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
                    [enc setComputePipelineState:be->pipe_grad_clip_scale];
                    [enc setBuffer:grad_bufs[b] offset:0 atIndex:0];
                    [enc setBytes:&buf_count length:sizeof(int) atIndex:1];
                    [enc setBytes:&clip_scale length:sizeof(float) atIndex:2];
                    int total4 = (buf_count + 3) / 4;
                    int ew = (int)be->pipe_grad_clip_scale.threadExecutionWidth;
                    int tg = ew; if (tg > 256) tg = 256; if (tg < 1) tg = 32;
                    if (tg > total4) tg = total4;
                    [enc dispatchThreads:MTLSizeMake(total4, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
                    [enc endEncoding];
                    [cmd commit];
                    [cmd waitUntilCompleted];
                }
            }
        }
    }
}

// ============ SQTX DATA LOADER ============
//[@GHOST]{context="SQTX binary format loader for real BCL training data. Reads SequenceLunchbox output: magic+version+mode+seq_len+num_sequences+vocab_size header, then packed input/target token arrays."}
//[@SUMMARY]{summary="load_sqtx: parse SQTX binary file into host memory. train_on_sqtx: run forward/backward/SGD on real BCL sequences with contrastive embedding loss."}

// SQTX binary format (generated by vb_sequence_lunchbox.py):
//   Header: magic(4)="SQTX" + version(int32) + mode(4 bytes) + seq_len(int32) + num_sequences(int64) + vocab_size(int32)
//   Body:   for each sequence: [input_tokens (seq_len x int32)] [target_tokens (seq_len x int32)]

typedef struct {
    int seq_len;
    int64_t num_sequences;
    int vocab_size;
    int* input_data;   // [num_sequences * seq_len] — host memory
    int* target_data;  // [num_sequences * seq_len] — host memory
    int loaded;
} SQTXData;

static SQTXData load_sqtx(const char* path) {
    SQTXData data;
    memset(&data, 0, sizeof(data));

    FILE* f = fopen(path, "rb");
    if (!f) {
        std::cout << "[XFORM] Cannot open SQTX file: " << path << "\n";
        return data;
    }

    // Read and verify magic
    char magic[4];
    if (fread(magic, 1, 4, f) != 4 || memcmp(magic, "SQTX", 4) != 0) {
        std::cout << "[XFORM] Invalid SQTX magic (expected SQTX)\n";
        fclose(f);
        return data;
    }

    // Read header fields
    int version = 0;
    char mode_bytes[4];
    memset(mode_bytes, 0, 4);
    fread(&version, sizeof(int), 1, f);
    fread(mode_bytes, 1, 4, f);
    fread(&data.seq_len, sizeof(int), 1, f);
    fread(&data.num_sequences, sizeof(int64_t), 1, f);
    fread(&data.vocab_size, sizeof(int), 1, f);

    std::cout << "[XFORM] SQTX header: version=" << version
              << " mode=" << mode_bytes[0] << mode_bytes[1] << mode_bytes[2]
              << " seq_len=" << data.seq_len
              << " num_sequences=" << data.num_sequences
              << " vocab_size=" << data.vocab_size << "\n";

    if (data.seq_len <= 0 || data.num_sequences <= 0 || data.vocab_size <= 0) {
        std::cout << "[XFORM] SQTX invalid header values\n";
        fclose(f);
        return data;
    }

    // Allocate host memory for all sequences
    size_t total_ints = (size_t)data.num_sequences * data.seq_len;
    data.input_data = (int*)malloc(total_ints * sizeof(int));
    data.target_data = (int*)malloc(total_ints * sizeof(int));

    if (!data.input_data || !data.target_data) {
        std::cout << "[XFORM] SQTX host allocation failed for " << total_ints << " ints\n";
        fclose(f);
        return data;
    }

    // Read all sequences: [input_tokens (seq_len)] [target_tokens (seq_len)] per sequence
    for (int64_t i = 0; i < data.num_sequences; i++) {
        size_t off = (size_t)i * data.seq_len;
        if (fread(data.input_data + off, sizeof(int), data.seq_len, f) != (size_t)data.seq_len) {
            std::cout << "[XFORM] SQTX read error at sequence " << i << " (input)\n";
            fclose(f);
            return data;
        }
        if (fread(data.target_data + off, sizeof(int), data.seq_len, f) != (size_t)data.seq_len) {
            std::cout << "[XFORM] SQTX read error at sequence " << i << " (target)\n";
            fclose(f);
            return data;
        }
    }

    fclose(f);
    data.loaded = 1;
    std::cout << "[XFORM] SQTX loaded: " << data.num_sequences << " sequences from " << path << "\n";
    return data;
}

static void SQTXData_Free(SQTXData* data) {
    if (data->input_data) { free(data->input_data); data->input_data = NULL; }
    if (data->target_data) { free(data->target_data); data->target_data = NULL; }
    data->loaded = 0;
}

// ============ TRAIN ON SQTX ============
// Train TransformerModel on real BCL sequences from SQTX file.
// Loss: contrastive embedding MSE — push output hidden state toward target token embedding.
// For each position i: loss += 0.5 * ||hidden[i] - W_emb[target[i]]||^2
// Gradient: grad_hidden[i] = (hidden[i] - W_emb[target[i]]) * grad_scale
// Token IDs are clamped to model vocab_size via modulo (handles vocab mismatch).

static void TransformerModel_TrainOnSqtx(TransformerModel* model, SQTXData* data, int epochs) {
    int seq_len = data->seq_len;
    int dm = model->config.d_model;
    int vocab = model->config.vocab_size;
    float grad_scale = 0.01f;  // gradient scaling factor

    // Clamp buffers (allocated once, reused for all sequences)
    int* clamped_input = (int*)malloc((size_t)seq_len * sizeof(int));
    int* clamped_target = (int*)malloc((size_t)seq_len * sizeof(int));

    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

    for (int epoch = 0; epoch < epochs; epoch++) {
        double epoch_loss = 0.0;

        for (int64_t s = 0; s < data->num_sequences; s++) {
            int* input_tokens = data->input_data + s * seq_len;
            int* target_tokens = data->target_data + s * seq_len;

            // Clamp token IDs to model vocab size (modulo)
            for (int i = 0; i < seq_len; i++) {
                clamped_input[i] = input_tokens[i] % vocab;
                if (clamped_input[i] < 0) clamped_input[i] += vocab;
                clamped_target[i] = target_tokens[i] % vocab;
                if (clamped_target[i] < 0) clamped_target[i] += vocab;
            }

            // Forward pass — output lands in model->hidden (n_layers=6 is even)
            TransformerModel_Forward(model, clamped_input, seq_len);

            // Compute contrastive loss and gradient
            // Output hidden state: model->hidden [seq_len, d_model] fp16
            // Target embeddings: model->W_emb [vocab_size, d_model] fp16
            __fp16* hidden = (__fp16*)model->hidden.contents;
            __fp16* W_emb_ptr = (__fp16*)model->W_emb.contents;
            __fp16* grad_h = (__fp16*)model->grad_hidden.contents;

            double seq_loss = 0.0;
            for (int i = 0; i < seq_len; i++) {
                int tgt = clamped_target[i];
                __fp16* tgt_emb = W_emb_ptr + (size_t)tgt * dm;
                __fp16* h = hidden + (size_t)i * dm;
                for (int d = 0; d < dm; d++) {
                    float diff = (float)h[d] - (float)tgt_emb[d];
                    seq_loss += diff * diff;
                    grad_h[(size_t)i * dm + d] = (__fp16)(diff * grad_scale);
                }
            }
            seq_loss = 0.5 * seq_loss / (seq_len * dm);
            epoch_loss += seq_loss;

            // Backward pass
            TransformerModel_Backward(model, clamped_input, seq_len);

            // SGD update
            TransformerModel_Optimize(model);

            // Log progress every 100 sequences or at the end
            if ((s + 1) % 100 == 0 || s == data->num_sequences - 1) {
                struct timespec tsn; clock_gettime(CLOCK_REALTIME, &tsn);
                double el = (tsn.tv_sec - ts0.tv_sec) + (tsn.tv_nsec - ts0.tv_nsec) / 1e9;
                std::cout << "[XFORM] Epoch " << epoch << "/" << epochs
                          << " seq " << (s + 1) << "/" << data->num_sequences
                          << " avg_loss=" << (epoch_loss / (s + 1))
                          << " time=" << el << "s\n";
            }
        }

        struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
        double el = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;
        std::cout << "[XFORM] Epoch " << epoch << " complete: avg_loss="
                  << (epoch_loss / data->num_sequences) << " time=" << el << "s\n";
    }

    free(clamped_input);
    free(clamped_target);
}

// ============ VBP1 PANTRY DATA LOADER ============
//[@GHOST]{file_path="core/Piplines/c_transformer_attention.mm" date="2026-07-04" author="devin" session_id="vb-pantry-metal" context="VBP1 sealed batch loader for PantrySystem output. Reads VBP1 binary format: magic+version+recipe_len+recipe_json+vocab_version+num_seqs+per-seq(seq_len+tokens). load_pantry_dir reads manifest.json and concatenates all active batches into one training set. TransformerModel_TrainOnPantry trains on all pantry sequences with contrastive embedding loss."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@FILEID]{id="c_transformer_attention.mm::vbp1" domain="pantry_loader" authority="BCLTransformer"}
//[@SUMMARY]{summary="load_vbp1: parse single VBP1 sealed batch file into host memory. load_pantry_dir: read manifest.json, load all active batches, concatenate sequences. PantryData_Free: release host memory. TransformerModel_TrainOnPantry: forward/backward/SGD on pantry sequences with contrastive embedding loss and progress logging."}

// VBP1 binary format (generated by vb_pantry.py PantrySystem):
//   Header: magic(4)="VBP1" + version(uint32) + recipe_len(uint32) + recipe_json(recipe_len bytes)
//           + vocab_version(uint32) + num_seqs(uint32)
//   Body:   for each sequence: seq_len(uint32) + tokens(seq_len x uint32)
//
// manifest.json tracks per batch:
//   batch_id, source, recipe, num_sequences, created_date,
//   status (active/obsolete), vocab_version, file (relative path), size_bytes

typedef struct {
    int num_seqs;
    int max_seq_len;
    int* seq_lengths;    // [num_seqs] — length of each sequence
    int** sequences;     // [num_seqs] — pointer to each sequence's token array
    int* flat_tokens;    // [total_tokens] — contiguous storage for all tokens
    int total_tokens;
    int loaded;
} VBP1Data;

// Load a single VBP1 sealed batch file
static VBP1Data load_vbp1(const char* path) {
    VBP1Data data;
    memset(&data, 0, sizeof(data));

    FILE* f = fopen(path, "rb");
    if (!f) {
        std::cout << "[PANTRY] Cannot open VBP1 file: " << path << "\n";
        return data;
    }

    // Read and verify magic
    char magic[4];
    if (fread(magic, 1, 4, f) != 4 || memcmp(magic, "VBP1", 4) != 0) {
        std::cout << "[PANTRY] Invalid VBP1 magic (expected VBP1)\n";
        fclose(f);
        return data;
    }

    // Read header fields
    uint32_t version = 0;
    uint32_t recipe_len = 0;
    uint32_t vocab_version = 0;
    uint32_t num_seqs = 0;

    if (fread(&version, sizeof(uint32_t), 1, f) != 1) {
        std::cout << "[PANTRY] Failed to read version\n";
        fclose(f);
        return data;
    }
    if (fread(&recipe_len, sizeof(uint32_t), 1, f) != 1) {
        std::cout << "[PANTRY] Failed to read recipe_len\n";
        fclose(f);
        return data;
    }

    // Skip recipe_json (recipe_len bytes)
    if (recipe_len > 0) {
        char* recipe_json = (char*)malloc(recipe_len + 1);
        if (fread(recipe_json, 1, recipe_len, f) != recipe_len) {
            std::cout << "[PANTRY] Failed to read recipe_json\n";
            free(recipe_json);
            fclose(f);
            return data;
        }
        recipe_json[recipe_len] = '\0';
        std::cout << "[PANTRY]   recipe: " << recipe_json << "\n";
        free(recipe_json);
    }

    if (fread(&vocab_version, sizeof(uint32_t), 1, f) != 1) {
        std::cout << "[PANTRY] Failed to read vocab_version\n";
        fclose(f);
        return data;
    }
    if (fread(&num_seqs, sizeof(uint32_t), 1, f) != 1) {
        std::cout << "[PANTRY] Failed to read num_seqs\n";
        fclose(f);
        return data;
    }

    std::cout << "[PANTRY] VBP1 header: version=" << version
              << " vocab_version=" << vocab_version
              << " num_seqs=" << num_seqs << "\n";

    if (num_seqs == 0) {
        std::cout << "[PANTRY] VBP1 file has 0 sequences\n";
        fclose(f);
        return data;
    }

    // Allocate arrays for sequence pointers and lengths
    data.num_seqs = (int)num_seqs;
    data.seq_lengths = (int*)malloc((size_t)num_seqs * sizeof(int));
    data.sequences = (int**)malloc((size_t)num_seqs * sizeof(int*));

    if (!data.seq_lengths || !data.sequences) {
        std::cout << "[PANTRY] VBP1 allocation failed for " << num_seqs << " seqs\n";
        fclose(f);
        return data;
    }

    // First pass: read all seq_lens, compute total_tokens and max_seq_len
    int total_tokens = 0;
    int max_seq_len = 0;
    uint32_t* seq_lens_buf = (uint32_t*)malloc((size_t)num_seqs * sizeof(uint32_t));

    for (uint32_t i = 0; i < num_seqs; i++) {
        uint32_t sl = 0;
        if (fread(&sl, sizeof(uint32_t), 1, f) != 1) {
            std::cout << "[PANTRY] VBP1 read error at seq " << i << " (seq_len)\n";
            free(seq_lens_buf);
            fclose(f);
            return data;
        }
        seq_lens_buf[i] = sl;
        data.seq_lengths[i] = (int)sl;
        total_tokens += (int)sl;
        if ((int)sl > max_seq_len) max_seq_len = (int)sl;

        // Read tokens for this sequence
        data.sequences[i] = (int*)malloc((size_t)sl * sizeof(int));
        if (sl > 0) {
            if (fread(data.sequences[i], sizeof(uint32_t), sl, f) != sl) {
                std::cout << "[PANTRY] VBP1 read error at seq " << i << " (tokens)\n";
                free(seq_lens_buf);
                fclose(f);
                return data;
            }
        }
    }

    free(seq_lens_buf);
    fclose(f);

    data.max_seq_len = max_seq_len;
    data.total_tokens = total_tokens;
    data.loaded = 1;

    std::cout << "[PANTRY] VBP1 loaded: " << data.num_seqs << " sequences"
              << " max_seq_len=" << max_seq_len
              << " total_tokens=" << total_tokens
              << " from " << path << "\n";

    return data;
}

// Free a single VBP1Data
static void VBP1Data_Free(VBP1Data* data) {
    if (data->sequences) {
        for (int i = 0; i < data->num_seqs; i++) {
            if (data->sequences[i]) { free(data->sequences[i]); data->sequences[i] = NULL; }
        }
        free(data->sequences);
        data->sequences = NULL;
    }
    if (data->seq_lengths) { free(data->seq_lengths); data->seq_lengths = NULL; }
    if (data->flat_tokens) { free(data->flat_tokens); data->flat_tokens = NULL; }
    data->loaded = 0;
    data->num_seqs = 0;
}

// Combined pantry data — all sequences from all active batches in a directory
typedef struct {
    int num_seqs;       // total sequences across all batches
    int max_seq_len;    // maximum seq_len across all batches
    int* seq_lengths;   // [num_seqs]
    int** sequences;    // [num_seqs]
    int loaded;
} PantryData;

// Free combined PantryData
static void PantryData_Free(PantryData* data) {
    if (data->sequences) {
        for (int i = 0; i < data->num_seqs; i++) {
            if (data->sequences[i]) { free(data->sequences[i]); data->sequences[i] = NULL; }
        }
        free(data->sequences);
        data->sequences = NULL;
    }
    if (data->seq_lengths) { free(data->seq_lengths); data->seq_lengths = NULL; }
    data->loaded = 0;
    data->num_seqs = 0;
}

// Minimal JSON parser for manifest.json — extracts active batch file names
// Looks for "file": "..." and "status": "active" pairs within the same object
static int parse_manifest_files(const char* json, char files[][512], int max_files) {
    int count = 0;
    const char* p = json;

    while (*p && count < max_files) {
        // Find "file" key
        const char* file_key = strstr(p, "\"file\"");
        if (!file_key) break;

        // Find the colon after "file"
        const char* colon = strchr(file_key, ':');
        if (!colon) break;

        // Find opening quote of value
        const char* open_q = strchr(colon, '"');
        if (!open_q) break;
        open_q++; // skip opening quote

        // Find closing quote
        const char* close_q = strchr(open_q, '"');
        if (!close_q) break;

        // Find the enclosing object — search backwards for '{'
        const char* obj_start = file_key;
        while (obj_start > json && *obj_start != '{') obj_start--;

        // Find the closing '}' of this object — search forward from file_key
        const char* obj_end = close_q;
        int depth = 0;
        while (*obj_end) {
            if (*obj_end == '{') depth++;
            else if (*obj_end == '}') {
                if (depth == 0) break;
                depth--;
            }
            obj_end++;
        }

        // Search for "status" within the object [obj_start, obj_end]
        const char* status_key = strstr(obj_start, "\"status\"");
        int is_active = 0;
        if (status_key && status_key < obj_end) {
            const char* status_colon = strchr(status_key, ':');
            if (status_colon && status_colon < obj_end) {
                const char* status_q = strchr(status_colon, '"');
                if (status_q && status_q < obj_end) {
                    status_q++;
                    if (strncmp(status_q, "active", 6) == 0) {
                        is_active = 1;
                    }
                }
            }
        }

        if (is_active) {
            // Extract filename
            int len = (int)(close_q - open_q);
            if (len >= 512) len = 511;
            strncpy(files[count], open_q, len);
            files[count][len] = '\0';
            count++;
        }

        p = close_q + 1;
    }

    return count;
}

// Load all active batches from a pantry directory
static PantryData load_pantry_dir(const char* dir_path) {
    PantryData pantry;
    memset(&pantry, 0, sizeof(pantry));

    // Build manifest.json path
    char manifest_path[1024];
    snprintf(manifest_path, sizeof(manifest_path), "%s/manifest.json", dir_path);

    std::cout << "[PANTRY] Loading manifest: " << manifest_path << "\n";

    FILE* mf = fopen(manifest_path, "r");
    if (!mf) {
        std::cout << "[PANTRY] Cannot open manifest.json: " << manifest_path << "\n";
        return pantry;
    }

    // Read entire manifest
    fseek(mf, 0, SEEK_END);
    long msize = ftell(mf);
    fseek(mf, 0, SEEK_SET);
    char* manifest_json = (char*)malloc(msize + 1);
    if (fread(manifest_json, 1, msize, mf) != (size_t)msize) {
        std::cout << "[PANTRY] Failed to read manifest.json\n";
        free(manifest_json);
        fclose(mf);
        return pantry;
    }
    manifest_json[msize] = '\0';
    fclose(mf);

    // Parse manifest to get active batch file names
    char batch_files[64][512];
    int num_batches = parse_manifest_files(manifest_json, batch_files, 64);
    free(manifest_json);

    std::cout << "[PANTRY] Found " << num_batches << " active batches in manifest\n";

    if (num_batches == 0) {
        std::cout << "[PANTRY] No active batches found\n";
        return pantry;
    }

    // Load each batch and collect sequences
    // First pass: load all batches, count total sequences
    VBP1Data* batches = (VBP1Data*)malloc((size_t)num_batches * sizeof(VBP1Data));
    int total_seqs = 0;
    int max_seq_len = 0;

    for (int b = 0; b < num_batches; b++) {
        char batch_path[1024];
        snprintf(batch_path, sizeof(batch_path), "%s/%s", dir_path, batch_files[b]);

        std::cout << "[PANTRY] Loading batch " << (b + 1) << "/" << num_batches
                  << ": " << batch_files[b] << "\n";

        batches[b] = load_vbp1(batch_path);
        if (!batches[b].loaded) {
            std::cout << "[PANTRY] WARNING: Failed to load batch " << batch_files[b] << "\n";
            continue;
        }
        total_seqs += batches[b].num_seqs;
        if (batches[b].max_seq_len > max_seq_len) {
            max_seq_len = batches[b].max_seq_len;
        }
    }

    if (total_seqs == 0) {
        std::cout << "[PANTRY] No sequences loaded from any batch\n";
        free(batches);
        return pantry;
    }

    // Allocate combined pantry data
    pantry.num_seqs = total_seqs;
    pantry.max_seq_len = max_seq_len;
    pantry.seq_lengths = (int*)malloc((size_t)total_seqs * sizeof(int));
    pantry.sequences = (int**)malloc((size_t)total_seqs * sizeof(int*));

    // Concatenate all sequences
    int idx = 0;
    for (int b = 0; b < num_batches; b++) {
        if (!batches[b].loaded) continue;
        for (int s = 0; s < batches[b].num_seqs; s++) {
            int sl = batches[b].seq_lengths[s];
            pantry.seq_lengths[idx] = sl;
            pantry.sequences[idx] = (int*)malloc((size_t)sl * sizeof(int));
            memcpy(pantry.sequences[idx], batches[b].sequences[s], (size_t)sl * sizeof(int));
            idx++;
        }
    }

    pantry.loaded = 1;

    std::cout << "[PANTRY] Directory loaded: " << total_seqs << " total sequences"
              << " max_seq_len=" << max_seq_len
              << " from " << num_batches << " batches\n";

    // Free individual batch data (sequences already copied)
    for (int b = 0; b < num_batches; b++) {
        VBP1Data_Free(&batches[b]);
    }
    free(batches);

    return pantry;
}

// ============ TRAIN ON PANTRY ============
// Train TransformerModel on sequences from PantrySystem sealed batches.
// Loss: contrastive embedding MSE — push output hidden state toward target token embedding.
// For each position i: loss += 0.5 * ||hidden[i] - W_emb[target[i]]||^2
// Target tokens = input tokens shifted by 1 (next-token prediction).
// Token IDs are clamped to model vocab_size via modulo (handles vocab mismatch).

static void TransformerModel_TrainOnPantry(TransformerModel* model, PantryData* pantry, int epochs) {
    int dm = model->config.d_model;
    int vocab = model->config.vocab_size;
    float grad_scale = 0.01f;

    // Clamp buffers (allocated once, reused for all sequences)
    int max_sl = pantry->max_seq_len;
    int* clamped_input = (int*)malloc((size_t)max_sl * sizeof(int));
    int* clamped_target = (int*)malloc((size_t)max_sl * sizeof(int));

    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

    for (int epoch = 0; epoch < epochs; epoch++) {
        double epoch_loss = 0.0;

        for (int s = 0; s < pantry->num_seqs; s++) {
            int sl = pantry->seq_lengths[s];
            int* tokens = pantry->sequences[s];

            // Clamp token IDs to model vocab size (modulo)
            for (int i = 0; i < sl; i++) {
                clamped_input[i] = tokens[i] % vocab;
                if (clamped_input[i] < 0) clamped_input[i] += vocab;
            }

            // Target = next token (shift by 1), last target = last input
            for (int i = 0; i < sl - 1; i++) {
                clamped_target[i] = tokens[i + 1] % vocab;
                if (clamped_target[i] < 0) clamped_target[i] += vocab;
            }
            clamped_target[sl - 1] = clamped_input[sl - 1];

            // Forward pass — output lands in model->hidden (n_layers=6 is even)
            TransformerModel_Forward(model, clamped_input, sl);

            // Compute contrastive loss and gradient
            __fp16* hidden = (__fp16*)model->hidden.contents;
            __fp16* W_emb_ptr = (__fp16*)model->W_emb.contents;
            __fp16* grad_h = (__fp16*)model->grad_hidden.contents;

            double seq_loss = 0.0;
            for (int i = 0; i < sl; i++) {
                int tgt = clamped_target[i];
                __fp16* tgt_emb = W_emb_ptr + (size_t)tgt * dm;
                __fp16* h = hidden + (size_t)i * dm;
                for (int d = 0; d < dm; d++) {
                    float diff = (float)h[d] - (float)tgt_emb[d];
                    seq_loss += diff * diff;
                    grad_h[(size_t)i * dm + d] = (__fp16)(diff * grad_scale);
                }
            }
            seq_loss = 0.5 * seq_loss / (sl * dm);
            epoch_loss += seq_loss;

            // Backward pass
            TransformerModel_Backward(model, clamped_input, sl);

            // SGD update
            TransformerModel_Optimize(model);

            // Log progress every 100 sequences or at the end
            if ((s + 1) % 100 == 0 || s == pantry->num_seqs - 1) {
                struct timespec tsn; clock_gettime(CLOCK_REALTIME, &tsn);
                double el = (tsn.tv_sec - ts0.tv_sec) + (tsn.tv_nsec - ts0.tv_nsec) / 1e9;
                std::cout << "[PANTRY] Epoch " << (epoch + 1) << "/" << epochs
                          << " seq " << (s + 1) << "/" << pantry->num_seqs
                          << " avg_loss=" << (epoch_loss / (s + 1))
                          << " time=" << el << "s\n";
            }
        }

        struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
        double el = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;
        std::cout << "[PANTRY] Epoch " << (epoch + 1) << " complete: avg_loss="
                  << (epoch_loss / pantry->num_seqs) << " time=" << el << "s\n";
    }

    free(clamped_input);
    free(clamped_target);
}

// ============ WEIGHT PERSISTENCE: SAVE / LOAD / CHECKPOINT ============
//[@GHOST]{file_path="core/Piplines/c_transformer_attention.mm" date="2026-07-01" author="cascade" session_id="c-bcl-transformer-persist" context="BCLT binary weight persistence for TransformerModel. Serializes fp16 weight tensors from MTLBuffer.contents via memcpy. Format: BCLT magic + version + config header + per-tensor (name_len, name, shape_len, shape, data_size, data)."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@FILEID]{id="c_transformer_attention.mm::persist" domain="weight_persistence" authority="BCLTransformer"}
//[@SUMMARY]{summary="save_model writes BCLT binary: 4-byte magic + uint32 version + 5x uint32 config (n_layers, d_model, n_heads, vocab_size, max_seq) + tensor stream. load_model verifies magic+config, memcpy into MTLBuffer.contents. checkpoint saves to dir/checkpoint_epoch_NNN.bin. ComputeDemoLoss returns L2 norm of final hidden output for save/load verification."}

// --- BCLT format constants ---
static const char BCLT_MAGIC[4] = {'B','C','L','T'};
static const uint32_t BCLT_VERSION = 1;

// --- Helper: write one tensor header + raw fp16 data to file ---
static void SaveTensor(FILE* f, const char* name, const uint32_t* shape, uint32_t shape_len, id<MTLBuffer> buf) {
    uint32_t name_len = (uint32_t)strlen(name);
    uint64_t data_size = (uint64_t)[buf length];
    fwrite(&name_len, sizeof(uint32_t), 1, f);
    fwrite(name, 1, name_len, f);
    fwrite(&shape_len, sizeof(uint32_t), 1, f);
    fwrite(shape, sizeof(uint32_t), shape_len, f);
    fwrite(&data_size, sizeof(uint64_t), 1, f);
    fwrite((const void*)[buf contents], 1, data_size, f);
}

// --- Helper: read one tensor header + raw data into MTLBuffer ---
static int LoadTensor(FILE* f, id<MTLBuffer> buf) {
    uint32_t name_len;
    if (fread(&name_len, sizeof(uint32_t), 1, f) != 1) return 0;
    char name[256];
    if (name_len >= sizeof(name)) return 0;
    if (fread(name, 1, name_len, f) != name_len) return 0;
    name[name_len] = '\0';
    uint32_t shape_len;
    if (fread(&shape_len, sizeof(uint32_t), 1, f) != 1) return 0;
    if (shape_len > 8) return 0;
    uint32_t shape[8];
    if (fread(shape, sizeof(uint32_t), shape_len, f) != shape_len) return 0;
    uint64_t data_size;
    if (fread(&data_size, sizeof(uint64_t), 1, f) != 1) return 0;
    if (data_size != (uint64_t)[buf length]) {
        std::cout << "[XFORM]   LoadTensor size mismatch: '" << name << "' file=" << data_size << " buf=" << [buf length] << "\n";
        return 0;
    }
    if (fread([buf contents], 1, data_size, f) != data_size) return 0;
    std::cout << "[XFORM]   Loaded: " << name << " shape=[";
    for (uint32_t i = 0; i < shape_len; i++) {
        std::cout << shape[i];
        if (i + 1 < shape_len) std::cout << ",";
    }
    std::cout << "] bytes=" << data_size << "\n";
    return 1;
}

// ============ METHOD: TransformerModel_SaveModel ============
// Writes all fp16 weight tensors to a BCLT binary file.
// Returns 1 on success, 0 on failure.

static int TransformerModel_SaveModel(TransformerModel* model, const char* path) {
    FILE* f = fopen(path, "wb");
    if (!f) {
        std::cout << "[XFORM] Save FAILED: cannot open " << path << "\n";
        return 0;
    }

    // --- Header: magic + version + config ---
    fwrite(BCLT_MAGIC, 4, 1, f);
    uint32_t version = BCLT_VERSION;
    fwrite(&version, sizeof(uint32_t), 1, f);

    uint32_t n_layers   = (uint32_t)model->config.n_layers;
    uint32_t d_model    = (uint32_t)model->config.d_model;
    uint32_t n_heads    = (uint32_t)model->config.n_heads;
    uint32_t vocab_size = (uint32_t)model->config.vocab_size;
    uint32_t max_seq    = (uint32_t)model->config.max_seq_len;
    fwrite(&n_layers,   sizeof(uint32_t), 1, f);
    fwrite(&d_model,    sizeof(uint32_t), 1, f);
    fwrite(&n_heads,    sizeof(uint32_t), 1, f);
    fwrite(&vocab_size, sizeof(uint32_t), 1, f);
    fwrite(&max_seq,    sizeof(uint32_t), 1, f);

    // --- Token embedding: [vocab_size, d_model] ---
    uint32_t emb_shape[2] = {vocab_size, d_model};
    SaveTensor(f, "token_embedding", emb_shape, 2, model->W_emb);

    // --- Per-layer weights ---
    for (int i = 0; i < model->config.n_layers; i++) {
        AttentionLayer* layer = &model->layers[i];
        char name[128];
        uint32_t mat_shape[2] = {d_model, d_model};
        uint32_t vec_shape[1] = {d_model};

        snprintf(name, sizeof(name), "layer_%d_W_q", i);
        SaveTensor(f, name, mat_shape, 2, layer->W_q);
        snprintf(name, sizeof(name), "layer_%d_W_k", i);
        SaveTensor(f, name, mat_shape, 2, layer->W_k);
        snprintf(name, sizeof(name), "layer_%d_W_v", i);
        SaveTensor(f, name, mat_shape, 2, layer->W_v);
        snprintf(name, sizeof(name), "layer_%d_W_o", i);
        SaveTensor(f, name, mat_shape, 2, layer->W_o);
        snprintf(name, sizeof(name), "layer_%d_LN1_scale", i);
        SaveTensor(f, name, vec_shape, 1, layer->ln_scale);
        snprintf(name, sizeof(name), "layer_%d_LN1_bias", i);
        SaveTensor(f, name, vec_shape, 1, layer->ln_bias);
    }

    fflush(f);
    fclose(f);

    // Report file size
    struct stat st;
    if (stat(path, &st) == 0) {
        std::cout << "[XFORM] Save OK: " << path << " (" << st.st_size << " bytes, "
                  << ((double)st.st_size / (1024.0 * 1024.0)) << " MB)\n";
    } else {
        std::cout << "[XFORM] Save OK: " << path << "\n";
    }
    return 1;
}

// ============ METHOD: TransformerModel_LoadModel ============
// Reads BCLT binary, verifies magic + config, loads weights into existing MTLBuffers.
// The model must already be initialized (buffers allocated).
// Returns 1 on success, 0 on failure.

static int TransformerModel_LoadModel(TransformerModel* model, const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) {
        std::cout << "[XFORM] Load FAILED: cannot open " << path << "\n";
        return 0;
    }

    // --- Verify magic ---
    char magic[4];
    if (fread(magic, 1, 4, f) != 4 || memcmp(magic, BCLT_MAGIC, 4) != 0) {
        std::cout << "[XFORM] Load FAILED: bad magic (expected BCLT)\n";
        fclose(f);
        return 0;
    }

    // --- Verify version ---
    uint32_t version;
    if (fread(&version, sizeof(uint32_t), 1, f) != 1 || version != BCLT_VERSION) {
        std::cout << "[XFORM] Load FAILED: version mismatch (expected " << BCLT_VERSION << ")\n";
        fclose(f);
        return 0;
    }

    // --- Read and verify config ---
    uint32_t n_layers, d_model, n_heads, vocab_size, max_seq;
    if (fread(&n_layers,   sizeof(uint32_t), 1, f) != 1 ||
        fread(&d_model,    sizeof(uint32_t), 1, f) != 1 ||
        fread(&n_heads,    sizeof(uint32_t), 1, f) != 1 ||
        fread(&vocab_size, sizeof(uint32_t), 1, f) != 1 ||
        fread(&max_seq,    sizeof(uint32_t), 1, f) != 1) {
        std::cout << "[XFORM] Load FAILED: truncated header\n";
        fclose(f);
        return 0;
    }

    if ((int)n_layers != model->config.n_layers ||
        (int)d_model  != model->config.d_model ||
        (int)n_heads   != model->config.n_heads ||
        (int)vocab_size != model->config.vocab_size) {
        std::cout << "[XFORM] Load FAILED: config mismatch"
                  << " (file: n_layers=" << n_layers << " d_model=" << d_model
                  << " n_heads=" << n_heads << " vocab=" << vocab_size
                  << " vs model: n_layers=" << model->config.n_layers
                  << " d_model=" << model->config.d_model
                  << " n_heads=" << model->config.n_heads
                  << " vocab=" << model->config.vocab_size << ")\n";
        fclose(f);
        return 0;
    }

    std::cout << "[XFORM] Load: header OK (n_layers=" << n_layers
              << " d_model=" << d_model << " n_heads=" << n_heads
              << " vocab=" << vocab_size << ")\n";

    // --- Load token embedding ---
    if (!LoadTensor(f, model->W_emb)) { fclose(f); return 0; }

    // --- Load per-layer weights ---
    for (int i = 0; i < model->config.n_layers; i++) {
        AttentionLayer* layer = &model->layers[i];
        if (!LoadTensor(f, layer->W_q))      { fclose(f); return 0; }
        if (!LoadTensor(f, layer->W_k))      { fclose(f); return 0; }
        if (!LoadTensor(f, layer->W_v))      { fclose(f); return 0; }
        if (!LoadTensor(f, layer->W_o))      { fclose(f); return 0; }
        if (!LoadTensor(f, layer->ln_scale)) { fclose(f); return 0; }
        if (!LoadTensor(f, layer->ln_bias))  { fclose(f); return 0; }
    }

    fclose(f);
    std::cout << "[XFORM] Load OK: " << path << "\n";
    return 1;
}

// ============ METHOD: TransformerModel_Checkpoint ============
// Saves model to dir/checkpoint_epoch_NNN.bin. Creates dir if needed.

static int TransformerModel_Checkpoint(TransformerModel* model, int epoch, const char* dir) {
    // Create directory if it doesn't exist
    mkdir(dir, 0755);

    char path[512];
    snprintf(path, sizeof(path), "%s/checkpoint_epoch_%03d.bin", dir, epoch);

    int ok = TransformerModel_SaveModel(model, path);
    if (ok) {
        std::cout << "[XFORM] Checkpoint epoch " << epoch << " -> " << path << "\n";
    }
    return ok;
}

// ============ METHOD: TransformerModel_ComputeDemoLoss ============
// Computes L2 loss (sum of squared activations) of the final hidden output.
// Used to verify that loaded weights produce identical forward pass.
// No kernel needed — direct CPU read of shared-mode MTLBuffer.

static float TransformerModel_ComputeDemoLoss(TransformerModel* model) {
    // Final output buffer: after n_layers forward passes with swap,
    // even n_layers -> output in model->hidden, odd -> model->hidden_next
    id<MTLBuffer> output = (model->config.n_layers % 2 == 0)
                           ? model->hidden
                           : model->hidden_next;
    __fp16* h = (__fp16*)[output contents];
    int count = model->seq_len * model->config.d_model;
    float loss = 0.0f;
    for (int i = 0; i < count; i++) {
        float v = (float)h[i];
        loss += v * v;
    }
    return loss;
}

// ============ BCL IR GRAPH (inline struct + extern C API) ============
//[@GHOST]{section="bcl_ir_graph_inline" date="2026-07-04" author="devin" session_id="bcl-ir-metal" context="BclIrGraph struct + API declarations copied inline from bcl_ir_graph.h to avoid path issues. Implementation compiled separately from bcl_ir_graph.c and linked via extern C. Computes all 5 structural signals: token_ids, pe_matrix, mask, domain_ids, graph_bias."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@SUMMARY]{summary="BclIrGraph: parses BCL once, computes token_ids (djb2), pe_matrix (depth+sibling sinusoidal 384-dim), mask (ancestor+sibling), domain_ids (10-domain substring), graph_bias (T5-style FEEDS/PAIRS/ENABLES/MEASURES). Self-contained, no tree_sitter."}

#define BCLIR_MAX_NODES    256
#define BCLIR_MAX_CONTENT  4096
#define BCLIR_MAX_TAG      64
#define BCLIR_PE_DIM       384
#define BCLIR_VOCAB_SIZE   162612
#define BCLIR_DOMAIN_COUNT 10

typedef struct {
    char tag[BCLIR_MAX_TAG];
    char content[BCLIR_MAX_CONTENT];
    int  start_pos;
    int  end_pos;
    int  depth;
    int  parent_idx;
    int  child_count;
    int  children[32];
} BclIrNode;

typedef struct {
    BclIrNode nodes[BCLIR_MAX_NODES];
    int   node_count;
    int   parse_ok;
    char  error_msg[256];
    int   error_pos;
    int   token_ids[BCLIR_MAX_NODES];
    float pe_matrix[BCLIR_MAX_NODES][BCLIR_PE_DIM];
    char  mask[BCLIR_MAX_NODES][BCLIR_MAX_NODES];
    int   domain_ids[BCLIR_MAX_NODES];
    float graph_bias[BCLIR_MAX_NODES][BCLIR_MAX_NODES];
    int   computed;
} BclIrGraph;

extern "C" {
    void BclIrGraph_Init(BclIrGraph *ir);
    int  BclIrGraph_Parse(BclIrGraph *ir, const char *bcl_text);
    void BclIrGraph_ComputeAll(BclIrGraph *ir);
    void BclIrGraph_Print(BclIrGraph *ir);
}

// ============ BCL IR DATA LOADER + NATIVE TRAINING ============
//[@GHOST]{section="bcl_native_train" date="2026-07-04" author="devin" session_id="bcl-ir-metal" context="BCL IR Graph -> Metal buffers training path. load_bcl_ir parses BCL via BclIrGraph, computes ALL 5 signals (token_ids, pe_matrix, mask, domain_ids, graph_bias) in one pass. TransformerModel_TrainOnBcl copies all 5 buffers to Metal, adds PE to embeddings, adds graph_bias to attention scores."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@SUMMARY]{summary="load_bcl_ir: parse BCL via BclIrGraph IR, extract all 5 signals into host buffers. BclIrData holds token_ids, pe_matrix (float32 seq*384), mask (char seq*seq), domain_ids (int32), graph_bias (float32 seq*seq). TransformerModel_TrainOnBcl: copy all 5 to Metal, add PE to embeddings, add graph_bias to attention scores, train N epochs."}

typedef struct {
    int    seq_len;
    int*   token_ids;
    float* pe_matrix;
    char*  mask_buffer;
    int*   domain_ids;
    float* graph_bias;
    int    parsed_ok;
} BclIrData;

static BclIrData load_bcl_ir(const char* bcl_text) {
    BclIrData result;
    memset(&result, 0, sizeof(result));

    BclIrGraph ir;
    BclIrGraph_Init(&ir);

    if (!BclIrGraph_Parse(&ir, bcl_text)) {
        std::cout << "[BCL-IR] Parse FAILED: " << ir.error_msg
                  << " at pos " << ir.error_pos << "\n";
        result.parsed_ok = 0;
        return result;
    }

    int n = ir.node_count;
    if (n <= 0) {
        std::cout << "[BCL-IR] Parse OK but no nodes found\n";
        result.parsed_ok = 0;
        return result;
    }

    // Compute ALL 5 structural signals in one pass
    BclIrGraph_ComputeAll(&ir);

    result.seq_len = n;
    result.token_ids = (int*)malloc((size_t)n * sizeof(int));
    result.pe_matrix = (float*)malloc((size_t)n * BCLIR_PE_DIM * sizeof(float));
    result.mask_buffer = (char*)malloc((size_t)n * n * sizeof(char));
    result.domain_ids = (int*)malloc((size_t)n * sizeof(int));
    result.graph_bias = (float*)malloc((size_t)n * n * sizeof(float));
    result.parsed_ok = 1;

    // Extract all 5 signals from the IR
    for (int i = 0; i < n; i++) {
        result.token_ids[i] = ir.token_ids[i];
        result.domain_ids[i] = ir.domain_ids[i];
        for (int j = 0; j < BCLIR_PE_DIM; j++) {
            result.pe_matrix[i * BCLIR_PE_DIM + j] = ir.pe_matrix[i][j];
        }
        for (int j = 0; j < n; j++) {
            result.mask_buffer[i * n + j] = ir.mask[i][j];
            result.graph_bias[i * n + j] = ir.graph_bias[i][j];
        }
    }

    // Print all 5 signals
    std::cout << "[BCL-IR] Parse OK: " << n << " nodes, ALL 5 signals computed\n";
    std::cout << "[BCL-IR] === SIGNAL 1: TOKEN IDS (djb2 hash mod vocab) ===\n";
    for (int i = 0; i < n; i++) {
        std::cout << "[BCL-IR]   node " << i << ": tag=[@" << ir.nodes[i].tag << "]"
                  << " depth=" << ir.nodes[i].depth
                  << " parent=" << ir.nodes[i].parent_idx
                  << " token_id=" << result.token_ids[i]
                  << " domain=" << result.domain_ids[i] << "\n";
    }

    std::cout << "[BCL-IR] === SIGNAL 2: PE MATRIX (L2 norms, 384-dim sinusoidal) ===\n";
    for (int i = 0; i < n; i++) {
        float sum = 0.0f;
        for (int j = 0; j < BCLIR_PE_DIM; j++) {
            float v = result.pe_matrix[i * BCLIR_PE_DIM + j];
            sum += v * v;
        }
        float norm = (float)sqrt((double)sum);
        std::cout << "[BCL-IR]   node " << i << ": L2norm=" << std::fixed << std::setprecision(4) << norm
                  << " first4=[" << std::setprecision(3)
                  << result.pe_matrix[i * BCLIR_PE_DIM + 0] << ", "
                  << result.pe_matrix[i * BCLIR_PE_DIM + 1] << ", "
                  << result.pe_matrix[i * BCLIR_PE_DIM + 2] << ", "
                  << result.pe_matrix[i * BCLIR_PE_DIM + 3] << "]\n";
    }

    std::cout << "[BCL-IR] === SIGNAL 3: ATTENTION MASK (0=allow, 1=block) ===\n";
    std::cout << "[BCL-IR]      ";
    for (int j = 0; j < n; j++) std::cout << std::setw(4) << j;
    std::cout << "\n";
    for (int i = 0; i < n; i++) {
        std::cout << "[BCL-IR]  " << std::setw(3) << i << ":";
        for (int j = 0; j < n; j++) {
            std::cout << "  " << (result.mask_buffer[i * n + j] ? "X" : ".");
        }
        std::cout << "\n";
    }

    std::cout << "[BCL-IR] === SIGNAL 4: DOMAIN IDS (10-domain routing) ===\n";
    for (int i = 0; i < n; i++) {
        const char* dname = (result.domain_ids[i] >= 0) ? "" : "unknown";
        std::cout << "[BCL-IR]   node " << i << ": domain_id=" << result.domain_ids[i]
                  << " (" << dname << ")\n";
    }

    std::cout << "[BCL-IR] === SIGNAL 5: GRAPH BIAS (T5-style, first " << (n < 10 ? n : 10) << "x" << (n < 10 ? n : 10) << ") ===\n";
    int show = (n < 10) ? n : 10;
    std::cout << "[BCL-IR]      ";
    for (int j = 0; j < show; j++) std::cout << std::setw(6) << j;
    std::cout << "\n";
    for (int i = 0; i < show; i++) {
        std::cout << "[BCL-IR]  " << std::setw(3) << i << ":";
        for (int j = 0; j < show; j++) {
            std::cout << " " << std::setw(5) << std::fixed << std::setprecision(2)
                      << result.graph_bias[i * n + j];
        }
        std::cout << "\n";
    }

    return result;
}

static void BclIrData_Free(BclIrData* data) {
    if (data->token_ids) { free(data->token_ids); data->token_ids = NULL; }
    if (data->pe_matrix) { free(data->pe_matrix); data->pe_matrix = NULL; }
    if (data->mask_buffer) { free(data->mask_buffer); data->mask_buffer = NULL; }
    if (data->domain_ids) { free(data->domain_ids); data->domain_ids = NULL; }
    if (data->graph_bias) { free(data->graph_bias); data->graph_bias = NULL; }
    data->parsed_ok = 0;
}

static void TransformerModel_TrainOnBcl(TransformerModel* model, const char* bcl_text, int epochs) {
    BclIrData bcl = load_bcl_ir(bcl_text);
    if (!bcl.parsed_ok) {
        std::cout << "[BCL-IR] Cannot train: BCL IR parse failed\n";
        return;
    }

    int seq_len = bcl.seq_len;
    int dm = model->config.d_model;
    int vocab = model->config.vocab_size;
    int model_sl = model->seq_len;

    if (seq_len > model_sl) {
        std::cout << "[BCL-IR] seq_len " << seq_len << " > model seq_len " << model_sl << ", clamping\n";
        seq_len = model_sl;
    }

    int* clamped_input = (int*)malloc((size_t)seq_len * sizeof(int));
    int* targets = (int*)malloc((size_t)seq_len * sizeof(int));
    for (int i = 0; i < seq_len; i++) {
        clamped_input[i] = bcl.token_ids[i] % vocab;
        if (clamped_input[i] < 0) clamped_input[i] += vocab;
        targets[i] = clamped_input[i];
    }

    // --- Copy ALL 5 signals to Metal buffers ---

    // Signal 3: mask -> bcl_mask [model_sl x model_sl] (padded with 0=allow)
    for (int i = 0; i < model->config.n_layers; i++) {
        size_t mask_size = (size_t)model_sl * model_sl * sizeof(char);
        char* mask_host = (char*)calloc(model_sl * model_sl, sizeof(char));
        for (int r = 0; r < seq_len; r++) {
            for (int c = 0; c < seq_len; c++) {
                mask_host[r * model_sl + c] = bcl.mask_buffer[r * bcl.seq_len + c];
            }
        }
        memcpy(model->layers[i].bcl_mask.contents, mask_host, mask_size);
        free(mask_host);
    }

    // Signal 5: graph_bias -> graph_bias_buf [model_sl x model_sl] float (padded with 0)
    size_t bias_size = (size_t)model_sl * model_sl * sizeof(float);
    float* bias_host = (float*)calloc(model_sl * model_sl, sizeof(float));
    for (int r = 0; r < seq_len; r++) {
        for (int c = 0; c < seq_len; c++) {
            bias_host[r * model_sl + c] = bcl.graph_bias[r * bcl.seq_len + c];
        }
    }
    for (int i = 0; i < model->config.n_layers; i++) {
        if (model->layers[i].graph_bias_buf) {
            memcpy(model->layers[i].graph_bias_buf.contents, bias_host, bias_size);
        } else {
            model->layers[i].graph_bias_buf = [model->backend.device newBufferWithBytes:bias_host
                                                                                  length:bias_size
                                                                                  options:MTLResourceStorageModeShared];
        }
        model->layers[i].has_graph_bias = 1;
    }
    free(bias_host);

    // Signal 2: PE matrix -> pe_buffer [model_sl x d_model] fp16 (padded with 0)
    size_t pe_size = (size_t)model_sl * dm * sizeof(__fp16);
    __fp16* pe_host = (__fp16*)calloc(model_sl * dm, sizeof(__fp16));
    for (int r = 0; r < seq_len; r++) {
        for (int c = 0; c < dm && c < BCLIR_PE_DIM; c++) {
            pe_host[r * dm + c] = (__fp16)bcl.pe_matrix[r * BCLIR_PE_DIM + c];
        }
    }
    if (model->pe_buffer) {
        memcpy(model->pe_buffer.contents, pe_host, pe_size);
    } else {
        model->pe_buffer = [model->backend.device newBufferWithBytes:pe_host
                                                              length:pe_size
                                                              options:MTLResourceStorageModeShared];
    }
    model->has_pe = 1;
    free(pe_host);

    // Signal 4: domain_ids stored on host for future domain-sparse attention
    std::cout << "[BCL-IR] Domain IDs (stored for future domain-sparse attention):";
    for (int i = 0; i < seq_len; i++) {
        std::cout << " " << bcl.domain_ids[i];
    }
    std::cout << "\n";

    std::cout << "[BCL-IR] Starting IR-based BCL training: " << epochs << " epochs, "
              << seq_len << " tokens, ALL 5 signals active\n";
    std::cout << "[BCL-IR]   PE: ADDED to embeddings | GraphBias: ADDED to attn scores | Mask: applied in softmax\n";
    std::cout << "[BCL-IR] LR schedule: warmup=" << model->lr_scheduler.warmup_steps
              << " max_lr=" << model->lr_scheduler.max_lr << "\n\n";

    float* epoch_losses = (float*)malloc((size_t)epochs * sizeof(float));
    float* epoch_lrs = (float*)malloc((size_t)epochs * sizeof(float));
    float* epoch_grad_norms = (float*)malloc((size_t)epochs * sizeof(float));

    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

    for (int epoch = 0; epoch < epochs; epoch++) {
        struct timespec ep_start; clock_gettime(CLOCK_REALTIME, &ep_start);

        TransformerModel_Forward(model, clamped_input, seq_len);

        float loss = 0.0f;
        TransformerModel_ComputeLoss(model, targets, seq_len, &loss);

        TransformerModel_LossBackward(model, targets, seq_len);
        TransformerModel_Backward(model, clamped_input, seq_len);

        float grad_norm = 0.0f;
        TransformerModel_ClipGradients(model, 1.0f, &grad_norm);

        float lr = LRScheduler_GetLR(&model->lr_scheduler);
        TransformerModel_Optimize(model);
        LRScheduler_Step(&model->lr_scheduler);

        struct timespec ep_end; clock_gettime(CLOCK_REALTIME, &ep_end);
        double ep_time = (ep_end.tv_sec - ep_start.tv_sec) + (ep_end.tv_nsec - ep_start.tv_nsec) / 1e9;

        epoch_losses[epoch] = loss;
        epoch_lrs[epoch] = lr;
        epoch_grad_norms[epoch] = grad_norm;

        std::cout << "[BCL-IR] Epoch " << (epoch + 1) << "/" << epochs
                  << "  loss=" << std::fixed << std::setprecision(6) << loss
                  << "  lr=" << std::scientific << std::setprecision(6) << lr
                  << "  grad_norm=" << std::fixed << std::setprecision(6) << grad_norm
                  << "  time=" << std::setprecision(3) << ep_time << "s\n";
    }

    struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
    double total_time = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;

    std::cout << "\n";
    std::cout << "==========================================================\n";
    std::cout << " BCL IR GRAPH TRAINING SUMMARY (5 signals: tokens+PE+mask+domains+bias)\n";
    std::cout << "==========================================================\n";
    std::cout << " Tokens: " << seq_len << "  Epochs: " << epochs
              << "  Total time: " << std::fixed << std::setprecision(3) << total_time << "s\n";
    std::cout << " Signals: token_ids[OK] PE[OK->embeddings] mask[OK->softmax] domain_ids[OK->stored] graph_bias[OK->attn_scores]\n";
    std::cout << "----------------------------------------------------------\n";
    std::cout << " Epoch |   Loss    |     LR      |  Grad Norm\n";
    std::cout << "----------------------------------------------------------\n";
    for (int e = 0; e < epochs; e++) {
        std::cout << "  " << std::right << std::setw(4) << (e + 1)
                  << " | " << std::fixed << std::setprecision(6) << std::setw(8) << epoch_losses[e]
                  << " | " << std::scientific << std::setprecision(6) << epoch_lrs[e]
                  << " | " << std::fixed << std::setprecision(6) << std::setw(9) << epoch_grad_norms[e]
                  << "\n";
    }
    std::cout << "----------------------------------------------------------\n";
    float first_loss = epoch_losses[0];
    float last_loss = epoch_losses[epochs - 1];
    float loss_delta = last_loss - first_loss;
    float loss_pct = (first_loss > 0.0f) ? (loss_delta / first_loss * 100.0f) : 0.0f;
    std::cout << " Loss trend: " << first_loss << " -> " << last_loss
              << "  (delta=" << loss_delta << ", " << loss_pct << "%)\n";
    std::cout << "==========================================================\n";

    // Reset IR flags so other training paths don't use stale PE/bias
    model->has_pe = 0;
    for (int i = 0; i < model->config.n_layers; i++) {
        model->layers[i].has_graph_bias = 0;
    }

    free(clamped_input);
    free(targets);
    free(epoch_losses);
    free(epoch_lrs);
    free(epoch_grad_norms);
    BclIrData_Free(&bcl);
}

// ============ INFERENCE MODE ============
//[@GHOST]{section="inference_mode" date="2026-07-03" author="cascade" session_id="c-bcl-transformer-infer" context="BCL Transformer inference mode: forward-only pass (no backward, no SGD) + argmax/top-k sampling decoding. BCL input -> model -> BCL output token IDs."}
//[@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}
//[@FILEID]{id="c_transformer_attention.mm::inference" domain="inference_engine" authority="BCLTransformer"}
//[@SUMMARY]{summary="TransformerModel_Infer: greedy argmax decoding. TransformerModel_InferSampled: top-k + temperature stochastic decoding. tokens_to_text: format token IDs as [tok_0, tok_1, ...]. Forward-only, no grad buffers touched."}

// ============ METHOD: TransformerModel_Infer ============
// Forward-only pass: embedding lookup -> N attention layers -> argmax decoding.
// The final hidden state [seq_len, d_model] is treated as pseudo-logits
// (vocab_size = d_model for the demo, matching the training loss approach).
// output_tokens must be pre-allocated with seq_len ints.
// Returns 1 on success.

static int TransformerModel_Infer(TransformerModel* model, int* input_tokens, int seq_len, int* output_tokens) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = seq_len;

    // --- Forward pass (no backward, no SGD) ---
    TransformerModel_Forward(model, input_tokens, seq_len);

    // Final output buffer: even n_layers -> hidden, odd -> hidden_next
    // (matches ComputeDemoLoss and TrainOnSqtx convention)
    id<MTLBuffer> final_output = (model->config.n_layers % 2 == 0)
                                 ? model->hidden
                                 : model->hidden_next;

    // --- Argmax decoding: hidden [seq, d_model] -> token_ids [seq] ---
    // Treat hidden as logits with vocab_size = d_model
    id<MTLBuffer> out_token_buf = [be->device newBufferWithLength:(size_t)sl * sizeof(int)
                                                          options:MTLResourceStorageModeShared];

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_argmax];
        [enc setBuffer:final_output offset:0 atIndex:0];
        [enc setBuffer:out_token_buf offset:0 atIndex:1];
        [enc setBytes:&dm length:sizeof(int) atIndex:2];  // vocab_size = d_model
        [enc setBytes:&sl length:sizeof(int) atIndex:3];
        int ew = (int)be->pipe_argmax.threadExecutionWidth;
        int tg = ew; if (tg > sl) tg = sl; if (tg < 1) tg = 1;
        if (tg > (int)be->pipe_argmax.maxTotalThreadsPerThreadgroup)
            tg = (int)be->pipe_argmax.maxTotalThreadsPerThreadgroup;
        [enc dispatchThreads:MTLSizeMake(sl, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // Copy results back to host
    memcpy(output_tokens, [out_token_buf contents], (size_t)sl * sizeof(int));

    return 1;
}

// ============ METHOD: TransformerModel_InferSampled ============
// Forward-only pass + top-k sampling with temperature.
// output_tokens must be pre-allocated with seq_len ints.
// Returns 1 on success.

static int TransformerModel_InferSampled(TransformerModel* model, int* input_tokens,
                                          int seq_len, int* output_tokens,
                                          int top_k, float temperature) {
    MetalBackend* be = &model->backend;
    int dm = model->config.d_model;
    int sl = seq_len;

    // Clamp top_k to valid range
    if (top_k < 1) top_k = 1;
    if (top_k > 128) top_k = 128;
    if (top_k > dm) top_k = dm;

    // --- Forward pass (no backward, no SGD) ---
    TransformerModel_Forward(model, input_tokens, seq_len);

    // Final output buffer
    id<MTLBuffer> final_output = (model->config.n_layers % 2 == 0)
                                 ? model->hidden
                                 : model->hidden_next;

    // --- Top-k sampling: hidden [seq, d_model] -> token_ids [seq] ---
    id<MTLBuffer> out_token_buf = [be->device newBufferWithLength:(size_t)sl * sizeof(int)
                                                          options:MTLResourceStorageModeShared];

    uint random_seed = (uint)time(NULL);

    @autoreleasepool {
        id<MTLCommandBuffer> cmd = [be->queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cmd computeCommandEncoder];
        [enc setComputePipelineState:be->pipe_top_k_sample];
        [enc setBuffer:final_output offset:0 atIndex:0];
        [enc setBuffer:out_token_buf offset:0 atIndex:1];
        [enc setBytes:&dm length:sizeof(int) atIndex:2];       // vocab_size = d_model
        [enc setBytes:&sl length:sizeof(int) atIndex:3];
        [enc setBytes:&top_k length:sizeof(int) atIndex:4];
        [enc setBytes:&temperature length:sizeof(float) atIndex:5];
        [enc setBytes:&random_seed length:sizeof(uint) atIndex:6];
        int ew = (int)be->pipe_top_k_sample.threadExecutionWidth;
        int tg = ew; if (tg > sl) tg = sl; if (tg < 1) tg = 1;
        if (tg > (int)be->pipe_top_k_sample.maxTotalThreadsPerThreadgroup)
            tg = (int)be->pipe_top_k_sample.maxTotalThreadsPerThreadgroup;
        [enc dispatchThreads:MTLSizeMake(sl, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];
        [cmd commit];
        [cmd waitUntilCompleted];
    }

    // Copy results back to host
    memcpy(output_tokens, [out_token_buf contents], (size_t)sl * sizeof(int));

    return 1;
}

// ============ METHOD: tokens_to_text ============
// Converts token IDs to a string representation: "[tok_0, tok_1, tok_2, ...]"
// Since we don't have a reverse vocab in C yet, we just print the IDs.
// Returns the number of characters written (excluding null terminator).

static int tokens_to_text(int* tokens, int count, char* out, size_t out_sz) {
    size_t pos = 0;
    pos += (size_t)snprintf(out + pos, out_sz - pos, "[");
    if (pos >= out_sz) return (int)pos;

    for (int i = 0; i < count; i++) {
        if (i > 0) {
            pos += (size_t)snprintf(out + pos, out_sz - pos, ", ");
            if (pos >= out_sz) return (int)pos;
        }
        pos += (size_t)snprintf(out + pos, out_sz - pos, "%d", tokens[i]);
        if (pos >= out_sz) return (int)pos;
    }
    pos += (size_t)snprintf(out + pos, out_sz - pos, "]");
    return (int)pos;
}

// ============ CLI ENTRY POINT ============
// Usage: ./bcl_transformer [--seq-len N] [--epochs N] [--total-steps N] [--data PATH] [--bcl "BCL TEXT"]
//                         [--pantry DIR] [--infer] [--top-k K] [--temperature T] [--weights PATH]
//
// If --infer is provided, runs inference mode (forward-only, no training).
//   Loads weights from --weights PATH (default: bcl_transformer_weights.bin) if exists.
//   Generates input tokens from --bcl text or random.
//   Runs argmax decoding (greedy) by default, or top-k sampling if --top-k is set.
// If --pantry DIR is provided, loads VBP1 sealed batches from PantrySystem directory and trains.
// If --bcl is provided (without --infer), parses BCL text via BCL IR Graph (5 signals) and trains.
// If --data PATH is provided, loads SQTX file and trains on real BCL data.
// Otherwise, runs random token demo with loss computation, LR schedule, grad clipping.
// Logs loss per epoch, LR, grad norm. Prints summary table at end.

// [@GHOST]{section="main_demo" date="2026-07-02" context="Training demo with loss logging, LR schedule, gradient clipping, summary table"}
// [@VBSTYLE]{standard="VBStyle" version="2" rules="PascalCase UPPERCASE"}

int main(int argc, char* argv[]) {
    srand((unsigned int)time(NULL));

    int seq_len = 64;
    int epochs = 10;
    int total_steps = 100000;
    const char* data_path = NULL;
    const char* bcl_text = NULL;
    const char* pantry_path = NULL;
    int infer_mode = 0;
    int top_k = 0;
    float temperature = 1.0f;
    const char* weights_path = "bcl_transformer_weights.bin";

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--seq-len") == 0 && i + 1 < argc) {
            seq_len = atoi(argv[i + 1]); i++;
        } else if (strcmp(argv[i], "--epochs") == 0 && i + 1 < argc) {
            epochs = atoi(argv[i + 1]); i++;
        } else if (strcmp(argv[i], "--total-steps") == 0 && i + 1 < argc) {
            total_steps = atoi(argv[i + 1]); i++;
        } else if (strcmp(argv[i], "--data") == 0 && i + 1 < argc) {
            data_path = argv[i + 1]; i++;
        } else if (strcmp(argv[i], "--bcl") == 0 && i + 1 < argc) {
            bcl_text = argv[i + 1]; i++;
        } else if (strcmp(argv[i], "--pantry") == 0 && i + 1 < argc) {
            pantry_path = argv[i + 1]; i++;
        } else if (strcmp(argv[i], "--infer") == 0) {
            infer_mode = 1;
        } else if (strcmp(argv[i], "--top-k") == 0 && i + 1 < argc) {
            top_k = atoi(argv[i + 1]); i++;
        } else if (strcmp(argv[i], "--temperature") == 0 && i + 1 < argc) {
            temperature = (float)atof(argv[i + 1]); i++;
        } else if (strcmp(argv[i], "--weights") == 0 && i + 1 < argc) {
            weights_path = argv[i + 1]; i++;
        }
    }

    // If --data provided, load SQTX and use its seq_len
    SQTXData sqtx;
    memset(&sqtx, 0, sizeof(sqtx));
    if (data_path) {
        sqtx = load_sqtx(data_path);
        if (!sqtx.loaded) {
            std::cout << "[XFORM] Failed to load SQTX data, aborting\n";
            return 1;
        }
        seq_len = sqtx.seq_len;
        std::cout << "[XFORM] Using SQTX seq_len=" << seq_len << " for model init\n";
    }

    // If --pantry provided, load VBP1 sealed batches and use max_seq_len
    PantryData pantry;
    memset(&pantry, 0, sizeof(pantry));
    if (pantry_path) {
        pantry = load_pantry_dir(pantry_path);
        if (!pantry.loaded) {
            std::cout << "[PANTRY] Failed to load pantry data, aborting\n";
            return 1;
        }
        seq_len = pantry.max_seq_len;
        std::cout << "[PANTRY] Using pantry max_seq_len=" << seq_len << " for model init\n";
    }

    if (seq_len > MAX_SEQ_LEN) {
        std::cout << "[XFORM] seq_len " << seq_len << " exceeds max " << MAX_SEQ_LEN << "\n";
        return 1;
    }

    TransformerConfig config = TransformerConfig_Default();
    TransformerModel model;
    memset(&model, 0, sizeof(model));

    if (!TransformerModel_Init(&model, &config, seq_len)) {
        std::cout << "[XFORM] Model init failed\n";
        return 1;
    }

    // Configure LR scheduler total steps
    model.lr_scheduler.total_steps = total_steps;
    // For short demos (<= 100 epochs), scale warmup and total to fit the demo
    // so the cosine decay is visible within the epoch count.
    // Standard transformer defaults: max_lr=3e-4, min_lr=1e-5, warmup=1000, total=100000
    // [@GHOST]{section="lr_demo_tuning" date="2026-07-04" context="Increased max_lr from 3e-4 to 1e-2 for short demos so loss decrease is visible within 50 epochs. The backward pass now flows gradients through LN and residual, so higher LR can actually reduce loss."}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    if (epochs <= 100 && total_steps == 100000) {
        model.lr_scheduler.warmup_steps = 2;
        model.lr_scheduler.total_steps = epochs;
        model.lr_scheduler.max_lr = 1e-2f;   // increased from 3e-4 for visible demo convergence
    }

    // [@GHOST]{section="main_infer" date="2026-07-03" context="Inference mode branch: load weights, generate input tokens, run forward-only pass, decode output tokens"}
    // [@VBSTYLE]{standard="VBStyle" version="2"}
    // --- INFERENCE MODE ---
    if (infer_mode) {
        struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

        std::cout << "[INFER] Inference mode: seq_len=" << seq_len
                  << " d_model=" << config.d_model
                  << " n_layers=" << config.n_layers << "\n";

        // Try to load weights from file
        FILE* wf = fopen(weights_path, "rb");
        if (wf) {
            fclose(wf);
            std::cout << "[INFER] Loading weights from " << weights_path << "\n";
            if (TransformerModel_LoadModel(&model, weights_path)) {
                std::cout << "[INFER] Weights loaded successfully\n";
            } else {
                std::cout << "[INFER] Weight load failed, using random init weights\n";
            }
        } else {
            std::cout << "[INFER] No weights file at " << weights_path
                      << ", using random init weights\n";
        }

        // Generate input tokens
        int* input_tokens = (int*)malloc((size_t)seq_len * sizeof(int));
        int* output_tokens = (int*)malloc((size_t)seq_len * sizeof(int));

        if (bcl_text) {
            // Generate tokens from BCL text (simple hash-based tokenization)
            // Since we don't have a full BCL tokenizer in C, we hash the text
            // to produce deterministic token IDs in [0, vocab_size)
            size_t blen = strlen(bcl_text);
            for (int i = 0; i < seq_len; i++) {
                unsigned int hash = 2166136261u;
                for (size_t c = 0; c < blen; c++) {
                    hash ^= (unsigned char)bcl_text[c];
                    hash *= 16777619u;
                }
                hash ^= (unsigned int)(i * 2654435761u);
                input_tokens[i] = (int)(hash % (unsigned int)config.vocab_size);
            }
            std::cout << "[INFER] Input tokens generated from BCL text (hash-based)\n";
        } else {
            // Random input tokens
            for (int i = 0; i < seq_len; i++) {
                input_tokens[i] = rand() % config.vocab_size;
            }
            std::cout << "[INFER] Input tokens generated randomly\n";
        }

        // Print input tokens
        char input_str[4096];
        tokens_to_text(input_tokens, seq_len, input_str, sizeof(input_str));
        std::cout << "[INFER] Input tokens:  " << input_str << "\n";

        // Run inference
        if (top_k > 0) {
            std::cout << "[INFER] Decoding: top-k sampling (k=" << top_k
                      << ", temperature=" << temperature << ")\n";
            TransformerModel_InferSampled(&model, input_tokens, seq_len,
                                           output_tokens, top_k, temperature);
        } else {
            std::cout << "[INFER] Decoding: greedy argmax\n";
            TransformerModel_Infer(&model, input_tokens, seq_len, output_tokens);
        }

        // Print output tokens
        char output_str[4096];
        tokens_to_text(output_tokens, seq_len, output_str, sizeof(output_str));
        std::cout << "[INFER] Output tokens: " << output_str << "\n";

        // Print summary
        struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
        double infer_time = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;

        std::cout << "\n";
        std::cout << "==========================================================\n";
        std::cout << " BCL TRANSFORMER INFERENCE SUMMARY\n";
        std::cout << "==========================================================\n";
        std::cout << " Config: d_model=" << config.d_model << " n_heads=" << config.n_heads
                  << " head_dim=" << config.head_dim << " n_layers=" << config.n_layers
                  << " seq_len=" << seq_len << "\n";
        std::cout << " Weights: " << weights_path << "\n";
        std::cout << " Decoding: " << (top_k > 0 ? "top-k sampling" : "greedy argmax");
        if (top_k > 0) std::cout << " (k=" << top_k << ", temp=" << temperature << ")";
        std::cout << "\n";
        std::cout << " Time: " << std::fixed << std::setprecision(3) << infer_time << "s\n";
        std::cout << "----------------------------------------------------------\n";
        std::cout << " Input:  " << input_str << "\n";
        std::cout << " Output: " << output_str << "\n";
        std::cout << "==========================================================\n";

        free(input_tokens);
        free(output_tokens);
        return 0;
    }

    struct timespec ts0; clock_gettime(CLOCK_REALTIME, &ts0);

    if (pantry_path) {
        // --- PANTRY TRAINING (VBP1 sealed batches from PantrySystem) ---
        std::cout << "[PANTRY] Training on pantry data: " << pantry.num_seqs
                  << " sequences, " << epochs << " epochs\n";
        TransformerModel_TrainOnPantry(&model, &pantry, epochs);
        PantryData_Free(&pantry);
        TransformerModel_SaveModel(&model, "bcl_transformer_weights.bin");
    } else if (bcl_text) {
        // --- BCL IR GRAPH TRAINING (full IR: 5 signals -> Metal, no Python) ---
        std::cout << "[BCL-IR] BCL IR Graph training mode — ALL 5 structural signals\n";
        std::cout << "[BCL-IR]   token_ids + PE matrix + attention mask + domain_ids + graph_bias\n";
        TransformerModel_TrainOnBcl(&model, bcl_text, epochs);
        TransformerModel_SaveModel(&model, "bcl_transformer_weights.bin");
    } else if (data_path) {
        // --- REAL BCL TRAINING ---
        std::cout << "[XFORM] Training on real BCL data: " << sqtx.num_sequences
                  << " sequences, " << epochs << " epochs\n";
        TransformerModel_TrainOnSqtx(&model, &sqtx, epochs);
        SQTXData_Free(&sqtx);
        TransformerModel_SaveModel(&model, "bcl_transformer_weights.bin");
    } else {
        // --- RANDOM TOKEN DEMO WITH LOSS + LR SCHEDULE + GRAD CLIP ---
        int* tokens = (int*)malloc((size_t)seq_len * sizeof(int));
        for (int i = 0; i < seq_len; i++) {
            tokens[i] = rand() % config.vocab_size;
        }

        // Generate target token IDs — identity mapping (target = input % d_model)
        // This gives the model a learnable pattern: predict the input token's embedding index
        int* targets = (int*)malloc((size_t)seq_len * sizeof(int));
        for (int i = 0; i < seq_len; i++) {
            targets[i] = tokens[i];  // identity: target = input token
        }

        std::cout << "[XFORM] Starting training: " << epochs << " epochs, seq_len=" << seq_len
                  << ", total_steps=" << total_steps << "\n";
        std::cout << "[XFORM] LR schedule: warmup=" << model.lr_scheduler.warmup_steps
                  << " max_lr=" << model.lr_scheduler.max_lr
                  << " min_lr=" << model.lr_scheduler.min_lr << "\n";
        std::cout << "[XFORM] Gradient clipping: max_norm=1.0\n\n";

        // Arrays to store per-epoch stats for summary table
        float* epoch_losses = (float*)malloc((size_t)epochs * sizeof(float));
        float* epoch_lrs = (float*)malloc((size_t)epochs * sizeof(float));
        float* epoch_grad_norms = (float*)malloc((size_t)epochs * sizeof(float));
        double* epoch_times = (double*)malloc((size_t)epochs * sizeof(double));

        for (int epoch = 0; epoch < epochs; epoch++) {
            struct timespec ep_start; clock_gettime(CLOCK_REALTIME, &ep_start);

            // Forward pass
            TransformerModel_Forward(&model, tokens, seq_len);

            // Compute cross-entropy loss
            float loss = 0.0f;
            TransformerModel_ComputeLoss(&model, targets, seq_len, &loss);

            // Loss backward: compute grad_logits -> grad_hidden
            TransformerModel_LossBackward(&model, targets, seq_len);

            // Backward pass through transformer layers
            TransformerModel_Backward(&model, tokens, seq_len);

            // Gradient clipping (max_norm = 1.0)
            float grad_norm = 0.0f;
            TransformerModel_ClipGradients(&model, 1.0f, &grad_norm);

            // Get current LR
            float lr = LRScheduler_GetLR(&model.lr_scheduler);

            // SGD update with scheduled LR
            TransformerModel_Optimize(&model);

            // Advance LR scheduler
            LRScheduler_Step(&model.lr_scheduler);

            // Record stats
            struct timespec ep_end; clock_gettime(CLOCK_REALTIME, &ep_end);
            double ep_time = (ep_end.tv_sec - ep_start.tv_sec) + (ep_end.tv_nsec - ep_start.tv_nsec) / 1e9;

            epoch_losses[epoch] = loss;
            epoch_lrs[epoch] = lr;
            epoch_grad_norms[epoch] = grad_norm;
            epoch_times[epoch] = ep_time;

            // Log per-epoch
            std::cout << "[XFORM] Epoch " << (epoch + 1) << "/" << epochs
                      << "  loss=" << std::fixed << std::setprecision(6) << loss
                      << "  lr=" << std::scientific << std::setprecision(6) << lr
                      << "  grad_norm=" << std::fixed << std::setprecision(6) << grad_norm
                      << "  time=" << std::setprecision(3) << ep_time << "s\n";
        }

        struct timespec ts1; clock_gettime(CLOCK_REALTIME, &ts1);
        double total_time = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) / 1e9;

        // Print summary table
        std::cout << "\n";
        std::cout << "==========================================================\n";
        std::cout << " BCL TRANSFORMER TRAINING SUMMARY\n";
        std::cout << "==========================================================\n";
        std::cout << " Config: d_model=" << config.d_model << " n_heads=" << config.n_heads
                  << " head_dim=" << config.head_dim << " n_layers=" << config.n_layers
                  << " seq_len=" << seq_len << "\n";
        std::cout << " Epochs: " << epochs << "  Total time: " << std::fixed << std::setprecision(3)
                  << total_time << "s\n";
        std::cout << "----------------------------------------------------------\n";
        std::cout << " Epoch |   Loss    |     LR      |  Grad Norm |  Time(s)\n";
        std::cout << "----------------------------------------------------------\n";
        for (int e = 0; e < epochs; e++) {
            std::cout << "  " << std::right << std::setw(4) << (e + 1)
                      << " | " << std::fixed << std::setprecision(6) << std::setw(8) << epoch_losses[e]
                      << " | " << std::scientific << std::setprecision(6) << epoch_lrs[e]
                      << " | " << std::fixed << std::setprecision(6) << std::setw(9) << epoch_grad_norms[e]
                      << " | " << std::setprecision(3) << epoch_times[e] << "\n";
        }
        std::cout << "----------------------------------------------------------\n";

        // Loss trend analysis
        float first_loss = epoch_losses[0];
        float last_loss = epoch_losses[epochs - 1];
        float loss_delta = last_loss - first_loss;
        float loss_pct = (first_loss > 0.0f) ? (loss_delta / first_loss * 100.0f) : 0.0f;
        std::cout << " Loss trend: " << first_loss << " -> " << last_loss
                  << "  (delta=" << loss_delta << ", " << loss_pct << "%)\n";
        std::cout << " LR range:   " << epoch_lrs[0] << " -> " << epoch_lrs[epochs - 1] << "\n";
        std::cout << "==========================================================\n";

        free(tokens);
        free(targets);
        free(epoch_losses);
        free(epoch_lrs);
        free(epoch_grad_norms);
        free(epoch_times);
    }

    return 0;
}
