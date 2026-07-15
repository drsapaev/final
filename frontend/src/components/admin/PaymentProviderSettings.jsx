import { useState, useEffect, useCallback } from 'react';
import {
  Settings,
  CreditCard,
  Save,
  RefreshCw,
  Eye,
  EyeOff,
  CheckCircle,
  XCircle,
  AlertTriangle
} from 'lucide-react';
import { toast } from 'react-toastify';
import { useAsyncAction } from '../../hooks/useAsyncAction';
import {
  MacOSCard,
  Button,
  Input,
  Checkbox,
  Select,
} from '../ui/macos';
import {
  fetchPaymentProviderSettings,
  savePaymentProviderSettings,
  testPaymentProviderConfig,
} from '../../api/adminSettings';
import { useTranslation } from '../../i18n/useTranslation';

const PaymentProviderSettings = () => {
  const { t } = useTranslation();
  const { executeAction, loading } = useAsyncAction();

  const [settings, setSettings] = useState({
    default_provider: 'click',
    enabled_providers: ['click', 'payme'],
    click: {
      enabled: true,
      service_id: '',
      merchant_id: '',
      secret_key: '',
      base_url: 'https://api.click.uz/v2',
      test_mode: true
    },
    payme: {
      enabled: true,
      merchant_id: '',
      secret_key: '',
      base_url: 'https://checkout.paycom.uz',
      api_url: 'https://api.paycom.uz',
      test_mode: true
    }
  });

  const [showSecrets, setShowSecrets] = useState({
    click: false,
    payme: false
  });

  const [testResults, setTestResults] = useState({});

  const loadSettings = useCallback(async () => {
    await executeAction(
      async () => {
        const data = await fetchPaymentProviderSettings();
        setSettings((prev) => ({ ...prev, ...data }));
      },
      {
        loadingMessage: 'Загрузка настроек...',
        errorMessage: 'Ошибка загрузки настроек'
      }
    );
  }, [executeAction]);

  // Загрузка настроек при монтировании
  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const saveSettings = async () => {
    await executeAction(
      async () => {
        await savePaymentProviderSettings(settings);
        toast.success('Настройки сохранены успешно');
      },
      {
        loadingMessage: 'Сохранение настроек...',
        errorMessage: 'Ошибка сохранения настроек'
      }
    );
  };

  const testProvider = async (providerName) => {
    await executeAction(
      async () => {
        const result = await testPaymentProviderConfig(providerName, settings[providerName]);

        setTestResults(prev => ({
          ...prev,
          [providerName]: {
            success: Boolean(result?.success),
            message: result.message || result.detail || 'Тест завершён',
            timestamp: new Date().toLocaleString()
          }
        }));

        if (result?.success) {
          toast.success(`${providerName.toUpperCase()}: Тест прошёл успешно`);
        } else {
          toast.error(`${providerName.toUpperCase()}: ${result.message || result.detail}`);
        }
      },
      {
        loadingMessage: `Тестирование ${providerName.toUpperCase()}...`,
        errorMessage: `Ошибка тестирования ${providerName.toUpperCase()}`
      }
    );
  };

  const updateProviderSetting = (provider, field, value) => {
    setSettings(prev => ({
      ...prev,
      [provider]: {
        ...prev[provider],
        [field]: value
      }
    }));
  };

  const updateGeneralSetting = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const toggleProviderEnabled = (provider) => {
    const newEnabled = !settings[provider].enabled;
    updateProviderSetting(provider, 'enabled', newEnabled);

    // Обновляем список включённых провайдеров
    if (newEnabled) {
      if (!settings.enabled_providers.includes(provider)) {
        updateGeneralSetting('enabled_providers', [...settings.enabled_providers, provider]);
      }
    } else {
      updateGeneralSetting('enabled_providers', settings.enabled_providers.filter(p => p !== provider));

      // Если отключили провайдер по умолчанию, выбираем другой
      if (settings.default_provider === provider) {
        const remainingProviders = settings.enabled_providers.filter(p => p !== provider);
        if (remainingProviders.length > 0) {
          updateGeneralSetting('default_provider', remainingProviders[0]);
        }
      }
    }
  };

  const toggleShowSecret = (provider) => {
    setShowSecrets(prev => ({
      ...prev,
      [provider]: !prev[provider]
    }));
  };

  const renderProviderConfig = (providerName, providerConfig) => {
    const testResult = testResults[providerName];

    return (
      <MacOSCard key={providerName} className="admin-p-20-bd-1px-solid-var-mac-bo">
        <div className="admin-d-flex-jc-between-ai-center-mb-16-pb-16-bd-b-1px-solid-var-mac-bo">
          <div className="admin-flex-center-12">
            <CreditCard className="admin-w-24-h-24-blue" />
            <h3 className="admin-fs-lg-fw-semi-primary-m-0">
              {providerName.toUpperCase()}
            </h3>
            <div className="admin-flex-center-8">
              <Checkbox
                checked={providerConfig.enabled}
                onChange={() => toggleProviderEnabled(providerName)}
              />
              <span className="admin-text-sm admin-text-secondary">
                {providerConfig.enabled ? 'Включён' : 'Отключён'}
              </span>
            </div>
          </div>

          <Button
            variant="outline"
            onClick={() => testProvider(providerName)}
            disabled={!providerConfig.enabled || loading}
            className="admin-d-flex-ai-center-gap-8-p-6px-12px"
          >
            <RefreshCw className="admin-icon-16" />
            Тест
          </Button>
        </div>

        {testResult && (
          <MacOSCard className="admin-p-12-mb-16-bgc-dyn-bd-dyn" style={{ '--admin-bgc0': testResult.success ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)', '--admin-bd1': testResult.success ? '1px solid var(--mac-success-border)' : '1px solid var(--mac-error-border)' }}>
            <div className="admin-flex-center-8">
              {testResult.success ? (
                <CheckCircle className="admin-w-16-h-16-success" />
              ) : (
                <XCircle className="admin-w-16-h-16-error" />
              )}
              <span className="admin-fs-sm-fw-med-col-dyn" style={{ '--admin-col0': testResult.success ? 'var(--mac-success)' : 'var(--mac-error)' }}>
                {testResult.message}
              </span>
              <small className="admin-fs-xs-tertiary-ml-auto">
                {testResult.timestamp}
              </small>
            </div>
          </MacOSCard>
        )}

        {providerConfig.enabled && (
          <div className="admin-flex-col-16">
            <div className="admin-flex-center-8">
              <Checkbox
                checked={providerConfig.test_mode}
                onChange={(checked) => updateProviderSetting(providerName, 'test_mode', checked)}
              />
              <span className="admin-fs-sm-primary">
                Тестовый режим
              </span>
            </div>

            {providerName === 'click' && (
              <>
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Service ID
                  </label>
                  <Input
                    type="text"
                    value={providerConfig.service_id}
                    onChange={(e) => updateProviderSetting(providerName, 'service_id', e.target.value)}
                    placeholder="Введите Service ID"
                    className="admin-w-full"
                  />
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Merchant ID
                  </label>
                  <Input
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                    className="admin-w-full"
                  />
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Secret Key
                  </label>
                  <div className="admin-pos-relative">
                    <Input
                      type={showSecrets.click ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                      className="admin-w-100pct-pr-40"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      title={showSecrets.click ? 'Hide Click secret key' : 'Show Click secret key'}
                      aria-label={showSecrets.click ? 'Hide Click secret key' : 'Show Click secret key'}
                      onClick={() => toggleShowSecret('click')}
                      className="admin-pos-absolute-right-8-top-50pct-tf-translateY-50-p-4-minw-auto-w-32-h-32"
                    >
                      {showSecrets.click ? (
                        <EyeOff aria-hidden="true" className="admin-icon-16" />
                      ) : (
                        <Eye aria-hidden="true" className="admin-icon-16" />
                      )}
                    </Button>
                  </div>
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Base URL
                  </label>
                  <Input
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://api.click.uz/v2"
                    className="admin-w-full"
                  />
                </div>
              </>
            )}

            {providerName === 'payme' && (
              <>
                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Merchant ID
                  </label>
                  <Input
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                    className="admin-w-full"
                  />
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Secret Key
                  </label>
                  <div className="admin-pos-relative">
                    <Input
                      type={showSecrets.payme ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                      className="admin-w-100pct-pr-40"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      title={showSecrets.payme ? 'Hide Payme secret key' : 'Show Payme secret key'}
                      aria-label={showSecrets.payme ? 'Hide Payme secret key' : 'Show Payme secret key'}
                      onClick={() => toggleShowSecret('payme')}
                      className="admin-pos-absolute-right-8-top-50pct-tf-translateY-50-p-4-minw-auto-w-32-h-32"
                    >
                      {showSecrets.payme ? (
                        <EyeOff aria-hidden="true" className="admin-icon-16" />
                      ) : (
                        <Eye aria-hidden="true" className="admin-icon-16" />
                      )}
                    </Button>
                  </div>
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    Base URL
                  </label>
                  <Input
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://checkout.paycom.uz"
                    className="admin-w-full"
                  />
                </div>

                <div>
                  <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                    API URL
                  </label>
                  <Input
                    type="url"
                    value={providerConfig.api_url}
                    onChange={(e) => updateProviderSetting(providerName, 'api_url', e.target.value)}
                    placeholder="https://api.paycom.uz"
                    className="admin-w-full"
                  />
                </div>
              </>
            )}
          </div>
        )}
      </MacOSCard>
    );
  };

  return (
    <div className="admin-p-0-bgc-bg-primary-minh-100vh">
      <MacOSCard className="admin-p-24">
        {/* Заголовок */}
        <div className="admin-d-flex-jc-between-ai-center-mb-24-pb-24-bd-b-1px-solid-var-mac-bo">
          <div className="admin-flex-center-12">
            <Settings className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              Настройки платежных провайдеров
            </h2>
          </div>

          <Button
            onClick={saveSettings}
            disabled={loading}
            className="admin-d-flex-ai-center-gap-8-bgc-blue-bd-none-p-8px-16px"
          >
            <Save className="admin-icon-16" />
            Сохранить
          </Button>
        </div>

        <div className="admin-flex-col-24">
          {/* Общие настройки */}
          <MacOSCard className="admin-p-24">
            <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
              Общие настройки
            </h3>

            <div className="admin-flex-col-16">
              <div>
                <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">
                  Провайдер по умолчанию
                </label>
                <Select
                  value={settings.default_provider}
                  onChange={(value) => updateGeneralSetting('default_provider', value)}
                  options={settings.enabled_providers.map(provider => ({
                    value: provider,
                    label: provider.toUpperCase()
                  }))}
                  size="large"
                  className="admin-w-full"
                />
              </div>

              <MacOSCard className="admin-p-16-bgc-var-mac-warning-bg-bd-1px-solid-var-mac-wa">
                <div className="admin-d-flex-ai-start-gap-12">
                  <AlertTriangle className="admin-w-20-h-20-warning-mt-2-fsk-0" />
                  <div>
                    <p className="admin-fs-sm-fw-med-warning-m-0-0-8px-0">
                      <strong>Важно:</strong>
                    </p>
                    <ul className="admin-fs-sm-warning-m-0-pl-16">
                      <li>Провайдер по умолчанию будет предложен пользователям первым</li>
                      <li>Тестовый режим использует sandbox окружение провайдеров</li>
                      <li>Обязательно протестируйте настройки перед использованием</li>
                      <li>Secret Key хранится в зашифрованном виде</li>
                    </ul>
                  </div>
                </div>
              </MacOSCard>
            </div>
          </MacOSCard>

          {/* Настройки провайдеров */}
          <MacOSCard className="admin-p-24">
            <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
              Конфигурация провайдеров
            </h3>

            <div className="admin-flex-col-24">
              {Object.entries(settings).map(([key, value]) => {
                if (key === 'click' || key === 'payme') {
                  return renderProviderConfig(key, value);
                }
                return null;
              })}
            </div>
          </MacOSCard>
        </div>
      </MacOSCard>
    </div>
  );
};

export default PaymentProviderSettings;

