# Wizard SVG Animation Engine

A procedural SVG animation compiler with a C core and Python/Qt control layer.

## Architecture

```
Python/Qt UI (Studio) → Scene JSON → C Engine → SVG Output
```

The C engine is a deterministic animation compiler that converts:
**Scene → Timeline → Motion Rules → SVG DOM**

## Features

- **Scene graph** with typed objects (hat, wand, star, coat, beard, etc.)
- **Keyframe animation** with 13 easing functions (linear, elastic, bounce, back, etc.)
- **Particle system** — magic dust, stars, sparks, runes
- **Orbit physics** + noise drift + float + wand wave + glow
- **JSON scene DSL** — declarative scene definitions
- **SVG export** with SMIL animations
- **MCP node graph** — animated node visualization for installer UIs
- **Qt Studio** — live preview, JSON editor, property panels, timeline

## Quick Start

```bash
# Build the C engine
make c-engine

# Generate demo scenes
make demo
make mcp-demo

# Open in browser
open examples/wizard_idle.svg
open examples/mcp_nodes.svg

# Run the Qt Studio (requires PyQt6)
pip install PyQt6
make run-studio
```

## CLI Usage

```bash
# Render a JSON scene to SVG
cd c && ./wizard_engine ../scenes/wizard_idle.json output.svg

# Built-in demos
cd c && ./wizard_engine --demo output.svg
cd c && ./wizard_engine --mcp-demo output.svg
```

## Scene JSON Format

```json
{
  "name": "Wizard Idle",
  "width": 512,
  "height": 512,
  "background": [0.05, 0.03, 0.12],
  "duration": 4.0,
  "fps": 60,
  "objects": [
    {
      "id": "hat",
      "type": "hat",
      "position": [256, 180],
      "rotation": 0,
      "scale": 1.0,
      "opacity": 1.0,
      "color": "#2a1860",
      "stroke_color": "#ffd700",
      "stroke_width": 2,
      "motion": {
        "type": "float",
        "speed": 0.4,
        "amplitude": 6,
        "radius": 0,
        "phase": 0
      }
    }
  ]
}
```

## Object Types

| Type | Description |
|------|-------------|
| `hat` | Wizard hat with star and band |
| `wand` | Magic wand with glowing tip |
| `star` | 5-pointed star with glow |
| `coat` | Wizard robe/coat |
| `beard` | Wizard beard with mustache |
| `circle` | Basic circle |
| `rect` | Basic rectangle |
| `text` | Text element |
| `glow_orb` | Glowing orb with gradient |
| `rune_circle` | Animated rune circle |
| `lightning` | Lightning bolt |
| `mcp_node` | MCP service node with status |
| `emitter` | Particle emitter |

## Motion Types

| Type | Description |
|------|-------------|
| `rotate` | Continuous rotation |
| `orbit` | Circular orbit around center |
| `pulse` | Scale pulsing |
| `fade` | Opacity oscillation |
| `noise_drift` | Perlin noise drift |
| `float` | Gentle up/down bobbing |
| `wand_wave` | Wand-specific wave motion |
| `glow` | Color/glow pulsing |

## Easing Functions

`linear`, `in_quad`, `out_quad`, `in_out_quad`, `in_cubic`, `out_cubic`,
`in_out_cubic`, `in_elastic`, `out_elastic`, `in_bounce`, `out_bounce`,
`in_back`, `out_back`

## File Layout

```
engine/
├── c/                          C core engine
│   ├── wizard_engine.h         Public API header
│   ├── wizard_engine_core.c    Vectors, easing, math, Perlin noise
│   ├── wizard_engine_scene.c   Scene graph, keyframes, motion
│   ├── wizard_engine_particles.c  Particle system
│   ├── wizard_engine_svg.c     SVG exporter with SMIL
│   ├── wizard_engine_json.c    JSON scene parser/serializer
│   ├── wizard_engine_main.c    CLI entry point
│   ├── Makefile
│   ├── wizard_engine           Compiled CLI binary
│   └── libwizard_engine.dylib  Shared library for Python ctypes
├── python/
│   ├── wizard_engine_bridge.py ctypes bridge to C engine
│   └── wizard_studio.py        Qt6 GUI (live preview, editor, timeline)
├── scenes/
│   └── wizard_idle.json        Example scene
├── examples/
│   ├── wizard_idle.svg         Generated demo
│   └── mcp_nodes.svg           MCP node graph demo
└── Makefile
```
