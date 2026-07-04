# Essential Guidelines: Instructing Devin Effectively

Source pages (fetched 2026-06-22 from docs.devin.ai):
- /essential-guidelines/good-vs-bad-instructions.md
- /essential-guidelines/instructing-devin-effectively.md
- /essential-guidelines/prompt-templates-cheat-sheet.md
- /essential-guidelines/when-to-use-devin.md
- /desktop/best-practices/prompt-engineering.md

---

## 1. Core Principle

**Be as specific as possible.** Provide a detailed spec just as you would when asking a coworker to code something.

### Components of a High-Quality Prompt
1. **Clear objective or outcome** — What are you asking for? A plan? New code? A refactor?
2. **All relevant context** — Use @-mentions for code blocks. Include customer-specific context.
3. **Necessary constraints** — Frameworks, libraries, languages, space/time complexity, security.

### Example of an Effective Prompt
> In the Devin repo, build a tool that monitors RAM and CPU usage of remote machines Devin runs on:
> - Create a background task that launches automatically when devin.rs starts.
> - Open a connection to all forked remote machines and monitor RAM/CPU.
> - If usage exceeds 80%, emit a new Devin event (check how we use Kafka).
> - Architect this so it doesn't block other operations. Understand how containers for Devin sub-agents interact.

**Why it works:** provides context, step-by-step instructions, clear success criteria (emit event at 80%), references existing patterns (Kafka, containers).

---

## 2. Good vs. Bad Instructions

### Good Patterns

**Adding an API endpoint:**
> Create a new endpoint `/users/stats` that returns JSON with user count and average signup age. Use the existing users table in PostgreSQL. Reference the `/orders/stats` endpoint in `statsController.js` for response structure. Ensure covered by `StatsController.test.js`.

**Writing unit tests:**
> Add Jest tests for AuthService methods: login and logout. Ensure coverage ≥80%. Use `UserService.test.js` as example. After implementation, run `npm test -- --coverage` and verify >80% for both. Confirm tests pass with valid and invalid credentials, and logout clears session data.

**Migrating code:**
> Migrate `logger.js` from JavaScript to TypeScript. We have `tsconfig.json` and `LoggerTest.test.js`. Make sure it compiles without errors and don't change the existing config. Verify by: 1) running `tsc`, 2) running `npm test LoggerTest.test.js`, 3) checking all existing logger method calls still work without type errors.

**Implementing from design:**
> Implement the pricing page from this Figma file: [link]. Focus on the 'Pricing Section' frame. Use our Tailwind config in `tailwind.config.ts`. Reuse existing Card and Button components from `src/components/ui/`. After implementing, spin up the dev server and take screenshots at desktop (1440px) and mobile (375px). Do not open a PR until it matches the design.

**Investigating a production bug:**
> Users are reporting 500 errors on checkout. Use the Sentry MCP to pull latest stack traces for payments-api. Check the database for related data issues. Find the root cause, fix it, and add a regression test. Link the Sentry issue in the PR description.

### Bad Patterns (and why they fail)

| Bad Instruction | Why It Fails | Instead |
|----------------|-------------|---------|
| "Add a user stats endpoint" | Unspecific about what stats, no data sources, no patterns, no tests | Specify route, response format, data source, reference existing code, include test requirements |
| "Make the user profile page more user-friendly" | "User-friendly" is subjective, no specific UI components, unclear interaction | Name specific components, list exact elements, reference existing styling, define interaction flow |
| "Find issues with our codebase and fix them" | Too vague, no success criteria, no way to know when done | Use Devin Review for automated review, or give targeted task like "Find and fix all uses of deprecated `oldLogger` API in `src/services/`" |
| "Make the landing page look better" | "Better" is subjective, Devin can't make aesthetic judgment calls | Provide Figma design, reference site, or specific changes: "Increase hero font to 48px, add 32px padding, use `indigo-500` from Tailwind config" |
| "Build a new microservices architecture for our app" | Very large, unstructured, requires many architectural decisions | Use Ask Devin to investigate, propose architectures with trade-offs, create separate sessions for each service |
| "Improve our database's performance" | No specific queries, no metrics | Specify which queries to optimize and what metrics to target |

---

## 3. Best Practices: Do's and Don'ts

### Be Opinionated and Specific
**Do:** Make important decisions for Devin. Offer specific design choices. Define clear scope, boundaries, success criteria.
**Don't:** Leave decisions open-ended. Vague instructions lead to unexpected results.

### Leverage Devin's Strengths
**Do:** Pick tasks Devin is good at. Provide examples, modules, resources, templates. Share direct links to docs. Share specific filenames. Connect MCP integrations (Figma, databases, monitoring).
**Don't:** Skip providing context for complex tasks. For visual tasks, provide Figma files or detailed specs — Devin won't invent aesthetics.

### Use Feedback Loops
**Do:** Use tests (unit/integration) to confirm correctness. Maintain build validations, lint checks, static analysis. Enable Devin Review with Auto-Fix for closed-loop PR iteration.
**Don't:** Neglect providing feedback. Don't assign tasks without defining how you'll evaluate them.

### Set Checkpoints
**Do:** Break complex tasks into verifiable sub-tasks. Start one session per sub-task. Define what success looks like for each. Ask Devin to report back after each checkpoint.
**Don't:** Skip specific validation requirements. Don't leave verification steps implicit.

### Let Devin Test Its Own Work
Devin has a full desktop environment (shell, IDE, browser):
- "Run `npm run dev` and verify the new page renders at `/settings`."
- "Open the browser, navigate to login page, confirm OAuth flow completes."
- "Take screenshots at desktop (1440px) and mobile (375px) and confirm layout matches design."
- "Record yourself testing the checkout flow end-to-end."

### Use Playbooks and Knowledge
- **Playbooks**: reusable, shareable prompts for repetitive/complex tasks. Iterate on them.
- **Knowledge**: persistent context Devin remembers across all sessions (coding standards, common bugs, deployment workflows, internal tools). Automatically recalled when relevant.

---

## 4. Prompt Templates Cheat Sheet

### Bug Fixes
```
Fix the bug where [describe behavior].
Steps to reproduce: 1. [step] 2. [step] 3. [step]
Expected: [what should happen]. Actual: [what happens].
Please: 1. Investigate root cause in [file/dir] 2. Implement fix 3. Add regression test 4. Run test suite
```

### Investigate Production Issue
```
Users are reporting [issue] in production.
Please: 1. Use [Sentry/DataDog] MCP to pull error logs 2. Identify root cause 3. Implement fix 4. Add error handling 5. Create regression test 6. Link alert in PR description
```

### Add New API Endpoint
```
Create a new API endpoint [path] that [description].
Requirements: Method, Request body, Response format, Authentication.
Please: 1. Reference existing [similar endpoint] 2. Implement following conventions 3. Add validation + error handling 4. Write unit tests 5. Update docs 6. Run test suite
```

### Add New UI Component
```
Add a new [component type] to [file/location].
Requirements: Name, Props, Functionality, Styling reference.
Please: 1. Create following existing patterns 2. Implement functionality 3. Add TypeScript types 4. Style to match design system 5. Add unit tests 6. Integrate into [parent] 7. Test manually
```

### Implement from Design
```
Implement [feature] from this design: [Figma link]. Focus on [frame].
Requirements: Use existing components from [path], follow styling in [design system], responsive at [breakpoints].
Please: 1. Implement following specs 2. Reuse existing components 3. Test at desktop (1440px) and mobile (375px) 4. Take screenshots 5. Do not open PR until it visually matches
```

### Refactor a Module
```
Refactor [module] to improve [aspect].
Current issues: [list].
Requirements: Keep all functionality, follow patterns in [reference], improve [metric].
Please: 1. Analyze current 2. Refactor 3. Ensure tests pass 4. Add tests for new functions 5. Run full suite 6. Report improvements
```

### Add Test Coverage
```
Add comprehensive test coverage for [file/module].
Current: [X]%. Target: [Y]%.
Please: 1. Analyze code for edge cases 2. Write unit tests for public methods 3. Add integration tests 4. Reference [existing test file] 5. Run `npm test -- --coverage` 6. Ensure all pass
```

### Optimize Database Queries
```
Optimize database queries in [file/module].
Issues: [query] is slow ([time]), [operation] causes N+1.
Please: 1. Analyze execution plans 2. Add indexes to [table/column] 3. Refactor to JOINs 4. Benchmark before/after 5. Ensure tests pass 6. Document improvements
```

### Fix Security Vulnerability
```
Fix security vulnerability in [file/module].
Type: [SQL injection/XSS/CSRF]. Severity: [High/Medium/Low].
Please: 1. Review advisory: [link] 2. Implement fix 3. Add input validation/sanitization 4. Add security test 5. Run security audit 6. Check for similar vulnerabilities
```

### Upgrade Dependency
```
Upgrade [package] from [old] to [new].
Please: 1. Review changelog for breaking changes 2. Update in [package file] 3. Update deprecated API usage 4. Run migration script if applicable 5. Run all tests 6. Test manually 7. Update docs
```

### Review a Pull Request
```
Review PR: [link/number].
Focus: code quality, performance, security, test coverage, documentation.
Please: 1. Review each changed file 2. Leave specific actionable comments 3. Verify changes address PR description 4. Check edge cases 5. Ensure tests adequate 6. Approve or request changes
```

---

## 5. When to Use Devin

### Best Practices
1. **Scope tasks with Ask Devin** before implementation — explore codebase, scope approach, auto-generate high-context prompt.
2. **Run multiple Devins in parallel** — carve out independent tasks, run simultaneously.
3. **Tag Devin on Slack or Teams** — start sessions from conversations about bugs/features.
4. **Let Devin close the loop** — enable Devin Review with Auto-Fix for automatic PR iteration.
5. **Extend with MCP integrations** — Datadog, Sentry, databases, Figma, Notion, Stripe, etc.
6. **Let Devin test its own work** — full desktop environment with shell, IDE, browser.
7. **Automate recurring tasks** with Scheduled Sessions.
8. **Use Devin CLI for local coding** — `/handoff` to cloud when needed.

### Evaluating Tasks for Devin
1. **Can I describe clear success criteria?** Tests, CI checks, verifiable outcomes → best results.
2. **Is there enough context?** Files, patterns, docs, examples.
3. **Would breaking this down help?** Split large projects into focused sessions.

**Rule of thumb:** if a task would take you ≤3 hours, Devin can most likely do it. For longer tasks, break into smaller sessions.

### Pre-Task Checklist
- **Task Definition**: clear start/end, explicit success criteria.
- **Available Context**: examples, patterns, prototypes, filenames, design files, MCP integrations.
- **Success Validation**: test suites, lint checks, compilation steps, browser testing.
- **Review Effort**: with Auto-Fix, Devin responds to review comments and CI failures automatically.
- **Task Size**: keep sessions focused (XS, S, or M per Session Insights). Split large tasks.

### Post-Task Review
- Monitor session trajectory with Session Insights.
- If Devin hits session usage limits → task may be too complex.
- If Devin struggles with dev environment → revisit Workspace setup.
- Learn from mistakes: provide more context in future sessions, add Knowledge items.
- Use improved prompt from Session Insights as starting point for similar future tasks.

---

## 6. Prompt Engineering (Devin Desktop specific)

### Components
1. **Clear objective** — plan? new code? refactor?
2. **All relevant context** — @-mentions for code blocks. Customer-specific context.
3. **Necessary constraints** — frameworks, libraries, languages, complexity, security.

### Examples
- **Bad**: "Write unit tests for all test cases for an Order Book object."
- **Good**: "Using `@class:unit-testing-module` write unit tests for `@func:src-order-book-add` testing for exceptions thrown when above or below stop loss."

- **Bad**: "Refactor rawDataTransform."
- **Good**: "Refactor `@func:rawDataTransform` by turning the while loop into a for loop and using the same data structure output as `@func:otherDataTransformer`"

- **Bad**: "Create a new Button for the Contact Form."
- **Good**: "Create a new Button component for the `@class:ContactForm` using the style guide in `@repo:frontend-components` that says 'Continue'"

**Tip:** For complex tasks requiring @-mentions of specific code blocks, use Chat instead of Command.
