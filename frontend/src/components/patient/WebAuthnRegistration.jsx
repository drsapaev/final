import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import {
  Card, CardContent, CardHeader, CardTitle, Badge, Button, Icon, Alert, Input,
} from '../ui/macos';
import { useWebAuthn } from '../../hooks/useWebAuthn';

/**
 * WebAuthn Registration UI — P5 frontend integration.
 *
 * Allows patients to register passkeys (TouchID/FaceID/YubiKey) as
 * an alternative to Telegram Mini App authentication.
 */
export default function WebAuthnRegistration({ patientId }) {
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
      name: credentialName || `Passkey ${new Date().toLocaleDateString('ru-RU')}`,
      rpId: window.location.hostname,
      rpName: 'Медицинская клиника',
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
            WebAuthn не поддерживается этим браузером. Используйте Chrome, Safari или Edge с включённой поддержкой биометрии.
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card variant="filled" padding="none">
      <CardHeader style={{ background: 'var(--mac-bg-tertiary)', borderBottom: '1px solid var(--mac-border)', padding: '12px 16px' }}>
        <CardTitle style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="lock.shield" size={20} />
          Ключи доступа (Passkeys)
        </CardTitle>
      </CardHeader>
      <CardContent style={{ padding: '16px', display: 'grid', gap: '16px' }}>
        {/* Registration form */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <Input
              label="Название устройства"
              value={credentialName}
              onChange={(e) => setCredentialName(e.target.value)}
              placeholder="Напр. iPhone 15, Рабочий ноутбук"
              disabled={isRegistering}
            />
          </div>
          <Button
            variant="primary"
            onClick={handleRegister}
            loading={isRegistering}
            disabled={isRegistering}
          >
            <Icon name="plus" size={16} />
            {isRegistering ? 'Регистрация…' : 'Добавить passkey'}
          </Button>
        </div>

        {error && (
          <Alert severity="error">
            {error === 'webauthn_not_supported' && 'Браузер не поддерживает WebAuthn'}
            {error === 'not_authenticated' && 'Необходимо войти в систему'}
            {error === 'registration_cancelled' && 'Регистрация отменена'}
            {error === 'registration_failed' && 'Ошибка регистрации. Попробуйте снова.'}
            {!['webauthn_not_supported', 'not_authenticated', 'registration_cancelled', 'registration_failed'].includes(error) && error}
          </Alert>
        )}

        {/* Credentials list */}
        {loading ? (
          <Alert severity="info">Загрузка списка ключей…</Alert>
        ) : credentials.length === 0 ? (
          <Alert severity="info">
            У вас нет зарегистрированных ключей доступа. Добавьте passkey для входа без Telegram.
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
                    {cred.name || 'Без названия'}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--mac-text-muted)' }}>
                    {cred.device_type || 'Устройство'}
                    {cred.last_used_at ? ` · посл. использование: ${new Date(cred.last_used_at).toLocaleDateString('ru-RU')}` : ''}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="small"
                  onClick={() => handleDeactivate(cred.id)}
                >
                  <Icon name="trash" size={14} />
                  Удалить
                </Button>
              </div>
            ))}
          </div>
        )}

        {/* Info */}
        <Alert severity="info">
          Ключи доступа (passkeys) — это безопасная альтернатива паролям.
          Они хранятся на вашем устройстве и используют биометрию (Face ID, Touch ID)
          или PIN-код для входа. Passkeys защищены от фишинга.
        </Alert>
      </CardContent>
    </Card>
  );
}

WebAuthnRegistration.propTypes = {
  patientId: PropTypes.number,
};
