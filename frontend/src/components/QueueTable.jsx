import React, { useEffect, useMemo, useRef, useState } from "react";
import { getQueueStats, openQueue } from "../api/queues";
import { openQueueWS } from "../api/ws";

/**
 * Изменения по задаче:
 *  • Открытие очереди всегда с start_number=0
 *  • WS всегда подключается с (department, today)
 */
export default function QueueTable({ department = "Reg" }) {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const wsCloseRef = useRef(() => {});

  // YYYY-MM-DD (today)
  const today = new Date().toISOString().slice(0, 10);

  async function loadStats() {
    setErr("");
    try {
      const data = await getQueueStats(department, today);
      setStats(data);
    } catch (e) {
      setStats(null);
      setErr(e?.data?.detail || e?.message || "Ошибка загрузки статистики");
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      await loadStats();
      if (!mounted) return;

      try {
        wsCloseRef.current = openQueueWS(department, today, (msg) => {
          if (msg?.type === "queue.update" && msg?.payload) {
            setStats((cur) => ({ ...(cur || {}), ...(msg.payload || {}) }));
          } else if (Array.isArray(msg)) {
            setStats({ items: msg });
          }
        });
      } catch {
        wsCloseRef.current = () => {};
      }
    })();

    const t = setInterval(loadStats, 15000);
    return () => {
      mounted = false;
      clearInterval(t);
      try { wsCloseRef.current(); } catch {}
      wsCloseRef.current = () => {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [department, today]);

  async function handleOpenQueue() {
    setBusy(true);
    setErr("");
    try {
      await openQueue(department, today, 0);
      await loadStats();
    } catch (e) {
      setErr(e?.data?.detail || e?.message || "Ошибка открытия очереди");
    } finally {
      setBusy(false);
    }
  }

  const info = useMemo(() => {
    const s = stats || {};
    return [
      { k: "Начальный номер", v: s.start_number ?? "—" },
      { k: "Последний талон", v: s.last_ticket ?? "—" },
      { k: "Ожидают", v: s.waiting ?? "—" },
      { k: "В работе", v: s.serving ?? "—" },
      { k: "Готово", v: s.done ?? "—" },
    ];
  }, [stats]);

  return (
    <div style={{ display: "grid", gap: 12 }}>
      {err && <div style={errBox}>{String(err)}</div>}

      <div style={statGrid}>
        {info.map((x) => (
          <div key={x.k} style={statCard}>
            <div style={{ fontSize: 12, opacity: 0.6 }}>{x.k}</div>
            <div style={{ fontSize: 22, fontWeight: 800 }}>{x.v}</div>
          </div>
        ))}
      </div>

      <div>
        <button onClick={handleOpenQueue} disabled={busy} style={btnPrimary}>
          {busy ? "..." : "Открыть очередь (start=0)"}
        </button>
      </div>
    </div>
  );
}

const statGrid = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 };
const statCard = { border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" };
const btnPrimary = {
  padding: "8px 12px",
  borderRadius: 10,
  border: "1px solid #0284c7",
  background: "#0ea5e9",
  color: "#fff",
  cursor: "pointer",
};
const errBox = {
  color: "#7f1d1d",
  background: "#fee2e2",
  border: "1px solid #fecaca",
  borderRadius: 8,
  padding: 8,
};



