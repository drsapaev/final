import React, { useEffect, useMemo, useState } from "react";
import * as api from "../api/client";
import { connectQueueWS } from "../api/ws";

/**
 * Экран табло ожидания (Full HD/UHD дружественно):
 * - Крупный текущий номер
 * - Статистика (ожидают / принимаются / готово)
 * - Автообновление через WS + периодический fallback
 */
export default function DisplayBoard({
  department = "Reg",
  dateStr = todayStr(),
  refreshMs = 15000,
}) {
  const qs = useMemo(
    () => ({ department: String(department).trim(), d: String(dateStr).trim() }),
    [department, dateStr]
  );

  const [stats, setStats] = useState({ last_ticket: 0, waiting: 0, serving: 0, done: 0 });
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const s = await api.get("/queues/stats", { query: qs });
      setStats(s || { last_ticket: 0, waiting: 0, serving: 0, done: 0 });
    } catch (e) {
      setErr(e?.message || "Ошибка загрузки");
    }
  }

  useEffect(() => {
    load();
    const { close } = connectQueueWS({
      department: qs.department,
      dateStr: qs.d,
      onMessage: (msg) => {
        if (msg?.type === "queue.update" && msg?.payload) setStats(msg.payload);
      },
    });
    const t = setInterval(load, Math.max(5000, Number(refreshMs || 0)));
    return () => {
      clearInterval(t);
      close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qs.department, qs.d, refreshMs]);

  return (
    <div style={wrap}>
      <div style={head}>
        <div style={dept}>{department}</div>
        <div style={dateBox}>{dateStr}</div>
      </div>

      <div style={numberBlock}>
        <div style={cap}>СЕЙЧАС ПРИНИМАЕТСЯ</div>
        <div style={bigNumber}>{stats.last_ticket || 0}</div>
      </div>

      <div style={statsRow}>
        <Stat label="Ожидают" value={stats.waiting} />
        <Stat label="Принимаются" value={stats.serving} />
        <Stat label="Готово" value={stats.done} />
      </div>

      {err ? <div style={errBox}>{err}</div> : null}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={statBox}>
      <div style={statLabel}>{label}</div>
      <div style={statValue}>{value ?? 0}</div>
    </div>
  );
}

function todayStr() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

const wrap = {
  minHeight: "100vh",
  background: "linear-gradient(180deg, #0f172a 0%, #111827 100%)",
  color: "white",
  display: "grid",
  gridTemplateRows: "auto 1fr auto",
  gap: 24,
  padding: "24px 32px",
  boxSizing: "border-box",
};
const head = { display: "flex", justifyContent: "space-between", alignItems: "center" };
const dept = { fontSize: "48px", fontWeight: 800, letterSpacing: 1 };
const dateBox = { fontSize: "24px", opacity: 0.9 };
const numberBlock = {
  display: "grid",
  gap: 12,
  placeItems: "center",
  padding: "24px 16px",
  borderRadius: 24,
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.12)",
};
const cap = { fontSize: "18px", letterSpacing: 2, opacity: 0.85 };
const bigNumber = { fontSize: "220px", lineHeight: 1, fontWeight: 900, letterSpacing: 4 };
const statsRow = { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 };
const statBox = {
  borderRadius: 20,
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.12)",
  padding: "16px 20px",
  textAlign: "center",
};
const statLabel = { fontSize: "18px", opacity: 0.8 };
const statValue = { fontSize: "72px", fontWeight: 800, marginTop: 8 };
const errBox = {
  textAlign: "center",
  color: "#fecaca",
  background: "rgba(239,68,68,0.2)",
  border: "1px solid rgba(239,68,68,0.35)",
  padding: 8,
  borderRadius: 12,
};

