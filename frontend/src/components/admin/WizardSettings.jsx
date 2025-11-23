import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSCheckbox,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert,
  MacOSBadge,
  MacOSModal,
  MacOSStatCard,
  MacOSInput,
  MacOSSelect,
  MacOSTab
} from '../ui/macos';
import { Settings, ToggleLeft, ToggleRight, Save, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

const WizardSettings = () => {
  const [settings, setSettings] = useState({
    use_new_wizard: false,
    updated_at: null
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [error, setError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // Загрузка настроек
  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/wizard-settings');
      setSettings(response.data);
      setHasChanges(false);
    } catch (error) {
      console.error('Error fetching wizard settings:', error);
      setError('Не удалось загрузить настройки мастера. Проверьте подключение к серверу.');
      // Fallback данные при ошибке
      setSettings({
        use_new_wizard: false,
        updated_at: new Date().toISOString()
      });
      setHasChanges(false);
      toast.error('Ошибка загрузки настроек мастера');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleWizard = () => {
    setSettings(prev => ({
      ...prev,
      use_new_wizard: !prev.use_new_wizard
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setShowConfirmModal(true);
  };

  const confirmSave = async () => {
    try {
      setSaving(true);
      setShowConfirmModal(false);
      const response = await api.post('/admin/wizard-settings', {
        use_new_wizard: settings.use_new_wizard
      });
      
      if (response.data.success) {
        toast.success(response.data.message);
        setSettings(response.data.settings);
        setHasChanges(false);
      } else {
        throw new Error(response.data.message || 'Ошибка сохранения');
      }
    } catch (error) {
      console.error('Error saving wizard settings:', error);
      toast.error('Ошибка сохранения настроек');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <MacOSCard style={{ 
        padding: '24px',
        backgroundColor: 'var(--mac-bg-primary)',
        minHeight: '100vh'
      }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            marginBottom: '24px' 
          }}>
            <Settings style={{ 
              width: '32px', 
              height: '32px', 
              color: 'var(--mac-accent-blue)' 
            }} />
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Настройки мастера регистрации
            </h2>
          </div>
          <MacOSLoadingSkeleton height="400px" />
      </MacOSCard>
    );
  }

  // Критическая ошибка загрузки
  if (error && !settings.updated_at) {
    return (
      <MacOSCard style={{ 
        padding: '24px',
        backgroundColor: 'var(--mac-bg-primary)',
        minHeight: '100vh'
      }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            marginBottom: '24px' 
          }}>
            <Settings style={{ 
              width: '32px', 
              height: '32px', 
              color: 'var(--mac-accent-blue)' 
            }} />
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Настройки мастера регистрации
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertCircle}
            title="Не удалось загрузить настройки"
            description="Проверьте подключение к серверу и попробуйте обновить страницу"
            action={
              <MacOSButton onClick={fetchSettings} variant="primary">
                <RefreshCw style={{ 
                  width: '16px', 
                  height: '16px', 
                  marginRight: '4px' 
                }} />
                Попробовать снова
              </MacOSButton>
            }
          />
      </MacOSCard>
    );
  }

  return (
    <MacOSCard style={{ 
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '8px', 
        marginBottom: '24px',
        flexWrap: 'wrap'
      }}>
          <Settings style={{ 
            width: '32px', 
            height: '32px', 
            color: 'var(--mac-accent-blue)' 
          }} />
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            flex: 1,
            minWidth: '200px'
          }}>
            Настройки мастера регистрации
          </h2>

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

          {/* A/B Переключатель */}
          <MacOSCard style={{ 
            padding: '24px', 
            backgroundColor: 'var(--mac-bg-secondary)',
            border: '1px solid var(--mac-border)'
          }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between',
              marginBottom: '16px'
            }}>
              <div style={{ flex: 1 }}>
                <h3 style={{ 
                  fontSize: 'var(--mac-font-size-lg)', 
                  fontWeight: 'var(--mac-font-weight-semibold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 4px 0'
                }}>
                  Версия мастера регистрации
                </h3>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  {settings.use_new_wizard 
                    ? 'Используется новый мастер с улучшенным дизайном, корзиной и онлайн-оплатой'
                    : 'Используется классический мастер регистрации'
                  }
                </p>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MacOSCheckbox
                  checked={settings.use_new_wizard}
                  onChange={handleToggleWizard}
                />
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: settings.use_new_wizard ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                }}>
                  {settings.use_new_wizard ? 'Новый мастер' : 'Старый мастер'}
                </span>
              </div>
            </div>
          </MacOSCard>

          {/* Статистика использования */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px' 
          }}>
            <MacOSStatCard
              title="Использование нового мастера"
              value={settings.use_new_wizard ? "100%" : "0%"}
              icon={settings.use_new_wizard ? CheckCircle : AlertCircle}
              color={settings.use_new_wizard ? "var(--mac-success)" : "var(--mac-warning)"}
              trend={settings.use_new_wizard ? "Активен" : "Неактивен"}
              trendColor={settings.use_new_wizard ? "var(--mac-success)" : "var(--mac-warning)"}
            />
            
            <MacOSStatCard
              title="Последнее обновление"
              value={settings.updated_at ? new Date(settings.updated_at).toLocaleDateString('ru-RU') : "Неизвестно"}
              icon={RefreshCw}
              color="var(--mac-info)"
              trend="Настройки"
              trendColor="var(--mac-text-secondary)"
            />
          </div>

          {/* Информация о версиях */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '16px' 
          }}>
            <MacOSCard style={{ 
              padding: '24px',
              border: !settings.use_new_wizard ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
              backgroundColor: !settings.use_new_wizard ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              transform: !settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px', 
                marginBottom: '8px' 
              }}>
                <h4 style={{ 
                  fontSize: 'var(--mac-font-size-lg)', 
                  fontWeight: 'var(--mac-font-weight-semibold)', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  Классический мастер
                </h4>
                <MacOSBadge 
                  variant={!settings.use_new_wizard ? "primary" : "secondary"}
                  size="sm"
                >
                  {!settings.use_new_wizard ? "Активен" : "Неактивен"}
                </MacOSBadge>
              </div>
              <ul style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)', 
                margin: 0,
                paddingLeft: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}>
                <li>• Проверенная стабильность</li>
                <li>• Привычный интерфейс</li>
                <li>• Базовая функциональность</li>
                <li>• Простая оплата</li>
              </ul>
            </MacOSCard>

            <MacOSCard style={{ 
              padding: '24px',
              border: settings.use_new_wizard ? '2px solid var(--mac-success)' : '1px solid var(--mac-border)',
              backgroundColor: settings.use_new_wizard ? 'var(--mac-success-bg)' : 'var(--mac-bg-primary)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              transform: settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)'
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px', 
                marginBottom: '8px' 
              }}>
                <h4 style={{ 
                  fontSize: 'var(--mac-font-size-lg)', 
                  fontWeight: 'var(--mac-font-weight-semibold)', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  Новый мастер
                </h4>
                <MacOSBadge 
                  variant={settings.use_new_wizard ? "success" : "secondary"}
                  size="sm"
                >
                  {settings.use_new_wizard ? "Активен" : "Неактивен"}
                </MacOSBadge>
              </div>
              <ul style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)', 
                margin: 0,
                paddingLeft: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px'
              }}>
                <li>• macOS дизайн</li>
                <li>• Корзина услуг</li>
                <li>• Онлайн-оплата (Click)</li>
                <li>• Автосохранение</li>
                <li>• Горячие клавиши</li>
                <li>• Льготы и повторные визиты</li>
              </ul>
            </MacOSCard>
          </div>

          {/* Предупреждение */}
          {hasChanges && (
            <MacOSCard style={{ 
              padding: '16px', 
              backgroundColor: 'var(--mac-warning-bg)', 
              border: '1px solid var(--mac-warning-border)' 
            }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px' 
              }}>
                <AlertCircle style={{ 
                  width: '20px', 
                  height: '20px', 
                  color: 'var(--mac-warning)',
                  flexShrink: 0
                }} />
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-warning)',
                  margin: 0,
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>
                  Изменения не сохранены. Нажмите "Сохранить" для применения настроек.
                </p>
              </div>
            </MacOSCard>
          )}

          {/* Информация об обновлении */}
          {settings.updated_at && (
            <div style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-text-tertiary)',
              textAlign: 'center',
              padding: '8px 0'
            }}>
              Последнее обновление: {new Date(settings.updated_at).toLocaleString('ru-RU')}
            </div>
          )}

          {/* Кнопки действий */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'flex-end', 
            gap: '8px', 
            paddingTop: '16px', 
            borderTop: '1px solid var(--mac-border)',
            flexWrap: 'wrap'
          }}>
            <MacOSButton
              variant="outline"
              onClick={fetchSettings}
              disabled={saving}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px',
                padding: '4px 16px',
                minWidth: '120px'
              }}
            >
              Отменить
            </MacOSButton>
            
            <MacOSButton
              onClick={handleSave}
              disabled={!hasChanges || saving}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '4px 16px',
                minWidth: '120px'
              }}
            >
              {saving ? (
                <>
                  <RefreshCw style={{ 
                    width: '16px', 
                    height: '16px',
                    animation: 'spin 1s linear infinite'
                  }} />
                  Сохранение...
                </>
              ) : (
                <>
                  <Save style={{ width: '16px', height: '16px' }} />
                  Сохранить
                </>
              )}
            </MacOSButton>
          </div>
        </div>
      </div>

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
            lineHeight: 'var(--mac-line-height-relaxed)'
          }}>
            Вы собираетесь {settings.use_new_wizard ? 'включить' : 'отключить'} новый мастер регистрации. 
            Это изменение повлияет на всех пользователей системы.
          </p>
          
          <div style={{ 
            display: 'flex', 
            justifyContent: 'flex-end', 
            gap: 'var(--mac-spacing-sm)' 
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
                    marginRight: '4px'
                  }} />
                  Сохранение...
                </>
              ) : (
                <>
                  <Save style={{ 
                    width: '16px', 
                    height: '16px', 
                    marginRight: '4px' 
                  }} />
                  Подтвердить
                </>
              )}
            </MacOSButton>
          </div>
        </div>
      </MacOSModal>
    </MacOSCard>
  );
};

export default WizardSettings;

