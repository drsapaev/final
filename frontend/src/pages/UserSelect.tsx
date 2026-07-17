// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useState } from 'react';
import { api } from '../api/client';  // PR-54: replace raw fetch
import { useNavigate } from 'react-router-dom';
import tokenManager from '../utils/tokenManager';
import { roleToRoute } from '../constants/routes';
import {
  AppEmpty, AppError, AppLoading, Button, Card, CardContent, CardHeader,
} from '../components/ui/macos';
import { useTranslation } from '../i18n/useTranslation';

export default function UserSelect() {
  const { t } = useTranslation();
  const [items, setItems] = useState([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    (async () => {
      setLoading(true);
      setErr('');
      try {
        const token = tokenManager.getAccessToken();
        const r = await api.get('/admin/users');
        if (r.status >= 400) throw new Error(`HTTP ${r.status}`);
        const data = r.data;
        setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        setErr(e.message || t('misc.us_oshibka_zagruzki'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <Card style={{ maxWidth: 860 }}>
      <CardHeader>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0, color: 'var(--mac-text-primary)' }}>{t('misc.us_vybor_polzovatelya')}</h1>
        <div style={{ color: 'var(--mac-text-secondary)', fontSize: 13, marginTop: 8 }}>{t('misc.us_dostupno_administratoru_nazh')}</div>
      </CardHeader>
      <CardContent>
      {err && <AppError title={t('misc.us_ne_udalos_zagruzit_polzovate')} description={err} style={{ marginBottom: 12 }} />}
      {loading ? (
        <AppLoading
          title={t('misc.us_zagruzka_polzovateley')}
          description={t('misc.us_poluchaem_spisok_dostupnyh_p')}
          ariaLabel={t('misc.us_zagruzhaem_spisok_polzovatel')}
          size="sm"
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(u => (
            <div
              key={u.id}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 12,
                padding: '12px 14px',
                border: '1px solid var(--mac-card-border)',
                borderRadius: 'var(--mac-radius-md)',
                background: 'var(--mac-card-bg)'
              }}>
              <div>
                <div style={{ fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)' }}>{u.full_name || u.username}</div>
                <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{u.role || '—'} · {u.email || '—'}</div>
              </div>
              <div>
                <Button type="button" variant="outline" size="small" onClick={() => navigate(roleToRoute(u.role))}>
                  Перейти
                </Button>
              </div>
            </div>
          ))}
          {items.length === 0 && <AppEmpty title={t('misc.us_polzovateli_ne_naydeny')} description={t('misc.us_net_polzovateley_dostupnyh_d')} />}
        </div>
      )}
      </CardContent>
    </Card>
  );
}
