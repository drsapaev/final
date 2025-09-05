import React, { useState, useEffect } from 'react';
import { 
  Brain, 
  Plus, 
  Edit, 
  Trash2, 
  Save, 
  X,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,
  Key,
  Settings,
  BarChart3,
  Eye,
  EyeOff,
  Play,
  Zap,
  Clock,
  TrendingUp
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

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
      const [providersRes, settingsRes, statsRes] = await Promise.all([
        fetch('/api/v1/admin/ai/providers', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/ai/settings', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/ai/stats?days_back=7', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        })
      ]);

      if (providersRes.ok) {
        const providersData = await providersRes.json();
        setProviders(providersData);
      }

      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setSystemSettings(settingsData);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

    } catch (error) {
      console.error('Ошибка загрузки AI данных:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки AI данных' });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProvider = async (providerData) => {
    try {
      const method = editingProvider ? 'PUT' : 'POST';
      const url = editingProvider 
        ? `/api/v1/admin/ai/providers/${editingProvider.id}`
        : '/api/v1/admin/ai/providers';

      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(providerData)
      });

      if (response.ok) {
        setMessage({ 
          type: 'success', 
          text: editingProvider ? 'Провайдер обновлен' : 'Провайдер создан' 
        });
        setEditingProvider(null);
        setShowAddForm(false);
        await loadData();
      } else {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка сохранения провайдера');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const handleTestProvider = async (providerId) => {
    try {
      setTestResults(prev => ({ ...prev, [providerId]: { testing: true } }));

      const response = await fetch(`/api/v1/admin/ai/providers/${providerId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          test_prompt: "Проверка подключения AI провайдера",
          task_type: "text"
        })
      });

      if (response.ok) {
        const result = await response.json();
        setTestResults(prev => ({ ...prev, [providerId]: result }));
        setMessage({ type: 'success', text: 'Тест провайдера выполнен успешно' });
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка тестирования:', error);
      setTestResults(prev => ({ 
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
    setShowApiKeys(prev => ({
      ...prev,
      [providerId]: !prev[providerId]
    }));
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка AI настроек...</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Настройки AI
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Управление AI провайдерами и шаблонами
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus size={16} className="mr-2" />
            Добавить провайдера
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Статистика */}
      {stats.total_requests !== undefined && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{stats.total_requests}</div>
            <div className="text-sm text-gray-600">Всего запросов</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{stats.successful_requests}</div>
            <div className="text-sm text-gray-600">Успешных</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-orange-600">{Math.round(stats.cache_hit_rate)}%</div>
            <div className="text-sm text-gray-600">Кэш</div>
          </Card>
          <Card className="p-4 text-center">
            <div className="text-2xl font-bold text-purple-600">{stats.total_tokens_used}</div>
            <div className="text-sm text-gray-600">Токенов</div>
          </Card>
        </div>
      )}

      {/* Провайдеры */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {providers.map(provider => {
          const config = providerConfigs[provider.name] || {};
          const testResult = testResults[provider.id];
          
          return (
            <Card key={provider.id} className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center">
                  <div className={`w-3 h-3 rounded-full mr-3 ${provider.active ? 'bg-green-500' : 'bg-gray-400'}`} />
                  <div>
                    <h3 className="text-lg font-medium">{provider.display_name}</h3>
                    <p className="text-sm text-gray-500">{config.description}</p>
                  </div>
                </div>
                
                <div className="flex gap-2">
                  {provider.is_default && (
                    <Badge variant="success">По умолчанию</Badge>
                  )}
                  <Badge variant={provider.active ? 'success' : 'secondary'}>
                    {provider.active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </div>
              </div>

              {/* Настройки провайдера */}
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Модель:</span>
                  <span className="font-medium">{provider.model || '—'}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-gray-600">Температура:</span>
                  <span className="font-medium">{provider.temperature}</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-gray-600">Макс. токенов:</span>
                  <span className="font-medium">{provider.max_tokens}</span>
                </div>

                {/* API ключ */}
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">API ключ:</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs">
                      {showApiKeys[provider.id] 
                        ? provider.api_key || '***не установлен***'
                        : '***скрыт***'
                      }
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => toggleApiKeyVisibility(provider.id)}
                    >
                      {showApiKeys[provider.id] ? <EyeOff size={14} /> : <Eye size={14} />}
                    </Button>
                  </div>
                </div>

                {/* Возможности */}
                {provider.capabilities && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Возможности:</span>
                    <div className="flex gap-1">
                      {provider.capabilities.map(cap => (
                        <Badge key={cap} variant="outline" className="text-xs">
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Результат тестирования */}
              {testResult && (
                <div className={`mt-4 p-3 rounded-lg ${
                  testResult.success 
                    ? 'bg-green-50 border border-green-200 dark:bg-green-900/20'
                    : 'bg-red-50 border border-red-200 dark:bg-red-900/20'
                }`}>
                  <div className="text-sm">
                    {testResult.testing ? (
                      <div className="flex items-center">
                        <RefreshCw size={14} className="animate-spin mr-2" />
                        Тестирование...
                      </div>
                    ) : testResult.success ? (
                      <div>
                        <div className="flex items-center text-green-700 dark:text-green-400 mb-1">
                          <CheckCircle size={14} className="mr-2" />
                          Тест пройден успешно
                        </div>
                        <div className="text-xs space-y-1">
                          <div>Время ответа: {testResult.response_time_ms}мс</div>
                          <div>Токенов: {testResult.tokens_used}</div>
                        </div>
                      </div>
                    ) : (
                      <div className="text-red-700 dark:text-red-400">
                        <div className="flex items-center mb-1">
                          <AlertCircle size={14} className="mr-2" />
                          Ошибка тестирования
                        </div>
                        <div className="text-xs">{testResult.error_message}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Действия */}
              <div className="flex gap-2 mt-4">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditingProvider(provider)}
                  className="flex-1"
                >
                  <Edit size={14} className="mr-2" />
                  Настроить
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTestProvider(provider.id)}
                  disabled={!provider.active || !provider.api_key}
                >
                  <TestTube size={14} />
                </Button>
              </div>
            </Card>
          );
        })}

        {/* Карточка добавления нового провайдера */}
        <Card className="p-6 border-2 border-dashed border-gray-300 dark:border-gray-600">
          <div className="text-center">
            <Brain size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Добавить AI провайдера
            </h3>
            <p className="text-gray-500 mb-4">
              Настройте новый AI провайдер для использования в системе
            </p>
            <Button onClick={() => setShowAddForm(true)}>
              <Plus size={16} className="mr-2" />
              Добавить
            </Button>
          </div>
        </Card>
      </div>

      {/* Системные настройки */}
      <Card className="p-6">
        <h3 className="text-lg font-medium mb-4 flex items-center">
          <Settings size={20} className="mr-2 text-blue-600" />
          Системные настройки AI
        </h3>
        
        <SystemSettingsForm 
          settings={systemSettings}
          onSave={(settings) => {
            // Сохранение системных настроек
            console.log('Сохранение системных настроек:', settings);
          }}
        />
      </Card>

      {/* Форма провайдера */}
      {(showAddForm || editingProvider) && (
        <ProviderForm
          provider={editingProvider}
          providerConfigs={providerConfigs}
          onSave={handleSaveProvider}
          onCancel={() => {
            setShowAddForm(false);
            setEditingProvider(null);
          }}
        />
      )}
    </div>
  );
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
      setFormData(prev => ({
        ...prev,
        name: presetName,
        display_name: preset.displayName,
        model: preset.defaultModel,
        capabilities: preset.capabilities
      }));
    }
  };

  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium mb-4">
        {provider ? 'Редактирование провайдера' : 'Добавление AI провайдера'}
      </h3>
      
      {/* Быстрые пресеты */}
      {!provider && (
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Быстрые настройки:
          </label>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(providerConfigs).map(([key, config]) => (
              <Button
                key={key}
                variant="outline"
                size="sm"
                onClick={() => handlePresetSelect(key)}
              >
                {config.displayName}
              </Button>
            ))}
          </div>
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Имя провайдера *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="openai, gemini, deepseek"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Отображаемое имя *
            </label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="OpenAI GPT-4"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Key size={16} className="inline mr-1" />
              API ключ
            </label>
            <input
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="sk-..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Модель
            </label>
            <input
              type="text"
              value={formData.model}
              onChange={(e) => setFormData(prev => ({ ...prev, model: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="gpt-4, gemini-pro"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Температура
            </label>
            <input
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={formData.temperature}
              onChange={(e) => setFormData(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Макс. токенов
            </label>
            <input
              type="number"
              min="100"
              max="8000"
              value={formData.max_tokens}
              onChange={(e) => setFormData(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>
        </div>

        <div className="flex items-center gap-4">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.active}
              onChange={(e) => setFormData(prev => ({ ...prev, active: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">Активен</span>
          </label>
          
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.is_default}
              onChange={(e) => setFormData(prev => ({ ...prev, is_default: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">По умолчанию</span>
          </label>
        </div>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            <X size={16} className="mr-2" />
            Отменить
          </Button>
          <Button type="submit">
            <Save size={16} className="mr-2" />
            Сохранить
          </Button>
        </div>
      </form>
    </Card>
  );
};

// Компонент системных настроек
const SystemSettingsForm = ({ settings, onSave }) => {
  const [formData, setFormData] = useState(settings);

  useEffect(() => {
    setFormData(settings);
  }, [settings]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.enabled || false}
              onChange={(e) => setFormData(prev => ({ ...prev, enabled: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">AI система включена</span>
          </label>
        </div>

        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.cache_enabled || false}
              onChange={(e) => setFormData(prev => ({ ...prev, cache_enabled: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">Кэширование включено</span>
          </label>
        </div>

        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.require_consent_for_files || false}
              onChange={(e) => setFormData(prev => ({ ...prev, require_consent_for_files: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">Требовать согласие для файлов</span>
          </label>
        </div>

        <div>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={formData.anonymize_data || false}
              onChange={(e) => setFormData(prev => ({ ...prev, anonymize_data: e.target.checked }))}
              className="mr-2"
            />
            <span className="text-sm font-medium">Анонимизировать данные</span>
          </label>
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={() => onSave(formData)}>
          <Save size={16} className="mr-2" />
          Сохранить настройки
        </Button>
      </div>
    </div>
  );
};

export default AISettings;
