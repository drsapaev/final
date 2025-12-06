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
import { Card, Button, Badge, MacOSInput, MacOSCheckbox } from '../ui/macos';
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
        api.get('/admin/ai/stats?days_back=7')
      ]);

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
      setTestResults(prev => ({ ...prev, [providerId]: { testing: true } }));

      const response = await api.post(`/admin/ai/providers/${providerId}/test`, {
        test_prompt: 'Проверка подключения AI провайдера',
        task_type: 'text'
      });

      setTestResults(prev => ({ ...prev, [providerId]: response.data }));
      setMessage({ type: 'success', text: 'Тест провайдера выполнен успешно' });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
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
      <Card style={{ padding: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <RefreshCw style={{ 
            width: '20px', 
            height: '20px', 
            marginRight: '8px', 
            animation: 'spin 1s linear infinite' 
          }} />
          <span style={{ color: 'var(--mac-text-primary)' }}>Загрузка AI настроек...</span>
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            marginBottom: '4px'
          }}>
            Настройки AI
          </h2>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Управление AI провайдерами и шаблонами
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Обновить
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить провайдера
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          padding: '16px', 
          borderRadius: 'var(--mac-radius-md)',
          backgroundColor: message.type === 'success' 
            ? 'var(--mac-success-bg)' 
            : 'var(--mac-error-bg)',
          color: message.type === 'success' 
            ? 'var(--mac-success)' 
            : 'var(--mac-error)',
          border: `1px solid ${message.type === 'success' 
            ? 'var(--mac-success-border)' 
            : 'var(--mac-error-border)'}`
        }}>
          {message.type === 'success' ? (
            <CheckCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          ) : (
            <AlertCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          )}
          {message.text}
        </div>
      )}

      {/* Статистика */}
      {stats.total_requests !== undefined && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <Card style={{ padding: '24px', textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-accent-blue)',
              marginBottom: '8px'
            }}>
              {stats.total_requests}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>
              Всего запросов
            </div>
          </Card>
          <Card style={{ padding: '24px', textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-success)',
              marginBottom: '8px'
            }}>
              {stats.successful_requests}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>
              Успешных
            </div>
          </Card>
          <Card style={{ padding: '24px', textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-warning)',
              marginBottom: '8px'
            }}>
              {Math.round(stats.cache_hit_rate)}%
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>
              Кэш
            </div>
          </Card>
          <Card style={{ padding: '24px', textAlign: 'center' }}>
            <div style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-accent-purple)',
              marginBottom: '8px'
            }}>
              {stats.total_tokens_used}
            </div>
            <div style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>
              Токенов
            </div>
          </Card>
        </div>
      )}

      {/* Провайдеры */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px' }}>
        {providers.map(provider => {
          const config = providerConfigs[provider.name] || {};
          const testResult = testResults[provider.id];
          
          return (
            <Card key={provider.id} style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ 
                    width: '12px', 
                    height: '12px', 
                    borderRadius: '50%', 
                    marginRight: '12px',
                    backgroundColor: provider.active ? 'var(--mac-success)' : 'var(--mac-text-tertiary)'
                  }} />
                  <div>
                    <h3 style={{ 
                      fontSize: 'var(--mac-font-size-lg)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      {provider.display_name}
                    </h3>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>
                      {config.description}
                    </p>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  {provider.is_default && (
                    <Badge variant="success">По умолчанию</Badge>
                  )}
                  <Badge variant={provider.active ? 'success' : 'secondary'}>
                    {provider.active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </div>
              </div>

              {/* Настройки провайдера */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: 'var(--mac-font-size-sm)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>Модель:</span>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>{provider.model || '—'}</span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>Температура:</span>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>{provider.temperature}</span>
                </div>
                
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>Макс. токенов:</span>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>{provider.max_tokens}</span>
                </div>

                {/* API ключ */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--mac-text-secondary)' }}>API ключ:</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ 
                      fontFamily: 'monospace', 
                      fontSize: 'var(--mac-font-size-xs)',
                      color: 'var(--mac-text-primary)'
                    }}>
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
                      {showApiKeys[provider.id] ? <EyeOff style={{ width: '14px', height: '14px' }} /> : <Eye style={{ width: '14px', height: '14px' }} />}
                    </Button>
                  </div>
                </div>

                {/* Возможности */}
                {provider.capabilities && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--mac-text-secondary)' }}>Возможности:</span>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      {provider.capabilities.map(cap => (
                        <Badge key={cap} variant="outline" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Результат тестирования */}
              {testResult && (
                <div style={{ 
                  marginTop: '16px', 
                  padding: '12px', 
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: testResult.success 
                    ? 'var(--mac-success-bg)' 
                    : 'var(--mac-error-bg)',
                  border: `1px solid ${testResult.success 
                    ? 'var(--mac-success-border)' 
                    : 'var(--mac-error-border)'}`
                }}>
                  <div style={{ fontSize: 'var(--mac-font-size-sm)' }}>
                    {testResult.testing ? (
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <RefreshCw style={{ width: '14px', height: '14px', marginRight: '8px', animation: 'spin 1s linear infinite' }} />
                        Тестирование...
                      </div>
                    ) : testResult.success ? (
                      <div>
                        <div style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          color: 'var(--mac-success)', 
                          marginBottom: '4px' 
                        }}>
                          <CheckCircle style={{ width: '14px', height: '14px', marginRight: '8px' }} />
                          Тест пройден успешно
                        </div>
                        <div style={{ 
                          fontSize: 'var(--mac-font-size-xs)', 
                          display: 'flex', 
                          flexDirection: 'column', 
                          gap: '4px' 
                        }}>
                          <div style={{ color: 'var(--mac-text-primary)' }}>Время ответа: {testResult.response_time_ms}мс</div>
                          <div style={{ color: 'var(--mac-text-primary)' }}>Токенов: {testResult.tokens_used}</div>
                        </div>
                      </div>
                    ) : (
                      <div style={{ color: 'var(--mac-error)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                          <AlertCircle style={{ width: '14px', height: '14px', marginRight: '8px' }} />
                          Ошибка тестирования
                        </div>
                        <div style={{ fontSize: 'var(--mac-font-size-xs)' }}>{testResult.error_message}</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Действия */}
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditingProvider(provider)}
                  style={{ flex: 1 }}
                >
                  <Edit style={{ width: '14px', height: '14px', marginRight: '8px' }} />
                  Настроить
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTestProvider(provider.id)}
                  disabled={!provider.active || !provider.api_key}
                >
                  <TestTube style={{ width: '14px', height: '14px' }} />
                </Button>
              </div>
            </Card>
          );
        })}

        {/* Карточка добавления нового провайдера */}
        <Card style={{ 
          padding: '24px', 
          border: '2px dashed var(--mac-border)', 
          textAlign: 'center' 
        }}>
          <Brain style={{ width: '48px', height: '48px', margin: '0 auto 16px', color: 'var(--mac-text-tertiary)' }} />
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px',
            margin: 0
          }}>
            Добавить AI провайдера
          </h3>
          <p style={{ 
            color: 'var(--mac-text-secondary)', 
            marginBottom: '16px',
            margin: 0
          }}>
            Настройте новый AI провайдер для использования в системе
          </p>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить
          </Button>
        </Card>
      </div>

      {/* Системные настройки */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '16px', 
          display: 'flex', 
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          <Settings style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
          Системные настройки AI
        </h3>
        
        <SystemSettingsForm 
          settings={systemSettings}
          onSave={(settings) => {
            // Сохранение системных настроек
            logger.log('Сохранение системных настроек:', settings);
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
    <Card style={{ padding: '24px' }}>
      <h3 style={{ 
        fontSize: 'var(--mac-font-size-lg)', 
        fontWeight: 'var(--mac-font-weight-medium)', 
        marginBottom: '16px',
        color: 'var(--mac-text-primary)',
        margin: 0
      }}>
        {provider ? 'Редактирование провайдера' : 'Добавление AI провайдера'}
      </h3>
      
      {/* Быстрые пресеты */}
      {!provider && (
        <div style={{ marginBottom: '24px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Быстрые настройки:
          </label>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
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
      
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Имя провайдера *
            </label>
            <MacOSInput
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="openai, gemini, deepseek"
              style={{ width: '100%' }}
              required
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
              Отображаемое имя *
            </label>
            <MacOSInput
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData(prev => ({ ...prev, display_name: e.target.value }))}
              placeholder="OpenAI GPT-4"
              style={{ width: '100%' }}
              required
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
              <Key style={{ width: '16px', height: '16px', display: 'inline', marginRight: '4px' }} />
              API ключ
            </label>
            <MacOSInput
              type="password"
              value={formData.api_key}
              onChange={(e) => setFormData(prev => ({ ...prev, api_key: e.target.value }))}
              placeholder="sk-..."
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
              Модель
            </label>
            <MacOSInput
              type="text"
              value={formData.model}
              onChange={(e) => setFormData(prev => ({ ...prev, model: e.target.value }))}
              placeholder="gpt-4, gemini-pro"
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
              Температура
            </label>
            <MacOSInput
              type="number"
              min="0"
              max="2"
              step="0.1"
              value={formData.temperature}
              onChange={(e) => setFormData(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
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
              Макс. токенов
            </label>
            <MacOSInput
              type="number"
              min="100"
              max="8000"
              value={formData.max_tokens}
              onChange={(e) => setFormData(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.active}
              onChange={(checked) => setFormData(prev => ({ ...prev, active: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Активен</span>
          </label>
          
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.is_default}
              onChange={(checked) => setFormData(prev => ({ ...prev, is_default: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>По умолчанию</span>
          </label>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <Button type="button" variant="outline" onClick={onCancel}>
            <X style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Отменить
          </Button>
          <Button type="submit">
            <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        <div>
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.enabled || false}
              onChange={(checked) => setFormData(prev => ({ ...prev, enabled: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>AI система включена</span>
          </label>
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.cache_enabled || false}
              onChange={(checked) => setFormData(prev => ({ ...prev, cache_enabled: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Кэширование включено</span>
          </label>
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.require_consent_for_files || false}
              onChange={(checked) => setFormData(prev => ({ ...prev, require_consent_for_files: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Требовать согласие для файлов</span>
          </label>
        </div>

        <div>
          <label style={{ display: 'flex', alignItems: 'center' }}>
            <MacOSCheckbox
              checked={formData.anonymize_data || false}
              onChange={(checked) => setFormData(prev => ({ ...prev, anonymize_data: checked }))}
              style={{ marginRight: '8px' }}
            />
            <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Анонимизировать данные</span>
          </label>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button onClick={() => onSave(formData)}>
          <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
          Сохранить настройки
        </Button>
      </div>
    </div>
  );
};

export default AISettings;

