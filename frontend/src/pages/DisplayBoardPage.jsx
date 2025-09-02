import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import DisplayBoard from './DisplayBoard.jsx';
import { api } from '../api/client.js';

export default function DisplayBoardPage() {
  const [params] = useSearchParams();
  const { role } = useParams();
  const [roleMap, setRoleMap] = useState({});
  const roleDept = mapRoleToDept(role, roleMap);
  const baseDept = roleDept || params.get('department') || params.get('dept') || 'Reg';
  const dateStr = params.get('date') || params.get('d') || todayStr();
  const refreshMs = Number(params.get('refreshMs') || params.get('refresh') || 15000);
  const announcement = params.get('announcement') || '';
  const lang = (params.get('lang') || 'ru').toLowerCase();
  const kiosk = params.get('kiosk') === '1' || params.get('kiosk') === 'true';
  const sound = params.get('sound'); // 1/0
  const contrast = params.get('contrast') === '1' || params.get('contrast') === 'true';
  const fontScale = Number(params.get('font') || 1);
  const rotate = (params.get('depts') || '').split(',').map(s => s.trim()).filter(Boolean);
  const rotateSec = Number(params.get('rotate') || 0);

  const [currentDept, setCurrentDept] = useState(baseDept);

  // Авто-ротация отделений по времени
  useEffect(() => {
    if (!rotate.length || !rotateSec) return;
    let idx = 0;
    setCurrentDept(rotate[0] || baseDept);
    const t = setInterval(() => {
      idx = (idx + 1) % rotate.length;
      setCurrentDept(rotate[idx]);
    }, Math.max(3000, rotateSec * 1000));
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rotate.join(','), rotateSec]);

  // Загрузка мэппинга ролей из админских настроек
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await api.get('/settings', { params: { category: 'display_board' } });
        let obj = {};
        if (Array.isArray(res?.items)) {
          res.items.forEach((it) => { if (it.key) obj[String(it.key).toLowerCase()] = it.value; });
        } else if (res && typeof res === 'object') {
          Object.entries(res).forEach(([k, v]) => { obj[String(k).toLowerCase()] = v; });
        }
        if (mounted) setRoleMap(obj);
      } catch (_) {}
    })();
    return () => { mounted = false; };
  }, []);

  const dept = useMemo(() => currentDept || baseDept, [currentDept, baseDept]);

  return (
    <DisplayBoard 
      department={dept} 
      dateStr={dateStr} 
      refreshMs={refreshMs}
      announcement={announcement}
      lang={lang}
      kiosk={kiosk}
      soundInitial={sound}
      contrast={contrast}
      fontScale={isNaN(fontScale) || fontScale <= 0 ? 1 : Math.min(2, fontScale)}
    />
  );
}

function todayStr() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function mapRoleToDept(r, roleMap) {
  if (!r) return '';
  const x = String(r).toLowerCase();
  // сначала ищем в конфиге админки
  if (roleMap && roleMap[x]) return roleMap[x];
  if (x === 'cardio' || x === 'cardiologist') return 'Cardio';
  if (x === 'dentist' || x === 'dental') return 'Dental';
  if (x === 'derma' || x === 'dermatologist') return 'Derma';
  if (x === 'lab' || x === 'laboratory') return 'Lab';
  if (x === 'procedures' || x === 'procedure') return 'Procedures';
  return '';
}


