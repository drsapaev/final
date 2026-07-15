import { useState, useEffect } from 'react';
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
  Button,
  Input,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
  MacOSStatCard,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { fetchBenefitSettings, saveBenefitSettings } from '../../api/adminSettings';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/adapter';
/**
 * Компонент для управления настройками льгот в админке
 */
const BenefitSettings = () => {
  const { t } = useTranslation();
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
      const data = await fetchBenefitSettings();
      setSettings(data);
      setOriginalSettings(data);
      setLastUpdated(new Date(data.updated_at));
    } catch (error) {
      logger.error('Error loading benefit settings:', error);
      setError(error.response?.data?.detail || 'Не удалось загрузить настройки льгот. Проверьте подключение к серверу.');
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
      const response = await saveBenefitSettings(settings);
      toast.success(response?.message || 'Настройки сохранены');
      setOriginalSettings(settings);
      setLastUpdated(new Date());
    } catch (error) {
      logger.error('Error saving benefit settings:', error);
      toast.error(error.response?.data?.detail || 'Ошибка сохранения настроек');
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
      <div className="admin-benefit-container">
        <MacOSCard className="p-6">
          <div className="admin-flex-center-12 mb-6">
            <Settings className="admin-icon-32-blue" />
            <h2 className="admin-benefit-h2">
              Настройки льгот
            </h2>
          </div>
          <Skeleton height="600px" />
        </MacOSCard>
      </div>
    );
  }

  // Критическая ошибка загрузки
  if (error && !settings.updated_at) {
    return (
      <div className="admin-benefit-container">
        <MacOSCard className="p-6">
          <div className="admin-flex-center-12 mb-6">
            <Settings className="admin-icon-32-blue" />
            <h2 className="admin-benefit-h2">
              Настройки льгот
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertCircle}
            title="Не удалось загрузить настройки"
            description="Проверьте подключение к серверу и попробуйте обновить страницу"
            action={
              <Button onClick={loadSettings} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                Попробовать снова
              </Button>
            }
          />
        </MacOSCard>
      </div>
    );
  }

  return (
    <div className="admin-benefit-container">
      <MacOSCard className="p-6">
        <div className="flex flex-col gap-6">
          {/* Критическая ошибка */}
          {error && (
            <Alert
              type="error"
              title="Ошибка загрузки"
              message={error}
              onClose={() => setError(null)}
            />
          )}

          {/* Header */}
          <div className="admin-benefit-header">
            <div>
              <h2 className="admin-benefit-h2-with-icon">
                <Settings className="admin-icon-32-blue" />
                Настройки льгот
              </h2>
              <p className="admin-setting-desc">
                Управление параметрами льгот и повторных визитов
              </p>
            </div>

            <div className="admin-flex-center-16">
              {lastUpdated && (
                <div className="admin-benefit-updated">
                  Обновлено: {lastUpdated.toLocaleDateString('ru-RU')} в {lastUpdated.toLocaleTimeString('ru-RU')}
                </div>
              )}

              <Button
                onClick={loadSettings}
                disabled={loading}
                variant="outline"
                className="admin-action-btn"
              >
                <RefreshCw className="admin-refresh-conditional" style={{ '--admin-spin-anim': loading ? 'admin-spin 1s linear infinite' : 'none' }} />
                Обновить
              </Button>
            </div>
          </div>

          {/* Настройки */}
          <div className="admin-grid-auto-400-24">
            {/* Повторные визиты */}
            <MacOSCard className="admin-settings-card" style={{ '--admin-card-transform': settings.repeat_visit_discount > 0 ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-setting-card-header">
                <div className="admin-icon-bg-success">
                  <Calendar className="admin-icon-20-success" />
                </div>
                <div>
                  <div className="admin-setting-title">
                    <h3 className="admin-setting-h3">
                      Повторные визиты
                    </h3>
                    <Badge
                      variant={settings.repeat_visit_discount > 0 ? 'success' : 'secondary'}
                      size="sm"
                    >
                      {settings.repeat_visit_discount > 0 ? 'Активны' : 'Неактивны'}
                    </Badge>
                  </div>
                  <p className="admin-setting-desc">
                    Настройки для повторных консультаций
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                {/* Окно повторного визита */}
                <div>
                  <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                    Окно повторного визита (дней)
                  </label>
                  <div className="admin-flex-center-12">
                    <div className="admin-input-icon-wrap">
                      <Clock className="admin-input-icon" />
                      <Input
                        type="number"
                        min="1"
                        max="365"
                        value={settings.repeat_visit_days}
                        onChange={(e) => handleInputChange('repeat_visit_days', parseInt(e.target.value) || 21)}
                        placeholder="21"
                        className="admin-input-with-icon"
                      />
                    </div>
                    <span className="admin-unit-span">
                      дней
                    </span>
                  </div>
                  <p className="admin-help-p">
                    Период, в течение которого консультация считается повторной
                  </p>
                </div>

                {/* Скидка на повторный визит */}
                <div>
                  <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                    Скидка на повторный визит (%)
                  </label>
                  <div className="admin-flex-center-12">
                    <div className="admin-input-icon-wrap">
                      <Percent className="admin-input-icon" />
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={settings.repeat_visit_discount}
                        onChange={(e) => handleInputChange('repeat_visit_discount', parseInt(e.target.value) || 0)}
                        placeholder="0"
                        className="admin-input-with-icon"
                      />
                    </div>
                    <span className="admin-unit-span">
                      %
                    </span>
                  </div>
                  <p className="admin-help-p">
                    0% = бесплатно, 50% = половина цены, 100% = полная цена
                  </p>
                </div>

                {/* Информационная карточка */}
                <MacOSCard className="admin-info-card-accent">
                  <div className="admin-info-row">
                    <Info className="admin-info-icon-blue" />
                    <div className="admin-info-text-blue">
                      <p className="admin-info-p-mt-8">
                        Как работают повторные визиты:
                      </p>
                      <ul className="admin-info-list">
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
            <MacOSCard className="admin-settings-card" style={{ '--admin-card-transform': settings.benefit_consultation_free ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-setting-card-header">
                <div className="admin-icon-bg-warning">
                  <Shield className="admin-icon-20-warning" />
                </div>
                <div>
                  <div className="admin-setting-title">
                    <h3 className="admin-setting-h3">
                      Льготные визиты
                    </h3>
                    <Badge
                      variant={settings.benefit_consultation_free ? 'success' : 'warning'}
                      size="sm"
                    >
                      {settings.benefit_consultation_free ? 'Бесплатно' : 'Платно'}
                    </Badge>
                  </div>
                  <p className="admin-setting-desc">
                    Настройки для льготных категорий пациентов
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                {/* Льготные консультации бесплатны */}
                <div>
                  <div className="admin-info-row">
                    <Checkbox
                      checked={settings.benefit_consultation_free}
                      onChange={(checked) => handleInputChange('benefit_consultation_free', checked)}
                    />
                    <div>
                      <span className="admin-setting-label-block">
                        Льготные консультации бесплатны
                      </span>
                      <p className="admin-setting-p-tertiary">
                        Консультации специалистов для льготных категорий
                      </p>
                    </div>
                  </div>
                </div>

                {/* Автоодобрение All Free */}
                <div>
                  <div className="admin-info-row">
                    <Checkbox
                      checked={settings.all_free_auto_approve}
                      onChange={(checked) => handleInputChange('all_free_auto_approve', checked)}
                    />
                    <div>
                      <span className="admin-setting-label-block">
                        Автоодобрение заявок &quot;All Free&quot;
                      </span>
                      <p className="admin-setting-p-tertiary">
                        Автоматически одобрять все заявки на бесплатные услуги
                      </p>
                    </div>
                  </div>
                </div>

                {/* Предупреждение об автоодобрении */}
                {settings.all_free_auto_approve && (
                  <MacOSCard className="admin-info-card-warning">
                    <div className="admin-info-row">
                      <AlertCircle className="admin-info-icon-warning" />
                      <div className="admin-info-text-warning">
                        <p className="admin-info-p-mt-4">
                          Внимание!
                        </p>
                        <p className="admin-text-xs admin-m-0">
                          При включении автоодобрения все заявки &quot;All Free&quot; будут одобряться без проверки администратора.
                        </p>
                      </div>
                    </div>
                  </MacOSCard>
                )}

                {/* Информационная карточка */}
                <MacOSCard className="admin-info-card-warning">
                  <div className="admin-info-row">
                    <Info className="admin-info-icon-warning" />
                    <div className="admin-info-text-warning">
                      <p className="admin-info-p-mt-8">
                        Типы льгот:
                      </p>
                      <ul className="admin-info-list">
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
          <div className="admin-actions-bar">
            <div className="flex items-center justify-center gap-2">
              {hasChanges() && (
                <div className="admin-unsaved-badge">
                  <AlertCircle className="w-3.5 h-3.5" />
                  Есть несохранённые изменения
                </div>
              )}
            </div>

            <div className="admin-flex-gap-12-wrap">
              {hasChanges() && (
                <Button
                  onClick={resetSettings}
                  variant="outline"
                  disabled={saving}
                  className="admin-action-btn"
                >
                  Отменить
                </Button>
              )}

              <Button
                onClick={saveSettings}
                disabled={saving || !hasChanges()}
                className="admin-action-btn-primary"
              >
                {saving ? (
                  <RefreshCw className="admin-icon-16-spin-mr-8 admin-mr-0" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {saving ? 'Сохранение...' : 'Сохранить настройки'}
              </Button>
            </div>
          </div>

          {/* Статистика настроек */}
          <div className="admin-grid-auto-200">
            <MacOSStatCard
              title="Окно повторных визитов"
              value={`${settings.repeat_visit_days} дней`}
              icon={Calendar}
              color="blue"
              trend={settings.repeat_visit_discount > 0 ? 'Скидка активна' : 'Скидка неактивна'}
              trendColor={settings.repeat_visit_discount > 0 ? 'var(--mac-success)' : 'var(--mac-text-secondary)'}
            />

            <MacOSStatCard
              title="Скидка на повторные визиты"
              value={`${settings.repeat_visit_discount}%`}
              icon={Percent}
              color={settings.repeat_visit_discount > 0 ? 'green' : 'orange'}
              trend={settings.repeat_visit_discount > 0 ? 'Применяется' : 'Не применяется'}
              trendColor={settings.repeat_visit_discount > 0 ? 'var(--mac-success)' : 'var(--mac-warning)'}
            />

            <MacOSStatCard
              title="Льготные консультации"
              value={settings.benefit_consultation_free ? 'Бесплатно' : 'Платно'}
              icon={Shield}
              color={settings.benefit_consultation_free ? 'green' : 'orange'}
              trend={settings.benefit_consultation_free ? 'Активны' : 'Неактивны'}
              trendColor={settings.benefit_consultation_free ? 'var(--mac-success)' : 'var(--mac-warning)'}
            />

            <MacOSStatCard
              title="Автоодобрение All Free"
              value={settings.all_free_auto_approve ? 'Включено' : 'Выключено'}
              icon={CheckCircle}
              color={settings.all_free_auto_approve ? 'orange' : 'blue'}
              trend={settings.all_free_auto_approve ? 'Автоматически' : 'Вручную'}
              trendColor={settings.all_free_auto_approve ? 'var(--mac-warning)' : 'var(--mac-info)'}
            />
          </div>

          {/* Предварительный просмотр */}
          <MacOSCard className="admin-preview-card">
            <h4 className="admin-preview-h4">
              Текущие настройки:
            </h4>
            <div className="admin-preview-grid">
              <div className="flex items-center justify-center gap-2">
                <Calendar className="admin-icon-14-tertiary" />
                <span className="text-[var(--mac-text-secondary)]">
                  Окно: {settings.repeat_visit_days} дней
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <DollarSign className="admin-icon-14-tertiary" />
                <span className="text-[var(--mac-text-secondary)]">
                  Скидка: {settings.repeat_visit_discount}%
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <CheckCircle className="admin-icon-14-color" style={{ '--admin-icon-color': settings.benefit_consultation_free ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' }} />
                <span className="text-[var(--mac-text-secondary)]">
                  Льготы: {settings.benefit_consultation_free ? 'Бесплатно' : 'Платно'}
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <Shield className="admin-icon-14-color" style={{ '--admin-icon-color': settings.all_free_auto_approve ? 'var(--mac-warning)' : 'var(--mac-text-tertiary)' }} />
                <span className="text-[var(--mac-text-secondary)]">
                  All Free: {settings.all_free_auto_approve ? 'Автоодобрение' : 'Ручное одобрение'}
                </span>
              </div>
            </div>
          </MacOSCard>
        </div>
      </MacOSCard>

      {/* Модальное окно подтверждения */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="Подтверждение изменений"
        size="sm"
      >
        <div className="p-6">
          <p className="admin-confirm-p">
            Вы собираетесь сохранить изменения в настройках льгот.
            Это повлияет на всех пользователей системы.
          </p>

          <div className="admin-flex-end-12">
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}
              disabled={saving}
            >
              Отмена
            </Button>
            <Button
              onClick={confirmSave}
              disabled={saving}
              aria-label="Confirm benefit settings save"
              className="admin-confirm-primary"
            >
              {saving ? (
                <>
                  <RefreshCw className="admin-refresh-mr-8-conditional" style={{ '--admin-spin-anim': 'admin-spin 1s linear infinite' }} />
                  Сохранение...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  Подтвердить
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default BenefitSettings;

