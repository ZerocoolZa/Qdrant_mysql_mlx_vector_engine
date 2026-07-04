/*
 * wizard_engine_core.c — Core math, vectors, easing, utilities
 */
#include "wizard_engine.h"

/* ============================================================
 * VECTOR OPERATIONS
 * ============================================================ */

Vec2 vec2_make(float x, float y) {
    Vec2 v = {x, y};
    return v;
}

Vec3 vec3_make(float x, float y, float z) {
    Vec3 v = {x, y, z};
    return v;
}

Vec2 vec2_add(Vec2 a, Vec2 b) {
    return vec2_make(a.x + b.x, a.y + b.y);
}

Vec2 vec2_sub(Vec2 a, Vec2 b) {
    return vec2_make(a.x - b.x, a.y - b.y);
}

Vec2 vec2_scale(Vec2 a, float s) {
    return vec2_make(a.x * s, a.y * s);
}

float vec2_dot(Vec2 a, Vec2 b) {
    return a.x * b.x + a.y * b.y;
}

float vec2_len(Vec2 a) {
    return sqrtf(a.x * a.x + a.y * a.y);
}

Vec2 vec2_normalize(Vec2 a) {
    float len = vec2_len(a);
    if (len < 0.0001f) return vec2_make(0, 0);
    return vec2_make(a.x / len, a.y / len);
}

Vec2 vec2_lerp(Vec2 a, Vec2 b, float t) {
    return vec2_make(lerpf(a.x, b.x, t), lerpf(a.y, b.y, t));
}

/* ============================================================
 * EASING FUNCTIONS
 * ============================================================ */

float ease_apply(EaseType type, float t) {
    if (t <= 0.0f) return 0.0f;
    if (t >= 1.0f) return 1.0f;

    switch (type) {
    case EASE_LINEAR:
        return t;

    case EASE_IN_QUAD:
        return t * t;

    case EASE_OUT_QUAD:
        return t * (2.0f - t);

    case EASE_IN_OUT_QUAD:
        return t < 0.5f ? 2.0f * t * t : -1.0f + (4.0f - 2.0f * t) * t;

    case EASE_IN_CUBIC:
        return t * t * t;

    case EASE_OUT_CUBIC: {
        float f = t - 1.0f;
        return f * f * f + 1.0f;
    }

    case EASE_IN_OUT_CUBIC:
        return t < 0.5f ? 4.0f * t * t * t
                        : (t - 1.0f) * (2.0f * (t - 1.0f)) * (2.0f * (t - 1.0f)) + 1.0f;

    case EASE_IN_ELASTIC: {
        if (t == 0.0f || t == 1.0f) return t;
        float p = 0.3f;
        float s = p / 4.0f;
        return -(powf(2.0f, 10.0f * (t - 1.0f)) * sinf((t - 1.0f - s) * TWO_PI / p));
    }

    case EASE_OUT_ELASTIC: {
        if (t == 0.0f || t == 1.0f) return t;
        float p = 0.3f;
        float s = p / 4.0f;
        return powf(2.0f, -10.0f * t) * sinf((t - s) * TWO_PI / p) + 1.0f;
    }

    case EASE_IN_BOUNCE:
        return 1.0f - ease_apply(EASE_OUT_BOUNCE, 1.0f - t);

    case EASE_OUT_BOUNCE: {
        if (t < 4.0f / 11.0f)
            return (121.0f / 16.0f) * t * t;
        else if (t < 8.0f / 11.0f)
            return (121.0f / 16.0f) * (t - 6.0f / 11.0f) * (t - 6.0f / 11.0f) + 0.75f;
        else if (t < 10.0f / 11.0f)
            return (121.0f / 16.0f) * (t - 9.0f / 11.0f) * (t - 9.0f / 11.0f) + 0.9375f;
        else
            return (121.0f / 16.0f) * (t - 10.5f / 11.0f) * (t - 10.5f / 11.0f) + 0.984375f;
    }

    case EASE_IN_BACK: {
        float s = 1.70158f;
        return t * t * ((s + 1.0f) * t - s);
    }

    case EASE_OUT_BACK: {
        float s = 1.70158f;
        t = t - 1.0f;
        return t * t * ((s + 1.0f) * t + s) + 1.0f;
    }

    default:
        return t;
    }
}

/* ============================================================
 * UTILITIES
 * ============================================================ */

float clampf(float v, float min, float max) {
    if (v < min) return min;
    if (v > max) return max;
    return v;
}

float lerpf(float a, float b, float t) {
    return a + (b - a) * t;
}

float deg2rad(float deg) {
    return deg * PI / 180.0f;
}

float rad2deg(float rad) {
    return rad * 180.0f / PI;
}

void rgb_to_hex(Vec3 rgb, char* out) {
    int r = (int)(clampf(rgb.x, 0, 1) * 255);
    int g = (int)(clampf(rgb.y, 0, 1) * 255);
    int b = (int)(clampf(rgb.z, 0, 1) * 255);
    snprintf(out, MAX_COLOR_LEN, "#%02x%02x%02x", r, g, b);
}

Vec3 hex_to_rgb(const char* hex) {
    Vec3 rgb = {0, 0, 0};
    if (!hex || hex[0] != '#' || strlen(hex) < 7)
        return rgb;
    unsigned int r, g, b;
    if (sscanf(hex + 1, "%02x%02x%02x", &r, &g, &b) == 3) {
        rgb.x = r / 255.0f;
        rgb.y = g / 255.0f;
        rgb.z = b / 255.0f;
    }
    return rgb;
}

/* Simple deterministic PRNG (xorshift32) */
float frandom(int* state) {
    if (*state == 0) *state = 1;
    *state ^= *state << 13;
    *state ^= *state >> 17;
    *state ^= *state << 5;
    return (*state & 0x00FFFFFF) / (float)0x01000000;
}

void srandom_seed(int* state, int seed) {
    *state = seed;
    if (*state == 0) *state = 1;
}

/* Simple Perlin-like noise (value noise with smooth interpolation) */
static float smoothstep(float t) {
    return t * t * (3.0f - 2.0f * t);
}

static float value_noise(int x, int y, int seed) {
    int n = x * 374761393 + y * 668265263 + seed * 982451653;
    n = (n >> 13) ^ n;
    n = n * (n * n * 60493 + 19990303) + 1376312589;
    return (n & 0x7FFFFFFF) / (float)0x7FFFFFFF;
}

float perlin_noise2d(float x, float y, int seed) {
    int xi = (int)floorf(x);
    int yi = (int)floorf(y);
    float xf = x - xi;
    float yf = y - yi;

    float v00 = value_noise(xi, yi, seed);
    float v10 = value_noise(xi + 1, yi, seed);
    float v01 = value_noise(xi, yi + 1, seed);
    float v11 = value_noise(xi + 1, yi + 1, seed);

    float sx = smoothstep(xf);
    float sy = smoothstep(yf);

    float n0 = lerpf(v00, v10, sx);
    float n1 = lerpf(v01, v11, sx);
    return lerpf(n0, n1, sy);
}
