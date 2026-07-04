R"(
#include <metal_stdlib>
using namespace metal;

static inline float fast_sigmoid(float x) {
    if (x > 30.0f) return 1.0f;
    if (x < -30.0f) return 0.0f;
    return 1.0f / (1.0f + exp(-x));
}

static inline uint xorshift32(thread uint* s) {
    *s ^= *s << 13; *s ^= *s >> 17; *s ^= *s << 5; return *s;
}

// PRE-PACKED KERNEL: GPU receives pre-generated (center, context) pairs.
// No corpus, no file boundaries, no window logic, no discard probs.
// GPU does ONLY: negative sampling + dot product + sigmoid + gradient update.
// This is pure "cooking" — all prep done offline.
//
// Buffer layout:
//   0: half* W_in
//   1: half* W_out
//   2: int* pairs (center, context) — interleaved, 2 ints per pair
//   3: int* neg_table
//   4: atomic_uint work_counter
//   5: int dims
//   6: int n_pairs
//   7: int neg_samples
//   8: float lr
//   9: uint neg_table_size
//   10: uint rng_seed
kernel void sgns_train_packed(
    device half* W_in             [[buffer(0)]],
    device half* W_out            [[buffer(1)]],
    device const int* pairs       [[buffer(2)]],
    device const int* neg_table   [[buffer(3)]],
    device atomic_uint* work_counter [[buffer(4)]],
    constant int& dims            [[buffer(5)]],
    constant int& n_pairs         [[buffer(6)]],
    constant int& neg_samples     [[buffer(7)]],
    constant float& lr            [[buffer(8)]],
    constant uint& neg_table_size [[buffer(9)]],
    constant uint& rng_seed       [[buffer(10)]],
    uint gid [[thread_position_in_grid]])
{
    int d4 = dims / 4;

    while (true) {
        uint my_idx = atomic_fetch_add_explicit(work_counter, 1, memory_order_relaxed);
        if (my_idx >= (uint)n_pairs) break;

        uint pair_offset = my_idx * 2;
        int center = pairs[pair_offset];
        int ctx = pairs[pair_offset + 1];
        if (center < 0 || ctx < 0) continue;

        uint rng = rng_seed + my_idx * 2654435761u;
        device half* cv = W_in + (device size_t)center * dims;
        device half* pv = W_out + (device size_t)ctx * dims;

        // Positive pair
        float pos_dot = 0.0f;
        for (int d = 0; d < d4; d++) {
            half4 cv4 = *(device half4*)(cv + d*4); half4 pv4 = *(device half4*)(pv + d*4);
            pos_dot += dot(float4(cv4), float4(pv4));
        }
        float pos_grad = lr * (1.0f - fast_sigmoid(pos_dot));
        for (int d = 0; d < d4; d++) {
            half4 cv4 = *(device half4*)(cv + d*4); half4 pv4 = *(device half4*)(pv + d*4);
            float4 cvf = float4(cv4), pvf = float4(pv4); float4 g = float4(pos_grad);
            float4 cvo = cvf; cvf += g * pvf; pvf += g * cvo;
            *(device half4*)(cv + d*4) = half4(cvf); *(device half4*)(pv + d*4) = half4(pvf);
        }

        // Negative samples
        for (int k = 0; k < neg_samples; k++) {
            int nid = neg_table[xorshift32(&rng) % neg_table_size];
            if (nid == ctx) nid = neg_table[xorshift32(&rng) % neg_table_size];
            device half* nv = W_out + (device size_t)nid * dims;
            float neg_dot = 0.0f;
            for (int d = 0; d < d4; d++) {
                half4 cv4 = *(device half4*)(cv + d*4); half4 nv4 = *(device half4*)(nv + d*4);
                neg_dot += dot(float4(cv4), float4(nv4));
            }
            float neg_grad = lr * (0.0f - fast_sigmoid(neg_dot));
            for (int d = 0; d < d4; d++) {
                half4 cv4 = *(device half4*)(cv + d*4); half4 nv4 = *(device half4*)(nv + d*4);
                float4 cvf = float4(cv4), nvf = float4(nv4); float4 g = float4(neg_grad);
                float4 nvo = nvf; nvf += g * cvf; cvf += g * nvo;
                *(device half4*)(cv + d*4) = half4(cvf); *(device half4*)(nv + d*4) = half4(nvf);
            }
        }
    }
}

kernel void l2_normalize_kernel(
    device half* W_in  [[buffer(0)]],
    constant int& dims  [[buffer(1)]],
    constant int& vsize [[buffer(2)]],
    uint gid [[thread_position_in_grid]])
{
    if (gid >= (uint)vsize) return;
    device half* v = W_in + (device size_t)gid * dims;
    int d4 = dims / 4;
    float norm = 0.0f;
    for (int d = 0; d < d4; d++) { half4 v4 = *(device half4*)(v + d*4); norm += dot(float4(v4), float4(v4)); }
    norm = sqrt(norm);
    if (norm > 0.0f) { float4 inv4 = float4(1.0f / norm);
        for (int d = 0; d < d4; d++) { half4 v4 = *(device half4*)(v + d*4); *(device half4*)(v + d*4) = half4(float4(v4) * inv4); }
    }
}

kernel void reset_counter(device atomic_uint* counter [[buffer(0)]], uint gid [[thread_position_in_grid]]) {
    if (gid == 0) atomic_store_explicit(counter, 0, memory_order_relaxed);
}
)"
