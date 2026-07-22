import { useEffect, useState } from 'react';
import type { CSSProperties } from "react";
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
  Button,
  Input,
} from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{value}</div>
    </div>
  );
}

MetricCard.propTypes = {
  accent: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
};

function SectionShell({ title, description, action, children }: { title?: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode; children?: React.ReactNode }) {
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

function EmptyState({ icon: Icon, title, description, action }: { icon?: React.ComponentType<{ size?: number; className?: string }>; title?: React.ReactNode; description?: React.ReactNode; action?: React.ReactNode }) {
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
        <div style={{ fontSize: 15, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>{title}</div>
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

function formatDate(dateString, t) {
  if (!dateString) return t('misc.tfm_date_not_specified');
  const parsed = new Date(dateString);
  if (Number.isNaN(parsed.getTime())) return t('misc.tfm_date_not_specified');
  return parsed.toLocaleString('ru-RU');
}

function resolveApiError(error, fallbackMessage) {
  return error?.response?.data?.detail || fallbackMessage;
}

function DeviceCard({ badgeLabel, details, lastUsed, name, pending, onCancel, onConfirm, onToggle }) {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
            <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)' }}>{name}</div>
            <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{details}</div>
            <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{t('misc.tfm_device_last_login')} {lastUsed}</div>
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            {badgeLabel && (
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    borderRadius: 999,
                    padding: '6px 10px',
                    ...toneChipStyles.info,
                  }}
                >
                {badgeLabel}
              </span>
            )}
            <Button variant="ghost" onClick={onToggle} startIcon={<Trash2 size={16} />}>
              {t('misc.tfm_device_revoke_access')}
            </Button>
          </div>
        </div>

        {pending && (
          <Alert severity="warning">
            <div style={{ display: 'grid', gap: 12 }}>
              <div>{t('misc.tfm_device_revoke_warning')}</div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Button variant="danger" onClick={onConfirm} startIcon={<Trash2 size={16} />}>
                  {t('misc.tfm_device_confirm_revoke')}
                </Button>
                <Button variant="ghost" onClick={onCancel}>
                  {t('misc.tfm_cancel')}
                </Button>
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      const response = (await api.get('/2fa/status')) as import('axios').AxiosResponse<Record<string, unknown>>;
      const data = response.data;
      setStatus(data);
      if (data?.enabled) {
        setSetupData(null);
        setVerificationCode('');
      }
    } catch (err) {
      setError(resolveApiError(err, t('misc.tfm_error_load_status')));
    }
  }

  async function loadDevices() {
    try {
      const response = (await api.get('/2fa/devices')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setDevices((response.data?.devices as unknown[]) || []);
    } catch (err) {
      logger.error('Error loading devices:', err);
    }
  }

  async function loadSecurityLogs() {
    try {
      const response = (await api.get('/2fa/security-logs')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setSecurityLogs((response.data?.logs as unknown[]) || []);
    } catch (err) {
      logger.error('Error loading security logs:', err);
    }
  }

  async function loadRecoveryMethods() {
    try {
      const response = (await api.get('/2fa/recovery-methods')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setRecoveryMethods((response.data?.methods as unknown[]) || []);
    } catch (err) {
      logger.error('Error loading recovery methods:', err);
    }
  }

  async function loadBackupCodes() {
    if (!status?.enabled) {
      setError(t('misc.tfm_backup_codes_setup_required'));
      return;
    }

    try {
      setLoading(true);
      setError('');
      const response = (await api.get('/2fa/backup-codes')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setBackupCodes((response.data?.backup_codes as unknown[]) || []);
      logger.info('[FIX:2FA] Loaded backup codes for enabled 2FA');
    } catch (err) {
      logger.error('Error loading backup codes:', err);
      setError(resolveApiError(err, t('misc.tfm_error_load_backup_codes')));
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
      const response = (await api.post('/2fa/setup', {
        recovery_email: status?.recovery_email || '',
        recovery_phone: status?.recovery_phone || '',
      })) as import('axios').AxiosResponse<Record<string, unknown>>;
      setSetupData(response.data);
      setBackupCodes((response.data?.backup_codes as unknown[]) || []);
      setVerificationCode('');
      setSuccess(t('misc.tfm_setup_qr_prompt'));
      logger.info('[FIX:2FA] 2FA setup created, waiting for verify-setup');
    } catch (err) {
      setError(resolveApiError(err, t('misc.tfm_error_setup')));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify2FASetup() {
    if (verificationCode.length !== 6) {
      setError(t('misc.tfm_verify_code_invalid_length'));
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      logger.info('[FIX:2FA] Verifying 2FA setup');
      const response = await api.post('/2fa/verify-setup', null, {
        params: { totp_code: verificationCode },
      }) as import('axios').AxiosResponse<Record<string, unknown>>;
      if (response.data?.success) {
        setSuccess(t('misc.tfm_enable_success'));
        await loadStatus();
      } else {
        setError(String(response.data?.detail || response.data?.message || t('misc.tfm_verify_code_invalid')));
      }
    } catch (err) {
      logger.error('Error verifying 2FA setup:', err);
      setError(resolveApiError(err, t('misc.tfm_error_verify')));
    } finally {
      setLoading(false);
    }
  }

  async function handleDisable2FA() {
    if (!disablePassword || !disableCode) {
      setError(t('misc.tfm_disable_require_credentials'));
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
      setSuccess(t('misc.tfm_disable_success'));
      await loadAll();
    } catch (err) {
      setError(resolveApiError(err, t('misc.tfm_error_disable')));
    } finally {
      setLoading(false);
    }
  }

  async function handleRegenerateBackupCodes() {
    if (!status?.enabled) {
      setError(t('misc.tfm_regenerate_require_enabled'));
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      logger.info('[FIX:2FA] Regenerating backup codes via supported endpoint');
      const response = (await api.post('/2fa/backup-codes/regenerate')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setBackupCodes((response.data?.backup_codes as unknown[]) || []);
      setConfirmRegenerate(false);
      setSuccess(t('misc.tfm_regenerate_success'));
    } catch (err) {
      setError(resolveApiError(err, t('misc.tfm_error_regenerate')));
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
      setSuccess(t('misc.tfm_revoke_device_success'));
      await loadDevices();
    } catch (err) {
      setError(resolveApiError(err, t('misc.tfm_error_revoke_device')));
    } finally {
      setLoading(false);
    }
  }

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      setSuccess(t('misc.tfm_copied_to_clipboard'));
    } catch (err) {
      logger.error('[FIX:2FA] Failed to copy to clipboard', err);
      setError(t('misc.tfm_error_copy_to_clipboard'));
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
        title={t('misc.tfm_section_protection_title')}
        description={t('misc.tfm_section_protection_desc')}
        action={(
          <Button
            variant="outline"
            onClick={loadAll}
            disabled={loading}
            startIcon={<RefreshCw size={16} />}
          >
            {t('misc.tfm_refresh_data')}
          </Button>
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
            label={t('misc.tfm_metric_2fa_status')}
            value={status?.enabled ? t('misc.tfm_metric_status_enabled') : t('misc.tfm_metric_status_disabled')}
          />
          <MetricCard
            accent={accentGradients.info}
            icon={Key}
            label={t('misc.tfm_metric_backup_codes')}
            value={status?.enabled ? t('misc.tfm_metric_backup_codes_available', { count: status?.backup_codes_count || 0 }) : t('misc.tfm_metric_backup_codes_unavailable')}
          />
          <MetricCard
            accent={accentGradients.success}
            icon={Smartphone}
            label={t('misc.tfm_metric_trusted_devices')}
            value={t('misc.tfm_metric_trusted_devices_count', { count: status?.trusted_devices_count ?? devices.length })}
          />
          <MetricCard
            accent={accentGradients.warning}
            icon={Clock3}
            label={t('misc.tfm_metric_last_used')}
            value={formatDate(status?.last_used, t)}
          />
        </div>

        {status?.enabled ? (
          <div style={{ display: 'grid', gap: 16 }}>
            <Alert severity="info">
              {t('misc.tfm_2fa_already_enabled_info')}
            </Alert>

            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Button
                variant="outline"
                onClick={loadBackupCodes}
                disabled={loading}
                startIcon={<Key size={16} />}
              >
                {t('misc.tfm_show_backup_codes')}
              </Button>
              <Button
                variant="ghost"
                onClick={() => setConfirmRegenerate(true)}
                disabled={loading}
                startIcon={<RefreshCw size={16} />}
              >
                {t('misc.tfm_create_new_codes_set')}
              </Button>
              <Button
                variant="danger"
                onClick={() => setShowDisableForm((prev) => !prev)}
                disabled={loading}
                startIcon={<Trash2 size={16} />}
              >
                {showDisableForm ? t('misc.tfm_hide_disable_form') : t('misc.tfm_disable_2fa')}
              </Button>
            </div>

            {confirmRegenerate && (
              <Alert severity="warning">
                <div style={{ display: 'grid', gap: 12 }}>
                  <div>
                    {t('misc.tfm_regenerate_confirm_warning')}
                  </div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <Button
                      variant="primary"
                      onClick={handleRegenerateBackupCodes}
                      disabled={loading}
                      startIcon={<RefreshCw size={16} />}
                    >
                      {t('misc.tfm_confirm_codes_update')}
                    </Button>
                    <Button variant="ghost" onClick={() => setConfirmRegenerate(false)}>
                      {t('misc.tfm_cancel')}
                    </Button>
                  </div>
                </div>
              </Alert>
            )}

            {showDisableForm && (
              <Card shadow="none" style={{ borderStyle: 'dashed' }}>
                <CardHeader style={{ paddingBottom: 12 }}>
                  <CardTitle>{t('misc.tfm_disable_2fa_title')}</CardTitle>
                </CardHeader>
                <CardContent style={{ display: 'grid', gap: 14 }}>
                  <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                    {t('misc.tfm_disable_form_desc')}
                  </div>
                  <Input
                    type="password"
                    value={disablePassword}
                    onChange={(event) => setDisablePassword(event.target.value)}
                    placeholder={t('misc.tfm_disable_form_password_placeholder')}
                  />
                  <Input
                    type="text"
                    value={disableCode}
                    onChange={(event) => setDisableCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                    placeholder={t('misc.tfm_disable_form_code_placeholder')}
                  />
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <Button
                      variant="danger"
                      onClick={handleDisable2FA}
                      disabled={loading}
                      startIcon={<Trash2 size={16} />}
                    >
                      {t('misc.tfm_confirm_disable')}
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => {
                        setShowDisableForm(false);
                        setDisablePassword('');
                        setDisableCode('');
                      }}
                    >
                      {t('misc.tfm_cancel')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <div style={{ display: 'grid', gap: 16 }}>
            <EmptyState
              icon={Shield}
              title={t('misc.tfm_2fa_not_activated_title')}
              description={t('misc.tfm_2fa_not_activated_desc')}
              action={(
                <Button
                  variant="primary"
                  onClick={handleEnable2FA}
                  disabled={loading}
                  startIcon={<ShieldCheck size={16} />}
                >
                  {t('misc.tfm_enable_2fa')}
                </Button>
              )}
            />

            {setupData && (
              <Card shadow="none" style={{ borderStyle: 'dashed' }}>
                <CardHeader style={{ paddingBottom: 12 }}>
                  <CardTitle>{t('misc.tfm_setup_verification_title')}</CardTitle>
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
                        <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>{t('misc.tfm_qr_unavailable')}</div>
                      )}
                    </div>

                    <div style={{ display: 'grid', gap: 14, alignContent: 'start' }}>
                      <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                        {t('misc.tfm_scan_qr_hint')}
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
                        <Button
                          variant="ghost"
                          onClick={() => copyToClipboard(setupData.secret_key)}
                          startIcon={<Copy size={16} />}
                        >
                          {t('misc.tfm_copy')}
                        </Button>
                      </div>
                      <Input
                        type="text"
                        value={verificationCode}
                        onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                        placeholder={t('misc.tfm_enter_6digit_code')}
                      />
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                        <Button
                          variant="primary"
                          onClick={handleVerify2FASetup}
                          disabled={loading || verificationCode.length !== 6}
                          startIcon={<CheckCircle size={16} />}
                        >
                          {t('misc.tfm_confirm_and_enable')}
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setSetupData(null);
                            setVerificationCode('');
                          }}
                        >
                          {t('misc.tfm_cancel_setup')}
                        </Button>
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
        title={t('misc.tfm_section_recovery_title')}
        description={t('misc.tfm_section_recovery_desc')}
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
                    <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)' }}>{method.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>{method.value}</div>
                  </div>
                </div>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    borderRadius: 999,
                    padding: '6px 10px',
                    ...(method.verified ? toneChipStyles.success : toneChipStyles.warning),
                  }}
                >
                  {method.verified ? t('misc.tfm_recovery_verified') : t('misc.tfm_recovery_not_verified')}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Mail}
            title={t('misc.tfm_recovery_empty_title')}
            description={t('misc.tfm_recovery_empty_desc')}
          />
        )}
      </SectionShell>

      <SectionShell
        title={t('misc.tfm_section_devices_title')}
        description={t('misc.tfm_section_devices_desc')}
      >
        {devices.length > 0 ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {devices.map((device) => (
              <DeviceCard
                key={device.id}
                badgeLabel={device.trusted ? t('misc.tfm_device_badge_trusted') : device.active ? t('misc.tfm_device_badge_active') : ''}
                details={[
                  device.device_type ? t('misc.tfm_device_type_label', { type: device.device_type }) : null,
                  device.ip_address,
                  device.user_agent,
                ].filter(Boolean).join(' • ') || t('misc.tfm_device_no_extra_info')}
                lastUsed={formatDate(device.last_used, t)}
                name={device.device_name || t('misc.tfm_device_unknown')}
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
            title={t('misc.tfm_devices_empty_title')}
            description={t('misc.tfm_devices_empty_desc')}
          />
        )}
      </SectionShell>

      <SectionShell
        title={t('misc.tfm_section_backup_codes_title')}
        description={t('misc.tfm_section_backup_codes_desc')}
        action={status?.enabled ? (
          <Button
            variant="outline"
            onClick={loadBackupCodes}
            disabled={loading}
            startIcon={<Download size={16} />}
          >
            {t('misc.tfm_load_current_codes')}
          </Button>
        ) : null}
      >
        {!status?.enabled ? (
          <EmptyState
            icon={Key}
            title={t('misc.tfm_backup_codes_unavailable_title')}
            description={t('misc.tfm_backup_codes_unavailable_desc')}
          />
        ) : backupCodes.length > 0 ? (
          <div style={{ display: 'grid', gap: 16 }}>
            <Alert severity="warning">
              {t('misc.tfm_backup_codes_save_warning')}
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
                  <Button variant="ghost" onClick={() => copyToClipboard(code)} startIcon={<Copy size={16} />}>
                    {t('misc.tfm_copy_button_short')}
                  </Button>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Button variant="outline" onClick={() => copyToClipboard(backupCodes.join('\n'))} startIcon={<Copy size={16} />}>
                {t('misc.tfm_copy_all')}
              </Button>
              <Button variant="outline" onClick={downloadBackupCodes} startIcon={<Download size={16} />}>
                {t('misc.tfm_download_txt')}
              </Button>
              <Button variant="ghost" onClick={() => setConfirmRegenerate(true)} disabled={loading} startIcon={<RefreshCw size={16} />}>
                {t('misc.tfm_create_new_set')}
              </Button>
            </div>
          </div>
        ) : (
          <EmptyState
            icon={Key}
            title={t('misc.tfm_backup_codes_not_loaded_title')}
            description={t('misc.tfm_backup_codes_not_loaded_desc')}
            action={(
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                <Button variant="outline" onClick={loadBackupCodes} disabled={loading} startIcon={<Download size={16} />}>
                  {t('misc.tfm_load_current_codes')}
                </Button>
                <Button variant="ghost" onClick={() => setConfirmRegenerate(true)} disabled={loading} startIcon={<RefreshCw size={16} />}>
                  {t('misc.tfm_create_new_set')}
                </Button>
              </div>
            )}
          />
        )}
      </SectionShell>

      <SectionShell
        title={t('misc.tfm_section_logs_title')}
        description={t('misc.tfm_section_logs_desc')}
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
                  <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)' }}>{log.action}</div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>{log.description}</div>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {formatDate(log.timestamp, t)} • {log.ip_address || 'unknown'} • {log.user_agent || 'unknown'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={Clock3}
            title={t('misc.tfm_logs_empty_title')}
            description={t('misc.tfm_logs_empty_desc')}
          />
        )}
      </SectionShell>
    </div>
  );
}
