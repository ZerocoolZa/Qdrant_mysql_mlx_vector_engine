#include "gui.h"
#include "imgui.h"

void render_hotkeys(GuiState *state, EventBus *bus) {
    ImGuiIO &io = ImGui::GetIO();

    bool cmd = io.KeySuper;
    bool shift = io.KeyShift;

    if (cmd && ImGui::IsKeyPressed(ImGuiKey_N) && !shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "New session");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_O) && !shift) {
        event_bus_publish(bus, CH_FILE, EV_INFO, "Hotkey", "Open project");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_S) && !shift) {
        ImGui::SaveIniSettingsToDisk("cascade_layout.ini");
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Layout saved");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_S) && shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Screenshot");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_E) && !shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Export events");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_Q) && !shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Quit");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_Z) && !shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_DEBUG, "Hotkey", "Undo");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_Z) && shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_DEBUG, "Hotkey", "Redo");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_K) && !shift) {
        event_bus_clear(bus);
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Events cleared");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_R) && !shift) {
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey", "Run pipeline");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_G) && !shift) {
        event_bus_publish(bus, CH_GRAPH, EV_INFO, "Hotkey", "Graph analysis");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_I) && !shift) {
        event_bus_publish(bus, CH_AI, EV_INFO, "Hotkey", "AI query");
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_P) && !shift) {
        state->paused = !state->paused;
        event_bus_publish(bus, CH_SYSTEM, EV_INFO, "Hotkey",
                          state->paused ? "Paused" : "Resumed");
    }

    if (cmd && !shift) {
        if (ImGui::IsKeyPressed(ImGuiKey_1)) state->show_events = !state->show_events;
        if (ImGui::IsKeyPressed(ImGuiKey_2)) state->show_graph = !state->show_graph;
        if (ImGui::IsKeyPressed(ImGuiKey_3)) state->show_ai = !state->show_ai;
        if (ImGui::IsKeyPressed(ImGuiKey_4)) state->show_console = !state->show_console;
        if (ImGui::IsKeyPressed(ImGuiKey_5)) state->show_profiler = !state->show_profiler;
        if (ImGui::IsKeyPressed(ImGuiKey_6)) state->show_memory = !state->show_memory;
    }

    if (cmd && shift && ImGui::IsKeyPressed(ImGuiKey_F)) {
        state->fullscreen = !state->fullscreen;
    }
    if (cmd && shift && ImGui::IsKeyPressed(ImGuiKey_A)) {
        state->show_about = !state->show_about;
    }
    if (cmd && ImGui::IsKeyPressed(ImGuiKey_Slash)) {
        state->show_shortcuts = !state->show_shortcuts;
    }
}
