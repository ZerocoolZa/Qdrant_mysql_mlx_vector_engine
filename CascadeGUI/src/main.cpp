#include "gui/gui.h"
#include "event_bus.h"
#include "ai/ai_bridge.h"
#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"
#ifdef CASCADE_HAS_IMPLOT
#include "implot.h"
#endif
#include "GLFW/glfw3.h"
#include <stdio.h>
#include <stdlib.h>

static EventBus g_bus;
static GuiState g_gui;
static GLFWwindow *g_window = NULL;

static void glfw_error_callback(int err, const char *desc) {
    fprintf(stderr, "GLFW Error %d: %s\n", err, desc);
}

int main(int argc, char **argv) {
    glfwSetErrorCallback(glfw_error_callback);
    if (!glfwInit()) {
        fprintf(stderr, "Failed to init GLFW\n");
        return 1;
    }

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_OPENGL_FORWARD_COMPAT, GL_TRUE);
    glfwWindowHint(GLFW_DECORATED, GLFW_TRUE);
    glfwWindowHint(GLFW_RESIZABLE, GLFW_TRUE);
    glfwWindowHint(GLFW_MAXIMIZED, GLFW_TRUE);

    g_window = glfwCreateWindow(1600, 900, "Cascade GUI", NULL, NULL);
    if (!g_window) {
        fprintf(stderr, "Failed to create window\n");
        glfwTerminate();
        return 1;
    }

    glfwMakeContextCurrent(g_window);
    glfwSwapInterval(1);

    /* Init ImGui */
    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
#ifdef CASCADE_HAS_IMPLOT
    ImPlot::CreateContext();
#endif
    ImGuiIO &io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;
    io.IniFilename = "cascade_layout.ini";

    /* Apply theme */
    apply_theme(3);
    apply_font_scale(100);

    /* Init backends */
    ImGui_ImplGlfw_InitForOpenGL(g_window, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    /* Init systems */
    event_bus_init(&g_bus);
    gui_state_init(&g_gui);
    ai_bridge_init();

    event_bus_publish(&g_bus, CH_SYSTEM, EV_INFO, "Main", "Cascade GUI started");
    event_bus_publish(&g_bus, CH_SYSTEM, EV_INFO, "Main", "ImGui docking enabled");
    event_bus_publish(&g_bus, CH_AI, EV_INFO, "Main", "AI bridge initialized");

    /* Main loop */
    while (!glfwWindowShouldClose(g_window)) {
        glfwPollEvents();

        /* Start frame */
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        /* Hotkeys */
        render_hotkeys(&g_gui, &g_bus);

        /* Menu bar */
        render_menubar(&g_gui, &g_bus);

        /* Dockspace */
        ImGuiViewport *viewport = ImGui::GetMainViewport();
        ImGui::SetNextWindowPos(viewport->WorkPos);
        ImGui::SetNextWindowSize(viewport->WorkSize);
        ImGui::SetNextWindowViewport(viewport->ID);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
        ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));

        ImGuiWindowFlags dock_flags = ImGuiWindowFlags_NoDocking |
                                       ImGuiWindowFlags_NoTitleBar |
                                       ImGuiWindowFlags_NoCollapse |
                                       ImGuiWindowFlags_NoResize |
                                       ImGuiWindowFlags_NoMove |
                                       ImGuiWindowFlags_NoBringToFrontOnFocus |
                                       ImGuiWindowFlags_NoNavFocus |
                                       ImGuiWindowFlags_MenuBar;

        if (g_gui.docking) {
            dock_flags |= ImGuiWindowFlags_NoDocking;
            ImGui::Begin("##Dockspace", NULL, dock_flags);
            ImGui::PopStyleVar(3);

            ImGuiID dockspace_id = ImGui::GetID("CascadeDockspace");
            ImGui::DockSpace(dockspace_id, ImVec2(0, 0),
                             g_gui.docking ? ImGuiDockNodeFlags_PassthruCentralNode : 0);

            /* Right-click context menu on dockspace */
            render_dockspace_context_menu(&g_gui);
        } else {
            ImGui::Begin("##Main", NULL, dock_flags);
            ImGui::PopStyleVar(3);
        }

        ImGui::End();

        /* Panels */
        panel_events_render(&g_gui, &g_bus);
        panel_graph_render(&g_gui, &g_bus);
        panel_ai_render(&g_gui, &g_bus);
        panel_console_render(&g_gui, &g_bus);
        panel_profiler_render(&g_gui, &g_bus);
        panel_memory_render(&g_gui, &g_bus);

        /* Settings, shortcuts, status bar, notifications */
        render_activity_rail(&g_gui, &g_bus);
        render_right_bar(&g_gui, &g_bus);
        render_settings_panel(&g_gui, &g_bus);
        render_shortcuts_window(&g_gui);
        render_appearance_window(&g_gui);
        render_statusbar(&g_gui, &g_bus);
        render_notification(&g_gui);

        /* Demo / metrics / style / about */
        if (g_gui.show_demo) ImGui::ShowDemoWindow(&g_gui.show_demo);
        if (g_gui.show_metrics) ImGui::ShowMetricsWindow(&g_gui.show_metrics);
        if (g_gui.show_style_editor) {
            ImGui::Begin("Style Editor", &g_gui.show_style_editor);
            ImGui::ShowStyleEditor();
            ImGui::End();
        }
        if (g_gui.show_about) {
            ImGui::Begin("About Cascade", &g_gui.show_about, ImGuiWindowFlags_AlwaysAutoResize);
            ImGui::Text("Cascade GUI v1.0");
            ImGui::Text("Dear ImGui + GLFW + OpenGL3 + ImPlot");
            ImGui::Text("EventBus: %llu events, %llu dropped",
                        (unsigned long long)event_bus_count(&g_bus),
                        (unsigned long long)event_bus_dropped(&g_bus));
            ImGui::Separator();
            ImGui::Text("Built: %s %s", __DATE__, __TIME__);
            ImGui::Text("ImGui: %s", IMGUI_VERSION);
#ifdef CASCADE_HAS_IMPLOT
            ImGui::Text("ImPlot: %s", IMPLOT_VERSION);
#endif
            ImGui::Separator();
            ImGui::TextDisabled("Right-click dockspace for context menu");
            ImGui::TextDisabled("Cmd+/ for keyboard shortcuts");
            ImGui::End();
        }

        /* Render */
        ImGui::Render();
        int display_w, display_h;
        glfwGetFramebufferSize(g_window, &display_w, &display_h);
        glViewport(0, 0, display_w, display_h);
        glClearColor(0.08f, 0.08f, 0.10f, 1.00f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

        /* Update viewports */
        if (io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
            GLFWwindow *backup = glfwGetCurrentContext();
            ImGui::UpdatePlatformWindows();
            ImGui::RenderPlatformWindowsDefault();
            glfwMakeContextCurrent(backup);
        }

        glfwSwapBuffers(g_window);

        /* Simulate events for demo */
        static double last_sim = 0;
        double now = ImGui::GetTime();
        if (!g_gui.paused && now - last_sim > 0.5) {
            last_sim = now;
            const char *sources[] = { "Pipeline", "Graph", "AI", "Profiler", "Memory" };
            const char *msgs[] = {
                "Pipeline stage completed",
                "Graph node updated",
                "AI inference done",
                "Profiler sample recorded",
                "Memory allocation tracked",
            };
            int si = (int)(now * 7) % 5;
            CascadeChannel chs[] = { CH_SYSTEM, CH_GRAPH, CH_AI, CH_PROFILER, CH_MEMORY };
            CascadeEventLevel lvls[] = { EV_INFO, EV_INFO, EV_DEBUG, EV_TRACE, EV_INFO };
            event_bus_publish(&g_bus, chs[si], lvls[si], sources[si], msgs[si]);
        }
    }

    /* Cleanup */
    ai_bridge_shutdown();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
#ifdef CASCADE_HAS_IMPLOT
    ImPlot::DestroyContext();
#endif
    ImGui::DestroyContext();
    glfwDestroyWindow(g_window);
    glfwTerminate();

    return 0;
}
