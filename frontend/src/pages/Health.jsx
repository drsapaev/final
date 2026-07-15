import { useEffect, useState } from 'react';
import { getApiBase } from '../api/client.js';
import { getHealth, getActivationStatus } from '../api/index.js';
import {
  AppEmpty, AppError, AppLoading, Button,
} from '../components/ui/macos';
import auth from '../stores/auth.js';
import { useTranslation } from '../i18n/adapter';

export default function Health() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [act, setAct] = useState(null);
  const [err, setErr] = useState('');
  const [authState, setAuthState] = useState(() => auth.getState());
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => auth.subscribe(setAuthState), []);
  const isAdmin = Boolean(authState?.token) && String(authState?.profile?.role || '').toLowerCase() === 'admin';

  useEffect(() => {
    let mounted = true;
    async function load() {
      setErr('');
      setLoading(true);
      try {
        const [h, a = null] = await Promise.all(
          isAdmin ? [getHealth(), getActivationStatus()] : [getHealth()]
        );
        if (!mounted) return;
        setHealth(h);
        setAct(a);
      } catch (e) {
        if (!mounted) return;
        setErr(e?.data?.detail || e?.message || 'Ошибка загрузки');
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => { mounted = false; };
  }, [isAdmin, refreshNonce]);

  const refreshStatus = () => {
    setRefreshNonce((value) => value + 1);
  };

  const styles = {
    page: {
      minHeight: '100vh',
      background: 'var(--mac-gradient-window)',
      color: 'var(--mac-text-primary)',
      padding: '24px 16px',
    },
    main: {
      maxWidth: '960px',
      margin: '0 auto',
    },
    headingRow: {
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: 'var(--mac-spacing-4)',
      marginBottom: 'var(--mac-spacing-2)',
    },
    headingCopy: {
      minWidth: 0,
    },
    title: {
      fontSize: 'var(--mac-font-size-3xl)',
      fontWeight: 'var(--mac-font-weight-bold)',
      lineHeight: 1.2,
      margin: 0,
    },
    meta: {
      color: 'var(--mac-text-secondary)',
      fontSize: 'var(--mac-font-size-base)',
      margin: '8px 0 20px',
    },
    section: {
      background: 'var(--mac-card-bg)',
      border: '1px solid var(--mac-card-border, var(--mac-border))',
      borderRadius: 'var(--mac-radius-xl)',
      boxShadow: 'var(--mac-main-shell-shadow)',
      padding: '18px',
      marginBottom: '18px',
    },
    sectionTitle: {
      fontSize: 'var(--mac-font-size-xl)',
      fontWeight: 650,
      margin: '0 0 12px',
    },
    pre: {
      margin: 0,
      padding: '14px',
      overflow: 'auto',
      borderRadius: 'var(--mac-radius-lg)',
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      fontSize: 'var(--mac-font-size-sm)',
      lineHeight: 1.5,
      maxHeight: '56vh',
    },
    appState: {
      minHeight: '120px',
      padding: 'var(--mac-spacing-4)',
    },
  };

  return (
    <div style={styles.page}>
      <main style={styles.main} aria-labelledby="health-page-title">
        <div style={styles.headingRow}>
          <div style={styles.headingCopy}>
            <h1 id="health-page-title" style={styles.title}>Состояние приложения</h1>
            <div style={styles.meta}>
              API base: <code>{getApiBase()}</code>
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="small"
            onClick={refreshStatus}
            disabled={loading}
            loading={loading}
            aria-label="Обновить состояние приложения">
            Обновить
          </Button>
        </div>

        {err && (
          <AppError
            title="Ошибка загрузки"
            description={String(err)}
            action={
              <Button
                type="button"
                variant="outline"
                size="small"
                onClick={refreshStatus}
                disabled={loading}
                loading={loading}
                aria-label="Повторить проверку состояния приложения">
                Повторить
              </Button>
            }
            style={{ marginBottom: '18px' }}
          />
        )}

        <section style={styles.section} aria-labelledby="health-status-title" aria-busy={loading}>
          <h2 id="health-status-title" style={styles.sectionTitle}>Health</h2>
          {loading ? (
            <AppLoading
              title="Проверка состояния сервера..."
              description="Запрашиваем текущий ответ health endpoint."
              ariaLabel="Проверяем состояние сервера"
              size="sm"
              style={styles.appState}
            />
          ) : health ? (
            <pre style={styles.pre} aria-label="Ответ health endpoint" tabIndex={0}>
              {typeof health === 'string' ? health : JSON.stringify(health, null, 2)}
            </pre>
          ) : (
            <AppEmpty
              title="Health недоступен"
              description="Спец-эндпоинт health не обнаружен в OpenAPI. Это нормально."
              style={styles.appState}
            />
          )}
        </section>

        {isAdmin && (
          <section style={styles.section} aria-labelledby="activation-status-title" aria-busy={loading}>
            <h2 id="activation-status-title" style={styles.sectionTitle}>Статус активации</h2>
            {loading ? (
              <AppLoading
                title="Загрузка статуса..."
                description="Запрашиваем текущий статус активации для администратора."
                ariaLabel="Загружаем статус активации"
                size="sm"
                style={styles.appState}
              />
            ) : act ? (
              <pre style={styles.pre} aria-label="Ответ activation status endpoint" tabIndex={0}>
                {typeof act === 'string' ? act : JSON.stringify(act, null, 2)}
              </pre>
            ) : (
              <AppEmpty
                title="Статус активации недоступен"
                description="Эндпоинт статуса активации отсутствует в OpenAPI. Всё в порядке."
                style={styles.appState}
              />
            )}
          </section>
        )}
      </main>
    </div>
  );
}
