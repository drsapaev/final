import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  Brain,
  Plus,
  Edit,

  Save,
  X,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,
  Key,
  Settings,

  Eye,
  EyeOff } from




'lucide-react';
import {
  MacOSCard, Button, Badge, Input, Checkbox,
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const AISettings = () => {
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState([]);
  const [systemSettings, setSystemSettings] = useState({});
  const [stats, setStats] = useState({});
  const [editingProvider, setEditingProvider] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showApiKeys, setShowApiKeys] = useState({});
  const [testResults, setTestResults] = useState({});
  const [message, setMessage] = useState({ type: '', text: '' });

  // Конфигурация провайдеров
  const providerConfigs = {
    openai: {
      displayName: 'OpenAI GPT',
      description: 'GPT-4, GPT-3.5 для текста и изображений',
      defaultModel: 'gpt-4',
      capabilities: ['text', 'vision'],
      color: 'bg-green-500',
      models: ['gpt-4', 'gpt-3.5-turbo', 'gpt-4-vision-preview']
    },
    gemini: {
      displayName: 'Google Gemini',
      description: 'Gemini Pro для текста и мультимодальных задач',
      defaultModel: 'gemini-pro',
      capabilities: ['text', 'vision'],
      color: 'bg-blue-500',
      models: ['gemini-pro', 'gemini-pro-vision']
    },
    deepseek: {
      displayName: 'DeepSeek',
      description: 'Экономичная альтернатива для текстовых задач',
      defaultModel: 'deepseek-chat',
      capabilities: ['text'],
      color: 'bg-purple-500',
      models: ['deepseek-chat', 'deepseek-coder']
    },
    grok: {
      displayName: 'xAI Grok',
      description: 'Grok от xAI для разговорных задач',
      defaultModel: 'grok-beta',
      capabilities: ['text'],
      color: 'bg-orange-500',
      models: ['grok-beta']
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Загружаем провайдеров, настройки и статистику
      const [providersRes, settingsRes, statsRes] = await Promise.allSettled([
      api.get('/admin/ai/providers'),
      api.get('/admin/ai/settings'),
      api.get('/admin/ai/stats?days_back=7')]
      );

      if (providersRes.status === 'fulfilled') {
        setProviders(providersRes.value.data);
      }

      if (settingsRes.status === 'fulfilled') {
        setSystemSettings(settingsRes.value.data);
      }

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      }

    } catch (error) {
      logger.error('Ошибка загрузки AI данных:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки AI данных' });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProvider = async (providerData) => {
    try {
      if (editingProvider) {
        await api.put(`/admin/ai/providers/${editingProvider.id}`, providerData);
      } else {
        await api.post('/admin/ai/providers', providerData);
      }

      setMessage({
        type: 'success',
        text: editingProvider ? 'Провайдер обновлен' : 'Провайдер создан'
      });
      setEditingProvider(null);
      setShowAddForm(false);
      await loadData();
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || error.message || 'Ошибка сохранения провайдера' });
    }
  };

  const handleTestProvider = async (providerId) => {
    try {
      setTestResults((prev) => ({ ...prev, [providerId]: { testing: true } }));

      const response = await api.post(`/admin/ai/providers/${providerId}/test`, {
        test_prompt: 'Проверка подключения AI провайдера',
        task_type: 'text'
      });

      setTestResults((prev) => ({ ...prev, [providerId]: response.data }));
      setMessage({ type: 'success', text: 'Тест провайдера выполнен успешно' });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setTestResults((prev) => ({
        ...prev,
        [providerId]: {
          success: false,
          error_message: error.message
        }
      }));
      setMessage({ type: 'error', text: 'Ошибка тестирования провайдера' });
    }
  };

  const toggleApiKeyVisibility = (providerId) => {
    setShowApiKeys((prev) => ({
      ...prev,
      [providerId]: !prev[providerId]
    }));
  };

  if (loading) {
    return (
      <MacOSCard className="admin-p-32">
        <div className="admin-flex-center-justify">
          <RefreshCw className="admin-icon-20-spin-mr-8" />
          <span className="admin-text-primary">Загрузка AI настроек...</span>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="admin-flex-col-24">
      {/* Заголовок */}
      <div className="admin-flex-between">
        <div>
          <h2 className="admin-text-2xl admin-text-semi admin-text-primary admin-m-0 admin-mb-4">
            Настройки AI
          </h2>
          <p className="admin-text-sm-secondary admin-m-0">
            Управление AI провайдерами и шаблонами
          </p>
        </div>
        
        <div className="admin-flex-gap-12">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className="admin-icon-16-mr-8" />
            Обновить
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus className="admin-icon-16-mr-8" />
            Добавить провайдера
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text &&
      <div className="admin-flex-center admin-p-16 admin-msg-banner-dynamic" style={{
        '--admin-msg-bg': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
        '--admin-msg-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)',
        '--admin-msg-border': message.type === 'success' ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
      }}>
          {message.type === 'success' ?
        <CheckCircle className="admin-icon-20-mr-8" /> :

        <AlertCircle className="admin-icon-20-mr-8" />
        }
          {message.text}
        </div>
      }

      {/* Статистика */}
      {stats.total_requests !== undefined &&
      <div className="admin-grid-auto-200">
          <MacOSCard className="admin-loading-p-24-center">
            <div className="admin-stat-number admin-text-blue admin-mb-8">
              {stats.total_requests}
            </div>
            <div className="admin-text-sm-secondary">
              Всего запросов
            </div>
          </MacOSCard>
          <MacOSCard className="admin-loading-p-24-center">
            <div className="admin-stat-number admin-text-success admin-mb-8">
              {stats.successful_requests}
            </div>
            <div className="admin-text-sm-secondary">
              Успешных
            </div>
          </MacOSCard>
          <MacOSCard className="admin-loading-p-24-center">
            <div className="admin-stat-number admin-text-warning admin-mb-8">
              {Math.round(stats.cache_hit_rate)}%
            </div>
            <div className="admin-text-sm-secondary">
              Кэш
            </div>
          </MacOSCard>
          <MacOSCard className="admin-loading-p-24-center">
            <div className="admin-stat-number admin-text-purple admin-mb-8">
              {stats.total_tokens_used}
            </div>
            <div className="admin-text-sm-secondary">
              Токенов
            </div>
          </MacOSCard>
        </div>
      }

      {/* Провайдеры */}
      <div className="admin-grid-auto-400-24">
        {providers.map((provider) => {
          const config = providerConfigs[provider.name] || {};
          const testResult = testResults[provider.id];

          return (
            <MacOSCard key={provider.id} className="admin-p-24">
              <div className="admin-flex-between-mb-16">
                <div className="admin-flex-center">
                  <div className="admin-status-dot-12" style={{ '--admin-dot-bg': provider.active ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' }} />
                  <div>
                    <h3 className="admin-heading-lg admin-text-med admin-text-primary admin-m-0">
                      {provider.display_name}
                    </h3>
                    <p className="admin-text-sm-secondary admin-m-0">
                      {config.description}
                    </p>
                  </div>
                </div>
                
                <div className="admin-flex-gap-8">
                  {provider.is_default &&
                  <Badge variant="success">По умолчанию</Badge>
                  }
                  <Badge variant={provider.active ? 'success' : 'secondary'}>
                    {provider.active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </div>
              </div>

              {/* Настройки провайдера */}
              <div className="admin-flex-col-12-sm">
                <div className="admin-flex-between">
                  <span className="admin-text-secondary">Модель:</span>
                  <span className="admin-text-med-primary">{provider.model || '—'}</span>
                </div>
                
                <div className="admin-flex-between">
                  <span className="admin-text-secondary">Температура:</span>
                  <span className="admin-text-med-primary">{provider.temperature}</span>
                </div>
                
                <div className="admin-flex-between">
                  <span className="admin-text-secondary">Макс. токенов:</span>
                  <span className="admin-text-med-primary">{provider.max_tokens}</span>
                </div>

                {/* API ключ */}
                <div className="admin-flex-between">
                  <span className="admin-text-secondary">API ключ:</span>
                  <div className="admin-flex-center-8">
                    <span className="admin-text-xs admin-text-primary admin-font-mono">
                      {showApiKeys[provider.id] ?
                      provider.api_key || '***не установлен***' :
                      '***скрыт***'
                      }
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      title={showApiKeys[provider.id] ? `Hide API key for ${provider.display_name}` : `Show API key for ${provider.display_name}`}
                      aria-label={showApiKeys[provider.id] ? `Hide API key for ${provider.display_name}` : `Show API key for ${provider.display_name}`}
                      onClick={() => toggleApiKeyVisibility(provider.id)}>
                      {showApiKeys[provider.id] ? <EyeOff aria-hidden="true" className="admin-icon-14" /> : <Eye aria-hidden="true" className="admin-icon-14" />}
                    </Button>
                  </div>
                </div>

                {/* Возможности */}
                {provider.capabilities &&
                <div className="admin-flex-between">
                    <span className="admin-text-secondary">Возможности:</span>
                    <div className="admin-flex-gap-4">
                      {provider.capabilities.map((cap) =>
                    <Badge key={cap} variant="outline" className="admin-text-xs">
                          {cap}
                        </Badge>
                    )}
                    </div>
                  </div>
                }
              </div>

              {/* Результат тестирования */}
              {testResult &&
              <div className="admin-mt-16 admin-p-12 admin-test-result-dynamic" style={{
                '--admin-tr-bg': testResult.success ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
                '--admin-tr-border': testResult.success ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
              }}>
                  <div className="admin-text-sm">
                    {testResult.testing ?
                  <div className="admin-flex-center">
                        <RefreshCw className="admin-icon-14-spin-mr-8" />
                        Тестирование...
                      </div> :
                  testResult.success ?
                  <div>
                        <div className="admin-flex-center admin-text-success admin-mb-4">
                          <CheckCircle className="admin-icon-14-mr-8" />
                          Тест пройден успешно
                        </div>
                        <div className="admin-text-xs admin-flex-col-4">
                          <div className="admin-text-primary">Время ответа: {testResult.response_time_ms}мс</div>
                          <div className="admin-text-primary">Токенов: {testResult.tokens_used}</div>
                        </div>
                      </div> :

                  <div className="admin-text-error">
                        <div className="admin-flex-center admin-mb-4">
                          <AlertCircle className="admin-icon-14-mr-8" />
                          Ошибка тестирования
                        </div>
                        <div className="admin-text-xs">{testResult.error_message}</div>
                      </div>
                  }
                  </div>
                </div>
              }

              {/* Действия */}
              <div className="admin-flex-gap-8-mt-16">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditingProvider(provider)}
                  className="admin-flex-1">
                  
                  <Edit className="admin-icon-14-mr-8" />
                  Настроить
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  title={`Test ${provider.display_name} provider`}
                  aria-label={`Test ${provider.display_name} provider`}
                  onClick={() => handleTestProvider(provider.id)}
                  disabled={!provider.active || !provider.api_key}>
                  <TestTube aria-hidden="true" className="admin-icon-14" />
                </Button>
              </div>
            </MacOSCard>);

        })}

        {/* Карточка добавления нового провайдера */}
        <MacOSCard className="admin-p-24 admin-text-center admin-card-dashed">
          <Brain className="admin-icon-48-mx-auto-mb-16-tertiary" />
          <h3 className="admin-heading-lg admin-text-med admin-text-primary admin-m-0 admin-mb-8">
            Добавить AI провайдера
          </h3>
          <p className="admin-text-secondary admin-mb-16 admin-m-0">
            Настройте новый AI провайдер для использования в системе
          </p>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus className="admin-icon-16-mr-8" />
            Добавить
          </Button>
        </MacOSCard>
      </div>

      {/* Системные настройки */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-heading-lg admin-text-med admin-text-primary admin-m-0 admin-mb-16 admin-flex-center">
          <Settings className="admin-icon-20-mr-8-blue" />
          Системные настройки AI
        </h3>
        
        <SystemSettingsForm
          settings={systemSettings}
          onSave={(settings) => {
            // Сохранение системных настроек
            logger.log('Сохранение системных настроек:', settings);
          }} />
        
      </MacOSCard>

      {/* Форма провайдера */}
      {(showAddForm || editingProvider) &&
      <ProviderForm
        provider={editingProvider}
        providerConfigs={providerConfigs}
        onSave={handleSaveProvider}
        onCancel={() => {
          setShowAddForm(false);
          setEditingProvider(null);
        }} />

      }
    </div>);

};

// Компонент формы провайдера
const ProviderForm = ({ provider, providerConfigs, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    name: provider?.name || '',
    display_name: provider?.display_name || '',
    api_key: provider?.api_key || '',
    api_url: provider?.api_url || '',
    model: provider?.model || '',
    temperature: provider?.temperature || 0.2,
    max_tokens: provider?.max_tokens || 1000,
    active: provider?.active || false,
    is_default: provider?.is_default || false,
    capabilities: provider?.capabilities || ['text']
  });

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!formData.name || !formData.display_name) {
      alert('Заполните обязательные поля');
      return;
    }

    onSave(formData);
  };

  const handlePresetSelect = (presetName) => {
    const preset = providerConfigs[presetName];
    if (preset) {
      setFormData((prev) => ({
        ...prev,
        name: presetName,
        display_name: preset.displayName,
        model: preset.defaultModel,
        capabilities: preset.capabilities
      }));
    }
  };

  return (
    <MacOSCard className="admin-p-24">
      <h3 className="admin-heading-lg admin-text-med admin-text-primary admin-m-0 admin-mb-16">
        {provider ? 'Редактирование провайдера' : 'Добавление AI провайдера'}
      </h3>
      
      {/* Быстрые пресеты */}
      {!provider &&
      <div className="admin-mb-24">
          <label className="admin-text-sm-med-primary admin-label-block-md">
            Быстрые настройки:
          </label>
          <div className="admin-flex-gap-8-wrap">
            {Object.entries(providerConfigs).map(([key, config]) =>
          <Button
            key={key}
            variant="outline"
            size="sm"
            onClick={() => handlePresetSelect(key)}>
            
                {config.displayName}
              </Button>
          )}
          </div>
        </div>
      }
      
      <form onSubmit={handleSubmit} className="admin-flex-col-16">
        <div className="admin-grid-auto-300">
          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              Имя провайдера *
            </label>
            <Input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="openai, gemini, deepseek"
              className="admin-w-full"
              required />
            
          </div>

          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              Отображаемое имя *
            </label>
            <Input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData((prev) => ({ ...prev, display_name: e.target.value }))}
              placeholder="OpenAI GPT-4"
              className="admin-w-full"
              required />
            
          </div>

          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              <Key className="admin-icon-16-inline-mr-4" />
              API ключ
            </label>
            <Input
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData((prev) => ({ ...prev, api_key: e.target.value }))}
              placeholder="sk-..."
              className="admin-w-full" />
            
          </div>

          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              Модель
            </label>
            <Input
              type="text"
              value={formData.model}
              onChange={(e) => setFormData((prev) => ({ ...prev, model: e.target.value }))}
              placeholder="gpt-4, gemini-pro"
              className="admin-w-full" />
            
          </div>

          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              Температура
            </label>
            <Input
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={formData.temperature}
              onChange={(e) => setFormData((prev) => ({ ...prev, temperature: parseFloat(e.target.value) }))}
              className="admin-w-full" />
            
          </div>

          <div>
            <label className="admin-text-sm-med-primary admin-label-block-md">
              Макс. токенов
            </label>
            <Input
              type="number"
              min="100"
              max="8000"
              value={formData.max_tokens}
              onChange={(e) => setFormData((prev) => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
              className="admin-w-full" />
            
          </div>
        </div>

        <div className="admin-flex-center-16">
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.active}
              onChange={(checked) => setFormData((prev) => ({ ...prev, active: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">Активен</span>
          </label>
          
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.is_default}
              onChange={(checked) => setFormData((prev) => ({ ...prev, is_default: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">По умолчанию</span>
          </label>
        </div>

        <div className="admin-flex-end-12">
          <Button type="button" variant="outline" onClick={onCancel}>
            <X className="admin-icon-16-mr-8" />
            Отменить
          </Button>
          <Button type="submit">
            <Save className="admin-icon-16-mr-8" />
            Сохранить
          </Button>
        </div>
      </form>
    </MacOSCard>);

};

// Компонент системных настроек
const SystemSettingsForm = ({ settings, onSave }) => {
  const [formData, setFormData] = useState(settings);

  useEffect(() => {
    setFormData(settings);
  }, [settings]);

  return (
    <div className="admin-flex-col-16">
      <div className="admin-grid-auto-300">
        <div>
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.enabled || false}
              onChange={(checked) => setFormData((prev) => ({ ...prev, enabled: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">AI система включена</span>
          </label>
        </div>

        <div>
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.cache_enabled || false}
              onChange={(checked) => setFormData((prev) => ({ ...prev, cache_enabled: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">Кэширование включено</span>
          </label>
        </div>

        <div>
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.require_consent_for_files || false}
              onChange={(checked) => setFormData((prev) => ({ ...prev, require_consent_for_files: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">Требовать согласие для файлов</span>
          </label>
        </div>

        <div>
          <label className="admin-flex-center">
            <Checkbox
              checked={formData.anonymize_data || false}
              onChange={(checked) => setFormData((prev) => ({ ...prev, anonymize_data: checked }))}
              className="admin-mr-8" />
            
            <span className="admin-text-sm-med-primary">Анонимизировать данные</span>
          </label>
        </div>
      </div>

      <div className="admin-flex-justify-end">
        <Button onClick={() => onSave(formData)}>
          <Save className="admin-icon-16-mr-8" />
          Сохранить настройки
        </Button>
      </div>
    </div>);

};

const providerShape = PropTypes.shape({
  name: PropTypes.string,
  display_name: PropTypes.string,
  api_key: PropTypes.string,
  api_url: PropTypes.string,
  model: PropTypes.string,
  temperature: PropTypes.number,
  max_tokens: PropTypes.number,
  active: PropTypes.bool,
  is_default: PropTypes.bool,
  capabilities: PropTypes.arrayOf(PropTypes.string)
});

const providerConfigShape = PropTypes.shape({
  displayName: PropTypes.string,
  defaultModel: PropTypes.string,
  capabilities: PropTypes.arrayOf(PropTypes.string)
});

ProviderForm.propTypes = {
  provider: providerShape,
  providerConfigs: PropTypes.objectOf(providerConfigShape),
  onSave: PropTypes.func,
  onCancel: PropTypes.func
};

SystemSettingsForm.propTypes = {
  settings: PropTypes.shape({
    enabled: PropTypes.bool,
    cache_enabled: PropTypes.bool,
    require_consent_for_files: PropTypes.bool,
    anonymize_data: PropTypes.bool
  }),
  onSave: PropTypes.func
};

export default AISettings;
