#include "gui.h"
#include "imgui.h"
#include "ai/ai_bridge.h"
#include <string.h>

static char ai_input[4096];
static char ai_output[8192];
static bool ai_thinking = false;
static float ai_confidence = 0.0f;
static char ai_model[64] = "cascade-local";
static int ai_temperature = 50;

void panel_ai_render(GuiState *state, EventBus *bus) {
    if (!state->show_ai) return;
    if (!ImGui::Begin("AI", &state->show_ai)) { ImGui::End(); return; }

    /* Model selector */
    ImGui::TextDisabled("Model:");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(150);
    const char *models[] = { "cascade-local", "gpt-4", "claude-3", "devin", "custom" };
    ImGui::Combo("##model", (int *)&ai_model[0], models, IM_ARRAYSIZE(models));

    ImGui::SameLine();
    ImGui::TextDisabled("Temp:");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(80);
    ImGui::SliderInt("##temp", &ai_temperature, 0, 100, "%d%%");

    ImGui::Separator();

    /* Output area */
    ImGui::BeginChild("ai_output", ImVec2(0, -80), true);
    if (ai_output[0] != '\0') {
        ImGui::TextUnformatted(ai_output);
    } else {
        ImGui::TextDisabled("AI output will appear here...");
    }
    if (ai_thinking) {
        ImGui::TextColored(ImVec4(0.4f, 0.6f, 1.0f, 1.0f), " [thinking...]");
    }
    ImGui::EndChild();

    /* Input bar */
    ImGui::PushItemWidth(-100);
    bool enter = ImGui::InputTextWithHint("##ai_input", "Ask AI anything...", ai_input, sizeof(ai_input),
                                           ImGuiInputTextFlags_EnterReturnsTrue);
    ImGui::PopItemWidth();
    ImGui::SameLine();
    if (ImGui::Button("Send", ImVec2(80, 0)) || enter) {
        if (ai_input[0] != '\0') {
            ai_thinking = true;
            event_bus_publish(bus, CH_AI, EV_INFO, "AI", ai_input);
            const char *response = ai_bridge_query(ai_input, ai_model, (float)ai_temperature / 100.0f);
            if (response) {
                size_t remaining = sizeof(ai_output) - strlen(ai_output) - 1;
                strncat(ai_output, response, remaining);
                ai_confidence = ai_bridge_last_confidence();
            }
            ai_thinking = false;
            ai_input[0] = '\0';
        }
    }

    ImGui::Separator();
    ImGui::Text("Confidence: %.1f%%  |  Model: %s  |  Status: %s",
                ai_confidence * 100.0f, ai_model, ai_thinking ? "Thinking" : "Idle");

    if (ImGui::Button("Clear Output")) {
        ai_output[0] = '\0';
    }
    ImGui::SameLine();
    if (ImGui::Button("Export Conversation")) {
        event_bus_publish(bus, CH_AI, EV_INFO, "AI", "Export conversation requested");
    }

    ImGui::End();
}
