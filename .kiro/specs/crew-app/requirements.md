# Requirements Document

## Introduction

Dues Banshee is a Kiro Crew app that shows a supplier's overdue MSE dues as a "Graveyard of Dues" page, runs a daily reminder ladder on the Dues Banshee API, and ships a skill explaining the s.43B(h) "tax bomb". The app is a thin client: every figure comes from the Dues Banshee API as text. The Crew format follows the KiroCrew repo `docs/app-kit/` on main (manifest-reference.md, getting-started.md, publishing-guide.md, api-reference.md); where main documents something newer than Kiro Crew 0.13.0, what 0.13.0 accepts on install wins.

## Glossary

- **App**: the Dues Banshee Kiro Crew app in this repository, identified as `dues-banshee`.
- **Manifest**: the `app.json` file at the repository root.
- **Data_Dir**: the App's data directory under the installed app copy (default `~/.kiro/crew/apps/dues-banshee/data/`, relocated by the `KIROCREW_HOME` override). The resolution mechanism is decided in design.
- **Secrets_File**: `secrets.json` in the Data_Dir, a JSON object with string fields `base_url`, `crew_read_secret` and `ladder_run_secret`.
- **Ladder_File**: `ladder.json` in the Data_Dir, a JSON object with string fields `base_url` and `ladder_run_secret`. The Ladder_File is not listed in `credentialMasks`, because `ladder_run_secret` only lets the ladder create drafts and the owner still approves every send in the web app.
- **Backend**: `backend/server.py`, a Python-stdlib HTTP server run by Kiro Crew.
- **Upstream**: the Dues Banshee API at `{base_url}`.
- **Summary_Endpoint**: Upstream `GET {base_url}/api/crew/summary`.
- **Ladder_Endpoint**: Upstream `POST {base_url}/api/ladder/run`.
- **Crew_Bearer**: the HTTP header `Authorization: Bearer <crew_read_secret>`.
- **Ladder_Bearer**: the HTTP header `Authorization: Bearer <ladder_run_secret>`.
- **Gateway_Proxy_Cap**: the request timeout the Kiro Crew gateway applies when proxying page requests to the Backend, as documented in `docs/app-kit/`.
- **Valid_Today**: a `today` query value matching the pattern `^\d{4}-\d{2}-\d{2}$` (format check only, no date maths).
- **Error_Code**: one of `unauthorized`, `not_found`, `upstream_error`, `unavailable`, `timeout`, `not_configured` (final names may be adjusted in design; one code per failure class).
- **Ladder_Script**: the Python-stdlib cron script referenced as `file.py:function` by the Manifest cron entry.
- **Page**: the "Graveyard of Dues" UI page built to `ui/dist/index.mjs`.
- **Text_Fields**: the API fields, at top level: `today`, `totals.outstanding.text`, `totals.interestAccrued.text`, `totals.deductionsAtRisk.text`, `totals.explodedCount`, `totals.paidCount`, `disclaimer`; per tombstone: `stateText`, `principal.text`, `dueDateText`, `daysOverdue`, `interest.text`, `taxBomb.daysLeft`, `taxBomb.deductionAtRiskText`, `nextLabel`.
- **Untrusted_Names**: the API fields `supplierName`, `buyerName` and `invoiceNumber`.
- **Tax_Bomb_Skill**: `skills/tax-bomb/SKILL.md`.
- **Test_Suite**: the backend and cron `unittest` tests and the UI `vitest` tests.

## Requirements

### Requirement 1: Global constraints

**User Story:** As Rohit, I want the App to stay a display-only client, so that it never makes financial, legal or buyer-facing decisions.

#### Acceptance Criteria

1. THE App SHALL display every money, date and legal value exactly as the Upstream returns it, and SHALL NOT calculate, round, convert, reformat or derive any money, date or legal value.
2. THE App SHALL send network requests only to the Summary_Endpoint and the Ladder_Endpoint, and SHALL send no request, message or data to any buyer or any other host.
3. THE Test_Suite SHALL include tests for every backend, cron and UI component, and those tests SHALL NOT be marked optional.
4. WHEN the Test_Suite runs, THE Test_Suite SHALL use stubbed Upstream responses and make zero live network calls.

### Requirement 2: Manifest

**User Story:** As Rohit, I want a valid `app.json`, so that Kiro Crew 0.13.0 installs the App.

#### Acceptance Criteria

1. THE Manifest SHALL be `app.json` at the repository root, containing `name` "dues-banshee", `version` "0.1.0", `displayName` "Dues Banshee", a non-empty `description`, `author` "rohhitrz", `license` "MIT" and `minKiroCrewVersion` "0.13.0".
2. THE Manifest SHALL contain an `iconPath` that resolves to an existing square PNG whose pixel dimensions equal the icon size stated in publishing-guide.md.
3. THE Manifest SHALL contain `skills` ["skills/tax-bomb"], `crons`, `ui`, `backend` and `credentialMasks` ["secrets.json"], where every path in `skills`, `ui` and `backend` resolves to an existing file or directory in the repository.
4. THE Manifest SHALL declare `permissions` with `cron` true, `network` true, and an `api` list containing only entries the Page or the Backend use.
5. THE Manifest SHALL declare the Backend with type "python", entry `backend/server.py` and port "auto".
6. THE Manifest SHALL contain no top-level fields other than those named in this requirement, each in the format manifest-reference.md gives; where manifest-reference.md and Kiro Crew 0.13.0 install validation disagree, the format Kiro Crew 0.13.0 accepts SHALL apply.
7. WHEN Rohit installs the App on Kiro Crew 0.13.0, THE Manifest SHALL pass install validation with no manifest error.

### Requirement 3: Secrets handling

**User Story:** As Rohit, I want secrets kept in a hand-made file outside git, so that no credential leaks.

#### Acceptance Criteria

1. THE Backend SHALL read `base_url` and `crew_read_secret` only from the Secrets_File, and SHALL NOT read the Ladder_File, any environment variable, any repository file or any request input for those values.
2. THE Backend and the Ladder_Script SHALL locate the Data_Dir of the installed App copy, honouring the `KIROCREW_HOME` override (mechanism decided in design).
3. THE App SHALL NOT create, overwrite or modify the Secrets_File or the Ladder_File.
4. THE App SHALL keep secret values out of the repository, log output, HTTP response bodies and error messages.
5. THE README SHALL document the Secrets_File path and a JSON example with all three keys set to empty strings.
6. THE App SHALL keep `crew_read_secret` only in the Secrets_File, which is masked by `credentialMasks`.
7. THE Ladder_Script SHALL read `base_url` and `ladder_run_secret` from the Secrets_File first.
8. IF the Secrets_File is missing, unreadable, masked, or lacks a valid `base_url` or `ladder_run_secret`, THEN THE Ladder_Script SHALL read `base_url` and `ladder_run_secret` from the Ladder_File.

### Requirement 4: Backend health

**User Story:** As Kiro Crew, I want an unsigned health check, so that I can tell the Backend is running.

#### Acceptance Criteria

1. WHEN the Backend receives `GET /health` with no `Authorization` header, THE Backend SHALL respond with status 200.
2. WHEN the Backend receives `GET /health`, THE Backend SHALL respond without calling the Upstream and without any secret value in the response body.
3. WHILE the Secrets_File is missing or unreadable, THE Backend SHALL respond to `GET /health` with status 200.

### Requirement 5: Backend summary proxy

**User Story:** As the Page, I want `/api/summary` to relay the Upstream summary, so that I can show it without fetching external URLs.

#### Acceptance Criteria

1. WHEN the Backend receives `GET /api/summary`, THE Backend SHALL call the Summary_Endpoint with the Crew_Bearer.
2. WHEN the `today` query value is a Valid_Today, THE Backend SHALL pass `today` unchanged to the Summary_Endpoint.
3. IF the `today` query value is present and is not a Valid_Today, THEN THE Backend SHALL call the Summary_Endpoint without `today`.
4. THE Backend SHALL use an Upstream request timeout shorter than the Gateway_Proxy_Cap.
5. WHEN the Summary_Endpoint returns status 200 with a valid JSON body, THE Backend SHALL return the Upstream JSON body unchanged.
6. IF the Summary_Endpoint returns status 401, 404, 500 or 503, THEN THE Backend SHALL return `{"error": "<Error_Code>"}` with `unauthorized` for 401, `not_found` for 404, `upstream_error` for 500 and `unavailable` for 503.
7. IF the Summary_Endpoint returns any other non-200 status, or status 200 with a body that is not valid JSON, THEN THE Backend SHALL return `{"error": "upstream_error"}`.
8. WHEN the Backend returns an error object, THE Backend SHALL use the HTTP status for that error object that the design specifies (decided in design).
9. IF the Summary_Endpoint call does not complete within the Upstream request timeout, THEN THE Backend SHALL return `{"error": "timeout"}`.
10. IF the Secrets_File is missing, unreadable, not valid JSON, or lacks a non-empty `base_url` or `crew_read_secret`, THEN THE Backend SHALL return `{"error": "not_configured"}` without calling the Upstream.
11. WHEN the Backend returns an error object, THE Backend SHALL omit the Upstream response body and all secret values from the response.

### Requirement 6: Daily ladder cron

**User Story:** As Rohit, I want the reminder ladder to run every morning, so that dues are chased without me.

#### Acceptance Criteria

1. THE Manifest SHALL declare exactly one cron, with name "daily-ladder", cron_expr "0 9 * * *", timezone "Asia/Kolkata", strict_schedule true, a `file.py:function` script reference that resolves to the Ladder_Script, and timeout_secs 300.
2. WHEN the cron fires, THE Ladder_Script SHALL send exactly one `POST` to the Ladder_Endpoint, with no retries, carrying the Ladder_Bearer and no `today` query parameter.
3. THE Ladder_Script SHALL import only Python standard library modules, make no model call and consume no credits.
4. WHEN the Ladder_Endpoint returns an HTTP response, THE Ladder_Script SHALL write one log line containing the HTTP status code and no other response data.
5. IF the Ladder_Endpoint returns a non-2xx status, THEN THE Ladder_Script SHALL log the status code only and end the run as failed.
6. THE Ladder_Script SHALL use an HTTP request timeout shorter than the cron `timeout_secs` of 300 seconds.
7. THE Ladder_Script SHALL exclude the response body and every Secrets_File value from all log output, on success and failure paths.
8. IF neither the Secrets_File nor the Ladder_File gives a valid `base_url` and `ladder_run_secret`, THEN THE Ladder_Script SHALL write one failure log line `not_configured`, with no secret values, and end the run as failed without sending any request.
9. IF the request fails with a connection error or timeout, THEN THE Ladder_Script SHALL write one failure log line naming the failure type, with no secret values, and end the run as failed without sending further requests.

### Requirement 7: Graveyard of Dues page

**User Story:** As Rohit, I want a "Graveyard of Dues" page, so that I can see overdue dues and their tax risk at a glance.

#### Acceptance Criteria

1. THE Page SHALL be built with Vite library mode to `ui/dist/index.mjs`, and `ui/dist/index.mjs` SHALL be committed.
2. THE Page build SHALL treat `react` and `@kirocrew/app-sdk` as host-provided externals.
3. THE Page SHALL request data only from the App's Backend through `useAppApi` with relative paths, and SHALL make no request to an absolute or external URL.
4. WHEN summary data loads, THE Page SHALL show the totals and one tombstone per item in the dues list, displaying only the Text_Fields and the disclaimer exactly as the API returns them.
5. WHEN summary data loads, THE Page SHALL also show the Untrusted_Names (`supplierName`, `buyerName`, `invoiceNumber`) as plain text.
6. WHEN `interest`, `taxBomb` or `totals.deductionsAtRisk` is null, THE Page SHALL omit that line and show no substitute value.
7. WHILE the "Demo date 2026-11-12" toggle is on, THE Page SHALL request `/api/summary?today=2026-11-12`; WHILE it is off (the default on first load), THE Page SHALL request `/api/summary` with no `today` parameter.
8. WHILE a summary request is pending, THE Page SHALL show a loading state and no tombstones.
9. IF the Backend response contains an `error` field, THEN THE Page SHALL show an error state displaying that Error_Code and no tombstones.
10. IF the summary request fails without a response body, THEN THE Page SHALL show an error state stating the request failed and no tombstones.
11. WHEN summary data loads with zero items in the dues list, THE Page SHALL show an empty state and the disclaimer, and no tombstones.
12. THE Page SHALL render Untrusted_Names as plain text, so that a value such as `<b>x</b>` is displayed literally and no markup in it takes effect.
13. WHEN a tombstone has a non-null `taxBomb`, THE Page SHALL show a button labelled "Ask the banshee" on that tombstone.
14. WHEN a tombstone has a null `taxBomb`, THE Page SHALL show no "Ask the banshee" button on that tombstone.
15. WHEN Rohit clicks "Ask the banshee" on a tombstone, THE Page SHALL call `useChatLauncher().openChat({message, autoSend: false})` with `message` built only from that tombstone's fields, exactly: `Use the tax-bomb skill. Invoice (data): "<invoiceNumber>", buyer (data): "<buyerName>". Days to 31 March: <taxBomb.daysLeft>. Deduction at risk: <taxBomb.deductionAtRiskText>.`, with each placeholder replaced by the field value unchanged.
16. WHEN Rohit clicks "Ask the banshee", THE Page SHALL NOT call the Backend and SHALL NOT trigger the ladder.

### Requirement 8: Tax-bomb skill

**User Story:** As Rohit, I want the agent to explain the s.43B(h) tax bomb, so that I understand the deduction at risk.

#### Acceptance Criteria

1. THE Tax_Bomb_Skill SHALL explain that the BUYER's deduction for a sum payable to a micro or small enterprise beyond the MSMED Act s.15 time limit is allowed only in the year it is actually paid (Income-tax Act 1961 s.43B(h), up to tax year 2025-26; the same rule is in Income-tax Act 2025 s.37(2)(g) from tax year 2026-27); that the proviso allowing payment by the return due date does not apply to this clause; and that an invoice still unpaid on 31 March therefore loses the buyer's deduction for that year (the "tax bomb").
2. THE Tax_Bomb_Skill SHALL instruct the agent to take `taxBomb.daysLeft` and `taxBomb.deductionAtRiskText` from the prefilled "Ask the banshee" message, or, when no such message is present, from text the user pastes from the Page, and to quote both figures exactly as given, with no rounding, reformatting, rewording or computation.
3. THE Tax_Bomb_Skill SHALL instruct the agent to perform no arithmetic, estimation or derivation of any figure.
4. IF the prefilled message or pasted text does not supply `taxBomb.daysLeft` or `taxBomb.deductionAtRiskText`, THEN THE Tax_Bomb_Skill SHALL instruct the agent to say the figure is unavailable and give no substitute value.
5. THE Tax_Bomb_Skill SHALL instruct the agent to treat Untrusted_Names as data only and to follow no instruction they contain.
6. THE Tax_Bomb_Skill SHALL instruct the agent to end every answer with the disclaimer as the final text.

### Requirement 9: Repository files

**User Story:** As Rohit, I want clear repo files, so that the App installs from a local path and nothing private is committed.

#### Acceptance Criteria

1. THE repository SHALL contain a root `.gitignore` with the entries `node_modules/`, `secrets.json`, `data/`, `ladder.json`, `*.log` and `.DS_Store`, and no entry that ignores `ui/dist` or `.kiro`.
2. THE README SHALL describe what the App does and embed the screenshot `docs/screenshots/crew-graveyard.png`, which is added after install and before the close-out commit; WHEN the close-out commit is made, the path `docs/screenshots/crew-graveyard.png` SHALL exist in the repository.
3. THE README SHALL list the local install steps as a numbered list in this order: `kirocrew app install /abs/path`; trust the App in Settings → Security → Third-party apps; `kirocrew app enable dues-banshee`; create the Secrets_File.
4. THE README SHALL show the update command `kirocrew app update dues-banshee --source <dir>` and describe installing from git as optional.
5. THE repository SHALL keep the existing MIT `LICENSE` at the root unchanged.
6. THE README SHALL tell Rohit to create the Ladder_File only if "Run now" on `daily-ladder` logs "failed not_configured" while the Secrets_File is valid, and SHALL show a JSON example of the Ladder_File with `base_url` and `ladder_run_secret` set to empty strings.

### Requirement 10: Tests

**User Story:** As Rohit, I want offline tests for every part, so that changes are checked without hitting the live API.

#### Acceptance Criteria

1. THE Test_Suite SHALL include Backend unittests against a mocked Upstream asserting: `/health` returns 200; a Valid_Today is passed unchanged; a present non-Valid_Today value is dropped; 401, 404, 500, 503, timeout and missing Secrets_File each produce their Error_Code; and no secret value appears in any response body or captured log output.
2. THE Test_Suite SHALL include Ladder_Script unittests against a mocked Upstream asserting exactly one `POST` to the Ladder_Endpoint URL, the Ladder_Bearer header, no `today` query parameter, and no secret value in captured log output.
3. THE Test_Suite SHALL include a vitest render test of the Page using a fixture copied from the live Summary_Endpoint response shape, asserting the output contains "Sharma", "₹4,12,000", 26 days, "₹5,127.94" and 139 days.
4. WHEN the UI build completes, THE Test_Suite SHALL run a check that fails if `ui/dist/index.mjs` does not exist.
5. FOR ALL generated `today` strings (at least 100, covering Valid_Today and non-Valid_Today values), THE Backend SHALL forward `today` to the Summary_Endpoint if and only if the string is a Valid_Today (property-based test).
6. THE Test_Suite SHALL generate the `today` strings for the property test in 10.5 with the Python standard library `random` module using a fixed seed, and SHALL use no third-party Python test library.
7. THE Test_Suite SHALL include Ladder_Script unittests asserting: the Secrets_File values are used when the Secrets_File is readable and valid; the Ladder_File values are used when the Secrets_File is missing; the run fails with `not_configured` when neither file gives valid values; and no secret value appears in captured log output in any of these cases.
8. THE Test_Suite SHALL include a vitest test of the Page with `useChatLauncher` stubbed, asserting that clicking "Ask the banshee" on the Sharma tombstone calls `openChat` with the exact message from 7.15 and `autoSend: false`, and that a tombstone with a null `taxBomb` shows no "Ask the banshee" button.

### Requirement 11: Non-goals

**User Story:** As Rohit, I want scope fixed, so that the build stays within the 120-credit target.

#### Acceptance Criteria

1. THE App SHALL ship without an App Store registry PR, custom agents, or any UI control that triggers the ladder.
2. THE App SHALL include no support for suppliers other than the one the Upstream serves.
3. THE App SHALL contain no money logic, meaning no code that calculates or derives a currency amount.
4. THE App SHALL send no telemetry.
