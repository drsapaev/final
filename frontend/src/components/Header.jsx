import React, { useEffect, useState } from "react";
import auth, { setProfile } from "../stores/auth.js";
import { useNavigate } from "react-router-dom";

export default function Header() {
  const [st, setSt] = useState(auth.getState());
  const [lang, setLang] = useState(localStorage.getItem("lang") || "ru");
  const navigate = useNavigate();

  useEffect(() => auth.subscribe(setSt), []);

  function changeLang(v) {
    setLang(v);
    localStorage.setItem("lang", v);
  }

  const user = st.profile || st.user || null;
  const role = user?.role || user?.role_name || "Guest";

  return (
    <div style={bar}>
      <div style={left}>
        <div style={logo} onClick={() => navigate("/")}>🏥 Clinic</div>
        <div style={{ opacity: .6, fontSize: 12 }}>v0.1.0</div>
      </div>

      <div style={center}>
        <button style={link} onClick={() => navigate("/activation")}>Activation</button>
        <button style={link} onClick={() => navigate("/help")}>Help</button>
      </div>

      <div style={right}>
        <select value={lang} onChange={(e)=>changeLang(e.target.value)} style={sel}>
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
          <option value="en">EN</option>
        </select>
        {user ? (
          <>
            <span style={{ opacity: .85 }}>{user.full_name || user.username} · {role}</span>
            <button
              onClick={() => { auth.clearToken(); setProfile(null); navigate("/login"); }}
              style={btn}
            >Выйти</button>
          </>
        ) : (
          <button onClick={() => navigate("/login")} style={btn}>Войти</button>
        )}
      </div>
    </div>
  );
}

const bar = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  padding: "10px 12px",
  borderBottom: "1px solid #e5e7eb",
  position: "sticky",
  top: 0,
  background: "white",
  zIndex: 10,
};
const left = { display: "flex", alignItems: "center", gap: 8 };
const logo = { fontWeight: 800, cursor: "pointer" };
const center = { display: "flex", gap: 8, alignItems: "center" };
const right = { display: "flex", gap: 8, alignItems: "center" };
const sel = { padding: "6px 8px", border: "1px solid #ddd", borderRadius: 8, background: "#fff" };
const btn = { padding: "6px 10px", borderRadius: 8, border: "1px solid #ddd", background: "#fff", cursor: "pointer" };
const link = { padding: "6px 10px", borderRadius: 8, border: "1px solid #eee", background: "#fff", cursor: "pointer" };
