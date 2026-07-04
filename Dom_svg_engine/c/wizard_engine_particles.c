/*
 * wizard_engine_particles.c — Particle system (dust, stars, sparks, runes)
 */
#include "wizard_engine.h"

/* ============================================================
 * PARTICLE EMITTER
 * ============================================================ */

void emitter_init(ParticleEmitter* e, ParticleType type, Vec2 pos) {
    if (!e) return;
    memset(e, 0, sizeof(ParticleEmitter));
    e->emit_type = type;
    e->emit_position = pos;
    e->emit_area = vec2_make(20.0f, 20.0f);
    e->emit_rate = 20.0f;          /* particles per second */
    e->emit_speed = 30.0f;
    e->emit_speed_var = 15.0f;
    e->particle_size = 3.0f;
    e->particle_size_var = 1.0f;
    e->particle_life = 2.0f;
    e->particle_life_var = 0.5f;
    e->color_start = vec3_make(0.8f, 0.6f, 1.0f);  /* purple-ish */
    e->color_end = vec3_make(0.2f, 0.1f, 0.4f);     /* dark purple */
    e->gravity = -20.0f;           /* negative = floats up (SVG y is down) */
    e->drag = 0.98f;
    e->max_particles = 200;
    e->seed = 42;
    e->particle_count = 0;
    e->emit_accumulator = 0.0f;
    e->rng_state = e->seed;
}

void emitter_set_rate(ParticleEmitter* e, float rate) {
    if (e) e->emit_rate = rate;
}

void emitter_set_speed(ParticleEmitter* e, float speed, float variance) {
    if (e) { e->emit_speed = speed; e->emit_speed_var = variance; }
}

void emitter_set_size(ParticleEmitter* e, float size, float variance) {
    if (e) { e->particle_size = size; e->particle_size_var = variance; }
}

void emitter_set_life(ParticleEmitter* e, float life, float variance) {
    if (e) { e->particle_life = life; e->particle_life_var = variance; }
}

void emitter_set_colors(ParticleEmitter* e, Vec3 start, Vec3 end) {
    if (e) { e->color_start = start; e->color_end = end; }
}

void emitter_set_gravity(ParticleEmitter* e, float gravity) {
    if (e) e->gravity = gravity;
}

void emitter_set_drag(ParticleEmitter* e, float drag) {
    if (e) e->drag = clampf(drag, 0, 1);
}

void emitter_set_area(ParticleEmitter* e, Vec2 area) {
    if (e) e->emit_area = area;
}

void emitter_set_max(ParticleEmitter* e, int max) {
    if (e) e->max_particles = clampf(max, 1, MAX_PARTICLES);
}

static void spawn_particle(ParticleEmitter* e) {
    if (e->particle_count >= e->max_particles || e->particle_count >= MAX_PARTICLES)
        return;

    /* Find a dead particle slot or use next */
    int idx = -1;
    for (int i = 0; i < e->particle_count; i++) {
        if (!e->particles[i].active) {
            idx = i;
            break;
        }
    }
    if (idx == -1 && e->particle_count < MAX_PARTICLES) {
        idx = e->particle_count;
        e->particle_count++;
    }
    if (idx == -1) return;

    Particle* p = &e->particles[idx];
    memset(p, 0, sizeof(Particle));
    p->active = 1;
    p->type = e->emit_type;

    /* Position with spread */
    float rx = (frandom(&e->rng_state) - 0.5f) * e->emit_area.x;
    float ry = (frandom(&e->rng_state) - 0.5f) * e->emit_area.y;
    p->position = vec2_add(e->emit_position, vec2_make(rx, ry));

    /* Velocity — random direction with speed */
    float angle = frandom(&e->rng_state) * TWO_PI;
    float speed = e->emit_speed + (frandom(&e->rng_state) - 0.5f) * e->emit_speed_var;
    p->velocity = vec2_make(cosf(angle) * speed, sinf(angle) * speed);
    p->acceleration = vec2_make(0, e->gravity);

    /* Life */
    p->life = 1.0f;
    p->max_life = e->particle_life + (frandom(&e->rng_state) - 0.5f) * e->particle_life_var;

    /* Size */
    p->size = e->particle_size + (frandom(&e->rng_state) - 0.5f) * e->particle_size_var;

    /* Rotation */
    p->rotation = frandom(&e->rng_state) * 360.0f;
    p->angular_vel = (frandom(&e->rng_state) - 0.5f) * 180.0f;

    /* Color */
    p->color = e->color_start;
    p->opacity = 1.0f;
}

void emitter_update(ParticleEmitter* e, float dt) {
    if (!e || dt <= 0) return;

    /* Spawn new particles */
    e->emit_accumulator += e->emit_rate * dt;
    while (e->emit_accumulator >= 1.0f) {
        spawn_particle(e);
        e->emit_accumulator -= 1.0f;
    }

    /* Update existing particles */
    for (int i = 0; i < e->particle_count; i++) {
        Particle* p = &e->particles[i];
        if (!p->active) continue;

        /* Physics */
        p->velocity.x += p->acceleration.x * dt;
        p->velocity.y += p->acceleration.y * dt;
        p->velocity.x *= e->drag;
        p->velocity.y *= e->drag;
        p->position.x += p->velocity.x * dt;
        p->position.y += p->velocity.y * dt;
        p->rotation += p->angular_vel * dt;

        /* Life */
        p->life -= dt / p->max_life;
        if (p->life <= 0.0f) {
            p->active = 0;
            continue;
        }

        /* Color interpolation */
        float t = 1.0f - p->life;
        p->color.x = lerpf(e->color_start.x, e->color_end.x, t);
        p->color.y = lerpf(e->color_start.y, e->color_end.y, t);
        p->color.z = lerpf(e->color_start.z, e->color_end.z, t);

        /* Fade out in last 30% of life */
        if (p->life < 0.3f) {
            p->opacity = p->life / 0.3f;
        } else {
            p->opacity = 1.0f;
        }

        /* Shrink slightly over lifetime */
        p->size *= (0.5f + 0.5f * p->life);
    }
}
