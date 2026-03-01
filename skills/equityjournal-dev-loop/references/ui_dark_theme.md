# UI Dark Theme Reference

## Primary Constraints

- Treat dark theme as default UX baseline.
- Keep visual consistency across dialogs, menus, completers, dropdowns, and table selections.
- Avoid light fallback states on focus, selection, or double-click.

## Primary Files

- `assets/css/theme_dark.qss`
- `ui/main_window.py`
- `ui/dashboard_view.py`
- `ui/journal_view.py`
- `ui/ui_kit.py`

## Implementation Rules

- Reuse existing object names and style tokens when possible.
- Keep sidebar behavior predictable (always visible).
- Keep hierarchy clear: top utility bar, KPI strip, main dashboard sections.
- Keep action buttons with consistent idle/hover/active states.
- Keep portfolio operations on Dashboard as the primary surface.
- Keep dashboard root opaque (non-transparent) to avoid paint bleed/ghost artifacts.

## Dark Tokens (Current Baseline)

- Root background: `#0E1117`
- Surface panel: `#101A27` to `#161D27`
- Border: `rgba(116, 142, 179, 0.20)`
- Primary blue gradient: `#3D5AFE -> #60A5FA`
- Gain text: `#34D399`
- Loss text: `#F87171`
- Secondary text: `#8FA2B8`

## Layout Standards

- Sidebar menu order:
  - `Dashboard`, `Journal`, `Filings`, `Insights`, `Settings`, `Help`
- Sidebar quick action:
  - pill-style `New Trade` button below menu items
- Header metadata format:
  - `FY YYYY-YY · Last updated: DD Mon YYYY, HH:MM AM/PM`
- Do not render legacy top filter pills in the header.
- Dashboard structure:
  - Chart/value panel + snapshot panel (top row, width ratio `3:2`)
  - Portfolio table (bottom row)
- Journal content lives in `Journal` view, not Dashboard.
- Top KPI cards should stay compact:
  - two-line structure: title, then value with inline `%`
  - reduced font size to preserve table space.

## Manual Verification Checklist

- Login/registration screens follow dark styling.
- Add Transaction dialog follows active theme styles.
- Portfolio action menus and symbol search popup follow dark styles.
- Filings/Insights popups and row selection colors stay readable.
- Sidebar logo is visible in dark mode.
- Header does not show obsolete labels like `NSE Live` or `Dark Theme`.
- Dashboard table columns match product contract:
  - `Date, Symbol, Qty, Avg Price, LTP, Investment, Weight, P&L, Return, Notes, Action`
