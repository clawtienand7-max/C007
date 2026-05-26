# CLAUDE.md

This file provides guidance for AI assistants (Claude Code and similar tools) working in this repository.

## Repository Overview

This is a minimal test/bootstrap repository. As of the initial commit it contains only a `README.md`. This file will be updated as the codebase grows.

## Current State

| Item | Status |
|------|--------|
| Source code | Not yet added |
| Tests | Not yet added |
| Build system | Not yet configured |
| CI/CD | Not yet configured |
| Dependencies | None |

## Branch Conventions

- `main` — stable, production-ready code
- `claude/<short-description>` — branches used by AI assistants for automated changes
- Feature branches should be named `feature/<short-description>`
- Bug fix branches should be named `fix/<short-description>`

## Development Workflow

Since no toolchain is configured yet, the general workflow to follow once one is added:

1. Make changes on a feature branch, never directly on `main`
2. Run tests before committing
3. Push and open a draft PR for review
4. Only merge when CI passes

## Git Conventions

- Write commit messages in the imperative mood: `Add X`, `Fix Y`, `Remove Z`
- Keep the subject line under 72 characters
- Reference issue numbers in the body when relevant
- Never force-push to `main`
- Never skip pre-commit hooks (`--no-verify`)

## AI Assistant Guidelines

### Before making changes
- Read this file and `README.md` first
- Check `git log --oneline -10` to understand recent history
- Prefer editing existing files over creating new ones
- Do not create documentation files (`.md`) unless explicitly requested

### Code style (defaults until a linter/formatter is configured)
- Prefer explicit over implicit
- Keep functions small and single-purpose
- No commented-out code
- No debug print statements left in commits

### What to avoid
- Do not commit secrets, credentials, or `.env` files
- Do not install dependencies without discussing it first
- Do not refactor code that is not related to the current task
- Do not add features beyond what the task requires

### Pull requests
- Always open PRs as drafts
- Title: imperative mood, under 70 characters
- Body: brief summary of what changed and why, plus a test plan

## Updating This File

Update `CLAUDE.md` whenever:
- A new language or framework is added to the project
- The build, test, or deploy workflow changes
- New conventions are established
- CI/CD is configured
