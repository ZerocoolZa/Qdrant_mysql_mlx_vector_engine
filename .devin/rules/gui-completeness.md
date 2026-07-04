# [@GHOST]{[@file<gui-completeness.md>][@domain<rules>][@role<vbstyle_rule>][@auth<devin>][@date<2026-06-27>][@ver<1.0>]}
# [@VBSTYLE]{[@auth<devin>][@role<rule>][@return<none>][@orch<none>][@no<decorators|print|hardcoded|tabs|self_underscore>][@model<rule>]}
# [@SUMMARY]{The Porsche Principle — GUI completeness is a first-class VBStyle requirement, not optional polish. A GUI missing its standard infrastructure is like a Porsche missing its engine. It may be recognizable, but it is not complete.}
# [@RULE]{gui_completeness}

# The Porsche Principle — GUI Completeness Rule

## Core Principle

A GUI is not judged by whether it has windows and buttons.
It is judged by whether it is a complete, usable application.

A GUI missing its standard infrastructure is like a Porsche missing its engine.
It may still be recognizable, but it is not complete.

GUI completeness is a first-class VBStyle requirement, not an optional polish step.

## The Rule

A VBStyle-compliant GUI MUST include its infrastructure as well as its visible widgets.
A GUI that has controls but no supporting surfaces is NOT VBStyle compliant.

## Application-Level Requirements

Every GUI application MUST have:

- [ ] Menu bar — File, Edit, View, Settings, Help
- [ ] Toolbar — quick access to primary actions
- [ ] Status bar — current state, connection status, audio level
- [ ] Settings dialog — every configurable item exposed
- [ ] Help menu — auto-generated from GuiAspect registry
- [ ] About dialog — app name, version, author
- [ ] Search — search within content
- [ ] Theme support — at minimum Dark and Light
- [ ] Font configuration — user-adjustable font sizes
- [ ] Context menus — right-click on all interactive elements
- [ ] Keyboard navigation — Tab, Enter, Escape work everywhere
- [ ] Standard actions — undo, redo, copy, paste, find
- [ ] Error reporting — errors shown to user, not silently swallowed
- [ ] Window persistence — position, size, state saved and restored

## Window-Level Requirements

Every window MUST have:

- [ ] Title — descriptive, updates with context
- [ ] Icon — window icon set
- [ ] Keyboard navigation — focus traversal works
- [ ] Status updates — window reflects current application state
- [ ] Close handling — confirm before destructive close
- [ ] Resize — min/max size enforced
- [ ] Position persistence — saved to settings

## Widget-Level Requirements

Every configurable widget MUST have (via GuiAspect):

- [ ] Setting — current value, synced with config
- [ ] Help — full help text for Help menu
- [ ] Tooltip — hover tooltip
- [ ] Shortcut — keyboard shortcut (where appropriate)
- [ ] Icon — icon name or path (where appropriate)
- [ ] Label — display label
- [ ] Config key — maps to Config.py
- [ ] Persistence — saved to settings file

## Table-Level Requirements

Every table MUST have:

- [ ] Sorting — click column header to sort
- [ ] Filtering — filter by text
- [ ] Searching — search within table
- [ ] Copy/export — copy selected rows
- [ ] Context menu — right-click actions
- [ ] Column resize — user can resize columns
- [ ] Column visibility — user can show/hide columns

## Editor-Level Requirements

Every text editor MUST have:

- [ ] Undo/redo — Ctrl+Z / Ctrl+Shift+Z
- [ ] Copy/paste — standard clipboard
- [ ] Find — Ctrl+F
- [ ] Replace — Ctrl+H
- [ ] Zoom — Ctrl+= / Ctrl+-
- [ ] Font options — adjustable font family and size
- [ ] Line numbers (where appropriate)
- [ ] Syntax highlighting (where appropriate)

## Enforcement

This rule is enforced by the VBStyle checker:

1. Every GUI application is scanned for required infrastructure
2. Every configurable widget is checked for GuiAspect registration
3. Missing infrastructure = VBStyle violation
4. Missing GuiAspect = VBStyle violation
5. A GUI with controls but no infrastructure FAILS VBStyle

## The Porsche Test

Before declaring a GUI "done", ask:

"Is this a Porsche, or is this a cardboard box of Porsche parts?"

- If it has buttons but no menu bar → cardboard box
- If it has settings but no help → cardboard box
- If it has widgets but no tooltips → cardboard box
- If it has controls but no shortcuts → cardboard box
- If it has a window but no persistence → cardboard box

A complete GUI is one where every piece exists, belongs, supports the others,
and works together so perfectly that the user never has to think about them.

When that happens, you don't notice the toolbar.
You don't notice the status bar.
You don't notice the shortcuts.
You simply smile, because everything feels complete.

That is the Porsche Principle.
