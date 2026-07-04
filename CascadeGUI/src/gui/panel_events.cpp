#include "gui.h"
#include "imgui.h"
#include <string.h>
#include <stdio.h>

static CascadeEvent polled[512];
static bool auto_scroll = true;
static int selected_event = -1;
static CascadeEvent selected_ev;
static char clip_buf[2048];

void panel_events_render(GuiState *state, EventBus *bus) {
    if (!state->show_events) return;
    if (!ImGui::Begin("Events", &state->show_events, ImGuiWindowFlags_NoFocusOnAppearing)) {
        ImGui::End();
        return;
    }

    /* --- Filter bar --- */
    ImGui::TextDisabled("Channel:");
    ImGui::SameLine();
    const char *channels[] = { "All", "SYSTEM", "AI", "GRAPH", "PROFILER", "MEMORY",
                               "CONSOLE", "FILE", "NETWORK", "USER", "ERROR" };
    ImGui::SetNextItemWidth(90);
    ImGui::Combo("##ch_filter", &state->selected_channel, channels, IM_ARRAYSIZE(channels));

    ImGui::SameLine();
    ImGui::TextDisabled("Level:");
    ImGui::SameLine();
    const char *levels[] = { "All", "INFO", "WARN", "ERROR", "DEBUG", "TRACE" };
    ImGui::SetNextItemWidth(70);
    ImGui::Combo("##lvl_filter", &state->selected_level, levels, IM_ARRAYSIZE(levels));

    ImGui::SameLine();
    ImGui::Checkbox("Auto-scroll", &auto_scroll);

    ImGui::SameLine();
    if (ImGui::Button("Clear All")) {
        event_bus_clear(bus);
        selected_event = -1;
        show_notification(state, "Events cleared");
    }

    ImGui::Separator();

    /* --- Poll events --- */
    uint32_t n = event_bus_poll(bus, polled, 512);

    /* Split: table on top, detail on bottom */
    float detail_h = selected_event >= 0 ? 180.0f : 0.0f;

    ImGuiTableFlags flags = ImGuiTableFlags_ScrollY | ImGuiTableFlags_RowBg |
                            ImGuiTableFlags_BordersOuter | ImGuiTableFlags_BordersV |
                            ImGuiTableFlags_Resizable | ImGuiTableFlags_Sortable;

    if (ImGui::BeginTable("events_table", 6, flags, ImVec2(0, -detail_h - 30), 0.0f)) {
        ImGui::TableSetupColumn("ID", ImGuiTableColumnFlags_DefaultSort | ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableSetupColumn("Time", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Ch", ImGuiTableColumnFlags_WidthFixed, 70);
        ImGui::TableSetupColumn("Lvl", ImGuiTableColumnFlags_WidthFixed, 50);
        ImGui::TableSetupColumn("Source", ImGuiTableColumnFlags_WidthFixed, 80);
        ImGui::TableSetupColumn("Message", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableHeadersRow();

        for (uint32_t i = 0; i < n; i++) {
            CascadeEvent *ev = &polled[i];

            if (state->selected_channel > 0 && (int)ev->channel != state->selected_channel - 1) continue;
            if (state->selected_level > 0 && (int)ev->level != state->selected_level - 1) continue;
            if (state->search_filter[0] != '\0') {
                if (!strstr(ev->message, state->search_filter) && !strstr(ev->source, state->search_filter))
                    continue;
            }

            bool is_selected = (selected_event == (int)i);

            ImGui::TableNextRow(0, 0);

            /* Row background for selected */
            if (is_selected) {
                ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg0, IM_COL32(40, 60, 100, 100));
                ImGui::TableSetBgColor(ImGuiTableBgTarget_RowBg1, IM_COL32(40, 60, 100, 140));
            }

            float r, g, b, a;
            level_color(ev->level, &r, &g, &b, &a);

            /* ID — clickable + selectable */
            ImGui::TableSetColumnIndex(0);
            char id_label[32];
            snprintf(id_label, sizeof(id_label), "%llu", (unsigned long long)ev->id);
            if (ImGui::Selectable(id_label, is_selected,
                                  ImGuiSelectableFlags_SpanAllColumns | ImGuiSelectableFlags_AllowOverlap)) {
                selected_event = (int)i;
                selected_ev = *ev;
            }
            /* Right-click context menu on event row */
            if (ImGui::BeginPopupContextItem("##event_ctx")) {
                if (ImGui::MenuItem("Copy Message")) {
                    ImGui::SetClipboardText(ev->message);
                    show_notification(state, "Message copied");
                }
                if (ImGui::MenuItem("Copy Full Event")) {
                    snprintf(clip_buf, sizeof(clip_buf),
                             "[#%llu] %s %.3fs %s %s: %s (int=%d, float=%.3f)",
                             (unsigned long long)ev->id,
                             channel_name(ev->channel), (double)ev->timestamp_ns / 1e9,
                             level_name(ev->level), ev->source, ev->message,
                             ev->payload_int, ev->payload_float);
                    ImGui::SetClipboardText(clip_buf);
                    show_notification(state, "Event copied to clipboard");
                }
                ImGui::Separator();
                if (ImGui::MenuItem("Filter by This Channel")) {
                    state->selected_channel = (int)ev->channel + 1;
                    show_notification(state, "Filtered by channel");
                }
                if (ImGui::MenuItem("Filter by This Level")) {
                    state->selected_level = (int)ev->level + 1;
                    show_notification(state, "Filtered by level");
                }
                if (ImGui::MenuItem("Clear Filters")) {
                    state->selected_channel = -1;
                    state->selected_level = -1;
                    state->search_filter[0] = '\0';
                    show_notification(state, "Filters cleared");
                }
                ImGui::Separator();
                if (ImGui::MenuItem("Re-publish Event")) {
                    event_bus_publish(bus, ev->channel, ev->level, ev->source, ev->message);
                    show_notification(state, "Event re-published");
                }
                if (ImGui::MenuItem("Select Event")) {
                    selected_event = (int)i;
                    selected_ev = *ev;
                }
                ImGui::EndPopup();
            }

            ImGui::TableSetColumnIndex(1);
            double secs = (double)ev->timestamp_ns / 1e9;
            ImGui::Text("%.3f", secs);

            ImGui::TableSetColumnIndex(2);
            ImGui::TextColored(ImVec4(0.6f, 0.7f, 0.9f, 1.0f), "%s", channel_name(ev->channel));

            ImGui::TableSetColumnIndex(3);
            ImGui::TextColored(ImVec4(r, g, b, a), "%s", level_name(ev->level));

            ImGui::TableSetColumnIndex(4);
            ImGui::TextUnformatted(ev->source);

            ImGui::TableSetColumnIndex(5);
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(r * 0.7f + 0.3f, g * 0.7f + 0.3f, b * 0.7f + 0.3f, 1.0f));
            ImGui::TextUnformatted(ev->message);
            ImGui::PopStyleColor();
        }
        ImGui::EndTable();
    }

    if (auto_scroll && ImGui::GetScrollY() < ImGui::GetScrollMaxY()) {
        ImGui::SetScrollHereY(1.0f);
    }

    /* --- Event count bar --- */
    ImGui::TextDisabled("Showing %u of %llu events", n, (unsigned long long)event_bus_count(bus));
    if (selected_event >= 0) {
        ImGui::SameLine();
        ImGui::TextDisabled("| Selected: #%llu", (unsigned long long)selected_ev.id);
    }

    /* --- Event Detail Inspector --- */
    if (selected_event >= 0) {
        ImGui::Separator();
        ImGui::BeginChild("##event_detail", ImVec2(0, detail_h - 30), true);

        ImGui::TextColored(ImVec4(0.4f, 0.6f, 1.0f, 1.0f), "Event Inspector");
        ImGui::Separator();

        if (ImGui::BeginTable("detail_tbl", 2, ImGuiTableFlags_BordersV)) {
            ImGui::TableSetupColumn("Field", ImGuiTableColumnFlags_WidthFixed, 120);
            ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("ID");
            ImGui::TableSetColumnIndex(1); ImGui::Text("%llu", (unsigned long long)selected_ev.id);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Timestamp");
            ImGui::TableSetColumnIndex(1); ImGui::Text("%.6f s (%llu ns)",
                (double)selected_ev.timestamp_ns / 1e9,
                (unsigned long long)selected_ev.timestamp_ns);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Channel");
            ImGui::TableSetColumnIndex(1);
            ImGui::TextColored(ImVec4(0.6f, 0.7f, 0.9f, 1.0f), "%s (%d)",
                channel_name(selected_ev.channel), (int)selected_ev.channel);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Level");
            ImGui::TableSetColumnIndex(1);
            float r, g, b, a;
            level_color(selected_ev.level, &r, &g, &b, &a);
            ImGui::TextColored(ImVec4(r, g, b, a), "%s (%d)",
                level_name(selected_ev.level), (int)selected_ev.level);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Source");
            ImGui::TableSetColumnIndex(1); ImGui::TextUnformatted(selected_ev.source);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Message");
            ImGui::TableSetColumnIndex(1);
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(r * 0.7f + 0.3f, g * 0.7f + 0.3f, b * 0.7f + 0.3f, 1.0f));
            ImGui::TextWrapped("%s", selected_ev.message);
            ImGui::PopStyleColor();

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Payload (int)");
            ImGui::TableSetColumnIndex(1); ImGui::Text("%d", selected_ev.payload_int);

            ImGui::TableNextRow();
            ImGui::TableSetColumnIndex(0); ImGui::TextDisabled("Payload (float)");
            ImGui::TableSetColumnIndex(1); ImGui::Text("%.6f", selected_ev.payload_float);

            ImGui::EndTable();
        }

        ImGui::Separator();

        /* Action buttons */
        if (ImGui::Button("Copy Message")) {
            ImGui::SetClipboardText(selected_ev.message);
            show_notification(state, "Message copied");
        }
        ImGui::SameLine();
        if (ImGui::Button("Copy Full")) {
            snprintf(clip_buf, sizeof(clip_buf),
                     "[#%llu] %s %.3fs %s %s: %s (int=%d, float=%.3f)",
                     (unsigned long long)selected_ev.id,
                     channel_name(selected_ev.channel), (double)selected_ev.timestamp_ns / 1e9,
                     level_name(selected_ev.level), selected_ev.source, selected_ev.message,
                     selected_ev.payload_int, selected_ev.payload_float);
            ImGui::SetClipboardText(clip_buf);
            show_notification(state, "Full event copied");
        }
        ImGui::SameLine();
        if (ImGui::Button("Re-publish")) {
            event_bus_publish(bus, selected_ev.channel, selected_ev.level, selected_ev.source, selected_ev.message);
            show_notification(state, "Event re-published");
        }
        ImGui::SameLine();
        if (ImGui::Button("Filter Channel")) {
            state->selected_channel = (int)selected_ev.channel + 1;
            show_notification(state, "Filtered by channel");
        }
        ImGui::SameLine();
        if (ImGui::Button("Close")) {
            selected_event = -1;
        }

        ImGui::EndChild();
    }

    ImGui::End();
}
