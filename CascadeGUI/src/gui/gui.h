#ifndef CASCADE_GUI_H
#define CASCADE_GUI_H

#include "event_bus.h"
#include <stdbool.h>

typedef struct {
    bool show_events;
    bool show_graph;
    bool show_ai;
    bool show_console;
    bool show_profiler;
    bool show_memory;
    bool show_demo;
    bool show_about;
    bool show_metrics;
    bool show_style_editor;
    bool show_shortcuts;
    bool show_settings;
    bool show_statusbar;
    bool fullscreen;
    bool docking;
    bool vsync;
    bool paused;
    int theme;
    int font_scale;
    char search_filter[256];
    int selected_channel;
    int selected_level;
    int layout_preset;
    bool show_notifications;
    char notification_text[256];
    float notification_timer;
    bool show_activity_rail;
    bool show_right_bar;
    int active_rail_tab;
    bool show_appearance;
} GuiState;

void gui_state_init(GuiState *state);

void window_main_init(void);
void window_main_render(GuiState *state, EventBus *bus);
void window_main_shutdown(void);

void render_menubar(GuiState *state, EventBus *bus);
void render_toolbar(GuiState *state, EventBus *bus);
void render_hotkeys(GuiState *state, EventBus *bus);
void apply_theme(int theme_id);
void apply_font_scale(int scale);

void panel_events_render(GuiState *state, EventBus *bus);
void panel_graph_render(GuiState *state, EventBus *bus);
void panel_ai_render(GuiState *state, EventBus *bus);
void panel_console_render(GuiState *state, EventBus *bus);
void panel_profiler_render(GuiState *state, EventBus *bus);
void panel_memory_render(GuiState *state, EventBus *bus);

/* New: status bar, shortcuts, settings, context menu, layout, notifications */
void render_statusbar(GuiState *state, EventBus *bus);
void render_shortcuts_window(GuiState *state);
void render_settings_panel(GuiState *state, EventBus *bus);
void render_dockspace_context_menu(GuiState *state);
void apply_layout_preset(GuiState *state, int preset);
void render_notification(GuiState *state);
void show_notification(GuiState *state, const char *text);

/* Activity rail (left) and toggle bar (right) */
void render_activity_rail(GuiState *state, EventBus *bus);
void render_right_bar(GuiState *state, EventBus *bus);
void render_appearance_window(GuiState *state);

/* Toolbar helpers (implemented in toolbar.c) */
namespace ImGui {
    bool BeginToolbar(const char *id);
    void EndToolbar(void);
    bool ToolbarButton(const char *label, const char *tooltip);
    void ToolbarSeparator(void);
}

/* Utility (implemented in toolbar.c) */
const char *size_str(uint64_t bytes);

/* Profiler API (implemented in panel_profiler.c) */
void profiler_record(const char *section, float ms);

#endif
