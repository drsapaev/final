// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useMemo, useState, useCallback } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';
import {
  AppEmpty, AppError, AppLoading, Button, Card, CardContent, CardHeader, Input,
} from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';

/**
 * Аудит: список последних действий пользователей.
 * Совместимо с GET /audit?limit=...&offset=...
 */
export default function Audit() {
  const { t } = useTranslation();
  const [rows, setRows] = useState([]);
  const [limit, setLimit] = useState(100);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setBusy(true);
    setErr('');
    try {
      const res = await api.get('/audit', { params: { limit } });
      const payload = res?.data;
      const items = Array.isArray(payload) ? payload : Array.isArray(res) ? res : [];
      setRows(items);
    } catch (e) {
      setErr(e?.data?.detail || e?.message || t('misc.a_oshibka_zagruzki_audita'));
    } finally {
      setBusy(false);
    }
  }, [limit]);

  useEffect(() => {load();}, [load]);

  const filtered = useMemo(() => {
    if (!q) return rows;
    const qq = q.toLowerCase();
    return rows.filter((a) =>
    String(a.user || a.username || a.actor_user_id || '').toLowerCase().includes(qq) ||
    String(a.action || '').toLowerCase().includes(qq) ||
    String(a.entity || a.table || a.entity_type || '').toLowerCase().includes(qq) ||
    String(a.id || '').toLowerCase().includes(qq)
    );
  }, [q, rows]);

  const stateCellStyle = { minHeight: '96px', padding: 'var(--mac-spacing-4)' };
  const visuallyHiddenStyle = {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: 0,
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    border: 0
  };
  const limitInputId = 'audit-limit';
  const searchInputId = 'audit-search';
  const tableCaptionId = 'audit-table-caption';
  const toolbarStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    flexWrap: 'wrap'
  };
  const fieldStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    color: 'var(--mac-text-secondary)',
    fontSize: 13
  };
  const tableWrapStyle = {
    overflowX: 'auto',
    border: '1px solid var(--mac-card-border)',
    borderRadius: 8,
    background: 'var(--mac-card-bg)',
    marginTop: 16
  };
  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  return (
    <div>
      <RoleGate roles={['Admin']}>
        <Card>
          <CardHeader>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <h2 style={{ margin: 0, color: 'var(--mac-text-primary)' }}>{t('misc.a_audit')}</h2>
              <span style={{ color: 'var(--mac-text-secondary)', fontSize: 13 }}>
                {filtered.length} из {rows.length}
              </span>
            </div>
          </CardHeader>

          <CardContent>
          <div style={toolbarStyle}>
            <label htmlFor={limitInputId} style={fieldStyle}>
              Порог:&nbsp;
              <Input
                id={limitInputId}
                type="number"
                min={10}
                max={1000}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value) || 100)}
                aria-label={t('misc.a_kolichestvo_zapisey_audita_d')}
              />
            </label>
            <label htmlFor={searchInputId} style={visuallyHiddenStyle}>
              Поиск по пользователю, действию, сущности или ID
            </label>
            <Input
              id={searchInputId}
              placeholder={t('misc.a_poisk_po_polzovatelyu_deystv')}
              value={q}
              onChange={(e) => setQ(e.target.value)}
              style={{ minWidth: 260 }}
              aria-label={t('misc.a_poisk_po_zhurnalu_audita')}
            />
            <Button
              type="button"
              variant="outline"
              size="small"
              onClick={load}
              disabled={busy}
              loading={busy}
              aria-label={t('misc.a_obnovit_zhurnal_audita')}>
              Обновить
            </Button>
          </div>

          {err && (
            <AppError
              title={t('misc.a_oshibka_zagruzki_audita')}
              description={String(err)}
              action={
                <Button
                  type="button"
                  variant="outline"
                  size="small"
                  onClick={load}
                  disabled={busy}
                  loading={busy}
                  aria-label={t('misc.a_povtorit_zagruzku_zhurnala_a')}>
                  Повторить
                </Button>
              }
              style={{ marginBottom: 12 }}
            />
          )}

          <div style={tableWrapStyle} aria-busy={busy} aria-describedby={tableCaptionId}>
            <div className="admin-table-wrapper">
<table style={tableStyle}>
              <caption id={tableCaptionId} style={visuallyHiddenStyle}>{t('misc.a_zhurnal_audita')}</caption>
              <thead>
                <tr>
                  <th>{t('common.time')}</th>
                  <th>{t('misc.a_polzovatel')}</th>
                  <th>{t('misc.a_deystvie')}</th>
                  <th>{t('misc.a_suschnost')}</th>
                  <th>{t('misc.a_detali')}</th>
                </tr>
              </thead>
              <tbody>
                {busy && rows.length === 0 ? (
                  <tr>
                    <td colSpan={5}>
                      <AppLoading
                        title={t('misc.a_zagruzka_audita')}
                        description={t('misc.a_poluchaem_poslednie_deystviy')}
                        ariaLabel={t('misc.a_zagruzhaem_zhurnal_audita')}
                        size="sm"
                        style={stateCellStyle}
                      />
                    </td>
                  </tr>
                ) : (
                  <>
                    {filtered.map((a, i) =>
                    <tr key={a.id || i}>
                        <td>{a.created_at || a.time || '—'}</td>
                        <td>{a.user || a.username || a.actor_user_id || '—'}</td>
                        <td>{a.action || '—'}</td>
                        <td>{a.entity || a.table || a.entity_type || '—'}</td>
                        <td><code style={{ fontSize: 12 }}>{a.details ? JSON.stringify(a.details) : a.payload ? JSON.stringify(a.payload) : '—'}</code></td>
                      </tr>
                    )}
                    {filtered.length === 0 && (
                      <tr>
                        <td colSpan={5}>
                          <AppEmpty
                            title={t('misc.a_net_zapisey')}
                            description={q ? t('misc.a_po_tekuschemu_poisku_zapisi_') : t('misc.a_zhurnal_audita_poka_pust')}
                            style={stateCellStyle}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                )}
              </tbody>
            </table>
</div>
          </div>
          </CardContent>
        </Card>
      </RoleGate>
    </div>);

}
