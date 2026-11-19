import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Alert, Badge, Button, Card, CardContent } from '../components/ui/macos';
import { telegramMiniAppSessions, type MiniAppSession } from '../api/telegramMiniAppSession';
import './TelegramMiniAppSessions.css';

type Translate = (key: string, params?: Record<string, unknown>) => string;
type PendingAction = { type: 'device'; id: string } | { type: 'others' } | { type: 'logout' };

export default function TelegramMiniAppSessions({
  initData, languageCode, t, onLoggedOut,
}: {
  initData: string;
  languageCode: string;
  t: Translate;
  onLoggedOut: () => void;
}) {
  const [sessionView, setSessionView] = useState<{ initData: string; sessions: MiniAppSession[] }>(
    () => ({ initData, sessions: [] }),
  );
  const [loading, setLoading] = useState(Boolean(initData));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const confirmation = useRef<HTMLElement>(null);
  const generation = useRef(0);
  const listGeneration = useRef(0);
  const isCurrentView = sessionView.initData === initData;
  const sessions = isCurrentView ? sessionView.sessions : [];

  // Invalidate old continuations as soon as the new launch is committed,
  // before the browser can paint or an old action can schedule a follow-up.
  useLayoutEffect(() => {
    generation.current += 1;
    listGeneration.current += 1;
    return () => {
      generation.current += 1;
      listGeneration.current += 1;
    };
  }, [initData]);

  useEffect(() => {
    const ownGeneration = generation.current;
    const ownListGeneration = ++listGeneration.current;
    const isCurrent = () => generation.current === ownGeneration
      && listGeneration.current === ownListGeneration;
    setSessionView({ initData, sessions: [] });
    setLoading(Boolean(initData));
    setBusy(false);
    setError(false);
    setDone(false);
    setPending(null);
    if (!initData) return;
    telegramMiniAppSessions.list(initData)
      .then((data) => {
        if (isCurrent()) {
          setSessionView({ initData, sessions: data.sessions });
        }
      })
      .catch(() => { if (isCurrent()) setError(true); })
      .finally(() => { if (isCurrent()) setLoading(false); });
  }, [initData]);

  useEffect(() => { if (pending) confirmation.current?.focus(); }, [pending]);

  const reload = async () => {
    const ownGeneration = generation.current;
    const ownListGeneration = ++listGeneration.current;
    const isCurrent = () => generation.current === ownGeneration
      && listGeneration.current === ownListGeneration;
    setLoading(true);
    setError(false);
    try {
      const data = await telegramMiniAppSessions.list(initData);
      if (isCurrent()) {
        setSessionView({ initData, sessions: data.sessions });
      }
    } catch {
      if (isCurrent()) setError(true);
    } finally {
      if (isCurrent()) setLoading(false);
    }
  };

  const confirm = async () => {
    if (!pending || busy) return;
    const ownGeneration = generation.current;
    setBusy(true);
    setError(false);
    setDone(false);
    try {
      if (pending.type === 'logout') {
        await telegramMiniAppSessions.logout(initData);
        if (generation.current === ownGeneration) onLoggedOut();
        return;
      }
      if (pending.type === 'others') await telegramMiniAppSessions.revokeOthers(initData);
      else await telegramMiniAppSessions.revoke(pending.id, initData);
      if (generation.current !== ownGeneration) return;
      setPending(null);
      setDone(true);
      await reload();
    } catch {
      if (generation.current === ownGeneration) setError(true);
    } finally {
      if (generation.current === ownGeneration) setBusy(false);
    }
  };

  const dateLabel = (value: string) => new Date(value).toLocaleString(
    languageCode.startsWith('uz') ? 'uz-Latn' : 'ru',
    { dateStyle: 'short', timeStyle: 'short' },
  );

  return (
    <Card padding="small" shadow="none">
      <CardContent>
        <h2>{t('sessionsTitle')}</h2>
        <p>{t('sessionsDescription')}</p>
        {!initData ? <Alert severity="info">{t('sessionsUnavailable')}</Alert> : !isCurrentView ? (
          <p role="status">{t('sessionsLoading')}</p>
        ) : (
          <>
            {loading && <p role="status">{t('sessionsLoading')}</p>}
            {error && <Alert severity="error" role="alert">{t('sessionsFailed')}</Alert>}
            {done && <p role="status">{t('sessionsDone')}</p>}
            {!loading && !error && sessions.length === 0 && <p>{t('sessionsEmpty')}</p>}
            <ul className="telegram-mini-app-sessions-list">
              {sessions.map((session) => (
                <li key={session.id} className="telegram-mini-app-session">
                  <strong>{session.device_label}</strong>{' '}
                  {session.is_current && <Badge variant="primary">{t('sessionsCurrent')}</Badge>}
                  <p>{t('sessionsCreated', { date: dateLabel(session.created_at) })}</p>
                  <p>{t('sessionsActive', { date: dateLabel(session.last_active_at) })}</p>
                  {!session.is_current && (
                    <Button
                      type="button" disabled={busy || loading} variant="secondary"
                      aria-label={t('sessionsRevokeDevice', { device: session.device_label })}
                      onClick={() => { setPending({ type: 'device', id: session.id }); setDone(false); }}
                    >{t('sessionsRevoke')}</Button>
                  )}
                </li>
              ))}
            </ul>
            <div className="telegram-mini-app-session-actions">
              <Button type="button" variant="secondary" disabled={busy || loading} onClick={() => void reload()}>
                {t('sessionsRefresh')}
              </Button>
              <Button
                type="button" variant="secondary"
                disabled={busy || loading || !sessions.some((session) => !session.is_current)}
                onClick={() => { setPending({ type: 'others' }); setDone(false); }}
              >{t('sessionsRevokeOthers')}</Button>
              <Button type="button" variant="ghost" disabled={busy || loading}
                onClick={() => setPending({ type: 'logout' })}>
                {t('sessionsLogout')}
              </Button>
            </div>
            {pending && (
              <section
                ref={confirmation} tabIndex={-1} role="group"
                aria-labelledby="mini-app-session-confirmation"
              >
                <p id="mini-app-session-confirmation">
                  {t(pending.type === 'logout' ? 'sessionsConfirmLogout' : 'sessionsConfirmRevoke')}
                </p>
                <Button type="button" variant="primary" loading={busy} disabled={busy}
                  onClick={() => void confirm()}>{t('sessionsConfirm')}</Button>{' '}
                <Button type="button" variant="secondary" disabled={busy} onClick={() => setPending(null)}>
                  {t('sessionsCancel')}
                </Button>
              </section>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
