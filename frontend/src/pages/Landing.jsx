import React from "react";
import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div style={wrap}>
      <div style={card}>
        <div style={{ fontSize: 36, fontWeight: 800, marginBottom: 8 }}>🏥 Clinic Manager</div>
        <div style={{ opacity: .7, marginBottom: 16 }}>Добро пожаловать в систему клиники</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
          <button onClick={()=>navigate('/login')} style={btnPrimary}>Войти</button>
          <button onClick={()=>navigate('/activation')} style={btn}>Активировать аккаунт</button>
        </div>
        <div style={{ marginTop: 8, fontSize: 12, opacity: .7 }}>
          RU / UZ / EN
        </div>
      </div>

      <div style={card}>
        <div style={{ fontWeight: 700, marginBottom: 6 }}>Контакты</div>
        <div>Адрес: г. Ташкент, ул. Примерная 1</div>
        <div>Телефон: +998 (90) 000-00-00</div>
        <div>График: Пн–Сб 9:00–18:00</div>
        <div>Telegram: @clinic</div>
      </div>

      <div style={{ opacity: .6, fontSize: 12, marginTop: 12 }}>
        v0.1.0 · Политика конфиденциальности · Условия использования
      </div>
    </div>
  );
}

const wrap = { maxWidth: 920, margin: '40px auto', padding: 16, display: 'grid', gap: 16 };
const card = { border: '1px solid #eee', borderRadius: 12, background: '#fff', padding: 16 };
const btn = { padding: '10px 14px', borderRadius: 10, border: '1px solid #ddd', background: '#fff', cursor: 'pointer' };
const btnPrimary = { ...btn, borderColor: '#0284c7', background: '#0ea5e9', color: '#fff' };
