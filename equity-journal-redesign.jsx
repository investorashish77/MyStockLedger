import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const portfolioData = [
  { ticker: "MTARTECH", name: "MTAR Technologies Ltd.", qty: 10, avg: 2500.32, current: 3681.50, invested: 25003.20, weight: 2.4, pl: 11811.80, plPct: 47.24, sector: "Defence" },
  { ticker: "NAVINFLUOR", name: "Navin Fluorine Intl. Ltd.", qty: 21, avg: 6828.00, current: 6430.50, invested: 143388.00, weight: 8.7, pl: -8347.50, plPct: -5.82, sector: "Chemicals" },
  { ticker: "SOLARA", name: "Solara Active Pharma Sciences", qty: 200, avg: 501.57, current: 472.70, invested: 100314.00, weight: 6.1, pl: -5774.00, plPct: -5.76, sector: "Pharma" },
  { ticker: "GOODLUCK", name: "Goodluck India Ltd.", qty: 200, avg: 1088.40, current: 1203.80, invested: 217680.00, weight: 15.5, pl: 23080.01, plPct: 10.60, sector: "Steel" },
  { ticker: "HIKAL", name: "Hikal Ltd.", qty: 1000, avg: 213.12, current: 200.89, invested: 213120.00, weight: 12.9, pl: -12230.00, plPct: -5.74, sector: "Chemicals" },
  { ticker: "JAMNAAUTO", name: "Jamna Auto Industries Ltd.", qty: 800, avg: 123.29, current: 143.75, invested: 98632.00, weight: 7.4, pl: 16368.00, plPct: 16.60, sector: "Auto" },
  { ticker: "HONASA", name: "Honasa Consumer Ltd.", qty: 100, avg: 309.30, current: 304.20, invested: 30930.00, weight: 2.0, pl: -510.00, plPct: -1.65, sector: "FMCG" },
  { ticker: "CCL", name: "CCL Products (India) Ltd.", qty: 53, avg: 953.98, current: 1036.40, invested: 50560.94, weight: 3.5, pl: 4368.26, plPct: 8.64, sector: "FMCG" },
  { ticker: "EDELWEISS", name: "Edelweiss Financial Services", qty: 1000, avg: 106.27, current: 118.30, invested: 106270.00, weight: 7.6, pl: 12030.00, plPct: 11.32, sector: "Finance" },
];

const chartData = [
  { d: "Aug", v: 1480000 }, { d: "Sep", v: 1495000 }, { d: "Oct", v: 1472000 },
  { d: "Nov", v: 1510000 }, { d: "Dec", v: 1488000 }, { d: "Jan", v: 1530000 },
  { d: "Feb", v: 1556847 },
];

const sectorColors = {
  Defence: "#f59e0b", Chemicals: "#8b5cf6", Pharma: "#06b6d4",
  Steel: "#f97316", Auto: "#10b981", FMCG: "#ec4899", Finance: "#6366f1",
};

const fmt = (n) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Math.abs(n));
const fmtCur = (n) => `₹${fmt(n)}`;

const sectorBreakdown = portfolioData.reduce((acc, s) => {
  acc[s.sector] = (acc[s.sector] || 0) + s.invested;
  return acc;
}, {});

const pieData = Object.entries(sectorBreakdown).map(([name, value]) => ({ name, value }));

const CustomTooltip = ({ active, payload }) => {
  if (active && payload?.length) {
    return (
      <div style={{ background: "#0f1923", border: "1px solid #1e2d3d", borderRadius: 8, padding: "8px 14px" }}>
        <p style={{ color: "#94a3b8", fontSize: 11, marginBottom: 2 }}>{payload[0].payload.d}</p>
        <p style={{ color: "#34d399", fontSize: 13, fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600 }}>
          ₹{(payload[0].value / 100000).toFixed(2)}L
        </p>
      </div>
    );
  }
  return null;
};

const navItems = [
  { icon: "⬡", label: "Dashboard", active: false },
  { icon: "◈", label: "Portfolio", active: true },
  { icon: "◉", label: "Journal", active: false },
  { icon: "◎", label: "Filings", active: false },
  { icon: "◇", label: "Insights", active: false },
  { icon: "◫", label: "Settings", active: false },
];

const dateFilters = ["Today", "This Wk.", "This Mo.", "This Yr.", "All"];

export default function EquityJournal() {
  const [activeFilter, setActiveFilter] = useState("All");
  const [sortCol, setSortCol] = useState("weight");
  const [sortDir, setSortDir] = useState("desc");
  const [hovered, setHovered] = useState(null);

  const sorted = [...portfolioData].sort((a, b) =>
    sortDir === "desc" ? b[sortCol] - a[sortCol] : a[sortCol] - b[sortCol]
  );

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === "desc" ? "asc" : "desc");
    else { setSortCol(col); setSortDir("desc"); }
  };

  const totalPL = portfolioData.reduce((s, r) => s + r.pl, 0);
  const winners = portfolioData.filter(r => r.pl > 0).length;
  const losers = portfolioData.filter(r => r.pl < 0).length;

  return (
    <div style={{
      fontFamily: "'Outfit', sans-serif",
      background: "#070d13",
      minHeight: "100vh",
      color: "#e2e8f0",
      display: "flex",
      overflow: "hidden",
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
      
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e2d3d; border-radius: 4px; }
        .nav-item { cursor: pointer; border-radius: 10px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 500; color: #4a6080; transition: all 0.2s; }
        .nav-item:hover { background: #0f1923; color: #94a3b8; }
        .nav-item.active { background: linear-gradient(135deg, #0d2137 0%, #0f2a40 100%); color: #38bdf8; border: 1px solid #1e3a52; }
        .stat-card { background: #0a1520; border: 1px solid #132030; border-radius: 14px; padding: 20px 24px; position: relative; overflow: hidden; transition: transform 0.2s, border-color 0.2s; }
        .stat-card:hover { transform: translateY(-2px); border-color: #1e3a52; }
        .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; }
        .stat-card.green::before { background: linear-gradient(90deg, #10b981, transparent); }
        .stat-card.red::before { background: linear-gradient(90deg, #f43f5e, transparent); }
        .stat-card.blue::before { background: linear-gradient(90deg, #38bdf8, transparent); }
        .stat-card.amber::before { background: linear-gradient(90deg, #f59e0b, transparent); }
        .filter-btn { padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 500; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; color: #4a6080; background: transparent; }
        .filter-btn.active { background: #0f2a40; color: #38bdf8; border-color: #1e4a6a; }
        .filter-btn:hover:not(.active) { background: #0a1520; color: #7aa0c0; }
        .table-row { border-bottom: 1px solid #0d1e2d; transition: background 0.15s; cursor: pointer; }
        .table-row:hover { background: #0a1a28; }
        .table-row.highlighted { background: #0d2035; }
        .sort-btn { cursor: pointer; user-select: none; }
        .sort-btn:hover { color: #38bdf8; }
        .badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; letter-spacing: 0.5px; }
        .badge.green { background: #052016; color: #34d399; border: 1px solid #0a3020; }
        .badge.red { background: #1f0a10; color: #f87171; border: 1px solid #2d1018; }
        .add-btn { background: linear-gradient(135deg, #0ea5e9, #0284c7); color: white; border: none; border-radius: 8px; padding: 8px 16px; font-size: 12px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: opacity 0.2s; }
        .add-btn:hover { opacity: 0.9; }
        .weight-bar { height: 3px; background: #0d2035; border-radius: 2px; margin-top: 4px; }
        .weight-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #0ea5e9, #38bdf8); }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .fade-in { animation: fadeIn 0.4s ease forwards; }
        .mono { font-family: 'IBM Plex Mono', monospace; }
        .ticker-chip { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; flex-shrink: 0; }
      `}</style>

      {/* Sidebar */}
      <div style={{ width: 200, background: "#040a10", borderRight: "1px solid #0d1e2d", display: "flex", flexDirection: "column", padding: "0", flexShrink: 0 }}>
        {/* Logo */}
        <div style={{ padding: "22px 18px 18px", borderBottom: "1px solid #0d1e2d" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 30, height: 30, background: "linear-gradient(135deg, #0ea5e9, #38bdf8)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>◈</div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#e2e8f0" }}>Equity</div>
              <div style={{ fontSize: 10, fontWeight: 500, color: "#4a6080", letterSpacing: 2 }}>JOURNAL</div>
            </div>
          </div>
        </div>

        {/* Account */}
        <div style={{ padding: "14px 18px", borderBottom: "1px solid #0d1e2d" }}>
          <div style={{ fontSize: 10, color: "#2a4060", fontWeight: 600, letterSpacing: 1, marginBottom: 6 }}>ACCOUNT</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 28, height: 28, background: "linear-gradient(135deg, #1e3a5f, #0f2a40)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#38bdf8", border: "1px solid #1e3a52" }}>A</div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8" }}>Ashish</div>
              <div style={{ fontSize: 10, color: "#2a4060" }}>Zerodha · NSE</div>
            </div>
          </div>
        </div>

        {/* Nav */}
        <div style={{ padding: "12px 10px", flex: 1 }}>
          {navItems.map(item => (
            <div key={item.label} className={`nav-item ${item.active ? "active" : ""}`}>
              <span style={{ fontSize: 16 }}>{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div style={{ padding: "14px 18px", borderTop: "1px solid #0d1e2d" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#2a4060", cursor: "pointer" }}>
            <span>⊗</span> Sign Out
          </div>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        
        {/* Top Bar */}
        <div style={{ background: "#040a10", borderBottom: "1px solid #0d1e2d", padding: "12px 24px", display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 4 }}>
            {dateFilters.map(f => (
              <button key={f} className={`filter-btn ${activeFilter === f ? "active" : ""}`} onClick={() => setActiveFilter(f)}>{f}</button>
            ))}
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ fontSize: 11, color: "#2a4060", mono: true }}>
            <span className="mono">NSE · Live</span>
          </div>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#10b981", boxShadow: "0 0 6px #10b981" }} />
          <button style={{ background: "transparent", border: "1px solid #132030", borderRadius: 8, padding: "6px 12px", color: "#4a6080", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            🔔
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: "auto", padding: 24 }}>

          {/* Page Header */}
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 22 }}>
            <div>
              <div style={{ fontSize: 11, color: "#2a4060", fontWeight: 600, letterSpacing: 2, marginBottom: 4 }}>MY PORTFOLIO</div>
              <h1 style={{ fontSize: 22, fontWeight: 700, color: "#e2e8f0" }}>Holdings Overview</h1>
              <div style={{ fontSize: 12, color: "#2a4060", marginTop: 3 }}>FY 2025–26 · Last updated: 25 Feb 2026, 11:30 PM</div>
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button style={{ background: "transparent", border: "1px solid #132030", borderRadius: 8, padding: "8px 14px", color: "#4a6080", fontSize: 12, cursor: "pointer" }}>⬇ Export</button>
              <button className="add-btn">+ Add Transaction</button>
            </div>
          </div>

          {/* Stat Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 22 }} className="fade-in">
            {[
              { label: "Daily Gain / Loss", value: "₹8,054.93", sub: "+0.52% today", cls: "green", icon: "↑" },
              { label: "Weekly Gain / Loss", value: "₹15,285.88", sub: "+0.98% this week", cls: "green", icon: "↑" },
              { label: "Total P&L", value: "₹40,268.09", sub: "+2.66% all time", cls: "blue", icon: "◈" },
              { label: "Realized P/L (FY25-26)", value: "-₹7,658.50", sub: "Tax liability this year", cls: "red", icon: "↓" },
            ].map((card) => (
              <div key={card.label} className={`stat-card ${card.cls}`}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: "#2a4060", marginBottom: 10 }}>{card.label.toUpperCase()}</div>
                <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: card.cls === "red" ? "#f43f5e" : card.cls === "blue" ? "#38bdf8" : "#34d399", letterSpacing: -0.5 }}>
                  {card.value}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 5, marginTop: 6 }}>
                  <span style={{ fontSize: 11, color: "#2a4060" }}>{card.sub}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Two column: Chart + Stats */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 14, marginBottom: 22 }}>
            {/* Chart */}
            <div style={{ background: "#0a1520", border: "1px solid #132030", borderRadius: 14, padding: "20px 20px 10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: "#2a4060" }}>PORTFOLIO VALUE</div>
                  <div className="mono" style={{ fontSize: 26, fontWeight: 600, color: "#38bdf8", marginTop: 2 }}>₹15.57L</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="badge green">▲ +2.66% total</div>
                  <div style={{ fontSize: 10, color: "#2a4060", marginTop: 4 }}>Invested: ₹15.17L</div>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={140}>
                <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="d" tick={{ fill: "#2a4060", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis hide domain={["auto", "auto"]} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="v" stroke="#0ea5e9" strokeWidth={2} fill="url(#blueGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Stats Panel */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {/* Win/Loss */}
              <div style={{ background: "#0a1520", border: "1px solid #132030", borderRadius: 14, padding: 18 }}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: "#2a4060", marginBottom: 14 }}>HOLDINGS SNAPSHOT</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  {[
                    { label: "WINNERS", value: winners, pct: `${Math.round(winners/portfolioData.length*100)}%`, color: "#34d399", bg: "#052016", border: "#0a3020" },
                    { label: "LOSERS", value: losers, pct: `${Math.round(losers/portfolioData.length*100)}%`, color: "#f43f5e", bg: "#1f0a10", border: "#2d1018" },
                  ].map(s => (
                    <div key={s.label} style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 10, padding: "12px 14px" }}>
                      <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: s.color, opacity: 0.7, marginBottom: 6 }}>{s.label}</div>
                      <div className="mono" style={{ fontSize: 28, fontWeight: 600, color: s.color }}>{s.value}</div>
                      <div style={{ fontSize: 11, color: s.color, opacity: 0.6 }}>{s.pct} of portfolio</div>
                    </div>
                  ))}
                </div>
                <div style={{ marginTop: 12, padding: "10px 12px", background: "#060e18", borderRadius: 8, border: "1px solid #0d1e2d" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: 11, color: "#2a4060" }}>Best performer</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8" }}>MTARTECH</span>
                      <span className="badge green">+47.24%</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
                    <span style={{ fontSize: 11, color: "#2a4060" }}>Worst performer</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: "#94a3b8" }}>NAVINFLUOR</span>
                      <span className="badge red">-5.82%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Sector Allocation */}
              <div style={{ background: "#0a1520", border: "1px solid #132030", borderRadius: 14, padding: 18, flex: 1 }}>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: "#2a4060", marginBottom: 12 }}>SECTOR ALLOCATION</div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <PieChart width={80} height={80}>
                    <Pie data={pieData} cx={35} cy={35} innerRadius={22} outerRadius={38} paddingAngle={2} dataKey="value" strokeWidth={0}>
                      {pieData.map((entry) => (
                        <Cell key={entry.name} fill={sectorColors[entry.name] || "#38bdf8"} />
                      ))}
                    </Pie>
                  </PieChart>
                  <div style={{ flex: 1 }}>
                    {Object.entries(sectorBreakdown).slice(0, 5).map(([name, val]) => (
                      <div key={name} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                          <div style={{ width: 6, height: 6, borderRadius: "50%", background: sectorColors[name] || "#38bdf8", flexShrink: 0 }} />
                          <span style={{ fontSize: 10, color: "#4a6080" }}>{name}</span>
                        </div>
                        <span className="mono" style={{ fontSize: 10, color: "#94a3b8" }}>
                          {((val / 1516579) * 100).toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Holdings Table */}
          <div style={{ background: "#0a1520", border: "1px solid #132030", borderRadius: 14, overflow: "hidden" }}>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #0d1e2d", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1.5, color: "#2a4060" }}>ALL HOLDINGS</div>
              <div style={{ display: "flex", gap: 8 }}>
                <div style={{ background: "#060e18", border: "1px solid #0d1e2d", borderRadius: 6, padding: "5px 12px", fontSize: 11, color: "#2a4060", display: "flex", gap: 6 }}>
                  <span>Filter by sector</span> <span>▾</span>
                </div>
                <div style={{ background: "#060e18", border: "1px solid #0d1e2d", borderRadius: 6, padding: "5px 12px", fontSize: 11, color: "#2a4060" }}>
                  ⊞ Columns
                </div>
              </div>
            </div>

            {/* Table Header */}
            <div style={{ display: "grid", gridTemplateColumns: "36px 1fr 80px 110px 110px 130px 90px 120px 110px", padding: "10px 20px", borderBottom: "1px solid #0d1e2d" }}>
              {["#", "Asset", "Qty", "Avg Price", "LTP", "Investment", "Weight", "P&L", "Return"].map((col, i) => (
                <div key={col} className="sort-btn" onClick={() => handleSort(["", "name", "qty", "avg", "current", "invested", "weight", "pl", "plPct"][i])}
                  style={{ fontSize: 9, fontWeight: 700, letterSpacing: 1.5, color: "#2a4060", textAlign: i > 1 ? "right" : "left" }}>
                  {col} {sortCol === ["", "name", "qty", "avg", "current", "invested", "weight", "pl", "plPct"][i] && (sortDir === "desc" ? "↓" : "↑")}
                </div>
              ))}
            </div>

            {/* Table Body */}
            {sorted.map((row, i) => {
              const isPos = row.pl >= 0;
              const initials = row.ticker.slice(0, 2);
              return (
                <div key={row.ticker} className={`table-row ${hovered === i ? "highlighted" : ""}`}
                  style={{ display: "grid", gridTemplateColumns: "36px 1fr 80px 110px 110px 130px 90px 120px 110px", padding: "13px 20px", alignItems: "center" }}
                  onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}>
                  <div style={{ fontSize: 11, color: "#1e3a52", fontWeight: 600 }}>{i + 1}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div className="ticker-chip" style={{ background: `${sectorColors[row.sector] || "#38bdf8"}18`, color: sectorColors[row.sector] || "#38bdf8", border: `1px solid ${sectorColors[row.sector] || "#38bdf8"}30` }}>
                      {initials}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#e2e8f0" }}>{row.ticker}</div>
                      <div style={{ fontSize: 10, color: "#2a4060", marginTop: 1 }}>{row.name.slice(0, 28)}</div>
                    </div>
                  </div>
                  <div className="mono" style={{ fontSize: 12, color: "#64748b", textAlign: "right" }}>{row.qty.toLocaleString()}</div>
                  <div className="mono" style={{ fontSize: 12, color: "#64748b", textAlign: "right" }}>{fmtCur(row.avg)}</div>
                  <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: "#94a3b8", textAlign: "right" }}>{fmtCur(row.current)}</div>
                  <div className="mono" style={{ fontSize: 12, color: "#64748b", textAlign: "right" }}>{fmtCur(row.invested)}</div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: "#38bdf8" }}>{row.weight}%</div>
                    <div className="weight-bar" style={{ width: 60, marginLeft: "auto" }}>
                      <div className="weight-fill" style={{ width: `${(row.weight / 15.5) * 100}%` }} />
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: isPos ? "#34d399" : "#f43f5e" }}>
                      {isPos ? "+" : "-"}₹{fmt(row.pl)}
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <span className={`badge ${isPos ? "green" : "red"}`}>
                      {isPos ? "▲" : "▼"} {Math.abs(row.plPct).toFixed(2)}%
                    </span>
                  </div>
                </div>
              );
            })}

            {/* Footer */}
            <div style={{ display: "grid", gridTemplateColumns: "36px 1fr 80px 110px 110px 130px 90px 120px 110px", padding: "14px 20px", borderTop: "1px solid #132030", background: "#060e18" }}>
              <div />
              <div style={{ fontSize: 11, fontWeight: 700, color: "#4a6080" }}>TOTAL</div>
              <div />
              <div />
              <div />
              <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: "#64748b", textAlign: "right" }}>₹15,16,579</div>
              <div style={{ textAlign: "right", fontSize: 11, fontWeight: 600, color: "#38bdf8" }}>100%</div>
              <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: "#34d399", textAlign: "right" }}>+₹40,268</div>
              <div style={{ textAlign: "right" }}>
                <span className="badge green">▲ 2.66%</span>
              </div>
            </div>
          </div>

          {/* Bottom tip */}
          <div style={{ marginTop: 14, fontSize: 11, color: "#1e3a52", textAlign: "center" }}>
            ◈ Hover a row to highlight · Click column headers to sort · Double-click for full transaction history
          </div>
        </div>
      </div>
    </div>
  );
}
