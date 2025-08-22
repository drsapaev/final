import React, { useEffect, useMemo, useState } from "react";
import Nav from "../components/Nav.jsx";
import RoleGate from "../components/RoleGate.jsx";
import { api } from "../api/client.js";

function TabButton({ active, onClick, children }) {
  const st = {
    padding: "8px 12px",
    borderRadius: 10,
    border: "1px solid #ddd",
    background: active ? "#111" : "#fff",
    color: active ? "#fff" : "#111",
    cursor: "pointer",
  };
  return (
    <button onClick={onClick} style={st}>{children}</button>
  );
}

function Row({ k, v, onSave }) {
  const [val, setVal] = useState(String(v ?? ""));
  useEffect(() => setVal(String(v ?? "")), [v]);
  return (
    <div style={row}>
      <div style={{ fontWeight: 600 }}>{k}</div>
      <input value={val} onChange={(e)=>setVal(e.target.value)} style={inp} />
      <button onClick={()=>onSave(k, val)} style={btn}>Сохранить</button>
    </div>
  );
}

/**
 * Settings:
 *  - Вкладка "license": активация сервера и статус (работает даже при REQUIRE_LICENSE=1)
 *  - Вкладка "printer": простые пары key/value (если backend поддерживает PUT /settings)
 *  - Вкладка "online_queue": простые пары key/value
 */
export default function Settings() {
  const [page, setPage] = useState("Settings");
  const [tab, setTab] = useState("license");

  // license tab
  const [status, setStatus] = useState(null);
  const [key, setKey] = useState("");
  const [busyAct, setBusyAct] = useState(false);
  const [errAct, setErrAct] = useState("");

  async function loadStatus() {
    try {
      const st = await api.get("/activation/status");
      setStatus(st || null);
    } catch {
      setStatus(null);
    }
  }

  async function doActivate() {
    setBusyAct(true);
    setErrAct("");
    try {
      const res = await api.post("/activation/activate", { body: { key } });
      if (!res?.ok) {
        setErrAct(res?.reason || "Не удалось активировать");
      }
      await loadStatus();
    } catch (e) {
      setErrAct(e?.data?.detail || e?.message || "Ошибка активации");
    } finally {
      setBusyAct(false);
    }
  }

  useEffect(() => { if (tab === "license") loadStatus(); }, [tab]);

  // generic category settings (printer / online_queue)
  const [cat, setCat] = useState("printer");
  const [items, setItems] = useState([]);
  const [busyCat, setBusyCat] = useState(false);
  const [errCat, setErrCat] = useState("");

  async function loadCat(category) {
    setBusyCat(true);
    setErrCat("");
    try {
      // Ожидаем форму {items:[{key,value}]} или массив объектов
      const res = await api.get("/settings", { params: { category } });
      let arr = [];
      if (Array.isArray(res?.items)) arr = res.items;
      else if (Array.isArray(res)) arr = res;
      else if (res && typeof res === "object") {
        // возможный словарь
        arr = Object.entries(res).map(([k, v]) => ({ key: k, value: v }));
      }
      setItems(arr.map(x => ({ key: x.key ?? x.name ?? "", value: x.value ?? "" })));
    } catch (e) {
      setErrCat(e?.data?.detail || e?.message || "Ошибка загрузки настроек");
      setItems([]);
    } finally {
      setBusyCat(false);
    }
  }

  async function saveKV(category, key, value) {
    try {
      await api.put("/settings", { body: { category, key, value } });
      await loadCat(category);
    } catch (e) {
      alert(e?.data?.detail || e?.message || "Ошибка сохранения");
    }
  }

  useEffect(() => {
    if (tab === "printer" || tab === "online_queue") {
      const c = tab === "printer" ? "printer" : "online_queue";
      setCat(c);
      loadCat(c);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const licenseOk = !!status?.ok;
  const badge = useMemo(() => {
    const st = status?.status || (licenseOk ? "active" : "not_active");
    return (
      <span style={{
        padding: "2px 8px", borderRadius: 999,
        background: licenseOk ? "#ecfdf5" : "#fef2f2",
        color: licenseOk ? "#065f46" : "#7f1d1d",
        border: `1px solid ${licenseOk ? "#a7f3d0" : "#fecaca"}`,
        fontSize: 12,
        whiteSpace: "nowrap",
      }}>{st}</span>
    );
  }, [status, licenseOk]);

  return (
    <div>
      <Nav active={page} onNavigate={setPage} />
      <RoleGate roles={["Admin"]}>
        <div style={{ padding: 16, display: "grid", gap: 12 }}>
          <h2 style={{ margin: 0 }}>Настройки</h2>

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <TabButton active={tab==="license"} onClick={()=>setTab("license")}>Лицензия</TabButton>
            <TabButton active={tab==="printer"} onClick={()=>setTab("printer")}>Принтер</TabButton>
            <TabButton active={tab==="online_queue"} onClick={()=>setTab("online_queue")}>Онлайн-очередь</TabButton>
          </div>

          {tab === "license" && (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Статус активации</div>
                <div style={{ display: "grid", gap: 4 }}>
                  <div>Состояние: {badge}</div>
                  <div>Ключ: <code>{status?.key || "—"}</code></div>
                  <div>Machine hash: <code>{status?.machine_hash || "—"}</code></div>
                  <div>Действует до: <b>{status?.expiry_date || "—"}</b></div>
                </div>
              </div>

              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Активация сервера</div>
                {errAct && <div style={errBox}>{String(errAct)}</div>}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <input
                    placeholder="Вставьте ключ активации"
                    value={key}
                    onChange={(e)=>setKey(e.target.value)}
                    style={{ ...inp, minWidth: 320 }}
                  />
                  <button onClick={doActivate} disabled={busyAct || !key.trim()} style={btnPrimary}>
                    {busyAct ? "..." : "Активировать"}
                  </button>
                  <button onClick={loadStatus} style={btn}>Обновить статус</button>
                </div>
                <div style={{ fontSize: 12, opacity: .7, marginTop: 6 }}>
                  При отсутствии ключа — обратитесь к администратору для выдачи.
                </div>
              </div>
            </div>
          )}

          {(tab === "printer" || tab === "online_queue") && (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>
                  Категория: <code>{cat}</code>
                </div>
                {busyCat && <div style={{ opacity: .7 }}>Загрузка…</div>}
                {errCat && <div style={errBox}>{String(errCat)}</div>}
                <div style={{ display: "grid", gap: 8 }}>
                  {items.map((it) => (
                    <Row
                      key={it.key}
                      k={it.key}
                      v={it.value}
                      onSave={(k, v) => saveKV(cat, k, v)}
                    />
                  ))}
                  {!busyCat && items.length === 0 && (
                    <div style={{ opacity: .7 }}>Записей нет</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </RoleGate>
    </div>
  );
}

const card = { border: "1px solid #eee", borderRadius: 12, padding: 12, background: "#fff" };
const row  = { display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8, alignItems: "center" };
const inp  = { padding: "6px 10px", border: "1px solid #ddd", borderRadius: 8, background: "#fff" };
const btn  = { padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" };
const btnPrimary = { ...btn, borderColor: "#0284c7", background: "#0ea5e9", color: "#fff" };
const errBox = { color: "#7f1d1d", background: "#fee2e2", border: "1px solid #fecaca", borderRadius: 8, padding: 8 };