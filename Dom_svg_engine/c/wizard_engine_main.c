/*
 * wizard_engine_main.c — CLI entry point for the Wizard SVG Animation Engine
 *
 * Usage:
 *   wizard_engine <scene.json> <output.svg>
 *   wizard_engine --demo <output.svg>      (generate demo wizard scene)
 *   wizard_engine --mcp-demo <output.svg>  (generate MCP node graph demo)
 *
 * The engine reads a JSON scene file, compiles it into a scene graph,
 * and exports an animated SVG file.
 */
#include "wizard_engine.h"

/* ============================================================
 * DEMO SCENE: Wizard Idle
 * ============================================================ */

static void build_demo_scene(Scene* scene) {
    scene_init(scene);
    scene_set_name(scene, "Wizard Idle");
    scene_set_size(scene, 512, 512);
    scene_set_background(scene, 0.05f, 0.03f, 0.12f);
    scene_set_duration(scene, 4.0f);

    /* Rune circle behind wizard */
    WObject* rune = scene_add_object(scene, "rune_bg", "rune_circle");
    rune->position = vec2_make(256, 280);
    rune->color[0] = '\0'; strcpy(rune->color, "#00ffff");
    obj_set_motion(rune, MOTION_ROTATE, 0.2f, 0, 0, 0);

    /* Glow orb behind wizard */
    WObject* glow = scene_add_object(scene, "glow_bg", "glow_orb");
    glow->position = vec2_make(256, 280);
    glow->scale = 3.0f;
    strcpy(glow->color, "#7b2ff7");
    obj_set_motion(glow, MOTION_GLOW, 0.5f, 0, 0, 0);

    /* Hat */
    WObject* hat = scene_add_object(scene, "hat", "hat");
    hat->position = vec2_make(256, 180);
    strcpy(hat->stroke_color, "#ffd700");
    obj_set_motion(hat, MOTION_FLOAT, 0.4f, 6.0f, 0, 0);

    /* Coat */
    WObject* coat = scene_add_object(scene, "coat", "coat");
    coat->position = vec2_make(256, 300);
    strcpy(coat->stroke_color, "#ffd700");
    obj_set_motion(coat, MOTION_FLOAT, 0.4f, 4.0f, 0, 0.5f);

    /* Beard */
    WObject* beard = scene_add_object(scene, "beard", "beard");
    beard->position = vec2_make(256, 240);
    strcpy(beard->color, "#e0e0e0");
    obj_set_motion(beard, MOTION_FLOAT, 0.4f, 3.0f, 0, 0.3f);

    /* Wand */
    WObject* wand = scene_add_object(scene, "wand", "wand");
    wand->position = vec2_make(330, 280);
    wand->rotation = -25.0f;
    obj_set_motion(wand, MOTION_WAND_WAVE, 1.0f, 15.0f, 0, 0);

    /* Stars orbiting */
    for (int i = 0; i < 5; i++) {
        char id[32];
        snprintf(id, sizeof(id), "star_%d", i);
        WObject* star = scene_add_object(scene, id, "star");
        star->position = vec2_make(256, 256);
        star->scale = 0.6f + (i % 3) * 0.2f;
        strcpy(star->color, i % 2 ? "#ffd700" : "#7ec8ff");
        obj_set_motion(star, MOTION_ORBIT, 0.3f + i * 0.1f, 0, 80 + i * 20, i * 0.2f);
        obj_set_motion_center(star, vec2_make(256, 256));
    }

    /* Magic dust emitter */
    WObject* dust = scene_add_object(scene, "magic_dust", "emitter");
    dust->position = vec2_make(256, 200);
    emitter_init(&dust->emitter, PARTICLE_DUST, dust->position);
    emitter_set_rate(&dust->emitter, 30.0f);
    emitter_set_speed(&dust->emitter, 25.0f, 15.0f);
    emitter_set_size(&dust->emitter, 2.5f, 1.0f);
    emitter_set_life(&dust->emitter, 3.0f, 1.0f);
    emitter_set_colors(&dust->emitter,
        vec3_make(0.8f, 0.6f, 1.0f),
        vec3_make(0.2f, 0.1f, 0.4f));
    emitter_set_gravity(&dust->emitter, -15.0f);
    emitter_set_area(&dust->emitter, vec2_make(40, 20));

    /* Spark emitter from wand tip */
    WObject* sparks = scene_add_object(scene, "wand_sparks", "emitter");
    sparks->position = vec2_make(330, 220);
    emitter_init(&sparks->emitter, PARTICLE_SPARK, sparks->position);
    emitter_set_rate(&sparks->emitter, 15.0f);
    emitter_set_speed(&sparks->emitter, 40.0f, 20.0f);
    emitter_set_size(&sparks->emitter, 2.0f, 0.5f);
    emitter_set_life(&sparks->emitter, 1.5f, 0.5f);
    emitter_set_colors(&sparks->emitter,
        vec3_make(1.0f, 0.9f, 0.5f),
        vec3_make(0.5f, 0.2f, 0.0f));
    emitter_set_gravity(&sparks->emitter, 30.0f);
    emitter_set_area(&sparks->emitter, vec2_make(10, 10));
}

/* ============================================================
 * DEMO SCENE: MCP Node Graph
 * ============================================================ */

static void build_mcp_demo_scene(Scene* scene) {
    scene_init(scene);
    scene_set_name(scene, "MCP Node Graph");
    scene_set_size(scene, 800, 600);
    scene_set_background(scene, 0.02f, 0.02f, 0.06f);
    scene_set_duration(scene, 6.0f);

    /* Central wizard node */
    WObject* center = scene_add_object(scene, "mcp_core", "mcp_node");
    center->position = vec2_make(400, 300);
    strcpy(center->node_label, "MCP");
    center->node_status = 1; /* ok */
    center->scale = 1.5f;
    obj_set_motion(center, MOTION_GLOW, 0.3f, 0, 0, 0);

    /* Surrounding service nodes */
    const char* labels[] = {"Gmail", "Yahoo", "Drive", "Chrome", "Vault", "OpenAI"};
    int statuses[] = {1, 1, 1, 1, 1, 2}; /* 2 = warn for OpenAI */
    int n = 6;

    for (int i = 0; i < n; i++) {
        char id[32];
        snprintf(id, sizeof(id), "node_%s", labels[i]);
        WObject* node = scene_add_object(scene, id, "mcp_node");
        float angle = (float)i / n * TWO_PI;
        float radius = 180;
        node->position = vec2_make(
            400 + cosf(angle) * radius,
            300 + sinf(angle) * radius
        );
        strcpy(node->node_label, labels[i]);
        node->node_status = statuses[i];
        node->scale = 0.8f;
        obj_set_motion(node, MOTION_PULSE, 0.5f + i * 0.1f, 5.0f, 0, i * 0.15f);
    }

    /* Connecting lines (as rect objects) */
    for (int i = 0; i < n; i++) {
        char id[32];
        snprintf(id, sizeof(id), "link_%d", i);
        WObject* link = scene_add_object(scene, id, "rect");
        float angle = (float)i / n * TWO_PI;
        float radius = 180;
        Vec2 nodePos = vec2_make(400 + cosf(angle) * radius, 300 + sinf(angle) * radius);
        link->position = vec2_make(
            (400 + nodePos.x) / 2,
            (300 + nodePos.y) / 2
        );
        link->width = vec2_len(vec2_sub(nodePos, vec2_make(400, 300)));
        link->height = 1.5f;
        link->rotation = rad2deg(atanf((nodePos.y - 300) / (nodePos.x - 400)));
        strcpy(link->color, "#1e5eff");
        link->opacity = 0.3f;
    }

    /* Background particles */
    WObject* bgDust = scene_add_object(scene, "bg_particles", "emitter");
    bgDust->position = vec2_make(400, 300);
    emitter_init(&bgDust->emitter, PARTICLE_DUST, bgDust->position);
    emitter_set_rate(&bgDust->emitter, 10.0f);
    emitter_set_speed(&bgDust->emitter, 15.0f, 10.0f);
    emitter_set_size(&bgDust->emitter, 1.5f, 0.5f);
    emitter_set_life(&bgDust->emitter, 4.0f, 1.0f);
    emitter_set_colors(&bgDust->emitter,
        vec3_make(0.3f, 0.5f, 1.0f),
        vec3_make(0.05f, 0.05f, 0.15f));
    emitter_set_gravity(&bgDust->emitter, -5.0f);
    emitter_set_area(&bgDust->emitter, vec2_make(300, 200));
    emitter_set_max(&bgDust->emitter, 100);
}

/* ============================================================
 * MAIN
 * ============================================================ */

int main(int argc, char* argv[]) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <scene.json> <output.svg>\n", argv[0]);
        fprintf(stderr, "       %s --demo <output.svg>\n", argv[0]);
        fprintf(stderr, "       %s --mcp-demo <output.svg>\n", argv[0]);
        return 1;
    }

    Scene* scene = malloc(sizeof(Scene));
    if (!scene) {
        fprintf(stderr, "Error: Failed to allocate scene memory\n");
        return 1;
    }

    if (strcmp(argv[1], "--demo") == 0) {
        build_demo_scene(scene);
    } else if (strcmp(argv[1], "--mcp-demo") == 0) {
        build_mcp_demo_scene(scene);
    } else {
        if (load_scene_file(argv[1], scene) != 0) {
            fprintf(stderr, "Error: Failed to load scene file: %s\n", argv[1]);
            free(scene);
            return 1;
        }
    }

    if (export_svg(scene, argv[2]) != 0) {
        fprintf(stderr, "Error: Failed to export SVG: %s\n", argv[2]);
        free(scene);
        return 1;
    }

    fprintf(stderr, "OK: SVG exported to %s (%d objects)\n", argv[2], scene->object_count);
    free(scene);
    return 0;
}
