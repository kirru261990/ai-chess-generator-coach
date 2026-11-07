# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`GLOSSARY.md`** at the repo root, or
- **`GLOSSARY-MAP.md`** at the repo root if it exists: it points at one `GLOSSARY.md` per context. Read each one relevant to the topic.
- **`docs/decisions/`**: this repo's ADRs (`NNNN-short-name.md`). Read the ones that touch the area you're about to work in. **This repo keeps ADRs in `docs/decisions/`, not `docs/adr/`**: write new ADRs there, with the next free number, and never create a `docs/adr/` folder.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

## File structure

This repo is single-context:

```
/
├── GLOSSARY.md            ← created lazily by /domain-modeling
├── docs/decisions/        ← ADRs, e.g. 0001-open-source-reuse.md
├── backend/
└── web/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR 0005 (practice assistance), but worth reopening because…_
