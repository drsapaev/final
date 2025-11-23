import React, { useState, useEffect } from 'react';
import { 
  Settings, 
  Save, 
  RefreshCw, 
  Calendar, 
  Percent, 
  CheckCircle, 
  AlertCircle,
  Info,
  Clock,
  DollarSign,
  Shield
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput,
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSBadge,
  MacOSModal,
  MacOSStatCard
} from '../ui/macos';
import { toast } from 'react-toastify';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

/**
 * Компонент для управления настройками льгот в админке
 */
const BenefitSettings = () => {
  const [settings, setSettings] = useState({
    repeat_visit_days: 21,
    repeat_visit_discount: 0,
    benefit_consultation_free: true,
    all_free_auto_approve: false
  });
  const [originalSettings, setOriginalSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/admin/benefit-settings`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
        setOriginalSettings(data);
        setLastUpdated(new Date(data.updated_at));
      } else {
        setError('Не удалось загрузить настройки льгот. Проверьте подключение к серверу.');
        // Fallback данные при ошибке
        const fallbackData = {
          repeat_visit_days: 21,
          repeat_visit_discount: 0,
          benefit_consultation_free: true,
          all_free_auto_approve: false,
          updated_at: new Date().toISOString()
        };
        setSettings(fallbackData);
        setOriginalSettings(fallbackData);
        setLastUpdated(new Date());
        toast.error('Ошибка загрузки настроек льгот');
      }
    } catch (error) {
      console.error('Error loading benefit settings:', error);
      setError('Не удалось загрузить настройки льгот. Проверьте подключение к серверу.');
      // Fallback данные при ошибке
      const fallbackData = {
        repeat_visit_days: 21,
        repeat_visit_discount: 0,
        benefit_consultation_free: true,
        all_free_auto_approve: false,
        updated_at: new Date().toISOString()
      };
      setSettings(fallbackData);
      setOriginalSettings(fallbackData);
      setLastUpdated(new Date());
      toast.error('Ошибка загрузки настроек льгот');
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setShowConfirmModal(true);
  };

  const confirmSave = async () => {
    setSaving(true);
    setShowConfirmModal(false);
    try {
      const response = await fetch(`${API_BASE}/admin/benefit-settings`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        const result = await response.json();
        toast.success(result.message);
        setOriginalSettings(settings);
        setLastUpdated(new Date());
      } else {
        const errorData = await response.json();
        toast.error(errorData.detail || 'Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Error saving benefit settings:', error);
      toast.error('Ошибка сохранения настроек');
    } finally {
      setSaving(false);
    }
  };

  const resetSettings = () => {
    setSettings(originalSettings);
  };

  const hasChanges = () => {
    return JSON.stringify(settings) !== JSON.stringify(originalSettings);
  };

  const handleInputChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  if (loading) {
    return (
      <div style={{ 
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)',
        minHeight: '100vh'
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <Settings style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Настройки льгот
            </h2>
          </div>
          <MacOSLoadingSkeleton height="600px" />
        </MacOSCard>
      </div>
    );
  }

  // Критическая ошибка загрузки
  if (error && !settings.updated_at) {
    return (
      <div style={{ 
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)',
        minHeight: '100vh'
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <Settings style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Настройки льгот
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertCircle}
            title="Не удалось загрузить настройки"
            description="Проверьте подключение к серверу и попробуйте обновить страницу"
            action={
              <MacOSButton onClick={loadSettings} variant="primary">
                <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Попробовать снова
              </MacOSButton>
            }
          />
        </MacOSCard>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Критическая ошибка */}
          {error && (
            <MacOSAlert
              type="error"
              title="Ошибка загрузки"
              message={error}
              onClose={() => setError(null)}
            />
          )}

          {/* Header */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            paddingBottom: '24px',
            borderBottom: '1px solid var(--mac-border)',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div>
              <h2 style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <Settings style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
                Настройки льгот
              </h2>
              <p style={{ 
                color: 'var(--mac-text-secondary)',
                fontSize: 'var(--mac-font-size-sm)',
                margin: 0
              }}>
                Управление параметрами льгот и повторных визитов
              </p>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              {lastUpdated && (
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-tertiary)' 
                }}>
                  Обновлено: {lastUpdated.toLocaleDateString('ru-RU')} в {lastUpdated.toLocaleTimeString('ru-RU')}
                </div>
              )}
              
              <MacOSButton
                onClick={loadSettings}
                disabled={loading}
                variant="outline"
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  padding: '8px 16px'
                }}
              >
                <RefreshCw style={{ 
                  width: '16px', 
                  height: '16px',
                  animation: loading ? 'spin 1s linear infinite' : 'none'
                }} />
                Обновить
              </MacOSButton>
            </div>
          </div>

          {/* Настройки */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
            gap: '24px' 
          }}>
            {/* Повторные визиты */}
            <MacOSCard style={{ 
              padding: '24px',
              transition: 'all 0.3s ease-in-out',
              transform: settings.repeat_visit_discount > 0 ? 'scale(1.02)' : 'scale(1)'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px', 
                marginBottom: '20px' 
              }}>
                <div style={{ 
                  padding: '8px', 
                  backgroundColor: 'var(--mac-success-bg)', 
                  borderRadius: 'var(--mac-radius-md)' 
                }}>
                  <Calendar style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <h3 style={{ 
                      fontSize: 'var(--mac-font-size-lg)', 
                      fontWeight: 'var(--mac-font-weight-semibold)', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      Повторные визиты
                    </h3>
                    <MacOSBadge 
                      variant={settings.repeat_visit_discount > 0 ? "success" : "secondary"}
                      size="sm"
                    >
                      {settings.repeat_visit_discount > 0 ? "Активны" : "Неактивны"}
                    </MacOSBadge>
                  </div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    Настройки для повторных консультаций
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Окно повторного визита */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Окно повторного визита (дней)
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Clock style={{ 
                        width: '16px', 
                        height: '16px', 
                        position: 'absolute',
                        left: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: 'var(--mac-text-tertiary)'
                      }} />
                      <MacOSInput
                        type="number"
                        min="1"
                        max="365"
                        value={settings.repeat_visit_days}
                        onChange={(e) => handleInputChange('repeat_visit_days', parseInt(e.target.value) || 21)}
                        placeholder="21"
                        style={{ 
                          width: '100%', 
                          paddingLeft: '40px',
                          paddingRight: '12px'
                        }}
                      />
                    </div>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-tertiary)' 
                    }}>
                      дней
                    </span>
                  </div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-tertiary)', 
                    marginTop: '4px',
                    margin: '4px 0 0 0'
                  }}>
                    Период, в течение которого консультация считается повторной
                  </p>
                </div>

                {/* Скидка на повторный визит */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '8px' 
                  }}>
                    Скидка на повторный визит (%)
                  </label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ position: 'relative', flex: 1 }}>
                      <Percent style={{ 
                        width: '16px', 
                        height: '16px', 
                        position: 'absolute',
                        left: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        color: 'var(--mac-text-tertiary)'
                      }} />
                      <MacOSInput
                        type="number"
                        min="0"
                        max="100"
                        value={settings.repeat_visit_discount}
                        onChange={(e) => handleInputChange('repeat_visit_discount', parseInt(e.target.value) || 0)}
                        placeholder="0"
                        style={{ 
                          width: '100%', 
                          paddingLeft: '40px',
                          paddingRight: '12px'
                        }}
                      />
                    </div>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-tertiary)' 
                    }}>
                      %
                    </span>
                  </div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-tertiary)', 
                    marginTop: '4px',
                    margin: '4px 0 0 0'
                  }}>
                    0% = бесплатно, 50% = половина цены, 100% = полная цена
                  </p>
                </div>

                {/* Информационная карточка */}
                <MacOSCard style={{ 
                  padding: '16px', 
                  backgroundColor: 'var(--mac-accent-bg)', 
                  border: '1px solid var(--mac-accent-border)' 
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <Info style={{ 
                      width: '16px', 
                      height: '16px', 
                      color: 'var(--mac-accent-blue)',
                      marginTop: '2px',
                      flexShrink: 0
                    }} />
                    <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-accent-blue)' }}>
                      <p style={{ 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        margin: '0 0 8px 0' 
                      }}>
                        Как работают повторные визиты:
                      </p>
                      <ul style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        margin: 0,
                        paddingLeft: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px'
                      }}>
                        <li>• Проверяется наличие консультации у того же врача</li>
                        <li>• В течение указанного периода (дней)</li>
                        <li>• Применяется указанная скидка</li>
                      </ul>
                    </div>
                  </div>
                </MacOSCard>
              </div>
            </MacOSCard>

            {/* Льготные визиты */}
            <MacOSCard style={{ 
              padding: '24px',
              transition: 'all 0.3s ease-in-out',
              transform: settings.benefit_consultation_free ? 'scale(1.02)' : 'scale(1)'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px', 
                marginBottom: '20px' 
              }}>
                <div style={{ 
                  padding: '8px', 
                  backgroundColor: 'var(--mac-warning-bg)', 
                  borderRadius: 'var(--mac-radius-md)' 
                }}>
                  <Shield style={{ width: '20px', height: '20px', color: 'var(--mac-warning)' }} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <h3 style={{ 
                      fontSize: 'var(--mac-font-size-lg)', 
                      fontWeight: 'var(--mac-font-weight-semibold)', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      Льготные визиты
                    </h3>
                    <MacOSBadge 
                      variant={settings.benefit_consultation_free ? "success" : "warning"}
                      size="sm"
                    >
                      {settings.benefit_consultation_free ? "Бесплатно" : "Платно"}
                    </MacOSBadge>
                  </div>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    Настройки для льготных категорий пациентов
                  </p>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Льготные консультации бесплатны */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <MacOSCheckbox
                      checked={settings.benefit_consultation_free}
                      onChange={(checked) => handleInputChange('benefit_consultation_free', checked)}
                    />
                    <div>
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)',
                        display: 'block',
                        marginBottom: '4px'
                      }}>
                        Льготные консультации бесплатны
                      </span>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-tertiary)',
                        margin: 0
                      }}>
                        Консультации специалистов для льготных категорий
                      </p>
                    </div>
                  </div>
                </div>

                {/* Автоодобрение All Free */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <MacOSCheckbox
                      checked={settings.all_free_auto_approve}
                      onChange={(checked) => handleInputChange('all_free_auto_approve', checked)}
                    />
                    <div>
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)',
                        display: 'block',
                        marginBottom: '4px'
                      }}>
                        Автоодобрение заявок "All Free"
                      </span>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-tertiary)',
                        margin: 0
                      }}>
                        Автоматически одобрять все заявки на бесплатные услуги
                      </p>
                    </div>
                  </div>
                </div>

                {/* Предупреждение об автоодобрении */}
                {settings.all_free_auto_approve && (
                  <MacOSCard style={{ 
                    padding: '16px', 
                    backgroundColor: 'var(--mac-warning-bg)', 
                    border: '1px solid var(--mac-warning-border)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                      <AlertCircle style={{ 
                        width: '16px', 
                        height: '16px', 
                        color: 'var(--mac-warning)',
                        marginTop: '2px',
                        flexShrink: 0
                      }} />
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-warning)' }}>
                        <p style={{ 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          margin: '0 0 4px 0' 
                        }}>
                          Внимание!
                        </p>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-xs)', 
                          margin: 0 
                        }}>
                          При включении автоодобрения все заявки "All Free" будут одобряться без проверки администратора.
                        </p>
                      </div>
                    </div>
                  </MacOSCard>
                )}

                {/* Информационная карточка */}
                <MacOSCard style={{ 
                  padding: '16px', 
                  backgroundColor: 'var(--mac-warning-bg)', 
                  border: '1px solid var(--mac-warning-border)' 
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <Info style={{ 
                      width: '16px', 
                      height: '16px', 
                      color: 'var(--mac-warning)',
                      marginTop: '2px',
                      flexShrink: 0
                    }} />
                    <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-warning)' }}>
                      <p style={{ 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        margin: '0 0 8px 0' 
                      }}>
                        Типы льгот:
                      </p>
                      <ul style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        margin: 0,
                        paddingLeft: '16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px'
                      }}>
                        <li>• <strong>Льготный</strong> - обычно только консультации</li>
                        <li>• <strong>All Free</strong> - любые услуги (требует одобрения)</li>
                      </ul>
                    </div>
                  </div>
                </MacOSCard>
              </div>
            </MacOSCard>
          </div>

          {/* Действия */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            paddingTop: '24px', 
            borderTop: '1px solid var(--mac-border)',
            flexWrap: 'wrap',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {hasChanges() && (
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  padding: '6px 12px',
                  backgroundColor: 'var(--mac-warning-bg)',
                  border: '1px solid var(--mac-warning-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-warning)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>
                  <AlertCircle style={{ width: '14px', height: '14px' }} />
                  Есть несохранённые изменения
                </div>
              )}
            </div>
            
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              {hasChanges() && (
                <MacOSButton
                  onClick={resetSettings}
                  variant="outline"
                  disabled={saving}
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    padding: '8px 16px'
                  }}
                >
                  Отменить
                </MacOSButton>
              )}
              
              <MacOSButton
                onClick={saveSettings}
                disabled={saving || !hasChanges()}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none',
                  padding: '8px 16px'
                }}
              >
                {saving ? (
                  <RefreshCw style={{ 
                    width: '16px', 
                    height: '16px',
                    animation: 'spin 1s linear infinite'
                  }} />
                ) : (
                  <Save style={{ width: '16px', height: '16px' }} />
                )}
                {saving ? 'Сохранение...' : 'Сохранить настройки'}
              </MacOSButton>
            </div>
          </div>

          {/* Статистика настроек */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px' 
          }}>
            <MacOSStatCard
              title="Окно повторных визитов"
              value={`${settings.repeat_visit_days} дней`}
              icon={Calendar}
              color="var(--mac-success)"
              trend={settings.repeat_visit_discount > 0 ? "Скидка активна" : "Скидка неактивна"}
              trendColor={settings.repeat_visit_discount > 0 ? "var(--mac-success)" : "var(--mac-text-secondary)"}
            />
            
            <MacOSStatCard
              title="Скидка на повторные визиты"
              value={`${settings.repeat_visit_discount}%`}
              icon={Percent}
              color={settings.repeat_visit_discount > 0 ? "var(--mac-success)" : "var(--mac-warning)"}
              trend={settings.repeat_visit_discount > 0 ? "Применяется" : "Не применяется"}
              trendColor={settings.repeat_visit_discount > 0 ? "var(--mac-success)" : "var(--mac-warning)"}
            />
            
            <MacOSStatCard
              title="Льготные консультации"
              value={settings.benefit_consultation_free ? "Бесплатно" : "Платно"}
              icon={Shield}
              color={settings.benefit_consultation_free ? "var(--mac-success)" : "var(--mac-warning)"}
              trend={settings.benefit_consultation_free ? "Активны" : "Неактивны"}
              trendColor={settings.benefit_consultation_free ? "var(--mac-success)" : "var(--mac-warning)"}
            />
            
            <MacOSStatCard
              title="Автоодобрение All Free"
              value={settings.all_free_auto_approve ? "Включено" : "Выключено"}
              icon={CheckCircle}
              color={settings.all_free_auto_approve ? "var(--mac-warning)" : "var(--mac-info)"}
              trend={settings.all_free_auto_approve ? "Автоматически" : "Вручную"}
              trendColor={settings.all_free_auto_approve ? "var(--mac-warning)" : "var(--mac-info)"}
            />
          </div>

          {/* Предварительный просмотр */}
          <MacOSCard style={{ 
            padding: '20px', 
            backgroundColor: 'var(--mac-bg-secondary)' 
          }}>
            <h4 style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Текущие настройки:
            </h4>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
              gap: '16px',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Calendar style={{ width: '14px', height: '14px', color: 'var(--mac-text-tertiary)' }} />
                <span style={{ color: 'var(--mac-text-secondary)' }}>
                  Окно: {settings.repeat_visit_days} дней
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <DollarSign style={{ width: '14px', height: '14px', color: 'var(--mac-text-tertiary)' }} />
                <span style={{ color: 'var(--mac-text-secondary)' }}>
                  Скидка: {settings.repeat_visit_discount}%
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle style={{ 
                  width: '14px', 
                  height: '14px', 
                  color: settings.benefit_consultation_free ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' 
                }} />
                <span style={{ color: 'var(--mac-text-secondary)' }}>
                  Льготы: {settings.benefit_consultation_free ? 'Бесплатно' : 'Платно'}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Shield style={{ 
                  width: '14px', 
                  height: '14px', 
                  color: settings.all_free_auto_approve ? 'var(--mac-warning)' : 'var(--mac-text-tertiary)' 
                }} />
                <span style={{ color: 'var(--mac-text-secondary)' }}>
                  All Free: {settings.all_free_auto_approve ? 'Автоодобрение' : 'Ручное одобрение'}
                </span>
              </div>
            </div>
          </MacOSCard>
        </div>
      </MacOSCard>

      {/* Модальное окно подтверждения */}
      <MacOSModal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="Подтверждение изменений"
        size="sm"
      >
        <div style={{ padding: '24px' }}>
          <p style={{ 
            fontSize: 'var(--mac-font-size-base)', 
            color: 'var(--mac-text-primary)',
            marginBottom: '24px',
            lineHeight: '1.5'
          }}>
            Вы собираетесь сохранить изменения в настройках льгот. 
            Это повлияет на всех пользователей системы.
          </p>
          
          <div style={{ 
            display: 'flex', 
            justifyContent: 'flex-end', 
            gap: '12px' 
          }}>
            <MacOSButton
              variant="outline"
              onClick={() => setShowConfirmModal(false)}
              disabled={saving}
            >
              Отмена
            </MacOSButton>
            <MacOSButton
              onClick={confirmSave}
              disabled={saving}
              style={{ 
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none'
              }}
            >
              {saving ? (
                <>
                  <RefreshCw style={{ 
                    width: '16px', 
                    height: '16px',
                    animation: 'spin 1s linear infinite',
                    marginRight: '8px'
                  }} />
                  Сохранение...
                </>
              ) : (
                <>
                  <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Подтвердить
                </>
              )}
            </MacOSButton>
          </div>
        </div>
      </MacOSModal>
    </div>
  );
};

export default BenefitSettings;

