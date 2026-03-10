# Phase 1 Design: Integrated Portfolio via MCP Providers

## 1) Objective
Add a new sidebar menu **Integrated Portfolio** that lets a user view holdings from multiple broker platforms through MCP servers in one screen.

Phase 1 scope is **read-only holdings aggregation** (no order placement).

Target providers for Phase 1:
- Zerodha MCP: `https://mcp.kite.trade/mcp`
- Groww MCP: `https://mcp.groww.in/mcp`

References:
- Zerodha MCP repository: `https://github.com/zerodha/kite-mcp-server`
- Zerodha MCP README: `https://github.com/zerodha/kite-mcp-server/blob/master/README.md`
- Groww MCP page: `https://groww.in/updates/groww-mcp`
- Community Groww MCP server: `https://github.com/arkapravasinha/groww-mcp-server`

---

## 2.5 Groww Provider Options (Decision)

For Groww integration we have two viable modes:

### Option A: Official remote MCP endpoint (recommended for Phase 1)
- Endpoint: `https://mcp.groww.in/mcp`
- Pros:
  - Official channel by broker platform.
  - Lower maintenance overhead in our app.
  - Best fit for Phase 1 read-only holdings use case.
- Cons:
  - Toolset/auth behavior depends on remote platform policy and may evolve.

### Option B: Self-hosted community MCP server (advanced/optional)
- Repository: `arkapravasinha/groww-mcp-server`
- Observed capabilities include holdings, positions, orders, margins, market data, and technical-analysis tools.
- Pros:
  - More control over tooling surface and runtime.
  - Possible faster path for richer tool coverage if needed later.
- Cons:
  - Not official broker-maintained server.
  - Requires Node runtime + deployment/monitoring ownership.
  - Additional security/compliance review required before production use.

### Phase 1 decision
- Use **Option A** as default.
- Keep adapter abstraction so **Option B** can be plugged in later behind config without UI redesign.

---

## 2) User Experience Goals

### 2.1 Navigation
- Add sidebar item: **Integrated Portfolio**
- Clicking it opens a dedicated center view.

### 2.2 Screen Layout
- Sectioned by provider, per connected account.
- Example:
  - **Zerodha**
    - Holding 1
    - Holding 2
  - **Groww**
    - Holding 1
    - Holding 2

### 2.3 Loading Behavior
- Render last synced data immediately.
- Start background refresh per provider.
- Show per-provider sync state:
  - `Connected / Not connected`
  - `Last synced: <timestamp>`
  - `Sync in progress / failed / complete`

### 2.4 Readability
- Each provider in separate bordered card/panel.
- Holdings as table rows/cards with consistent dark-theme styling.

---

## 3) Functional Scope (Phase 1)

### In Scope
- Multi-provider MCP configuration from a dedicated config file.
- Per-user provider connection state.
- Fetch holdings from all enabled providers for that user.
- Normalize holdings into common schema.
- Display holdings grouped by provider.
- Manual sync action + background sync on view open.

### Out of Scope (Phase 1)
- Buy/Sell order placement via MCP.
- NLP trade execution.
- Advanced portfolio Q&A chat.
- Cross-broker realized P&L reconciliation.

---

## 4) Proposed Architecture

### 4.1 Components
- `IntegratedPortfolioView` (UI layer)
- `IntegratedPortfolioService` (orchestrator)
- `MCPProviderRegistry` (loads providers from config)
- Provider adapters:
  - `ZerodhaMCPAdapter`
  - `GrowwMCPAdapter`
- `BackgroundJobService` integration for non-blocking sync
- DB persistence for connections, snapshots, and sync runs

### 4.2 Data Flow
1. User opens **Integrated Portfolio** view.
2. UI loads latest cached holdings from DB.
3. Background sync queued for each connected provider.
4. Adapter calls MCP server tools and returns normalized holdings.
5. DB upsert snapshot rows.
6. UI refresh callback updates provider section(s).

---

## 5) Configurability Design

Create config file:
- `config/mcp_providers.yaml`

Example:
```yaml
providers:
  - key: zerodha
    name: Zerodha
    enabled: true
    endpoint: "https://mcp.kite.trade/mcp"
    mode: "read_only"
    auth:
      type: "oauth_session"
    tools:
      holdings: "get_holdings"
      positions: "get_positions"

  - key: groww
    name: Groww
    enabled: true
    endpoint: "https://mcp.groww.in/mcp"
    mode: "read_only"
    auth:
      type: "session"
    tools:
      holdings: "get_holdings"
```

Rules:
- Add/remove providers without code changes in core UI.
- Provider-specific tool names configurable.
- Disable provider globally by config flag.

---

## 6) Database Design (Phase 1)

### 6.1 `user_mcp_connections`
Tracks user-provider connectivity.
- `connection_id` (PK)
- `user_id`
- `provider_key` (zerodha/groww/...)
- `account_label`
- `status` (`CONNECTED`, `DISCONNECTED`, `ERROR`)
- `auth_metadata_json` (non-secret metadata)
- `last_connected_at`
- `last_error`

### 6.2 `integrated_holdings_snapshot`
Normalized holdings snapshot rows.
- `snapshot_id` (PK)
- `user_id`
- `provider_key`
- `account_label`
- `external_holding_id` (provider symbol/id ref)
- `symbol`
- `instrument_name`
- `exchange`
- `quantity`
- `avg_price`
- `ltp`
- `market_value`
- `pnl`
- `currency`
- `as_of_ts`
- `synced_at`
- unique key: (`user_id`, `provider_key`, `account_label`, `external_holding_id`, `as_of_ts`)

### 6.3 `integrated_sync_runs`
Per provider sync audit.
- `run_id` (PK)
- `user_id`
- `provider_key`
- `started_at`
- `completed_at`
- `status` (`SUCCESS`, `FAILED`, `PARTIAL`)
- `rows_fetched`
- `error_message`

---

## 7) Service Contracts

### 7.1 Adapter Interface
```python
class BaseMCPAdapter:
    def validate_connection(self, user_id: int) -> dict: ...
    def fetch_holdings(self, user_id: int) -> list[dict]: ...
    def fetch_positions(self, user_id: int) -> list[dict]: ...
```

### 7.2 Normalized Holding Shape
```python
{
  "provider_key": "zerodha",
  "account_label": "Primary",
  "external_holding_id": "NSE:INFY",
  "symbol": "INFY",
  "instrument_name": "Infosys Ltd",
  "exchange": "NSE",
  "quantity": 10,
  "avg_price": 1450.0,
  "ltp": 1520.0,
  "market_value": 15200.0,
  "pnl": 700.0,
  "currency": "INR",
  "as_of_ts": "2026-03-02T10:30:00"
}
```

---

## 8) UI Design Notes

### 8.1 New View
- File: `ui/integrated_portfolio_view.py`
- Add to `QStackedWidget` in `ui/main_window.py`
- Add sidebar button `Integrated Portfolio`

### 8.2 View Sections
- Top controls:
  - `Refresh All`
  - connection status chips
- Provider panels:
  - title, status, last sync
  - holdings table per provider

### 8.3 Table Columns (Phase 1)
- Symbol
- Instrument
- Qty
- Avg Price
- LTP
- Market Value
- P&L
- Updated At

---

## 9) Security & Compliance Notes
- Do not store provider secrets in plain text DB.
- Keep secrets in environment/OS keychain where possible.
- Persist only minimal auth metadata needed for session UX.
- Log sync failures without leaking secrets/tokens.

---

## 10) What Is Needed From User vs Codex

### Needed From You
1. Confirm provider list for Phase 1 (`zerodha`, `groww`).
2. Confirm per-provider login/auth expected user flow in app.
3. Provide any provider-specific access prerequisites (if required).
4. Confirm final table columns and grouping style in UI.

### Codex Can Implement
1. New sidebar menu + new stacked view.
2. Config file + provider registry.
3. DB schema additions + migrations.
4. MCP adapter abstraction + Zerodha/Groww adapter scaffolding.
5. Background sync and cached rendering.
6. Unit/integration tests for service + DB + UI wiring.

### Cannot Fully Guarantee in Phase 1
1. Uniform auth behavior across providers without provider-specific constraints.
2. Real-time tick-level consistency across all providers.
3. Trading operations and NLP execution (deferred to later phases).

---

## 11) Implementation Plan (Execution Tasks)

### Task A: Foundation
- Add `config/mcp_providers.yaml`
- Build `MCPProviderRegistry`
- Add DB tables + migration scripts

### Task B: Service Layer
- Create `services/integrated_portfolio_service.py`
- Create adapter interface + Zerodha/Groww adapters
- Implement normalize + upsert snapshot

### Task C: UI Layer
- Create `ui/integrated_portfolio_view.py`
- Add sidebar item and view routing
- Render grouped provider holdings

### Task D: Background Sync
- Queue provider sync jobs on view open
- Add sync status updates and failure handling

### Task E: Testing
- DB migration tests
- Adapter contract tests (mocked MCP responses)
- Service aggregation tests
- UI smoke tests for menu + grouped render

---

## 12) Acceptance Criteria (Phase 1)
1. User can open **Integrated Portfolio** from sidebar.
2. View shows provider sections for all enabled+connected providers.
3. Each provider displays normalized holdings rows.
4. Last synced timestamp visible per provider.
5. Refresh does not block UI; failures are isolated per provider.
6. Data persists and loads on next login without re-fetch delay.
