import React, { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { openQueueWS } from '../api/ws';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Экран табло ожидания (Full HD/UHD дружественно):
 * - Крупный текущий номер
 * - Статистика (ожидают / принимаются / готово)
 * - Автообновление через WS + периодический fallback
 */
export default function DisplayBoard({
  department = 'Reg',
  dateStr = todayStr(),
  refreshMs = 15000,
  announcement = '', // fallback, если не задан в админке
  lang = 'ru',
  kiosk = false,
  soundInitial = undefined, // '1'|'0'|undefined
  contrast = false,
  fontScale = 1,
}) {
  const { isDark, isLight, getColor, getSpacing, getFontSize } = useTheme();
  
  const qs = useMemo(
    () => ({ department: String(department).trim(), d: String(dateStr).trim() }),
    [department, dateStr]
  );

  const [stats, setStats] = useState({ last_ticket: 0, waiting: 0, serving: 0, done: 0 });
  const [err, setErr] = useState('');
  const [nowStr, setNowStr] = useState(timeNow());
  const [board, setBoard] = useState({
    brand: 'Clinic',
    logo: '',
    is_paused: false,
    is_closed: false,
    announcement: '',
    announcement_ru: '',
    announcement_uz: '',
    announcement_en: '',
    primary_color: '',
    bg_color: '',
    text_color: '',
    contrast_default: false,
    kiosk_default: false,
    sound_default: true,
  });
  const lastTicketRef = useRef(0);
  const [soundOn, setSoundOn] = useState(() => (soundInitial === '0' ? false : true));
  const [online, setOnline] = useState(true);
  const [windows, setWindows] = useState([]); // [{window: '1', ticket: 25, room: 'A-101'}]
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  async function load() {
    setErr('');
    try {
      const s = await api.get('/queues/stats', { query: qs });
      setStats(s || { last_ticket: 0, waiting: 0, serving: 0, done: 0 });
      setLastUpdatedAt(timeNow());
      try {
        localStorage.setItem(`board.stats.${qs.department}`, JSON.stringify(s || {}));
      } catch (_) {}
    } catch (e) {
      setErr(e?.message || 'Ошибка загрузки');
      // fallback из кэша
      try {
        const raw = localStorage.getItem(`board.stats.${qs.department}`);
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && typeof cached === 'object') setStats({ ...stats, ...cached });
        }
      } catch (_) {}
    }
  }

  async function loadBoardState() {
    try {
      const st = await api.get('/board/state');
      if (st && typeof st === 'object') {
        setBoard({
          brand: st.brand || st.title || 'Clinic',
          logo: st.logo || st.logo_url || '',
          is_paused: !!(st.is_paused || st.paused),
          is_closed: !!(st.is_closed || st.closed),
          announcement: st.announcement || st.ticker || '',
          announcement_ru: st.announcement_ru || '',
          announcement_uz: st.announcement_uz || '',
          announcement_en: st.announcement_en || '',
          primary_color: st.primary_color || '',
          bg_color: st.bg_color || '',
          text_color: st.text_color || '',
          contrast_default: !!(st.contrast_default),
          kiosk_default: !!(st.kiosk_default),
          sound_default: st.sound_default !== false,
        });
        if (soundInitial === undefined && typeof st.sound_default !== 'undefined') {
          setSoundOn(st.sound_default !== false);
        }
        try { localStorage.setItem('board.state', JSON.stringify(st)); } catch(_){}
      }
    } catch (_) {
      // fallback из кэша
      try {
        const raw = localStorage.getItem('board.state');
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && typeof cached === 'object') {
            setBoard({
              brand: cached.brand || cached.title || 'Clinic',
              logo: cached.logo || cached.logo_url || '',
              is_paused: !!(cached.is_paused || cached.paused),
              is_closed: !!(cached.is_closed || cached.closed),
              announcement: cached.announcement || cached.ticker || '',
              announcement_ru: cached.announcement_ru || '',
              announcement_uz: cached.announcement_uz || '',
              announcement_en: cached.announcement_en || '',
              primary_color: cached.primary_color || '',
              bg_color: cached.bg_color || '',
              text_color: cached.text_color || '',
              contrast_default: !!(cached.contrast_default),
              kiosk_default: !!(cached.kiosk_default),
              sound_default: cached.sound_default !== false,
            });
          }
        }
      } catch (_) {}
    }
  }

  async function loadWindows() {
    try {
      const st = await api.get('/queue/queue/status');
      let arr = [];
      if (Array.isArray(st?.windows)) arr = st.windows;
      else if (Array.isArray(st)) arr = st;
      else if (st && typeof st === 'object' && Array.isArray(st.items)) arr = st.items;
      const norm = arr.map((x) => ({
        window: x.window || x.win || x.cabinet || x.room || '',
        ticket: x.ticket || x.number || x.last_ticket || 0,
        label: x.label || '',
      })).filter((x) => x.window);
      setWindows(norm);
    } catch (_) {
      setWindows([]);
    }
  }

  useEffect(() => {
    load();
    loadBoardState();
    loadWindows();
    const close = openQueueWS(qs.department, qs.d, (msg) => {
      if (msg?.type === 'queue.update' && msg?.payload) setStats(msg.payload);
    });
    const t = setInterval(load, Math.max(5000, Number(refreshMs || 0)));
    const tb = setInterval(loadBoardState, Math.max(15000, Number(refreshMs || 0)));
    const tw = setInterval(loadWindows, Math.max(5000, Number(refreshMs || 0)));
    const clock = setInterval(() => setNowStr(timeNow()), 1000);
    return () => {
      clearInterval(t);
      clearInterval(tb);
      clearInterval(tw);
      clearInterval(clock);
      close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qs.department, qs.d, refreshMs]);

  // Звук при смене номера
  useEffect(() => {
    const prev = Number(lastTicketRef.current || 0);
    const cur = Number(stats.last_ticket || 0);
    if (cur && cur !== prev && soundOn) playBeep();
    lastTicketRef.current = cur;
  }, [stats.last_ticket, soundOn]);

  // online/offline
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    setOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, []);

  return (
    <div style={{ 
      ...wrap,
      ...(contrast || board.contrast_default ? wrapContrast : null),
      ...(kiosk || board.kiosk_default ? wrapKiosk : null),
      ...(board.bg_color ? { background: board.bg_color } : null),
      ...(board.text_color ? { color: board.text_color } : null),
      fontSize: `calc(1rem * ${fontScale})`
    }}>
      <div style={head}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {board.logo ? (
            <img src={board.logo} alt={board.brand} style={logoImg} />
          ) : (
            <div style={logoFallback}>🏥</div>
          )}
          <div style={brandTitle}>{board.brand}</div>
          <div style={dividerV} />
          <div style={dept}>{department}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={dateBox}>{dateStr}</div>
          <div style={clockBox}>{nowStr}</div>
          {lastUpdatedAt ? <div style={updBox}>{t('updated', lang)}: {lastUpdatedAt}</div> : null}
          <button onClick={() => {
            if (document.fullscreenElement) {
              document.exitFullscreen();
            } else {
              document.documentElement.requestFullscreen();
            }
          }} style={fsBtn} title="Полноэкранный режим">⛶</button>
          <button onClick={()=>setSoundOn(s=>!s)} style={fsBtn} title={soundOn ? 'Выключить звук' : 'Включить звук'}>{soundOn ? '🔊' : '🔇'}</button>
        </div>
      </div>

      {!online && (
        <div style={{ ...banner, background: 'rgba(59,130,246,0.25)', borderColor: 'rgba(59,130,246,0.5)' }}>
          Нет соединения. Показаны данные из кэша.
        </div>
      )}

      {board.is_closed && (
        <div style={{ ...banner, background: 'rgba(239,68,68,0.25)', borderColor: 'rgba(239,68,68,0.5)' }}>
          {t('closed', lang)}
        </div>
      )}

      {!board.is_closed && board.is_paused && (
        <div style={{ ...banner, background: 'rgba(245,158,11,0.25)', borderColor: 'rgba(245,158,11,0.5)' }}>
          {t('paused', lang)}
        </div>
      )}

      <div style={numberBlock}>
        <div style={cap}>{t('now_serving', lang)}</div>
        <div style={bigNumber} aria-live="polite">{stats.last_ticket || 0}</div>
      </div>

      {/* Следующие номера */}
      <div style={nextRow}>
        {getNextNumbers(stats.last_ticket, 5).map((n) => (
          <div key={n} style={nextChip}>{n}</div>
        ))}
      </div>

      {/* Окна / Кабинеты */}
      {windows && windows.length > 0 && (
        <div style={winGrid}>
          {windows.map((w, i) => (
            <div key={i} style={winCard}>
              <div style={winTitle}>Окно {w.window}</div>
              <div style={winNumber}>{w.ticket || '—'}</div>
              {w.label ? <div style={winHint}>{w.label}</div> : null}
            </div>
          ))}
        </div>
      )}

      <div style={statsRow}>
        <Stat label="Ожидают" value={stats.waiting} color="#f59e0b" />
        <Stat label="Принимаются" value={stats.serving} color="#10b981" />
        <Stat label="Готово" value={stats.done} color="#3b82f6" />
      </div>

      {err ? <div style={errBox}>{err}</div> : null}

      {(getAnnouncement(board, lang) || announcement) ? (
        <div style={footerRow}>
          <div style={ticker}>
            <div style={tickerInner}>
              {getAnnouncement(board, lang) || announcement || 'Добро пожаловать! Пожалуйста, ожидайте своей очереди.'}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div style={{ ...statBox, borderColor: rgba(color || 'rgba(255,255,255,0.12)', 0.6) }}>
      <div style={statLabel}>{label}</div>
      <div style={{ ...statValue, color: color || 'inherit' }}>{value ?? 0}</div>
    </div>
  );
}

function todayStr() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

// Объявляем стили до их использования - используем CSS переменные
const errBox = {
  textAlign: 'center',
  color: 'var(--danger-color)',
  background: 'rgba(239, 68, 68, 0.1)',
  border: '1px solid var(--danger-color)',
  padding: 8,
  borderRadius: 12,
};

const wrap = {
  minHeight: '100vh',
  background: 'linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%)',
  color: 'var(--text-primary)',
  display: 'grid',
  gridTemplateRows: 'auto 1fr auto',
  gap: 24,
  padding: '24px 32px',
  boxSizing: 'border-box',
};
const wrapContrast = {
  background: 'black',
  color: 'white',
};
const wrapKiosk = {
  cursor: 'none',
};
const head = { display: 'flex', justifyContent: 'space-between', alignItems: 'center' };
const dept = { fontSize: '48px', fontWeight: 800, letterSpacing: 1 };
const dateBox = { fontSize: '24px', opacity: 0.9 };
const clockBox = { fontSize: '24px', opacity: 0.9 };
const fsBtn = { fontSize: 18, padding: '6px 10px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(255,255,255,0.06)', color: 'white', cursor: 'pointer' };
const updBox = { fontSize: 14, opacity: 0.8 };
const logoImg = { width: 48, height: 48, objectFit: 'contain', borderRadius: 8, background: 'rgba(255,255,255,0.1)' };
const logoFallback = { width: 48, height: 48, display: 'grid', placeItems: 'center', fontSize: 28, borderRadius: 8, background: 'rgba(255,255,255,0.1)' };
const brandTitle = { fontSize: 28, fontWeight: 800, letterSpacing: 1 };
const dividerV = { width: 2, height: 28, background: 'rgba(255,255,255,0.2)', margin: '0 8px' };
const numberBlock = {
  display: 'grid',
  gap: 12,
  placeItems: 'center',
  padding: '24px 16px',
  borderRadius: 24,
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.12)',
};
const cap = { fontSize: '18px', letterSpacing: 2, opacity: 0.85 };
const bigNumber = { fontSize: '220px', lineHeight: 1, fontWeight: 900, letterSpacing: 4 };
const statsRow = { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 };
const statBox = {
  borderRadius: 20,
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.25)',
  padding: '16px 20px',
  textAlign: 'center',
};
const statLabel = { fontSize: '18px', opacity: 0.8 };
const statValue = { fontSize: '72px', fontWeight: 800, marginTop: 8 };
const footerRow = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 };
const ticker = { overflow: 'hidden', flex: 1, borderRadius: 12, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.06)' };
const tickerInner = { display: 'inline-block', padding: '10px 16px', whiteSpace: 'nowrap', animation: 'ticker 20s linear infinite' };
const banner = { border: '1px solid', borderRadius: 12, padding: 12, textAlign: 'center', fontSize: 18 };

// Следующие номера
const nextRow = { display: 'flex', gap: 12, justifyContent: 'center', alignItems: 'center', marginTop: 8 };
const nextChip = {
  minWidth: 90,
  padding: '10px 14px',
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.2)',
  background: 'rgba(255,255,255,0.06)',
  fontSize: 28,
  fontWeight: 800,
  textAlign: 'center',
};

// Окна / Кабинеты
const winGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginTop: 12 };
const winCard = {
  border: '1px solid rgba(255,255,255,0.2)',
  background: 'rgba(255,255,255,0.06)',
  borderRadius: 16,
  padding: 16,
  display: 'grid',
  justifyItems: 'center',
  gap: 8,
};
const winTitle = { fontSize: 18, opacity: 0.9 };
const winNumber = { fontSize: 72, fontWeight: 900, letterSpacing: 2 };
const winHint = { fontSize: 14, opacity: 0.8 };

function playBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = 'sine';
    o.frequency.value = 880;
    g.gain.value = 0.05;
    o.connect(g);
    g.connect(ctx.destination);
    o.start();
    setTimeout(() => { o.stop(); ctx.close(); }, 250);
  } catch (_) {}
}

function rgba(hexOrRgba, alpha) {
  if (!hexOrRgba) return `rgba(255,255,255,${alpha})`;
  if (hexOrRgba.startsWith('rgba') || hexOrRgba.startsWith('rgb')) return hexOrRgba;
  // parse #rrggbb
  const m = /^#?([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(hexOrRgba);
  if (!m) return `rgba(255,255,255,${alpha})`;
  const r = parseInt(m[1], 16);
  const g = parseInt(m[2], 16);
  const b = parseInt(m[3], 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function timeNow() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function getNextNumbers(last, count) {
  const base = Number(last || 0);
  return Array.from({ length: Math.max(0, count || 0) }, (_, i) => base + i + 1);
}

function t(key, lang = 'ru') {
  const dict = {
    ru: {
      now_serving: 'СЕЙЧАС ПРИНИМАЕТСЯ',
      paused: 'Очередь приостановлена. Пожалуйста, ожидайте.',
      closed: 'Очередь закрыта. Пожалуйста, обратитесь к администратору.',
      updated: 'Обновлено',
    },
    uz: {
      now_serving: 'HOZIR QABUL QILINMOQDA',
      paused: 'Navbat to‘xtatilgan. Iltimos, kuting.',
      closed: 'Navbat yopilgan. Iltimos, administratorga murojaat qiling.',
      updated: 'Yangilandi',
    },
    en: {
      now_serving: 'NOW SERVING',
      paused: 'Queue is paused. Please wait.',
      closed: 'Queue is closed. Please contact administrator.',
      updated: 'Updated',
    },
  };
  const d = dict[lang] || dict.ru;
  return d[key] || key;
}

function getAnnouncement(board, lang) {
  if (!board) return '';
  if (lang === 'ru' && board.announcement_ru) return board.announcement_ru;
  if (lang === 'uz' && board.announcement_uz) return board.announcement_uz;
  if (lang === 'en' && board.announcement_en) return board.announcement_en;
  return board.announcement || '';
}

