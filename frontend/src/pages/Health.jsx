import React, { useEffect, useState } from "react";
import Nav from "../components/Nav.jsx";
import RoleGate from "../components/RoleGate.jsx";
import { api, getApiBase } from "../api/client.js";

export default function Health() {
  const [page, setPage] = useState("Health");
  const [health, setHealth] = useState(null);
  const [act, setAct] = useState(null);
  const [err, setErr] = useState("");

  async function load() {
    setErr("");
    try {
      const [h, a] = await Promise.all([
        api.get("/health").catch(() => null),
        api.get("/activation/status").catch(() => null),
      ]);
      setHealth(h);
      setAct(a);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || "Ошибка загрузки");
    }
  }

  useEffect(() => { load(); }, []);

  const base = getApiBase();

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <div style={{ padding: 16, display: "grid", gap: 12 }}>
        <h2 style={{ margin: 0 }}>Health</h2>

        {err && <div style={errBox}>{String(err)}</div>}

        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Backend</div>
          <div>API base: <code>{base}</code></div>
          <div>Состояние:{" "}
            <b style={{ color: (health?.status === "ok" ? "#065f46" : "#7f1d1d") }}>
              {health?.status || "unknown"}
            </b>
          </div>
          {health?.version && <div>Версия: <code>{health.version}</code></div>}
          {health?.time && <div>Время сервера: <code>{health.time}</code></div>}
          {health?.db && <div>База данных: <code>{health.db}</code></div>}
        </div>

        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Активация</div>
          <div>
            Статус:{" "}
            <span style={{
              padding: "2px 8px", borderRadius: 999,
              background: act?.ok ? "#ecfdf5" : "#fef2f2",
              color: act?.ok ? "#065f46" : "#7f1d1d",
              border: `1px solid ${act?.ok ? "#a7f3d0" : "#fecaca"}`,
              fontSize: 12, whiteSpace: "nowrap",
            }}>
              {act?.status || (act?.ok ? "active" : "not_active")}
            </span>
          </div>
          <div>Ключ: <code>{act?.key || "—"}</code></div>
          <div>Machine hash: <code>{act?.machine_hash || "—"}</code></div>
          <div>Действует до: <b>{act?.expiry_date || "—"}</b></div>
        </div>

        <div style={{ fontSize: 12, opacity: .7 }}>
          Подсказка: если активация требуются — перейдите в <b>Настройки → Лицензия</b> или используйте панель <b>Activation</b> (Admin).
        </div>
      </div>
    </div>
  );
}

const card = { border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" };
const errBox = { color: "#7f1d1d", background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 8, padding: 8 };