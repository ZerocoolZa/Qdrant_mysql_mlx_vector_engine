//[@GHOST]{file_path="core/Dom_Bloodhound/bloodhound_vpa.c" date="2026-07-04" author="Devin" session_id="bloodhound-vpa" context="Bloodhound VPA — Visual Performance & Analysis module. Integrates ImPlot for live CPU/memory/FPS/events-per-sec graphs, ImNodes for interactive execution graph node editing, and ImGuiColorTextEdit for syntax-highlighted Python source viewer. This is the final 20% that completes the Bloodhound IDE."}
//[@VBSTYLE]{standard="VBStyle" version="1" rules="PascalCase UPPERCASE implot imnodes textedit"}
//[@FILEID]{id="bloodhound_vpa.h" domain="dom_bloodhound" authority="BloodhoundVPA"}
//[@SUMMARY]{summary="Bloodhound VPA header — declares the VPA panel render functions that extend bloodhound_ide.cpp with ImPlot live graphs, ImNodes interactive graph, and ImGuiColorTextEdit syntax-highlighted source editor."}
//[@CLASS]{class="BloodhoundVPA" domain="dom_bloodhound" authority="single"}

#ifndef BLOODHOUND_VPA_H
#define BLOODHOUND_VPA_H

#include "imgui.h"
#include "implot.h"
#include "imnodes.h"
#include "TextEditor.h"

// ide_state_t is defined in bloodhound_ide.cpp before including this header.
// We use a void* approach to avoid type conflicts.
// VPA functions accept void* and cast internally.

// VPA panel render functions
void VPA_RenderLiveDashboard(void *ide);
void VPA_RenderNodeGraph(void *ide);
void VPA_RenderCodeEditor(void *ide);
void VPA_RenderPerformanceGraphs(void *ide);
void VPA_RenderEventRateGraph(void *ide);
void VPA_RenderMemoryGraph(void *ide);
void VPA_RenderKindDistribution(void *ide);
void VPA_RenderAIReasoningGraph(void *ide);
void VPA_Init(void);
void VPA_Shutdown(void);

#endif
