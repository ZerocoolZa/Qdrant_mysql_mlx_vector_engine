#include "gui.h"
#include "imgui.h"
#include <stdio.h>
#include <string.h>

/* ═══════════════════════════════════════════════════════════
 * STATUS BAR — bottom bar showing FPS, events, memory, time
 * ═══════════════════════════════════════════════════════════ */

void render_statusbar(GuiState *state, EventBus *bus) {
    if (!state->show_statusbar) return;

    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImVec2 pos = ImVec2(vp->WorkPos.x, vp->WorkPos.y + vp->WorkSize.y - 24.0f);
    ImVec2 size = ImVec2(vp->WorkSize.x, 24.0f);

    ImGui::SetNextWindowPos(pos);
    ImGui::SetNextWindowSize(size);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(8, 2));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(12, 0));

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDocking |
                             ImGuiWindowFlags_NoTitleBar |
                             ImGuiWindowFlags_NoCollapse |
                             ImGuiWindowFlags_NoResize |
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoScrollbar |
                             ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_NoBringToFrontOnFocus;

    ImGui::Begin("##StatusBar", NULL, flags);
    ImGui::PopStyleVar(2);

    ImGuiIO &io = ImGui::GetIO();

    /* FPS */
    ImVec4 fps_color = io.Framerate > 50 ? ImVec4(0.3f, 0.8f, 0.3f, 1.0f) :
                       io.Framerate > 30 ? ImVec4(0.8f, 0.8f, 0.2f, 1.0f) :
                       ImVec4(0.9f, 0.3f, 0.3f, 1.0f);
    ImGui::TextColored(fps_color, "FPS: %.0f", io.Framerate);
    ImGui::SameLine();

    /* Events */
    ImGui::TextDisabled("|");
    ImGui::SameLine();
    ImGui::Text("Events: %llu", (unsigned long long)event_bus_count(bus));
    ImGui::SameLine();

    /* Dropped */
    uint64_t dropped = event_bus_dropped(bus);
    if (dropped > 0) {
        ImGui::TextDisabled("|");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(0.9f, 0.5f, 0.3f, 1.0f), "Dropped: %llu", (unsigned long long)dropped);
        ImGui::SameLine();
    }

    /* Windows count */
    ImGui::TextDisabled("|");
    ImGui::SameLine();
    ImGui::Text("Windows: %d", io.MetricsRenderWindows);
    ImGui::SameLine();

    /* Vertices */
    ImGui::TextDisabled("|");
    ImGui::SameLine();
    ImGui::Text("Verts: %d", io.MetricsRenderVertices);
    ImGui::SameLine();

    /* Paused indicator */
    if (state->paused) {
        ImGui::TextDisabled("|");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(0.9f, 0.8f, 0.2f, 1.0f), "[PAUSED]");
        ImGui::SameLine();
    }

    /* Right-aligned: time + theme */
    const char *theme_names[] = { "Dark", "Light", "Classic", "Cascade Dark" };
    const char *theme_name = state->theme >= 0 && state->theme < 4 ? theme_names[state->theme] : "?";

    float right_w = ImGui::CalcTextSize("Theme: XXX | 00:00:00").x + 16.0f;
    ImGui::SameLine(ImGui::GetWindowWidth() - right_w);
    ImGui::Text("Theme: %s | %02d:%02d:%02d",
                theme_name,
                (int)(ImGui::GetTime() / 3600) % 24,
                (int)(ImGui::GetTime() / 60) % 60,
                (int)ImGui::GetTime() % 60);

    ImGui::End();
}

/* ═══════════════════════════════════════════════════════════
 * KEYBOARD SHORTCUTS HELP WINDOW
 * ═══════════════════════════════════════════════════════════ */

void render_shortcuts_window(GuiState *state) {
    if (!state->show_shortcuts) return;

    ImGui::SetNextWindowSize(ImVec2(500, 400), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Keyboard Shortcuts", &state->show_shortcuts)) {
        ImGui::End();
        return;
    }

    ImGui::TextDisabled("Cascade GUI Keyboard Reference");
    ImGui::Separator();

    if (ImGui::BeginTable("shortcuts", 2, ImGuiTableFlags_BordersV | ImGuiTableFlags_RowBg)) {
        ImGui::TableSetupColumn("Shortcut", ImGuiTableColumnFlags_WidthFixed, 140);
        ImGui::TableSetupColumn("Action", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableHeadersRow();

        struct { const char *key; const char *action; } shortcuts[] = {
            {"Cmd+N",         "New session"},
            {"Cmd+O",         "Open project"},
            {"Cmd+S",         "Save layout to disk"},
            {"Cmd+Shift+S",   "Export screenshot"},
            {"Cmd+E",         "Export events"},
            {"Cmd+Q",         "Quit"},
            {"Cmd+Z",         "Undo"},
            {"Cmd+Shift+Z",   "Redo"},
            {"Cmd+K",         "Clear events"},
            {"Cmd+R",         "Run pipeline"},
            {"Cmd+G",         "Run graph analysis"},
            {"Cmd+I",         "AI query"},
            {"Cmd+P",         "Pause / resume EventBus"},
            {"Cmd+1",         "Toggle Events panel"},
            {"Cmd+2",         "Toggle Graph panel"},
            {"Cmd+3",         "Toggle AI panel"},
            {"Cmd+4",         "Toggle Console panel"},
            {"Cmd+5",         "Toggle Profiler panel"},
            {"Cmd+6",         "Toggle Memory panel"},
            {"Cmd+Shift+F",   "Toggle fullscreen"},
            {"Cmd+Shift+A",   "About Cascade"},
            {"Cmd+/",         "Show this shortcuts window"},
        };

        for (int i = 0; i < (int)(sizeof(shortcuts)/sizeof(shortcuts[0])); i++) {
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::TextColored(ImVec4(0.6f, 0.7f, 0.9f, 1.0f), "%s", shortcuts[i].key);
            ImGui::TableSetColumnIndex(1);
            ImGui::TextUnformatted(shortcuts[i].action);
        }
        ImGui::EndTable();
    }

    ImGui::Separator();
    ImGui::TextDisabled("Tip: Drag panel tabs to dock them. Right-click the dockspace for layout options.");
    ImGui::TextDisabled("Layout is auto-saved to cascade_layout.ini");

    ImGui::End();
}

/* ═══════════════════════════════════════════════════════════
 * SETTINGS / CONFIGURATION PANEL
 * ═══════════════════════════════════════════════════════════ */

void render_settings_panel(GuiState *state, EventBus *bus) {
    if (!state->show_settings) return;

    ImGui::SetNextWindowSize(ImVec2(400, 450), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Settings", &state->show_settings)) {
        ImGui::End();
        return;
    }

    /* --- Appearance --- */
    if (ImGui::CollapsingHeader("Appearance", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Text("Theme");
        ImGui::SameLine(150);
        const char *themes[] = { "Dark", "Light", "Classic", "Cascade Dark" };
        if (ImGui::Combo("##theme_set", &state->theme, themes, 4)) {
            apply_theme(state->theme);
            show_notification(state, "Theme changed");
        }

        ImGui::Text("Font Scale");
        ImGui::SameLine(150);
        if (ImGui::SliderInt("##font_set", &state->font_scale, 50, 200, "%d%%")) {
            apply_font_scale(state->font_scale);
        }

        ImGui::Text("Status Bar");
        ImGui::SameLine(150);
        ImGui::Checkbox("##statusbar_set", &state->show_statusbar);

        ImGui::Text("Notifications");
        ImGui::SameLine(150);
        ImGui::Checkbox("##notif_set", &state->show_notifications);
    }

    /* --- Layout --- */
    if (ImGui::CollapsingHeader("Layout", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Text("Docking");
        ImGui::SameLine(150);
        ImGui::Checkbox("##docking_set", &state->docking);

        ImGui::Text("VSync");
        ImGui::SameLine(150);
        ImGui::Checkbox("##vsync_set", &state->vsync);

        ImGui::Separator();

        ImGui::Text("Layout Preset");
        ImGui::SameLine(150);
        const char *presets[] = { "Default", "Debug", "Profiling", "AI Focus", "Minimal" };
        if (ImGui::Combo("##preset_set", &state->layout_preset, presets, 5)) {
            apply_layout_preset(state, state->layout_preset);
        }

        if (ImGui::Button("Save Layout", ImVec2(120, 0))) {
            ImGui::SaveIniSettingsToDisk("cascade_layout.ini");
            show_notification(state, "Layout saved to disk");
            event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Settings", "Layout saved");
        }
        ImGui::SameLine();
        if (ImGui::Button("Reset Layout", ImVec2(120, 0))) {
            apply_layout_preset(state, 0);
            show_notification(state, "Layout reset to default");
        }
    }

    /* --- Panels --- */
    if (ImGui::CollapsingHeader("Panels")) {
        ImGui::Text("Show / hide individual panels:");
        ImGui::Checkbox("Events",   &state->show_events);   ImGui::SameLine(150);
        ImGui::Checkbox("Graph",    &state->show_graph);
        ImGui::Checkbox("AI",       &state->show_ai);       ImGui::SameLine(150);
        ImGui::Checkbox("Console",  &state->show_console);
        ImGui::Checkbox("Profiler", &state->show_profiler); ImGui::SameLine(150);
        ImGui::Checkbox("Memory",   &state->show_memory);

        ImGui::Separator();
        if (ImGui::Button("Show All", ImVec2(100, 0))) {
            state->show_events = state->show_graph = state->show_ai = true;
            state->show_console = state->show_profiler = state->show_memory = true;
            show_notification(state, "All panels shown");
        }
        ImGui::SameLine();
        if (ImGui::Button("Hide All", ImVec2(100, 0))) {
            state->show_events = state->show_graph = state->show_ai = false;
            state->show_console = state->show_profiler = state->show_memory = false;
            show_notification(state, "All panels hidden");
        }
    }

    /* --- Debug --- */
    if (ImGui::CollapsingHeader("Debug")) {
        ImGui::Checkbox("ImGui Demo Window", &state->show_demo);
        ImGui::Checkbox("ImGui Metrics", &state->show_metrics);
        ImGui::Checkbox("Style Editor", &state->show_style_editor);

        ImGui::Separator();
        ImGuiIO &io = ImGui::GetIO();
        ImGui::TextDisabled("ImGui Version: %s", IMGUI_VERSION);
        ImGui::TextDisabled("Backend: GLFW + OpenGL3");
        ImGui::TextDisabled("FPS: %.1f  Verts: %d  Windows: %d",
                            io.Framerate, io.MetricsRenderVertices, io.MetricsRenderWindows);
    }

    ImGui::End();
}

/* ═══════════════════════════════════════════════════════════
 * DOCKSPACE RIGHT-CLICK CONTEXT MENU
 * ═══════════════════════════════════════════════════════════ */

void render_dockspace_context_menu(GuiState *state) {
    /* Right-click on empty dockspace area opens context menu */
    if (ImGui::BeginPopupContextWindow("##DockContextMenu",
                                        ImGuiPopupFlags_MouseButtonRight | ImGuiPopupFlags_NoOpenOverItems)) {
        ImGui::SeparatorText("Show Panels");

        ImGui::MenuItem("Events", NULL, &state->show_events);
        ImGui::MenuItem("Graph", NULL, &state->show_graph);
        ImGui::MenuItem("AI", NULL, &state->show_ai);
        ImGui::MenuItem("Console", NULL, &state->show_console);
        ImGui::MenuItem("Profiler", NULL, &state->show_profiler);
        ImGui::MenuItem("Memory", NULL, &state->show_memory);

        ImGui::Separator();

        if (ImGui::BeginMenu("Layout Presets")) {
            if (ImGui::MenuItem("Default (all panels)")) {
                apply_layout_preset(state, 0);
            }
            if (ImGui::MenuItem("Debug (events + console)")) {
                apply_layout_preset(state, 1);
            }
            if (ImGui::MenuItem("Profiling (profiler + graph + memory)")) {
                apply_layout_preset(state, 2);
            }
            if (ImGui::MenuItem("AI Focus (AI + events)")) {
                apply_layout_preset(state, 3);
            }
            if (ImGui::MenuItem("Minimal (events only)")) {
                apply_layout_preset(state, 4);
            }
            ImGui::EndMenu();
        }

        ImGui::Separator();

        if (ImGui::MenuItem("Show All Panels")) {
            state->show_events = state->show_graph = state->show_ai = true;
            state->show_console = state->show_profiler = state->show_memory = true;
            show_notification(state, "All panels shown");
        }
        if (ImGui::MenuItem("Hide All Panels")) {
            state->show_events = state->show_graph = state->show_ai = false;
            state->show_console = state->show_profiler = state->show_memory = false;
        }

        ImGui::Separator();

        if (ImGui::MenuItem("Save Layout", "Cmd+S")) {
            ImGui::SaveIniSettingsToDisk("cascade_layout.ini");
            show_notification(state, "Layout saved");
        }
        if (ImGui::MenuItem("Reset Layout")) {
            apply_layout_preset(state, 0);
            show_notification(state, "Layout reset");
        }

        ImGui::Separator();

        if (ImGui::MenuItem("Settings...", NULL, &state->show_settings)) {}
        if (ImGui::MenuItem("Keyboard Shortcuts...", "Cmd+/", &state->show_shortcuts)) {}
        if (ImGui::MenuItem("Status Bar", NULL, &state->show_statusbar)) {}

        ImGui::Separator();

        if (ImGui::MenuItem("ImGui Demo", NULL, &state->show_demo)) {}
        if (ImGui::MenuItem("Style Editor", NULL, &state->show_style_editor)) {}

        ImGui::EndPopup();
    }
}

/* ═══════════════════════════════════════════════════════════
 * LAYOUT PRESETS — toggle panels for different workflows
 * ═══════════════════════════════════════════════════════════ */

void apply_layout_preset(GuiState *state, int preset) {
    state->layout_preset = preset;

    /* Reset all panels first */
    state->show_events = false;
    state->show_graph = false;
    state->show_ai = false;
    state->show_console = false;
    state->show_profiler = false;
    state->show_memory = false;

    switch (preset) {
        case 0: /* Default — all panels */
            state->show_events = true;
            state->show_graph = true;
            state->show_ai = true;
            state->show_console = true;
            state->show_profiler = true;
            state->show_memory = true;
            break;
        case 1: /* Debug — events + console */
            state->show_events = true;
            state->show_console = true;
            break;
        case 2: /* Profiling — profiler + graph + memory */
            state->show_profiler = true;
            state->show_graph = true;
            state->show_memory = true;
            break;
        case 3: /* AI Focus — AI + events */
            state->show_ai = true;
            state->show_events = true;
            break;
        case 4: /* Minimal — events only */
            state->show_events = true;
            break;
    }
}

/* ═══════════════════════════════════════════════════════════
 * NOTIFICATIONS / TOASTS
 * ═══════════════════════════════════════════════════════════ */

void show_notification(GuiState *state, const char *text) {
    strncpy(state->notification_text, text, sizeof(state->notification_text) - 1);
    state->notification_text[sizeof(state->notification_text) - 1] = '\0';
    state->notification_timer = 3.0f;
}

void render_notification(GuiState *state) {
    if (!state->show_notifications || state->notification_timer <= 0.0f) return;

    state->notification_timer -= ImGui::GetIO().DeltaTime;
    if (state->notification_timer <= 0.0f) {
        state->notification_text[0] = '\0';
        return;
    }

    float alpha = state->notification_timer > 2.5f ? 1.0f :
                  state->notification_timer < 0.5f ? state->notification_timer * 2.0f : 1.0f;

    ImGuiViewport *vp = ImGui::GetMainViewport();
    ImVec2 pos = ImVec2(vp->WorkPos.x + vp->WorkSize.x - 280.0f,
                        vp->WorkPos.y + 60.0f);
    ImGui::SetNextWindowPos(pos);
    ImGui::SetNextWindowSize(ImVec2(260, 0));

    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 8.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(12, 8));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.15f, 0.15f, 0.20f, alpha * 0.95f));
    ImGui::PushStyleColor(ImGuiCol_Border, ImVec4(0.3f, 0.5f, 0.8f, alpha * 0.5f));

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar |
                             ImGuiWindowFlags_NoResize |
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoScrollbar |
                             ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_NoFocusOnAppearing |
                             ImGuiWindowFlags_NoNav;

    ImGui::Begin("##Notification", NULL, flags);
    ImGui::TextColored(ImVec4(0.4f, 0.6f, 1.0f, alpha), ">> %s", state->notification_text);
    ImGui::End();

    ImGui::PopStyleColor(2);
    ImGui::PopStyleVar(2);
}

/* ═══════════════════════════════════════════════════════════
 * ACTIVITY RAIL — left vertical icon bar (VS Code style)
 * ═══════════════════════════════════════════════════════════ */

/* Rail tab definitions: icon, tooltip, panel-toggle group */
struct RailTab {
    const char *icon;
    const char *tooltip;
    int tab_id;
};

static const RailTab rail_tabs[] = {
    {"\xE2\x96\xA3", "Events Explorer",   0},  // ▣
    {"\xE2\x97\x88", "Graph View",        1},  // ◈
    {"\xE2\x9C\xA6", "AI Assistant",      2},  // ✦
    {"\xE2\x96\xBC", "Console Terminal",  3},  // ▼
    {"\xE2\x97\x8F", "Profiler",          4},  // ●
    {"\xE2\x97\x87", "Memory Inspector",  5},  // ◇
};

static const int rail_tab_count = (int)(sizeof(rail_tabs)/sizeof(rail_tabs[0]));

/* Helper: draw a vertical icon button with active highlight */
static bool rail_icon_button(const char *icon, bool active, const char *tooltip) {
    ImGuiStyle &style = ImGui::GetStyle();

    ImVec2 btn_size(36, 36);
    ImVec4 normal_bg = ImVec4(0.08f, 0.08f, 0.10f, 0.0f);
    ImVec4 hover_bg  = ImVec4(0.20f, 0.25f, 0.35f, 1.0f);
    ImVec4 active_bg = ImVec4(0.15f, 0.20f, 0.35f, 1.0f);
    ImVec4 active_accent = ImVec4(0.30f, 0.55f, 0.90f, 1.0f);

    if (active) {
        ImGui::PushStyleColor(ImGuiCol_Button, active_bg);
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, active_bg);
        ImGui::PushStyleColor(ImGuiCol_ButtonActive, active_bg);
    } else {
        ImGui::PushStyleColor(ImGuiCol_Button, normal_bg);
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, hover_bg);
        ImGui::PushStyleColor(ImGuiCol_ButtonActive, hover_bg);
    }

    /* Left accent bar for active tab */
    if (active) {
        ImVec2 pos = ImGui::GetCursorScreenPos();
        ImDrawList *dl = ImGui::GetWindowDrawList();
        dl->AddRectFilled(pos, ImVec2(pos.x + 3, pos.y + btn_size.y), ImGui::ColorConvertFloat4ToU32(active_accent));
    }

    bool clicked = ImGui::Button(icon, btn_size);

    /* Active icon color */
    if (active) {
        ImGui::PopStyleColor(3);
        /* Re-tint the icon text by drawing over it */
    } else {
        ImGui::PopStyleColor(3);
    }

    if (tooltip && ImGui::IsItemHovered()) {
        ImGui::SetTooltip("%s", tooltip);
    }

    return clicked;
}

void render_activity_rail(GuiState *state, EventBus *bus) {
    if (!state->show_activity_rail) return;

    ImGuiViewport *vp = ImGui::GetMainViewport();
    float rail_w = 44.0f;
    float menu_h = 20.0f;  /* menu bar height */
    float status_h = state->show_statusbar ? 24.0f : 0.0f;

    ImVec2 pos = ImVec2(vp->WorkPos.x, vp->WorkPos.y + menu_h);
    ImVec2 size = ImVec2(rail_w, vp->WorkSize.y - menu_h - status_h);

    ImGui::SetNextWindowPos(pos);
    ImGui::SetNextWindowSize(size);

    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(4, 6));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(0, 4));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.10f, 0.10f, 0.13f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.0f, 0.0f, 0.0f, 0.0f));

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDocking |
                             ImGuiWindowFlags_NoTitleBar |
                             ImGuiWindowFlags_NoCollapse |
                             ImGuiWindowFlags_NoResize |
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoScrollbar |
                             ImGuiWindowFlags_NoScrollWithMouse |
                             ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_NoBringToFrontOnFocus |
                             ImGuiWindowFlags_NoNavFocus;

    ImGui::Begin("##ActivityRail", NULL, flags);

    /* Top icons — panel selectors */
    for (int i = 0; i < rail_tab_count; i++) {
        bool is_active = (state->active_rail_tab == i);
        if (rail_icon_button(rail_tabs[i].icon, is_active, rail_tabs[i].tooltip)) {
            state->active_rail_tab = i;
            /* Toggle the corresponding panel */
            switch (i) {
                case 0: state->show_events = !state->show_events; break;
                case 1: state->show_graph = !state->show_graph; break;
                case 2: state->show_ai = !state->show_ai; break;
                case 3: state->show_console = !state->show_console; break;
                case 4: state->show_profiler = !state->show_profiler; break;
                case 5: state->show_memory = !state->show_memory; break;
            }
            show_notification(state, rail_tabs[i].tooltip);
        }
    }

    /* Spacer to push bottom icons down */
    float used = rail_tab_count * (36.0f + 4.0f) + 12.0f;
    float avail = size.y - used - 80.0f;
    if (avail > 0) ImGui::Dummy(ImVec2(0, avail));

    /* Separator before bottom icons */
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 sep_pos = ImGui::GetCursorScreenPos();
    dl->AddLine(sep_pos, ImVec2(sep_pos.x + rail_w - 8, sep_pos.y), IM_COL32(60, 60, 70, 200));
    ImGui::Dummy(ImVec2(0, 8));

    /* Bottom icons — settings, appearance, shortcuts */
    if (rail_icon_button("\xE2\x9A\x99", state->show_settings, "Settings")) {
        state->show_settings = !state->show_settings;
    }
    if (rail_icon_button("\xE2\x97\x86", state->show_appearance, "Appearance & Layout")) {
        state->show_appearance = !state->show_appearance;
    }
    if (rail_icon_button("\xE2\x8C\x98", state->show_shortcuts, "Keyboard Shortcuts")) {
        state->show_shortcuts = !state->show_shortcuts;
    }

    ImGui::End();

    ImGui::PopStyleColor(2);
    ImGui::PopStyleVar(4);

    (void)bus;
}

/* ═══════════════════════════════════════════════════════════
 * RIGHT TOGGLE BAR — right-side vertical toggle bar
 * ═══════════════════════════════════════════════════════════ */

void render_right_bar(GuiState *state, EventBus *bus) {
    if (!state->show_right_bar) return;

    ImGuiViewport *vp = ImGui::GetMainViewport();
    float bar_w = 36.0f;
    float menu_h = 20.0f;
    float status_h = state->show_statusbar ? 24.0f : 0.0f;

    ImVec2 pos = ImVec2(vp->WorkPos.x + vp->WorkSize.x - bar_w, vp->WorkPos.y + menu_h);
    ImVec2 size = ImVec2(bar_w, vp->WorkSize.y - menu_h - status_h);

    ImGui::SetNextWindowPos(pos);
    ImGui::SetNextWindowSize(size);

    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(4, 6));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(0, 4));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.10f, 0.10f, 0.13f, 1.0f));
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.0f, 0.0f, 0.0f, 0.0f));

    ImGuiWindowFlags flags = ImGuiWindowFlags_NoDocking |
                             ImGuiWindowFlags_NoTitleBar |
                             ImGuiWindowFlags_NoCollapse |
                             ImGuiWindowFlags_NoResize |
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoScrollbar |
                             ImGuiWindowFlags_NoScrollWithMouse |
                             ImGuiWindowFlags_NoSavedSettings |
                             ImGuiWindowFlags_NoBringToFrontOnFocus |
                             ImGuiWindowFlags_NoNavFocus;

    ImGui::Begin("##RightBar", NULL, flags);

    /* Top toggles — Run/Pause, Docking, VSync */
    bool paused_active = state->paused;

    /* Run button */
    if (rail_icon_button("\xE2\x96\xB6", false, "Run Pipeline (Cmd+R)")) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Rail", "Run pipeline");
    }
    /* Pause button — highlighted when paused */
    if (rail_icon_button("\xE2\x8F\xB8", paused_active, paused_active ? "Resume (Cmd+P)" : "Pause (Cmd+P)")) {
        state->paused = !state->paused;
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Rail", state->paused ? "Paused" : "Resumed");
    }

    /* Separator */
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 sep_pos = ImGui::GetCursorScreenPos();
    dl->AddLine(sep_pos, ImVec2(sep_pos.x + bar_w - 8, sep_pos.y), IM_COL32(60, 60, 70, 200));
    ImGui::Dummy(ImVec2(0, 8));

    /* Toggle indicators */
    if (rail_icon_button("\xE2\x97\x89", state->docking, "Toggle Docking")) {
        state->docking = !state->docking;
        show_notification(state, state->docking ? "Docking enabled" : "Docking disabled");
    }
    if (rail_icon_button("\xE2\x97\x8B", state->vsync, "Toggle VSync")) {
        state->vsync = !state->vsync;
        show_notification(state, state->vsync ? "VSync enabled" : "VSync disabled");
    }
    if (rail_icon_button("\xE2\x96\xAD", state->show_statusbar, "Toggle Status Bar")) {
        state->show_statusbar = !state->show_statusbar;
    }
    if (rail_icon_button("\xE2\x97\x90", state->show_notifications, "Toggle Notifications")) {
        state->show_notifications = !state->show_notifications;
    }

    /* Spacer */
    float used = 6 * (36.0f + 4.0f) + 20.0f;
    float avail = size.y - used - 50.0f;
    if (avail > 0) ImGui::Dummy(ImVec2(0, avail));

    /* Bottom: fullscreen + about */
    if (rail_icon_button("\xE2\xA4\xA2", state->fullscreen, "Fullscreen (Cmd+Shift+F)")) {
        state->fullscreen = !state->fullscreen;
    }
    if (rail_icon_button("\xE2\x84\xb9", state->show_about, "About Cascade")) {
        state->show_about = !state->show_about;
    }

    ImGui::End();

    ImGui::PopStyleColor(2);
    ImGui::PopStyleVar(4);
}

/* ═══════════════════════════════════════════════════════════
 * APPEARANCE WINDOW — View > Appearance layout options
 * ═══════════════════════════════════════════════════════════ */

void render_appearance_window(GuiState *state) {
    if (!state->show_appearance) return;

    ImGui::SetNextWindowSize(ImVec2(380, 420), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Appearance", &state->show_appearance)) {
        ImGui::End();
        return;
    }

    /* --- Layout --- */
    if (ImGui::CollapsingHeader("Layout", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Text("Activity Rail (left)");
        ImGui::SameLine(180);
        ImGui::Checkbox("##rail_set", &state->show_activity_rail);

        ImGui::Text("Toggle Bar (right)");
        ImGui::SameLine(180);
        ImGui::Checkbox("##rbar_set", &state->show_right_bar);

        ImGui::Text("Status Bar (bottom)");
        ImGui::SameLine(180);
        ImGui::Checkbox("##sbar_set", &state->show_statusbar);

        ImGui::Text("Docking");
        ImGui::SameLine(180);
        ImGui::Checkbox("##dock_set", &state->docking);

        ImGui::Separator();

        ImGui::Text("Preset");
        ImGui::SameLine(180);
        const char *presets[] = { "Default", "Debug", "Profiling", "AI Focus", "Minimal" };
        if (ImGui::Combo("##app_preset", &state->layout_preset, presets, 5)) {
            apply_layout_preset(state, state->layout_preset);
        }

        if (ImGui::Button("Save Layout", ImVec2(110, 0))) {
            ImGui::SaveIniSettingsToDisk("cascade_layout.ini");
            show_notification(state, "Layout saved");
        }
        ImGui::SameLine();
        if (ImGui::Button("Reset Layout", ImVec2(110, 0))) {
            apply_layout_preset(state, 0);
            show_notification(state, "Layout reset");
        }
    }

    /* --- Theme --- */
    if (ImGui::CollapsingHeader("Theme", ImGuiTreeNodeFlags_DefaultOpen)) {
        const char *themes[] = { "Dark", "Light", "Classic", "Cascade Dark" };
        if (ImGui::Combo("Theme##app_theme", &state->theme, themes, 4)) {
            apply_theme(state->theme);
        }

        ImGui::SliderInt("Font Scale##app_font", &state->font_scale, 50, 200, "%d%%");
        if (ImGui::IsItemDeactivatedAfterEdit()) {
            apply_font_scale(state->font_scale);
        }
    }

    /* --- Panels --- */
    if (ImGui::CollapsingHeader("Panels")) {
        ImGui::Checkbox("Events##app_ev",   &state->show_events);   ImGui::SameLine(130);
        ImGui::Checkbox("Graph##app_gr",    &state->show_graph);
        ImGui::Checkbox("AI##app_ai",       &state->show_ai);       ImGui::SameLine(130);
        ImGui::Checkbox("Console##app_co",  &state->show_console);
        ImGui::Checkbox("Profiler##app_pr", &state->show_profiler); ImGui::SameLine(130);
        ImGui::Checkbox("Memory##app_me",   &state->show_memory);

        ImGui::Separator();
        if (ImGui::Button("Show All##app_all", ImVec2(90, 0))) {
            state->show_events = state->show_graph = state->show_ai = true;
            state->show_console = state->show_profiler = state->show_memory = true;
        }
        ImGui::SameLine();
        if (ImGui::Button("Hide All##app_none", ImVec2(90, 0))) {
            state->show_events = state->show_graph = state->show_ai = false;
            state->show_console = state->show_profiler = state->show_memory = false;
        }
    }

    /* --- Behavior --- */
    if (ImGui::CollapsingHeader("Behavior")) {
        ImGui::Checkbox("VSync##app_vsync", &state->vsync);
        ImGui::Checkbox("Notifications##app_notif", &state->show_notifications);
        ImGui::Checkbox("ImGui Demo##app_demo", &state->show_demo);
        ImGui::Checkbox("Metrics##app_metrics", &state->show_metrics);
    }

    ImGui::End();
}
