import { useEffect, useState } from 'react';
import type { ChangeEvent, CSSProperties } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle, XCircle } from 'lucide-react';

import { useTranslation } from '../i18n/useTranslation';
import { api } from '../api/client';
import { Button, Input } from '../components/ui/macos';

/**
 * Публичная страница завершения сброса пароля по ссылке из письма.
 *
 * Email-ссылка (backend password_reset_service) ведёт на
 * /reset-password?token=…; здесь токен валидируется
 * (GET /password-reset/validate-token) и публикуется форма
 * нового пароля (POST /password-reset/confirm {token, new_password}).
 *
 * #2772 finding: страница отсутствовала — письмо приходило, а ссылка
 * отдавала 404 маршрут-контракта.
 */

type Phase = 'checking' | 'form' | 'invalid' | 'done';

const ResetPasswordPage = () => {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [phase, setPhase] = useState<Phase>('checking');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    if (!token) {
      setPhase('invalid');
      return () => {
        alive = false;
      };
    }
    (async () => {
      try {
        const resp = (await api.get('/password-reset/validate-token', {
          params: { token },
        })) as unknown as { status: number; data: { valid?: boolean } };
        if (!alive) return;
        setPhase(
          resp.status < 300 && resp.data?.valid === true ? 'form' : 'invalid',
        );
      } catch {
        if (alive) setPhase('invalid');
      }
    })();
    return () => {
      alive = false;
    };
  }, [token]);

  const labelStyle = {
    display: 'block',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-medium)' as CSSProperties['fontWeight'],
    marginBottom: 'var(--mac-spacing-2)',
    color: 'var(--mac-text-primary)',
  } as const;

  const submit = async () => {
    if (newPassword.length < 8) {
      setError(t('final.fp_password_too_short'));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t('final.fp_password_mismatch'));
      return;
    }
    setLoading(true);
    setError('');
    try {
      const resp = (await api.post('/password-reset/confirm', {
        token,
        new_password: newPassword,
      })) as unknown as { status: number; data?: { success?: boolean } };
      if (resp.status < 300 && resp.data?.success) {
        setPhase('done');
      } else {
        setError(t('final.fp_reset_error'));
      }
    } catch (err) {
      // Сервер возвращает осмысленные причины (совпадение с текущим паролем,
      // состояние токена) — показываем их владельцу ссылки вместо общего
      // «Ошибка сброса пароля». Fallback — generic.
      const detail = (
        err as { response?: { data?: { detail?: string } } }
      )?.response?.data?.detail;
      setError(detail || t('final.fp_reset_error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="mx-auto w-full"
      style={{ maxWidth: 400, padding: '0 var(--mac-spacing-2)', fontFamily: 'inherit' }}
    >
      <div className="flex flex-col items-center text-center" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
        <h2 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)' as CSSProperties['fontWeight'] }}>
          {t('final.fp_new_password')}
        </h2>
      </div>

      {phase === 'checking' && (
        <p style={{ textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
          …
        </p>
      )}

      {phase === 'invalid' && (
        <div
          role="alert"
          aria-live="polite"
          className="flex flex-col items-center gap-2 text-center"
          style={{
            padding: 'var(--mac-spacing-4)',
            borderRadius: 'var(--mac-radius-md)',
            background: 'var(--mac-accent-red-bg)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
          }}
        >
          <XCircle style={{ width: 24, height: 24, color: 'var(--mac-accent-red)' }} />
          <span>{t('final.rp_invalid_link')}</span>
          <Link to="/login" style={{ color: 'var(--mac-accent-blue)', textDecoration: 'underline' }}>
            {t('final.fp_back_to_login')}
          </Link>
        </div>
      )}

      {phase === 'form' && (
        <div className="flex flex-col" style={{ gap: 'var(--mac-spacing-4)' }}>
          <div>
            <label htmlFor="rp-new-password" style={labelStyle}>
              {t('final.fp_new_password')}
            </label>
            <Input
              id="rp-new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                setNewPassword(e.target.value)
              }
            />
          </div>
          <div>
            <label htmlFor="rp-confirm-password" style={labelStyle}>
              {t('final.fp_confirm_password')}
            </label>
            <Input
              id="rp-confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
                setConfirmPassword(e.target.value)
              }
            />
          </div>
          {error && (
            <div role="alert" style={{ color: 'var(--mac-accent-red)', fontSize: 'var(--mac-font-size-sm)' }}>
              {error}
            </div>
          )}
          <Button onClick={submit} disabled={loading || newPassword.length < 8 || newPassword !== confirmPassword}>
            {t('final.fp_reset_password')}
          </Button>
        </div>
      )}

      {phase === 'done' && (
        <div className="flex flex-col items-center gap-2 text-center">
          <CheckCircle style={{ width: 48, height: 48, color: 'var(--mac-accent-green)' }} />
          <p style={{ color: 'var(--mac-text-primary)' }}>{t('final.fp_success')}</p>
          <Link to="/login" style={{ color: 'var(--mac-accent-blue)', textDecoration: 'underline' }}>
            {t('final.fp_back_to_login')}
          </Link>
        </div>
      )}
    </div>
  );
};

export default ResetPasswordPage;
