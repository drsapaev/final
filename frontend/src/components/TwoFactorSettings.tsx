import { useTranslation } from '../i18n/useTranslation';
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from './common/ConfirmDialog';
import {
  Shield,



  Trash2,
  Download,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Eye,

  Copy } from
'lucide-react';

const TwoFactorSettings = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 2 native confirm() calls).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [status, setStatus] = useState(null);
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [backupCodes, setBackupCodes] = useState([]);
  const [devices, setDevices] = useState([]);
  const [copiedCode, setCopiedCode] = useState('');

  useEffect(() => {
    loadStatus();
    loadDevices();
  }, []);

  const loadStatus = async () => {
    try {
      const response = (await api.get('/2fa/status')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setStatus(response);
    } catch {
      setError(t('misc.tfs_load_status_error'));
    }
  };

  const loadDevices = async () => {
    try {
      const response = (await api.get('/2fa/devices')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setDevices((response.data?.devices as unknown[]) || []);
    } catch (err) {
      logger.error('Error loading devices:', err);
    }
  };

  const loadBackupCodes = async () => {
    try {
      const response = (await api.get('/2fa/backup-codes')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setBackupCodes((response.data?.backup_codes as unknown[]) || []);
      setShowBackupCodes(true);
    } catch {
      setError(t('misc.tfs_load_backup_codes_error'));
    }
  };

  const handleDisable2FA = async () => {
    const password = prompt(t('misc.tfs_disable_password_prompt'));
    if (!password) return;

    const totpCode = prompt(t('misc.tfs_disable_totp_prompt'));
    if (!totpCode) return;

    setLoading(true);
    setError('');

    try {
      const response = (await api.post('/2fa/disable', {
        password,
        totp_code: totpCode
      })) as import('axios').AxiosResponse<Record<string, unknown>>;

      if (response.data?.success) {
        setSuccess(t('misc.tfs_disable_success'));
        loadStatus();
      } else {
        setError(t('misc.tfs_disable_invalid'));
      }
    } catch (err) {
      setError(err.response?.data?.detail || t('misc.tfs_disable_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('misc.tfs_regenerate_title'),
      message: t('misc.tfs_regenerate_message'),
      description: t('misc.tfs_regenerate_description'),
      confirmLabel: t('misc.tfs_regenerate_confirm'),
      cancelLabel: t('misc.cancel'),
      intent: 'warning',
    });
    if (!ok) {
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = (await api.post('/2fa/backup-codes/regenerate')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setBackupCodes((response.data?.backup_codes as unknown[]) || []);
      setShowBackupCodes(true);
      setSuccess(t('misc.tfs_regenerate_success'));
    } catch (err) {
      setError(err.response?.data?.detail || t('misc.tfs_regenerate_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleUntrustDevice = async (deviceId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('misc.tfs_untrust_title'),
      message: t('misc.tfs_untrust_message'),
      description: t('misc.tfs_untrust_description'),
      confirmLabel: t('misc.tfs_untrust_confirm'),
      cancelLabel: t('misc.cancel'),
      intent: 'warning',
    });
    if (!ok) {
      return;
    }

    try {
      await api.delete(`/2fa/devices/${deviceId}`);
      setSuccess(t('misc.tfs_untrust_success'));
      loadDevices();
    } catch (err) {
      setError(err.response?.data?.detail || t('misc.tfs_untrust_error'));
    }
  };

  const copyToClipboard = (text, code) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(''), 2000);
  };

  const downloadBackupCodes = () => {
    const codesText = backupCodes.join('\n');
    const blob = new Blob([codesText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!status) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '200px'
      }}>
        <RefreshCw size={24} className="animate-spin" />
      </div>);

  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{
          margin: '0 0 8px 0',
          color: 'var(--text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-3)'
        }}>
          <Shield size={32} />
          {t('misc.tfs_page_title')}
        </h1>
        <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
          {t('misc.tfs_page_subtitle')}
        </p>
      </div>

      {error &&
      <div style={{
        background: 'var(--mac-error-bg)',
        border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-4)',
        marginBottom: 'var(--mac-spacing-6)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-error)'
      }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      }

      {success &&
      <div style={{
        background: 'var(--mac-success-bg)',
        border: '1px solid #6EE7B7',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-4)',
        marginBottom: 'var(--mac-spacing-6)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        color: 'var(--mac-success)'
      }}>
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      }

      {/* Статус 2FA */}
      <div style={{
        background: 'var(--bg-secondary)',
        padding: 'var(--mac-spacing-6)',
        borderRadius: 'var(--mac-radius-lg)',
        marginBottom: 'var(--mac-spacing-6)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--mac-spacing-4)'
        }}>
          <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
            {t('misc.tfs_status_title')}
          </h3>
          <div style={{
            padding: '4px 12px',
            background: status.enabled ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
            color: status.enabled ? 'var(--mac-success)' : 'var(--mac-error)',
            borderRadius: 'var(--mac-radius-xl)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}>
            {status.enabled ? t('misc.tfs_status_enabled') : t('misc.tfs_status_disabled')}
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)',
          marginBottom: 'var(--mac-spacing-4)'
        }}>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--mac-font-size-base)', marginBottom: 'var(--mac-spacing-1)' }}>
              TOTP
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>
              {status.totp_verified ? t('misc.tfs_totp_configured') : t('misc.tfs_totp_not_configured')}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--mac-font-size-base)', marginBottom: 'var(--mac-spacing-1)' }}>
              {t('misc.tfs_backup_codes_label')}
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>
              {t('misc.tfs_backup_codes_remaining', { count: status.backup_codes_count })}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--mac-font-size-base)', marginBottom: 'var(--mac-spacing-1)' }}>
              {t('misc.tfs_recovery_label')}
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>
              {status.recovery_enabled ? t('misc.tfs_recovery_configured') : t('misc.tfs_recovery_not_configured')}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--mac-font-size-base)', marginBottom: 'var(--mac-spacing-1)' }}>
              {t('misc.tfs_trusted_devices_label')}
            </div>
            <div style={{ color: 'var(--text-primary)', fontWeight: 'var(--mac-font-weight-medium)' }}>
              {status.trusted_devices_count}
            </div>
          </div>
        </div>

        {status.last_used &&
        <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--mac-font-size-xs)' }}>
            {t('misc.tfs_last_used', { date: new Date(status.last_used).toLocaleString() })}
          </div>
        }
      </div>

      {/* Backup коды */}
      {status.enabled &&
      <div style={{
        background: 'var(--bg-secondary)',
        padding: 'var(--mac-spacing-6)',
        borderRadius: 'var(--mac-radius-lg)',
        marginBottom: 'var(--mac-spacing-6)'
      }}>
          <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 'var(--mac-spacing-4)'
        }}>
            <h3 style={{ margin: 0, color: 'var(--text-primary)' }}>
              {t('misc.tfs_backup_codes_title')}
            </h3>
            <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
              <button
              onClick={loadBackupCodes}
              style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                background: 'var(--accent-color)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-1)'
              }}>
              
                <Eye size={12} />
                {t('misc.tfs_show_button')}
              </button>
              <button
              onClick={handleRegenerateBackupCodes}
              disabled={loading}
              style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: loading ? 'not-allowed' : 'pointer',
                fontSize: 'var(--mac-font-size-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-1)'
              }}>
              
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                {t('misc.tfs_regenerate_button')}
              </button>
            </div>
          </div>

          {showBackupCodes && backupCodes.length > 0 &&
        <div>
              <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 'var(--mac-spacing-2)',
            marginBottom: 'var(--mac-spacing-4)'
          }}>
                {backupCodes.map((code, index) =>
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-2)',
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                background: 'var(--bg-primary)',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--border-color)'
              }}>
              
                    <code style={{
                flex: 1,
                fontFamily: 'monospace',
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--text-primary)'
              }}>
                      {code}
                    </code>
                    <button
                onClick={() => copyToClipboard(code, `code-${index}`)}
                aria-label={t('misc.tfs_copy_code_aria', { index: index + 1 })}
                style={{
                  padding: 'var(--mac-spacing-1)',
                  background: 'transparent',
                  color: 'var(--text-secondary)',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                
                      {copiedCode === `code-${index}` ? <CheckCircle size={12} /> : <Copy size={12} />}
                    </button>
                  </div>
            )}
              </div>
              
              <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--mac-spacing-3)',
            background: 'var(--mac-warning-bg)',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid #F59E0B'
          }}>
                <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)',
              color: 'var(--mac-warning)',
              fontSize: 'var(--mac-font-size-xs)'
            }}>
                  <AlertCircle size={16} />
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>{t('misc.tfs_important_label')}</span>
                  <span>{t('misc.tfs_backup_warning')}</span>
                </div>
                <button
              onClick={downloadBackupCodes}
              style={{
                padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
                background: 'var(--mac-warning)',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-1)'
              }}>
              
                  <Download size={12} />
                  {t('misc.tfs_download_button')}
                </button>
              </div>
            </div>
        }
        </div>
      }

      {/* Доверенные устройства */}
      {devices.length > 0 &&
      <div style={{
        background: 'var(--bg-secondary)',
        padding: 'var(--mac-spacing-6)',
        borderRadius: 'var(--mac-radius-lg)',
        marginBottom: 'var(--mac-spacing-6)'
      }}>
          <h3 style={{ margin: '0 0 16px 0', color: 'var(--text-primary)' }}>
            {t('misc.tfs_trusted_devices_title')}
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
            {devices.map((device) =>
          <div
            key={device.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: 'var(--mac-spacing-4)',
              background: 'var(--bg-primary)',
              borderRadius: 'var(--mac-radius-md)',
              border: '1px solid var(--border-color)'
            }}>
            
                <div style={{ flex: 1 }}>
                  <div style={{
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--text-primary)',
                marginBottom: 'var(--mac-spacing-1)'
              }}>
                    {device.device_name}
                  </div>
                  <div style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--mac-spacing-1)'
              }}>
                    {device.device_type} • {device.ip_address}
                  </div>
                  <div style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--text-secondary)'
              }}>
                    {device.last_used ?
                t('misc.tfs_device_last_used', { date: new Date(device.last_used).toLocaleString() }) :
                t('misc.tfs_device_never_used')
                }
                  </div>
                </div>
                
                <button
              onClick={() => handleUntrustDevice(device.id)}
              style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                background: 'var(--mac-error-bg)',
                color: 'var(--mac-error)',
                border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
                borderRadius: 'var(--mac-radius-sm)',
                cursor: 'pointer',
                fontSize: 'var(--mac-font-size-xs)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-1)'
              }}>
              
                  <Trash2 size={12} />
                  {t('misc.tfs_revoke_button')}
                </button>
              </div>
          )}
          </div>
        </div>
      }

      {/* Действия */}
      <div style={{
        background: 'var(--bg-secondary)',
        padding: 'var(--mac-spacing-6)',
        borderRadius: 'var(--mac-radius-lg)'
      }}>
        <h3 style={{ margin: '0 0 16px 0', color: 'var(--text-primary)' }}>
          {t('misc.tfs_actions_title')}
        </h3>
        
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', flexWrap: 'wrap' }}>
          {!status.enabled ?
          <button
            onClick={() => window.location.href = '/settings/2fa/setup'}
            style={{
              padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: 'var(--mac-radius-md)',
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
            
              <Shield size={16} />
              {t('misc.tfs_setup_button')}
            </button> :

          <button
            onClick={handleDisable2FA}
            disabled={loading}
            style={{
              padding: 'var(--mac-spacing-3) var(--mac-spacing-6)',
              background: 'var(--mac-error-bg)',
              color: 'var(--mac-error)',
              border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
              borderRadius: 'var(--mac-radius-md)',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
            
              <Trash2 size={16} />
              {loading ? t('misc.tfs_disabling') : t('misc.tfs_disable_button')}
            </button>
          }
        </div>
      </div>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

export default TwoFactorSettings;
