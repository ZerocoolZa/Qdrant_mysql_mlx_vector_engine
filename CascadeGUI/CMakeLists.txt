cmake_minimum_required(VERSION 3.16)
project(CascadeGUI C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

option(ENABLE_IMPLOT "Enable ImPlot for graphing" ON)

# --- ImGui ---
set(IMGUI_DIR ${CMAKE_SOURCE_DIR}/external/imgui)
if(NOT EXISTS ${IMGUI_DIR}/imgui.cpp)
    execute_process(COMMAND git clone --depth 1 https://github.com/ocornut/imgui.git ${IMGUI_DIR})
endif()

# --- GLFW via Homebrew ---
find_path(GLFW_INCLUDE_DIR NAMES GLFW/glfw3.h PATHS /opt/homebrew/opt/glfw/include /opt/homebrew/include /usr/local/include)
find_library(GLFW_LIBRARY NAMES glfw PATHS /opt/homebrew/opt/glfw/lib /opt/homebrew/lib /usr/local/lib)
if(NOT GLFW_LIBRARY)
    message(FATAL_ERROR "GLFW library not found. Install with: brew install glfw")
endif()

add_executable(CascadeGUI
    src/main.cpp
    src/event_bus.cpp
    src/gui/window_main.cpp
    src/gui/menus.cpp
    src/gui/toolbar.cpp
    src/gui/hotkeys.cpp
    src/gui/theme.cpp
    src/gui/panel_events.cpp
    src/gui/panel_graph.cpp
    src/gui/panel_ai.cpp
    src/gui/panel_console.cpp
    src/gui/panel_profiler.cpp
    src/gui/panel_memory.cpp
    src/gui/panel_extras.cpp
    src/ai/ai_bridge.cpp
    ${IMGUI_DIR}/imgui.cpp
    ${IMGUI_DIR}/imgui_draw.cpp
    ${IMGUI_DIR}/imgui_tables.cpp
    ${IMGUI_DIR}/imgui_widgets.cpp
    ${IMGUI_DIR}/imgui_demo.cpp
    ${IMGUI_DIR}/backends/imgui_impl_glfw.cpp
    ${IMGUI_DIR}/backends/imgui_impl_opengl3.cpp
)

target_include_directories(CascadeGUI PRIVATE
    src
    src/gui
    src/ai
    ${IMGUI_DIR}
    ${IMGUI_DIR}/backends
    ${GLFW_INCLUDE_DIR}
)

target_link_libraries(CascadeGUI PRIVATE
    ${GLFW_LIBRARY}
    "-framework OpenGL"
    "-framework Cocoa"
    "-framework IOKit"
    "-framework CoreVideo"
)

# --- ImPlot (optional) ---
if(ENABLE_IMPLOT)
    set(IMPLOT_DIR ${CMAKE_SOURCE_DIR}/external/implot)
    if(NOT EXISTS ${IMPLOT_DIR}/implot.cpp)
        execute_process(COMMAND git clone --depth 1 https://github.com/epezent/implot.git ${IMPLOT_DIR})
    endif()
    target_sources(CascadeGUI PRIVATE
        ${IMPLOT_DIR}/implot.cpp
        ${IMPLOT_DIR}/implot_items.cpp
    )
    target_include_directories(CascadeGUI PRIVATE ${IMPLOT_DIR})
    target_compile_definitions(CascadeGUI PRIVATE CASCADE_HAS_IMPLOT)
endif()
