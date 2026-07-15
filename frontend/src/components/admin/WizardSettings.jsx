import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
  MacOSStatCard,
} from '../ui/macos';
import { Settings, Save, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { fetchWizardSettings, saveWizardSettings } from '../../api/adminSettings';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
const WizardSettings = () => {
  const { t } = useTranslation();
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
      const data = await fetchWizardSettings();
      setSettings(data);
      setHasChanges(false);
    } catch (error) {
      logger.error('Error fetching wizard settings:', error);
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
    setSettings((prev) => ({
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
      const response = await saveWizardSettings({
        use_new_wizard: settings.use_new_wizard
      });

      if (response.success) {
        toast.success(response.message);
        setSettings(response.settings);
        setHasChanges(false);
      } else {
        throw new Error(response.message || 'Ошибка сохранения');
      }
    } catch (error) {
      logger.error('Error saving wizard settings:', error);
      toast.error('Ошибка сохранения настроек');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
          <div className="admin-d-flex-ai-center-gap-8-mb-24">
            <Settings className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              Настройки мастера регистрации
            </h2>
          </div>
          <Skeleton height="400px" />
      </MacOSCard>);

  }

  // Критическая ошибка загрузки
  if (error && !settings.updated_at) {
    return (
      <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
          <div className="admin-d-flex-ai-center-gap-8-mb-24">
            <Settings className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              Настройки мастера регистрации
            </h2>
          </div>
          <MacOSEmptyState
          icon={AlertCircle}
          title="Не удалось загрузить настройки"
          description="Проверьте подключение к серверу и попробуйте обновить страницу"
          action={
          <Button onClick={fetchSettings} variant="primary">
                <RefreshCw className="admin-w-16-h-16-mr-4" />
                Попробовать снова
              </Button>
          } />

      </MacOSCard>);

  }

  return (
    <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
      <div className="admin-d-flex-ai-center-gap-8-mb-24-fw-wrap">
          <Settings className="admin-w-32-h-32-blue" />
          <h2 className="admin-fs-2xl-fw-semi-primary-m-0-flex-1-minw-200">
            Настройки мастера регистрации
          </h2>

        <div className="admin-flex-col-24">
          {/* Критическая ошибка */}
          {error &&
          <Alert
            type="error"
            title="Ошибка загрузки"
            message={error}
            onClose={() => setError(null)} />

          }

          {/* A/B Переключатель */}
          <MacOSCard className="admin-p-24-bgc-bg-secondary-bd-1px-solid-var-mac-bo">
            <div className="admin-d-flex-ai-center-jc-between-mb-16">
              <div className="admin-flex-1">
                <h3 className="admin-fs-lg-fw-semi-primary-m-0-0-4px-0">
                  Версия мастера регистрации
                </h3>
                <p className="admin-fs-sm-secondary-m-0">
                  {settings.use_new_wizard ?
                  'Используется новый мастер с улучшенным дизайном, корзиной и онлайн-оплатой' :
                  'Используется классический мастер регистрации'
                  }
                </p>
              </div>
              
              <div className="admin-flex-center-8">
                <Checkbox
                  checked={settings.use_new_wizard}
                  onChange={handleToggleWizard} />

                <span className="admin-fs-sm-fw-med-col-dyn" style={{ '--admin-col0': settings.use_new_wizard ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' }}>
                  {settings.use_new_wizard ? 'Новый мастер' : 'Старый мастер'}
                </span>
              </div>
            </div>
          </MacOSCard>

          {/* Статистика использования */}
          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
            <MacOSStatCard
              title="Использование нового мастера"
              value={settings.use_new_wizard ? '100%' : '0%'}
              icon={settings.use_new_wizard ? CheckCircle : AlertCircle}
              color={settings.use_new_wizard ? 'green' : 'orange'}
              trend={settings.use_new_wizard ? 'Активен' : 'Неактивен'}
              trendColor={settings.use_new_wizard ? 'var(--mac-success)' : 'var(--mac-warning)'} />

            
            <MacOSStatCard
              title="Последнее обновление"
              value={settings.updated_at ? new Date(settings.updated_at).toLocaleDateString('ru-RU') : 'Неизвестно'}
              icon={RefreshCw}
              color="blue"
              trend="Настройки"
              trendColor="var(--mac-text-secondary)" />

          </div>

          {/* Информация о версиях */}
          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
            <MacOSCard className="admin-p-24-tr-all-var-mac-duration-bd-dyn-bgc-dyn-tf-dyn" style={{ '--admin-bd0': !settings.use_new_wizard ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)', '--admin-bgc1': !settings.use_new_wizard ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)', '--admin-tf2': !settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-d-flex-ai-center-gap-4-mb-8">
                <h4 className="admin-fs-lg-fw-semi-primary-m-0">
                  Классический мастер
                </h4>
                <Badge
                  variant={!settings.use_new_wizard ? 'primary' : 'secondary'}
                  size="sm">

                  {!settings.use_new_wizard ? 'Активен' : 'Неактивен'}
                </Badge>
              </div>
              <ul className="admin-fs-sm-secondary-m-0-pl-16-d-flex-fd-column-gap-4">
                <li>• Проверенная стабильность</li>
                <li>• Привычный интерфейс</li>
                <li>• Базовая функциональность</li>
                <li>• Простая оплата</li>
              </ul>
            </MacOSCard>

            <MacOSCard className="admin-p-24-tr-all-var-mac-duration-bd-dyn-bgc-dyn-tf-dyn" style={{ '--admin-bd0': settings.use_new_wizard ? '2px solid var(--mac-success)' : '1px solid var(--mac-border)', '--admin-bgc1': settings.use_new_wizard ? 'var(--mac-success-bg)' : 'var(--mac-bg-primary)', '--admin-tf2': settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-d-flex-ai-center-gap-4-mb-8">
                <h4 className="admin-fs-lg-fw-semi-primary-m-0">
                  Новый мастер
                </h4>
                <Badge
                  variant={settings.use_new_wizard ? 'success' : 'secondary'}
                  size="sm">

                  {settings.use_new_wizard ? 'Активен' : 'Неактивен'}
                </Badge>
              </div>
              <ul className="admin-fs-sm-secondary-m-0-pl-16-d-flex-fd-column-gap-4">
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
          {hasChanges &&
          <MacOSCard className="admin-p-16-bgc-var-mac-warning-bg-bd-1px-solid-var-mac-wa">
              <div className="admin-flex-center-8">
                <AlertCircle className="admin-w-20-h-20-warning-fsk-0" />
                <p className="admin-fs-sm-warning-m-0-fw-med">
                  Изменения не сохранены. Нажмите «Сохранить» для применения настроек.
                </p>
              </div>
            </MacOSCard>
          }

          {/* Информация об обновлении */}
          {settings.updated_at &&
          <div className="admin-fs-xs-tertiary-ta-center-p-8px-0">
              Последнее обновление: {new Date(settings.updated_at).toLocaleString('ru-RU')}
            </div>
          }

          {/* Кнопки действий */}
          <div className="admin-d-flex-jc-end-gap-8-pt-16-bd-t-1px-solid-var-mac-bo-fw-wrap">
            <Button
              variant="outline"
              onClick={fetchSettings}
              disabled={saving}
              className="admin-d-flex-ai-center-gap-4-p-4px-16px-minw-120">

              Отменить
            </Button>
            
            <Button
              type="button"
              title={saving ? 'Saving wizard settings' : 'Save wizard settings'}
              aria-label={saving ? 'Saving wizard settings' : 'Save wizard settings'}
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="admin-d-flex-ai-center-gap-4-bgc-blue-bd-none-p-4px-16px-minw-120">

              {saving ?
              <>
                  <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                  Сохранение...
                </> :

              <>
                  <Save aria-hidden="true" className="admin-icon-16" />
                  Сохранить
                </>
              }
            </Button>
          </div>
        </div>
      </div>

      {/* Модальное окно подтверждения */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="Подтверждение изменений"
        size="sm">

        <div className="admin-p-24">
          <p className="admin-fs-base-primary-mb-24-lh-var-mac-line-height">
            Вы собираетесь {settings.use_new_wizard ? 'включить' : 'отключить'} новый мастер регистрации. 
            Это изменение повлияет на всех пользователей системы.
          </p>
          
          <div className="admin-d-flex-jc-end-gap-var-mac-spacing-sm">
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}
              disabled={saving}>

              Отмена
            </Button>
            <Button
              type="button"
              title={saving ? 'Saving wizard settings' : 'Confirm wizard settings save'}
              aria-label={saving ? 'Saving wizard settings' : 'Confirm wizard settings save'}
              onClick={confirmSave}
              disabled={saving}
              className="admin-bgc-blue-bd-none">

              {saving ?
              <>
                  <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin-mr-4" />
                  Сохранение...
                </> :

              <>
                  <Save aria-hidden="true" className="admin-w-16-h-16-mr-4" />
                  Подтвердить
                </>
              }
            </Button>
          </div>
        </div>
      </Modal>
    </MacOSCard>);

};

export default WizardSettings;
