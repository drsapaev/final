import React, { useMemo, useState } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import QueueTable from '../components/QueueTable.jsx';

function todayStr() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dd}`;
}

/**
 * Экран Регистратуры:
 *  - выбор отделения (department)
 *  - аналитика текущей очереди
 *  - выдача следующего талона
 */
export default function Registrar() {
  const [page, setPage] = useState('Registrar');
  const [department, setDepartment] = useState('Reg');
  const [date, setDate] = useState(todayStr());

  const deps = useMemo(
    () => [
      { k: 'Reg', label: 'Регистратура' },
      { k: 'Doctor', label: 'Врач' },
      { k: 'Lab', label: 'Лаборатория' },
      { k: 'Cashier', label: 'Касса' },
    ],
    []
  );

  return (
    <div>
      <RoleGate roles={['Admin', 'Registrar']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Регистратура</h2>

          <div style={panel}>
            <label>
              Отделение:&nbsp;
              <select value={department} onChange={(e) => setDepartment(e.target.value)} style={inp}>
                {deps.map((d) => (
                  <option key={d.k} value={d.k}>{d.label}</option>
                ))}
              </select>
            </label>

            <label>
              Дата:&nbsp;
              <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={inp} />
            </label>
          </div>

          <QueueTable department={department} date={date} />
        </div>
      </RoleGate>
    </div>
  );
}

const panel = { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', border: '1px solid #eee', borderRadius: 12, padding: 12, background: '#fff' };
const inp = { padding: '6px 10px', border: '1px solid #ddd', borderRadius: 8, background: '#fff' };

