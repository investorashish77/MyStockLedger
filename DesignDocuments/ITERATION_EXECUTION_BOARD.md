# EquityJournal Iteration Execution Board

Last updated: 2026-02-25
Owner: Product + Engineering
Execution mode: Feature-by-feature build, review, test, fix, then mark done

---

## 1. Goal and Delivery Order

Primary goal:
- Stabilize UX in a single dark theme.
- Harden service boundaries so UI and data/AI workflows are decoupled.
- Prepare clean migration path for future web/mobile clients.

Delivery order:
1. Dark-only UX stabilization (highest priority)
2. Service boundary hardening + async job UX
3. Insights quality and filing intelligence reliability
4. Admin operations consolidation + migration readiness

---

## 2. Current State Snapshot

Completed baseline:
- Portfolio, Filings, Insights flows functional.
- SELL + Realized P/L foundation implemented.
- Watchman alert baseline implemented.
- AI review loop process documented (`DesignDocuments/AI_CODE_REVIEW_LOOP.md`).

Known focus areas:
- Remove light theme path and enforce dark-only consistency.
- Normalize popup/menu/list styling in all views.
- Improve async user experience for long-running AI/sync tasks.
- Improve insight freshness and quarter mapping clarity.

---

## 3. Execution Rules (Mandatory)

For every feature task:
1. Implement minimal scoped change.
2. Run local tests relevant to changed area.
3. Run AI code review pass (`scripts/ai_code_review.py`).
4. Fix critical/high findings.
5. Re-run tests and review.
6. Only then mark task `Done`.

Definition of Done (DoD):
- Acceptance criteria met.
- No open critical/high review findings.
- Tests updated and passing.
- Design docs updated where behavior changed.

---

## 4. Sprint Plan (Concrete)

## Sprint 1 (UX Stabilization, Dark-only)
Target window: 2026-02-25 to 2026-03-03

### S1-T1 Remove light theme and toggle
Priority: P0
Status: Done
Scope:
- Remove theme toggle UI and light-theme branching.
- Keep only `theme_dark.qss` as active runtime theme.
- Remove dead light-theme code paths.
Dependencies: None
Acceptance:
- App always launches in dark mode.
- No UI control references light/dark switch.
- No regressions in dialogs/popups.
Progress note:
- Removed header/menu theme toggle controls and forced `theme_dark.qss` in runtime.
- Removed `assets/css/theme_light.qss` to prevent accidental fallback.
- Validated in manual pass: dark-only behavior confirmed.

### S1-T2 Popup/menu consistency sweep
Priority: P0
Status: Done
Scope:
- Ensure `QMenu`, completer popup, dropdown popups, and context menus follow dark tokens globally.
- Verify Add Transaction, Portfolio actions, Filings actions, Insights actions.
Dependencies: S1-T1
Acceptance:
- No low-contrast text/background combinations.
- Hover/active states are readable and consistent.
Progress note:
- Added explicit dark selection states for table items (`selected`, `active`, `inactive`) to prevent light fallback on double-click.
- Refined dark palette tokens for modern contrast across cards, tables, menus, inputs, and list popups.
- Validated in manual pass: popup/menu/theme consistency confirmed.

### S1-T3 Layout polish pass (single-screen clarity)
Priority: P1
Status: Planned
Scope:
- Keep sidebar fixed.
- KPI strip at top.
- Chart + holdings side-by-side.
- Journal notes section below with edit-on-double-click.
- Remove low-value controls/labels that add clutter.
Dependencies: S1-T1
Acceptance:
- Main dashboard follows single-screen hierarchy without overflow on standard laptop size.

### S1-T4 UI consistency audit checklist
Priority: P1
Status: Planned
Scope:
- Standardize font sizes, spacing, button states, table headers, icon sizing.
- Add a QA checklist doc for visual regressions.
Dependencies: S1-T2, S1-T3
Acceptance:
- Checklist completed with no blocker issues.

### S1-T5 ErrorVerification service for parser QA
Priority: P0
Status: Done
Scope:
- Build `ErrorVerificationService` to parse financial parser audit logs.
- Generate tabular report: `Company | Output | Score | Notes`.
- Highlight what was not reviewed (missing metrics, missing quarter, weak parse source, validation flags).
- Add CLI script for repeatable report generation and manual QA handoff.
Dependencies: None
Acceptance:
- Report generated from `logs/equity_tracker.log` with actionable notes per company.
- CLI supports `--since`, `--limit`, and latest-per-company/all-events modes.
- Unit tests cover parsing, scoring, and markdown table output.
Execution:
- Baseline run:
  - `python3 scripts/run_error_verification.py --limit 200`
- Focus by date:
  - `python3 scripts/run_error_verification.py --since "YYYY-MM-DD HH:MM:SS"`
- Keep every parser event (no company dedupe):
  - `python3 scripts/run_error_verification.py --all-events`
- Custom output file:
  - `python3 scripts/run_error_verification.py --out logs/parser_verification_manual.md`
Report columns:
- `Company | Output | Score | Notes`
Manual review use:
- Sort by low score first and review `Notes` to identify missing/incorrect parser extraction.

### Sprint 1 test responsibilities
Codex:
- Update/add UI unit tests where feasible.
- Run compile + non-UI tests in workspace.
You (manual test pass):
- Login flow
- Add Transaction dialog
- Portfolio actions menu
- Filings grid actions
- Insights open/view interactions
- Notification bell visibility and readability

---

## Sprint 2 (Service Boundaries + Async UX)
Target window: 2026-03-04 to 2026-03-11

### S2-T1 Background job framework hardening
Priority: P0
Status: Planned
Scope:
- All long jobs (insight generation, regenerate, missing generation, sync jobs) run asynchronously.
- UI gets non-blocking toast/message: "We will alert once reports are ready."
Dependencies: Sprint 1 complete
Acceptance:
- UI remains responsive during job execution.
- Job failures/successes are surfaced via notifications.

### S2-T2 Notification center v1
Priority: P0
Status: Planned
Scope:
- Bell icon state (unread count).
- Notification panel with click action routing.
- Mark-as-read behavior.
Dependencies: S2-T1
Acceptance:
- Completion of async jobs creates actionable notifications.

### S2-T3 Global sync cursor model (shared data benefit)
Priority: P1
Status: Planned
Scope:
- Announcements sync cursor globally managed to avoid duplicate pulls across users.
- Preserve per-user visibility filters via holdings.
Dependencies: S2-T1
Acceptance:
- Sync calls reduce while portfolio users still see relevant updates.

---

## Sprint 3 (Insights Quality + Filing Intelligence)
Target window: 2026-03-12 to 2026-03-19

### S3-T1 Quarterly insight strictness
Priority: P0
Status: Planned
Scope:
- Quarter labeling fixes (`Qx FYyy` mapping).
- Show only available insights; suppress placeholder rows.
- Remove sentiment from table where not needed.
Dependencies: Sprint 2 complete
Acceptance:
- Insights table contains only meaningful rows for selected quarter.

### S3-T2 Result parser + source selection reliability
Priority: P0
Status: Planned
Scope:
- Improve result-document picking from filings (result + investor presentation support).
- Parser fallback and metric confidence logging.
- Continue using BSE-first data strategy.
Dependencies: S3-T1
Acceptance:
- Higher extraction hit rate for Revenue/PAT/EPS fields.
- Parser logs available for quality review.

### S3-T3 Watchman material-event quality tuning
Priority: P1
Status: Planned
Scope:
- Tight filters for material categories:
  - Order wins
  - Capacity/plant commissioning
  - Acquisitions/JV
  - Fund raise/preferential issue
- 20-word max alert summary rule.
Dependencies: S3-T2
Acceptance:
- Watchman alerts are concise and mostly material (low noise).

---

## Sprint 4 (Admin Ops + Future Platform Readiness)
Target window: 2026-03-20 to 2026-03-27

### S4-T1 Admin operations console
Priority: P1
Status: Planned
Scope:
- Admin-triggered sync controls:
  - Bhavcopy sync
  - Announcements sync (API/CSV mode)
  - Insight regeneration controls
- Execution status with logs.
Dependencies: Sprint 2 complete
Acceptance:
- Admin can operate core data pipelines from UI safely.

### S4-T2 Service boundary extraction map
Priority: P1
Status: Planned
Scope:
- Identify API-ready boundaries for:
  - Portfolio
  - Filings
  - Insights
  - Jobs/notifications
- Draft endpoint contract spec for future FastAPI layer.
Dependencies: S4-T1
Acceptance:
- Documented contracts ready for future React/mobile integration.

---

## Sprint 5 (UI Redesign V2 - Mockup Parity)
Target window: 2026-03-28 to 2026-04-08
Precondition: Sprint 1 P0 dark-theme tasks complete (Done)

### R1 UI Kit + Shell
Priority: P0
Status: In progress
Scope:
- Build reusable UI kit components:
  - StatCard
  - Badge
  - TickerChip
  - SectionPanel
  - FilterPill
  - SortHeader
  - WeightBar
- Restructure shell with:
  - Fixed left sidebar
  - Top utility bar
  - Central scroll content zone
Dependencies: Sprint 1 complete
Acceptance:
- New shell layout matches mock hierarchy and spacing.
- Reusable components adopted in Dashboard sections.
Progress note:
- Added `ui/ui_kit.py` with reusable primitives (`FilterPillButton`, `SectionPanel`, `TickerChip`, `StatCard`, `SortHeaderButton`, `WeightBar`).
- Main shell restructured to sidebar + top utility bar + KPI strip + content stack.

### R2 KPI + Chart + Snapshot Panel
Priority: P0
Status: In progress
Scope:
- Implement KPI strip visual redesign.
- Implement Portfolio Value chart panel.
- Implement right-side holdings snapshot and sector allocation panel.
Dependencies: R1
Acceptance:
- KPI values match existing calculations.
- Chart and snapshot render without blocking refresh flow.
Open dependency:
- Sector accuracy depends on symbol master sector coverage (fallback currently `Unknown`).
Progress note:
- Removed low-value header indicators (`NSE Live`, `Dark Theme`) from top bar.
- Added FY + Last Updated metadata line in header.
- Reworked dashboard chart panel to portfolio-value style (mockup-aligned structure).
- Replaced old `My Holdings` box with `Holding Snapshot`:
  - winners/losers
  - best/worst performer
  - sector allocation donut + legend
- Updated top-row panel ratio to `3:2` and aligned section title typography.
- Temporarily disabled sector donut rendering to improve spacing (will re-enable in sector-focused pass).

### R3 Holdings Table Redesign
Priority: P0
Status: In progress
Scope:
- Modern holdings table:
  - sortable headers
  - ticker chip + asset meta
  - weight bars
  - P&L badges
  - footer totals row
- Preserve double-click transaction drilldown behavior.
Progress note:
- Moved portfolio table into Dashboard and removed Journal Notes from Dashboard.
- Table columns aligned to requested model:
  - `Date, Symbol, Qty, Avg Price, LTP, Investment, Weight, P&L, Return, Notes, Action`
- `P&L` now shows amount only (percent moved to `Return` column).
- `Notes` column now uses a document icon trigger per row.
- Sidebar navigation updated to:
  - `Dashboard, Journal, Filings, Insights, Settings, Help`
- New `Journal` page added and wired.
- `Add Transaction` removed from Portfolio section; moved to sidebar as `New Trade` quick action.

### R4 Dashboard/Header/Navigation Alignment
Priority: P0
Status: In progress
Scope:
- Restore logo visibility in sidebar brand block.
- Remove obsolete page clutter from header/chart sections.
- Keep Dashboard as single operational page for portfolio actions.
Dependencies: R1
Acceptance:
- Logo visible in app shell and window icon.
- No standalone Portfolio menu entry in sidebar.
- Dashboard remains primary surface for holdings + transactions.
Dependencies: R2
Acceptance:
- Table totals and row metrics match Portfolio page calculations.
- Hover/selection/sort interactions remain consistent with dark theme.

### R4 Polish + QA + Regression Hardening
Priority: P1
Status: Planned
Scope:
- Final pass for spacing, typography, contrast, and micro-interactions.
- Regression checks for Dashboard/Portfolio/Filings/Insights navigation.
- Refresh performance sanity check.
Dependencies: R3
Acceptance:
- Visual QA checklist passes.
- No critical regressions in interaction or data display.

### Sprint 5 test responsibilities
Codex:
- Unit/UI behavior tests where feasible for sorting, totals, and component rendering.
- Compile and targeted service/UI test runs.
You (manual signoff):
- Visual parity vs mockup.
- Interaction quality (hover, click, double-click, sort).
- Data correctness in KPI, chart summary, holdings table, and footer totals.

---

## 5. Dependency Matrix (Critical)

- Dark-only enforcement is prerequisite for predictable UI behavior.
- Async job framework is prerequisite for scalable AI workflows.
- Global sync cursor depends on async job orchestration.
- Insight quality improvements depend on reliable filing/source selection.
- Platform migration planning depends on stabilized service boundaries.

---

## 6. Risks and Mitigations

Risk: UI regressions from theme consolidation  
Mitigation: Sprint 1 visual QA checklist + focused manual test matrix.

Risk: LLM cost/rate-limit instability  
Mitigation: Async queue, caching, never-regenerate default policy, admin-only regenerate.

Risk: Filing source inconsistencies (AttachLive vs AttachHis)  
Mitigation: Configurable primary/secondary URL fallback and link validation.

Risk: Parser quality variance across PDF formats  
Mitigation: Structured parser logs + targeted parser regression dataset.

---

## 7. What I Need From You (Most Critical)

1. Sprint-end manual UX signoff with annotated screenshots (top blocker reducer).
2. Priority decisions when tradeoffs arise (speed vs polish for specific screens).
3. Quick validation of real portfolio symbols/filings after each major sync/insight change.

---

## 8. Immediate Next Actions (Start Now)

1. Start Sprint 5 R1 (UI kit + shell structure) based on approved redesign mockup.
2. Deliver first visual checkpoint for sidebar + top bar + content shell before data-panel rewiring.
3. Run test + review loop after each R-phase and capture manual feedback screenshots.
