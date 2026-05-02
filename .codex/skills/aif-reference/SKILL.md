---
name: aif-reference
description: >-
  Create knowledge references from URLs, documents, or files for use by AI agents.
  Fetches, processes, and stores structured references in .ai-factory/references/.
  Use when the AI needs information it doesn't have — API docs, library guides,
  specifications, internal wikis, or any external knowledge source.
argument-hint: "<url|path> [url2|path2] [--name <ref-name>] [--update]"
allowed-tools: Read Write Edit Glob Grep Bash(mkdir *) Bash(ls *) Bash(wc *) WebFetch WebSearch AskUserQuestion
disable-model-invocation: false
metadata:
  author: ai-factory
  version: "1.0"
  category: knowledge-management
---

# Reference Creator

You create structured knowledge references from external sources (URLs, documents, files) and store them in `.ai-factory/references/` so that AI agents can use this knowledge in future conversations.

### Project Context

**Read `.ai-factory/skill-context/aif-reference/SKILL.md`** — MANDATORY if the file exists.

This file contains project-specific rules accumulated by `/aif-evolve` from patches,
codebase conventions, and tech-stack analysis. These rules are tailored to the current project.

**How to apply skill-context rules:**
- Treat them as **project-level overrides** for this skill's general instructions
- When a skill-context rule conflicts with a general rule written in this SKILL.md,
  **the skill-context rule wins**
- When there is no conflict, apply both
- **CRITICAL:** skill-context rules apply to ALL outputs of this skill — including the generated
  reference files. If a skill-context rule says "references MUST include X" — you MUST comply.

**Enforcement:** After generating any output artifact, verify it against all skill-context rules.
If any rule is violated — fix the output before presenting it to the user.

---

## When To Use

- You need AI to know about a library/API/framework it wasn't trained on or has outdated knowledge of
- You want to ground AI responses in specific documentation rather than general knowledge
- You want to capture internal docs, wikis, or guides for AI use
- You're preparing context for `/aif-plan` or `/aif-implement` that requires domain knowledge
- You want a persistent, reusable knowledge artifact (not just a one-off conversation)

---

## Argument Detection

```
Check $ARGUMENTS:
├── Contains "--update"         → Update Mode: refresh existing reference
├── Contains URLs (http/https)  → URL Mode: fetch and process web sources
├── Contains file paths         → File Mode: process local documents
├── "list"                      → List existing references
├── "show <name>"               → Show reference content
├── "delete <name>"             → Delete a reference (with confirmation)
└── Empty                       → Interactive: ask what to create
```

---

## Workflow

### Step 0: Setup

Ensure `.ai-factory/references/` exists:
```bash
mkdir -p .ai-factory/references
```

Check for existing references to avoid duplicates:
```bash
ls .ai-factory/references/
```

If `--name <ref-name>` is provided in arguments, use that as the reference name.
If `--update` is provided, find and update the existing reference instead of creating new.

### Step 1: Collect Sources

**For URLs:**

For EACH URL provided:

1. **Fetch the page** using `WebFetch`:
   ```
   WebFetch(url, "Extract ALL key information from this page:
   - Main topic and purpose
   - Key concepts, terms, and definitions
   - Code examples and patterns (preserve exactly)
   - API methods, parameters, return types, signatures
   - Configuration options with defaults
   - Best practices and recommendations
   - Error handling and edge cases
   - Version information and compatibility notes
   - Links to critical sub-pages
   Provide a comprehensive, structured extraction. Preserve code examples verbatim.")
   ```

2. **Assess depth** — if the page references critical sub-pages (API reference, detailed guides, changelogs), fetch those too (up to 8 additional pages per source URL, prioritize by relevance to the core topic).

3. **Search for gaps** — run 1-2 targeted `WebSearch` queries if the fetched content has obvious gaps:
   - `"<topic> API reference complete"` — for API docs
   - `"<topic> migration guide"` or `"<topic> changelog"` — for version-specific info

**For local files:**

1. Read each file with the `Read` tool
2. If the file references other local files, read those too (up to 5 levels of includes)
3. Identify the file format (markdown, HTML, JSON, YAML, plain text) and extract accordingly

**For interactive mode (no arguments):**

Ask the user:
1. What topic/technology do you want to create a reference for?
2. Do you have URLs or local files, or should I search?
3. What aspects are most important for your use case?

If the user wants you to search, use `WebSearch` to find authoritative sources, then proceed with URL mode.

### Step 2: Synthesize Reference

Transform collected material into a structured reference document.

**Reference file format:**

```markdown
# <Topic> Reference

> Source: <list of source URLs or file paths>
> Created: YYYY-MM-DD
> Updated: YYYY-MM-DD

## Overview

<1-3 paragraph summary: what this is, when to use it, key characteristics>

## Core Concepts

<Concept 1>: <clear explanation>
<Concept 2>: <clear explanation>
...

## API / Interface

<Only if applicable. Method signatures, parameters, return types.>
<Preserve exact signatures and types from source docs.>

## Usage Patterns

<Practical code examples organized by use case.>
<Every example must be complete enough to be useful — not just fragments.>

## Configuration

<Options, defaults, valid values. Table format preferred.>

## Best Practices

<Numbered list with reasoning — not just "do X" but "do X because Y">

## Common Pitfalls

<What goes wrong and how to avoid it>

## Version Notes

<Only if relevant. Breaking changes, migration notes, deprecations.>
```

**Quality rules:**
- **No hallucination** — only include information actually found in sources. If a topic wasn't covered, omit the section rather than guessing.
- **Preserve code verbatim** — code examples from docs must be exact, not paraphrased.
- **Actionable over academic** — write "Use X when..." not "X is a feature that..."
- **Dense** — pack maximum useful information per line. This is a reference, not a tutorial.
- **Complete signatures** — for APIs, include ALL parameters, types, and return types.
- **Source attribution** — always include source URLs at the top.

### Step 3: Name and Save

**Naming convention:**
- Derive from topic: `react-hooks.md`, `fastapi-endpoints.md`, `docker-compose.md`
- Use lowercase, hyphens, `.md` extension
- If `--name` was provided, use that (with `.md` extension if missing)
- Avoid generic names like `reference.md` or `docs.md`

**Save to:** `.ai-factory/references/<name>.md`

### Step 4: Register in Index

Check if `.ai-factory/references/INDEX.md` exists. Create or update it:

```markdown
# References Index

Available knowledge references for AI agents.

| Reference | Topic | Sources | Updated |
|-----------|-------|---------|---------|
| [react-hooks](react-hooks.md) | React Hooks API and patterns | react.dev | 2026-03-20 |
| [docker-compose](docker-compose.md) | Docker Compose configuration | docs.docker.com | 2026-03-20 |
```

### Step 5: Report

Show the user:
- Reference name and path
- Size (line count)
- Sections included
- Source URLs used
- How to use it: mention that other skills can read `.ai-factory/references/<name>.md`

---

## Update Mode (`--update`)

When `--update` is present:

1. Find the existing reference (by `--name` or by matching source URLs in the header)
2. Re-fetch the source URLs from the reference header
3. Compare with existing content — only update sections that changed
4. Preserve the `Created:` date, update `Updated:` date
5. Report what changed

---

## List / Show / Delete

**`/aif-reference list`** — read and display `.ai-factory/references/INDEX.md` or list files in the directory.

**`/aif-reference show <name>`** — read and display the reference content. Add `.md` if missing.

**`/aif-reference delete <name>`** — ask for confirmation, then delete the file and update INDEX.md.

---

## Integration With Other Skills

References in `.ai-factory/references/` are available to all AI Factory skills:
- `/aif-plan` and `/aif-implement` can read them for domain context
- `/aif-grounded` can use them as evidence sources
- `/aif-explore` can reference them during research

To make a skill aware of a specific reference, mention it in `.ai-factory/RULES.md`:
```markdown
## References
- For <topic> details, see `.ai-factory/references/<name>.md`
```

---

## Artifact Ownership

- **Primary ownership:** `.ai-factory/references/` (all files)
- **Shared ownership:** `.ai-factory/references/INDEX.md`
- **Read-only:** all other `.ai-factory/` files

---

## Guardrails

- **Max reference size:** aim for under 1000 lines per reference. If larger, split into multiple files and create a directory: `.ai-factory/references/<topic>/` with an `INDEX.md` inside.
- **No duplication** — before creating, check if a similar reference already exists.
- **No stale data** — always include source URLs so references can be refreshed with `--update`.
- **No opinions** — references state facts from sources, not the AI's preferences.
- **Respect access** — if a URL requires authentication or returns errors, report this to the user instead of guessing content.
