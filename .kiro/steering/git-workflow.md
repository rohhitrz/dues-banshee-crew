---
inclusion: always
---
# Git workflow

## First-time setup (only if the repo has no `.git` folder)
1. Check identity first: run `git config user.name` and `git config user.email`.
   - If either is empty, STOP and ask the user. Never set a name/email yourself and never use a placeholder identity.
2. Run `git init -b main`.
3. Create `.gitignore` with at least:
   node_modules/, .next/, dist/, coverage/, .turbo/, .vercel/,
   .env, .env.*, !.env.example, *.log, .DS_Store
   - NEVER ignore `.kiro/` or any of its sub-folders (required by the hackathon rules).
4. First commit: `chore: initial project setup with Kiro steering, spec and designs`.

## When to commit
Commit after every meaningful, working change. Each commit should be one logical unit:
- a finished spec task (one commit per task in tasks.md)
- a new or updated spec (requirements.md / design.md / tasks.md)
- a new or changed steering file, hook, custom agent or MCP config
- a bug fix, refactor or test addition that passes

Do NOT commit:
- half-done or broken code (tests/typecheck must pass for the files you touched)
- secrets, `.env` files, API keys, tokens or credentials. Check `git diff --staged` before every commit.
- large generated files or build output

Exception: everything in ui/dist/ (ui/dist/index.mjs) must be committed, because Crew local installs don't build. Never commit secrets.json, data/, node_modules/ or *.log.

## Commit message format (Conventional Commits)
`<type>(<scope>): <what changed, in plain English>`
- types: feat, fix, test, refactor, docs, chore, style, perf
- scope = package or area: app, backend, ui, skill, cron, docs, kiro
- Subject ≤ 72 chars, imperative mood ("add", not "added").
- Add a short body when the why isn't obvious, and reference the spec task, e.g. `Spec: legal-engine, task 2.1`.

Examples:
- `feat(engine): add statutoryInterest with monthly compounding (MSMED-16)`
- `test(engine): add fast-check properties for due date and tax bomb`
- `chore(kiro): add on-save hook to run engine tests`
- `docs(kiro): add legal-engine spec (requirements, design, tasks)`

## Rules
- Commit using the user's existing git identity only. Do not add any `Co-Authored-By` or AI/assistant attribution trailers.
- Stage files explicitly (`git add <paths>`). Avoid `git add .` unless you've checked `git status`.
- Never push, force-push, rebase, amend pushed commits, or delete branches unless the user asks.
- Never rewrite history.
- After committing, tell the user the commit message in one line.