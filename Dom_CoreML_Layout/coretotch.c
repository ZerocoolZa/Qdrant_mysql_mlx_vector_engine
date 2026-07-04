/*
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] coretotch.c
 *[@SUMMARY] C-based SGD training engine for 40-dim layout policy — CoreTotch
 *[@CLASS] none
 *[@METHOD] main
 *[@AUTHOR] Cascade
 *[@DATE] 2026-06-28
 *[@SESSION] coreml_layout_push
 *
 * CoreTotch: C does learning, CoreML does inference.
 *
 * Pipeline:
 *   1. C engine loads training data (JSON or binary)
 *   2. SGD weight updates on 40->128->128->10 MLP
 *   3. Export weights to weights.bin
 *   4. Python bridge injects weights into CoreML .mlpackage
 *   5. CoreML runs inference on Apple hardware (ANE/GPU)
 *
 * Build: cc -O2 -o coretotch coretotch.c -lm
 * Usage: ./coretotch train data.json weights.bin epochs
 *        ./coretotch infer weights.bin state.bin
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <dirent.h>

/* ── Model Dimensions ── */
#define INPUT_DIM   40
#define HIDDEN_DIM  128
#define OUTPUT_DIM  10

/* ── Weight Layout (row-major) ── */
/* W0: [HIDDEN_DIM x INPUT_DIM]  = 128*40 = 5120 */
/* B0: [HIDDEN_DIM]              = 128 */
/* W2: [HIDDEN_DIM x HIDDEN_DIM] = 128*128 = 16384 */
/* B2: [HIDDEN_DIM]              = 128 */
/* W4: [OUTPUT_DIM x HIDDEN_DIM] = 10*128 = 1280 */
/* B4: [OUTPUT_DIM]              = 10 */
/* Total params: 23050 (matches brain_model_v3.pt) */

#define W0_OFFSET 0
#define B0_OFFSET (W0_OFFSET + HIDDEN_DIM * INPUT_DIM)
#define W2_OFFSET (B0_OFFSET + HIDDEN_DIM)
#define B2_OFFSET (W2_OFFSET + HIDDEN_DIM * HIDDEN_DIM)
#define W4_OFFSET (B2_OFFSET + HIDDEN_DIM)
#define B4_OFFSET (W4_OFFSET + OUTPUT_DIM * HIDDEN_DIM)
#define TOTAL_PARAMS (B4_OFFSET + OUTPUT_DIM)

/* ── Activation ── */
static float relu(float x) {
    return x > 0.0f ? x : 0.0f;
}

static float relu_grad(float x) {
    return x > 0.0f ? 1.0f : 0.0f;
}

/* ── Forward Pass ── */
static void forward(float *weights, float *input, float *hidden0, float *hidden1, float *output) {
    /* fc0: input(40) -> hidden0(128) */
    for (int j = 0; j < HIDDEN_DIM; j++) {
        float sum = weights[B0_OFFSET + j];
        for (int i = 0; i < INPUT_DIM; i++) {
            sum += weights[W0_OFFSET + j * INPUT_DIM + i] * input[i];
        }
        hidden0[j] = relu(sum);
    }

    /* fc2: hidden0(128) -> hidden1(128) */
    for (int j = 0; j < HIDDEN_DIM; j++) {
        float sum = weights[B2_OFFSET + j];
        for (int i = 0; i < HIDDEN_DIM; i++) {
            sum += weights[W2_OFFSET + j * HIDDEN_DIM + i] * hidden0[i];
        }
        hidden1[j] = relu(sum);
    }

    /* fc4: hidden1(128) -> output(10) */
    for (int j = 0; j < OUTPUT_DIM; j++) {
        float sum = weights[B4_OFFSET + j];
        for (int i = 0; i < HIDDEN_DIM; i++) {
            sum += weights[W4_OFFSET + j * HIDDEN_DIM + i] * hidden1[i];
        }
        output[j] = sum;
    }
}

/* ── Backward Pass (SGD) ── */
static void backward(float *weights, float *input, float *hidden0, float *hidden1,
                     float *output, float *target, float lr) {
    float grad_out[OUTPUT_DIM];
    float grad_h1[HIDDEN_DIM];
    float grad_h0[HIDDEN_DIM];
    memset(grad_out, 0, sizeof(grad_out));
    memset(grad_h1, 0, sizeof(grad_h1));
    memset(grad_h0, 0, sizeof(grad_h0));

    /* Output layer gradient (MSE loss) */
    for (int j = 0; j < OUTPUT_DIM; j++) {
        grad_out[j] = (output[j] - target[j]) * lr;
    }

    /* Update W4, B4 and compute grad_h1 */
    for (int j = 0; j < OUTPUT_DIM; j++) {
        weights[B4_OFFSET + j] -= grad_out[j];
        for (int i = 0; i < HIDDEN_DIM; i++) {
            grad_h1[i] += grad_out[j] * weights[W4_OFFSET + j * HIDDEN_DIM + i];
            weights[W4_OFFSET + j * HIDDEN_DIM + i] -= grad_out[j] * hidden1[i];
        }
    }

    /* ReLU grad for hidden1 */
    for (int i = 0; i < HIDDEN_DIM; i++) {
        grad_h1[i] *= relu_grad(hidden1[i]);
    }

    /* Update W2, B2 and compute grad_h0 */
    for (int j = 0; j < HIDDEN_DIM; j++) {
        weights[B2_OFFSET + j] -= grad_h1[j];
        for (int i = 0; i < HIDDEN_DIM; i++) {
            grad_h0[i] += grad_h1[j] * weights[W2_OFFSET + j * HIDDEN_DIM + i];
            weights[W2_OFFSET + j * HIDDEN_DIM + i] -= grad_h1[j] * hidden0[i];
        }
    }

    /* ReLU grad for hidden0 */
    for (int i = 0; i < HIDDEN_DIM; i++) {
        grad_h0[i] *= relu_grad(hidden0[i]);
    }

    /* Update W0, B0 */
    for (int j = 0; j < HIDDEN_DIM; j++) {
        weights[B0_OFFSET + j] -= grad_h0[j];
        for (int i = 0; i < INPUT_DIM; i++) {
            weights[W0_OFFSET + j * INPUT_DIM + i] -= grad_h0[j] * input[i];
        }
    }
}

/* ── Simple JSON parser for training data ── */
/* Expects format: {"episodes":[{"steps":[{"state":[...],"action":[...]}]}]} */
typedef struct {
    float state[INPUT_DIM];
    float action[OUTPUT_DIM];
} TrainingSample;

static int parse_float_array(const char *json, const char *key, float *out, int max_count) {
    char pattern[64];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return 0;
    p += strlen(pattern);
    while (*p && (*p == ' ' || *p == ':' || *p == '\t' || *p == '\n')) p++;
    if (*p != '[') return 0;
    p++;
    int count = 0;
    while (*p && count < max_count) {
        if (*p == ']') break;
        if (*p == ',' || *p == ' ' || *p == '\n' || *p == '\t' || *p == '\r') { p++; continue; }
        out[count] = (float)atof(p);
        count++;
        while (*p && *p != ',' && *p != ']') p++;
    }
    return count;
}

static int load_training_data(const char *path, TrainingSample *samples, int max_samples) {
    FILE *f = fopen(path, "r");
    if (!f) {
        fprintf(stderr, "Cannot open %s\n", path);
        return -1;
    }
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *json = (char *)malloc(size + 1);
    fread(json, 1, size, f);
    json[size] = '\0';
    fclose(f);

    int count = 0;
    const char *p = json;
    while (count < max_samples) {
        const char *step = strstr(p, "\"state\"");
        if (!step) break;
        int n_state = parse_float_array(step, "state", samples[count].state, INPUT_DIM);
        int n_action = parse_float_array(step, "action", samples[count].action, OUTPUT_DIM);
        if (n_state == INPUT_DIM && n_action == OUTPUT_DIM) {
            count++;
        }
        p = step + 8;
    }
    free(json);
    return count;
}

/* ── Save / Load weights ── */
static int save_weights(const char *path, float *weights) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fwrite(weights, sizeof(float), TOTAL_PARAMS, f);
    fclose(f);
    return 0;
}

static int load_weights(const char *path, float *weights) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fread(weights, sizeof(float), TOTAL_PARAMS, f);
    fclose(f);
    return 0;
}

/* ── Init weights (Xavier) ── */
static void init_weights(float *weights) {
    srand((unsigned)time(NULL));
    float limit0 = sqrtf(6.0f / (INPUT_DIM + HIDDEN_DIM));
    for (int i = W0_OFFSET; i < B0_OFFSET; i++) {
        weights[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * limit0;
    }
    for (int i = B0_OFFSET; i < W2_OFFSET; i++) weights[i] = 0.0f;

    float limit2 = sqrtf(6.0f / (HIDDEN_DIM + HIDDEN_DIM));
    for (int i = W2_OFFSET; i < B2_OFFSET; i++) {
        weights[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * limit2;
    }
    for (int i = B2_OFFSET; i < W4_OFFSET; i++) weights[i] = 0.0f;

    float limit4 = sqrtf(6.0f / (HIDDEN_DIM + OUTPUT_DIM));
    for (int i = W4_OFFSET; i < B4_OFFSET; i++) {
        weights[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * limit4;
    }
    for (int i = B4_OFFSET; i < TOTAL_PARAMS; i++) weights[i] = 0.0f;
}

/* ── Load weights from PyTorch .pt (binary float32 export) ── */
static int load_pytorch_weights(const char *path, float *weights) {
    /* Expects pre-export binary: w0, b0, w2, b2, w4, b4 concatenated */
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fread(weights, sizeof(float), TOTAL_PARAMS, f);
    fclose(f);
    return 0;
}

/* ── Main ── */
int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "CoreTotch — C SGD engine for 40-dim layout policy\n");
        fprintf(stderr, "Usage:\n");
        fprintf(stderr, "  %s train  <data.json> <weights_out.bin> [epochs] [lr] [init_weights.bin]\n", argv[0]);
        fprintf(stderr, "  %s infer  <weights.bin> <state.bin>\n", argv[0]);
        fprintf(stderr, "  %s export <weights.bin> <coreml_weights.bin>\n", argv[0]);
        fprintf(stderr, "\nPipeline: C trains -> weights.bin -> Python injects into CoreML\n");
        return 1;
    }

    if (strcmp(argv[1], "train") == 0) {
        if (argc < 4) {
            fprintf(stderr, "train requires: data.json weights_out.bin [epochs] [lr] [init.bin]\n");
            return 1;
        }
        const char *dataPath = argv[2];
        const char *weightsPath = argv[3];
        int epochs = argc > 4 ? atoi(argv[4]) : 50;
        float lr = argc > 5 ? (float)atof(argv[5]) : 0.001f;
        const char *initPath = argc > 6 ? argv[6] : NULL;

        float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
        if (initPath) {
            if (load_weights(initPath, weights) != 0) {
                fprintf(stderr, "Init weights not found, using Xavier init\n");
                init_weights(weights);
            }
        } else {
            init_weights(weights);
        }

        TrainingSample *samples = (TrainingSample *)malloc(sizeof(TrainingSample) * 10000);
        int nSamples = load_training_data(dataPath, samples, 10000);
        if (nSamples <= 0) {
            fprintf(stderr, "No training samples loaded\n");
            free(weights);
            free(samples);
            return 1;
        }

        fprintf(stderr, "CoreTotch: %d samples, %d epochs, lr=%.4f\n", nSamples, epochs, lr);

        float hidden0[HIDDEN_DIM], hidden1[HIDDEN_DIM], output[OUTPUT_DIM];

        for (int epoch = 0; epoch < epochs; epoch++) {
            float totalLoss = 0.0f;
            for (int s = 0; s < nSamples; s++) {
                forward(weights, samples[s].state, hidden0, hidden1, output);
                backward(weights, samples[s].state, hidden0, hidden1, output, samples[s].action, lr);
                for (int j = 0; j < OUTPUT_DIM; j++) {
                    float diff = output[j] - samples[s].action[j];
                    totalLoss += diff * diff;
                }
            }
            float avgLoss = totalLoss / (nSamples * OUTPUT_DIM);
            fprintf(stderr, "  Epoch %d/%d — Loss: %.6f\n", epoch + 1, epochs, avgLoss);
        }

        save_weights(weightsPath, weights);
        fprintf(stderr, "Weights saved to %s (%d params)\n", weightsPath, TOTAL_PARAMS);

        free(weights);
        free(samples);
        return 0;
    }

    if (strcmp(argv[1], "infer") == 0) {
        if (argc < 4) {
            fprintf(stderr, "infer requires: weights.bin state.bin\n");
            return 1;
        }
        float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
        load_weights(argv[2], weights);

        float input[INPUT_DIM];
        FILE *f = fopen(argv[3], "rb");
        if (!f) { fprintf(stderr, "Cannot open %s\n", argv[3]); return 1; }
        fread(input, sizeof(float), INPUT_DIM, f);
        fclose(f);

        float hidden0[HIDDEN_DIM], hidden1[HIDDEN_DIM], output[OUTPUT_DIM];
        forward(weights, input, hidden0, hidden1, output);

        fprintf(stderr, "Output: ");
        for (int j = 0; j < OUTPUT_DIM; j++) {
            fprintf(stderr, "%.4f ", output[j]);
        }
        fprintf(stderr, "\n");
        free(weights);
        return 0;
    }

    if (strcmp(argv[1], "export") == 0) {
        if (argc < 4) {
            fprintf(stderr, "export requires: weights.bin coreml_weights.bin\n");
            return 1;
        }
        float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
        load_weights(argv[2], weights);
        save_weights(argv[3], weights);
        fprintf(stderr, "Exported %d params to %s\n", TOTAL_PARAMS, argv[3]);
        free(weights);
        return 0;
    }

    if (strcmp(argv[1], "select") == 0) {
        /* Runtime expert selection: load manifest, pick expert, run inference */
        /* Usage: ./coretotch select <expert_dir>/<name>.weights.bin <state.bin> */
        if (argc < 4) {
            fprintf(stderr, "select requires: <expert_name>.weights.bin state.bin\n");
            fprintf(stderr, "Available experts are in experts/ directory\n");
            return 1;
        }
        float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
        if (load_weights(argv[2], weights) != 0) {
            fprintf(stderr, "Cannot load expert weights: %s\n", argv[2]);
            free(weights);
            return 1;
        }
        fprintf(stderr, "Expert loaded: %s\n", argv[2]);

        float input[INPUT_DIM];
        FILE *f = fopen(argv[3], "rb");
        if (!f) { fprintf(stderr, "Cannot open state: %s\n", argv[3]); free(weights); return 1; }
        fread(input, sizeof(float), INPUT_DIM, f);
        fclose(f);

        float hidden0[HIDDEN_DIM], hidden1[HIDDEN_DIM], output[OUTPUT_DIM];
        forward(weights, input, hidden0, hidden1, output);

        fprintf(stderr, "Expert output: ");
        for (int j = 0; j < OUTPUT_DIM; j++) {
            fprintf(stderr, "%.4f ", output[j]);
        }
        fprintf(stderr, "\n");
        free(weights);
        return 0;
    }

    if (strcmp(argv[1], "list_experts") == 0) {
        /* List available expert weight files in experts/ directory */
        fprintf(stderr, "Available experts (weights.bin files in experts/):\n");
        DIR *dir;
        struct dirent *ent;
        const char *expDir = "experts";
        dir = opendir(expDir);
        if (!dir) {
            fprintf(stderr, "  No experts/ directory found\n");
            return 1;
        }
        int count = 0;
        while ((ent = readdir(dir)) != NULL) {
            if (strstr(ent->d_name, ".weights.bin")) {
                fprintf(stderr, "  %s/%s\n", expDir, ent->d_name);
                count++;
            }
        }
        closedir(dir);
        fprintf(stderr, "Total: %d experts\n", count);
        return 0;
    }

    if (strcmp(argv[1], "ensemble") == 0) {
        /* Ensemble: load multiple expert weights, average forward pass
         * Usage: ./coretotch ensemble <state.bin> <w1.bin> <w2.bin> [w3.bin] ...
         * Loads each weight file, runs forward, averages outputs
         */
        if (argc < 4) {
            fprintf(stderr, "ensemble requires: state.bin w1.bin w2.bin [w3.bin ...]\n");
            return 1;
        }
        int nExperts = argc - 3;
        float *input = (float *)malloc(sizeof(float) * INPUT_DIM);
        FILE *f = fopen(argv[2], "rb");
        if (!f) { fprintf(stderr, "Cannot open state: %s\n", argv[2]); free(input); return 1; }
        fread(input, sizeof(float), INPUT_DIM, f);
        fclose(f);

        float *outputSum = (float *)calloc(OUTPUT_DIM, sizeof(float));
        float hidden0[HIDDEN_DIM], hidden1[HIDDEN_DIM], output[OUTPUT_DIM];

        for (int e = 0; e < nExperts; e++) {
            float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
            const char *wPath = argv[3 + e];
            if (load_weights(wPath, weights) != 0) {
                fprintf(stderr, "Cannot load expert %d: %s\n", e, wPath);
                free(weights);
                continue;
            }
            forward(weights, input, hidden0, hidden1, output);
            for (int j = 0; j < OUTPUT_DIM; j++) {
                outputSum[j] += output[j];
            }
            fprintf(stderr, "  Expert %d (%s): loaded\n", e, wPath);
            free(weights);
        }

        fprintf(stderr, "Ensemble output (%d experts, averaged):\n  ", nExperts);
        for (int j = 0; j < OUTPUT_DIM; j++) {
            outputSum[j] /= nExperts;
            fprintf(stderr, "%.4f ", outputSum[j]);
        }
        fprintf(stderr, "\n");

        free(input);
        free(outputSum);
        return 0;
    }

    if (strcmp(argv[1], "list_bank") == 0) {
        /* List all versioned models in model_bank/ directory */
        fprintf(stderr, "Model Bank (versioned weights in model_bank/):\n");
        DIR *dir;
        struct dirent *ent;
        const char *bankDir = "model_bank";
        dir = opendir(bankDir);
        if (!dir) {
            fprintf(stderr, "  No model_bank/ directory found\n");
            return 1;
        }
        int count = 0;
        while ((ent = readdir(dir)) != NULL) {
            if (strstr(ent->d_name, ".weights.bin")) {
                fprintf(stderr, "  %s/%s\n", bankDir, ent->d_name);
                count++;
            }
        }
        closedir(dir);
        fprintf(stderr, "Total: %d model versions in bank\n", count);
        return 0;
    }

    if (strcmp(argv[1], "hotcache") == 0) {
        /* Hot cache mode: keep N models in RAM, swap between them
         * Usage: ./coretotch hotcache <state.bin> <cache_size> <w1.bin> <w2.bin> ...
         * Loads up to cache_size models into RAM, runs inference on each,
         * reports which are HOT vs COLD.
         */
        if (argc < 5) {
            fprintf(stderr, "hotcache requires: state.bin cache_size w1.bin [w2.bin ...]\n");
            return 1;
        }
        int cacheSize = atoi(argv[3]);
        int nAvailable = argc - 4;
        int nHot = (nAvailable < cacheSize) ? nAvailable : cacheSize;

        fprintf(stderr, "Hot Cache: %d slots, %d models available\n", cacheSize, nAvailable);

        /* Load state */
        float input[INPUT_DIM];
        FILE *f = fopen(argv[2], "rb");
        if (!f) { fprintf(stderr, "Cannot open state: %s\n", argv[2]); return 1; }
        fread(input, sizeof(float), INPUT_DIM, f);
        fclose(f);

        /* Allocate cache: array of weight pointers */
        float **cache = (float **)malloc(sizeof(float *) * cacheSize);
        char **cacheNames = (char **)malloc(sizeof(char *) * cacheSize);
        for (int i = 0; i < cacheSize; i++) {
            cache[i] = NULL;
            cacheNames[i] = NULL;
        }

        /* Load hot models */
        for (int i = 0; i < nHot; i++) {
            cache[i] = (float *)calloc(TOTAL_PARAMS, sizeof(float));
            const char *wPath = argv[4 + i];
            if (load_weights(wPath, cache[i]) != 0) {
                fprintf(stderr, "  Failed to load: %s\n", wPath);
                free(cache[i]);
                cache[i] = NULL;
                continue;
            }
            cacheNames[i] = strdup(wPath);
            fprintf(stderr, "  HOT [%d]: %s (%d KB)\n", i, wPath, TOTAL_PARAMS * 4 / 1024);
        }

        /* Run inference on each hot model */
        float hidden0[HIDDEN_DIM], hidden1[HIDDEN_DIM], output[OUTPUT_DIM];
        for (int i = 0; i < nHot; i++) {
            if (!cache[i]) continue;
            forward(cache[i], input, hidden0, hidden1, output);
            fprintf(stderr, "  Expert %d output: ", i);
            for (int j = 0; j < OUTPUT_DIM; j++) {
                fprintf(stderr, "%.4f ", output[j]);
            }
            fprintf(stderr, "\n");
        }

        /* Report cold models */
        for (int i = nHot; i < nAvailable; i++) {
            fprintf(stderr, "  COLD [%d]: %s (on disk, 0 RAM)\n", i, argv[4 + i]);
        }

        /* Simulate swap: evict slot 0, load next cold model */
        if (nAvailable > nHot && nHot > 0) {
            fprintf(stderr, "\n  --- Simulating swap: evict %s, load %s ---\n",
                    cacheNames[0], argv[4 + nHot]);
            free(cache[0]);
            cache[0] = (float *)calloc(TOTAL_PARAMS, sizeof(float));
            if (load_weights(argv[4 + nHot], cache[0]) == 0) {
                free(cacheNames[0]);
                cacheNames[0] = strdup(argv[4 + nHot]);
                forward(cache[0], input, hidden0, hidden1, output);
                fprintf(stderr, "  Swapped expert output: ");
                for (int j = 0; j < OUTPUT_DIM; j++) {
                    fprintf(stderr, "%.4f ", output[j]);
                }
                fprintf(stderr, "\n");
                fprintf(stderr, "  RAM unchanged: %d KB (swapped in-place)\n", TOTAL_PARAMS * 4 / 1024);
            }
        }

        /* Cleanup */
        for (int i = 0; i < cacheSize; i++) {
            if (cache[i]) free(cache[i]);
            if (cacheNames[i]) free(cacheNames[i]);
        }
        free(cache);
        free(cacheNames);
        return 0;
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    fprintf(stderr, "Commands: train, infer, export, select, ensemble, hotcache, list_experts, list_bank\n");
    return 1;
}
