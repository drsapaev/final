import React, { useState, useEffect } from 'react';
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
  MacOSButton, 
  MacOSInput, 
  MacOSSelect,
  MacOSCheckbox
} from '../ui/macos';

const API_BASE = '/api/v1';

const PaymentProviderSettings = () => {
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
  
  // Загрузка настроек при монтировании
  useEffect(() => {
    loadSettings();
  }, []);
  
  const loadSettings = async () => {
    await executeAction(
      async () => {
        const response = await fetch(`${API_BASE}/admin/payment-provider-settings`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            'Content-Type': 'application/json'
          }
        });
        if (response.ok) {
          const data = await response.json();
          setSettings(prev => ({ ...prev, ...data }));
        }
      },
      {
        loadingMessage: 'Загрузка настроек...',
        errorMessage: 'Ошибка загрузки настроек'
      }
    );
  };
  
  const saveSettings = async () => {
    await executeAction(
      async () => {
        const response = await fetch(`${API_BASE}/admin/payment-provider-settings`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Ошибка сохранения настроек');
        }
        
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
        const response = await fetch(`${API_BASE}/admin/test-payment-provider`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify({
            provider: providerName,
            config: settings[providerName]
          })
        });
        
        const result = await response.json();
        
        setTestResults(prev => ({
          ...prev,
          [providerName]: {
            success: response.ok && result.success,
            message: result.message || result.detail || 'Тест завершён',
            timestamp: new Date().toLocaleString()
          }
        }));
        
        if (response.ok && result.success) {
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
      <MacOSCard key={providerName} style={{ padding: '20px', border: '1px solid var(--mac-border)' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '16px',
          paddingBottom: '16px',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <CreditCard style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              {providerName.toUpperCase()}
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MacOSCheckbox
                checked={providerConfig.enabled}
                onChange={() => toggleProviderEnabled(providerName)}
              />
              <span style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                {providerConfig.enabled ? 'Включён' : 'Отключён'}
              </span>
            </div>
          </div>
          
          <MacOSButton
            variant="outline"
            onClick={() => testProvider(providerName)}
            disabled={!providerConfig.enabled || loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              padding: '6px 12px'
            }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Тест
          </MacOSButton>
        </div>
        
        {testResult && (
          <MacOSCard style={{ 
            padding: '12px', 
            marginBottom: '16px',
            backgroundColor: testResult.success ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
            border: testResult.success ? '1px solid var(--mac-success-border)' : '1px solid var(--mac-error-border)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {testResult.success ? (
                <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-success)' }} />
              ) : (
                <XCircle style={{ width: '16px', height: '16px', color: 'var(--mac-error)' }} />
              )}
              <span style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: testResult.success ? 'var(--mac-success)' : 'var(--mac-error)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                {testResult.message}
              </span>
              <small style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-tertiary)',
                marginLeft: 'auto'
              }}>
                {testResult.timestamp}
              </small>
            </div>
          </MacOSCard>
        )}
        
        {providerConfig.enabled && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MacOSCheckbox
                checked={providerConfig.test_mode}
                onChange={(checked) => updateProviderSetting(providerName, 'test_mode', checked)}
              />
              <span style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-primary)' 
              }}>
                Тестовый режим
              </span>
            </div>
            
            {providerName === 'click' && (
              <>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Service ID
                  </label>
                  <MacOSInput
                    type="text"
                    value={providerConfig.service_id}
                    onChange={(e) => updateProviderSetting(providerName, 'service_id', e.target.value)}
                    placeholder="Введите Service ID"
                    style={{ width: '100%' }}
                  />
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Merchant ID
                  </label>
                  <MacOSInput
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                    style={{ width: '100%' }}
                  />
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Secret Key
                  </label>
                  <div style={{ position: 'relative' }}>
                    <MacOSInput
                      type={showSecrets.click ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                      style={{ width: '100%', paddingRight: '40px' }}
                    />
                    <MacOSButton
                      type="button"
                      variant="outline"
                      onClick={() => toggleShowSecret('click')}
                      style={{ 
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        padding: '4px',
                        minWidth: 'auto',
                        width: '32px',
                        height: '32px'
                      }}
                    >
                      {showSecrets.click ? (
                        <EyeOff style={{ width: '16px', height: '16px' }} />
                      ) : (
                        <Eye style={{ width: '16px', height: '16px' }} />
                      )}
                    </MacOSButton>
                  </div>
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Base URL
                  </label>
                  <MacOSInput
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://api.click.uz/v2"
                    style={{ width: '100%' }}
                  />
                </div>
              </>
            )}
            
            {providerName === 'payme' && (
              <>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Merchant ID
                  </label>
                  <MacOSInput
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                    style={{ width: '100%' }}
                  />
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Secret Key
                  </label>
                  <div style={{ position: 'relative' }}>
                    <MacOSInput
                      type={showSecrets.payme ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                      style={{ width: '100%', paddingRight: '40px' }}
                    />
                    <MacOSButton
                      type="button"
                      variant="outline"
                      onClick={() => toggleShowSecret('payme')}
                      style={{ 
                        position: 'absolute',
                        right: '8px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        padding: '4px',
                        minWidth: 'auto',
                        width: '32px',
                        height: '32px'
                      }}
                    >
                      {showSecrets.payme ? (
                        <EyeOff style={{ width: '16px', height: '16px' }} />
                      ) : (
                        <Eye style={{ width: '16px', height: '16px' }} />
                      )}
                    </MacOSButton>
                  </div>
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Base URL
                  </label>
                  <MacOSInput
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://checkout.paycom.uz"
                    style={{ width: '100%' }}
                  />
                </div>
                
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    API URL
                  </label>
                  <MacOSInput
                    type="url"
                    value={providerConfig.api_url}
                    onChange={(e) => updateProviderSetting(providerName, 'api_url', e.target.value)}
                    placeholder="https://api.paycom.uz"
                    style={{ width: '100%' }}
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
    <div style={{ 
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '24px',
          paddingBottom: '24px',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Settings style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Настройки платежных провайдеров
            </h2>
          </div>
          
          <MacOSButton
            onClick={saveSettings}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-accent-blue)',
              border: 'none',
              padding: '8px 16px'
            }}
          >
            <Save style={{ width: '16px', height: '16px' }} />
            Сохранить
          </MacOSButton>
        </div>
      
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Общие настройки */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '16px' 
            }}>
              Общие настройки
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px' 
                }}>
                  Провайдер по умолчанию
                </label>
                <MacOSSelect
                  value={settings.default_provider}
                  onChange={(e) => updateGeneralSetting('default_provider', e.target.value)}
                  options={settings.enabled_providers.map(provider => ({
                    value: provider,
                    label: provider.toUpperCase()
                  }))}
                  style={{ width: '100%' }}
                />
              </div>
              
              <MacOSCard style={{ 
                padding: '16px', 
                backgroundColor: 'var(--mac-warning-bg)', 
                border: '1px solid var(--mac-warning-border)' 
              }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  <AlertTriangle style={{ 
                    width: '20px', 
                    height: '20px', 
                    color: 'var(--mac-warning)', 
                    marginTop: '2px',
                    flexShrink: 0
                  }} />
                  <div>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-warning)', 
                      margin: '0 0 8px 0' 
                    }}>
                      <strong>Важно:</strong>
                    </p>
                    <ul style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-warning)', 
                      margin: 0,
                      paddingLeft: '16px'
                    }}>
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
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '16px' 
            }}>
              Конфигурация провайдеров
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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

