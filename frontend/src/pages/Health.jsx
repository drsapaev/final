import { useEffect, useState } from 'react';
import { getApiBase } from '../api/client.js';
import { getHealth, getActivationStatus } from '../api/index.js';
import { AppEmpty, AppError, AppLoading } from '../components/ui/macos';
import auth from '../stores/auth.js';

export default function Health() {
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState(null);
  const [act, setAct] = useState(null);
  const [err, setErr] = useState('');
  const [authState, setAuthState] = useState(() => auth.getState());

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
  }, [isAdmin]);

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
    title: {
      fontSize: '28px',
      fontWeight: 700,
      lineHeight: 1.2,
      margin: 0,
    },
    meta: {
      color: 'var(--mac-text-secondary)',
      fontSize: '14px',
      margin: '8px 0 20px',
    },
    section: {
      background: 'var(--mac-card-bg)',
      border: '1px solid var(--mac-card-border, var(--mac-border))',
      borderRadius: '16px',
      boxShadow: 'var(--mac-main-shell-shadow)',
      padding: '18px',
      marginBottom: '18px',
    },
    sectionTitle: {
      fontSize: '18px',
      fontWeight: 650,
      margin: '0 0 12px',
    },
    pre: {
      margin: 0,
      padding: '14px',
      overflow: 'auto',
      borderRadius: '12px',
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      fontSize: '13px',
      lineHeight: 1.5,
      maxHeight: '56vh',
    },
    appState: {
      minHeight: '120px',
      padding: '16px',
    },
  };

  return (
    <div style={styles.page}>
      <main style={styles.main}>
        <h1 style={styles.title}>Состояние приложения</h1>
        <div style={styles.meta}>
          API base: <code>{getApiBase()}</code>
        </div>

        {err && (
          <AppError
            title="Ошибка загрузки"
            description={String(err)}
            style={{ marginBottom: '18px' }}
          />
        )}

        <section style={styles.section} aria-labelledby="health-status-title">
          <h2 id="health-status-title" style={styles.sectionTitle}>Health</h2>
          {loading ? (
            <AppLoading
              title="Проверка состояния сервера..."
              size="sm"
              style={styles.appState}
            />
          ) : health ? (
            <pre style={styles.pre}>
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
          <section style={styles.section} aria-labelledby="activation-status-title">
            <h2 id="activation-status-title" style={styles.sectionTitle}>Статус активации</h2>
            {loading ? (
              <AppLoading
                title="Загрузка статуса..."
                size="sm"
                style={styles.appState}
              />
            ) : act ? (
              <pre style={styles.pre}>
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
