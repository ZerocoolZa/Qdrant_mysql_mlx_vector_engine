#include "gui.h"
#include "imgui.h"

void apply_theme(int theme_id) {
    ImGuiStyle &style = ImGui::GetStyle();

    switch (theme_id) {
        case 0: ImGui::StyleColorsDark(&style); break;
        case 1: ImGui::StyleColorsLight(&style); break;
        case 2: ImGui::StyleColorsClassic(&style); break;
        case 3: {
            ImGui::StyleColorsDark(&style);
            ImVec4 *c = style.Colors;
            c[ImGuiCol_WindowBg]        = ImVec4(0.10f, 0.10f, 0.12f, 1.00f);
            c[ImGuiCol_ChildBg]         = ImVec4(0.08f, 0.08f, 0.10f, 1.00f);
            c[ImGuiCol_PopupBg]         = ImVec4(0.12f, 0.12f, 0.14f, 0.96f);
            c[ImGuiCol_Border]          = ImVec4(0.20f, 0.22f, 0.27f, 0.50f);
            c[ImGuiCol_FrameBg]         = ImVec4(0.16f, 0.16f, 0.19f, 1.00f);
            c[ImGuiCol_FrameBgHovered]  = ImVec4(0.22f, 0.22f, 0.26f, 1.00f);
            c[ImGuiCol_FrameBgActive]   = ImVec4(0.28f, 0.28f, 0.32f, 1.00f);
            c[ImGuiCol_TitleBg]         = ImVec4(0.12f, 0.12f, 0.14f, 1.00f);
            c[ImGuiCol_TitleBgActive]   = ImVec4(0.18f, 0.18f, 0.22f, 1.00f);
            c[ImGuiCol_MenuBarBg]       = ImVec4(0.10f, 0.10f, 0.12f, 1.00f);
            c[ImGuiCol_Tab]             = ImVec4(0.14f, 0.14f, 0.17f, 1.00f);
            c[ImGuiCol_TabHovered]      = ImVec4(0.30f, 0.40f, 0.60f, 1.00f);
            c[ImGuiCol_TabSelected]     = ImVec4(0.20f, 0.25f, 0.40f, 1.00f);
            c[ImGuiCol_DockingPreview]  = ImVec4(0.30f, 0.50f, 0.80f, 0.70f);
            c[ImGuiCol_DockingEmptyBg]  = ImVec4(0.06f, 0.06f, 0.08f, 1.00f);
            c[ImGuiCol_Header]          = ImVec4(0.20f, 0.25f, 0.40f, 1.00f);
            c[ImGuiCol_HeaderHovered]   = ImVec4(0.28f, 0.35f, 0.55f, 1.00f);
            c[ImGuiCol_HeaderActive]    = ImVec4(0.35f, 0.45f, 0.65f, 1.00f);
            c[ImGuiCol_Button]          = ImVec4(0.18f, 0.20f, 0.25f, 1.00f);
            c[ImGuiCol_ButtonHovered]   = ImVec4(0.25f, 0.30f, 0.45f, 1.00f);
            c[ImGuiCol_ButtonActive]    = ImVec4(0.32f, 0.38f, 0.55f, 1.00f);
            c[ImGuiCol_CheckMark]       = ImVec4(0.40f, 0.60f, 1.00f, 1.00f);
            c[ImGuiCol_SliderGrab]      = ImVec4(0.30f, 0.45f, 0.70f, 1.00f);
            c[ImGuiCol_SliderGrabActive]= ImVec4(0.40f, 0.55f, 0.85f, 1.00f);
            c[ImGuiCol_Separator]       = ImVec4(0.20f, 0.22f, 0.27f, 0.50f);
            c[ImGuiCol_PlotLines]       = ImVec4(0.40f, 0.60f, 1.00f, 1.00f);
            c[ImGuiCol_PlotHistogram]   = ImVec4(0.40f, 0.80f, 0.40f, 1.00f);
            break;
        }
        default: ImGui::StyleColorsDark(&style); break;
    }

    style.WindowRounding = 4.0f;
    style.ChildRounding = 4.0f;
    style.FrameRounding = 3.0f;
    style.TabRounding = 4.0f;
    style.ScrollbarRounding = 6.0f;
    style.GrabRounding = 3.0f;
    style.WindowBorderSize = 1.0f;
    style.FrameBorderSize = 0.0f;
    style.TabBorderSize = 0.0f;
    style.WindowPadding = ImVec2(8, 8);
    style.FramePadding = ImVec2(6, 4);
    style.ItemSpacing = ImVec2(8, 6);
    style.ItemInnerSpacing = ImVec2(6, 4);
}

void apply_font_scale(int scale) {
    ImGuiStyle &style = ImGui::GetStyle();
    style.FontScaleMain = (float)scale / 100.0f;
}
