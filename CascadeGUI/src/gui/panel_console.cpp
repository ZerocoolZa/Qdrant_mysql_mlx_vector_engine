#include "gui.h"
#include "imgui.h"
#include <string.h>
#include <stdio.h>

static char console_input[1024];
static char console_history[8192];
static int scroll_lines = 0;

/* Simple command processor */
static void process_command(const char *cmd, EventBus *bus) {
    char line[1280];

    snprintf(line, sizeof(line), "] %s", cmd);
    size_t remaining = sizeof(console_history) - strlen(console_history) - 1;
    strncat(console_history, line, remaining);
    remaining = sizeof(console_history) - strlen(console_history) - 1;
    strncat(console_history, "\n", remaining);

    if (strncmp(cmd, "help", 4) == 0) {
        const char *help =
            "Commands:\n"
            "  help          - Show this help\n"
            "  clear         - Clear console\n"
            "  events        - Show event count\n"
            "  pub <ch> <msg>- Publish event\n"
            "  pause         - Pause EventBus\n"
            "  resume        - Resume EventBus\n"
            "  status        - System status\n";
        remaining = sizeof(console_history) - strlen(console_history) - 1;
        strncat(console_history, help, remaining);
    } else if (strncmp(cmd, "clear", 5) == 0) {
        console_history[0] = '\0';
    } else if (strncmp(cmd, "events", 6) == 0) {
        snprintf(line, sizeof(line), "Events: %llu  Dropped: %llu\n",
                 (unsigned long long)event_bus_count(bus),
                 (unsigned long long)event_bus_dropped(bus));
        remaining = sizeof(console_history) - strlen(console_history) - 1;
        strncat(console_history, line, remaining);
    } else if (strncmp(cmd, "pub ", 4) == 0) {
        event_bus_publish(bus, CH_USER, EV_INFO, "Console", cmd + 4);
        remaining = sizeof(console_history) - strlen(console_history) - 1;
        strncat(console_history, "Published.\n", remaining);
    } else if (strncmp(cmd, "status", 6) == 0) {
        ImGuiIO &io = ImGui::GetIO();
        snprintf(line, sizeof(line),
                 "FPS: %.1f  Windows: %d  Verts: %d  Events: %llu\n",
                 io.Framerate, io.MetricsActiveWindows,
                 io.MetricsRenderVertices,
                 (unsigned long long)event_bus_count(bus));
        remaining = sizeof(console_history) - strlen(console_history) - 1;
        strncat(console_history, line, remaining);
    } else if (cmd[0] != '\0') {
        snprintf(line, sizeof(line), "Unknown command: %s\n", cmd);
        remaining = sizeof(console_history) - strlen(console_history) - 1;
        strncat(console_history, line, remaining);
    }
}

void panel_console_render(GuiState *state, EventBus *bus) {
    if (!state->show_console) return;
    if (!ImGui::Begin("Console", &state->show_console)) { ImGui::End(); return; }

    /* Console output */
    ImGui::BeginChild("console_output", ImVec2(0, -40), true);
    if (console_history[0] != '\0') {
        ImGui::TextUnformatted(console_history);
    } else {
        ImGui::TextDisabled("Type 'help' for commands...");
    }
    ImGui::SetScrollHereY(1.0f);
    ImGui::EndChild();

    /* Input */
    ImGui::PushItemWidth(-80);
    bool enter = ImGui::InputTextWithHint("##console_input", "Enter command...",
                                           console_input, sizeof(console_input),
                                           ImGuiInputTextFlags_EnterReturnsTrue);
    ImGui::PopItemWidth();
    ImGui::SameLine();
    if (ImGui::Button("Run", ImVec2(60, 0)) || enter) {
        if (console_input[0] != '\0') {
            process_command(console_input, bus);
            console_input[0] = '\0';
        }
    }

    ImGui::End();
}
