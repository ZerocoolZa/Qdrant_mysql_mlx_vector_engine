#include "gui.h"
#include "imgui.h"
#ifdef CASCADE_HAS_IMPLOT
#include "implot.h"
#endif
#include <math.h>
#include <string.h>

#define GRAPH_HISTORY 512

static float fps_history[GRAPH_HISTORY];
static float cpu_history[GRAPH_HISTORY];
static float mem_history[GRAPH_HISTORY];
static float event_rate_history[GRAPH_HISTORY];
static int history_idx = 0;
static int history_count = 0;

static double last_time = 0.0;
static double frame_times[60];
static int frame_idx = 0;

static void push_history(float fps, float cpu, float mem, float ev_rate) {
    fps_history[history_idx] = fps;
    cpu_history[history_idx] = cpu;
    mem_history[history_idx] = mem;
    event_rate_history[history_idx] = ev_rate;
    history_idx = (history_idx + 1) % GRAPH_HISTORY;
    if (history_count < GRAPH_HISTORY) history_count++;
}

void panel_graph_render(GuiState *state, EventBus *bus) {
    if (!state->show_graph) return;
    if (!ImGui::Begin("Graph", &state->show_graph)) { ImGui::End(); return; }

    ImGuiIO &io = ImGui::GetIO();
    double now = ImGui::GetTime();
    double dt = now - last_time;
    last_time = now;

    frame_times[frame_idx] = dt;
    frame_idx = (frame_idx + 1) % 60;

    double avg_dt = 0;
    for (int i = 0; i < 60; i++) avg_dt += frame_times[i];
    avg_dt /= 60.0;
    float fps = (float)(1.0 / avg_dt);

    static double last_push = 0;
    if (now - last_push > 0.1) {
        float cpu = (float)(avg_dt * 100.0);
        float mem_mb = (float)(io.MetricsRenderVertices / 1024.0);
        float ev_rate = (float)event_bus_count(bus) / (float)(now + 1.0) * 100.0f;
        push_history(fps, cpu, mem_mb, ev_rate);
        last_push = now;
    }

#ifdef CASCADE_HAS_IMPLOT
    if (ImPlot::BeginPlot("Performance", ImVec2(-1, 200), ImPlotFlags_Crosshairs)) {
        ImPlot::SetupAxes("Frames", "Value");
        ImPlot::SetupAxisLimits(ImAxis_X1, 0, GRAPH_HISTORY);
        ImPlot::SetupAxisLimits(ImAxis_Y1, 0, 120);

        if (history_count > 1) {
            int start = (history_idx - history_count + GRAPH_HISTORY) % GRAPH_HISTORY;
            ImPlot::PlotLine("FPS", fps_history + start, history_count);
            ImPlot::PlotLine("CPU%", cpu_history + start, history_count);
            ImPlot::PlotLine("Events/s", event_rate_history + start, history_count);
        }
        ImPlot::EndPlot();
    }

    if (ImPlot::BeginPlot("Memory (MB)", ImVec2(-1, 150), ImPlotFlags_Crosshairs)) {
        ImPlot::SetupAxes("Frames", "MB");
        if (history_count > 1) {
            int start = (history_idx - history_count + GRAPH_HISTORY) % GRAPH_HISTORY;
            ImPlot::PlotLine("Memory", mem_history + start, history_count);
        }
        ImPlot::EndPlot();
    }
#else
    ImGui::Text("FPS: %.1f", fps);
    ImGui::Text("Frame time: %.2f ms", avg_dt * 1000.0);
    ImGui::Text("Events in bus: %llu", (unsigned long long)event_bus_count(bus));
    ImGui::Text("Dropped: %llu", (unsigned long long)event_bus_dropped(bus));
    ImGui::Separator();
    ImGui::TextDisabled("Install ImPlot for live graphs (ENABLE_IMPLOT=ON)");
    /* Fallback: simple text-based sparkline */
    if (history_count > 0) {
        char spark[64];
        int step = history_count / 60;
        if (step < 1) step = 1;
        int j = 0;
        for (int i = 0; i < history_count && j < 60; i += step, j++) {
            int idx = (history_idx - history_count + i + GRAPH_HISTORY) % GRAPH_HISTORY;
            float v = fps_history[idx];
            int h = (int)(v / 120.0 * 8.0);
            if (h < 0) h = 0; if (h > 7) h = 7;
            const char *blocks[] = {" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"};
            spark[j] = 0;
            // Simple ASCII bar
        }
    }
#endif

    ImGui::Separator();
    ImGui::Text("Frame: %d  Windows: %d  Verts: %d  Cmds: %d",
                io.Framerate > 0 ? (int)io.Framerate : 0,
                io.MetricsRenderWindows,
                io.MetricsRenderVertices,
                io.MetricsRenderIndices / 3);

    ImGui::End();
}
