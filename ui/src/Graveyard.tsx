import type { CSSProperties } from "react";
import type { SummaryResult } from "./api";
import type { CrewSummary, Tombstone } from "./types";

// Pure view. Every value is rendered through JSX text interpolation (no HTML
// injection, no markdown) and is shown exactly as the API returned it.
// Nothing here calculates a money, date or day value.

export type ViewState = { kind: "loading" } | SummaryResult;

export interface GraveyardProps {
  state: ViewState;
  demo: boolean;
  onDemoChange: (demo: boolean) => void;
  onAsk: (t: Tombstone) => void;
}

const AMBER = "#ffb347";
const CANDLE_GLOW = "0 0 10px 2px rgba(255,179,71,0.55), 0 0 28px 8px rgba(255,160,40,0.22)";

const CSS = `
@keyframes banshee-flicker {
  0%, 100% { opacity: 1; transform: scale(1); }
  35% { opacity: 0.82; transform: scale(0.94); }
  60% { opacity: 1; transform: scale(1.06); }
  80% { opacity: 0.9; transform: scale(0.98); }
}
.banshee-flame { animation: banshee-flicker 2.6s ease-in-out infinite; }
.banshee-ask:hover { background: rgba(255,179,71,0.18); box-shadow: ${CANDLE_GLOW}; }
@media (prefers-reduced-motion: reduce) { .banshee-flame { animation: none; } }
`;

const s: Record<string, CSSProperties> = {
  page: {
    minHeight: "100%",
    boxSizing: "border-box",
    padding: "28px clamp(14px, 4vw, 40px) 40px",
    color: "#d9d6cf",
    fontFamily: "Georgia, 'Times New Roman', serif",
    background:
      "radial-gradient(ellipse at 50% -10%, rgba(255,179,71,0.10), transparent 55%), " +
      "radial-gradient(ellipse at 50% 110%, rgba(70,90,120,0.22), transparent 60%), " +
      "linear-gradient(180deg, #0a0c14 0%, #10131d 55%, #0b0d12 100%)",
  },
  header: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "flex-end",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 22,
  },
  titleRow: { display: "flex", alignItems: "center", gap: 14 },
  title: {
    margin: 0,
    fontSize: "clamp(26px, 4vw, 38px)",
    letterSpacing: "0.04em",
    color: "#ece8dc",
    textShadow: "0 2px 0 #000, 0 0 18px rgba(255,179,71,0.25)",
  },
  supplier: { margin: "4px 0 0", fontSize: 15, color: "#9a9788", fontStyle: "italic" },
  flame: {
    width: 14,
    height: 26,
    borderRadius: "50% 50% 50% 50% / 62% 62% 38% 38%",
    background: "linear-gradient(180deg, #fff3c4 0%, #ffb347 55%, #ff7a18 100%)",
    boxShadow: CANDLE_GLOW,
    flexShrink: 0,
  },
  toggle: {
    display: "inline-flex",
    alignItems: "center",
    gap: 10,
    padding: "8px 14px",
    border: "1px solid rgba(255,179,71,0.35)",
    borderRadius: 999,
    background: "rgba(255,179,71,0.06)",
    color: "#f0dcb4",
    fontSize: 14,
    cursor: "pointer",
    userSelect: "none",
  },
  checkbox: { accentColor: AMBER, width: 16, height: 16, cursor: "pointer" },
  totals: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: 12,
    marginBottom: 30,
  },
  total: {
    padding: "12px 16px",
    borderRadius: 10,
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(255,255,255,0.08)",
    boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
  },
  totalLabel: {
    fontSize: 11,
    textTransform: "uppercase",
    letterSpacing: "0.14em",
    color: "#8c897c",
  },
  totalValue: { marginTop: 4, fontSize: 20, color: "#f3eee0", fontWeight: 700 },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: 26,
    alignItems: "start",
  },
  stone: {
    position: "relative",
    boxSizing: "border-box",
    padding: "54px 22px 22px",
    borderRadius: "130px 130px 10px 10px / 110px 110px 10px 10px",
    background: "linear-gradient(170deg, #4a4e59 0%, #343842 45%, #262930 100%)",
    border: "1px solid rgba(255,255,255,0.12)",
    boxShadow:
      "inset 0 2px 0 rgba(255,255,255,0.12), inset 0 -10px 24px rgba(0,0,0,0.45), " +
      "0 14px 30px rgba(0,0,0,0.6), 0 0 38px rgba(255,179,71,0.07)",
    textAlign: "center",
  },
  candle: {
    position: "absolute",
    top: 16,
    left: "50%",
    width: 8,
    height: 15,
    marginLeft: -4,
    borderRadius: "50% 50% 50% 50% / 62% 62% 38% 38%",
    background: "linear-gradient(180deg, #fff3c4 0%, #ffb347 60%, #ff7a18 100%)",
    boxShadow: CANDLE_GLOW,
  },
  engraved: {
    color: "#c9c6bb",
    textShadow: "0 1px 0 rgba(255,255,255,0.18), 0 -1px 0 rgba(0,0,0,0.75)",
  },
  buyer: { margin: 0, fontSize: 20, lineHeight: 1.25, wordBreak: "break-word" },
  invoice: { margin: "4px 0 0", fontSize: 13, letterSpacing: "0.08em", wordBreak: "break-word" },
  state: {
    margin: "14px 0 6px",
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: "0.16em",
    color: AMBER,
    textShadow: "0 0 10px rgba(255,179,71,0.4)",
  },
  principal: { margin: "6px 0", fontSize: 26, fontWeight: 700 },
  lines: { margin: 0, padding: 0, listStyle: "none", fontSize: 14, lineHeight: 1.7 },
  bomb: {
    margin: "12px 0 0",
    padding: "8px 10px",
    borderRadius: 8,
    background: "rgba(255,110,40,0.10)",
    border: "1px dashed rgba(255,150,70,0.5)",
    fontSize: 14,
    lineHeight: 1.6,
    color: "#ffcf99",
  },
  next: { margin: "12px 0 0", fontSize: 13, fontStyle: "italic", color: "#aeb4c0" },
  ask: {
    marginTop: 14,
    padding: "8px 18px",
    borderRadius: 999,
    border: `1px solid ${AMBER}`,
    background: "rgba(255,179,71,0.08)",
    color: "#ffd9a0",
    fontFamily: "inherit",
    fontSize: 14,
    cursor: "pointer",
  },
  notice: {
    margin: "60px auto",
    maxWidth: 460,
    padding: "28px 24px",
    textAlign: "center",
    borderRadius: 14,
    background: "rgba(255,255,255,0.035)",
    border: "1px solid rgba(255,255,255,0.1)",
  },
  noticeTitle: { margin: 0, fontSize: 24, color: "#ece8dc" },
  noticeText: { margin: "10px 0 0", fontSize: 15, color: "#9a9788" },
  code: {
    display: "inline-block",
    marginTop: 12,
    padding: "3px 10px",
    borderRadius: 6,
    background: "rgba(0,0,0,0.45)",
    color: "#ff9d7a",
    fontFamily: "ui-monospace, Menlo, Consolas, monospace",
    fontSize: 14,
  },
  disclaimer: {
    marginTop: 36,
    textAlign: "center",
    fontSize: 13,
    fontStyle: "italic",
    color: "#7f7c70",
  },
};

function Total({ label, value }: { label: string; value: string }) {
  return (
    <div style={s.total}>
      <div style={s.totalLabel}>{label}</div>
      <div style={s.totalValue}>{value}</div>
    </div>
  );
}

function Totals({ summary }: { summary: CrewSummary }) {
  const { totals } = summary;
  return (
    <div style={s.totals}>
      <Total label="Outstanding" value={totals.outstanding.text} />
      {totals.interestAccrued !== null && (
        <Total label="Interest accrued" value={totals.interestAccrued.text} />
      )}
      {totals.deductionsAtRisk !== null && (
        <Total label="Deductions at risk" value={totals.deductionsAtRisk.text} />
      )}
      <Total label="Exploded" value={String(totals.explodedCount)} />
      <Total label="Paid" value={String(totals.paidCount)} />
      <Total label="As of" value={summary.today} />
    </div>
  );
}

function Stone({ t, onAsk }: { t: Tombstone; onAsk: (t: Tombstone) => void }) {
  // The banshee box and the Ask button only make sense while the bomb is armed;
  // stateText already says exploded or paid for the rest.
  const armed = t.taxBomb !== null && t.taxBomb.status === "armed" ? t.taxBomb : null;
  return (
    <article style={s.stone}>
      <span className="banshee-flame" style={s.candle} aria-hidden="true" />
      <h2 style={{ ...s.buyer, ...s.engraved }}>{t.buyerName}</h2>
      <p style={{ ...s.invoice, ...s.engraved }}>{t.invoiceNumber}</p>
      <p style={s.state}>{t.stateText}</p>
      <p style={{ ...s.principal, ...s.engraved }}>{t.principal.text}</p>
      <ul style={{ ...s.lines, ...s.engraved }}>
        {t.dueDateText !== null && <li>{t.dueDateText}</li>}
        <li>{`${t.daysOverdue} days overdue`}</li>
        {t.interest !== null && <li>{t.interest.text}</li>}
      </ul>
      {armed !== null && (
        <p style={s.bomb}>
          <span>{armed.deductionAtRiskText}</span>
          <br />
          <span>{`${armed.daysLeft} days to 31 March`}</span>
        </p>
      )}
      <p style={s.next}>{t.nextLabel}</p>
      {armed !== null && (
        <button type="button" className="banshee-ask" style={s.ask} onClick={() => onAsk(t)}>
          Ask the banshee
        </button>
      )}
    </article>
  );
}

function Body({ state, onAsk }: { state: ViewState; onAsk: (t: Tombstone) => void }) {
  if (state.kind === "loading") {
    return (
      <div style={s.notice} role="status">
        <h2 style={s.noticeTitle}>Summoning the dead…</h2>
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div style={s.notice} role="alert">
        <h2 style={s.noticeTitle}>The banshee is silent</h2>
        <span style={s.code}>{state.code === "request_failed" ? "Request failed" : state.code}</span>
      </div>
    );
  }
  const { summary } = state;
  if (summary.tombstones.length === 0) {
    return (
      <div style={s.notice}>
        <h2 style={s.noticeTitle}>No graves today</h2>
        <p style={s.noticeText}>{summary.disclaimer}</p>
      </div>
    );
  }
  return (
    <>
      <Totals summary={summary} />
      <div style={s.grid}>
        {summary.tombstones.map((t) => (
          <Stone key={t.id} t={t} onAsk={onAsk} />
        ))}
      </div>
      <p style={s.disclaimer}>{summary.disclaimer}</p>
    </>
  );
}

export default function Graveyard({ state, demo, onDemoChange, onAsk }: GraveyardProps) {
  return (
    <main style={s.page}>
      <style>{CSS}</style>
      <header style={s.header}>
        <div style={s.titleRow}>
          <span className="banshee-flame" style={s.flame} aria-hidden="true" />
          <div>
            <h1 style={s.title}>Graveyard of Dues</h1>
            {state.kind === "data" && <p style={s.supplier}>{state.summary.supplierName}</p>}
          </div>
        </div>
        <label style={s.toggle}>
          <input
            type="checkbox"
            style={s.checkbox}
            checked={demo}
            onChange={(e) => onDemoChange(e.target.checked)}
          />
          Demo date 2026-11-12
        </label>
      </header>
      <Body state={state} onAsk={onAsk} />
    </main>
  );
}
