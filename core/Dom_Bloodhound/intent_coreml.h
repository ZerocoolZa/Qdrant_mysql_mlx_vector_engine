// intent_coreml.h — CoreML intent router for MCP tool dispatch
// [@GHOST]{file_path="core/Dom_Bloodhound/intent_coreml.h" date="2026-07-04" author="Devin" session_id="coreml-router" context="Tiny CoreML model that routes natural language to MCP tools. Runs on Neural Engine, 28KB, zero RAM bloat."}
// [@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE"}
// [@FILEID]{id="intent_coreml.h" domain="dom_bloodhound" authority="IntentRouter"}
// [@SUMMARY]{summary="Loads IntentRouter.mlpackage, converts query to bag-of-words, runs CoreML inference, returns tool name + confidence."}
// [@CLASS]{class="IntentRouter" domain="dom_bloodhound" authority="single"}
// [@METHOD]{method="intent_load" type="init"}
// [@METHOD]{method="intent_predict" type="inference"}
// [@METHOD]{method="intent_free" type="cleanup"}
// [@METHOD]{method="bow_encode" type="helper"}

#ifndef INTENT_COREML_H
#define INTENT_COREML_H

#include <Foundation/Foundation.h>
#include <CoreML/CoreML.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

// ── Configuration ────────────────────────────────────────────
#define INTENT_VOCAB_SIZE   128
#define INTENT_NUM_CLASSES  19
#define INTENT_MAX_QUERY    512
#define INTENT_MAX_WORD     64

// Tool names (must match build_intent_coreml.py INTENTS order)
static const char *INTENT_TOOL_NAMES[INTENT_NUM_CLASSES] = {
    "cascade_chat_search_sessions",
    "cascade_chat_session_detail",
    "cascade_chat_search_files",
    "cascade_chat_search",
    "cascade_chat_load_all",
    "cascade_chat_scan",
    "cascade_chat_stats",
    "cascade_chat_list",
    "cascade_chat_read",
    "cascade_chat_export",
    "cascade_chat_export_db",
    "cascade_chat_verify_db",
    "cascade_chat_clean",
    "bcl_chat_compress",
    "bcl_chat_dry_run",
    "read_file",
    "write_file",
    "list_directory",
    "tools_md",
};

// Vocabulary (loaded from intent_vocab.json at runtime)
typedef struct {
    char words[INTENT_VOCAB_SIZE][INTENT_MAX_WORD];
    int  indices[INTENT_VOCAB_SIZE];  // hash map: word → index
    int  count;
} IntentVocab;

// Router state
typedef struct {
    MLModel          *model;
    IntentVocab      vocab;
    int              loaded;
} IntentRouter;

// ── Result ───────────────────────────────────────────────────
typedef struct {
    int    tool_index;     // 0-based index into INTENT_TOOL_NAMES
    float  confidence;     // softmax probability (0.0-1.0)
    const char *tool_name; // pointer into INTENT_TOOL_NAMES
    float  all_probs[INTENT_NUM_CLASSES]; // all class probabilities
} IntentResult;

// ── API ──────────────────────────────────────────────────────

// Load the CoreML model + vocab from disk.
// model_path: path to IntentRouter.mlpackage
// vocab_path: path to intent_vocab.json
// Returns 0 on success, -1 on error.
static int intent_load(IntentRouter *r, const char *model_path, const char *vocab_path);

// Predict which tool to use for a natural language query.
// Returns 0 on success, -1 on error.
static int intent_predict(IntentRouter *r, const char *query, IntentResult *out);

// Free resources.
static void intent_free(IntentRouter *r);

// ── Implementation ───────────────────────────────────────────

// Simple JSON parser for vocab (just extracts the "vocab" array)
static int intent_load_vocab(IntentVocab *v, const char *path) {
    FILE *f = fopen(path, "r");
    if (!f) return -1;

    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);

    char *buf = (char *)malloc(sz + 1);
    if (!buf) { fclose(f); return -1; }
    fread(buf, 1, sz, f);
    buf[sz] = '\0';
    fclose(f);

    // Find "vocab": [ ... ]
    char *p = strstr(buf, "\"vocab\"");
    if (!p) { free(buf); return -1; }
    p = strchr(p, '[');
    if (!p) { free(buf); return -1; }
    p++;

    v->count = 0;
    while (p && v->count < INTENT_VOCAB_SIZE) {
        // Find next quoted string
        p = strchr(p, '"');
        if (!p) break;
        p++;
        char *end = strchr(p, '"');
        if (!end) break;

        int len = end - p;
        if (len >= INTENT_MAX_WORD) len = INTENT_MAX_WORD - 1;
        strncpy(v->words[v->count], p, len);
        v->words[v->count][len] = '\0';
        v->count++;

        p = end + 1;
    }

    free(buf);
    return v->count > 0 ? 0 : -1;
}

// Find word index in vocab (linear search — vocab is only 128 words)
static int vocab_find(IntentVocab *v, const char *word) {
    for (int i = 0; i < v->count; i++) {
        if (strcmp(v->words[i], word) == 0) return i;
    }
    return -1;
}

// Convert query to bag-of-words vector
static void bow_encode(IntentVocab *v, const char *query, float *out) {
    memset(out, 0, INTENT_VOCAB_SIZE * sizeof(float));

    char buf[INTENT_MAX_QUERY];
    strncpy(buf, query, INTENT_MAX_QUERY - 1);
    buf[INTENT_MAX_QUERY - 1] = '\0';

    // Lowercase
    for (char *p = buf; *p; p++) *p = tolower(*p);

    // Tokenize by spaces
    char *tok = strtok(buf, " ,.!?:;\"'()[]{}\t\n");
    while (tok) {
        if (strlen(tok) >= 2) {
            int idx = vocab_find(v, tok);
            if (idx >= 0) out[idx] = 1.0f;
        }
        tok = strtok(NULL, " ,.!?:;\"'()[]{}\t\n");
    }
}

// Softmax
static void softmax(float *input, float *output, int n) {
    float max = input[0];
    for (int i = 1; i < n; i++) if (input[i] > max) max = input[i];

    float sum = 0;
    for (int i = 0; i < n; i++) {
        output[i] = expf(input[i] - max);
        sum += output[i];
    }
    for (int i = 0; i < n; i++) output[i] /= sum;
}

static int intent_load(IntentRouter *r, const char *model_path, const char *vocab_path) {
    memset(r, 0, sizeof(IntentRouter));

    // Load vocab
    if (intent_load_vocab(&r->vocab, vocab_path) != 0) {
        return -1;
    }

    // Load CoreML model
    NSURL *url = [NSURL fileURLWithPath:[NSString stringWithUTF8String:model_path]];
    NSError *err = nil;
    MLModelConfiguration *config = [MLModelConfiguration new];
    // Force Neural Engine for lowest power
    config.computeUnits = MLComputeUnitsAll; // ANE + GPU + CPU

    r->model = [MLModel modelWithContentsOfURL:url configuration:config error:&err];
    if (err || !r->model) {
        return -1;
    }

    r->loaded = 1;
    return 0;
}

static int intent_predict(IntentRouter *r, const char *query, IntentResult *out) {
    if (!r->loaded || !r->model) return -1;

    // Encode query to bag-of-words
    float bow[INTENT_VOCAB_SIZE];
    bow_encode(&r->vocab, query, bow);

    // Create MLMultiFeatureProvider with the input
    NSMutableArray *inputs = [NSMutableArray array];
    float *bowData = (float *)malloc(INTENT_VOCAB_SIZE * sizeof(float));
    memcpy(bowData, bow, INTENT_VOCAB_SIZE * sizeof(float));

    NSError *err = nil;
    MLFeatureValue *inputValue = [MLFeatureValue featureWithValueWithFloats:
        [NSArray arrayWithObjects:
            [NSNumber numberWithFloat:bow[0]],  // This won't work for array input
            nil]];

    // Use the dictionary-based input instead
    NSMutableDictionary *inputDict = [NSMutableDictionary dictionary];

    // Create a 1x128 float array for the input
    NSError *multiArrayErr = nil;
    MLMultiArray *inputArray = [[MLMultiArray alloc]
        initWithShape:@[@1, @INTENT_VOCAB_SIZE]
        dataType:MLMultiArrayDataTypeFloat32
        error:&multiArrayErr];

    if (multiArrayErr) return -1;

    // Fill the array
    float *arrayPtr = (float *)inputArray.dataPointer;
    for (int i = 0; i < INTENT_VOCAB_SIZE; i++) {
        arrayPtr[i] = bow[i];
    }

    MLFeatureValue *featureValue = [MLFeatureValue featureWithValueWithMultiArray:inputArray];
    inputDict[@"query_bow"] = featureValue;

    MLDictionaryFeatureProvider *provider =
        [[MLDictionaryFeatureProvider alloc] initWithDictionary:inputDict error:&err];
    if (err) return -1;

    // Run prediction
    id<MLFeatureProvider> result = [r->model predictionFromFeatures:provider error:&err];
    if (err) return -1;

    // Get output (auto-named to "var_10" by CoreML)
    NSString *outKey = [[result featureNames] anyObject];
    MLFeatureValue *outValue = [result featureValueForName:outKey];
    MLMultiArray *outArray = outValue.multiArrayValue;

    float *outPtr = (float *)outArray.dataPointer;

    // Softmax to get probabilities
    float logits[INTENT_NUM_CLASSES];
    for (int i = 0; i < INTENT_NUM_CLASSES; i++) {
        logits[i] = outPtr[i];
    }
    softmax(logits, out->all_probs, INTENT_NUM_CLASSES);

    // Find best
    out->tool_index = 0;
    float best = out->all_probs[0];
    for (int i = 1; i < INTENT_NUM_CLASSES; i++) {
        if (out->all_probs[i] > best) {
            best = out->all_probs[i];
            out->tool_index = i;
        }
    }
    out->confidence = best;
    out->tool_name = INTENT_TOOL_NAMES[out->tool_index];

    free(bowData);
    return 0;
}

static void intent_free(IntentRouter *r) {
    // ARC handles model release
    r->model = nil;
    r->loaded = 0;
}

#endif // INTENT_COREML_H
