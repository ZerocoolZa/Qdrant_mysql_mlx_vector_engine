#include "ai_bridge.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

static AiBridgeState g_ai;

void ai_bridge_init(void) {
    memset(&g_ai, 0, sizeof(g_ai));
    strcpy(g_ai.model, "cascade-local");
    g_ai.confidence = 0.0f;
}

void ai_bridge_shutdown(void) {
    /* cleanup */
}

static const char *stub_responses[] = {
    "I am Cascade AI. I can analyze your EventBus, profile performance, and suggest optimizations.",
    "Based on the current event flow, I recommend checking the GRAPH channel for bottlenecks.",
    "Memory usage looks stable. No leaks detected in the last 1000 allocations.",
    "Profiler shows ImGui render time is within normal range (< 3ms).",
    "EventBus has no dropped events. Throughput is healthy.",
    "I detected a potential issue: the AI channel has high latency. Consider batching queries.",
    "Graph analysis complete. 8 nodes, 12 edges, no cycles detected.",
    "Recommendation: enable ImPlot for real-time performance visualization.",
};

const char *ai_bridge_query(const char *prompt, const char *model, float temperature) {
    strncpy(g_ai.last_query, prompt ? prompt : "", sizeof(g_ai.last_query) - 1);
    g_ai.last_query[sizeof(g_ai.last_query) - 1] = '\0';
    strncpy(g_ai.model, model ? model : "cascade-local", sizeof(g_ai.model) - 1);
    g_ai.model[sizeof(g_ai.model) - 1] = '\0';
    g_ai.queries_made++;

    /* Stub: pick a response based on hash of prompt */
    unsigned int hash = 0;
    const char *p = prompt;
    while (p && *p) { hash = hash * 31 + (unsigned char)*p++; }
    int idx = hash % (sizeof(stub_responses) / sizeof(stub_responses[0]));

    g_ai.confidence = 0.75f + (float)(hash % 25) / 100.0f;
    return stub_responses[idx];
}

float ai_bridge_last_confidence(void) {
    return g_ai.confidence;
}
