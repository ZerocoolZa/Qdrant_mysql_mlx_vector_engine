/*
 *[@GHOST]
 *[@VBSTYLE]
 *[@FILEID] coretotch_fix.c
 *[@SUMMARY] C-based SGD training engine for 40->64->16 error fix classifier
 *[@CLASS] none
 *[@METHOD] main
 *[@AUTHOR] Cascade
 *[@DATE] 2026-06-28
 *[@SESSION] cli_ai_fix_coreml
 *
 * CoreTotch Fix: C does learning, cascade_cli does inference.
 * Same architecture pattern as Dom_CoreML_Layout/coretotch.c
 *
 * Pipeline:
 *   1. ai_fix_data_gen.c generates JSON training data
 *   2. This engine trains 40->64->16 MLP with SGD + momentum + cross-entropy
 *   3. Export weights to flat binary (no header — raw float32)
 *   4. cascade_cli loads weights directly for C inference
 *   5. Optional: CoreTotchBridge injects into CoreML .mlpackage
 *
 * Build: cc -O2 -o coretotch_fix coretotch_fix.c -lm
 * Usage: ./coretotch_fix train  data.json weights.bin [epochs] [lr] [init.bin]
 *        ./coretotch_fix infer  weights.bin state.bin
 *        ./coretotch_fix export weights.bin coreml_weights.bin
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <sys/statvfs.h>
#include <sys/sysctl.h>
#include <unistd.h>

/* ── Resource Guard Config (loaded from coretotch_fix.conf) ── */
#define MAX_BUF              4096
#define CONFIG_PATH_DEFAULT  "coretotch_fix.conf"

typedef struct {
    float min_ram_gb;
    float warn_ram_gb;
    int   min_disk_mb;
    int   max_train_memory_mb;
    int   ram_check_interval;
    int   ram_pause_wait_sec;
    int   ram_pause_max_retries;
} ResourceConfig;

/* Defaults — used if config file not found */
static void config_defaults(ResourceConfig *c) {
    c->min_ram_gb          = 0.5f;
    c->warn_ram_gb         = 1.0f;
    c->min_disk_mb         = 100;
    c->max_train_memory_mb = 512;
    c->ram_check_interval  = 10;
    c->ram_pause_wait_sec  = 5;
    c->ram_pause_max_retries = 6;
}

/* Load config from file — simple key=value format, # comments */
static void config_load(ResourceConfig *c, const char *path) {
    config_defaults(c);

    FILE *f = fopen(path, "r");
    if (!f) return;  /* silently use defaults */

    char line[256];
    while (fgets(line, sizeof(line), f)) {
        /* Skip comments and blank lines */
        char *p = line;
        while (*p == ' ' || *p == '\t') p++;
        if (*p == '#' || *p == '\n' || *p == '\0') continue;

        /* Parse key = value */
        char *eq = strchr(p, '=');
        if (!eq) continue;
        *eq = '\0';
        char *key = p;
        char *val = eq + 1;

        /* Trim whitespace from key */
        char *kend = key + strlen(key) - 1;
        while (kend > key && (*kend == ' ' || *kend == '\t')) *kend-- = '\0';

        /* Trim whitespace from value */
        while (*val == ' ' || *val == '\t') val++;
        char *vend = val + strlen(val) - 1;
        while (vend > val && (*vend == ' ' || *vend == '\t' || *vend == '\n' || *vend == '\r'))
            *vend-- = '\0';

        /* Map keys to struct fields */
        if (strcmp(key, "MIN_RAM_GB") == 0)
            c->min_ram_gb = (float)atof(val);
        else if (strcmp(key, "WARN_RAM_GB") == 0)
            c->warn_ram_gb = (float)atof(val);
        else if (strcmp(key, "MIN_DISK_MB") == 0)
            c->min_disk_mb = atoi(val);
        else if (strcmp(key, "MAX_TRAIN_MEMORY_MB") == 0)
            c->max_train_memory_mb = atoi(val);
        else if (strcmp(key, "RAM_CHECK_INTERVAL") == 0)
            c->ram_check_interval = atoi(val);
        else if (strcmp(key, "RAM_PAUSE_WAIT_SEC") == 0)
            c->ram_pause_wait_sec = atoi(val);
        else if (strcmp(key, "RAM_PAUSE_MAX_RETRIES") == 0)
            c->ram_pause_max_retries = atoi(val);
    }
    fclose(f);
}

/* Env var overrides config file — highest priority */
static void config_apply_env(ResourceConfig *c) {
    const char *e;
    if ((e = getenv("SAFE_RAM_GB")))       c->min_ram_gb = (float)atof(e);
    if ((e = getenv("SAFE_RAM_WARN_GB")))  c->warn_ram_gb = (float)atof(e);
    if ((e = getenv("SAFE_DISK_MB")))      c->min_disk_mb = atoi(e);
    if ((e = getenv("SAFE_MAX_MEM_MB")))   c->max_train_memory_mb = atoi(e);
}

/* ── Model Dimensions ── */
#define INPUT_DIM   40
#define HIDDEN_DIM  64
#define OUTPUT_DIM  16

/* ── Weight Layout (row-major, flat binary — no header) ── */
/* W0: [HIDDEN_DIM x INPUT_DIM]  = 64*40 = 2560 */
/* B0: [HIDDEN_DIM]              = 64 */
/* W2: [OUTPUT_DIM x HIDDEN_DIM] = 16*64 = 1024 */
/* B2: [OUTPUT_DIM]              = 16 */
/* Total params: 3664 */

#define W0_OFFSET 0
#define B0_OFFSET (W0_OFFSET + HIDDEN_DIM * INPUT_DIM)
#define W2_OFFSET (B0_OFFSET + HIDDEN_DIM)
#define B2_OFFSET (W2_OFFSET + OUTPUT_DIM * HIDDEN_DIM)
#define TOTAL_PARAMS (B2_OFFSET + OUTPUT_DIM)

/* ── Activation ── */
static float relu(float x) { return x > 0.0f ? x : 0.0f; }
static float relu_grad(float x) { return x > 0.0f ? 1.0f : 0.0f; }

/* ── Softmax ── */
static void softmax(float *x, int n) {
    float maxVal = x[0];
    for (int i = 1; i < n; i++)
        if (x[i] > maxVal) maxVal = x[i];
    float sum = 0.0f;
    for (int i = 0; i < n; i++) {
        x[i] = expf(x[i] - maxVal);
        sum += x[i];
    }
    for (int i = 0; i < n; i++)
        x[i] /= sum;
}

/* ── Forward Pass ── */
static void forward(float *w, float *input, float *hidden, float *output) {
    for (int j = 0; j < HIDDEN_DIM; j++) {
        float s = w[B0_OFFSET + j];
        for (int i = 0; i < INPUT_DIM; i++)
            s += w[W0_OFFSET + j * INPUT_DIM + i] * input[i];
        hidden[j] = relu(s);
    }
    for (int k = 0; k < OUTPUT_DIM; k++) {
        float s = w[B2_OFFSET + k];
        for (int j = 0; j < HIDDEN_DIM; j++)
            s += w[W2_OFFSET + k * HIDDEN_DIM + j] * hidden[j];
        output[k] = s;
    }
    softmax(output, OUTPUT_DIM);
}

/* ── Backward Pass (SGD + momentum + cross-entropy) ── */
static void backward(float *w, float *vel, float *input, float *hidden,
                     float *output, float *target, float lr, float mom) {
    float grad_out[OUTPUT_DIM];
    float grad_h[HIDDEN_DIM];
    memset(grad_h, 0, sizeof(grad_h));

    for (int k = 0; k < OUTPUT_DIM; k++)
        grad_out[k] = (output[k] - target[k]) * lr;

    for (int k = 0; k < OUTPUT_DIM; k++) {
        vel[B2_OFFSET + k] = mom * vel[B2_OFFSET + k] - grad_out[k];
        w[B2_OFFSET + k] += vel[B2_OFFSET + k];
        for (int j = 0; j < HIDDEN_DIM; j++) {
            grad_h[j] += grad_out[k] * w[W2_OFFSET + k * HIDDEN_DIM + j];
            int idx = W2_OFFSET + k * HIDDEN_DIM + j;
            vel[idx] = mom * vel[idx] - grad_out[k] * hidden[j];
            w[idx] += vel[idx];
        }
    }

    for (int j = 0; j < HIDDEN_DIM; j++)
        grad_h[j] *= relu_grad(hidden[j]);

    for (int j = 0; j < HIDDEN_DIM; j++) {
        vel[B0_OFFSET + j] = mom * vel[B0_OFFSET + j] - grad_h[j];
        w[B0_OFFSET + j] += vel[B0_OFFSET + j];
        for (int i = 0; i < INPUT_DIM; i++) {
            int idx = W0_OFFSET + j * INPUT_DIM + i;
            vel[idx] = mom * vel[idx] - grad_h[j] * input[i];
            w[idx] += vel[idx];
        }
    }
}

/* ── Training Sample ── */
typedef struct {
    float state[INPUT_DIM];
    float action[OUTPUT_DIM];
} TrainingSample;

/* ── JSON parser (same format as coretotch.c) ── */
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
    if (!f) { fprintf(stderr, "Cannot open %s\n", path); return -1; }
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
        if (n_state == INPUT_DIM && n_action == OUTPUT_DIM)
            count++;
        p = step + 8;
    }
    free(json);
    return count;
}

/* ── Save / Load weights (flat binary, no header) ── */
static int save_weights(const char *path, float *w) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fwrite(w, sizeof(float), TOTAL_PARAMS, f);
    fclose(f);
    return 0;
}

static int load_weights(const char *path, float *w) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    fread(w, sizeof(float), TOTAL_PARAMS, f);
    fclose(f);
    return 0;
}

/* ── Xavier init ── */
static void init_weights(float *w) {
    srand((unsigned)time(NULL));
    float lim0 = sqrtf(6.0f / (INPUT_DIM + HIDDEN_DIM));
    for (int i = W0_OFFSET; i < B0_OFFSET; i++)
        w[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * lim0;
    for (int i = B0_OFFSET; i < W2_OFFSET; i++) w[i] = 0.0f;
    float lim2 = sqrtf(6.0f / (HIDDEN_DIM + OUTPUT_DIM));
    for (int i = W2_OFFSET; i < B2_OFFSET; i++)
        w[i] = ((float)rand() / RAND_MAX - 0.5f) * 2.0f * lim2;
    for (int i = B2_OFFSET; i < TOTAL_PARAMS; i++) w[i] = 0.0f;
}

/* ── Resource Guard: check available RAM via sysctl (macOS) ── */
static float check_ram_gb(void) {
    int mib[2] = {CTL_HW, HW_MEMSIZE};
    uint64_t total_ram = 0;
    size_t len = sizeof(total_ram);
    if (sysctl(mib, 2, &total_ram, &len, NULL, 0) != 0)
        return -1.0f;

    /* Get page size and free pages via vm_stat */
    FILE *fp = popen("vm_stat", "r");
    if (!fp)
        return (float)total_ram / (1024.0f * 1024.0f * 1024.0f);

    int page_size = 4096;
    long free_pages = 0, inactive_pages = 0;
    char line[256];
    while (fgets(line, sizeof(line), fp)) {
        if (strstr(line, "page size of")) {
            char *p = strstr(line, "of ");
            if (p) page_size = atoi(p + 3);
        }
        if (strstr(line, "Pages free:") || strstr(line, "Pages free ")) {
            char *col = strchr(line, ':');
            if (col) free_pages = atol(col + 1);
        }
        if (strstr(line, "Pages inactive:") || strstr(line, "Pages inactive ")) {
            char *col = strchr(line, ':');
            if (col) inactive_pages = atol(col + 1);
        }
    }
    pclose(fp);

    long available = (free_pages + inactive_pages) * page_size;
    return (float)available / (1024.0f * 1024.0f * 1024.0f);
}

/* ── Resource Guard: check disk space for output path ── */
static long check_disk_mb(const char *path) {
    struct statvfs vfs;
    char dir[MAX_BUF];

    /* Get directory of output path */
    snprintf(dir, sizeof(dir), "%s", path);
    char *slash = strrchr(dir, '/');
    if (slash) slash[1] = '\0';
    else { dir[0] = '.'; dir[1] = '/'; dir[2] = '\0'; }

    if (statvfs(dir, &vfs) != 0)
        return -1;

    return (long)((long long)vfs.f_bavail * vfs.f_frsize / (1024 * 1024));
}

/* ── Resource Guard: estimate training memory in MB ── */
static float estimate_train_memory_mb(int n_samples) {
    /* weights: 3664 * 4 bytes = 14KB */
    /* velocity: same = 14KB */
    /* samples: n * (40+16) * 4 bytes */
    /* hidden/output buffers: negligible */
    float weights_mb = (float)TOTAL_PARAMS * 4.0f / (1024.0f * 1024.0f);
    float velocity_mb = weights_mb;
    float samples_mb = (float)n_samples * (INPUT_DIM + OUTPUT_DIM) * 4.0f / (1024.0f * 1024.0f);
    float indices_mb = (float)n_samples * sizeof(int) / (1024.0f * 1024.0f);
    return weights_mb + velocity_mb + samples_mb + indices_mb;
}

/* ── Main ── */
int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "CoreTotch Fix — C SGD engine for 40->64->16 error fix classifier\n");
        fprintf(stderr, "Usage:\n");
        fprintf(stderr, "  %s train  <data.json> <weights_out.bin> [epochs] [lr] [init.bin]\n", argv[0]);
        fprintf(stderr, "  %s infer  <weights.bin> <state.bin>\n", argv[0]);
        fprintf(stderr, "  %s export <weights.bin> <coreml_weights.bin>\n", argv[0]);
        fprintf(stderr, "\nModel: %d->%d->%d (%d params, %d bytes)\n",
                INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM, TOTAL_PARAMS, (int)(TOTAL_PARAMS * 4));
        fprintf(stderr, "Config: %s (env vars override: SAFE_RAM_GB, SAFE_RAM_WARN_GB, SAFE_DISK_MB, SAFE_MAX_MEM_MB)\n",
                CONFIG_PATH_DEFAULT);
        return 1;
    }

    if (strcmp(argv[1], "train") == 0) {
        if (argc < 4) {
            fprintf(stderr, "train requires: data.json weights_out.bin [epochs] [lr] [init.bin]\n");
            return 1;
        }
        const char *dataPath = argv[2];
        const char *weightsPath = argv[3];
        int epochs = argc > 4 ? atoi(argv[4]) : 300;
        float lr = argc > 5 ? (float)atof(argv[5]) : 0.005f;
        const char *initPath = argc > 6 ? argv[6] : NULL;
        float momentum = 0.9f;

        /* ── Load resource config from file, then apply env overrides ── */
        ResourceConfig rcfg;
        config_load(&rcfg, CONFIG_PATH_DEFAULT);
        config_apply_env(&rcfg);

        float *weights = (float *)calloc(TOTAL_PARAMS, sizeof(float));
        float *velocity = (float *)calloc(TOTAL_PARAMS, sizeof(float));

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
            free(weights); free(velocity); free(samples);
            return 1;
        }

        /* ── Resource Guard: check RAM, disk, estimated memory ── */
        float free_ram = check_ram_gb();
        long free_disk = check_disk_mb(weightsPath);
        float est_mem = estimate_train_memory_mb(nSamples);

        fprintf(stderr, "CoreTotch Fix: %d samples, %d epochs, lr=%.4f, momentum=%.1f\n",
                nSamples, epochs, lr, momentum);
        fprintf(stderr, "Model: %d->%d->%d (%d params)\n",
                INPUT_DIM, HIDDEN_DIM, OUTPUT_DIM, TOTAL_PARAMS);
        fprintf(stderr, "Config: %s\n", CONFIG_PATH_DEFAULT);
        fprintf(stderr, "Resources: RAM free=%.2f GB (min=%.2f), disk free=%ld MB (min=%d), est train mem=%.2f MB (max=%d)\n",
                free_ram, rcfg.min_ram_gb, free_disk, rcfg.min_disk_mb, est_mem, rcfg.max_train_memory_mb);

        if (free_ram > 0 && free_ram < rcfg.min_ram_gb) {
            fprintf(stderr, "\n[ABORT] Free RAM %.2f GB < minimum %.2f GB. Close other apps and retry.\n",
                    free_ram, rcfg.min_ram_gb);
            free(weights); free(velocity); free(samples);
            return 2;
        }
        if (free_disk >= 0 && free_disk < rcfg.min_disk_mb) {
            fprintf(stderr, "\n[ABORT] Free disk %ld MB < minimum %d MB. Clean up disk space.\n",
                    free_disk, rcfg.min_disk_mb);
            free(weights); free(velocity); free(samples);
            return 2;
        }
        if (est_mem > rcfg.max_train_memory_mb) {
            fprintf(stderr, "\n[ABORT] Estimated train memory %.1f MB > max %d MB. Reduce sample count.\n",
                    est_mem, rcfg.max_train_memory_mb);
            free(weights); free(velocity); free(samples);
            return 2;
        }
        fprintf(stderr, "Resource check: OK\n\n");

        float hidden[HIDDEN_DIM], output[OUTPUT_DIM];
        int ram_aborted = 0;

        for (int epoch = 0; epoch < epochs; epoch++) {
            float totalLoss = 0.0f;
            int correct = 0;

            /* ── Periodic RAM monitor during training ── */
            if (epoch > 0 && epoch % rcfg.ram_check_interval == 0) {
                float current_ram = check_ram_gb();
                if (current_ram > 0 && current_ram < rcfg.min_ram_gb) {
                    int retries = 0;
                    fprintf(stderr, "  [RAM GUARD] Epoch %d: free RAM %.2f GB < limit %.2f GB — pausing...\n",
                            epoch + 1, current_ram, rcfg.min_ram_gb);
                    while (retries < rcfg.ram_pause_max_retries) {
                        fprintf(stderr, "  [RAM GUARD] Paused %d/%d — waiting %d sec for RAM to free...\n",
                                retries + 1, rcfg.ram_pause_max_retries, rcfg.ram_pause_wait_sec);
                        sleep(rcfg.ram_pause_wait_sec);
                        current_ram = check_ram_gb();
                        fprintf(stderr, "  [RAM GUARD] Recheck: free RAM = %.2f GB\n", current_ram);
                        if (current_ram >= rcfg.min_ram_gb) {
                            fprintf(stderr, "  [RAM GUARD] RAM recovered — resuming training\n");
                            break;
                        }
                        retries++;
                    }
                    if (current_ram < rcfg.min_ram_gb) {
                        fprintf(stderr, "  [RAM GUARD] RAM did not recover after %d pauses — aborting\n",
                                rcfg.ram_pause_max_retries);
                        fprintf(stderr, "  [RAM GUARD] Saving partial weights to %s\n", weightsPath);
                        save_weights(weightsPath, weights);
                        ram_aborted = 1;
                        break;
                    }
                } else if (current_ram > 0 && current_ram < rcfg.warn_ram_gb) {
                    fprintf(stderr, "  [RAM GUARD] Epoch %d: free RAM %.2f GB — WARNING approaching limit\n",
                            epoch + 1, current_ram);
                }
            }

            /* Shuffle */
            int *indices = (int *)malloc(sizeof(int) * nSamples);
            for (int i = 0; i < nSamples; i++) indices[i] = i;
            for (int i = nSamples - 1; i > 0; i--) {
                int j = rand() % (i + 1);
                int tmp = indices[i]; indices[i] = indices[j]; indices[j] = tmp;
            }

            for (int s = 0; s < nSamples; s++) {
                int idx = indices[s];
                forward(weights, samples[idx].state, hidden, output);
                backward(weights, velocity, samples[idx].state, hidden,
                         output, samples[idx].action, lr, momentum);

                float eps = 1e-7f;
                for (int k = 0; k < OUTPUT_DIM; k++) {
                    if (samples[idx].action[k] > 0.5f)
                        totalLoss += -logf(output[k] + eps);
                }

                int predIdx = 0, targetIdx = 0;
                float predVal = output[0];
                for (int k = 1; k < OUTPUT_DIM; k++)
                    if (output[k] > predVal) { predVal = output[k]; predIdx = k; }
                for (int k = 0; k < OUTPUT_DIM; k++)
                    if (samples[idx].action[k] > 0.5f) { targetIdx = k; break; }
                if (predIdx == targetIdx) correct++;
            }

            free(indices);

            float avgLoss = totalLoss / nSamples;
            float accuracy = (float)correct / nSamples * 100.0f;

            if ((epoch + 1) % 50 == 0 || epoch == 0) {
                fprintf(stderr, "  Epoch %d/%d  Loss: %.4f  Acc: %.1f%%\n",
                        epoch + 1, epochs, avgLoss, accuracy);
            }
        }

        if (ram_aborted) {
            fprintf(stderr, "\nTraining aborted due to RAM pressure.\n");
            fprintf(stderr, "Partial weights saved. Re-run with fewer samples or close apps.\n");
            free(weights); free(velocity); free(samples);
            return 3;
        }

        save_weights(weightsPath, weights);
        fprintf(stderr, "\nWeights saved to %s (%d params, %d bytes)\n",
                weightsPath, TOTAL_PARAMS, (int)(TOTAL_PARAMS * 4));

        /* Final accuracy */
        float hidden_f[HIDDEN_DIM], output_f[OUTPUT_DIM];
        int correct = 0;
        for (int s = 0; s < nSamples; s++) {
            forward(weights, samples[s].state, hidden_f, output_f);
            int predIdx = 0, targetIdx = 0;
            float predVal = output_f[0];
            for (int k = 1; k < OUTPUT_DIM; k++)
                if (output_f[k] > predVal) { predVal = output_f[k]; predIdx = k; }
            for (int k = 0; k < OUTPUT_DIM; k++)
                if (samples[s].action[k] > 0.5f) { targetIdx = k; break; }
            if (predIdx == targetIdx) correct++;
        }
        fprintf(stderr, "Final accuracy: %.1f%% (%d/%d)\n",
                (float)correct / nSamples * 100.0f, correct, nSamples);

        free(weights); free(velocity); free(samples);
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

        float hidden[HIDDEN_DIM], output[OUTPUT_DIM];
        forward(weights, input, hidden, output);

        fprintf(stderr, "Output: ");
        for (int k = 0; k < OUTPUT_DIM; k++)
            fprintf(stderr, "%.4f ", output[k]);
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

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    fprintf(stderr, "Commands: train, infer, export\n");
    return 1;
}
