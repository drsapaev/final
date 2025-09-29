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
import { Card, Badge, Button } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

const API_BASE = (import.meta?.env?.VITE_API_BASE || 'http://localhost:8000/api/v1');

/**
 * Компонент для управления настройками льгот в админке
 */
const BenefitSettings = () => {
  const { theme, getColor } = useTheme();
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
        toast.error('Ошибка загрузки настроек льгот');
      }
    } catch (error) {
      console.error('Error loading benefit settings:', error);
      toast.error('Ошибка загрузки настроек льгот');
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
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
      <Card className="p-6">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
          <p className="text-gray-500 mt-2">Загрузка настроек...</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <Settings size={24} className="text-blue-600" />
              Настройки льгот
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Управление параметрами льгот и повторных визитов
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {lastUpdated && (
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Обновлено: {lastUpdated.toLocaleDateString('ru-RU')} в {lastUpdated.toLocaleTimeString('ru-RU')}
              </div>
            )}
            
            <Button
              onClick={loadSettings}
              disabled={loading}
              variant="outline"
              className="flex items-center gap-2"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Обновить
            </Button>
          </div>
        </div>

        {/* Настройки */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Повторные визиты */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-green-100 rounded-lg">
                <Calendar size={20} className="text-green-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Повторные визиты
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Настройки для повторных консультаций
                </p>
              </div>
            </div>

            <div className="space-y-4">
              {/* Окно повторного визита */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Окно повторного визита (дней)
                </label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1">
                    <Clock size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={settings.repeat_visit_days}
                      onChange={(e) => handleInputChange('repeat_visit_days', parseInt(e.target.value) || 21)}
                      className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    />
                  </div>
                  <span className="text-sm text-gray-500">дней</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Период, в течение которого консультация считается повторной
                </p>
              </div>

              {/* Скидка на повторный визит */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Скидка на повторный визит (%)
                </label>
                <div className="flex items-center gap-3">
                  <div className="relative flex-1">
                    <Percent size={16} className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={settings.repeat_visit_discount}
                      onChange={(e) => handleInputChange('repeat_visit_discount', parseInt(e.target.value) || 0)}
                      className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    />
                  </div>
                  <span className="text-sm text-gray-500">%</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  0% = бесплатно, 50% = половина цены, 100% = полная цена
                </p>
              </div>

              {/* Информационная карточка */}
              <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                <div className="flex items-start gap-2">
                  <Info size={16} className="text-blue-600 mt-0.5" />
                  <div className="text-sm text-blue-800 dark:text-blue-200">
                    <p className="font-medium mb-1">Как работают повторные визиты:</p>
                    <ul className="text-xs space-y-1">
                      <li>• Проверяется наличие консультации у того же врача</li>
                      <li>• В течение указанного периода (дней)</li>
                      <li>• Применяется указанная скидка</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Льготные визиты */}
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-orange-100 rounded-lg">
                <Shield size={20} className="text-orange-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Льготные визиты
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Настройки для льготных категорий пациентов
                </p>
              </div>
            </div>

            <div className="space-y-4">
              {/* Льготные консультации бесплатны */}
              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.benefit_consultation_free}
                    onChange={(e) => handleInputChange('benefit_consultation_free', e.target.checked)}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Льготные консультации бесплатны
                    </span>
                    <p className="text-xs text-gray-500">
                      Консультации специалистов для льготных категорий
                    </p>
                  </div>
                </label>
              </div>

              {/* Автоодобрение All Free */}
              <div>
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={settings.all_free_auto_approve}
                    onChange={(e) => handleInputChange('all_free_auto_approve', e.target.checked)}
                    className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Автоодобрение заявок "All Free"
                    </span>
                    <p className="text-xs text-gray-500">
                      Автоматически одобрять все заявки на бесплатные услуги
                    </p>
                  </div>
                </label>
              </div>

              {/* Предупреждение об автоодобрении */}
              {settings.all_free_auto_approve && (
                <div className="bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded-lg">
                  <div className="flex items-start gap-2">
                    <AlertCircle size={16} className="text-yellow-600 mt-0.5" />
                    <div className="text-sm text-yellow-800 dark:text-yellow-200">
                      <p className="font-medium">Внимание!</p>
                      <p className="text-xs mt-1">
                        При включении автоодобрения все заявки "All Free" будут одобряться без проверки администратора.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Информационная карточка */}
              <div className="bg-orange-50 dark:bg-orange-900/20 p-3 rounded-lg">
                <div className="flex items-start gap-2">
                  <Info size={16} className="text-orange-600 mt-0.5" />
                  <div className="text-sm text-orange-800 dark:text-orange-200">
                    <p className="font-medium mb-1">Типы льгот:</p>
                    <ul className="text-xs space-y-1">
                      <li>• <strong>Льготный</strong> - обычно только консультации</li>
                      <li>• <strong>All Free</strong> - любые услуги (требует одобрения)</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Действия */}
        <div className="flex items-center justify-between pt-6 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            {hasChanges() && (
              <Badge variant="warning" className="flex items-center gap-1">
                <AlertCircle size={14} />
                Есть несохранённые изменения
              </Badge>
            )}
          </div>
          
          <div className="flex gap-3">
            {hasChanges() && (
              <Button
                onClick={resetSettings}
                variant="outline"
                disabled={saving}
              >
                Отменить
              </Button>
            )}
            
            <Button
              onClick={saveSettings}
              disabled={saving || !hasChanges()}
              className="flex items-center gap-2"
            >
              {saving ? (
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              ) : (
                <Save size={16} />
              )}
              {saving ? 'Сохранение...' : 'Сохранить настройки'}
            </Button>
          </div>
        </div>

        {/* Предварительный просмотр */}
        <Card className="p-4 bg-gray-50 dark:bg-gray-800">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Текущие настройки:
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Calendar size={14} className="text-gray-500" />
              <span>Окно: {settings.repeat_visit_days} дней</span>
            </div>
            <div className="flex items-center gap-2">
              <DollarSign size={14} className="text-gray-500" />
              <span>Скидка: {settings.repeat_visit_discount}%</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle size={14} className={settings.benefit_consultation_free ? 'text-green-500' : 'text-gray-400'} />
              <span>Льготы: {settings.benefit_consultation_free ? 'Бесплатно' : 'Платно'}</span>
            </div>
            <div className="flex items-center gap-2">
              <Shield size={14} className={settings.all_free_auto_approve ? 'text-orange-500' : 'text-gray-400'} />
              <span>All Free: {settings.all_free_auto_approve ? 'Автоодобрение' : 'Ручное одобрение'}</span>
            </div>
          </div>
        </Card>
      </div>
    </Card>
  );
};

export default BenefitSettings;

