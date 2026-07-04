//[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_vpa.cpp" date="2026-07-04" author="Devin" session_id="bloodhound-vpa" context="Bloodhound VPA implementation — ImPlot live performance graphs, ImNodes interactive execution graph, ImGuiColorTextEdit syntax-highlighted Python editor, AI reasoning graph. Uses new ImPlot v1.0 ImPlotSpec API."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE implot-v1 imnodes colortextedit"}
//[@FILEID]{id="bloodhound_vpa.cpp" domain="dom_bloodhound" authority="BloodhoundVPA"}
//[@SUMMARY]{summary="Bloodhound VPA — Visual Performance & Analysis with ImPlot v1.0 ImPlotSpec API, ImNodes, TextEditor."}
//[@CLASS]{class="BloodhoundVPA" domain="dom_bloodhound" authority="single"}

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include <time.h>

#define IMGUI_DEFINE_MATH_OPERATORS
#include "imgui.h"
#include "imgui_internal.h"
#include "implot.h"
#include "imnodes.h"
#include "TextEditor.h"

#include "bloodhound_vpa.h"

// Event kinds
enum { KIND_STEP = 1, KIND_RESULT = 2, KIND_ERROR = 3, KIND_VAR = 4,
       KIND_STATE = 5, KIND_TIMING = 6, KIND_IMPORT = 7,
       KIND_CALL = 8, KIND_RETURN = 9, KIND_FIX = 10 };

enum { VAL_NULL=0, VAL_INT=1, VAL_FLOAT=2, VAL_STRING=3, VAL_BOOL=4 };

typedef struct {
    uint8_t type;
    union { int64_t i64; double f64; bool b; } num;
    char str[64];
} vpa_value_t;

typedef struct {
    uint64_t    id;
    uint64_t    timestamp_ns;
    uint16_t    kind;
    uint16_t    severity;
    uint16_t    source;
    uint16_t    phase;
    uint32_t    entity;
    uint32_t    name;
    vpa_value_t value;
    uint64_t    parent_id;
    int         source_line;
} vpa_event_t;

#define VPA_MAX_EVENTS    100000
#define VPA_MAX_SOURCES   256
#define VPA_HISTORY_LEN   256

typedef struct {
    vpa_event_t  events[VPA_MAX_EVENTS];
    size_t       count;
    uint64_t     next_id;
    uint64_t     count_by_kind[16];
    uint64_t     error_count;
    uint64_t     total_events;
    double       timing_total_ms;
    double       timing_min_ms;
    double       timing_max_ms;
    uint64_t     timing_count;
    bool         seen_source[VPA_MAX_SOURCES];
    int          source_count;
} vpa_bus_t;

extern char     *g_interned[];
extern uint32_t  g_intern_count;

static const char* vpa_str_lookup(uint32_t id) {
    return (id < g_intern_count && g_interned[id]) ? g_interned[id] : "?";
}

static const char* vpa_kind_name(uint16_t k) {
    static const char *names[] = {
        "?","step","result","error","variable","state","timing","import","call","return","fix"
    };
    return k < 11 ? names[k] : "?";
}

static ImVec4 ColV4(ImU32 col) {
    return ImVec4(
        (float)((col >> IM_COL32_R_SHIFT) & 0xFF) / 255.0f,
        (float)((col >> IM_COL32_G_SHIFT) & 0xFF) / 255.0f,
        (float)((col >> IM_COL32_B_SHIFT) & 0xFF) / 255.0f,
        (float)((col >> IM_COL32_A_SHIFT) & 0xFF) / 255.0f
    );
}

// VPA state
static struct {
    float fps_history[VPA_HISTORY_LEN];
    float event_rate_history[VPA_HISTORY_LEN];
    float memory_history[VPA_HISTORY_LEN];
    float timing_history[VPA_HISTORY_LEN];
    int   history_pos;
    int   history_count;
    bool  nodes_initialized;
    int   node_selected;
    TextEditor *editor;
    bool  editor_initialized;
    bool  editor_loaded;
} vpa;

void VPA_Init(void) {
    memset(&vpa, 0, sizeof(vpa));
    ImNodes::CreateContext();
    vpa.editor = new TextEditor();
    vpa.editor_initialized = true;
    vpa.nodes_initialized = true;
}

void VPA_Shutdown(void) {
    if (vpa.editor_initialized) { delete vpa.editor; vpa.editor = nullptr; vpa.editor_initialized = false; }
    if (vpa.nodes_initialized) { ImNodes::DestroyContext(); vpa.nodes_initialized = false; }
}

static void vpa_update_history(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    int pos = vpa.history_pos;
    vpa.fps_history[pos] = ImGui::GetIO().Framerate;
    vpa.event_rate_history[pos] = (float)bus->total_events;
    vpa.memory_history[pos] = (float)(bus->count * sizeof(vpa_event_t)) / (1024.0f * 1024.0f);
    vpa.timing_history[pos] = (float)(bus->timing_count > 0 ? bus->timing_total_ms / bus->timing_count : 0.0);
    vpa.history_pos = (pos + 1) % VPA_HISTORY_LEN;
    if (vpa.history_count < VPA_HISTORY_LEN) vpa.history_count++;
}

// Helper to create ImPlotSpec with line color and weight
static ImPlotSpec SpecLine(ImU32 color, float weight = 2.0f, int flags = 0) {
    ImPlotSpec spec;
    spec.LineColor = ColV4(color);
    spec.LineWeight = weight;
    spec.Flags = flags;
    return spec;
}

static ImPlotSpec SpecLineFill(ImU32 color, float weight = 2.0f, int flags = 0) {
    ImPlotSpec spec;
    spec.LineColor = ColV4(color);
    spec.LineWeight = weight;
    spec.FillColor = ColV4(color);
    spec.FillAlpha = 0.3f;
    spec.Flags = flags | ImPlotLineFlags_Shaded;
    return spec;
}

// ═══════════════════════════════════════════════════════════
// LIVE DASHBOARD
// ═══════════════════════════════════════════════════════════

void VPA_RenderLiveDashboard(void *ide_ptr) {
    vpa_update_history(ide_ptr);
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;

    ImGui::Begin("Live Dashboard##vpa_dashboard");
    ImGui::TextColored(ColV4(IM_COL32(80,200,255,255)), "Real-Time Performance Dashboard");
    ImGui::Separator();

    if (ImPlot::BeginPlot("FPS & Events", ImVec2(-1, 200))) {
        ImPlot::SetupAxes("Frame", "Value");
        ImPlot::SetupAxisLimits(ImAxis_Y1, 0, 120);
        ImPlot::PlotLine("FPS", vpa.fps_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLine(IM_COL32(80,255,120,255)));
        ImPlot::PlotLine("Events", vpa.event_rate_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLine(IM_COL32(80,200,255,255)));
        ImPlot::EndPlot();
    }

    ImGui::Separator();

    if (ImPlot::BeginPlot("Memory (MB)", ImVec2(-1, 150))) {
        ImPlot::SetupAxes("Frame", "MB");
        ImPlot::PlotLine("Memory", vpa.memory_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLineFill(IM_COL32(255,220,80,255)));
        ImPlot::EndPlot();
    }

    ImGui::Separator();

    if (ImPlot::BeginPlot("Avg Timing (ms)", ImVec2(-1, 150))) {
        ImPlot::SetupAxes("Frame", "ms");
        ImPlot::PlotLine("Timing", vpa.timing_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLine(IM_COL32(120,160,255,255)));
        ImPlot::EndPlot();
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// KIND DISTRIBUTION — Pie chart
// ═══════════════════════════════════════════════════════════

void VPA_RenderKindDistribution(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    ImGui::Begin("Event Distribution##vpa_dist");
    ImGui::TextColored(ColV4(IM_COL32(255,120,255,255)), "Event Kind Distribution");
    ImGui::Separator();

    if (bus->total_events == 0) { ImGui::TextDisabled("No events yet."); ImGui::End(); return; }

    const char* labels[] = {"step","result","error","variable","state","timing","import","call","return","fix"};
    double values[10];
    for (int i = 0; i < 10; i++) values[i] = (double)bus->count_by_kind[i+1];

    if (ImPlot::BeginPlot("##pie", ImVec2(-1, 300), ImPlotFlags_Equal)) {
        ImPlot::PlotPieChart(labels, values, 10, 0.5, 0.5, 0.4, "%.0f", true, 0);
        ImPlot::EndPlot();
    }

    ImGui::Separator();
    for (int i = 0; i < 10; i++) {
        if (bus->count_by_kind[i+1] == 0) continue;
        ImU32 col = IM_COL32(80+i*15, 200-i*10, 255-i*20, 255);
        ImGui::TextColored(ColV4(col), "%-10s %6llu  %.1f%%",
            vpa_kind_name(i+1), (unsigned long long)bus->count_by_kind[i+1],
            100.0 * bus->count_by_kind[i+1] / bus->total_events);
    }
    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// NODE GRAPH — ImNodes
// ═══════════════════════════════════════════════════════════

void VPA_RenderNodeGraph(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    ImGui::Begin("Node Graph##vpa_nodes");
    ImGui::TextColored(ColV4(IM_COL32(80,255,120,255)), "Interactive Execution Graph");
    ImGui::Separator();

    ImNodes::BeginNodeEditor();

    int node_id = 1, attr_id = 100;
    struct { int node, attr_in, attr_out; } nodes[64];
    int node_count = 0;

    for (uint16_t s = 0; s < VPA_MAX_SOURCES && node_count < 64; s++) {
        if (!bus->seen_source[s]) continue;
        int ev_count = 0, err_count = 0;
        for (size_t j = 0; j < bus->count; j++) {
            if (bus->events[j].source == s) { ev_count++; if (bus->events[j].severity >= 3) err_count++; }
        }

        ImNodes::BeginNode(node_id);
        ImNodes::BeginNodeTitleBar();
        ImGui::TextColored(err_count > 0 ? ColV4(IM_COL32(255,80,80,255)) : ColV4(IM_COL32(80,255,120,255)),
            "%s", vpa_str_lookup(s));
        ImNodes::EndNodeTitleBar();
        ImNodes::BeginInputAttribute(attr_id); ImGui::Text("in"); ImNodes::EndInputAttribute();
        ImGui::Text("  %d events", ev_count);
        if (err_count > 0) ImGui::TextColored(ColV4(IM_COL32(255,80,80,255)), "  %d errors", err_count);
        ImNodes::BeginOutputAttribute(attr_id + 1); ImGui::Text("out"); ImNodes::EndOutputAttribute();
        ImNodes::EndNode();

        nodes[node_count].node = node_id;
        nodes[node_count].attr_in = attr_id;
        nodes[node_count].attr_out = attr_id + 1;
        node_count++;
        node_id++; attr_id += 2;
    }

    for (int i = 0; i < node_count - 1; i++)
        ImNodes::Link(i + 1, nodes[i].attr_out, nodes[i+1].attr_in);

    ImNodes::EndNodeEditor();
    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// CODE EDITOR — ImGuiColorTextEdit
// ═══════════════════════════════════════════════════════════

void VPA_RenderCodeEditor(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    ImGui::Begin("Code Editor##vpa_editor", NULL, ImGuiWindowFlags_HorizontalScrollbar);

    if (!vpa.editor_initialized) { ImGui::TextDisabled("Editor not initialized"); ImGui::End(); return; }

    if (!vpa.editor_loaded) {
        vpa.editor->SetLanguageDefinition(TextEditor::LanguageDefinition::Python());
        std::string code = "# Bloodhound Code Editor\n# Source loaded from event stream\n\n";
        for (size_t i = 0; i < bus->count && i < 200; i++) {
            vpa_event_t *ev = &bus->events[i];
            if (ev->source_line > 0) {
                char buf[256];
                snprintf(buf, sizeof(buf), "# Line %d: %s/%s\n", ev->source_line,
                    vpa_kind_name(ev->kind), vpa_str_lookup(ev->entity));
                code += buf;
            }
        }
        vpa.editor->SetText(code);
        vpa.editor_loaded = true;
    }

    vpa.editor->Render("##code_editor", ImVec2(-1, -1), true);
    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// PERFORMANCE GRAPHS
// ═══════════════════════════════════════════════════════════

void VPA_RenderPerformanceGraphs(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    vpa_update_history(ide_ptr);

    ImGui::Begin("Performance##vpa_perf");
    ImGui::TextColored(ColV4(IM_COL32(120,160,255,255)), "Performance Metrics");
    ImGui::Separator();

    ImGui::TextColored(ColV4(IM_COL32(80,255,120,255)), "FPS: %.0f", ImGui::GetIO().Framerate);
    ImGui::SameLine();
    ImGui::TextColored(ColV4(IM_COL32(80,200,255,255)), "Events: %llu", (unsigned long long)bus->total_events);
    ImGui::SameLine();
    ImGui::TextColored(ColV4(IM_COL32(255,80,80,255)), "Errors: %llu", (unsigned long long)bus->error_count);
    ImGui::Separator();

    if (ImPlot::BeginPlot("Frame Rate", ImVec2(-1, 180))) {
        ImPlot::SetupAxes("Frame", "FPS");
        ImPlot::SetupAxisLimits(ImAxis_Y1, 0, 120);
        ImPlot::PlotLine("FPS", vpa.fps_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLineFill(IM_COL32(80,255,120,255)));
        ImPlot::EndPlot();
    }

    if (ImPlot::BeginPlot("Event Accumulation", ImVec2(-1, 180))) {
        ImPlot::SetupAxes("Frame", "Events");
        ImPlot::PlotLine("Total", vpa.event_rate_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLineFill(IM_COL32(80,200,255,255)));
        ImPlot::EndPlot();
    }

    if (bus->timing_count > 0) {
        ImGui::Separator();
        static double timing_bins[20];
        for (int i = 0; i < 20; i++) timing_bins[i] = 0;
        double max_ms = bus->timing_max_ms; if (max_ms == 0) max_ms = 1;
        for (size_t i = 0; i < bus->count; i++) {
            if (bus->events[i].kind != KIND_TIMING) continue;
            double ms = bus->events[i].value.type == VAL_FLOAT ? bus->events[i].value.num.f64 : 0;
            int bin = (int)(ms / max_ms * 19); if (bin < 0) bin = 0; if (bin > 19) bin = 19;
            timing_bins[bin]++;
        }
        if (ImPlot::BeginPlot("Timing Distribution", ImVec2(-1, 180))) {
            ImPlot::SetupAxes("Bin", "Count");
            ImPlotSpec spec;
            spec.LineColor = ColV4(IM_COL32(120,160,255,255));
            spec.FillColor = ColV4(IM_COL32(120,160,255,255));
            spec.FillAlpha = 0.7f;
            ImPlot::PlotBars("Timing", timing_bins, 20, 0.8, 1.0, 0.0, spec);
            ImPlot::EndPlot();
        }
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// EVENT RATE GRAPH
// ═══════════════════════════════════════════════════════════

void VPA_RenderEventRateGraph(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    vpa_update_history(ide_ptr);

    ImGui::Begin("Event Rate##vpa_rate");
    ImGui::TextColored(ColV4(IM_COL32(80,200,255,255)), "Events Per Second");
    ImGui::Separator();

    static float rate_buf[VPA_HISTORY_LEN];
    static uint64_t last_total = 0;
    float rate = (float)(bus->total_events - last_total) * ImGui::GetIO().Framerate;
    last_total = bus->total_events;
    rate_buf[vpa.history_pos] = rate;

    if (ImPlot::BeginPlot("##rate", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Frame", "Events/sec");
        ImPlot::PlotLine("Rate", rate_buf, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLineFill(IM_COL32(80,200,255,255)));
        ImPlot::EndPlot();
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// MEMORY GRAPH
// ═══════════════════════════════════════════════════════════

void VPA_RenderMemoryGraph(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    vpa_update_history(ide_ptr);

    ImGui::Begin("Memory##vpa_memory");
    ImGui::TextColored(ColV4(IM_COL32(255,220,80,255)), "Memory Usage");
    ImGui::Separator();

    float current_mb = (float)(bus->count * sizeof(vpa_event_t)) / (1024*1024);
    float max_mb = (float)(VPA_MAX_EVENTS * sizeof(vpa_event_t)) / (1024*1024);
    ImGui::Text("Current: %.2f MB / %.2f MB (%.1f%%)", current_mb, max_mb, 100.0f * current_mb / max_mb);
    ImGui::ProgressBar(current_mb / max_mb, ImVec2(-1, 20), "");
    ImGui::Separator();

    if (ImPlot::BeginPlot("##mem", ImVec2(-1, -1))) {
        ImPlot::SetupAxes("Frame", "MB");
        ImPlot::SetupAxisLimits(ImAxis_Y1, 0, max_mb);
        ImPlot::PlotLine("Memory", vpa.memory_history, VPA_HISTORY_LEN, 1.0, 0.0,
            SpecLineFill(IM_COL32(255,220,80,255)));
        ImPlot::EndPlot();
    }

    ImGui::End();
}

// ═══════════════════════════════════════════════════════════
// AI REASONING GRAPH
// ═══════════════════════════════════════════════════════════

void VPA_RenderAIReasoningGraph(void *ide_ptr) {
    vpa_bus_t *bus = (vpa_bus_t *)ide_ptr;
    ImGui::Begin("AI Reasoning##vpa_ai");
    ImGui::TextColored(ColV4(IM_COL32(80,255,120,255)), "AI Reasoning Graph");
    ImGui::Separator();

    ImNodes::BeginNodeEditor();

    // Error node
    ImNodes::BeginNode(1);
    ImNodes::BeginNodeTitleBar();
    ImGui::TextColored(ColV4(IM_COL32(255,80,80,255)), "Error");
    ImNodes::EndNodeTitleBar();
    ImGui::Text("%llu errors", (unsigned long long)bus->error_count);
    ImNodes::BeginOutputAttribute(10); ImGui::Text("->"); ImNodes::EndOutputAttribute();
    ImNodes::EndNode();

    // Root Cause
    ImNodes::BeginNode(2);
    ImNodes::BeginNodeTitleBar();
    ImGui::TextColored(ColV4(IM_COL32(255,220,80,255)), "Root Cause");
    ImNodes::EndNodeTitleBar();
    ImGui::Text("Analyzed %llu events", (unsigned long long)bus->total_events);
    ImNodes::BeginInputAttribute(20); ImGui::Text("<-"); ImNodes::EndInputAttribute();
    ImNodes::BeginOutputAttribute(21); ImGui::Text("->"); ImNodes::EndOutputAttribute();
    ImNodes::EndNode();

    // Affected
    ImNodes::BeginNode(3);
    ImNodes::BeginNodeTitleBar();
    ImGui::TextColored(ColV4(IM_COL32(255,120,255,255)), "Affected");
    ImNodes::EndNodeTitleBar();
    ImGui::Text("%d sources", bus->source_count);
    ImNodes::BeginInputAttribute(30); ImGui::Text("<-"); ImNodes::EndInputAttribute();
    ImNodes::BeginOutputAttribute(31); ImGui::Text("->"); ImNodes::EndOutputAttribute();
    ImNodes::EndNode();

    // Fix
    ImNodes::BeginNode(4);
    ImNodes::BeginNodeTitleBar();
    ImGui::TextColored(ColV4(IM_COL32(80,255,120,255)), "Suggested Fix");
    ImNodes::EndNodeTitleBar();
    if (bus->error_count > 0) { ImGui::Text("Apply fix"); ImGui::Text("Confidence: 0.85"); }
    else { ImGui::TextDisabled("No fix needed"); }
    ImNodes::BeginInputAttribute(40); ImGui::Text("<-"); ImNodes::EndInputAttribute();
    ImNodes::EndNode();

    ImNodes::Link(1, 10, 20);
    ImNodes::Link(2, 21, 30);
    ImNodes::Link(3, 31, 40);

    ImNodes::EndNodeEditor();
    ImGui::Separator();
    ImGui::TextColored(ColV4(IM_COL32(80,255,120,255)), "Chain: Error -> Cause -> Affected -> Fix");
    ImGui::End();
}
