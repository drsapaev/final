import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client.js';

/**
 * Универсальный выбор услуги (одиночный или множественный).
 *
 * Props:
 *  - value: object | array<object> | null
 *  - onChange: (val) => void
 *  - multi?: boolean (default: false)
 *  - placeholder?: string
 *  - style?: React.CSSProperties
 */
export default function ServicePicker({
  value = null,
  onChange = () => {},
  multi = false,
  placeholder = 'Выберите услугу…',
  style,
}) {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.get('/services', { params: { limit: 1000 } });
      // ожидаем массив вида [{id, name, code, price, group}]
      setItems(Array.isArray(res?.items) ? res.items : Array.isArray(res) ? res : []);
    } catch {
      // Игнорируем ошибки загрузки услуг
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    if (!q) return items;
    const qq = q.toLowerCase();
    return items.filter(
      (s) =>
        String(s.name || '').toLowerCase().includes(qq) ||
        String(s.code || '').toLowerCase().includes(qq) ||
        String(s.group || '').toLowerCase().includes(qq)
    );
  }, [q, items]);

  function toggle(item) {
    if (!multi) {
      onChange(item);
      return;
    }
    const arr = Array.isArray(value) ? value : [];
    const exists = arr.find((x) => x.id === item.id);
    if (exists) {
      onChange(arr.filter((x) => x.id !== item.id));
    } else {
      onChange([...arr, item]);
    }
  }

  const selectedIds = new Set(
    multi ? (Array.isArray(value) ? value.map((v) => v.id) : []) : value?.id ? [value.id] : []
  );

  return (
    <div style={{ display: 'grid', gap: 8, ...style }}>
      <input
        placeholder="Поиск по названию/коду…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        style={inp}
      />
      <div style={listBox}>
        {loading && <div style={{ padding: 8, opacity: 0.7 }}>Загрузка…</div>}
        {!loading && filtered.length === 0 && (
          <div style={{ padding: 8, opacity: 0.7 }}>Нет услуг</div>
        )}
        {filtered.map((s) => {
          const active = selectedIds.has(s.id);
          return (
            <div
              key={s.id}
              onClick={() => toggle(s)}
              style={{
                ...row,
                background: active ? '#eef2ff' : '#fff',
                borderColor: active ? '#c7d2fe' : '#eee',
                cursor: 'pointer',
              }}
              title={placeholder}
            >
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div style={{ opacity: 0.75, fontSize: 12 }}>
                {s.code ? <code>{s.code}</code> : null}{' '}
                {s.group ? <span>· {s.group}</span> : null}
              </div>
              <div style={{ marginLeft: 'auto', fontWeight: 700 }}>
                {s.price != null ? Number(s.price).toFixed(0) : '—'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const inp = { padding: '8px 10px', border: '1px solid #e5e7eb', borderRadius: 8 };
const listBox = { display: 'grid', gap: 6, maxHeight: 280, overflow: 'auto', border: '1px solid #eee', borderRadius: 10, padding: 6, background: '#fff' };
const row = { display: 'grid', gridTemplateColumns: '1fr auto', gap: 6, alignItems: 'center', padding: 8, border: '1px solid #eee', borderRadius: 8 };

