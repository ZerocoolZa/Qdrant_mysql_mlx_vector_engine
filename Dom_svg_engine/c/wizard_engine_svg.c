/*
 * wizard_engine_svg.c — SVG export with SMIL animations
 *
 * Renders the scene graph to SVG, including:
 *   - All wizard object types (hat, wand, star, coat, beard, etc.)
 *   - Keyframe animations via SMIL <animate> and <animateTransform>
 *   - Motion-driven animations (orbit, pulse, rotate, float, etc.)
 *   - Particle systems as animated SVG elements
 *   - Gradients, filters (glow), clipping
 */
#include "wizard_engine.h"

/* Forward declarations */
static void write_object_svg(WObject* obj, Scene* scene, FILE* f, float time);
static void write_particles_svg(ParticleEmitter* e, FILE* f);
static void write_hat_svg(WObject* obj, FILE* f, Transform t);
static void write_wand_svg(WObject* obj, FILE* f, Transform t);
static void write_star_svg(WObject* obj, FILE* f, Transform t);
static void write_coat_svg(WObject* obj, FILE* f, Transform t);
static void write_beard_svg(WObject* obj, FILE* f, Transform t);
static void write_circle_svg(WObject* obj, FILE* f, Transform t);
static void write_rect_svg(WObject* obj, FILE* f, Transform t);
static void write_text_svg(WObject* obj, FILE* f, Transform t);
static void write_glow_orb_svg(WObject* obj, FILE* f, Transform t);
static void write_rune_circle_svg(WObject* obj, FILE* f, Transform t);
static void write_lightning_svg(WObject* obj, FILE* f, Transform t);
static void write_mcp_node_svg(WObject* obj, FILE* f, Transform t);
static void write_motion_animations(WObject* obj, FILE* f, float duration);
static void write_keyframe_animations(WObject* obj, FILE* f, float duration);
static void write_defs(Scene* scene, FILE* f);

/* ============================================================
 * MAIN SVG EXPORT
 * ============================================================ */

int export_svg(Scene* scene, const char* filename) {
    FILE* f = fopen(filename, "w");
    if (!f) return -1;

    /* Update particles for one frame */
    float dt = 1.0f / scene->fps;
    for (int i = 0; i < scene->object_count; i++) {
        if (scene->objects[i].type == OBJ_PARTICLE_EMITTER) {
            /* Simulate a few frames to populate */
            for (int j = 0; j < 30; j++) {
                emitter_update(&scene->objects[i].emitter, dt);
            }
        }
    }

    char bgHex[MAX_COLOR_LEN];
    rgb_to_hex(scene->background, bgHex);

    fprintf(f, "<?xml version='1.0' encoding='UTF-8'?>\n");
    fprintf(f, "<svg width='%d' height='%d' viewBox='0 0 %d %d' "
               "xmlns='http://www.w3.org/2000/svg' "
               "xmlns:xlink='http://www.w3.org/1999/xlink'>\n",
            scene->width, scene->height, scene->width, scene->height);

    /* Defs: gradients, filters */
    write_defs(scene, f);

    /* Background */
    fprintf(f, "<rect width='100%%' height='100%%' fill='%s'/>\n", bgHex);

    /* Objects */
    float time = 0;
    for (int i = 0; i < scene->object_count; i++) {
        write_object_svg(&scene->objects[i], scene, f, time);
    }

    fprintf(f, "</svg>\n");
    fclose(f);
    return 0;
}

int export_svg_to_string(Scene* scene, char* output, int max_len) {
    if (!scene || !output || max_len <= 0) return -1;

    /* Use a temp file and read it back */
    const char* tmp = "/tmp/wizard_engine_output.svg";
    if (export_svg(scene, tmp) != 0) return -1;

    FILE* f = fopen(tmp, "r");
    if (!f) return -1;

    int n = fread(output, 1, max_len - 1, f);
    output[n] = '\0';
    fclose(f);
    return n;
}

int export_svg_frame(Scene* scene, int frame, const char* filename) {
    scene->current_frame = frame;
    return export_svg(scene, filename);
}

/* ============================================================
 * DEFS — gradients, filters
 * ============================================================ */

static void write_defs(Scene* scene, FILE* f) {
    fprintf(f, "<defs>\n");

    /* Glow filter */
    fprintf(f,
        "  <filter id='glow' x='-50%%' y='-50%%' width='200%%' height='200%%'>\n"
        "    <feGaussianBlur stdDeviation='4' result='blur'/>\n"
        "    <feMerge>\n"
        "      <feMergeNode in='blur'/>\n"
        "      <feMergeNode in='SourceGraphic'/>\n"
        "    </feMerge>\n"
        "  </filter>\n");

    /* Strong glow filter */
    fprintf(f,
        "  <filter id='glow-strong' x='-50%%' y='-50%%' width='200%%' height='200%%'>\n"
        "    <feGaussianBlur stdDeviation='8' result='blur'/>\n"
        "    <feMerge>\n"
        "      <feMergeNode in='blur'/>\n"
        "      <feMergeNode in='blur'/>\n"
        "      <feMergeNode in='SourceGraphic'/>\n"
        "    </feMerge>\n"
        "  </filter>\n");

    /* Magic gradient (purple to blue) */
    fprintf(f,
        "  <radialGradient id='magic-gradient' cx='50%%' cy='50%%' r='50%%'>\n"
        "    <stop offset='0%%' stop-color='#7b2ff7' stop-opacity='0.8'/>\n"
        "    <stop offset='100%%' stop-color='#1a365d' stop-opacity='0'/>\n"
        "  </radialGradient>\n");

    /* Star gradient */
    fprintf(f,
        "  <radialGradient id='star-gradient' cx='50%%' cy='50%%' r='50%%'>\n"
        "    <stop offset='0%%' stop-color='#ffffff' stop-opacity='1'/>\n"
        "    <stop offset='50%%' stop-color='#7ec8ff' stop-opacity='0.6'/>\n"
        "    <stop offset='100%%' stop-color='#1e5eff' stop-opacity='0'/>\n"
        "  </radialGradient>\n");

    /* Hat gradient */
    fprintf(f,
        "  <linearGradient id='hat-gradient' x1='0%%' y1='0%%' x2='0%%' y2='100%%'>\n"
        "    <stop offset='0%%' stop-color='#2a1860'/>\n"
        "    <stop offset='100%%' stop-color='#1a0a40'/>\n"
        "  </linearGradient>\n");

    /* Wand gradient */
    fprintf(f,
        "  <linearGradient id='wand-gradient' x1='0%%' y1='0%%' x2='0%%' y2='100%%'>\n"
        "    <stop offset='0%%' stop-color='#ffd700'/>\n"
        "    <stop offset='100%%' stop-color='#b8860b'/>\n"
        "  </linearGradient>\n");

    /* Coat gradient */
    fprintf(f,
        "  <linearGradient id='coat-gradient' x1='0%%' y1='0%%' x2='0%%' y2='100%%'>\n"
        "    <stop offset='0%%' stop-color='#1e5eff'/>\n"
        "    <stop offset='100%%' stop-color='#0a2060'/>\n"
        "  </linearGradient>\n");

    /* Rune gradient */
    fprintf(f,
        "  <radialGradient id='rune-gradient' cx='50%%' cy='50%%' r='50%%'>\n"
        "    <stop offset='0%%' stop-color='#00ffff' stop-opacity='0.8'/>\n"
        "    <stop offset='100%%' stop-color='#0088ff' stop-opacity='0'/>\n"
        "  </radialGradient>\n");

    fprintf(f, "</defs>\n");
}

/* ============================================================
 * OBJECT SVG WRITERS
 * ============================================================ */

static void write_object_svg(WObject* obj, Scene* scene, FILE* f, float time) {
    Transform t = evaluate_transform(obj, time);

    /* Apply opacity */
    if (t.opacity < 1.0f) {
        fprintf(f, "<g opacity='%.3f'>\n", t.opacity);
    }

    /* Write the object based on its type */
    switch (obj->type) {
    case OBJ_HAT:             write_hat_svg(obj, f, t); break;
    case OBJ_WAND:            write_wand_svg(obj, f, t); break;
    case OBJ_STAR:            write_star_svg(obj, f, t); break;
    case OBJ_COAT:            write_coat_svg(obj, f, t); break;
    case OBJ_BEARD:           write_beard_svg(obj, f, t); break;
    case OBJ_CIRCLE:          write_circle_svg(obj, f, t); break;
    case OBJ_RECT:            write_rect_svg(obj, f, t); break;
    case OBJ_TEXT:            write_text_svg(obj, f, t); break;
    case OBJ_GLOW_ORB:        write_glow_orb_svg(obj, f, t); break;
    case OBJ_RUNE_CIRCLE:     write_rune_circle_svg(obj, f, t); break;
    case OBJ_LIGHTNING:       write_lightning_svg(obj, f, t); break;
    case OBJ_MCP_NODE:        write_mcp_node_svg(obj, f, t); break;
    case OBJ_PARTICLE_EMITTER:
        /* Update emitter and render particles */
        emitter_update(&obj->emitter, 1.0f / scene->fps);
        write_particles_svg(&obj->emitter, f);
        break;
    case OBJ_GROUP:
    case OBJ_PATH:
    default:
        /* Generic group — just render children (no visual) */
        break;
    }

    /* Write SMIL animations for motion */
    if (obj->motion.type != MOTION_NONE) {
        write_motion_animations(obj, f, scene->duration);
    }

    /* Write keyframe animations */
    if (obj->keyframe_count > 0) {
        write_keyframe_animations(obj, f, scene->duration);
    }

    if (t.opacity < 1.0f) {
        fprintf(f, "</g>\n");
    }
}

/* ============================================================
 * WIZARD OBJECT: HAT
 * ============================================================ */

static void write_hat_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Hat cone */
    fprintf(f, "  <path d='M0,-80 L-50,30 L50,30 Z' fill='url(#hat-gradient)' "
               "stroke='%s' stroke-width='%.1f'/>\n",
            obj->stroke_color, obj->stroke_width);

    /* Hat brim */
    fprintf(f, "  <ellipse cx='0' cy='32' rx='65' ry='12' fill='#1a0a40' "
               "stroke='%s' stroke-width='%.1f'/>\n",
            obj->stroke_color, obj->stroke_width);

    /* Star on hat */
    fprintf(f, "  <path d='M0,-50 L4,-40 L14,-38 L6,-30 L8,-20 L0,-25 L-8,-20 "
               "L-6,-30 L-14,-38 L-4,-40 Z' fill='#ffd700' filter='url(#glow)'/>\n");

    /* Hat band */
    fprintf(f, "  <rect x='-48' y='22' width='96' height='8' rx='2' fill='#ffd700' opacity='0.8'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * WIZARD OBJECT: WAND
 * ============================================================ */

static void write_wand_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Wand stick */
    fprintf(f, "  <line x1='0' y1='0' x2='0' y2='80' stroke='url(#wand-gradient)' "
               "stroke-width='6' stroke-linecap='round'/>\n");

    /* Wand tip glow */
    fprintf(f, "  <circle cx='0' cy='-5' r='12' fill='url(#star-gradient)' filter='url(#glow-strong)'/>\n");

    /* Wand tip star */
    fprintf(f, "  <path d='M0,-15 L3,-6 L12,-4 L5,3 L7,12 L0,7 L-7,12 L-5,3 "
               "L-12,-4 L-3,-6 Z' fill='#ffffff' filter='url(#glow)'/>\n");

    /* Sparkles around tip */
    fprintf(f, "  <circle cx='10' cy='-12' r='1.5' fill='#7ec8ff' opacity='0.8'/>\n");
    fprintf(f, "  <circle cx='-8' cy='-8' r='1' fill='#ffd700' opacity='0.6'/>\n");
    fprintf(f, "  <circle cx='14' cy='-2' r='1.2' fill='#ffffff' opacity='0.7'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * WIZARD OBJECT: STAR
 * ============================================================ */

static void write_star_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* 5-pointed star */
    float r1 = 12.0f;  /* outer radius */
    float r2 = 5.0f;   /* inner radius */
    fprintf(f, "  <path d='");
    for (int i = 0; i < 10; i++) {
        float angle = (i * PI / 5.0f) - PI / 2.0f;
        float r = (i % 2 == 0) ? r1 : r2;
        float x = cosf(angle) * r;
        float y = sinf(angle) * r;
        if (i == 0)
            fprintf(f, "M%.1f,%.1f ", x, y);
        else
            fprintf(f, "L%.1f,%.1f ", x, y);
    }
    fprintf(f, "Z' fill='%s' filter='url(#glow)'/>\n", obj->color);

    fprintf(f, "</g>\n");
}

/* ============================================================
 * WIZARD OBJECT: COAT
 * ============================================================ */

static void write_coat_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Coat body — flowing robe shape */
    fprintf(f, "  <path d='M-40,-20 Q-50,40 -60,80 L-45,85 Q-35,50 -25,10 L-15,85 "
               "Q-5,50 0,10 L5,50 L15,85 Q25,50 25,10 L35,85 Q45,50 45,85 "
               "L60,80 Q50,40 40,-20 Z' fill='url(#coat-gradient)' "
               "stroke='%s' stroke-width='%.1f'/>\n",
            obj->stroke_color, obj->stroke_width);

    /* Collar */
    fprintf(f, "  <path d='M-30,-20 L0,-5 L30,-20 L25,-10 L0,5 L-25,-10 Z' "
               "fill='#ffd700' opacity='0.7'/>\n");

    /* Buttons */
    fprintf(f, "  <circle cx='0' cy='10' r='3' fill='#ffd700'/>\n");
    fprintf(f, "  <circle cx='0' cy='30' r='3' fill='#ffd700'/>\n");
    fprintf(f, "  <circle cx='0' cy='50' r='3' fill='#ffd700'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * WIZARD OBJECT: BEARD
 * ============================================================ */

static void write_beard_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Beard — flowing triangular shape with wavy bottom */
    fprintf(f, "  <path d='M-25,0 Q-30,30 -20,60 Q-15,70 -10,55 Q-5,75 0,60 "
               "Q5,75 10,55 Q15,70 20,60 Q30,30 25,0 Q15,-5 0,-5 Q-15,-5 -25,0 Z' "
               "fill='%s' opacity='0.95'/>\n", obj->color);

    /* Mustache */
    fprintf(f, "  <path d='M-18,-2 Q-10,-8 0,-3 Q10,-8 18,-2 Q10,2 0,-1 Q-10,2 -18,-2 Z' "
               "fill='%s'/>\n", obj->color);

    fprintf(f, "</g>\n");
}

/* ============================================================
 * BASIC SHAPES
 * ============================================================ */

static void write_circle_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<circle cx='%.1f' cy='%.1f' r='%.1f' fill='%s' "
               "stroke='%s' stroke-width='%.1f' opacity='%.3f'/>\n",
            t.position.x, t.position.y, obj->width / 2.0f * t.scale,
            obj->color, obj->stroke_color, obj->stroke_width, t.opacity);
}

static void write_rect_svg(WObject* obj, FILE* f, Transform t) {
    float w = obj->width * t.scale;
    float h = obj->height * t.scale;
    fprintf(f, "<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' "
               "rx='4' fill='%s' stroke='%s' stroke-width='%.1f' opacity='%.3f' "
               "transform='rotate(%.1f %.1f %.1f)'/>\n",
            t.position.x - w/2, t.position.y - h/2, w, h,
            obj->color, obj->stroke_color, obj->stroke_width, t.opacity,
            t.rotation, t.position.x, t.position.y);
}

static void write_text_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<text x='%.1f' y='%.1f' font-size='%.1f' fill='%s' "
               "text-anchor='middle' opacity='%.3f' "
               "transform='rotate(%.1f %.1f %.1f)'>%s</text>\n",
            t.position.x, t.position.y, obj->font_size * t.scale,
            obj->color, t.opacity,
            t.rotation, t.position.x, t.position.y, obj->text);
}

/* ============================================================
 * GLOW ORB
 * ============================================================ */

static void write_glow_orb_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.scale);

    /* Outer glow */
    fprintf(f, "  <circle cx='0' cy='0' r='30' fill='url(#magic-gradient)' "
               "filter='url(#glow-strong)'/>\n");

    /* Inner orb */
    fprintf(f, "  <circle cx='0' cy='0' r='15' fill='%s' opacity='0.7' "
               "filter='url(#glow)'/>\n", obj->color);

    /* Bright center */
    fprintf(f, "  <circle cx='0' cy='0' r='5' fill='#ffffff' opacity='0.9'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * RUNE CIRCLE
 * ============================================================ */

static void write_rune_circle_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Outer ring */
    fprintf(f, "  <circle cx='0' cy='0' r='40' fill='none' stroke='%s' "
               "stroke-width='2' opacity='0.6' filter='url(#glow)'/>\n", obj->color);

    /* Inner ring */
    fprintf(f, "  <circle cx='0' cy='0' r='32' fill='none' stroke='%s' "
               "stroke-width='1' opacity='0.4' stroke-dasharray='4,4'/>\n", obj->color);

    /* Rune marks around the circle */
    for (int i = 0; i < 8; i++) {
        float angle = (i * TWO_PI / 8.0f);
        float x1 = cosf(angle) * 36;
        float y1 = sinf(angle) * 36;
        float x2 = cosf(angle) * 44;
        float y2 = sinf(angle) * 44;
        fprintf(f, "  <line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' "
                   "stroke='%s' stroke-width='2' opacity='0.7'/>\n",
                x1, y1, x2, y2, obj->color);
    }

    /* Center glow */
    fprintf(f, "  <circle cx='0' cy='0' r='20' fill='url(#rune-gradient)'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * LIGHTNING
 * ============================================================ */

static void write_lightning_svg(WObject* obj, FILE* f, Transform t) {
    fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f) scale(%.3f)' "
               "filter='url(#glow)'>\n",
            t.position.x, t.position.y, t.rotation, t.scale);

    /* Lightning bolt — zigzag path */
    fprintf(f, "  <path d='M0,-40 L-8,-10 L4,-10 L-4,20 L10,15 L0,40 L-6,15 L4,10 L-8,-5 L0,-40 Z' "
               "fill='%s' opacity='0.9'/>\n", obj->color);

    /* Electric arcs */
    fprintf(f, "  <path d='M0,-35 Q5,-25 -3,-15 Q3,-5 -5,5 Q2,15 -2,25' "
               "fill='none' stroke='#ffffff' stroke-width='1' opacity='0.6'/>\n");

    fprintf(f, "</g>\n");
}

/* ============================================================
 * MCP NODE
 * ============================================================ */

static void write_mcp_node_svg(WObject* obj, FILE* f, Transform t) {
    const char* statusColor = "#888888";
    const char* statusGlow = "glow";
    switch (obj->node_status) {
    case 1: statusColor = "#00ff88"; statusGlow = "glow"; break;
    case 2: statusColor = "#ffaa00"; statusGlow = "glow"; break;
    case 3: statusColor = "#ff4444"; statusGlow = "glow-strong"; break;
    }

    fprintf(f, "<g transform='translate(%.1f,%.1f) scale(%.3f)'>\n",
            t.position.x, t.position.y, t.scale);

    /* Node background circle */
    fprintf(f, "  <circle cx='0' cy='0' r='30' fill='%s' opacity='0.2' "
               "filter='url(#%s)'/>\n", statusColor, statusGlow);

    /* Node border */
    fprintf(f, "  <circle cx='0' cy='0' r='25' fill='none' stroke='%s' "
               "stroke-width='2' opacity='0.8'/>\n", statusColor);

    /* Status dot */
    fprintf(f, "  <circle cx='18' cy='-18' r='5' fill='%s' filter='url(#glow)'/>\n",
            statusColor);

    /* Label */
    if (obj->node_label[0]) {
        fprintf(f, "  <text x='0' y='5' font-size='10' fill='#ffffff' "
                   "text-anchor='middle' font-family='monospace'>%s</text>\n",
                obj->node_label);
        fprintf(f, "  <text x='0' y='45' font-size='9' fill='%s' "
                   "text-anchor='middle' font-family='monospace' opacity='0.7'>%s</text>\n",
                statusColor, obj->id);
    }

    fprintf(f, "</g>\n");
}

/* ============================================================
 * PARTICLES
 * ============================================================ */

static void write_particles_svg(ParticleEmitter* e, FILE* f) {
    for (int i = 0; i < e->particle_count; i++) {
        Particle* p = &e->particles[i];
        if (!p->active) continue;

        char colorHex[MAX_COLOR_LEN];
        rgb_to_hex(p->color, colorHex);

        switch (p->type) {
        case PARTICLE_DUST:
            fprintf(f, "<circle cx='%.1f' cy='%.1f' r='%.1f' fill='%s' "
                       "opacity='%.3f' filter='url(#glow)'/>\n",
                    p->position.x, p->position.y, p->size, colorHex, p->opacity);
            break;

        case PARTICLE_STAR:
            fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f)'>\n",
                    p->position.x, p->position.y, p->rotation);
            fprintf(f, "  <path d='M0,%-.1f L%.1f,%-.1f L%.1f,0 L%.1f,%.1f L0,%.1f "
                       "L-%.1f,%.1f L-%.1f,0 L-%.1f,%-.1f Z' fill='%s' opacity='%.3f'/>\n",
                    -p->size, p->size*0.3f, -p->size*0.3f, p->size, p->size*0.3f, p->size,
                    p->size, p->size*0.3f, -p->size, p->size*0.3f, -p->size*0.3f,
                    colorHex, p->opacity);
            fprintf(f, "</g>\n");
            break;

        case PARTICLE_SPARK:
            fprintf(f, "<line x1='%.1f' y1='%.1f' x2='%.1f' y2='%.1f' "
                       "stroke='%s' stroke-width='%.1f' opacity='%.3f'/>\n",
                    p->position.x, p->position.y,
                    p->position.x - p->velocity.x * 0.05f,
                    p->position.y - p->velocity.y * 0.05f,
                    colorHex, p->size * 0.5f, p->opacity);
            break;

        case PARTICLE_RUNE:
            fprintf(f, "<g transform='translate(%.1f,%.1f) rotate(%.1f)' opacity='%.3f'>\n",
                    p->position.x, p->position.y, p->rotation, p->opacity);
            fprintf(f, "  <circle cx='0' cy='0' r='%.1f' fill='none' stroke='%s' "
                       "stroke-width='1'/>\n", p->size, colorHex);
            fprintf(f, "  <line x1='-%.1f' y1='0' x1='%.1f' y2='0' stroke='%s' "
                       "stroke-width='0.5'/>\n", p->size, p->size, colorHex);
            fprintf(f, "</g>\n");
            break;
        }
    }
}

/* ============================================================
 * SMIL ANIMATIONS
 * ============================================================ */

static void write_motion_animations(WObject* obj, FILE* f, float duration) {
    float dur = duration > 0 ? duration : 4.0f;
    char durStr[32];
    snprintf(durStr, sizeof(durStr), "%.1fs", dur);

    switch (obj->motion.type) {
    case MOTION_ROTATE:
        fprintf(f, "<animateTransform attributeName='transform' type='rotate' "
                   "from='0' to='360' dur='%s' repeatCount='indefinite'/>\n", durStr);
        break;

    case MOTION_PULSE:
        fprintf(f, "<animateTransform attributeName='transform' type='scale' "
                   "values='1;1.1;1' dur='%s' repeatCount='indefinite'/>\n", durStr);
        break;

    case MOTION_FADE:
        fprintf(f, "<animate attributeName='opacity' values='1;0.3;1' "
                   "dur='%s' repeatCount='indefinite'/>\n", durStr);
        break;

    case MOTION_GLOW:
        fprintf(f, "<animate attributeName='opacity' values='0.6;1;0.6' "
                   "dur='%s' repeatCount='indefinite'/>\n", durStr);
        fprintf(f, "<animateTransform attributeName='transform' type='scale' "
                   "values='0.95;1.05;0.95' dur='%s' repeatCount='indefinite'/>\n", durStr);
        break;

    case MOTION_FLOAT:
        fprintf(f, "<animateTransform attributeName='transform' type='translate' "
                   "values='0,0;0,-%.1f;0,0' dur='%s' repeatCount='indefinite'/>\n",
                obj->motion.amplitude, durStr);
        break;

    case MOTION_ORBIT:
        /* Orbit is complex — we use animateMotion with a path */
        fprintf(f, "<animateMotion dur='%s' repeatCount='indefinite' "
                   "path='M %.1f,0 A %.1f,%.1f 0 1,1 %.1f,0 A %.1f,%.1f 0 1,1 %.1f,0'/>\n",
                durStr,
                obj->motion.radius, obj->motion.radius, obj->motion.radius,
                -obj->motion.radius, obj->motion.radius, obj->motion.radius,
                obj->motion.radius);
        break;

    default:
        break;
    }
}

static void write_keyframe_animations(WObject* obj, FILE* f, float duration) {
    if (obj->keyframe_count < 2) return;

    float dur = duration > 0 ? duration : 4.0f;
    char durStr[32];
    snprintf(durStr, sizeof(durStr), "%.1fs", dur);

    /* Build values strings for position, rotation, scale, opacity */
    char xValues[2048] = "";
    char yValues[2048] = "";
    char rotValues[2048] = "";
    char scaleValues[2048] = "";
    char opacityValues[2048] = "";
    char keyTimes[1024] = "";

    for (int i = 0; i < obj->keyframe_count; i++) {
        Keyframe* kf = &obj->keyframes[i];
        char xStr[32], yStr[32], rStr[32], sStr[32], oStr[32], tStr[32];

        snprintf(xStr, sizeof(xStr), "%.1f", kf->position.x);
        snprintf(yStr, sizeof(yStr), "%.1f", kf->position.y);
        snprintf(rStr, sizeof(rStr), "%.1f", kf->rotation);
        snprintf(sStr, sizeof(sStr), "%.3f", kf->scale);
        snprintf(oStr, sizeof(oStr), "%.3f", kf->opacity);
        snprintf(tStr, sizeof(tStr), "%.3f", kf->time);

        if (i > 0) {
            strncat(xValues, ";", sizeof(xValues) - strlen(xValues) - 1);
            strncat(yValues, ";", sizeof(yValues) - strlen(yValues) - 1);
            strncat(rotValues, ";", sizeof(rotValues) - strlen(rotValues) - 1);
            strncat(scaleValues, ";", sizeof(scaleValues) - strlen(scaleValues) - 1);
            strncat(opacityValues, ";", sizeof(opacityValues) - strlen(opacityValues) - 1);
            strncat(keyTimes, ";", sizeof(keyTimes) - strlen(keyTimes) - 1);
        }
        strncat(xValues, xStr, sizeof(xValues) - strlen(xValues) - 1);
        strncat(yValues, yStr, sizeof(yValues) - strlen(yValues) - 1);
        strncat(rotValues, rStr, sizeof(rotValues) - strlen(rotValues) - 1);
        strncat(scaleValues, sStr, sizeof(scaleValues) - strlen(scaleValues) - 1);
        strncat(opacityValues, oStr, sizeof(opacityValues) - strlen(opacityValues) - 1);
        strncat(keyTimes, tStr, sizeof(keyTimes) - strlen(keyTimes) - 1);
    }

    /* Position animation */
    fprintf(f, "<animateTransform attributeName='transform' type='translate' "
               "values='%s' keyTimes='%s' dur='%s' repeatCount='indefinite'/>\n",
            xValues, keyTimes, durStr);

    /* Rotation animation */
    fprintf(f, "<animateTransform attributeName='transform' type='rotate' "
               "values='%s' keyTimes='%s' dur='%s' repeatCount='indefinite' "
               "additive='sum'/>\n",
            rotValues, keyTimes, durStr);

    /* Scale animation */
    fprintf(f, "<animateTransform attributeName='transform' type='scale' "
               "values='%s' keyTimes='%s' dur='%s' repeatCount='indefinite' "
               "additive='sum'/>\n",
            scaleValues, keyTimes, durStr);

    /* Opacity animation */
    fprintf(f, "<animate attributeName='opacity' values='%s' keyTimes='%s' "
               "dur='%s' repeatCount='indefinite'/>\n",
            opacityValues, keyTimes, durStr);
}
