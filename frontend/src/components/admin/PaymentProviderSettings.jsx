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
import { toast } from 'react-hot-toast';
import { useAsyncAction } from '../../hooks/useAsyncAction';
import './PaymentProviderSettings.css';

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
      <div key={providerName} className="provider-config">
        <div className="provider-header">
          <div className="provider-title">
            <CreditCard size={20} />
            <h3>{providerName.toUpperCase()}</h3>
            <div className="provider-toggle">
              <label className="switch">
                <input
                  type="checkbox"
                  checked={providerConfig.enabled}
                  onChange={() => toggleProviderEnabled(providerName)}
                />
                <span className="slider"></span>
              </label>
              <span>{providerConfig.enabled ? 'Включён' : 'Отключён'}</span>
            </div>
          </div>
          
          <div className="provider-actions">
            <button
              className="test-btn"
              onClick={() => testProvider(providerName)}
              disabled={!providerConfig.enabled || loading}
            >
              <RefreshCw size={16} />
              Тест
            </button>
          </div>
        </div>
        
        {testResult && (
          <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
            {testResult.success ? <CheckCircle size={16} /> : <XCircle size={16} />}
            <span>{testResult.message}</span>
            <small>{testResult.timestamp}</small>
          </div>
        )}
        
        {providerConfig.enabled && (
          <form className="provider-fields" onSubmit={(e) => e.preventDefault()}>
            <div className="field-row">
              <label>
                <input
                  type="checkbox"
                  checked={providerConfig.test_mode}
                  onChange={(e) => updateProviderSetting(providerName, 'test_mode', e.target.checked)}
                />
                Тестовый режим
              </label>
            </div>
            
            {providerName === 'click' && (
              <>
                <div className="field-row">
                  <label>Service ID</label>
                  <input
                    type="text"
                    value={providerConfig.service_id}
                    onChange={(e) => updateProviderSetting(providerName, 'service_id', e.target.value)}
                    placeholder="Введите Service ID"
                  />
                </div>
                
                <div className="field-row">
                  <label>Merchant ID</label>
                  <input
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                  />
                </div>
                
                <div className="field-row">
                  <label>Secret Key</label>
                  <div className="secret-field">
                    <input
                      type={showSecrets.click ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                    />
                    <button
                      type="button"
                      className="toggle-secret"
                      onClick={() => toggleShowSecret('click')}
                    >
                      {showSecrets.click ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                
                <div className="field-row">
                  <label>Base URL</label>
                  <input
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://api.click.uz/v2"
                  />
                </div>
              </>
            )}
            
            {providerName === 'payme' && (
              <>
                <div className="field-row">
                  <label>Merchant ID</label>
                  <input
                    type="text"
                    value={providerConfig.merchant_id}
                    onChange={(e) => updateProviderSetting(providerName, 'merchant_id', e.target.value)}
                    placeholder="Введите Merchant ID"
                  />
                </div>
                
                <div className="field-row">
                  <label>Secret Key</label>
                  <div className="secret-field">
                    <input
                      type={showSecrets.payme ? 'text' : 'password'}
                      value={providerConfig.secret_key}
                      onChange={(e) => updateProviderSetting(providerName, 'secret_key', e.target.value)}
                      placeholder="Введите Secret Key"
                    />
                    <button
                      type="button"
                      className="toggle-secret"
                      onClick={() => toggleShowSecret('payme')}
                    >
                      {showSecrets.payme ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                </div>
                
                <div className="field-row">
                  <label>Base URL</label>
                  <input
                    type="url"
                    value={providerConfig.base_url}
                    onChange={(e) => updateProviderSetting(providerName, 'base_url', e.target.value)}
                    placeholder="https://checkout.paycom.uz"
                  />
                </div>
                
                <div className="field-row">
                  <label>API URL</label>
                  <input
                    type="url"
                    value={providerConfig.api_url}
                    onChange={(e) => updateProviderSetting(providerName, 'api_url', e.target.value)}
                    placeholder="https://api.paycom.uz"
                  />
                </div>
              </>
            )}
          </form>
        )}
      </div>
    );
  };
  
  return (
    <div className="payment-provider-settings">
      <div className="settings-header">
        <div className="header-title">
          <Settings size={24} />
          <h2>Настройки платежных провайдеров</h2>
        </div>
        
        <button
          className="save-btn primary"
          onClick={saveSettings}
          disabled={loading}
        >
          <Save size={16} />
          Сохранить
        </button>
      </div>
      
      <div className="settings-content">
        {/* Общие настройки */}
        <div className="general-settings">
          <h3>Общие настройки</h3>
          
          <div className="field-row">
            <label>Провайдер по умолчанию</label>
            <select
              value={settings.default_provider}
              onChange={(e) => updateGeneralSetting('default_provider', e.target.value)}
            >
              {settings.enabled_providers.map(provider => (
                <option key={provider} value={provider}>
                  {provider.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
          
          <div className="info-block">
            <AlertTriangle size={16} />
            <div>
              <p><strong>Важно:</strong></p>
              <ul>
                <li>Провайдер по умолчанию будет предложен пользователям первым</li>
                <li>Тестовый режим использует sandbox окружение провайдеров</li>
                <li>Обязательно протестируйте настройки перед использованием</li>
                <li>Secret Key хранится в зашифрованном виде</li>
              </ul>
            </div>
          </div>
        </div>
        
        {/* Настройки провайдеров */}
        <div className="providers-settings">
          <h3>Конфигурация провайдеров</h3>
          
          <div className="providers-list">
            {Object.entries(settings).map(([key, value]) => {
              if (key === 'click' || key === 'payme') {
                return renderProviderConfig(key, value);
              }
              return null;
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaymentProviderSettings;
