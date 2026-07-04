#include "gui.h"
#include "imgui.h"
#include <stdio.h>
#include <string.h>

/* --- Toolbar helpers (ImGui has no built-in toolbar) --- */

static bool s_in_toolbar = false;

bool ImGui::BeginToolbar(const char *id) {
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse |
                             ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoTitleBar |
                             ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove;
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(4, 4));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(4, 4));
    bool visible = ImGui::Begin(id, NULL, flags);
    s_in_toolbar = visible;
    return visible;
}

void ImGui::EndToolbar(void) {
    if (s_in_toolbar) {
        ImGui::End();
    }
    s_in_toolbar = false;
    ImGui::PopStyleVar(2);
}

bool ImGui::ToolbarButton(const char *label, const char *tooltip) {
    bool clicked = ImGui::Button(label, ImVec2(0, 0));
    if (tooltip && ImGui::IsItemHovered()) {
        ImGui::SetTooltip("%s", tooltip);
    }
    return clicked;
}

void ImGui::ToolbarSeparator(void) {
    ImGui::SameLine();
    ImGui::Dummy(ImVec2(2, 0));
    ImGui::SameLine();
    ImGui::Separator();
    ImGui::SameLine();
}

/* --- size_str helper for memory panel --- */
const char *size_str(uint64_t bytes) {
    static char buf[32];
    if (bytes < 1024) snprintf(buf, sizeof(buf), "%llu B", (unsigned long long)bytes);
    else if (bytes < 1024 * 1024) snprintf(buf, sizeof(buf), "%.1f KB", bytes / 1024.0);
    else if (bytes < 1024ULL * 1024 * 1024) snprintf(buf, sizeof(buf), "%.1f MB", bytes / (1024.0 * 1024));
    else snprintf(buf, sizeof(buf), "%.2f GB", bytes / (1024.0 * 1024 * 1024));
    return buf;
}

void render_toolbar(GuiState *state, EventBus *bus) {
    if (!ImGui::BeginToolbar("MainToolbar")) return;

    if (ImGui::ToolbarButton("Run", "Cmd+R")) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Toolbar", "Run clicked");
    }
    if (ImGui::ToolbarButton("Pause", "Cmd+P")) {
        state->paused = !state->paused;
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Toolbar",
                          state->paused ? "Paused" : "Resumed");
    }
    ImGui::ToolbarSeparator();
    if (ImGui::ToolbarButton("Events", "Cmd+1")) { state->show_events = !state->show_events; }
    if (ImGui::ToolbarButton("Graph", "Cmd+2")) { state->show_graph = !state->show_graph; }
    if (ImGui::ToolbarButton("AI", "Cmd+3")) { state->show_ai = !state->show_ai; }
    if (ImGui::ToolbarButton("Console", "Cmd+4")) { state->show_console = !state->show_console; }
    if (ImGui::ToolbarButton("Profiler", "Cmd+5")) { state->show_profiler = !state->show_profiler; }
    if (ImGui::ToolbarButton("Memory", "Cmd+6")) { state->show_memory = !state->show_memory; }
    ImGui::ToolbarSeparator();
    if (ImGui::ToolbarButton("Clear", "Cmd+K")) {
        event_bus_clear(bus);
    }
    if (ImGui::ToolbarButton("Export", "Cmd+E")) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Toolbar", "Export clicked");
    }
    if (ImGui::ToolbarButton("Settings", "Open settings panel")) {
        state->show_settings = !state->show_settings;
    }
    ImGui::ToolbarSeparator();

    ImGui::SetNextItemWidth(200);
    ImGui::InputTextWithHint("##search", "Search events...", state->search_filter, sizeof(state->search_filter));

    ImGui::SameLine();
    const char *channels[] = { "All", "SYSTEM", "AI", "GRAPH", "PROFILER", "MEMORY",
                               "CONSOLE", "FILE", "NETWORK", "USER", "ERROR" };
    ImGui::SetNextItemWidth(100);
    ImGui::Combo("##channel", &state->selected_channel, channels, IM_ARRAYSIZE(channels));

    ImGui::SameLine();
    const char *levels[] = { "All", "INFO", "WARN", "ERROR", "DEBUG", "TRACE" };
    ImGui::SetNextItemWidth(80);
    ImGui::Combo("##level", &state->selected_level, levels, IM_ARRAYSIZE(levels));

    ImGui::SameLine();
    ImGui::Text("Events: %llu  Dropped: %llu",
                (unsigned long long)event_bus_count(bus),
                (unsigned long long)event_bus_dropped(bus));

    if (state->paused) {
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(0.9f, 0.8f, 0.2f, 1.0f), " [PAUSED]");
    }

    ImGui::EndToolbar();
}
