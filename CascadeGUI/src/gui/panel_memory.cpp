#include "gui.h"
#include "imgui.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#define MEM_REGION_MAX 128

typedef struct {
    char name[64];
    uint64_t address;
    uint64_t size;
    int alive;
    char tag[32];
} MemRegion;

static MemRegion regions[MEM_REGION_MAX];
static int region_count = 0;
static uint64_t total_allocated = 0;
static uint64_t peak_allocated = 0;
static int alloc_count = 0;
static int free_count = 0;
static bool track_enabled = true;

void mem_track_alloc(const char *name, uint64_t addr, uint64_t size, const char *tag) {
    if (!track_enabled) return;
    if (region_count >= MEM_REGION_MAX) return;
    MemRegion *r = &regions[region_count++];
    strncpy(r->name, name ? name : "?", sizeof(r->name) - 1);
    r->name[sizeof(r->name) - 1] = '\0';
    r->address = addr;
    r->size = size;
    r->alive = 1;
    strncpy(r->tag, tag ? tag : "", sizeof(r->tag) - 1);
    r->tag[sizeof(r->tag) - 1] = '\0';
    total_allocated += size;
    if (total_allocated > peak_allocated) peak_allocated = total_allocated;
    alloc_count++;
}

void mem_track_free(uint64_t addr) {
    for (int i = 0; i < region_count; i++) {
        if (regions[i].address == addr && regions[i].alive) {
            regions[i].alive = 0;
            total_allocated -= regions[i].size;
            free_count++;
            return;
        }
    }
}

void panel_memory_render(GuiState *state, EventBus *bus) {
    if (!state->show_memory) return;
    if (!ImGui::Begin("Memory", &state->show_memory)) { ImGui::End(); return; }

    /* Summary */
    ImGui::Text("Current: %s  Peak: %s  Allocs: %d  Frees: %d  Alive: %d",
                size_str(total_allocated), size_str(peak_allocated),
                alloc_count, free_count, alloc_count - free_count);
    ImGui::Separator();

    /* Controls */
    ImGui::Checkbox("Track", &track_enabled);
    ImGui::SameLine();
    if (ImGui::Button("Clear Dead")) {
        int j = 0;
        for (int i = 0; i < region_count; i++) {
            if (regions[i].alive) {
                if (i != j) regions[j] = regions[i];
                j++;
            }
        }
        region_count = j;
    }
    ImGui::SameLine();
    if (ImGui::Button("Simulate Alloc")) {
        char nm[32];
        snprintf(nm, sizeof(nm), "block_%d", alloc_count);
        mem_track_alloc(nm, (uint64_t)rand() * 4096, (uint64_t)(rand() % 65536) + 256, "test");
        event_bus_publish(bus, CH_MEMORY, EV_DEBUG, "Memory", nm);
    }
    ImGui::SameLine();
    if (ImGui::Button("Simulate Free") && region_count > 0) {
        for (int i = region_count - 1; i >= 0; i--) {
            if (regions[i].alive) {
                mem_track_free(regions[i].address);
                break;
            }
        }
    }

    ImGui::Separator();

    /* Region table */
    ImGuiTableFlags flags = ImGuiTableFlags_ScrollY | ImGuiTableFlags_RowBg |
                            ImGuiTableFlags_BordersOuter | ImGuiTableFlags_BordersV |
                            ImGuiTableFlags_Resizable;

    if (ImGui::BeginTable("mem_table", 5, flags)) {
        ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Address", ImGuiTableColumnFlags_WidthFixed, 120);
        ImGui::TableSetupColumn("Size", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Tag", ImGuiTableColumnFlags_WidthFixed, 60);
        ImGui::TableSetupColumn("Status", ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableHeadersRow();

        for (int i = 0; i < region_count; i++) {
            MemRegion *r = &regions[i];
            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0);
            ImGui::TextUnformatted(r->name);
            ImGui::TableSetColumnIndex(1);
            ImGui::TextDisabled("0x%llx", (unsigned long long)r->address);
            ImGui::TableSetColumnIndex(2);
            ImGui::Text("%s", size_str(r->size));
            ImGui::TableSetColumnIndex(3);
            ImGui::TextUnformatted(r->tag);
            ImGui::TableSetColumnIndex(4);
            if (r->alive) {
                ImGui::TextColored(ImVec4(0.4f, 0.8f, 0.4f, 1.0f), "alive");
            } else {
                ImGui::TextColored(ImVec4(0.5f, 0.5f, 0.5f, 1.0f), "freed");
            }
        }
        ImGui::EndTable();
    }

    ImGui::End();
}
