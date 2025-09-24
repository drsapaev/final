import React, { useState, useEffect } from 'react';
import { Card, Button } from '../ui';
import { Settings, ToggleLeft, ToggleRight, Save, AlertCircle, CheckCircle } from 'lucide-react';
import { toast } from 'react-hot-toast';

const WizardSettings = () => {
  const [settings, setSettings] = useState({
    use_new_wizard: false,
    updated_at: null
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Загрузка настроек
  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/admin/wizard-settings`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error('Ошибка загрузки настроек');
      }

      const data = await response.json();
      setSettings(data);
      setHasChanges(false);
    } catch (error) {
      console.error('Error fetching wizard settings:', error);
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
    try {
      setSaving(true);
      const response = await fetch(`/api/v1/admin/wizard-settings`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          use_new_wizard: settings.use_new_wizard
        })
      });

      if (!response.ok) {
        throw new Error('Ошибка сохранения настроек');
      }

      const data = await response.json();
      
      if (data.success) {
        toast.success(data.message);
        setSettings(data.settings);
        setHasChanges(false);
      } else {
        throw new Error(data.message || 'Ошибка сохранения');
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
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Settings className="h-6 w-6 text-blue-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Настройки мастера регистрации
          </h2>
        </div>
        <Card className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-full"></div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Settings className="h-6 w-6 text-blue-600" />
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Настройки мастера регистрации
        </h2>
      </div>

      <Card className="p-6">
        <div className="space-y-6">
          {/* A/B Переключатель */}
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div className="flex-1">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                Версия мастера регистрации
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                {settings.use_new_wizard 
                  ? 'Используется новый мастер с улучшенным дизайном, корзиной и онлайн-оплатой'
                  : 'Используется классический мастер регистрации'
                }
              </p>
            </div>
            
            <button
              onClick={handleToggleWizard}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200 ${
                settings.use_new_wizard
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-400 dark:hover:bg-gray-500'
              }`}
            >
              {settings.use_new_wizard ? (
                <>
                  <ToggleRight className="h-5 w-5" />
                  Новый мастер
                </>
              ) : (
                <>
                  <ToggleLeft className="h-5 w-5" />
                  Старый мастер
                </>
              )}
            </button>
          </div>

          {/* Информация о версиях */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className={`p-4 border-2 rounded-lg ${
              !settings.use_new_wizard 
                ? 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20' 
                : 'border-gray-200 dark:border-gray-700'
            }`}>
              <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                Классический мастер
              </h4>
              <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                <li>• Проверенная стабильность</li>
                <li>• Привычный интерфейс</li>
                <li>• Базовая функциональность</li>
                <li>• Простая оплата</li>
              </ul>
            </div>

            <div className={`p-4 border-2 rounded-lg ${
              settings.use_new_wizard 
                ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20' 
                : 'border-gray-200 dark:border-gray-700'
            }`}>
              <h4 className="font-medium text-gray-900 dark:text-white mb-2">
                Новый мастер
              </h4>
              <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-1">
                <li>• Windows 11 дизайн</li>
                <li>• Корзина услуг</li>
                <li>• Онлайн-оплата (Click)</li>
                <li>• Автосохранение</li>
                <li>• Горячие клавиши</li>
                <li>• Льготы и повторные визиты</li>
              </ul>
            </div>
          </div>

          {/* Предупреждение */}
          {hasChanges && (
            <div className="flex items-center gap-3 p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
              <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                Изменения не сохранены. Нажмите "Сохранить" для применения настроек.
              </p>
            </div>
          )}

          {/* Информация об обновлении */}
          {settings.updated_at && (
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Последнее обновление: {new Date(settings.updated_at).toLocaleString('ru-RU')}
            </div>
          )}

          {/* Кнопки действий */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
            <Button
              variant="outline"
              onClick={fetchSettings}
              disabled={saving}
            >
              Отменить
            </Button>
            
            <Button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="flex items-center gap-2"
            >
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  Сохранение...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  Сохранить
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default WizardSettings;
