#include "gui.h"
#include "imgui.h"
#ifdef CASCADE_HAS_IMPLOT
#include "implot.h"
#endif
#include <string.h>

#define PROFILER_MAX_SECTIONS 64
#define PROFILER_HISTORY 256

typedef struct {
    char name[64];
    float times[PROFILER_HISTORY];
    int idx;
    int count;
    float last_ms;
    float avg_ms;
    float max_ms;
    int calls;
} ProfilerSection;

static ProfilerSection sections[PROFILER_MAX_SECTIONS];
static int section_count = 0;
static bool profiler_paused = false;

static ProfilerSection *find_or_create_section(const char *name) {
    for (int i = 0; i < section_count; i++) {
        if (strcmp(sections[i].name, name) == 0) return &sections[i];
    }
    if (section_count >= PROFILER_MAX_SECTIONS) return NULL;
    ProfilerSection *s = &sections[section_count++];
    strncpy(s->name, name, sizeof(s->name) - 1);
    s->name[sizeof(s->name) - 1] = '\0';
    s->idx = 0;
    s->count = 0;
    s->last_ms = 0;
    s->avg_ms = 0;
    s->max_ms = 0;
    s->calls = 0;
    return s;
}

void profiler_record(const char *section, float ms) {
    if (profiler_paused) return;
    ProfilerSection *s = find_or_create_section(section);
    if (!s) return;
    s->times[s->idx] = ms;
    s->idx = (s->idx + 1) % PROFILER_HISTORY;
    if (s->count < PROFILER_HISTORY) s->count++;
    s->last_ms = ms;
    s->calls++;
    if (ms > s->max_ms) s->max_ms = ms;
    float sum = 0;
    for (int i = 0; i < s->count; i++) sum += s->times[i];
    s->avg_ms = sum / s->count;
}

void panel_profiler_render(GuiState *state, EventBus *bus) {
    if (!state->show_profiler) return;
    if (!ImGui::Begin("Profiler", &state->show_profiler)) { ImGui::End(); return; }

    if (ImGui::Button(profiler_paused ? "Resume" : "Pause")) {
        profiler_paused = !profiler_paused;
    }
    ImGui::SameLine();
    if (ImGui::Button("Reset")) {
        section_count = 0;
    }
    ImGui::SameLine();
    ImGui::Text("Sections: %d", section_count);

    ImGui::Separator();

    /* Table */
    ImGuiTableFlags flags = ImGuiTableFlags_ScrollY | ImGuiTableFlags_RowBg |
                            ImGuiTableFlags_BordersOuter | ImGuiTableFlags_BordersV |
                            ImGuiTableFlags_Resizable | ImGuiTableFlags_Sortable;

    if (ImGui::BeginTable("profiler_table", 5, flags)) {
        ImGui::TableSetupColumn("Section", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Last (ms)", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Avg (ms)", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Max (ms)", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Calls", ImGuiTableColumnFlags_WidthFixed, 60);
        ImGui::TableHeadersRow();

        for (int i = 0; i < section_count; i++) {
            ProfilerSection *s = &sections[i];
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::TextUnformatted(s->name);
            ImGui::TableSetColumnIndex(1);
            ImGui::Text("%.3f", s->last_ms);
            ImGui::TableSetColumnIndex(2);
            float avg_color = s->avg_ms > 16.0f ? 0.9f : (s->avg_ms > 8.0f ? 0.8f : 0.4f);
            ImGui::TextColored(ImVec4(avg_color, 0.8f, 0.4f, 1.0f), "%.3f", s->avg_ms);
            ImGui::TableSetColumnIndex(3);
            ImGui::TextColored(ImVec4(0.9f, 0.4f, 0.4f, 1.0f), "%.3f", s->max_ms);
            ImGui::TableSetColumnIndex(4);
            ImGui::TextDisabled("%d", s->calls);
        }
        ImGui::EndTable();
    }

#ifdef CASCADE_HAS_IMPLOT
    /* Per-section timeline */
    if (section_count > 0 && ImPlot::BeginPlot("Section Timelines", ImVec2(-1, 150))) {
        ImPlot::SetupAxes("Samples", "ms");
        for (int i = 0; i < section_count; i++) {
            ProfilerSection *s = &sections[i];
            if (s->count > 1) {
                ImPlot::PlotLine(s->name, s->times, s->count);
            }
        }
        ImPlot::EndPlot();
    }
#endif

    /* Simulated profiling data for demo */
    static double last = 0;
    double now = ImGui::GetTime();
    if (!profiler_paused && now - last > 0.1) {
        last = now;
        ImGuiIO &io = ImGui::GetIO();
        profiler_record("Render", (float)(1000.0 / io.Framerate));
        profiler_record("EventBus", (float)(event_bus_count(bus) % 10) * 0.01f);
        profiler_record("ImGui", io.MetricsRenderWindows * 0.05f);
        profiler_record("Input", 0.1f + (float)(now * 0.001));
    }

    ImGui::End();
}
