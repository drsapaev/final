import React, { useState } from 'react';

export default function Search() {
  const [q, setQ] = useState('');
  const [patients, setPatients] = useState([]);
  const [visits, setVisits] = useState([]);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const token = localStorage.getItem('auth_token');
      const p = await fetch(`/api/v1/patients/?q=${encodeURIComponent(q)}&limit=20`, { headers: { Authorization: `Bearer ${token}` } });
      const v = await fetch('/api/v1/visits/visits?limit=20', { headers: { Authorization: `Bearer ${token}` } });
      const pp = p.ok ? await p.json() : [];
      const vv = v.ok ? await v.json() : [];
      setPatients(Array.isArray(pp) ? pp : []);
      setVisits(Array.isArray(vv) ? vv : []);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: '20px auto', padding: 16, display: 'grid', gap: 12 }}>
      <h1 style={{ margin: 0 }}>Поиск</h1>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={q} onChange={(e)=>setQ(e.target.value)} placeholder="ФИО / телефон / ID / № визита" style={{ flex: 1, padding: '8px 12px', border: '1px solid #ddd', borderRadius: 8 }} />
        <button onClick={run} disabled={busy} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #ddd', background: '#fff' }}>{busy ? '...' : 'Искать'}</button>
      </div>

      <div style={{ display: 'grid', gap: 10 }}>
        <div>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Пациенты</div>
          {patients.map(p => (
            <div key={p.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 8, background: '#fff' }}>
              #{p.id} · {p.last_name} {p.first_name} {p.middle_name || ''} · {p.phone || '—'}
            </div>
          ))}
          {patients.length === 0 && <div style={{ opacity: .7 }}>Ничего не найдено</div>}
        </div>
        <div>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Визиты</div>
          {visits.map(v => (
            <div key={v.id} style={{ border: '1px solid #eee', borderRadius: 8, padding: 8, background: '#fff' }}>
              Визит #{v.id} · Статус: {v.status || '—'}
            </div>
          ))}
          {visits.length === 0 && <div style={{ opacity: .7 }}>Ничего не найдено</div>}
        </div>
      </div>
    </div>
  );
}
