#include "gui.h"
#include "imgui.h"
#include <stdio.h>

void render_menubar(GuiState *state, EventBus *bus) {
    if (!ImGui::BeginMainMenuBar()) return;

    if (ImGui::BeginMenu("File")) {
        if (ImGui::MenuItem("New Session", "Cmd+N")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "New session requested");
        }
        if (ImGui::MenuItem("Open Project...", "Cmd+O")) {
            event_bus_publish(bus, CH_FILE, EV_INFO, "Menu", "Open project requested");
        }
        if (ImGui::MenuItem("Save Layout", "Cmd+S")) {
            ImGui::SaveIniSettingsToDisk("cascade_layout.ini");
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Layout saved");
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Export Events...", "Cmd+E")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Export events requested");
        }
        if (ImGui::MenuItem("Export Screenshot...", "Cmd+Shift+S")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Screenshot requested");
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Quit", "Cmd+Q")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Quit requested");
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Edit")) {
        if (ImGui::MenuItem("Undo", "Cmd+Z")) {}
        if (ImGui::MenuItem("Redo", "Cmd+Shift+Z")) {}
        ImGui::Separator();
        if (ImGui::MenuItem("Clear Events", "Cmd+K")) {
            event_bus_clear(bus);
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Events cleared");
        }
        if (ImGui::MenuItem("Clear Console")) {
            event_bus_publish(bus, CH_CONSOLE, EV_INFO, "Menu", "Console cleared");
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("View")) {
        ImGui::MenuItem("Events", "Cmd+1", &state->show_events);
        ImGui::MenuItem("Graph", "Cmd+2", &state->show_graph);
        ImGui::MenuItem("AI", "Cmd+3", &state->show_ai);
        ImGui::MenuItem("Console", "Cmd+4", &state->show_console);
        ImGui::MenuItem("Profiler", "Cmd+5", &state->show_profiler);
        ImGui::MenuItem("Memory", "Cmd+6", &state->show_memory);
        ImGui::Separator();
        ImGui::MenuItem("Fullscreen", "Cmd+Shift+F", &state->fullscreen);
        ImGui::MenuItem("Docking", NULL, &state->docking);
        ImGui::MenuItem("VSync", NULL, &state->vsync);
        ImGui::Separator();
        ImGui::MenuItem("Status Bar", NULL, &state->show_statusbar);
        ImGui::MenuItem("Activity Rail", NULL, &state->show_activity_rail);
        ImGui::MenuItem("Toggle Bar (right)", NULL, &state->show_right_bar);
        ImGui::Separator();
        ImGui::MenuItem("Appearance...", NULL, &state->show_appearance);
        ImGui::MenuItem("Settings...", NULL, &state->show_settings);
        ImGui::MenuItem("Keyboard Shortcuts...", "Cmd+/", &state->show_shortcuts);
        ImGui::Separator();
        if (ImGui::BeginMenu("Layout Presets")) {
            if (ImGui::MenuItem("Default (all panels)")) apply_layout_preset(state, 0);
            if (ImGui::MenuItem("Debug (events + console)")) apply_layout_preset(state, 1);
            if (ImGui::MenuItem("Profiling (profiler + graph + memory)")) apply_layout_preset(state, 2);
            if (ImGui::MenuItem("AI Focus (AI + events)")) apply_layout_preset(state, 3);
            if (ImGui::MenuItem("Minimal (events only)")) apply_layout_preset(state, 4);
            ImGui::EndMenu();
        }
        ImGui::Separator();
        ImGui::MenuItem("ImGui Demo", NULL, &state->show_demo);
        ImGui::MenuItem("Metrics", NULL, &state->show_metrics);
        ImGui::MenuItem("Style Editor", NULL, &state->show_style_editor);
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Tools")) {
        if (ImGui::MenuItem("Run Pipeline", "Cmd+R")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Pipeline run requested");
        }
        if (ImGui::MenuItem("Run Graph Analysis", "Cmd+G")) {
            event_bus_publish(bus, CH_GRAPH, EV_INFO, "Menu", "Graph analysis requested");
        }
        if (ImGui::MenuItem("AI Query", "Cmd+I")) {
            event_bus_publish(bus, CH_AI, EV_INFO, "Menu", "AI query requested");
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Pause EventBus", "Cmd+P", &state->paused)) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu",
                              state->paused ? "EventBus paused" : "EventBus resumed");
        }
        ImGui::Separator();
        if (ImGui::BeginMenu("Theme")) {
            if (ImGui::MenuItem("Dark", NULL, state->theme == 0)) { state->theme = 0; apply_theme(0); }
            if (ImGui::MenuItem("Light", NULL, state->theme == 1)) { state->theme = 1; apply_theme(1); }
            if (ImGui::MenuItem("Classic", NULL, state->theme == 2)) { state->theme = 2; apply_theme(2); }
            if (ImGui::MenuItem("Cascade Dark", NULL, state->theme == 3)) { state->theme = 3; apply_theme(3); }
            ImGui::EndMenu();
        }
        if (ImGui::BeginMenu("Font Scale")) {
            if (ImGui::MenuItem("80%", NULL, state->font_scale == 80)) { state->font_scale = 80; apply_font_scale(80); }
            if (ImGui::MenuItem("100%", NULL, state->font_scale == 100)) { state->font_scale = 100; apply_font_scale(100); }
            if (ImGui::MenuItem("120%", NULL, state->font_scale == 120)) { state->font_scale = 120; apply_font_scale(120); }
            if (ImGui::MenuItem("150%", NULL, state->font_scale == 150)) { state->font_scale = 150; apply_font_scale(150); }
            ImGui::EndMenu();
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Help")) {
        if (ImGui::MenuItem("About Cascade", "Cmd+Shift+A")) { state->show_about = true; }
        if (ImGui::MenuItem("Documentation")) {
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Menu", "Documentation requested");
        }
        if (ImGui::MenuItem("Keyboard Shortcuts", "Cmd+/")) {
            state->show_shortcuts = true;
        }
        ImGui::EndMenu();
    }

    ImGui::EndMainMenuBar();
}
