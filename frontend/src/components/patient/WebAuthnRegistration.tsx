
import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Icon, Alert, Input,
} from '../ui/macos';
import { useWebAuthn } from '../../hooks/useWebAuthn';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";

/**
 * WebAuthn Registration UI — P5 frontend integration.
 *
 * Allows patients to register passkeys (TouchID/FaceID/YubiKey) as
 * an alternative to Telegram Mini App authentication.
 */
export default function WebAuthnRegistration({ patientId }) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const { isSupported, isRegistering, error, register, listCredentials, deactivateCredential } = useWebAuthn();
  const [credentials, setCredentials] = useState([]);
  const [credentialName, setCredentialName] = useState('');
  const [loading, setLoading] = useState(true);

  const loadCredentials = useCallback(async () => {
    setLoading(true);
    const creds = await listCredentials();
    setCredentials(creds);
    setLoading(false);
  }, [listCredentials]);

  useEffect(() => { loadCredentials(); }, [loadCredentials]);

  const handleRegister = async () => {
    const success = await register({
      name: credentialName || t('patient.pat_web_passkey_default', { date: new Date().toLocaleDateString('ru-RU') }),
      rpId: window.location.hostname,
      rpName: t('patient.pat_web_rp_name'),
    });
    if (success) {
      setCredentialName('');
      await loadCredentials();
    }
  };

  const handleDeactivate = async (credentialId) => {
    const success = await deactivateCredential(credentialId);
    if (success) {
      await loadCredentials();
    }
  };

  if (!isSupported) {
    return (
      <Card variant="filled" padding="default">
        <CardContent>
          <Alert severity="warning">
            {t('patient.pat_web_not_supported')}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="filled" padding="none">
      <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
        <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="lock.shield" size={20 as unknown as "small" | "default" | "large" | "xlarge"} />
          {t('patient.pat_web_title')}
        </CardTitle>
      </CardHeader>
      <CardContent style={{ padding: '16px', display: 'grid', gap: '16px' }}>
        {/* Registration form */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <Input
              label={t('patient.pat_web_device_name')}
              value={credentialName}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setCredentialName(e.target.value)}
              placeholder={t('patient.pat_web_device_name_placeholder')}
              disabled={isRegistering}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleRegister}
            loading={isRegistering}
            disabled={isRegistering}
          >
            <Icon name="plus" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
            {isRegistering ? t('patient.pat_web_registering') : t('patient.pat_web_add_passkey')}
          </Button>
        </div>

        {error && (
          <Alert severity="error">
            {error === 'webauthn_not_supported' && t('patient.pat_web_err_not_supported')}
            {error === 'not_authenticated' && t('patient.pat_web_err_not_authenticated')}
            {error === 'registration_cancelled' && t('patient.pat_web_err_cancelled')}
            {error === 'registration_failed' && t('patient.pat_web_err_failed')}
            {!['webauthn_not_supported', 'not_authenticated', 'registration_cancelled', 'registration_failed'].includes(error) && error}
          </Alert>
        )}

        {/* Credentials list */}
        {loading ? (
          <Alert severity="info">{t('patient.pat_web_loading')}</Alert>
        ) : credentials.length === 0 ? (
          <Alert severity="info">
            {t('patient.pat_web_empty')}
          </Alert>
        ) : (
          <div style={{ display: 'grid', gap: '8px' }}>
            {credentials.map((cred) => (
              <div
                key={cred.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 14px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  background: 'var(--mac-bg-primary)',
                }}
              >
                <div>
                  <div style={{ fontWeight: 500, color: 'var(--mac-text-primary)' }}>
                    {cred.name || t('patient.pat_web_no_name')}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>
                    {cred.device_type || t('patient.pat_web_device_default')}
                    {cred.last_used_at ? ` · ${t('patient.pat_web_last_used', { date: new Date(cred.last_used_at).toLocaleDateString('ru-RU') })}` : ''}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="small"
                  onClick={() => handleDeactivate(cred.id)}
                >
                  <Icon name="trash" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                  {t('patient.pat_web_delete')}
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Info */}
        <Alert severity="info">
          {t('patient.pat_web_info')}
        </Alert>
      </CardContent>
    </Card>
  );
}

WebAuthnRegistration.propTypes = {
  patientId: PropTypes.number,
};
