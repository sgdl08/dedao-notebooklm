# dedao-notebooklm

## Purpose

Use this skill when the task is to work with purchased Dedao content through this repository's stable interfaces:

- download a course
- sync a course into a structured local bundle
- export AI pack files
- upload notes to NotebookLM
- generate chapter PPT decks from NotebookLM
- migrate project-local `downloads/` and `ppts/` outside the repository

This skill is meant to be callable by Codex, Claude Code, and OpenClaw.

## Stable interfaces

Prefer the CLI first:

```bash
dedao-nb --json list-courses
dedao-nb --json download <COURSE_ID>
dedao-nb --json sync-course <COURSE_ID>
dedao-nb --json export-ai-pack "<COURSE_DIR>" --course-id <COURSE_ID>
dedao-nb --json course-ppts "<COURSE_DIR>"
dedao-nb --json migrate-data --project-root .
```

If an HTTP interface is required, use:

```bash
dedao-api
```

## Data layout

By default, data does not live in the repository.

- download root: `~/Documents/dedao-notebooklm-data/downloads`
- ppt root: `~/Documents/dedao-notebooklm-data/ppts`

Do not assume `./downloads` or `./ppts` inside the repo unless the user explicitly overrides paths.

## Workflow

1. Read config with `dedao-nb --json config-list` if paths matter.
2. For course ingestion, prefer `sync-course` over ad hoc script chains.
3. For NotebookLM slide generation, use `course-ppts` and keep `--language zh_Hans` unless the user asks otherwise.
4. For old repositories with in-repo data folders, run `migrate-data` before doing more work.
5. Return structured paths from CLI JSON instead of reconstructing paths by hand.

## Guardrails

- Only operate on content the user already purchased or legally exported.
- Keep large outputs out of Git.
- When changing CLI/API behavior, update `README.md`, `CLAUDE.md`, and this skill.
