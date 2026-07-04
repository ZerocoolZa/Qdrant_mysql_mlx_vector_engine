/*
 * wizard_engine.h — Procedural SVG Animation Engine
 *
 * A deterministic animation compiler that converts:
 *   Scene → Timeline → Motion Rules → SVG DOM
 *
 * Features:
 *   - Scene graph with typed objects
 *   - Keyframe animation with easing functions
 *   - Particle system (magic dust, stars, sparks)
 *   - Orbit physics + noise drift
 *   - JSON scene DSL parser
 *   - SVG export with SMIL animations
 *   - Wizard object library (hat, wand, stars, coat, beard, particles)
 *
 * Architecture:
 *   Python/Qt UI → Scene JSON → C Engine → SVG Output
 *
 * Author: Unified MCP Setup Wizard
 * License: MIT
 */
#ifndef WIZARD_ENGINE_H
#define WIZARD_ENGINE_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ============================================================
 * CONSTANTS
 * ============================================================ */

#define MAX_OBJECTS     256
#define MAX_KEYFRAMES   32
#define MAX_PARTICLES   512
#define MAX_CHILDREN    16
#define MAX_ID_LEN      64
#define MAX_TYPE_LEN    32
#define MAX_COLOR_LEN   16
#define MAX_PATH_LEN    512
#define MAX_SVG_LEN     1048576   /* 1MB max SVG output */
#define MAX_JSON_LEN    1048576
#define PI              3.14159265358979323846f
#define TWO_PI          6.28318530717958647692f

/* ============================================================
 * VECTOR TYPES
 * ============================================================ */

typedef struct { float x, y; } Vec2;
typedef struct { float x, y, z; } Vec3;

Vec2  vec2_make(float x, float y);
Vec3  vec3_make(float x, float y, float z);
Vec2  vec2_add(Vec2 a, Vec2 b);
Vec2  vec2_sub(Vec2 a, Vec2 b);
Vec2  vec2_scale(Vec2 a, float s);
float vec2_dot(Vec2 a, Vec2 b);
float vec2_len(Vec2 a);
Vec2  vec2_normalize(Vec2 a);
Vec2  vec2_lerp(Vec2 a, Vec2 b, float t);

/* ============================================================
 * EASING FUNCTIONS
 * ============================================================ */

typedef enum {
    EASE_LINEAR = 0,
    EASE_IN_QUAD,
    EASE_OUT_QUAD,
    EASE_IN_OUT_QUAD,
    EASE_IN_CUBIC,
    EASE_OUT_CUBIC,
    EASE_IN_OUT_CUBIC,
    EASE_IN_ELASTIC,
    EASE_OUT_ELASTIC,
    EASE_IN_BOUNCE,
    EASE_OUT_BOUNCE,
    EASE_IN_BACK,
    EASE_OUT_BACK,
} EaseType;

float ease_apply(EaseType type, float t);

/* ============================================================
 * MOTION TYPES
 * ============================================================ */

typedef enum {
    MOTION_NONE = 0,
    MOTION_ROTATE,       /* continuous rotation */
    MOTION_ORBIT,        /* circular orbit around center */
    MOTION_PULSE,        /* scale pulsing */
    MOTION_FADE,         /* opacity oscillation */
    MOTION_NOISE_DRIFT,  /* perlin-like drift */
    MOTION_FLOAT,        /* gentle up/down bobbing */
    MOTION_WAND_WAVE,    /* wand-specific wave motion */
    MOTION_PARTICLE_EMIT,/* particle emission */
    MOTION_GLOW,         /* color/glow pulsing */
} MotionType;

typedef struct {
    MotionType type;
    float speed;       /* cycles per second */
    float amplitude;   /* how far / how much */
    float radius;      /* orbit radius */
    float phase;       /* phase offset 0-1 */
    Vec2  center;      /* orbit/noise center */
    int   seed;        /* for deterministic noise */
} Motion;

/* ============================================================
 * KEYFRAME ANIMATION
 * ============================================================ */

typedef struct {
    float   time;       /* 0.0 - 1.0 on timeline */
    Vec2    position;
    float   rotation;   /* degrees */
    float   scale;
    float   opacity;    /* 0.0 - 1.0 */
    EaseType easing;    /* easing to next keyframe */
} Keyframe;

/* ============================================================
 * PARTICLE SYSTEM
 * ============================================================ */

typedef enum {
    PARTICLE_DUST = 0,
    PARTICLE_STAR,
    PARTICLE_SPARK,
    PARTICLE_RUNE,
} ParticleType;

typedef struct {
    Vec2    position;
    Vec2    velocity;
    Vec2    acceleration;
    float   life;        /* 0.0 - 1.0, 1 = just born */
    float   max_life;    /* total lifetime in seconds */
    float   size;
    float   rotation;
    float   angular_vel;
    Vec3    color;       /* RGB 0-1 */
    float   opacity;
    ParticleType type;
    int     active;
} Particle;

typedef struct {
    ParticleType  emit_type;
    Vec2          emit_position;
    Vec2          emit_area;       /* spread area */
    float         emit_rate;       /* particles per second */
    float         emit_speed;      /* initial speed */
    float         emit_speed_var;  /* speed variance */
    float         particle_size;
    float         particle_size_var;
    float         particle_life;
    float         particle_life_var;
    Vec3          color_start;
    Vec3          color_end;
    float         gravity;         /* downward acceleration */
    float         drag;            /* air resistance 0-1 */
    int           max_particles;
    int           seed;
    /* Internal state */
    Particle      particles[MAX_PARTICLES];
    int           particle_count;
    float         emit_accumulator;
    int           rng_state;
} ParticleEmitter;

/* ============================================================
 * SCENE OBJECT
 * ============================================================ */

typedef enum {
    OBJ_GROUP = 0,
    OBJ_HAT,
    OBJ_WAND,
    OBJ_STAR,
    OBJ_COAT,
    OBJ_BEARD,
    OBJ_CIRCLE,
    OBJ_RECT,
    OBJ_PATH,
    OBJ_TEXT,
    OBJ_PARTICLE_EMITTER,
    OBJ_GLOW_ORB,
    OBJ_RUNE_CIRCLE,
    OBJ_LIGHTNING,
    OBJ_MCP_NODE,
} ObjectType;

typedef struct {
    char        id[MAX_ID_LEN];
    ObjectType  type;
    Vec2        position;
    float       rotation;
    float       scale;
    float       opacity;
    char        color[MAX_COLOR_LEN];
    char        stroke_color[MAX_COLOR_LEN];
    float       stroke_width;
    float       width;        /* for rect, text */
    float       height;       /* for rect */
    char        text[128];    /* for text objects */
    float       font_size;    /* for text */

    /* Animation */
    int         keyframe_count;
    Keyframe    keyframes[MAX_KEYFRAMES];
    Motion      motion;

    /* Particles */
    ParticleEmitter emitter;

    /* Hierarchy */
    char        parent_id[MAX_ID_LEN];
    int         has_parent;

    /* MCP node specific */
    char        node_label[64];
    int         node_status;  /* 0=unknown, 1=ok, 2=warn, 3=error */
} WObject;

/* ============================================================
 * SCENE
 * ============================================================ */

typedef struct {
    char        name[128];
    int         width;
    int         height;
    Vec3        background;     /* RGB 0-1 */
    float       duration;       /* animation duration in seconds */
    float       fps;
    int         object_count;
    WObject     objects[MAX_OBJECTS];
    int         current_frame;
} Scene;

/* ============================================================
 * ENGINE API — Scene Management
 * ============================================================ */

void    scene_init(Scene* scene);
void    scene_set_name(Scene* scene, const char* name);
void    scene_set_size(Scene* scene, int width, int height);
void    scene_set_background(Scene* scene, float r, float g, float b);
void    scene_set_duration(Scene* scene, float seconds);
WObject* scene_add_object(Scene* scene, const char* id, const char* type_str);
WObject* scene_find_object(Scene* scene, const char* id);
void    scene_remove_object(Scene* scene, const char* id);

/* ============================================================
 * ENGINE API — Keyframes
 * ============================================================ */

void    obj_add_keyframe(WObject* obj, Keyframe kf);
void    obj_clear_keyframes(WObject* obj);
Keyframe keyframe_make(float time, Vec2 pos, float rot, float scale, float opacity, EaseType easing);

/* ============================================================
 * ENGINE API — Motion
 * ============================================================ */

void    obj_set_motion(WObject* obj, MotionType type, float speed, float amplitude, float radius, float phase);
void    obj_set_motion_center(WObject* obj, Vec2 center);
void    obj_set_motion_seed(WObject* obj, int seed);

/* ============================================================
 * ENGINE API — Particles
 * ============================================================ */

void    emitter_init(ParticleEmitter* e, ParticleType type, Vec2 pos);
void    emitter_set_rate(ParticleEmitter* e, float rate);
void    emitter_set_speed(ParticleEmitter* e, float speed, float variance);
void    emitter_set_size(ParticleEmitter* e, float size, float variance);
void    emitter_set_life(ParticleEmitter* e, float life, float variance);
void    emitter_set_colors(ParticleEmitter* e, Vec3 start, Vec3 end);
void    emitter_set_gravity(ParticleEmitter* e, float gravity);
void    emitter_set_drag(ParticleEmitter* e, float drag);
void    emitter_set_area(ParticleEmitter* e, Vec2 area);
void    emitter_set_max(ParticleEmitter* e, int max);
void    emitter_update(ParticleEmitter* e, float dt);

/* ============================================================
 * ENGINE API — SVG Export
 * ============================================================ */

int     export_svg(Scene* scene, const char* filename);
int     export_svg_to_string(Scene* scene, char* output, int max_len);
int     export_svg_frame(Scene* scene, int frame, const char* filename);

/* ============================================================
 * ENGINE API — JSON Scene Parser
 * ============================================================ */

int     parse_scene_json(const char* json, Scene* scene);
int     load_scene_file(const char* filename, Scene* scene);
int     save_scene_json(Scene* scene, const char* filename);

/* ============================================================
 * ENGINE API — Object Type Helpers
 * ============================================================ */

ObjectType  parse_object_type(const char* str);
const char* object_type_name(ObjectType type);
const char* motion_type_name(MotionType type);
const char* ease_type_name(EaseType type);
EaseType    parse_ease_type(const char* str);
MotionType  parse_motion_type(const char* str);

/* ============================================================
 * ENGINE API — Animation Evaluation
 * ============================================================ */

typedef struct {
    Vec2    position;
    float   rotation;
    float   scale;
    float   opacity;
} Transform;

Transform   evaluate_transform(WObject* obj, float time);
Transform   evaluate_keyframes(WObject* obj, float time);
Transform   evaluate_motion(WObject* obj, float time, Transform base);

/* ============================================================
 * UTILITIES
 * ============================================================ */

float   clampf(float v, float min, float max);
float   lerpf(float a, float b, float t);
float   deg2rad(float deg);
float   rad2deg(float rad);
void    rgb_to_hex(Vec3 rgb, char* out);
Vec3    hex_to_rgb(const char* hex);
float   perlin_noise2d(float x, float y, int seed);
float   frandom(int* state);
void    srandom_seed(int* state, int seed);

#endif /* WIZARD_ENGINE_H */
