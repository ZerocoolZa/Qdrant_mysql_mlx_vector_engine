# SVG Engine — DevChat Plan

> **Module**: `svg_engine/`
> **Created**: 2026-06-22
> **Status**: Complete — C engine + Python Qt studio working

---

## What Was Built (Session History)

### Session 1 — SVG Animation Engine (today)
- Built C core engine (6 source files, compiled to binary + dylib)
- Built `wizard_engine_core.c` — Vec2/Vec3 types, 13 easing functions, Perlin noise, PRNG
- Built `wizard_engine_scene.c` — scene graph (256 objects), keyframe system, 9 motion types
- Built `wizard_engine_particles.c` — particle system (512 particles, 4 types: dust/star/spark/rune)
- Built `wizard_engine_svg.c` — SVG exporter with SMIL, 14 object renderers, gradients/filters
- Built `wizard_engine_json.c` — JSON scene parser + serializer
- Built `wizard_engine_main.c` — CLI with 2 built-in demos (wizard idle + MCP node graph)
- Built `wizard_engine_bridge.py` — Python ctypes bridge to C engine
- Built `wizard_studio.py` — Qt6 GUI with live animated SVG preview (QWebEngineView)
- Built `wizard_idle.json` — example scene
- Built Makefile + README.md

### Origin
- Started from a concept for a "procedural SVG animation engine with compiled core"
- Goal: wizard-themed UI engine for MCP installer wizard skin
- Architecture: Python/Qt UI → Scene JSON → C Engine → SVG Output

---

## Current File Inventory

| File | Lines | Purpose | Status |
|------|-------|---------|--------|
| **C Core** | | | |
| `c/wizard_engine.h` | 280 | Public API header | Complete |
| `c/wizard_engine_core.c` | 180 | Vectors, easing, Perlin noise, PRNG | Complete |
| `c/wizard_engine_scene.c` | 350 | Scene graph, keyframes, motion, types | Complete |
| `c/wizard_engine_particles.c` | 200 | Particle system with physics | Complete |
| `c/wizard_engine_svg.c` | 600 | SVG exporter with SMIL animations | Complete |
| `c/wizard_engine_json.c` | 500 | JSON scene parser + serializer | Complete |
| `c/wizard_engine_main.c` | 220 | CLI entry point + 2 demo scenes | Complete |
| `c/wizard_engine` | 52KB | Compiled binary (arm64) | Working |
| `c/libwizard_engine.dylib` | 52KB | Shared library for Python ctypes | Working |
| **Python** | | | |
| `python/wizard_engine_bridge.py` | 120 | ctypes bridge to C engine | Working |
| `python/wizard_studio.py` | 750 | Qt6 GUI (live preview, editor, timeline) | Working |
| **Scenes/Examples** | | | |
| `scenes/wizard_idle.json` | 200 | Example wizard scene | Complete |
| `examples/wizard_idle.svg` | 10KB | Generated wizard demo (13 objects) | Working |
| `examples/mcp_nodes.svg` | 8KB | MCP node graph demo (14 objects) | Working |
| **Other** | | | |
| `Makefile` | 30 | Build targets | Complete |
| `README.md` | 150 | Full documentation | Complete |

---

## What Works

- C engine compiles clean (arm64, no warnings except format)
- CLI: `./wizard_engine scene.json output.svg`
- CLI: `./wizard_engine --demo output.svg` (built-in wizard scene)
- CLI: `./wizard_engine --mcp-demo output.svg` (MCP node graph)
- JSON scene loading → SVG export
- 14 object types: hat, wand, star, coat, beard, circle, rect, text, glow_orb, rune_circle, lightning, mcp_node, emitter, group
- 9 motion types: rotate, orbit, pulse, fade, noise_drift, float, wand_wave, glow, particle_emit
- 13 easing functions: linear, quad, cubic, elastic, bounce, back (in/out/in-out variants)
- Particle system with physics (velocity, gravity, drag, lifetime, color interpolation)
- Qt Studio with live animated SVG preview (QWebEngineView/Chromium)
- JSON editor with syntax highlighting
- Object property panels (position, rotation, scale, color, motion)
- Timeline scrubber with play/pause
- Dark theme

---

## What's Broken / Incomplete

### P1 — Should Fix
1. **ctypes bridge segfaults** — Scene struct is ~6MB (256 objects × 512 particles). Python ctypes buffer allocation is fragile. Currently using CLI subprocess as workaround.
2. **Star particle SVG path has format bug** — `x1` instead of `x2` in one path attribute (warning, not crash)
3. **No keyframe editing in Qt Studio** — "Add Keyframe" button is a placeholder

### P2 — Nice to Have
4. **No orbit path animation in SMIL** — orbit motion uses `animateMotion` but the path syntax may not render in all browsers
5. **No undo/redo** in Qt Studio editor
6. **No SVG export from Qt Studio preview** — only from JSON via CLI
7. **Particle rendering is static** — particles are simulated at export time, not animated in SVG (SMIL doesn't support particle systems natively)

---

## Next Steps

1. **Fix star particle path** — `x1` → `x2` format bug
2. **Fix ctypes bridge** — or permanently switch to CLI subprocess (simpler, more robust)
3. **Add keyframe editing** to Qt Studio timeline
4. **Add undo/redo** to Qt Studio
5. **Add SVG export button** to Qt Studio (calls CLI internally)
6. **Add more object types** — wand sparks, spell effects, portal, crystal ball

---

## Integration with Ghost Core

SVG engine becomes the **UI skin engine** for Ghost:

```
ghost/gui/skin_engine.py
  └── uses svg_engine for animated wizard-themed UI
  └── MCP installer wizard skin (each MCP = animated node)
  └── Ghost boot screen with wizard animation
  └── Settings panel with magical particle effects
  └── generates SVG skins from config
```

The MCP node graph demo (`--mcp-demo`) already shows how MCP services can be visualized as an animated node graph — this is the basis for the Ghost control center UI.
