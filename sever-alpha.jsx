import { useState, useEffect, useRef } from "react";
import { fetchSubscriptions, isApiConfigured, postAction, postUndo } from "./src/api.js";

// ————————————————————————————————————————————————
// SEVER — Autonomous Subscription Guardian (alpha)
// Design: ledger paper + guard green + leak crimson.
// Money is always set in mono. The signature element is the
// Monthly Bleed counter that ticks down live as the guardian acts.
// ————————————————————————————————————————————————

const INK = "#17221C";
const PAPER = "#EEF2EC";
const CARD = "#FFFFFF";
const LEAK = "#C22F2F";
const GUARD = "#1E7A4C";
const GOLD = "#A67C1B";
const MUTE = "#6B776F";
const LINE = "#D8DFD6";

const seedSubs = [
  { id: 1, name: "Netflix", category: "Streaming", price: 15.49, cadence: "mo", lastUsed: 2, status: "active" },
  { id: 2, name: "iCloud+ 200GB", category: "Storage", price: 2.99, cadence: "mo", lastUsed: 0, status: "active" },
  { id: 3, name: "Peak Fitness Gym", category: "Health", price: 44.0, cadence: "mo", lastUsed: 67, status: "active" },
  { id: 4, name: "Adobe Creative Cloud", category: "Software", price: 59.99, cadence: "mo", lastUsed: 41, status: "active" },
  { id: 5, name: "Duolingo Super", category: "Education", price: 6.99, cadence: "mo", lastUsed: 88, status: "active" },
  { id: 6, name: "DashPass", category: "Delivery", price: 9.99, cadence: "mo", lastUsed: 34, status: "active" },
  { id: 7, name: "Spotify Premium", category: "Streaming", price: 11.99, cadence: "mo", lastUsed: 1, status: "active" },
  { id: 8, name: "Calm", category: "Wellness", price: 69.99, cadence: "yr", lastUsed: 122, status: "active" },
  { id: 9, name: "NYT Digital", category: "News", price: 17.0, cadence: "mo", lastUsed: 12, status: "active" },
  { id: 10, name: "Dropbox Plus", category: "Storage", price: 11.99, cadence: "mo", lastUsed: 55, status: "active" },
];

const monthly = (s) => (s.cadence === "yr" ? s.price / 12 : s.price);
const money = (n) => "$" + n.toFixed(2);

// Animated number that eases toward its target — the "bleed" ticking down.
function useEased(target, ms = 900) {
  const [val, setVal] = useState(target);
  const raf = useRef(null);
  useEffect(() => {
    const from = val;
    const t0 = performance.now();
    cancelAnimationFrame(raf.current);
    const step = (t) => {
      const p = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      setVal(from + (target - from) * e);
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target]);
  return val;
}

const now = () =>
  new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export default function SeverAlpha() {
  const [subs, setSubs] = useState(seedSubs);
  const [log, setLog] = useState([
    { t: now(), kind: "sys", text: "Guardian online. 10 recurring charges detected via transaction feed." },
    { t: now(), kind: "sys", text: "Virtual card issued per merchant. Kill-switch armed." },
  ]);
  const [threshold, setThreshold] = useState(30);
  const [busy, setBusy] = useState({});
  const [autopilotRunning, setAutopilotRunning] = useState(false);
  const [reclaimed, setReclaimed] = useState(0);
  const feedRef = useRef(null);

  const active = subs.filter((s) => s.status === "active" || s.status === "negotiated");
  const bleedTarget = active.reduce(
    (a, s) => a + (s.status === "negotiated" ? monthly({ ...s, price: s.newPrice }) : monthly(s)),
    0
  );
  const bleed = useEased(bleedTarget);
  const reclaimedEased = useEased(reclaimed);
  const flagged = subs.filter((s) => s.status === "active" && s.lastUsed >= threshold);

  const addLog = (kind, text) =>
    setLog((l) => [...l, { t: now(), kind, text }]);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [log]);

  useEffect(() => {
    if (!isApiConfigured()) return;
    fetchSubscriptions()
      .then((data) => {
        setSubs(data);
        // Derive reclaimed from server state so it survives refreshes:
        // canceled/paused reclaim their full monthly; negotiated reclaims the discount.
        const recovered = data.reduce((acc, s) => {
          if (s.status === "canceled" || s.status === "paused") return acc + monthly(s);
          if (s.status === "negotiated" && s.newPrice) return acc + (monthly(s) - monthly({ ...s, price: s.newPrice }));
          return acc;
        }, 0);
        setReclaimed(recovered);
        addLog("sys", `Live API connected — ${data.length} recurring charges loaded.`);
      })
      .catch(() => addLog("sys", "Live API unavailable — running in preview mode."));
  }, []);

  const clearBusy = (id) =>
    setBusy((b) => {
      const c = { ...b };
      delete c[id];
      return c;
    });

  const act = (id, mode) => {
    const s = subs.find((x) => x.id === id);
    if (!s || busy[id]) return;
    setBusy((b) => ({ ...b, [id]: mode }));
    addLog(
      "work",
      mode === "cancel"
        ? `Freezing virtual card for ${s.name} and filing cancellation…`
        : mode === "pause"
        ? `Pausing ${s.name} — card frozen, merchant notified…`
        : `Opening retention negotiation with ${s.name}…`
    );

    if (isApiConfigured()) {
      postAction(id, mode)
        .then(({ subscription, reclaimedMonthly, message }) => {
          setSubs((prev) => prev.map((x) => (x.id === id ? subscription : x)));
          if (reclaimedMonthly > 0) setReclaimed((r) => r + reclaimedMonthly);
          addLog("done", message);
        })
        .catch(() => addLog("sys", `Guardian could not reach ${s.name} — action aborted.`))
        .finally(() => clearBusy(id));
      return;
    }

    const delay = 900 + Math.random() * 1100;
    setTimeout(() => {
      setSubs((prev) =>
        prev.map((x) => {
          if (x.id !== id) return x;
          if (mode === "cancel") return { ...x, status: "canceled" };
          if (mode === "pause") return { ...x, status: "paused" };
          const cut = 0.3 + Math.random() * 0.25;
          return { ...x, status: "negotiated", newPrice: +(x.price * (1 - cut)).toFixed(2) };
        })
      );
      if (mode === "cancel" || mode === "pause") {
        setReclaimed((r) => r + monthly(s));
        addLog(
          "done",
          `${s.name} ${mode === "cancel" ? "canceled" : "paused"}. ${money(monthly(s))}/mo reclaimed. Undo window: 72h.`
        );
      } else {
        const cutPrice = +(s.price * 0.62).toFixed(2);
        setReclaimed((r) => r + (monthly(s) - monthly({ ...s, price: cutPrice })));
        addLog("done", `${s.name} countered with a retention deal. New rate locked in.`);
      }
      clearBusy(id);
    }, delay);
  };

  const runAutopilot = () => {
    if (autopilotRunning || flagged.length === 0) return;
    setAutopilotRunning(true);
    addLog("sys", `Autopilot engaged — ${flagged.length} leak${flagged.length > 1 ? "s" : ""} over the ${threshold}-day line.`);
    flagged.forEach((s, i) => {
      setTimeout(() => {
        act(s.id, s.lastUsed > 60 ? "cancel" : "pause");
        if (i === flagged.length - 1)
          setTimeout(() => setAutopilotRunning(false), 2400);
      }, i * 1500);
    });
  };

  const undo = (id) => {
    const s = subs.find((x) => x.id === id);
    if (!s) return;

    if (isApiConfigured()) {
      postUndo(id)
        .then(({ subscription, reclaimedMonthly, message }) => {
          setSubs((prev) => prev.map((x) => (x.id === id ? subscription : x)));
          setReclaimed((r) => Math.max(0, r + reclaimedMonthly));
          addLog("sys", message);
        })
        .catch(() => addLog("sys", `Could not restore ${s.name} — try again.`));
      return;
    }

    setSubs((prev) => prev.map((x) => (x.id === id ? { ...x, status: "active", newPrice: undefined } : x)));
    setReclaimed((r) => Math.max(0, r - monthly(s)));
    addLog("sys", `${s.name} restored. Card unfrozen.`);
  };

  const statusChip = (s) => {
    const map = {
      canceled: { txt: "SEVERED", bg: INK, fg: PAPER },
      paused: { txt: "PAUSED", bg: "#E4E9E2", fg: INK },
      negotiated: { txt: "DEAL LOCKED", bg: "#F3EAD2", fg: GOLD },
    };
    const m = map[s.status];
    if (!m) return null;
    return (
      <span style={{ background: m.bg, color: m.fg, fontSize: 10, letterSpacing: "0.08em", padding: "3px 8px", borderRadius: 3, fontFamily: "'IBM Plex Mono', monospace" }}>
        {m.txt}
      </span>
    );
  };

  return (
    <div style={{ minHeight: "100vh", background: PAPER, color: INK, fontFamily: "'Archivo', system-ui, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75,400..900;100,400..700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
        @keyframes drip { 0% { transform: translateY(-2px); opacity: 0; } 30% { opacity: 1; } 100% { transform: translateY(14px); opacity: 0; } }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
        .drip { animation: drip 1.4s ease-in infinite; }
        .working { animation: pulse 1s ease-in-out infinite; }
        button { cursor: pointer; }
        button:focus-visible { outline: 2px solid ${INK}; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) { .drip, .working { animation: none; } }
      `}</style>

      {/* Masthead */}
      <header style={{ borderBottom: `1px solid ${LINE}`, padding: "18px 28px", display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap" }}>
        <div style={{ fontFamily: "'Archivo', sans-serif", fontStretch: "75%", fontWeight: 900, fontSize: 28, letterSpacing: "0.02em" }}>
          SEVER<span style={{ color: LEAK }}>/</span>
        </div>
        <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 11, color: MUTE, letterSpacing: "0.06em" }}>
          AUTONOMOUS SUBSCRIPTION GUARDIAN · BETA · ACCOUNT LINKED VIA PLAID (SANDBOX)
        </div>
      </header>

      {/* Bleed band — the signature */}
      <section style={{ display: "flex", flexWrap: "wrap", borderBottom: `1px solid ${LINE}`, background: CARD }}>
        <div style={{ flex: "2 1 320px", padding: "26px 28px", borderRight: `1px solid ${LINE}` }}>
          <div style={{ fontSize: 11, letterSpacing: "0.14em", color: MUTE, fontFamily: "'IBM Plex Mono', monospace" }}>MONTHLY BLEED</div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: "clamp(40px, 7vw, 64px)", color: bleedTarget < bleed ? GUARD : LEAK, lineHeight: 1.05, fontVariantNumeric: "tabular-nums" }}>
            {money(bleed)}
          </div>
          <div style={{ fontSize: 12, color: MUTE, marginTop: 4, fontFamily: "'IBM Plex Mono', monospace" }}>
            {money(bleed * 12)} / year across {active.length} live charges
          </div>
        </div>
        <div style={{ flex: "1 1 200px", padding: "26px 28px", borderRight: `1px solid ${LINE}` }}>
          <div style={{ fontSize: 11, letterSpacing: "0.14em", color: MUTE, fontFamily: "'IBM Plex Mono', monospace" }}>RECLAIMED BY GUARDIAN</div>
          <div style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: 34, color: GUARD, fontVariantNumeric: "tabular-nums" }}>
            {money(reclaimedEased)}<span style={{ fontSize: 14, color: MUTE }}>/mo</span>
          </div>
        </div>
        <div style={{ flex: "1 1 220px", padding: "22px 28px", display: "flex", flexDirection: "column", justifyContent: "center", gap: 10 }}>
          <label style={{ fontSize: 11, letterSpacing: "0.14em", color: MUTE, fontFamily: "'IBM Plex Mono', monospace" }}>
            LEAK LINE: {threshold} DAYS UNUSED
          </label>
          <input type="range" min={7} max={90} value={threshold} onChange={(e) => setThreshold(+e.target.value)} style={{ accentColor: INK, width: "100%" }} />
          <button
            onClick={runAutopilot}
            disabled={autopilotRunning || flagged.length === 0}
            style={{
              background: flagged.length && !autopilotRunning ? LEAK : "#CDD5CB",
              color: "#fff", border: "none", padding: "12px 16px", borderRadius: 4,
              fontFamily: "'Archivo', sans-serif", fontWeight: 700, fontSize: 14, letterSpacing: "0.04em",
            }}
          >
            {autopilotRunning ? "AUTOPILOT WORKING…" : `RUN AUTOPILOT — SEVER ${flagged.length} LEAK${flagged.length === 1 ? "" : "S"}`}
          </button>
        </div>
      </section>

      {/* Body */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "stretch" }}>
        {/* Ledger */}
        <main style={{ flex: "2 1 460px", padding: "20px 28px 40px" }}>
          <div style={{ fontSize: 11, letterSpacing: "0.14em", color: MUTE, fontFamily: "'IBM Plex Mono', monospace", margin: "8px 0 12px" }}>
            RECURRING CHARGE LEDGER — SORTED BY NEGLECT
          </div>
          {[...subs].sort((a, b) => b.lastUsed - a.lastUsed).map((s) => {
            const leaking = s.status === "active" && s.lastUsed >= threshold;
            const dead = s.status === "canceled" || s.status === "paused";
            const working = busy[s.id];
            return (
              <div key={s.id} className={working ? "working" : ""} style={{
                background: CARD, border: `1px solid ${leaking ? LEAK : LINE}`,
                borderLeft: `4px solid ${dead ? INK : leaking ? LEAK : s.status === "negotiated" ? GOLD : GUARD}`,
                borderRadius: 4, padding: "12px 16px", marginBottom: 8,
                display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
                opacity: dead ? 0.55 : 1, position: "relative",
              }}>
                {leaking && (
                  <div aria-hidden style={{ position: "absolute", left: -2.5, top: 8, width: 5, height: 5, borderRadius: "50%", background: LEAK }} className="drip" />
                )}
                <div style={{ flex: "2 1 160px", minWidth: 140 }}>
                  <div style={{ fontWeight: 700, fontSize: 15, textDecoration: s.status === "canceled" ? "line-through" : "none" }}>{s.name}</div>
                  <div style={{ fontSize: 11, color: MUTE, fontFamily: "'IBM Plex Mono', monospace" }}>
                    {s.category} · card ••{String(4000 + s.id * 37).slice(-4)} {dead ? "· FROZEN" : ""}
                  </div>
                </div>
                <div style={{ flex: "1 1 90px", fontFamily: "'IBM Plex Mono', monospace", fontSize: 14, fontVariantNumeric: "tabular-nums" }}>
                  {s.status === "negotiated" ? (
                    <>
                      <span style={{ textDecoration: "line-through", color: MUTE, fontSize: 12 }}>{money(s.price)}</span>{" "}
                      <span style={{ color: GOLD, fontWeight: 600 }}>{money(s.newPrice)}</span>
                    </>
                  ) : money(s.price)}
                  <span style={{ color: MUTE, fontSize: 11 }}>/{s.cadence}</span>
                </div>
                <div style={{ flex: "1 1 110px", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace", color: leaking ? LEAK : MUTE }}>
                  {s.lastUsed === 0 ? "used today" : `${s.lastUsed}d since last use`}
                  <div style={{ height: 3, background: "#E7ECE5", borderRadius: 2, marginTop: 4, maxWidth: 120 }}>
                    <div style={{ height: 3, width: `${Math.min(100, (s.lastUsed / 90) * 100)}%`, background: leaking ? LEAK : GUARD, borderRadius: 2 }} />
                  </div>
                </div>
                <div style={{ flex: "1 1 190px", display: "flex", gap: 6, justifyContent: "flex-end", alignItems: "center" }}>
                  {statusChip(s)}
                  {dead || s.status === "negotiated" ? (
                    <button onClick={() => undo(s.id)} style={{ background: "transparent", border: `1px solid ${LINE}`, borderRadius: 3, padding: "6px 10px", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace" }}>
                      UNDO
                    </button>
                  ) : working ? (
                    <span style={{ fontSize: 11, color: MUTE, fontFamily: "'IBM Plex Mono', monospace" }}>guardian working…</span>
                  ) : (
                    <>
                      <button onClick={() => act(s.id, "negotiate")} style={{ background: "transparent", border: `1px solid ${GOLD}`, color: GOLD, borderRadius: 3, padding: "6px 10px", fontSize: 11, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>
                        HAGGLE
                      </button>
                      <button onClick={() => act(s.id, "pause")} style={{ background: "transparent", border: `1px solid ${INK}`, borderRadius: 3, padding: "6px 10px", fontSize: 11, fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>
                        PAUSE
                      </button>
                      <button onClick={() => act(s.id, "cancel")} style={{ background: LEAK, border: `1px solid ${LEAK}`, color: "#fff", borderRadius: 3, padding: "6px 10px", fontSize: 11, fontWeight: 700, fontFamily: "'IBM Plex Mono', monospace" }}>
                        SEVER
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </main>

        {/* Guardian feed */}
        <aside style={{ flex: "1 1 300px", borderLeft: `1px solid ${LINE}`, background: INK, color: "#D8E2DA", display: "flex", flexDirection: "column", minHeight: 400 }}>
          <div style={{ padding: "18px 20px 10px", fontSize: 11, letterSpacing: "0.14em", fontFamily: "'IBM Plex Mono', monospace", color: "#8FA396", borderBottom: "1px solid #263229" }}>
            GUARDIAN FEED — EVERY ACTION, AUDITED
          </div>
          <div ref={feedRef} style={{ flex: 1, overflowY: "auto", padding: "12px 20px", maxHeight: 520 }}>
            {log.map((e, i) => (
              <div key={i} style={{ marginBottom: 12, fontFamily: "'IBM Plex Mono', monospace", fontSize: 12, lineHeight: 1.5 }}>
                <span style={{ color: "#5E6F64" }}>{e.t}</span>{" "}
                <span style={{ color: e.kind === "done" ? "#7FD6A4" : e.kind === "work" ? "#E5C877" : "#93A79A" }}>
                  {e.kind === "done" ? "✓" : e.kind === "work" ? "…" : "·"}
                </span>{" "}
                {e.text}
              </div>
            ))}
          </div>
          <div style={{ padding: "14px 20px", borderTop: "1px solid #263229", fontSize: 11, fontFamily: "'IBM Plex Mono', monospace", color: "#8FA396" }}>
            72-hour undo on every action · re-signup guarantee · you hold the keys
          </div>
        </aside>
      </div>
    </div>
  );
}
