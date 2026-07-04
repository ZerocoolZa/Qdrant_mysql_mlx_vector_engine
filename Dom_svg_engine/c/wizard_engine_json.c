/*
 * wizard_engine_json.c — JSON scene DSL parser and serializer
 *
 * Parses a JSON scene definition into a Scene struct, and can
 * serialize a Scene back to JSON.
 *
 * JSON format:
 * {
 *   "name": "Wizard Idle",
 *   "width": 512,
 *   "height": 512,
 *   "background": [0.1, 0.075, 0.18],
 *   "duration": 4.0,
 *   "fps": 60,
 *   "objects": [
 *     {
 *       "id": "wizard_hat",
 *       "type": "hat",
 *       "position": [256, 180],
 *       "rotation": 0,
 *       "scale": 1.0,
 *       "opacity": 1.0,
 *       "color": "#2a1860",
 *       "stroke_color": "#ffd700",
 *       "stroke_width": 2,
 *       "motion": {
 *         "type": "float",
 *         "speed": 0.5,
 *         "amplitude": 8,
 *         "radius": 40,
 *         "phase": 0,
 *         "center": [256, 180],
 *         "seed": 42
 *       },
 *       "keyframes": [
 *         {"time": 0, "position": [256, 180], "rotation": 0, "scale": 1, "opacity": 1, "easing": "linear"},
 *         {"time": 1, "position": [256, 200], "rotation": 5, "scale": 1.1, "opacity": 0.8, "easing": "out_cubic"}
 *       ],
 *       "emitter": {
 *         "type": "dust",
 *         "rate": 20,
 *         "speed": 30,
 *         "speed_var": 15,
 *         "size": 3,
 *         "size_var": 1,
 *         "life": 2.0,
 *         "life_var": 0.5,
 *         "colors": [[0.8, 0.6, 1.0], [0.2, 0.1, 0.4]],
 *         "gravity": -20,
 *         "drag": 0.98,
 *         "area": [20, 20],
 *         "max": 200
 *       }
 *     }
 *   ]
 * }
 */
#include "wizard_engine.h"

/* ============================================================
 * MINIMAL JSON PARSER
 * ============================================================ */

typedef enum {
    JSON_NULL, JSON_BOOL, JSON_NUMBER, JSON_STRING, JSON_ARRAY, JSON_OBJECT
} JsonType;

typedef struct JsonValue {
    JsonType type;
    union {
        int boolean;
        double number;
        char string[256];
        struct {
            struct JsonValue* items;
            int count;
        } array;
        struct {
            char** keys;
            struct JsonValue* values;
            int count;
        } object;
    };
} JsonValue;

/* Simple recursive descent JSON parser */
typedef struct {
    const char* data;
    int pos;
    int len;
} JsonParser;

static void skip_ws(JsonParser* p) {
    while (p->pos < p->len) {
        char c = p->data[p->pos];
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r')
            p->pos++;
        else
            break;
    }
}

static JsonValue* parse_value(JsonParser* p);

static JsonValue* parse_string(JsonParser* p) {
    JsonValue* v = calloc(1, sizeof(JsonValue));
    v->type = JSON_STRING;
    p->pos++; /* skip opening quote */
    int start = p->pos;
    while (p->pos < p->len && p->data[p->pos] != '"') {
        if (p->data[p->pos] == '\\') p->pos++;
        p->pos++;
    }
    int slen = p->pos - start;
    if (slen >= 255) slen = 254;
    memcpy(v->string, p->data + start, slen);
    v->string[slen] = '\0';
    if (p->pos < p->len) p->pos++; /* skip closing quote */
    return v;
}

static JsonValue* parse_number(JsonParser* p) {
    JsonValue* v = calloc(1, sizeof(JsonValue));
    v->type = JSON_NUMBER;
    int start = p->pos;
    while (p->pos < p->len) {
        char c = p->data[p->pos];
        if ((c >= '0' && c <= '9') || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E')
            p->pos++;
        else
            break;
    }
    v->number = atof(p->data + start);
    return v;
}

static JsonValue* parse_array(JsonParser* p) {
    JsonValue* v = calloc(1, sizeof(JsonValue));
    v->type = JSON_ARRAY;
    v->array.items = calloc(64, sizeof(JsonValue));
    v->array.count = 0;
    p->pos++; /* skip [ */
    skip_ws(p);
    while (p->pos < p->len && p->data[p->pos] != ']') {
        if (v->array.count < 64) {
            v->array.items[v->array.count++] = *parse_value(p);
        } else {
            free(parse_value(p));
        }
        skip_ws(p);
        if (p->pos < p->len && p->data[p->pos] == ',') p->pos++;
        skip_ws(p);
    }
    if (p->pos < p->len) p->pos++; /* skip ] */
    return v;
}

static JsonValue* parse_object(JsonParser* p) {
    JsonValue* v = calloc(1, sizeof(JsonValue));
    v->type = JSON_OBJECT;
    v->object.keys = calloc(32, sizeof(char*));
    v->object.values = calloc(32, sizeof(JsonValue));
    v->object.count = 0;
    p->pos++; /* skip { */
    skip_ws(p);
    while (p->pos < p->len && p->data[p->pos] != '}') {
        skip_ws(p);
        /* Parse key */
        if (p->data[p->pos] != '"') break;
        JsonValue* key = parse_string(p);
        skip_ws(p);
        if (p->pos < p->len && p->data[p->pos] == ':') p->pos++;
        skip_ws(p);
        JsonValue* val = parse_value(p);
        if (v->object.count < 32) {
            v->object.keys[v->object.count] = strdup(key->string);
            v->object.values[v->object.count] = *val;
            v->object.count++;
        }
        free(key);
        free(val);
        skip_ws(p);
        if (p->pos < p->len && p->data[p->pos] == ',') p->pos++;
        skip_ws(p);
    }
    if (p->pos < p->len) p->pos++; /* skip } */
    return v;
}

static JsonValue* parse_value(JsonParser* p) {
    skip_ws(p);
    if (p->pos >= p->len) return calloc(1, sizeof(JsonValue));
    char c = p->data[p->pos];
    if (c == '"') return parse_string(p);
    if (c == '{') return parse_object(p);
    if (c == '[') return parse_array(p);
    if (c == 't' || c == 'f') {
        JsonValue* v = calloc(1, sizeof(JsonValue));
        v->type = JSON_BOOL;
        v->boolean = (c == 't');
        p->pos += (c == 't') ? 4 : 5;
        return v;
    }
    if (c == 'n') {
        p->pos += 4;
        return calloc(1, sizeof(JsonValue));
    }
    return parse_number(p);
}

static JsonValue* json_get(JsonValue* obj, const char* key) {
    if (!obj || obj->type != JSON_OBJECT) return NULL;
    for (int i = 0; i < obj->object.count; i++) {
        if (strcmp(obj->object.keys[i], key) == 0)
            return &obj->object.values[i];
    }
    return NULL;
}

static double json_num(JsonValue* v, double def) {
    if (!v || v->type != JSON_NUMBER) return def;
    return v->number;
}

static const char* json_str(JsonValue* v, const char* def) {
    if (!v || v->type != JSON_STRING) return def;
    return v->string;
}

static float json_arr_num(JsonValue* arr, int index, float def) {
    if (!arr || arr->type != JSON_ARRAY || index >= arr->array.count) return def;
    JsonValue* item = &arr->array.items[index];
    if (item->type != JSON_NUMBER) return def;
    return (float)item->number;
}

static void json_free(JsonValue* v) {
    if (!v) return;
    if (v->type == JSON_ARRAY) {
        for (int i = 0; i < v->array.count; i++)
            json_free(&v->array.items[i]);
        free(v->array.items);
    } else if (v->type == JSON_OBJECT) {
        for (int i = 0; i < v->object.count; i++) {
            free(v->object.keys[i]);
            json_free(&v->object.values[i]);
        }
        free(v->object.keys);
        free(v->object.values);
    }
}

/* ============================================================
 * SCENE JSON PARSER
 * ============================================================ */

static void parse_motion_json(WObject* obj, JsonValue* motionJson) {
    if (!motionJson || motionJson->type != JSON_OBJECT) return;
    const char* mtype = json_str(json_get(motionJson, "type"), "none");
    obj->motion.type = parse_motion_type(mtype);
    obj->motion.speed = (float)json_num(json_get(motionJson, "speed"), 1.0);
    obj->motion.amplitude = (float)json_num(json_get(motionJson, "amplitude"), 10.0);
    obj->motion.radius = (float)json_num(json_get(motionJson, "radius"), 40.0);
    obj->motion.phase = (float)json_num(json_get(motionJson, "phase"), 0.0);
    JsonValue* center = json_get(motionJson, "center");
    if (center) {
        obj->motion.center.x = json_arr_num(center, 0, obj->position.x);
        obj->motion.center.y = json_arr_num(center, 1, obj->position.y);
    }
    obj->motion.seed = (int)json_num(json_get(motionJson, "seed"), 42);
}

static void parse_keyframes_json(WObject* obj, JsonValue* kfJson) {
    if (!kfJson || kfJson->type != JSON_ARRAY) return;
    for (int i = 0; i < kfJson->array.count && i < MAX_KEYFRAMES; i++) {
        JsonValue* kf = &kfJson->array.items[i];
        if (kf->type != JSON_OBJECT) continue;
        Keyframe k;
        memset(&k, 0, sizeof(k));
        k.time = (float)json_num(json_get(kf, "time"), 0);
        JsonValue* pos = json_get(kf, "position");
        k.position = vec2_make(
            json_arr_num(pos, 0, obj->position.x),
            json_arr_num(pos, 1, obj->position.y)
        );
        k.rotation = (float)json_num(json_get(kf, "rotation"), 0);
        k.scale = (float)json_num(json_get(kf, "scale"), 1.0);
        k.opacity = (float)json_num(json_get(kf, "opacity"), 1.0);
        k.easing = parse_ease_type(json_str(json_get(kf, "easing"), "linear"));
        obj_add_keyframe(obj, k);
    }
}

static void parse_emitter_json(WObject* obj, JsonValue* emJson) {
    if (!emJson || emJson->type != JSON_OBJECT) return;
    ParticleEmitter* e = &obj->emitter;
    const char* ptype = json_str(json_get(emJson, "type"), "dust");
    if (strcmp(ptype, "dust") == 0) e->emit_type = PARTICLE_DUST;
    else if (strcmp(ptype, "star") == 0) e->emit_type = PARTICLE_STAR;
    else if (strcmp(ptype, "spark") == 0) e->emit_type = PARTICLE_SPARK;
    else if (strcmp(ptype, "rune") == 0) e->emit_type = PARTICLE_RUNE;
    else e->emit_type = PARTICLE_DUST;

    e->emit_rate = (float)json_num(json_get(emJson, "rate"), 20.0);
    e->emit_speed = (float)json_num(json_get(emJson, "speed"), 30.0);
    e->emit_speed_var = (float)json_num(json_get(emJson, "speed_var"), 15.0);
    e->particle_size = (float)json_num(json_get(emJson, "size"), 3.0);
    e->particle_size_var = (float)json_num(json_get(emJson, "size_var"), 1.0);
    e->particle_life = (float)json_num(json_get(emJson, "life"), 2.0);
    e->particle_life_var = (float)json_num(json_get(emJson, "life_var"), 0.5);
    e->gravity = (float)json_num(json_get(emJson, "gravity"), -20.0);
    e->drag = (float)json_num(json_get(emJson, "drag"), 0.98);
    e->max_particles = (int)json_num(json_get(emJson, "max"), 200);
    JsonValue* area = json_get(emJson, "area");
    if (area) {
        e->emit_area.x = json_arr_num(area, 0, 20);
        e->emit_area.y = json_arr_num(area, 1, 20);
    }
    JsonValue* colors = json_get(emJson, "colors");
    if (colors && colors->type == JSON_ARRAY && colors->array.count >= 2) {
        JsonValue* start = &colors->array.items[0];
        JsonValue* end = &colors->array.items[1];
        e->color_start.x = json_arr_num(start, 0, 0.8f);
        e->color_start.y = json_arr_num(start, 1, 0.6f);
        e->color_start.z = json_arr_num(start, 2, 1.0f);
        e->color_end.x = json_arr_num(end, 0, 0.2f);
        e->color_end.y = json_arr_num(end, 1, 0.1f);
        e->color_end.z = json_arr_num(end, 2, 0.4f);
    }
}

int parse_scene_json(const char* json, Scene* scene) {
    if (!json || !scene) return -1;

    JsonParser p = {json, 0, (int)strlen(json)};
    JsonValue* root = parse_value(&p);
    if (!root || root->type != JSON_OBJECT) {
        json_free(root);
        free(root);
        return -1;
    }

    scene_init(scene);

    scene_set_name(scene, json_str(json_get(root, "name"), "Untitled"));
    scene_set_size(scene, (int)json_num(json_get(root, "width"), 512),
                         (int)json_num(json_get(root, "height"), 512));
    JsonValue* bg = json_get(root, "background");
    if (bg && bg->type == JSON_ARRAY) {
        scene_set_background(scene,
            json_arr_num(bg, 0, 0.1f),
            json_arr_num(bg, 1, 0.075f),
            json_arr_num(bg, 2, 0.18f));
    }
    scene_set_duration(scene, (float)json_num(json_get(root, "duration"), 4.0));
    scene->fps = (float)json_num(json_get(root, "fps"), 60.0);

    JsonValue* objects = json_get(root, "objects");
    if (objects && objects->type == JSON_ARRAY) {
        for (int i = 0; i < objects->array.count && i < MAX_OBJECTS; i++) {
            JsonValue* objJson = &objects->array.items[i];
            if (objJson->type != JSON_OBJECT) continue;

            const char* id = json_str(json_get(objJson, "id"), "obj");
            const char* type = json_str(json_get(objJson, "type"), "group");
            WObject* obj = scene_add_object(scene, id, type);
            if (!obj) continue;

            JsonValue* pos = json_get(objJson, "position");
            if (pos) {
                obj->position.x = json_arr_num(pos, 0, scene->width / 2.0f);
                obj->position.y = json_arr_num(pos, 1, scene->height / 2.0f);
            }
            obj->rotation = (float)json_num(json_get(objJson, "rotation"), 0);
            obj->scale = (float)json_num(json_get(objJson, "scale"), 1.0);
            obj->opacity = (float)json_num(json_get(objJson, "opacity"), 1.0);
            strncpy(obj->color, json_str(json_get(objJson, "color"), "#1e5eff"), MAX_COLOR_LEN - 1);
            strncpy(obj->stroke_color, json_str(json_get(objJson, "stroke_color"), "#ffffff"), MAX_COLOR_LEN - 1);
            obj->stroke_width = (float)json_num(json_get(objJson, "stroke_width"), 2.0);
            obj->width = (float)json_num(json_get(objJson, "width"), 64.0);
            obj->height = (float)json_num(json_get(objJson, "height"), 64.0);
            obj->font_size = (float)json_num(json_get(objJson, "font_size"), 16.0);
            strncpy(obj->text, json_str(json_get(objJson, "text"), ""), sizeof(obj->text) - 1);

            /* MCP node fields */
            strncpy(obj->node_label, json_str(json_get(objJson, "node_label"), ""), sizeof(obj->node_label) - 1);
            obj->node_status = (int)json_num(json_get(objJson, "node_status"), 0);

            /* Parent */
            const char* parent = json_str(json_get(objJson, "parent"), "");
            if (parent[0]) {
                strncpy(obj->parent_id, parent, MAX_ID_LEN - 1);
                obj->has_parent = 1;
            }

            /* Motion */
            parse_motion_json(obj, json_get(objJson, "motion"));

            /* Keyframes */
            parse_keyframes_json(obj, json_get(objJson, "keyframes"));

            /* Emitter */
            if (obj->type == OBJ_PARTICLE_EMITTER) {
                parse_emitter_json(obj, json_get(objJson, "emitter"));
                obj->emitter.emit_position = obj->position;
            }
        }
    }

    json_free(root);
    free(root);
    return 0;
}

int load_scene_file(const char* filename, Scene* scene) {
    FILE* f = fopen(filename, "r");
    if (!f) return -1;

    char* buffer = malloc(MAX_JSON_LEN);
    int n = fread(buffer, 1, MAX_JSON_LEN - 1, f);
    buffer[n] = '\0';
    fclose(f);

    int result = parse_scene_json(buffer, scene);
    free(buffer);
    return result;
}

/* ============================================================
 * SCENE JSON SERIALIZER
 * ============================================================ */

int save_scene_json(Scene* scene, const char* filename) {
    FILE* f = fopen(filename, "w");
    if (!f) return -1;

    fprintf(f, "{\n");
    fprintf(f, "  \"name\": \"%s\",\n", scene->name);
    fprintf(f, "  \"width\": %d,\n", scene->width);
    fprintf(f, "  \"height\": %d,\n", scene->height);
    fprintf(f, "  \"background\": [%.3f, %.3f, %.3f],\n",
            scene->background.x, scene->background.y, scene->background.z);
    fprintf(f, "  \"duration\": %.2f,\n", scene->duration);
    fprintf(f, "  \"fps\": %.0f,\n", scene->fps);
    fprintf(f, "  \"objects\": [\n");

    for (int i = 0; i < scene->object_count; i++) {
        WObject* obj = &scene->objects[i];
        fprintf(f, "    {\n");
        fprintf(f, "      \"id\": \"%s\",\n", obj->id);
        fprintf(f, "      \"type\": \"%s\",\n", object_type_name(obj->type));
        fprintf(f, "      \"position\": [%.1f, %.1f],\n", obj->position.x, obj->position.y);
        fprintf(f, "      \"rotation\": %.1f,\n", obj->rotation);
        fprintf(f, "      \"scale\": %.3f,\n", obj->scale);
        fprintf(f, "      \"opacity\": %.3f,\n", obj->opacity);
        fprintf(f, "      \"color\": \"%s\",\n", obj->color);
        fprintf(f, "      \"stroke_color\": \"%s\",\n", obj->stroke_color);
        fprintf(f, "      \"stroke_width\": %.1f,\n", obj->stroke_width);

        if (obj->motion.type != MOTION_NONE) {
            fprintf(f, "      \"motion\": {\n");
            fprintf(f, "        \"type\": \"%s\",\n", motion_type_name(obj->motion.type));
            fprintf(f, "        \"speed\": %.2f,\n", obj->motion.speed);
            fprintf(f, "        \"amplitude\": %.1f,\n", obj->motion.amplitude);
            fprintf(f, "        \"radius\": %.1f,\n", obj->motion.radius);
            fprintf(f, "        \"phase\": %.3f,\n", obj->motion.phase);
            fprintf(f, "        \"center\": [%.1f, %.1f],\n", obj->motion.center.x, obj->motion.center.y);
            fprintf(f, "        \"seed\": %d\n", obj->motion.seed);
            fprintf(f, "      },\n");
        }

        if (obj->keyframe_count > 0) {
            fprintf(f, "      \"keyframes\": [\n");
            for (int j = 0; j < obj->keyframe_count; j++) {
                Keyframe* kf = &obj->keyframes[j];
                fprintf(f, "        {\"time\": %.3f, \"position\": [%.1f, %.1f], "
                           "\"rotation\": %.1f, \"scale\": %.3f, \"opacity\": %.3f, "
                           "\"easing\": \"%s\"}%s\n",
                        kf->time, kf->position.x, kf->position.y,
                        kf->rotation, kf->scale, kf->opacity,
                        ease_type_name(kf->easing),
                        (j < obj->keyframe_count - 1) ? "," : "");
            }
            fprintf(f, "      ],\n");
        }

        if (obj->type == OBJ_PARTICLE_EMITTER) {
            ParticleEmitter* e = &obj->emitter;
            const char* ptype = "dust";
            switch (e->emit_type) {
            case PARTICLE_STAR: ptype = "star"; break;
            case PARTICLE_SPARK: ptype = "spark"; break;
            case PARTICLE_RUNE: ptype = "rune"; break;
            default: break;
            }
            fprintf(f, "      \"emitter\": {\n");
            fprintf(f, "        \"type\": \"%s\",\n", ptype);
            fprintf(f, "        \"rate\": %.1f,\n", e->emit_rate);
            fprintf(f, "        \"speed\": %.1f,\n", e->emit_speed);
            fprintf(f, "        \"speed_var\": %.1f,\n", e->emit_speed_var);
            fprintf(f, "        \"size\": %.1f,\n", e->particle_size);
            fprintf(f, "        \"size_var\": %.1f,\n", e->particle_size_var);
            fprintf(f, "        \"life\": %.2f,\n", e->particle_life);
            fprintf(f, "        \"life_var\": %.2f,\n", e->particle_life_var);
            fprintf(f, "        \"gravity\": %.1f,\n", e->gravity);
            fprintf(f, "        \"drag\": %.3f,\n", e->drag);
            fprintf(f, "        \"max\": %d\n", e->max_particles);
            fprintf(f, "      },\n");
        }

        if (obj->type == OBJ_MCP_NODE) {
            fprintf(f, "      \"node_label\": \"%s\",\n", obj->node_label);
            fprintf(f, "      \"node_status\": %d,\n", obj->node_status);
        }

        fprintf(f, "      \"text\": \"%s\"\n", obj->text);
        fprintf(f, "    }%s\n", (i < scene->object_count - 1) ? "," : "");
    }

    fprintf(f, "  ]\n");
    fprintf(f, "}\n");

    fclose(f);
    return 0;
}
