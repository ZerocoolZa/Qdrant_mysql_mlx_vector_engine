#include "gui.h"
#include "imgui.h"

void gui_state_init(GuiState *state) {
    state->show_events = true;
    state->show_graph = true;
    state->show_ai = true;
    state->show_console = true;
    state->show_profiler = true;
    state->show_memory = true;
    state->show_demo = false;
    state->show_about = false;
    state->show_metrics = false;
    state->show_style_editor = false;
    state->show_shortcuts = false;
    state->show_settings = false;
    state->show_statusbar = true;
    state->fullscreen = true;
    state->docking = true;
    state->vsync = true;
    state->paused = false;
    state->theme = 3;
    state->font_scale = 100;
    state->search_filter[0] = '\0';
    state->selected_channel = -1;
    state->selected_level = -1;
    state->layout_preset = 0;
    state->show_notifications = true;
    state->notification_text[0] = '\0';
    state->notification_timer = 0.0f;
    state->show_activity_rail = true;
    state->show_right_bar = true;
    state->active_rail_tab = 0;
    state->show_appearance = false;
}
