/*
 * wizard_engine_scene.c — Scene graph, objects, keyframes, motion
 */
#include "wizard_engine.h"

/* ============================================================
 * SCENE MANAGEMENT
 * ============================================================ */

void scene_init(Scene* scene) {
    if (!scene) return;
    memset(scene, 0, sizeof(Scene));
    scene->width = 512;
    scene->height = 512;
    scene->background.x = 0.1f;
    scene->background.y = 0.075f;
    scene->background.z = 0.18f; /* dark purple */
    scene->duration = 4.0f;
    scene->fps = 60.0f;
    scene->object_count = 0;
    scene->current_frame = 0;
}

void scene_set_name(Scene* scene, const char* name) {
    if (!scene || !name) return;
    strncpy(scene->name, name, sizeof(scene->name) - 1);
    scene->name[sizeof(scene->name) - 1] = '\0';
}

void scene_set_size(Scene* scene, int width, int height) {
    if (!scene) return;
    scene->width = width;
    scene->height = height;
}

void scene_set_background(Scene* scene, float r, float g, float b) {
    if (!scene) return;
    scene->background.x = clampf(r, 0, 1);
    scene->background.y = clampf(g, 0, 1);
    scene->background.z = clampf(b, 0, 1);
}

void scene_set_duration(Scene* scene, float seconds) {
    if (!scene) return;
    scene->duration = seconds;
}

WObject* scene_add_object(Scene* scene, const char* id, const char* type_str) {
    if (!scene || scene->object_count >= MAX_OBJECTS) return NULL;
    WObject* obj = &scene->objects[scene->object_count];
    memset(obj, 0, sizeof(WObject));

    strncpy(obj->id, id ? id : "", MAX_ID_LEN - 1);
    obj->type = parse_object_type(type_str);
    obj->position = vec2_make(scene->width / 2.0f, scene->height / 2.0f);
    obj->rotation = 0.0f;
    obj->scale = 1.0f;
    obj->opacity = 1.0f;
    strcpy(obj->color, "#1e5eff");
    strcpy(obj->stroke_color, "#ffffff");
    obj->stroke_width = 2.0f;
    obj->width = 64.0f;
    obj->height = 64.0f;
    obj->font_size = 16.0f;
    obj->keyframe_count = 0;
    obj->motion.type = MOTION_NONE;
    obj->motion.speed = 1.0f;
    obj->motion.amplitude = 10.0f;
    obj->motion.radius = 40.0f;
    obj->motion.phase = 0.0f;
    obj->motion.center = obj->position;
    obj->motion.seed = 42;
    obj->has_parent = 0;
    obj->parent_id[0] = '\0';
    obj->node_status = 0;

    /* Initialize particle emitter if type is emitter */
    if (obj->type == OBJ_PARTICLE_EMITTER) {
        emitter_init(&obj->emitter, PARTICLE_DUST, obj->position);
    }

    scene->object_count++;
    return obj;
}

WObject* scene_find_object(Scene* scene, const char* id) {
    if (!scene || !id) return NULL;
    for (int i = 0; i < scene->object_count; i++) {
        if (strcmp(scene->objects[i].id, id) == 0)
            return &scene->objects[i];
    }
    return NULL;
}

void scene_remove_object(Scene* scene, const char* id) {
    if (!scene || !id) return;
    for (int i = 0; i < scene->object_count; i++) {
        if (strcmp(scene->objects[i].id, id) == 0) {
            /* Shift remaining objects down */
            for (int j = i; j < scene->object_count - 1; j++) {
                scene->objects[j] = scene->objects[j + 1];
            }
            scene->object_count--;
            return;
        }
    }
}

/* ============================================================
 * KEYFRAMES
 * ============================================================ */

Keyframe keyframe_make(float time, Vec2 pos, float rot, float scale, float opacity, EaseType easing) {
    Keyframe kf;
    kf.time = clampf(time, 0, 1);
    kf.position = pos;
    kf.rotation = rot;
    kf.scale = scale;
    kf.opacity = clampf(opacity, 0, 1);
    kf.easing = easing;
    return kf;
}

void obj_add_keyframe(WObject* obj, Keyframe kf) {
    if (!obj || obj->keyframe_count >= MAX_KEYFRAMES) return;
    /* Insert sorted by time */
    int i = obj->keyframe_count;
    while (i > 0 && obj->keyframes[i - 1].time > kf.time) {
        obj->keyframes[i] = obj->keyframes[i - 1];
        i--;
    }
    obj->keyframes[i] = kf;
    obj->keyframe_count++;
}

void obj_clear_keyframes(WObject* obj) {
    if (!obj) return;
    obj->keyframe_count = 0;
}

/* ============================================================
 * MOTION
 * ============================================================ */

void obj_set_motion(WObject* obj, MotionType type, float speed, float amplitude, float radius, float phase) {
    if (!obj) return;
    obj->motion.type = type;
    obj->motion.speed = speed;
    obj->motion.amplitude = amplitude;
    obj->motion.radius = radius;
    obj->motion.phase = phase;
}

void obj_set_motion_center(WObject* obj, Vec2 center) {
    if (!obj) return;
    obj->motion.center = center;
}

void obj_set_motion_seed(WObject* obj, int seed) {
    if (!obj) return;
    obj->motion.seed = seed;
}

/* ============================================================
 * TYPE NAME CONVERSIONS
 * ============================================================ */

ObjectType parse_object_type(const char* str) {
    if (!str) return OBJ_GROUP;
    if (strcmp(str, "group") == 0) return OBJ_GROUP;
    if (strcmp(str, "hat") == 0) return OBJ_HAT;
    if (strcmp(str, "wand") == 0) return OBJ_WAND;
    if (strcmp(str, "star") == 0) return OBJ_STAR;
    if (strcmp(str, "coat") == 0) return OBJ_COAT;
    if (strcmp(str, "beard") == 0) return OBJ_BEARD;
    if (strcmp(str, "circle") == 0) return OBJ_CIRCLE;
    if (strcmp(str, "rect") == 0) return OBJ_RECT;
    if (strcmp(str, "path") == 0) return OBJ_PATH;
    if (strcmp(str, "text") == 0) return OBJ_TEXT;
    if (strcmp(str, "emitter") == 0 || strcmp(str, "particle_emitter") == 0) return OBJ_PARTICLE_EMITTER;
    if (strcmp(str, "glow_orb") == 0) return OBJ_GLOW_ORB;
    if (strcmp(str, "rune_circle") == 0) return OBJ_RUNE_CIRCLE;
    if (strcmp(str, "lightning") == 0) return OBJ_LIGHTNING;
    if (strcmp(str, "mcp_node") == 0) return OBJ_MCP_NODE;
    return OBJ_GROUP;
}

const char* object_type_name(ObjectType type) {
    switch (type) {
    case OBJ_GROUP:           return "group";
    case OBJ_HAT:             return "hat";
    case OBJ_WAND:            return "wand";
    case OBJ_STAR:            return "star";
    case OBJ_COAT:            return "coat";
    case OBJ_BEARD:           return "beard";
    case OBJ_CIRCLE:          return "circle";
    case OBJ_RECT:            return "rect";
    case OBJ_PATH:            return "path";
    case OBJ_TEXT:            return "text";
    case OBJ_PARTICLE_EMITTER:return "emitter";
    case OBJ_GLOW_ORB:        return "glow_orb";
    case OBJ_RUNE_CIRCLE:     return "rune_circle";
    case OBJ_LIGHTNING:       return "lightning";
    case OBJ_MCP_NODE:        return "mcp_node";
    default: return "unknown";
    }
}

const char* motion_type_name(MotionType type) {
    switch (type) {
    case MOTION_NONE:          return "none";
    case MOTION_ROTATE:        return "rotate";
    case MOTION_ORBIT:         return "orbit";
    case MOTION_PULSE:         return "pulse";
    case MOTION_FADE:          return "fade";
    case MOTION_NOISE_DRIFT:   return "noise_drift";
    case MOTION_FLOAT:         return "float";
    case MOTION_WAND_WAVE:     return "wand_wave";
    case MOTION_PARTICLE_EMIT: return "particle_emit";
    case MOTION_GLOW:          return "glow";
    default: return "none";
    }
}

const char* ease_type_name(EaseType type) {
    switch (type) {
    case EASE_LINEAR:        return "linear";
    case EASE_IN_QUAD:       return "in_quad";
    case EASE_OUT_QUAD:      return "out_quad";
    case EASE_IN_OUT_QUAD:   return "in_out_quad";
    case EASE_IN_CUBIC:      return "in_cubic";
    case EASE_OUT_CUBIC:     return "out_cubic";
    case EASE_IN_OUT_CUBIC:  return "in_out_cubic";
    case EASE_IN_ELASTIC:    return "in_elastic";
    case EASE_OUT_ELASTIC:   return "out_elastic";
    case EASE_IN_BOUNCE:     return "in_bounce";
    case EASE_OUT_BOUNCE:    return "out_bounce";
    case EASE_IN_BACK:       return "in_back";
    case EASE_OUT_BACK:      return "out_back";
    default: return "linear";
    }
}

EaseType parse_ease_type(const char* str) {
    if (!str) return EASE_LINEAR;
    if (strcmp(str, "linear") == 0) return EASE_LINEAR;
    if (strcmp(str, "in_quad") == 0) return EASE_IN_QUAD;
    if (strcmp(str, "out_quad") == 0) return EASE_OUT_QUAD;
    if (strcmp(str, "in_out_quad") == 0) return EASE_IN_OUT_QUAD;
    if (strcmp(str, "in_cubic") == 0) return EASE_IN_CUBIC;
    if (strcmp(str, "out_cubic") == 0) return EASE_OUT_CUBIC;
    if (strcmp(str, "in_out_cubic") == 0) return EASE_IN_OUT_CUBIC;
    if (strcmp(str, "in_elastic") == 0) return EASE_IN_ELASTIC;
    if (strcmp(str, "out_elastic") == 0) return EASE_OUT_ELASTIC;
    if (strcmp(str, "in_bounce") == 0) return EASE_IN_BOUNCE;
    if (strcmp(str, "out_bounce") == 0) return EASE_OUT_BOUNCE;
    if (strcmp(str, "in_back") == 0) return EASE_IN_BACK;
    if (strcmp(str, "out_back") == 0) return EASE_OUT_BACK;
    return EASE_LINEAR;
}

MotionType parse_motion_type(const char* str) {
    if (!str) return MOTION_NONE;
    if (strcmp(str, "rotate") == 0) return MOTION_ROTATE;
    if (strcmp(str, "orbit") == 0) return MOTION_ORBIT;
    if (strcmp(str, "pulse") == 0) return MOTION_PULSE;
    if (strcmp(str, "fade") == 0) return MOTION_FADE;
    if (strcmp(str, "noise_drift") == 0) return MOTION_NOISE_DRIFT;
    if (strcmp(str, "float") == 0) return MOTION_FLOAT;
    if (strcmp(str, "wand_wave") == 0) return MOTION_WAND_WAVE;
    if (strcmp(str, "particle_emit") == 0) return MOTION_PARTICLE_EMIT;
    if (strcmp(str, "glow") == 0) return MOTION_GLOW;
    return MOTION_NONE;
}

/* ============================================================
 * ANIMATION EVALUATION
 * ============================================================ */

Transform evaluate_keyframes(WObject* obj, float time) {
    Transform t;
    t.position = obj->position;
    t.rotation = obj->rotation;
    t.scale = obj->scale;
    t.opacity = obj->opacity;

    if (obj->keyframe_count == 0) return t;
    if (obj->keyframe_count == 1) {
        t.position = obj->keyframes[0].position;
        t.rotation = obj->keyframes[0].rotation;
        t.scale = obj->keyframes[0].scale;
        t.opacity = obj->keyframes[0].opacity;
        return t;
    }

    /* Clamp time to keyframe range */
    float minTime = obj->keyframes[0].time;
    float maxTime = obj->keyframes[obj->keyframe_count - 1].time;
    if (time <= minTime) {
        t.position = obj->keyframes[0].position;
        t.rotation = obj->keyframes[0].rotation;
        t.scale = obj->keyframes[0].scale;
        t.opacity = obj->keyframes[0].opacity;
        return t;
    }
    if (time >= maxTime) {
        int last = obj->keyframe_count - 1;
        t.position = obj->keyframes[last].position;
        t.rotation = obj->keyframes[last].rotation;
        t.scale = obj->keyframes[last].scale;
        t.opacity = obj->keyframes[last].opacity;
        return t;
    }

    /* Find surrounding keyframes */
    int i = 0;
    while (i < obj->keyframe_count - 1 && obj->keyframes[i + 1].time < time) i++;

    Keyframe* k0 = &obj->keyframes[i];
    Keyframe* k1 = &obj->keyframes[i + 1];

    float localT = (time - k0->time) / (k1->time - k0->time);
    float easedT = ease_apply(k0->easing, localT);

    t.position = vec2_lerp(k0->position, k1->position, easedT);
    t.rotation = lerpf(k0->rotation, k1->rotation, easedT);
    t.scale = lerpf(k0->scale, k1->scale, easedT);
    t.opacity = lerpf(k0->opacity, k1->opacity, easedT);

    return t;
}

Transform evaluate_motion(WObject* obj, float time, Transform base) {
    Transform t = base;
    float phase = time * obj->motion.speed + obj->motion.phase * TWO_PI;

    switch (obj->motion.type) {
    case MOTION_ROTATE:
        t.rotation = base.rotation + phase * 180.0f / PI;
        break;

    case MOTION_ORBIT: {
        float angle = phase;
        t.position.x = obj->motion.center.x + cosf(angle) * obj->motion.radius;
        t.position.y = obj->motion.center.y + sinf(angle) * obj->motion.radius;
        break;
    }

    case MOTION_PULSE: {
        float pulse = 1.0f + sinf(phase) * obj->motion.amplitude * 0.01f;
        t.scale = base.scale * pulse;
        break;
    }

    case MOTION_FADE: {
        t.opacity = base.opacity * (0.5f + 0.5f * sinf(phase));
        break;
    }

    case MOTION_NOISE_DRIFT: {
        float nx = perlin_noise2d(time * obj->motion.speed, 0, obj->motion.seed);
        float ny = perlin_noise2d(0, time * obj->motion.speed, obj->motion.seed + 100);
        t.position.x = base.position.x + (nx - 0.5f) * obj->motion.amplitude * 2;
        t.position.y = base.position.y + (ny - 0.5f) * obj->motion.amplitude * 2;
        break;
    }

    case MOTION_FLOAT: {
        t.position.y = base.position.y + sinf(phase) * obj->motion.amplitude;
        break;
    }

    case MOTION_WAND_WAVE: {
        t.rotation = base.rotation + sinf(phase) * obj->motion.amplitude;
        t.position.x = base.position.x + sinf(phase * 0.5f) * obj->motion.amplitude * 0.3f;
        break;
    }

    case MOTION_GLOW: {
        float glow = 0.5f + 0.5f * sinf(phase);
        t.opacity = base.opacity * (0.6f + 0.4f * glow);
        t.scale = base.scale * (0.95f + 0.1f * glow);
        break;
    }

    case MOTION_PARTICLE_EMIT:
        /* Particle emission is handled by the emitter, not the transform */
        break;

    case MOTION_NONE:
    default:
        break;
    }

    return t;
}

Transform evaluate_transform(WObject* obj, float time) {
    Transform base = evaluate_keyframes(obj, time);
    return evaluate_motion(obj, time, base);
}
