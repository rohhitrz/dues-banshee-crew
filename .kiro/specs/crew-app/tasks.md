# Implementation Plan: crew-app

## Overview

Build the Dues Banshee Kiro Crew app in this order: icon, Backend, Ladder_Script, UI tooling, Page, skill, manifest, then README and `.gitignore`. Each parent task carries its own required tests. Python code and Python tests use the standard library only (`unittest`; property tests loop over `random.Random(<fixed seed>)` cases). The UI is TypeScript + React, built with Vite and tested with vitest and fast-check. No component computes money, dates, days or legal values, and no test makes a live network call.

## Tasks

- [x] 1. Icon generator and committed icon
  - Files created: `.gitignore`, `scripts/make_icon.py`, `assets/icon.png`, `tests/test_icon.py`
  - [x] 1.0 Write .gitignore
    - Entries `node_modules/`, `secrets.json`, `data/`, `ladder.json`, `*.log`, `.DS_Store`; nothing that ignores `ui/dist`, `dist` or `.kiro`
    - _Requirements: 3.4, 9.1_
  - [x] 1.1 Write the stdlib icon generator and generate the PNG
    - `scripts/make_icon.py` writes a deterministic 512×512 RGB PNG (IHDR bit depth 8, colour type 2, one IDAT of filter-0 rows via `zlib.compress`, IEND, `struct` lengths, `zlib.crc32`) with a near-black background, grey tombstone and amber candle flame (design D7, "Icon generator")
    - Accept an output path argument, default `assets/icon.png`; run it and keep the generated `assets/icon.png` in the repo
    - _Requirements: 2.2_
  - [x] 1.2 Write icon tests
    - `tests/test_icon.py` (unittest): PNG signature; IHDR 512×512, bit depth 8, colour type 2 (opaque, square); running `scripts/make_icon.py` into a temp dir reproduces the committed bytes
    - _Requirements: 2.2, 10.4_

- [x] 2. Backend (`backend/server.py`)
  - Files created: `backend/server.py`, `backend/test_server.py`
  - [x] 2.1 Implement the pure Backend helpers
    - `data_dir(env)`: `$KIROCREW_HOME/apps/<KIROCREW_APP_NAME or dues-banshee>/data` when `KIROCREW_HOME` is set and non-empty, else `~/.kiro/crew/apps/dues-banshee/data` (design D1)
    - `load_secrets(path)`: read-only; returns values only when the file is readable JSON with non-empty string `base_url` (must start with `https://`) and `crew_read_secret`; else `None`; never raises or logs content; never opens `ladder.json`
    - `valid_today(value)`: `re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)`, format only
    - `summary_url(base_url, query)`: `base_url.rstrip("/") + "/api/crew/summary"`, plus `?today=<v>` only when there is exactly one `today` value and it is valid; other keys dropped
    - `map_upstream(status, body)`: summary error mapping table (200+JSON → bytes unchanged; 200 non-JSON, 401, 404, 500, other → 502 with `upstream_error`/`unauthorized`/`not_found`; 503 → 503 `unavailable`)
    - `verify_signature(header, method, target, body, secret, now)`: HMAC-SHA256 over `timestamp:method:target:sha256hex(body)`, ±60 s, `hmac.compare_digest`, fails closed (design D9)
    - `fetch_summary(url, bearer, opener)`: one GET, 20 s timeout, opener that refuses every redirect (design D4, "no redirects")
    - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.10_
    - Notes: also add `__pycache__/` to .gitignore and stage it in this task's commit; stage files explicitly, one commit per parent task is fine.
  - [x] 2.2 Implement the HTTP server and routes
    - `ThreadingHTTPServer` on `127.0.0.1:$PORT`; `GET /health` → `200 {"ok": true}` with no file read and no upstream call
    - `GET /api/summary`: verify `X-KiroCrew-Proxy` against `KIROCREW_PROXY_SECRET` (bad/missing → `401 {"error":"unsigned"}`), load secrets (`503 not_configured` without an upstream call), fetch, map; timeout → `504 timeout`; connection error → `503 unavailable`; unexpected exception → `502 upstream_error`
    - Other paths `404 no_route`; non-GET `405 method_not_allowed`; no ladder route
    - Every error body is exactly `{"error": "<code>"}`; upstream body read only on 200
    - Override `log_message` to write `METHOD PATH STATUS [code]` only; no headers, bodies or secret values in logs or exception text
    - _Requirements: 3.4, 4.1, 4.2, 4.3, 5.8, 5.9, 5.10, 5.11, 11.1, 11.4_
  - [x] 2.3 Write Backend example tests
    - `backend/test_server.py` (unittest, server on an ephemeral loopback port, upstream stubbed via injected opener / patched `urlopen`, no live calls)
    - `/health` 200 with no `Authorization` and no Secrets_File, no upstream call; summary request carries `Authorization: Bearer <crew_read_secret>`
    - 401, 404, 500, 503, timeout, connection error and each `not_configured` variant (missing file, bad JSON, empty `base_url`, empty `crew_read_secret`, `http://` base_url) give their code and HTTP status
    - Upstream 3xx is refused and maps to `upstream_error`; signed request accepted; missing, wrong and stale (>60 s) signatures → `401 unsigned`
    - `data_dir` with and without `KIROCREW_HOME`; only a valid `ladder.json` present → `not_configured`, no upstream call; Secrets_File bytes and mtime unchanged; upstream timeout constant < 30
    - AST scan: every import in `backend/server.py` is in `sys.stdlib_module_names`
    - _Requirements: 1.4, 3.1, 3.2, 3.3, 3.6, 4.1, 4.2, 4.3, 5.1, 5.4, 5.6, 5.8, 5.9, 5.10, 10.1_
  - [x] 2.4 Write Backend property tests (stdlib `random`, fixed seeds, ≥100 cases each, `subTest`, tagged `# Feature: crew-app, Property N`)
    - **Property 1: `today` is forwarded if and only if it is a Valid_Today** (seed 4318; valid `%04d-%02d-%02d` strings and invalid mutations incl. trailing `\n`, Unicode digits, empty, repeated key)
    - **Validates: Requirements 5.2, 5.3, 10.5, 10.6**
    - **Property 2: Successful upstream JSON passes through byte for byte** (random nested JSON with `₹`, `<b>`, quotes, random indent/ensure_ascii, through the full handler)
    - **Validates: Requirements 1.1, 5.5**
    - **Property 3: Every non-success upstream outcome maps to exactly one error object** (all statuses 100–599 except 200, plus ≥100 random non-JSON 200 bodies)
    - **Validates: Requirements 5.6, 5.7, 5.8, 5.11**
    - **Property 4 (Backend half): Secret values never appear in responses or logs** (random secrets across all outcomes; captured stderr and logging)
    - **Validates: Requirements 3.4, 5.11, 10.1**

- [x] 3. Ladder_Script (`cron/daily_ladder.py`)
  - Files created: `cron/daily_ladder.py`, `cron/test_daily_ladder.py`
  - [x] 3.1 Implement the ladder script
    - Duplicate `data_dir` and a `load_secrets` variant needing an https `base_url` and non-empty `ladder_run_secret` (no import from `backend/`)
    - `ladder_credentials(d)`: `secrets.json` first, then `ladder.json`, else `None`; a masked/unreadable/invalid file falls through; which file was used is not logged
    - `run(ctx)`: on `None` print `daily-ladder: failed not_configured`, raise `LadderFailed("not_configured")`, send nothing
    - One `POST {base_url}/api/ladder/run`, no query, empty body, `Authorization: Bearer <ladder_run_secret>`, HTTP timeout 240 s (below cron `timeout` 290 and `timeout_secs` 300), redirects refused, no retry
    - Any response: print `daily-ladder: status <code>`, body never read; non-2xx raises `LadderFailed("status <code>")`; timeout → `failed timeout`; other `URLError`/`OSError` → `failed connection`; raise `from None` with fixed tokens only
    - Imports limited to `json`, `os`, `pathlib`, `re`, `socket`, `urllib.request`, `urllib.error`
    - _Requirements: 1.2, 3.2, 3.3, 3.4, 3.7, 3.8, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9_
  - [x] 3.2 Write ladder example tests
    - `cron/test_daily_ladder.py` (unittest, patched `urlopen`, temp Data_Dir via `KIROCREW_HOME`, no live calls)
    - Exactly one request: `POST`, URL `{base_url}/api/ladder/run` with no query string, `Authorization: Bearer <ladder_run_secret>`
    - Valid `secrets.json` plus a different valid `ladder.json` → `secrets.json` bearer sent; `secrets.json` missing + valid `ladder.json` → `ladder.json` bearer; neither → `failed not_configured`, zero requests; no secret from either file in captured output
    - Timeout and connection error each log one failure line, raise, and send no further request; HTTP timeout constant < 290 and < 300
    - AST scan: every import in `cron/daily_ladder.py` is in `sys.stdlib_module_names`
    - _Requirements: 1.4, 3.7, 3.8, 6.2, 6.3, 6.6, 6.7, 6.8, 6.9, 10.2, 10.7_
  - [x] 3.3 Write ladder property tests (stdlib `random`, fixed seeds, `subTest`, tagged `# Feature: crew-app, Property N`)
    - **Property 4 (Ladder half): Secret values never appear in responses or logs** (≥100 random secrets across status, timeout, connection and not_configured outcomes; log output and exception messages)
    - **Validates: Requirements 3.4, 6.7, 10.2**
    - **Property 5: Ladder log line and run outcome follow the status code** (all statuses 100–599)
    - **Validates: Requirements 6.4, 6.5**
    - **Property 7: Ladder credentials come from secrets.json, then ladder.json, else not_configured** (all 7×7 file-state pairs plus ≥100 random pairs, seed 9001)
    - **Validates: Requirements 3.7, 3.8, 6.8, 10.7**

- [x] 4. UI tooling setup
  - Files created: `ui/package.json`, `ui/package-lock.json`, `ui/vite.config.ts`, `ui/vitest.config.ts`, `ui/tsconfig.json`, `ui/scripts/check-dist.mjs`, `ui/src/test/app-sdk-stub.ts`
  - [x] 4.1 Create the UI package, build and test config
    - Version rule: every dependency in `ui/package.json` is pinned to an exact version (no `^` or `~`), and no chosen version may have been published less than 7 days before 2026-11-20 (i.e. after 2026-11-13). Check publish dates with `npm view <pkg> time` and pick the newest version at least 7 days old. Commit `ui/package-lock.json`.
    - Dev dependencies under that rule: `vite`, `@vitejs/plugin-react`, `typescript`, `vitest`, `jsdom`, `@testing-library/react`, `react`, `react-dom`, `@types/react`, `@types/react-dom`, `fast-check` (design Property 6)
    - `vite.config.ts`: `build.lib` entry `src/index.tsx`, `formats: ["es"]`, `fileName: () => "index.mjs"`, `outDir: "dist"`, `rollupOptions.external` = `react`, `react-dom`, `react/jsx-runtime`, `@kirocrew/app-sdk`, `@kirocrew/app-sdk/ui` (design D6)
    - `vitest.config.ts`: jsdom environment; alias `@kirocrew/app-sdk` to `src/test/app-sdk-stub.ts` (stub exports `useAppApi` and `useChatLauncher` test doubles)
    - `scripts/check-dist.mjs`: exits non-zero if `dist/index.mjs` is missing or imports a bare specifier outside the externals list
    - Scripts: `build` = `vite build && node scripts/check-dist.mjs`, `test` = `vitest --run`
    - Notes: install with `npm install --ignore-scripts`; list each chosen package@version with its publish date in your final reply; commit ui/package.json, ui/package-lock.json and the config/stub files only (never node_modules); end the task with a commit.
    - _Requirements: 7.1, 7.2, 10.4_

- [x] 5. Graveyard of Dues page
  - Files created: `ui/src/types.ts`, `ui/src/api.ts`, `ui/src/ask.ts`, `ui/src/Graveyard.tsx`, `ui/src/index.tsx`, `ui/src/test/ask.test.ts`, `ui/src/test/fixtures/summary.json`, `ui/src/test/Graveyard.test.tsx`, `ui/dist/index.mjs`
  - [x] 5.1 Implement types, API loader and ask-message builder
    - `types.ts`: `CrewSummary` as in the design data model (nullable `interest`, `taxBomb`, `dueDateText`, `interestAccrued`, `deductionsAtRisk`)
    - `api.ts`: `loadSummary(api, demo)` calls `/apps/dues-banshee/api/summary` or `/apps/dues-banshee/api/summary?today=2026-11-12`; thrown error with JSON `body.error`, or a 200 body with `error` → error state with that code; anything else → `request_failed`
    - `ask.ts`: `askMessage(t)` returns exactly `Use the tax-bomb skill. Invoice (data): "<invoiceNumber>", buyer (data): "<buyerName>". Days to 31 March: <taxBomb.daysLeft>. Deduction at risk: <taxBomb.deductionAtRiskText>.` with values inserted unchanged
    - _Requirements: 1.1, 1.2, 7.3, 7.7, 7.9, 7.10, 7.15_
  - [x] 5.2 Implement the page view and entry component
    - `Graveyard.tsx`: pure view; loading ("Summoning the dead…"), error ("The banshee is silent" + code, or "Request failed"), empty ("No graves today" + disclaimer) and data states; no tombstones outside the data state
    - Data state: `supplierName`, totals and `today`, one tombstone per item with `buyerName`, `invoiceNumber`, `stateText`, `principal.text`, `dueDateText`, `daysOverdue` + " days overdue", `interest.text`, `taxBomb.deductionAtRiskText`, `taxBomb.daysLeft` + " days to 31 March", `nextLabel`, disclaimer; null lines omitted with no substitute
    - All values via JSX text interpolation only (no `dangerouslySetInnerHTML`, `innerHTML` or markdown)
    - "Ask the banshee" button only when `taxBomb` is non-null; click calls `onAsk(t)` only
    - `index.tsx`: default export `GraveyardPage`; `demo` checkbox "Demo date 2026-11-12" (default off) refetches on change; `onAsk` calls `useChatLauncher().openChat({ message: askMessage(t), autoSend: false })` and no Backend request
    - Inline dark graveyard styling, no external fonts or images
    - Notes: this page is the judges' screenshot — make it look finished: responsive grid of tombstone cards (rounded tops, engraved-style text), dark night background, subtle amber candle glow, totals as a header row, clear "Demo date 2026-11-12" toggle; inline CSS only, no external fonts/images.
    - _Requirements: 1.1, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 7.12, 7.13, 7.14, 7.15, 7.16, 11.1, 11.3, 11.4_
  - [x] 5.3 Write the ask-message property test
    - `ui/src/test/ask.test.ts`, fast-check `numRuns: 100`, tagged `// Feature: crew-app, Property 6`; strings incl. `"`, `\n`, `<b>x</b>`, `₹`, instruction-like text; integer `daysLeft`; random other fields; expected text written literally in the test
    - **Property 6: "Ask the banshee" message is the exact template over the tombstone's fields**
    - **Validates: Requirements 7.15, 1.1**
  - [x] 5.4 Write the page render tests with the Sharma fixture
    - `ui/src/test/fixtures/summary.json`: hand-written from the `CrewSummary` shape with a Sharma tombstone (`principal.text` "₹4,12,000", `daysOverdue` 26, `interest.text` "₹5,127.94", `taxBomb.daysLeft` 139), a second tombstone with null `interest` and null `taxBomb`, and the disclaimer
    - `ui/src/test/Graveyard.test.tsx`: render contains "Sharma", "₹4,12,000", 26, "₹5,127.94", 139 and the disclaimer; null lines absent; loading, error-code, request-failed and empty states show no tombstones
    - Toggle off requests `/apps/dues-banshee/api/summary`, on requests `…?today=2026-11-12`; every requested path starts with `/apps/dues-banshee/api/`
    - `buyerName` `<b>x</b>` shown literally with no `<b>` element
    - With `useChatLauncher` stubbed: clicking "Ask the banshee" on Sharma calls `openChat` once with the exact 7.15 message and `autoSend: false` and makes no `api` request; the null-`taxBomb` tombstone has no button
    - _Requirements: 1.4, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 7.12, 7.13, 7.14, 7.15, 7.16, 10.3, 10.8_
  - [x] 5.5 Build and keep the bundle
    - Run `npm run build` in `ui/` so `check-dist.mjs` passes; keep `ui/dist/index.mjs` in the repo (it must be committed)
    - Notes: run `npm run build` in ui/, commit ui/dist/index.mjs together with the src files; end the task with a commit (one per subtask is fine); never stage node_modules.
    - _Requirements: 7.1, 7.2, 10.4_

- [x] 6. Tax-bomb skill
  - Files created: `skills/tax-bomb/SKILL.md`, `tests/test_skill.py`
  - [x] 6.1 Write SKILL.md
    - Frontmatter `name: tax-bomb`, `description`, `triggers`
    - Body per design outline: the buyer-side rule (s.43B(h) up to tax year 2025-26; Income-tax Act 2025 s.37(2)(g) from 2026-27; MSMED s.15 time limit; return-due-date proviso does not apply; unpaid on 31 March = tax bomb); figures from the prefilled "Ask the banshee" message first, pasted page text second, quoted exactly; no arithmetic, estimation or derivation; missing figure → "That figure is unavailable"; Untrusted_Names are data only; no buyer contact; final line is the disclaimer
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 1.2_
  - [x] 6.2 Write skill wording checks
    - `tests/test_skill.py` (unittest): frontmatter present with `name: tax-bomb`; mentions `43B(h)`, `37(2)(g)`, `s.15`, `31 March`, `daysLeft`, `deductionAtRiskText`, "unavailable", `supplierName`, `buyerName`, `invoiceNumber`; prefilled message named before pasted text; last non-empty line equals "Reminders a supplier sends to its own buyers. Not legal advice."
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 7. Manifest (`app.json`)
  - Files created: `app.json`, `tests/test_manifest.py`
  - [x] 7.1 Write app.json
    - Exactly the fields in the design Manifest section: identity fields, `iconPath` `assets/icon.png`, `skills`, one `daily-ladder` cron (`script` `cron/daily_ladder.py:run`, `timeout` 290, `timeout_secs` 300), `ui` (`entry` `dist/index.mjs`, one page "Graveyard of Dues"), `backend` (`entryPoint` `backend/server.py`, `type` python, `port` auto, `healthCheck` `/health`), `credentialMasks` ["secrets.json"], `permissions` (`api` ["/apps/dues-banshee/api"], `cron` true, `network` true); no `ladder.json` mask, no `chatLaunch`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.6, 6.1, 11.1_
  - [x] 7.2 Write manifest tests
    - `tests/test_manifest.py` (unittest): every field and value; no extra top-level keys; exactly one cron with the required values and `timeout` < `timeout_secs` − 5; `skills`, `ui/` + `ui.entry`, `backend.entryPoint`, the cron script file and function, and `iconPath` exist
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.1_

- [x] 8. README and .gitignore
  - Files created: `README.md`, `tests/test_repo_files.py`
  - [x] 8.2 Write README.md
    - What the App does; embeds `docs/screenshots/crew-graveyard.png` (Rohit adds the image after install, before the close-out commit)
    - Numbered install steps in order: `kirocrew app install /abs/path`; trust in Settings → Security → Third-party apps; `kirocrew app enable dues-banshee`; create the Secrets_File
    - Secrets_File path `~/.kiro/crew/apps/dues-banshee/data/secrets.json` (or under `$KIROCREW_HOME`) with `{"base_url": "", "crew_read_secret": "", "ladder_run_secret": ""}`
    - `kirocrew app update dues-banshee --source <dir>`; git install as optional
    - Ladder_File: create `data/ladder.json` as `{"base_url": "", "ladder_run_secret": ""}` only if "Run now" on `daily-ladder` logs "failed not_configured" while `secrets.json` is valid; note it is unmasked and holds no `crew_read_secret`
    - Note the scheduler auto-pauses the cron after 5 consecutive failures; check the Schedule page
    - Test commands: `python3 -m unittest discover` for `backend`, `cron`, `tests`; `cd ui && npx vitest --run && npm run build`
    - _Requirements: 3.5, 9.2, 9.3, 9.4, 9.6_
  - [x] 8.3 Write repo-file tests
    - `tests/test_repo_files.py` (unittest): `.gitignore` has the six entries and none matching `ui/dist`, `dist` or `.kiro`; README has the four install steps in order, the empty secrets example, the update command, the optional git install, the empty `ladder.json` example with the "failed not_configured" condition, and the screenshot path; `LICENSE` exists and is MIT
    - _Requirements: 3.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

## Notes

- No task is optional; every test sub-task is required (Req 1.3).
- No checkpoint tasks: Rohit runs the checks himself.
- The design puts `.gitignore`, skill and README checks in `tests/test_manifest.py`; this plan splits them into `tests/test_icon.py`, `tests/test_skill.py` and `tests/test_repo_files.py` so each task owns its test file.
- Not automated: Req 2.7 (install validation on Kiro Crew 0.13.0) and the screenshot file in Req 9.2 are checked by Rohit during the manual install.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1", "3.1", "4.1", "6.1"] },
    { "id": 1, "tasks": ["1.2", "2.2", "3.2", "5.1", "6.2"] },
    { "id": 2, "tasks": ["2.3", "3.3", "5.2", "5.3"] },
    { "id": 3, "tasks": ["2.4", "5.4"] },
    { "id": 4, "tasks": ["5.5"] },
    { "id": 5, "tasks": ["7.1"] },
    { "id": 6, "tasks": ["7.2"] },
    { "id": 7, "tasks": ["8.1", "8.2"] },
    { "id": 8, "tasks": ["8.3"] }
  ]
}
```
