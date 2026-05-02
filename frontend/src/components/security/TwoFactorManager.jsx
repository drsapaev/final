import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  AlertTriangle,
  CheckCircle,
  Clock3,
  Copy,
  Download,
  Key,
  Mail,
  RefreshCw,
  Shield,
  ShieldCheck,
  Smartphone,
  Trash2,
} from 'lucide-react';

import logger from '../../utils/logger';
import { api } from '../../api/client';
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  MacOSButton,
  MacOSInput,
} from '../ui/macos';

const accentGradients = {
  info: 'linear-gradient(135deg, var(--mac-accent), color-mix(in srgb, var(--mac-accent), white 18%))',
  success: 'linear-gradient(135deg, var(--mac-success), color-mix(in srgb, var(--mac-success), white 18%))',
  warning: 'linear-gradient(135deg, var(--mac-warning), color-mix(in srgb, var(--mac-warning), white 18%))',
  purple: 'linear-gradient(135deg, var(--mac-accent-purple), color-mix(in srgb, var(--mac-accent), white 12%))',
};

const toneChipStyles = {
  success: {
    background: 'var(--mac-success-bg)',
    color: 'var(--mac-success)',
    border: '1px solid var(--mac-success-border)',
  },
  warning: {
    background: 'var(--mac-warning-bg)',
    color: 'var(--mac-warning)',
    border: '1px solid var(--mac-warning-border)',
  },
  error: {
    background: 'var(--mac-error-bg)',
    color: 'var(--mac-error)',
    border: '1px solid var(--mac-error-border)',
  },
  info: {
    background: 'var(--mac-accent-bg)',
    color: 'var(--mac-accent)',
    border: '1px solid var(--mac-accent-border)',
  },
};

function MetricCard({ accent, icon: Icon, label, value }) {
  return (
    <div
      className="theme-soft-surface"
      style={{
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 38,
          height: 38,
          borderRadius: 12,
          background: accent,
          color: 'white',
          marginBottom: 12,
        }}
      >
        <Icon size={18} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--mac-text-primary)' }}>{value}</div>
    </div>
  );
}

MetricCard.propTypes = {
  accent: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
};

function SectionShell({ title, description, action, children }) {
  return (
    <Card shadow="default">
      <CardHeader style={{ paddingBottom: 12 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <CardTitle>{title}</CardTitle>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
              {description}
            </div>
          </div>
          {action}
        </div>
      </CardHeader>
      <CardContent style={{ display: 'grid', gap: 16 }}>{children}</CardContent>
    </Card>
  );
}

SectionShell.propTypes = {
  action: PropTypes.node,
  children: PropTypes.node.isRequired,
  description: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
};

function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div
      className="theme-empty-state"
      style={{
        display: 'grid',
        justifyItems: 'center',
        textAlign: 'center',
        gap: 12,
        padding: '28px 20px',
      }}
    >
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 18,
          background: 'color-mix(in srgb, var(--mac-text-secondary), transparent 86%)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--mac-text-secondary)',
        }}
      >
        <Icon size={22} />
      </div>
      <div>
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--mac-text-primary)' }}>{title}</div>
        <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>{description}</div>
      </div>
      {action}
    </div>
  );
}

EmptyState.propTypes = {
  action: PropTypes.node,
  description: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  title: PropTypes.string.isRequired,
};

function formatDate(dateString) {
  if (!dateString) return 'Не указано';
  const parsed = new Date(dateString);
  if (Number.isNaN(parsed.getTime())) return 'Не указано';
  return parsed.toLocaleString('ru-RU');
}

function resolveApiError(error, fallbackMessage) {
  return error?.response?.data?.detail || fallbackMessage;
}

function DeviceCard({ badgeLabel, details, lastUsed, name, pending, onCancel, onConfirm, onToggle }) {
  return (
    <Card shadow="none" style={{ borderStyle: 'solid' }}>
      <CardContent style={{ display: 'grid', gap: 12 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'grid', gap: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{name}</div>
            <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{details}</div>
            <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>Последний вход: {lastUsed}</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {badgeLabel && (
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: '6px 10px',
                    ...toneChipStyles.info,
                  }}
                >
                {badgeLabel}
              </span>
            )}
            <MacOSButton variant="ghost" onClick={onToggle} startIcon={<Trash2 size={16} />}>
              Отозвать доступ
            </MacOSButton>
          </div>
        </div>

        {pending && (
          <Alert severity="warning">
            <div style={{ display: 'grid', gap: 12 }}>
              <div>После отзыва доступа при следующем входе снова потребуется подтверждение 2FA.</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <MacOSButton variant="danger" onClick={onConfirm} startIcon={<Trash2 size={16} />}>
                  Подтвердить отзыв
                </MacOSButton>
                <MacOSButton variant="ghost" onClick={onCancel}>
                  Отмена
                </MacOSButton>
              </div>
            </div>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

DeviceCard.propTypes = {
  badgeLabel: PropTypes.string,
  details: PropTypes.string.isRequired,
  lastUsed: PropTypes.string.isRequired,
  name: PropTypes.string.isRequired,
  onCancel: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  onToggle: PropTypes.func.isRequired,
  pending: PropTypes.bool,
};

export default function TwoFactorManager() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [status, setStatus] = useState(null);
  const [setupData, setSetupData] = useState(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [showDisableForm, setShowDisableForm] = useState(false);
  const [confirmRegenerate, setConfirmRegenerate] = useState(false);
  const [backupCodes, setBackupCodes] = useState([]);
  const [devices, setDevices] = useState([]);
  const [deviceToRevoke, setDeviceToRevoke] = useState(null);
  const [securityLogs, setSecurityLogs] = useState([]);
  const [recoveryMethods, setRecoveryMethods] = useState([]);

  useEffect(() => {
    void (async () => {
      setError('');
      try {
        await Promise.all([loadStatus(), loadDevices(), loadSecurityLogs(), loadRecoveryMethods()]);
      } catch (err) {
        logger.error('[FIX:2FA] Failed to refresh full security state', err);
      }
    })();
  }, []);

  async function loadAll() {
    setError('');
    try {
      await Promise.all([loadStatus(), loadDevices(), loadSecurityLogs(), loadRecoveryMethods()]);
    } catch (err) {
      logger.error('[FIX:2FA] Failed to refresh full security state', err);
    }
  }

  async function loadStatus() {
    try {
      const response = await api.get('/2fa/status');
      const data = response.data;
      setStatus(data);
      if (data?.enabled) {
        setSetupData(null);
        setVerificationCode('');
      }
    } catch (err) {
      setError(resolveApiError(err, 'Ошибка загрузки статуса 2FA'));
    }
  }

  async function loadDevices() {
    try {
      const response = await api.get('/2fa/devices');
      setDevices(response.data?.devices || []);
    } catch (err) {
      logger.error('Error loading devices:', err);
    }
  }

  async function loadSecurityLogs() {
    try {
      const response = await api.get('/2fa/security-logs');
      setSecurityLogs(response.data?.logs || []);
    } catch (err) {
      logger.error('Error loading security logs:', err);
    }
  }

  async function loadRecoveryMethods() {
    try {
      const response = await api.get('/2fa/recovery-methods');
      setRecoveryMethods(response.data?.methods || []);
    } catch (err) {
      logger.error('Error loading recovery methods:', err);
    }
  }

  async function loadBackupCodes() {
    if (!status?.enabled) {
      setError('Сначала завершите настройку 2FA и подтвердите код из приложения.');
      return;
    }

    try {
      setLoading(true);
      setError('');
      const response = await api.get('/2fa/backup-codes');
      setBackupCodes(response.data?.backup_codes || []);
      logger.info('[FIX:2FA] Loaded backup codes for enabled 2FA');
    } catch (err) {
      logger.error('Error loading backup codes:', err);
      setError(resolveApiError(err, 'Ошибка загрузки резервных кодов'));
    } finally {
      setLoading(false);
    }
  }

  async function handleEnable2FA() {
    setLoading(true);
    setError('');
    setSuccess('');
    setConfirmRegenerate(false);

    try {
      const response = await api.post('/2fa/setup', {
        recovery_email: status?.recovery_email || '',
        recovery_phone: status?.recovery_phone || '',
      });
      setSetupData(response.data);
      setBackupCodes(response.data?.backup_codes || []);
      setVerificationCode('');
      setSuccess('Сканируйте QR-код и подтвердите 6-значный код из приложения, чтобы включить 2FA.');
      logger.info('[FIX:2FA] 2FA setup created, waiting for verify-setup');
    } catch (err) {
      setError(resolveApiError(err, 'Ошибка настройки 2FA'));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify2FASetup() {
    if (verificationCode.length !== 6) {
      setError('Введите 6-значный код из приложения-аутентификатора');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      logger.info('[FIX:2FA] Verifying 2FA setup');
      const response = await api.post('/2fa/verify-setup', null, {
        params: { totp_code: verificationCode },
      });
      if (response.data?.success) {
        setSuccess('2FA успешно включена');
        await loadStatus();
      } else {
        setError(response.data?.detail || response.data?.message || 'Неверный код подтверждения');
      }
    } catch (err) {
      logger.error('Error verifying 2FA setup:', err);
      setError(resolveApiError(err, 'Ошибка подтверждения 2FA'));
    } finally {
      setLoading(false);
    }
  }

  async function handleDisable2FA() {
    if (!disablePassword || !disableCode) {
      setError('Введите пароль и код из приложения, чтобы отключить 2FA.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.post('/2fa/disable', {
        password: disablePassword,
        totp_code: disableCode,
      });
      setDisablePassword('');
      setDisableCode('');
      setShowDisableForm(false);
      setBackupCodes([]);
      setSuccess('2FA успешно отключена');
      await loadAll();
    } catch (err) {
      setError(resolveApiError(err, 'Ошибка отключения 2FA'));
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerateBackupCodes() {
    if (!status?.enabled) {
      setError('Нельзя обновить резервные коды, пока 2FA не включена и не подтверждена.');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      logger.info('[FIX:2FA] Regenerating backup codes via supported endpoint');
      const response = await api.post('/2fa/backup-codes/regenerate');
      setBackupCodes(response.data?.backup_codes || []);
      setConfirmRegenerate(false);
      setSuccess('Резервные коды обновлены. Старый комплект больше недействителен.');
    } catch (err) {
      setError(resolveApiError(err, 'Ошибка генерации резервных кодов'));
    } finally {
      setLoading(false);
    }
  }

  async function handleRevokeDevice(deviceId) {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      await api.delete(`/2fa/devices/${deviceId}`);
      setDeviceToRevoke(null);
      setSuccess('Доступ устройства отозван');
      await loadDevices();
    } catch (err) {
      setError(resolveApiError(err, 'Ошибка отзыва доступа'));
    } finally {
      setLoading(false);
    }
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      setSuccess('Скопировано в буфер обмена');
    } catch (err) {
      logger.error('[FIX:2FA] Failed to copy to clipboard', err);
      setError('Не удалось скопировать в буфер обмена');
    }
  }

  function downloadBackupCodes() {
    const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'backup-codes.txt';
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div style={{ display: 'grid', gap: 20 }}>
      {error && <Alert severity="error">{error}</Alert>}
      {success && <Alert severity="success">{success}</Alert>}

      <SectionShell
        title="Защита входа"
        description="Управляйте двухфакторной аутентификацией без вложенных экранов и всплывающих системных prompt."
        action={(
          <MacOSButton
            variant="outline"
            onClick={loadAll}
            disabled={loading}
            startIcon={<RefreshCw size={16} />}
          >
            Обновить данные
          </MacOSButton>
        )}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 12,
          }}
        >
          <MetricCard
            accent={accentGradients.purple}
            icon={ShieldCheck}
            label="Статус 2FA"
            value={status?.enabled ? 'Включена' : 'Отключена'}
          />
          <MetricCard
            accent={accentGradients.info}
            icon={Key}
            label="Резервные коды"
            value={status?.enabled ? `${status?.backup_codes_count || 0} доступно` : 'Недоступны'}
          />
          <MetricCard
            accent={accentGradients.success}
            icon={Smartphone}
            label="Доверенные устройства"
            value={`${status?.trusted_devices_count ?? devices.length} шт.`}
          />
          <MetricCard
            accent={accentGradients.warning}
            icon={Clock3}
            label="Последнее использование"
            value={formatDate(status?.last_used)}
          />
        </div>

        {status?.enabled ? (
          <div style={{ display: 'grid', gap: 16 }}>
            <Alert severity="info">
              2FA уже включена. Здесь можно загрузить резервные коды, проверить связанные устройства и безопасно отключить защиту.
            </Alert>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <MacOSButton
                variant="outline"
                onClick={loadBackupCodes}
                disabled={loading}
                startIcon={<Key size={16} />}
              >
                Показать резервные коды
              </MacOSButton>
              <MacOSButton
                variant="ghost"
                onClick={() => setConfirmRegenerate(true)}
                disabled={loading}
                startIcon={<RefreshCw size={16} />}
              >
                Создать новый комплект кодов
              </MacOSButton>
              <MacOSButton
                variant="danger"
                onClick={() => setShowDisableForm((prev) => !prev)}
                disabled={loading}
                startIcon={<Trash2 size={16} />}
              >
                {showDisableForm ? 'Скрыть форму отключения' : 'Отключить 2FA'}
              </MacOSButton>
            </div>

            {confirmRegenerate && (
              <Alert severity="warning">
                <div style={{ display: 'grid', gap: 12 }}>
                  <div>
                    Новый комплект резервных кодов немедленно сделает старый недействительным. Сначала сохраните действующие коды, если они ещё нужны.
                  </div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <MacOSButton
                      variant="primary"
                      onClick={handleRegenerateBackupCodes}
                      disabled={loading}
                      startIcon={<RefreshCw size={16} />}
                    >
                      Подтвердить обновление кодов
                    </MacOSButton>
                    <MacOSButton variant="ghost" onClick={() => setConfirmRegenerate(false)}>
                      Отмена
                    </MacOSButton>
                  </div>
                </div>
              </Alert>
            )}

            {showDisableForm && (
              <Card shadow="none" style={{ borderStyle: 'dashed' }}>
                <CardHeader style={{ paddingBottom: 12 }}>
                  <CardTitle>Отключение 2FA</CardTitle>
                </CardHeader>
                <CardContent style={{ display: 'grid', gap: 14 }}>
                  <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                    Для отключения нужен текущий пароль и 6-значный код из приложения-аутентификатора.
                  </div>
                  <MacOSInput
                    type="password"
                    value={disablePassword}
                    onChange={(event) => setDisablePassword(event.target.value)}
                    placeholder="Текущий пароль"
                  />
                  <MacOSInput
                    type="text"
                    value={disableCode}
                    onChange={(event) => setDisableCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder="Код из приложения"
                  />
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <MacOSButton
                      variant="danger"
                      onClick={handleDisable2FA}
                      disabled={loading}
                      startIcon={<Trash2 size={16} />}
                    >
                      Подтвердить отключение
                    </MacOSButton>
                    <MacOSButton
                      variant="ghost"
                      onClick={() => {
                        setShowDisableForm(false);
                        setDisablePassword('');
                        setDisableCode('');
                      }}
                    >
                      Отмена
                    </MacOSButton>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 16 }}>
            <EmptyState
              icon={Shield}
              title="2FA ещё не активирована"
              description="Сначала создайте QR-код и секрет, затем подтвердите код из приложения-аутентификатора."
              action={(
                <MacOSButton
                  variant="primary"
                  onClick={handleEnable2FA}
                  disabled={loading}
                  startIcon={<ShieldCheck size={16} />}
                >
                  Включить 2FA
                </MacOSButton>
              )}
            />

            {setupData && (
              <Card shadow="none" style={{ borderStyle: 'dashed' }}>
                <CardHeader style={{ paddingBottom: 12 }}>
                  <CardTitle>Подтверждение настройки 2FA</CardTitle>
                </CardHeader>
                <CardContent style={{ display: 'grid', gap: 18 }}>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'minmax(220px, 280px) minmax(0, 1fr)',
                      gap: 18,
                    }}
                  >
                    <div
                      className="theme-soft-surface"
                      style={{
                        padding: 16,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minHeight: 220,
                      }}
                    >
                      {setupData.qr_code_url ? (
                        <img
                          src={setupData.qr_code_url}
                          alt="QR code for 2FA setup"
                          style={{ maxWidth: '100%', borderRadius: 12 }}
                        />
                      ) : (
                        <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>QR код недоступен</div>
                      )}
                    </div>

                    <div style={{ display: 'grid', gap: 14, alignContent: 'start' }}>
                      <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                        Отсканируйте QR-код любым TOTP-приложением или введите секрет вручную.
                      </div>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 10,
                          border: '1px solid var(--mac-border)',
                          borderRadius: 14,
                          padding: '12px 14px',
                          background: 'var(--mac-bg-secondary)',
                        }}
                      >
                        <code style={{ fontSize: 12, wordBreak: 'break-all' }}>{setupData.secret_key}</code>
                        <MacOSButton
                          variant="ghost"
                          onClick={() => copyToClipboard(setupData.secret_key)}
                          startIcon={<Copy size={16} />}
                        >
                          Копировать
                        </MacOSButton>
                      </div>
                      <MacOSInput
                        type="text"
                        value={verificationCode}
                        onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                        placeholder="Введите 6-значный код"
                      />
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <MacOSButton
                          variant="primary"
                          onClick={handleVerify2FASetup}
                          disabled={loading || verificationCode.length !== 6}
                          startIcon={<CheckCircle size={16} />}
                        >
                          Подтвердить и включить 2FA
                        </MacOSButton>
                        <MacOSButton
                          variant="ghost"
                          onClick={() => {
                            setSetupData(null);
                            setVerificationCode('');
                          }}
                        >
                          Отменить настройку
                        </MacOSButton>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </SectionShell>

      <SectionShell
        title="Методы восстановления"
        description="Каналы, которые помогут вернуть доступ к аккаунту, если устройство с TOTP будет потеряно."
      >
        {recoveryMethods.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {recoveryMethods.map((method) => (
              <div
                key={`${method.type}-${method.value}`}
                className="theme-soft-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr auto',
                  gap: 12,
                  alignItems: 'center',
                  padding: '14px 16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 12,
                      background: method.type === 'email' ? 'var(--mac-accent-bg)' : 'var(--mac-success-bg)',
                      color: method.type === 'email' ? 'var(--mac-accent)' : 'var(--mac-success)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {method.type === 'email' ? <Mail size={16} /> : <Smartphone size={16} />}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>{method.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{method.value}</div>
                  </div>
                </div>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    borderRadius: 999,
                    padding: '6px 10px',
                    ...(method.verified ? toneChipStyles.success : toneChipStyles.warning),
                  }}
                >
                  {method.verified ? 'Подтверждён' : 'Не подтверждён'}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Mail}
            title="Методы восстановления не настроены"
            description="Сейчас доступ возможен только через приложение-аутентификатор и резервные коды."
          />
        )}
      </SectionShell>

      <SectionShell
        title="Доверенные устройства"
        description="Устройства, на которых вход уже подтверждался через 2FA."
      >
        {devices.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {devices.map((device) => (
              <DeviceCard
                key={device.id}
                badgeLabel={device.trusted ? 'Доверено' : device.active ? 'Активно' : ''}
                details={[
                  device.device_type ? `Тип: ${device.device_type}` : null,
                  device.ip_address,
                  device.user_agent,
                ].filter(Boolean).join(' • ') || 'Нет дополнительной информации'}
                lastUsed={formatDate(device.last_used)}
                name={device.device_name || 'Неизвестное устройство'}
                pending={deviceToRevoke === device.id}
                onToggle={() => setDeviceToRevoke(deviceToRevoke === device.id ? null : device.id)}
                onCancel={() => setDeviceToRevoke(null)}
                onConfirm={() => handleRevokeDevice(device.id)}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Smartphone}
            title="Нет доверенных устройств"
            description="Список заполнится после входов, подтверждённых через 2FA."
          />
        )}
      </SectionShell>

      <SectionShell
        title="Резервные коды"
        description="Аварийный способ входа, если доступ к приложению-аутентификатору временно потерян."
        action={status?.enabled ? (
          <MacOSButton
            variant="outline"
            onClick={loadBackupCodes}
            disabled={loading}
            startIcon={<Download size={16} />}
          >
            Загрузить текущие коды
          </MacOSButton>
        ) : null}
      >
        {!status?.enabled ? (
          <EmptyState
            icon={Key}
            title="Резервные коды пока недоступны"
            description="Они появятся только после завершения настройки и подтверждения 2FA."
          />
        ) : backupCodes.length > 0 ? (
          <div style={{ display: 'grid', gap: 16 }}>
            <Alert severity="warning">
              Сохраните эти коды в безопасном месте. Каждый код можно использовать только один раз.
            </Alert>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                gap: 12,
              }}
            >
              {backupCodes.map((code) => (
                <div
                  key={code}
                  className="theme-soft-surface"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 10,
                    padding: '12px 14px',
                  }}
                >
                  <code style={{ fontSize: 13 }}>{code}</code>
                  <MacOSButton variant="ghost" onClick={() => copyToClipboard(code)} startIcon={<Copy size={16} />}>
                    Копия
                  </MacOSButton>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <MacOSButton variant="outline" onClick={() => copyToClipboard(backupCodes.join('\n'))} startIcon={<Copy size={16} />}>
                Копировать все
              </MacOSButton>
              <MacOSButton variant="outline" onClick={downloadBackupCodes} startIcon={<Download size={16} />}>
                Скачать TXT
              </MacOSButton>
              <MacOSButton variant="ghost" onClick={() => setConfirmRegenerate(true)} disabled={loading} startIcon={<RefreshCw size={16} />}>
                Создать новый комплект
              </MacOSButton>
            </div>
          </div>
        ) : (
          <EmptyState
            icon={Key}
            title="Коды ещё не загружены"
            description="Можно загрузить текущий набор или создать новый комплект кодов."
            action={(
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                <MacOSButton variant="outline" onClick={loadBackupCodes} disabled={loading} startIcon={<Download size={16} />}>
                  Загрузить текущие коды
                </MacOSButton>
                <MacOSButton variant="ghost" onClick={() => setConfirmRegenerate(true)} disabled={loading} startIcon={<RefreshCw size={16} />}>
                  Создать новый комплект
                </MacOSButton>
              </div>
            )}
          />
        )}
      </SectionShell>

      <SectionShell
        title="Журнал безопасности"
        description="Последние события, связанные с 2FA, доверенными сессиями и восстановлением доступа."
      >
        {securityLogs.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {securityLogs.map((log, index) => (
              <div
                key={`${log.timestamp}-${index}`}
                className="theme-soft-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'auto 1fr',
                  gap: 14,
                  padding: '14px 16px',
                }}
              >
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 12,
                    background: log.type === 'success' ? 'var(--mac-success-bg)' : log.type === 'warning' ? 'var(--mac-warning-bg)' : 'var(--mac-error-bg)',
                    color: log.type === 'success' ? 'var(--mac-success)' : log.type === 'warning' ? 'var(--mac-warning)' : 'var(--mac-error)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  {log.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600 }}>{log.action}</div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>{log.description}</div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {formatDate(log.timestamp)} • {log.ip_address || 'unknown'} • {log.user_agent || 'unknown'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Clock3}
            title="Пока нет событий безопасности"
            description="История заполнится после действий с 2FA, доверенными устройствами и восстановлением доступа."
          />
        )}
      </SectionShell>
    </div>
  );
}
