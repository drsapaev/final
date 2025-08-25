import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { getApiBase, api } from "../api/client";
import { setToken, setProfile } from "../stores/auth";

/**
 * Логин по OAuth2 Password (FastAPI):
 * POST /login с application/x-www-form-urlencoded полями:
 *   username, password, grant_type=password, scope, client_id, client_secret
 */
export default function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

  async function performLogin(u, p) {
    // Собираем абсолютный URL к /login из VITE_API_BASE
    const base = getApiBase().replace(/\/+$/, ""); // http://localhost:8000/api/v1
    const url = `${base}/login`;

    // OAuth2 Password — строго x-www-form-urlencoded + grant_type=password
    const body = new URLSearchParams();
    body.set("username", u);
    body.set("password", p);
    body.set("grant_type", "password");
    body.set("scope", "");
    body.set("client_id", "");
    body.set("client_secret", "");

    const res = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
    });

    if (!res.ok) {
      // Попытка вытащить подробности ошибки от FastAPI
      let detail = "";
      try {
        const text = await res.text();
        detail = text;
      } catch {}
      const msg = `${res.status} ${res.statusText}${detail ? `\n${detail}` : ""}`;
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }

    const data = await res.json();
    const token = data?.access_token;
    if (!token) throw new Error("В ответе не найден access_token");
    setToken(token);

    // Загрузим профиль (GET /me) — уже с Authorization: Bearer <token>
    try {
      const profile = await api.get("/me");
      setProfile(profile || null);
    } catch (e) {
      // Если /me недоступен, это не должно блокировать вход
      setProfile(null);
    }
  }

  async function onLoginClick(e) {
    e?.preventDefault?.();
    if (busy) return;
    setBusy(true);
    setErr("");
    try {
      await performLogin(username, password);
      navigate(from, { replace: true });
    } catch (e2) {
      setErr(e2?.message || "Ошибка входа");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={wrap}>
      <div style={card}>
        <h2 style={{ margin: 0, marginBottom: 8 }}>Вход</h2>

        {err ? <div style={errBox}>{err}</div> : null}

        <div style={{ display: "grid", gap: 10 }}>
          <label style={lbl}>
            <span>Логин</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={inp}
              autoComplete="username"
              disabled={busy}
            />
          </label>
          <label style={lbl}>
            <span>Пароль</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={inp}
              autoComplete="current-password"
              disabled={busy}
            />
          </label>

          <button type="button" disabled={busy} onClick={onLoginClick} style={btnPrimary}>
            {busy ? "Входим..." : "Войти"}
          </button>
        </div>

        <small style={{ opacity: 0.8, lineHeight: 1.4, display: "block", marginTop: 10 }}>
          По умолчанию админ создаётся скриптом <code>ensure_admin.py</code> (admin/admin).
          Настраивается переменными окружения.
        </small>
      </div>
    </div>
  );
}

/* стили */
const wrap = {
  minHeight: "100vh",
  display: "grid",
  placeItems: "center",
  background: "#f8fafc",
  padding: 16,
};
const card = {
  width: "min(420px, 94vw)",
  background: "#fff",
  border: "1px solid #e5e7eb",
  borderRadius: 12,
  boxShadow: "0 10px 30px rgba(0,0,0,.06)",
  padding: 16,
};
const lbl = { display: "grid", gap: 6, fontSize: 14 };
const inp = {
  padding: "10px 12px",
  border: "1px solid #e5e7eb",
  borderRadius: 8,
  outline: "none",
};
const btnPrimary = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #0284c7",
  background: "#0ea5e9",
  color: "white",
  cursor: "pointer",
};
const errBox = {
  color: "#7f1d1d",
  background: "#fee2e2",
  border: "1px solid #fecaca",
  borderRadius: 8,
  padding: 8,
  whiteSpace: "pre-wrap",
  marginBottom: 10,
};

