---
description: Devin documentation index — points to comprehensive reference docs for Cascade, CLI, context/models, and guidelines
trigger: model_decision
---

# Devin Documentation Index

Comprehensive reference documentation for Devin (Cascade, CLI, context, models, guidelines) has been collected from docs.devin.ai and organized into section files in `.devin/docs/`.

## When to consult these docs

- **User asks about Cascade features** (modes, arena, app deploys, terminal, previews, quick review, codemaps, deepwiki, agent command center, spaces, Devin Local) → read `.devin/docs/cascade-core.md`
- **User asks about context awareness, indexing, .codeiumignore, models, or Adaptive** → read `.devin/docs/context-and-models.md`
- **User asks about Devin CLI** (commands, config, rules, skills, hooks, MCP, subagents, permissions, handoff) → read `.devin/docs/cli-reference.md`
- **User asks about how to instruct Devin effectively, prompt templates, or best practices** → read `.devin/docs/guidelines.md`
- **User asks about Cascade workflows, memories, rules, AGENTS.md, or web search** → also check `.devin/rules/cascade-workflows-and-features.md` (pre-existing)
- **User asks about VBStyle coding rules** → check `.devin/rules/code.md` (pre-existing)

## File inventory

| File | Content | Source pages |
|------|---------|-------------|
| `.devin/docs/cascade-core.md` | Cascade overview, modes, arena, app deploys, terminal, previews, quick review, vibe-and-replace, codemaps, deepwiki, AI commit messages, agent command center, spaces, advanced config, Devin Local | 15 pages from /desktop/ |
| `.devin/docs/context-and-models.md` | Context awareness, fast context, remote indexing, .codeiumignore, AI models, Adaptive router | 7 pages from /desktop/context-awareness/ and /desktop/ |
| `.devin/docs/cli-reference.md` | CLI quickstart, essential commands, configuration, rules & AGENTS.md, skills, hooks, MCP, subagents, permissions, models, handoff | 15 pages from /cli/ |
| `.devin/docs/guidelines.md` | Good vs bad instructions, instructing effectively, prompt templates cheat sheet, when to use Devin, prompt engineering | 5 pages from /essential-guidelines/ and /desktop/best-practices/ |
| `.devin/rules/cascade-workflows-and-features.md` | Cascade workflows, memories, rules, AGENTS.md, web search, worktrees, MCP, hooks, skills | 10 pages from /desktop/cascade/ and /desktop/context-awareness/ |
| `.devin/rules/code.md` | VBStyle coding rules | Extracted from book.db |

## Notes

- All docs fetched on 2026-06-22 from docs.devin.ai.
- API reference endpoint specs (v1/v2/v3) and OpenAPI YAML files were intentionally excluded — they are REST endpoint schemas, not conceptual documentation.
- Enterprise, integrations, onboarding, and product-guides sections were not included as they don't directly affect Cascade behavior. Consult https://docs.devin.ai/ directly for those topics.
- Some content may be slightly out of date as Devin evolves rapidly. Always check the live docs for the latest information.
