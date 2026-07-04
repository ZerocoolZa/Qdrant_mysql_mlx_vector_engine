// wizard_engine.c
// MAXED PROCEDURAL SVG ANIMATION ENGINE — C SINGLE FILE
// Compile: gcc -shared -o libwizard.dylib -fPIC wizard_engine.c
//   OR:    gcc -o wizard_engine wizard_engine.c

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#define MAX_OBJECTS 128
#define MAX_KEYS 16
#define MAX_PARTICLES 256
#define SVG_BUF_SIZE 65536

// =========================
// VECTOR
// =========================
typedef struct { float x; float y; } Vec2;

// =========================
// KEYFRAME
// =========================
typedef struct {
    float t;
    Vec2 pos;
    float rot;
    float scale;
    float opacity;
} Keyframe;

// =========================
// OBJECT
// =========================
typedef struct {
    char id[32];
    char type[32];
    Vec2 pos;
    float rot;
    float scale;
    float opacity;
    char color[16];
    Keyframe keys[MAX_KEYS];
    int key_count;
} Object;

// =========================
// PARTICLE
// =========================
typedef struct {
    Vec2 pos;
    Vec2 vel;
    float life;
    float max_life;
    char color[16];
} Particle;

// =========================
// SCENE
// =========================
typedef struct {
    int w;
    int h;
    Object objects[MAX_OBJECTS];
    int obj_count;
    Particle particles[MAX_PARTICLES];
    int particle_count;
    unsigned int seed;
    char bg_color[16];
} Scene;

// =========================
// RNG
// =========================
static float frand(Scene* s) {
    s->seed = s->seed * 1103515245 + 12345;
    return (float)((s->seed >> 16) & 0x7FFF) / 32767.0f;
}

// =========================
// INIT
// =========================
void scene_init(Scene* s, int w, int h) {
    s->w = w;
    s->h = h;
    s->obj_count = 0;
    s->particle_count = 0;
    s->seed = (unsigned int)time(NULL);
    strcpy(s->bg_color, "#0b1020");
}

// =========================
// ADD OBJECT
// =========================
Object* add_object(Scene* s, const char* id, const char* type) {
    if (s->obj_count >= MAX_OBJECTS) return NULL;
    Object* o = &s->objects[s->obj_count++];
    strcpy(o->id, id);
    strcpy(o->type, type);
    o->pos = (Vec2){ s->w/2.0f, s->h/2.0f };
    o->rot = 0;
    o->scale = 1;
    o->opacity = 1;
    strcpy(o->color, "#1e5eff");
    o->key_count = 0;
    return o;
}

// =========================
// KEYFRAME ADD
// =========================
void add_key(Object* o, float t, Vec2 p, float r, float sc, float op) {
    if (o->key_count >= MAX_KEYS) return;
    Keyframe* k = &o->keys[o->key_count++];
    k->t = t;
    k->pos = p;
    k->rot = r;
    k->scale = sc;
    k->opacity = op;
}

// =========================
// EASING
// =========================
static float lerp(float a, float b, float t) {
    return a + (b - a) * t;
}

static float ease_in_out(float t) {
    return t * t * (3.0f - 2.0f * t);
}

// =========================
// SAMPLE KEYFRAMES
// =========================
static void sample(Object* o, float t, Vec2* out_p, float* out_r, float* out_s, float* out_op) {
    if (o->key_count == 0) {
        *out_p = o->pos;
        *out_r = o->rot;
        *out_s = o->scale;
        *out_op = o->opacity;
        return;
    }
    Keyframe* a = &o->keys[0];
    Keyframe* b = &o->keys[o->key_count - 1];
    for (int i = 0; i < o->key_count - 1; i++) {
        if (t >= o->keys[i].t && t <= o->keys[i+1].t) {
            a = &o->keys[i];
            b = &o->keys[i+1];
            break;
        }
    }
    float span = (b->t - a->t);
    float lt = span == 0 ? 0 : ease_in_out((t - a->t) / span);
    out_p->x = lerp(a->pos.x, b->pos.x, lt);
    out_p->y = lerp(a->pos.y, b->pos.y, lt);
    *out_r = lerp(a->rot, b->rot, lt);
    *out_s = lerp(a->scale, b->scale, lt);
    *out_op = lerp(a->opacity, b->opacity, lt);
}

// =========================
// PARTICLES
// =========================
void spawn_particle(Scene* s, Vec2 p, const char* color) {
    if (s->particle_count >= MAX_PARTICLES) return;
    Particle* pt = &s->particles[s->particle_count++];
    pt->pos = p;
    pt->vel = (Vec2){ (frand(s)-0.5f)*3, (frand(s)-0.5f)*3 - 1.0f };
    pt->life = 1.0f;
    pt->max_life = 1.0f;
    strcpy(pt->color, color);
}

void update_particles(Scene* s, float dt) {
    for (int i = 0; i < s->particle_count; i++) {
        Particle* p = &s->particles[i];
        p->pos.x += p->vel.x;
        p->pos.y += p->vel.y;
        p->vel.y += 0.05f; // gravity
        p->life -= dt;
        if (p->life <= 0) {
            *p = s->particles[--s->particle_count];
            i--;
        }
    }
}

// =========================
// STAR POLYGON HELPER
// =========================
static void star_poly(FILE* f, float cx, float cy, float size) {
    fprintf(f, "polygon points=\"");
    for (int i = 0; i < 10; i++) {
        float angle = i * 3.14159265f / 5.0f - 3.14159265f / 2.0f;
        float r = (i % 2 == 0) ? size : size * 0.4f;
        if (i > 0) fprintf(f, " ");
        fprintf(f, "%.1f,%.1f", cx + r * cosf(angle), cy + r * sinf(angle));
    }
    fprintf(f, "\"");
}

// =========================
// OBJECT RENDER
// =========================
static void render_object(FILE* f, Object* o, float t) {
    Vec2 p;
    float r, sc, op;
    sample(o, t, &p, &r, &sc, &op);

    if (strcmp(o->type, "wizard_hat") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f) scale(%.2f)' opacity='%.2f'>"
            "<path d='M0 -80 L-60 40 L60 40 Z' fill='%s'/>"
            "<rect x='-65' y='40' width='130' height='20' fill='%s' rx='3'/>"
            "<polygon points=\"0,-50 4,-40 14,-39 6,-32 9,-22 0,-28 -9,-22 -6,-32 -14,-39 -4,-40\" fill='#FFD700' opacity='0.9'/>"
            "</g>\n",
            p.x, p.y, r, sc, op, o->color, o->color
        );
    }
    else if (strcmp(o->type, "wide_hat") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f) scale(%.2f)' opacity='%.2f'>"
            "<path d='M0 -75 L-50 30 L50 30 Z' fill='%s'/>"
            "<ellipse cx='0' cy='32' rx='70' ry='12' fill='%s'/>"
            "<polygon points=\"0,-40 4,-30 12,-29 5,-22 8,-13 0,-18 -8,-13 -5,-22 -12,-29 -4,-30\" fill='#FFD700' opacity='0.8'/>"
            "</g>\n",
            p.x, p.y, r, sc, op, o->color, o->color
        );
    }
    else if (strcmp(o->type, "crown_hat") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f) scale(%.2f)' opacity='%.2f'>"
            "<path d='M0 -70 L-55 30 L55 30 Z' fill='%s'/>"
            "<rect x='-60' y='30' width='120' height='20' fill='%s' rx='3'/>"
            "<polygon points='-35,30 -25,5 -15,30' fill='#FFD700' opacity='0.8'/>"
            "<polygon points='-10,30 0,0 10,30' fill='#FFD700' opacity='0.8'/>"
            "<polygon points='15,30 25,5 35,30' fill='#FFD700' opacity='0.8'/>"
            "<circle cx='0' cy='10' r='3' fill='#FFD700'/>"
            "</g>\n",
            p.x, p.y, r, sc, op, o->color, o->color
        );
    }
    else if (strcmp(o->type, "wand") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f)' opacity='%.2f'>"
            "<line x1='0' y1='0' x2='80' y2='-40' stroke='#caa472' stroke-width='5' stroke-linecap='round'/>"
            "<circle cx='80' cy='-40' r='10' fill='%s' opacity='0.9'/>"
            "<circle cx='80' cy='-40' r='6' fill='#FFFFFF' opacity='0.5'/>"
            "</g>\n",
            p.x, p.y, r, op, o->color
        );
    }
    else if (strcmp(o->type, "fire_wand") == 0) {
        float pulse = 10.0f + sinf(t * 6.28f) * 3.0f;
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f)' opacity='%.2f'>"
            "<line x1='0' y1='0' x2='80' y2='-40' stroke='#4a2a1a' stroke-width='6' stroke-linecap='round'/>"
            "<circle cx='80' cy='-40' r='%.1f' fill='#FF4500' opacity='0.8'/>"
            "<circle cx='80' cy='-40' r='7' fill='#FFD700' opacity='0.9'/>"
            "<circle cx='78' cy='-42' r='3' fill='#FFFFFF' opacity='0.7'/>"
            "<path d='M80 -40 Q75 -55 80 -70' fill='none' stroke='#FF4500' stroke-width='2' opacity='0.5'/>"
            "</g>\n",
            p.x, p.y, r, op, pulse
        );
    }
    else if (strcmp(o->type, "crystal_staff") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f)' opacity='%.2f'>"
            "<line x1='0' y1='0' x2='80' y2='-10' stroke='#5a4a3a' stroke-width='7' stroke-linecap='round'/>"
            "<line x1='0' y1='0' x2='80' y2='-10' stroke='#8a7a6a' stroke-width='3' stroke-linecap='round'/>"
            "<polygon points='80,-30 92,-15 80,5 68,-15' fill='%s' opacity='0.8' stroke='%s' stroke-width='1'/>"
            "<polygon points='80,-25 87,-15 80,-5 73,-15' fill='#FFFFFF' opacity='0.3'/>"
            "</g>\n",
            p.x, p.y, r, op, o->color, o->color
        );
    }
    else if (strcmp(o->type, "lightning_wand") == 0) {
        float flash = 0.4f + fabsf(sinf(t * 8.0f)) * 0.6f;
        fprintf(f,
            "<g transform='translate(%.2f %.2f) rotate(%.2f)' opacity='%.2f'>"
            "<line x1='0' y1='0' x2='80' y2='-40' stroke='#4a4a6a' stroke-width='5' stroke-linecap='round'/>"
            "<polygon points='80,-55 88,-45 83,-45 90,-30 80,-40 85,-40 77,-32' fill='%s' stroke='#FFFFFF' stroke-width='1' opacity='%.1f'/>"
            "<circle cx='80' cy='-40' r='8' fill='%s' opacity='0.3'/>"
            "</g>\n",
            p.x, p.y, r, op, o->color, flash, o->color
        );
    }
    else if (strcmp(o->type, "star") == 0) {
        float twinkle = 0.3f + fabsf(sinf(t * 3.14f + p.x * 0.1f)) * 0.7f;
        fprintf(f,
            "<circle cx='%.2f' cy='%.2f' r='2' fill='%s' opacity='%.2f'/>",
            p.x, p.y, o->color, twinkle * op
        );
    }
    else if (strcmp(o->type, "big_star") == 0) {
        float pulse = sc + sinf(t * 3.14f) * 0.2f;
        fprintf(f, "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>",
            p.x, p.y, pulse, op);
        fprintf(f, "<");
        star_poly(f, 0, 0, 8);
        fprintf(f, " fill='%s'/></g>\n", o->color);
    }
    else if (strcmp(o->type, "coat") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>"
            "<path d='M-50 30 L-90 160 L90 160 L50 30 Z' fill='%s'/>"
            "<path d='M-20 30 L-30 160' stroke='#4a4a4a' stroke-width='2' opacity='0.5'/>"
            "<path d='M20 30 L30 160' stroke='#4a4a4a' stroke-width='2' opacity='0.5'/>"
            "<path d='M-90 160 Q0 155 90 160' fill='none' stroke='%s' stroke-width='2' opacity='0.6'/>"
            "<circle cx='0' cy='80' r='10' fill='none' stroke='%s' stroke-width='1.5' opacity='0.4'/>"
            "</g>\n",
            p.x, p.y, sc, op, o->color, o->color, o->color
        );
    }
    else if (strcmp(o->type, "face") == 0) {
        float blink = (fmodf(t * 0.5f, 1.0f) > 0.97f) ? 0.1f : 1.0f;
        fprintf(f,
            "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>"
            "<ellipse cx='0' cy='0' rx='28' ry='32' fill='#F4D4A0' stroke='#D4A060' stroke-width='1.5'/>"
            "<ellipse cx='-22' cy='2' rx='5' ry='9' fill='#F4D4A0' stroke='#D4A060' stroke-width='1'/>"
            "<ellipse cx='22' cy='2' rx='5' ry='9' fill='#F4D4A0' stroke='#D4A060' stroke-width='1'/>"
            "<ellipse cx='-9' cy='-8' rx='3.5' ry='%.1f' fill='#1a1a2e'/>"
            "<ellipse cx='9' cy='-8' rx='3.5' ry='%.1f' fill='#1a1a2e'/>"
            "<circle cx='-8' cy='-9' r='1.5' fill='%s'/>"
            "<circle cx='10' cy='-9' r='1.5' fill='%s'/>"
            "<path d='M-14 -14 Q-9 -16 -4 -13' fill='none' stroke='#8a6a3a' stroke-width='2'/>"
            "<path d='M4 -13 Q9 -16 14 -14' fill='none' stroke='#8a6a3a' stroke-width='2'/>"
            "<path d='M0 -2 L-3 6 Q0 8 3 6 Z' fill='#E4C490'/>"
            "<path d='M-10 12 Q0 18 10 12' fill='none' stroke='#8a5a2a' stroke-width='2' stroke-linecap='round'/>"
            "</g>\n",
            p.x, p.y, sc, op,
            5.0f * blink, 5.0f * blink,
            o->color, o->color
        );
    }
    else if (strcmp(o->type, "beard") == 0) {
        fprintf(f,
            "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>"
            "<path d='M-24 8 Q-30 40 -22 60 Q-14 50 -8 58 Q0 45 8 58 Q14 50 22 60 Q30 40 24 8 Q12 14 0 12 Q-12 14 -24 8 Z' fill='#EEEEEE' stroke='#CCCCCC' stroke-width='1'/>"
            "<path d='M-12 8 Q-18 12 -20 16 Q-12 13 -6 10' fill='#EEEEEE' stroke='#CCCCCC' stroke-width='0.5'/>"
            "<path d='M12 8 Q18 12 20 16 Q12 13 6 10' fill='#EEEEEE' stroke='#CCCCCC' stroke-width='0.5'/>"
            "</g>\n",
            p.x, p.y, sc, op
        );
    }
    else if (strcmp(o->type, "glow") == 0) {
        float pulse = 50.0f + sinf(t * 1.57f) * 10.0f;
        fprintf(f,
            "<circle cx='%.2f' cy='%.2f' r='%.1f' fill='%s' opacity='0.1'/>"
            "<circle cx='%.2f' cy='%.2f' r='30' fill='%s' opacity='0.06'/>",
            p.x, p.y, pulse, o->color, p.x, p.y, o->color
        );
    }
    else if (strcmp(o->type, "rune") == 0) {
        float op2 = op * (0.15f + fabsf(sinf(t * 0.5f + p.x * 0.05f)) * 0.25f);
        const char* runes[] = {"\u16a0","\u16a2","\u16a6","\u16a8","\u16b1","\u16b2","\u16b7","\u16b9","\u16ba","\u16be","\u16c1","\u16c3","\u16c7","\u16c8"};
        int ri = (int)(p.x * 0.1f + p.y * 0.1f) % 14;
        if (ri < 0) ri += 14;
        fprintf(f, "<text x='%.2f' y='%.2f' font-size='14' fill='%s' opacity='%.2f' font-family='serif'>%s</text>",
            p.x, p.y, o->color, op2, runes[ri]);
    }
    else if (strcmp(o->type, "crystal_ball") == 0) {
        float pulse = 0.3f + fabsf(sinf(t * 2.0f)) * 0.4f;
        fprintf(f,
            "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>"
            "<ellipse cx='0' cy='60' rx='25' ry='8' fill='#000' opacity='0.3'/>"
            "<rect x='-15' y='50' width='30' height='15' fill='#5a4a3a' rx='3'/>"
            "<circle cx='0' cy='30' r='22' fill='%s' opacity='%.1f'/>"
            "<circle cx='0' cy='30' r='18' fill='%s' opacity='0.5'/>"
            "<circle cx='-5' cy='25' r='6' fill='#FFFFFF' opacity='0.4'/>"
            "</g>\n",
            p.x, p.y, sc, op, o->color, pulse, o->color
        );
    }
    else if (strcmp(o->type, "owl") == 0) {
        float bob = sinf(t * 2.0f) * 5.0f;
        fprintf(f,
            "<g transform='translate(%.2f %.2f) scale(%.2f)' opacity='%.2f'>"
            "<ellipse cx='0' cy='%d' rx='18' ry='25' fill='#6a5a4a'/>"
            "<circle cx='0' cy='%d' r='16' fill='#7a6a5a'/>"
            "<polygon points='-12,-10 -10,-25 -5,-12' fill='#6a5a4a'/>"
            "<polygon points='12,-10 10,-25 5,-12' fill='#6a5a4a'/>"
            "<circle cx='-6' cy='%d' r='6' fill='#FFF'/>"
            "<circle cx='6' cy='%d' r='6' fill='#FFF'/>"
            "<circle cx='-6' cy='%d' r='3' fill='#1a1a2e'/>"
            "<circle cx='6' cy='%d' r='3' fill='#1a1a2e'/>"
            "<polygon points='0,-4 -3,0 3,0' fill='#FFD700'/>"
            "</g>\n",
            p.x, p.y, sc, op,
            (int)(20 + bob), (int)(0 + bob), (int)(0+bob), (int)(0+bob), (int)(0+bob), (int)(0+bob)
        );
    }
}

// =========================
// PARTICLE RENDER
// =========================
static void render_particles(FILE* f, Scene* s) {
    for (int i = 0; i < s->particle_count; i++) {
        Particle* p = &s->particles[i];
        fprintf(f,
            "<circle cx='%.2f' cy='%.2f' r='1.5' fill='%s' opacity='%.2f'/>",
            p->pos.x, p->pos.y, p->color, p->life
        );
    }
}

// =========================
// EXPORT SVG TO FILE
// =========================
void export_svg(Scene* s, const char* path, float t) {
    FILE* f = fopen(path, "w");
    if (!f) return;
    fprintf(f, "<svg width='%d' height='%d' viewBox='0 0 %d %d' xmlns='http://www.w3.org/2000/svg'>\n",
        s->w, s->h, s->w, s->h);
    fprintf(f, "<rect width='%d' height='%d' fill='%s'/>\n", s->w, s->h, s->bg_color);
    for (int i = 0; i < s->obj_count; i++) {
        render_object(f, &s->objects[i], t);
    }
    render_particles(f, s);
    fprintf(f, "</svg>");
    fclose(f);
}

// =========================
// RENDER SVG TO BUFFER (for shared library / ctypes)
// =========================
int render_svg(Scene* s, float t, char* buffer, int bufsize) {
    FILE* f = tmpfile();
    if (!f) return 0;
    fprintf(f, "<svg width='%d' height='%d' viewBox='0 0 %d %d' xmlns='http://www.w3.org/2000/svg'>\n",
        s->w, s->h, s->w, s->h);
    fprintf(f, "<rect width='%d' height='%d' fill='%s'/>\n", s->w, s->h, s->bg_color);
    for (int i = 0; i < s->obj_count; i++) {
        render_object(f, &s->objects[i], t);
    }
    render_particles(f, s);
    fprintf(f, "</svg>");
    fflush(f);
    long len = ftell(f);
    if (len >= bufsize) len = bufsize - 1;
    fseek(f, 0, SEEK_SET);
    size_t rd = fread(buffer, 1, len, f);
    buffer[rd] = '\0';
    fclose(f);
    return (int)rd;
}

// =========================
// DEMO SCENE BUILDERS
// =========================
void build_demo(Scene* s) {
    scene_init(s, 512, 512);
    strcpy(s->bg_color, "#0d1117");

    // Glow
    Object* glow = add_object(s, "glow", "glow");
    glow->pos = (Vec2){256, 300};
    strcpy(glow->color, "#1e5eff");

    // Stars
    for (int i = 0; i < 20; i++) {
        Object* star = add_object(s, "star", "star");
        star->pos = (Vec2){ frand(s)*512, frand(s)*512 };
        strcpy(star->color, "#7ec8ff");
    }

    // Coat
    Object* coat = add_object(s, "coat", "coat");
    coat->pos = (Vec2){256, 290};
    strcpy(coat->color, "#2b2b2b");

    // Beard
    Object* beard = add_object(s, "beard", "beard");
    beard->pos = (Vec2){256, 268};

    // Face
    Object* face = add_object(s, "face", "face");
    face->pos = (Vec2){256, 250};
    strcpy(face->color, "#7ec8ff");

    // Hat
    Object* hat = add_object(s, "hat", "wizard_hat");
    hat->pos = (Vec2){256, 200};
    strcpy(hat->color, "#1e5eff");
    add_key(hat, 0.0f, (Vec2){256, 200}, -3, 1, 1);
    add_key(hat, 0.5f, (Vec2){256, 198}, 3, 1, 1);
    add_key(hat, 1.0f, (Vec2){256, 200}, -3, 1, 1);

    // Wand
    Object* wand = add_object(s, "wand", "wand");
    wand->pos = (Vec2){310, 280};
    strcpy(wand->color, "#7ec8ff");
    add_key(wand, 0.0f, (Vec2){310, 280}, -10, 1, 1);
    add_key(wand, 0.5f, (Vec2){310, 280}, 15, 1, 1);
    add_key(wand, 1.0f, (Vec2){310, 280}, -10, 1, 1);
}

void build_fire_mage(Scene* s) {
    scene_init(s, 512, 512);
    strcpy(s->bg_color, "#1a0500");

    Object* glow = add_object(s, "glow", "glow");
    glow->pos = (Vec2){256, 300};
    strcpy(glow->color, "#FF4500");

    for (int i = 0; i < 15; i++) {
        Object* star = add_object(s, "star", "star");
        star->pos = (Vec2){ frand(s)*512, frand(s)*512 };
        strcpy(star->color, "#FF4500");
    }

    Object* coat = add_object(s, "coat", "coat");
    coat->pos = (Vec2){256, 290};
    strcpy(coat->color, "#3B1B00");

    Object* beard = add_object(s, "beard", "beard");
    beard->pos = (Vec2){256, 268};

    Object* face = add_object(s, "face", "face");
    face->pos = (Vec2){256, 250};
    strcpy(face->color, "#FF4500");

    Object* hat = add_object(s, "hat", "crown_hat");
    hat->pos = (Vec2){256, 200};
    strcpy(hat->color, "#8B0000");
    add_key(hat, 0.0f, (Vec2){256, 200}, 0, 1, 1);
    add_key(hat, 1.0f, (Vec2){256, 200}, 5, 1, 1);

    Object* wand = add_object(s, "wand", "fire_wand");
    wand->pos = (Vec2){310, 280};
    strcpy(wand->color, "#FF4500");
    add_key(wand, 0.0f, (Vec2){310, 280}, -5, 1, 1);
    add_key(wand, 1.0f, (Vec2){310, 280}, 20, 1, 1);
}

void build_arcane(Scene* s) {
    scene_init(s, 512, 512);
    strcpy(s->bg_color, "#021a36");

    Object* glow = add_object(s, "glow", "glow");
    glow->pos = (Vec2){256, 300};
    strcpy(glow->color, "#00BFFF");

    // Runes
    for (int i = 0; i < 15; i++) {
        Object* rune = add_object(s, "rune", "rune");
        rune->pos = (Vec2){ frand(s)*512, frand(s)*512 };
        strcpy(rune->color, "#00BFFF");
    }

    Object* coat = add_object(s, "coat", "coat");
    coat->pos = (Vec2){256, 290};
    strcpy(coat->color, "#0a2a46");

    Object* beard = add_object(s, "beard", "beard");
    beard->pos = (Vec2){256, 268};

    Object* face = add_object(s, "face", "face");
    face->pos = (Vec2){256, 250};
    strcpy(face->color, "#00BFFF");

    Object* hat = add_object(s, "hat", "wide_hat");
    hat->pos = (Vec2){256, 200};
    strcpy(hat->color, "#1a5276");
    add_key(hat, 0.0f, (Vec2){256, 200}, -2, 1, 1);
    add_key(hat, 1.0f, (Vec2){256, 200}, 4, 1, 1);

    Object* wand = add_object(s, "wand", "crystal_staff");
    wand->pos = (Vec2){310, 280};
    strcpy(wand->color, "#00BFFF");
    add_key(wand, 0.0f, (Vec2){310, 280}, -8, 1, 1);
    add_key(wand, 0.5f, (Vec2){310, 280}, 12, 1, 1);
    add_key(wand, 1.0f, (Vec2){310, 280}, -8, 1, 1);

    // Crystal ball
    Object* ball = add_object(s, "ball", "crystal_ball");
    ball->pos = (Vec2){140, 360};
    strcpy(ball->color, "#00BFFF");
}

void build_storm(Scene* s) {
    scene_init(s, 512, 512);
    strcpy(s->bg_color, "#10002b");

    Object* glow = add_object(s, "glow", "glow");
    glow->pos = (Vec2){256, 300};
    strcpy(glow->color, "#4cc9f0");

    for (int i = 0; i < 25; i++) {
        Object* star = add_object(s, "star", "star");
        star->pos = (Vec2){ frand(s)*512, frand(s)*512 };
        strcpy(star->color, "#4cc9f0");
    }

    Object* coat = add_object(s, "coat", "coat");
    coat->pos = (Vec2){256, 290};
    strcpy(coat->color, "#10002b");

    Object* beard = add_object(s, "beard", "beard");
    beard->pos = (Vec2){256, 268};

    Object* face = add_object(s, "face", "face");
    face->pos = (Vec2){256, 250};
    strcpy(face->color, "#4cc9f0");

    Object* hat = add_object(s, "hat", "wizard_hat");
    hat->pos = (Vec2){256, 200};
    strcpy(hat->color, "#3a0ca3");
    add_key(hat, 0.0f, (Vec2){256, 200}, -5, 1, 1);
    add_key(hat, 0.5f, (Vec2){256, 200}, 5, 1, 1);
    add_key(hat, 1.0f, (Vec2){256, 200}, -5, 1, 1);

    Object* wand = add_object(s, "wand", "lightning_wand");
    wand->pos = (Vec2){310, 280};
    strcpy(wand->color, "#4cc9f0");
    add_key(wand, 0.0f, (Vec2){310, 280}, -10, 1, 1);
    add_key(wand, 1.0f, (Vec2){310, 280}, 25, 1, 1);

    // Owl familiar
    Object* owl = add_object(s, "owl", "owl");
    owl->pos = (Vec2){130, 330};
    owl->scale = 1.2f;
}

// =========================
// SCENE EDITOR API (for ctypes bridge)
// =========================
void set_object_pos(Scene* s, int idx, float x, float y) {
    if (idx < 0 || idx >= s->obj_count) return;
    s->objects[idx].pos = (Vec2){x, y};
}

void set_object_rot(Scene* s, int idx, float r) {
    if (idx < 0 || idx >= s->obj_count) return;
    s->objects[idx].rot = r;
}

void set_object_scale(Scene* s, int idx, float sc) {
    if (idx < 0 || idx >= s->obj_count) return;
    s->objects[idx].scale = sc;
}

void set_object_opacity(Scene* s, int idx, float op) {
    if (idx < 0 || idx >= s->obj_count) return;
    s->objects[idx].opacity = op;
}

void set_object_color(Scene* s, int idx, const char* color) {
    if (idx < 0 || idx >= s->obj_count) return;
    strcpy(s->objects[idx].color, color);
}

void clear_keyframes(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return;
    s->objects[idx].key_count = 0;
}

void remove_object(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return;
    for (int i = idx; i < s->obj_count - 1; i++) {
        s->objects[i] = s->objects[i+1];
    }
    s->obj_count--;
}

void clear_scene(Scene* s) {
    s->obj_count = 0;
    s->particle_count = 0;
}

void set_bg_color(Scene* s, const char* color) {
    strcpy(s->bg_color, color);
}

void set_seed(Scene* s, unsigned int seed) {
    s->seed = seed;
}

int get_obj_count(Scene* s) {
    return s->obj_count;
}

float get_obj_pos_x(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return 0;
    return s->objects[idx].pos.x;
}

float get_obj_pos_y(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return 0;
    return s->objects[idx].pos.y;
}

float get_obj_rot(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return 0;
    return s->objects[idx].rot;
}

float get_obj_scale(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return 1;
    return s->objects[idx].scale;
}

float get_obj_opacity(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return 1;
    return s->objects[idx].opacity;
}

const char* get_obj_type(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return "";
    return s->objects[idx].type;
}

const char* get_obj_color(Scene* s, int idx) {
    if (idx < 0 || idx >= s->obj_count) return "";
    return s->objects[idx].color;
}

// =========================
// MAIN (standalone mode — renders 60 frames)
// =========================
#ifndef SHARED_LIB
int main() {
    Scene s;
    build_demo(&s);

    for (int i = 0; i < 60; i++) {
        float t = (float)i / 60.0f;
        s.particle_count = 0;
        for (int j = 0; j < 8; j++) {
            spawn_particle(&s, (Vec2){390, 240}, "#7ec8ff");
        }
        update_particles(&s, 0.02f);
        char name[64];
        sprintf(name, "frame_%02d.svg", i);
        export_svg(&s, name, t);
    }
    printf("Generated 60 frames.\n");
    return 0;
}
#endif
