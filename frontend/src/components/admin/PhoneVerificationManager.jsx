import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Skeleton,
  Input,
  Select,
  Textarea,
} from '../ui/macos';
import {
  Phone,
  Shield,
  Send,
  BarChart3,

  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Settings } from

'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const PhoneVerificationManager = () => {
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [adminForm, setAdminForm] = useState({
    phone: '',
    purpose: 'verification',
    provider: '',
    message: ''
  });

  useEffect(() => {
    loadStatistics();
  }, []);

  const loadStatistics = async () => {
    setLoading(true);
    try {
      const response = await api.get('/phone-verification/statistics');
      setStatistics(response.data.statistics);
    } catch (error) {
      logger.error('Error loading verification statistics:', error);
      toast.error('Ошибка загрузки статистики верификации');
    } finally {
      setLoading(false);
    }
  };

  const sendAdminCode = async () => {
    if (!adminForm.phone.trim()) {
      toast.error('Введите номер телефона');
      return;
    }

    setLoading(true);
    try {
      const params = {
        phone: adminForm.phone,
        purpose: adminForm.purpose
      };

      if (adminForm.provider) {
        params.provider = adminForm.provider;
      }

      if (adminForm.message.trim()) {
        params.message = adminForm.message;
      }

      const response = await api.post('/phone-verification/admin/send-code', null, { params });

      if (response.data.success) {
        toast.success(`Код отправлен на ${adminForm.phone}`);
        setAdminForm({
          phone: '',
          purpose: 'verification',
          provider: '',
          message: ''
        });
        loadStatistics(); // Обновляем статистику
      }
    } catch (error) {
      logger.error('Error sending admin verification code:', error);
      toast.error('Ошибка отправки кода верификации');
    } finally {
      setLoading(false);
    }
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, '');
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    return value;
  };

  const renderOverview = () =>
  <div className="flex flex-col gap-6">
      {/* Основная статистика */}
      <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-sm-secondary-m-008px0">
                Активные коды
              </p>
              <p className="admin-2xl-bold-primary-m-0">
                {statistics?.total_active_codes || 0}
              </p>
            </div>
            <Shield className="admin-w-24-h-24-blue" />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-sm-secondary-m-008px0">
                Подтверждено
              </p>
              <p className="admin-2xl-bold-success-m-0">
                {statistics?.verified_codes || 0}
              </p>
            </div>
            <CheckCircle className="admin-w-24-h-24-success" />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-sm-secondary-m-008px0">
                Ожидают
              </p>
              <p className="admin-2xl-bold-warning-m-0">
                {statistics?.pending_codes || 0}
              </p>
            </div>
            <Clock className="admin-w-24-h-24-warning" />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-sm-secondary-m-008px0">
                Истекают скоро
              </p>
              <p className="admin-2xl-bold-error-m-0">
                {statistics?.expiring_soon || 0}
              </p>
            </div>
            <AlertTriangle className="admin-w-24-h-24-error" />
          </div>
        </MacOSCard>
      </div>

      {/* Статистика по целям */}
      <MacOSCard className="p-6">
        <h3 className="admin-lg-med-primary-m-0016px0-flex-ai-center-gap-8">
          <BarChart3 className="w-5 h-5" />
          Статистика по целям верификации
        </h3>
        <div className="admin-grid-gtc-rauto-fitcminmax250pxc1fr-gap-16">
          {statistics?.by_purpose && Object.entries(statistics.by_purpose).map(([purpose, count]) =>
        <div key={purpose} className="admin-flex-ai-center-jc-between-p-12-bd-1solidvar-mac-border-radius-var--mac-rad-77bc24ad">
              <div>
                <p className="admin-med-sm-primary-m-004px0-texttransform-aab31f">
                  {purpose}
                </p>
                <p className="admin-xs-secondary-m-0">
                  {purpose === 'verification' && 'Подтверждение номера'}
                  {purpose === 'password_reset' && 'Сброс пароля'}
                  {purpose === 'phone_change' && 'Смена номера'}
                  {purpose === 'registration' && 'Регистрация'}
                </p>
              </div>
              <Badge variant="outline">{count}</Badge>
            </div>
        )}
        </div>
      </MacOSCard>

      {/* Статистика по провайдерам */}
      <MacOSCard className="p-6">
        <h3 className="admin-lg-med-primary-m-0016px0-flex-ai-center-gap-8">
          <Send className="w-5 h-5" />
          Статистика по SMS провайдерам
        </h3>
        <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
          {statistics?.by_provider && Object.entries(statistics.by_provider).map(([provider, count]) =>
        <div key={provider} className="admin-flex-ai-center-jc-between-p-12-bd-1solidvar-mac-border-radius-var--mac-rad-77bc24ad">
              <div>
                <p className="admin-med-sm-primary-m-0-texttransform-aab31f">
                  {provider}
                </p>
              </div>
              <Badge variant={provider === 'mock' ? 'secondary' : 'success'}>{count}</Badge>
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderAdminTools = () =>
  <div className="flex flex-col gap-6">
      <MacOSCard className="p-6">
        <h3 className="admin-lg-med-primary-m-0016px0-flex-ai-center-gap-8">
          <Send className="w-5 h-5" />
          Отправка кода администратором
        </h3>
        <div className="flex flex-col gap-4">
          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              Номер телефона
            </label>
            <Input
            type="tel"
            value={adminForm.phone}
            onChange={(e) => setAdminForm((prev) => ({ ...prev, phone: formatPhone(e.target.value) }))}
            placeholder="+998XXXXXXXXX"
            className="w-full" />
          
          </div>

          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              Цель верификации
            </label>
            <Select
            value={adminForm.purpose}
            onChange={(value) => setAdminForm((prev) => ({ ...prev, purpose: value }))}
            options={[
            { value: 'verification', label: 'Подтверждение номера' },
            { value: 'password_reset', label: 'Сброс пароля' },
            { value: 'phone_change', label: 'Смена номера' },
            { value: 'registration', label: 'Регистрация' }]
            }
            size="large"
            className="w-full" />
          
          </div>

          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              SMS провайдер (опционально)
            </label>
            <Select
            value={adminForm.provider}
            onChange={(value) => setAdminForm((prev) => ({ ...prev, provider: value }))}
            options={[
            { value: '', label: 'По умолчанию' },
            { value: 'eskiz', label: 'Eskiz' },
            { value: 'playmobile', label: 'PlayMobile' },
            { value: 'mock', label: 'Mock (тест)' }]
            }
            size="large"
            className="w-full" />
          
          </div>

          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              Кастомное сообщение (опционально)
            </label>
            <Textarea
            value={adminForm.message}
            onChange={(e) => setAdminForm((prev) => ({ ...prev, message: e.target.value }))}
            placeholder="Ваш код подтверждения: {code}. Код действителен 5 минут."
            className="admin-minh-80-w-100pct" />
          
            <p className="admin-xs-secondary-m-4px000">
              Используйте {'{code}'} для вставки кода верификации
            </p>
          </div>

          <Button
          onClick={sendAdminCode}
          disabled={loading || !adminForm.phone.trim()}
          aria-label="Send admin verification code"
          className="w-full">
          
            {loading ?
          <>
                <RefreshCw className="admin-w-16-h-16-mr-8-anim-spin1slinearinfinite" />
                Отправка...
              </> :

          <>
                <Send className="w-4 h-4 mr-2" />
                Отправить код
              </>
          }
          </Button>
        </div>
      </MacOSCard>
    </div>;


  const renderSettings = () =>
  <div className="flex flex-col gap-6">
      <MacOSCard className="p-6">
        <h3 className="admin-lg-med-primary-m-0016px0-flex-ai-center-gap-8">
          <Settings className="w-5 h-5" />
          Настройки верификации
        </h3>
        <div className="flex flex-col gap-4">
          {statistics?.settings &&
        <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
              <div className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                <p className="admin-med-sm-primary-m-008px0">
                  Длина кода
                </p>
                <p className="admin-2xl-bold-blue-m-004px0">
                  {statistics.settings.code_length}
                </p>
                <p className="admin-xs-secondary-m-0">
                  цифр
                </p>
              </div>

              <div className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                <p className="admin-med-sm-primary-m-008px0">
                  Время жизни кода
                </p>
                <p className="admin-2xl-bold-success-m-004px0">
                  {statistics.settings.ttl_minutes}
                </p>
                <p className="admin-xs-secondary-m-0">
                  минут
                </p>
              </div>

              <div className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                <p className="admin-med-sm-primary-m-008px0">
                  Максимум попыток
                </p>
                <p className="admin-2xl-bold-warning-m-004px0">
                  {statistics.settings.max_attempts}
                </p>
                <p className="admin-xs-secondary-m-0">
                  попыток
                </p>
              </div>

              <div className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                <p className="admin-med-sm-primary-m-008px0">
                  Лимит частоты
                </p>
                <p className="admin-2xl-bold-error-m-004px0">
                  {statistics.settings.rate_limit_minutes}
                </p>
                <p className="admin-xs-secondary-m-0">
                  минут
                </p>
              </div>
            </div>
        }

          <div className="admin-p-16-bg-info-bg-bd-1solidvar-mac-info-border-radius-var--mac-radius-md">
            <h4 className="admin-med-info-sm-m-008px0">
              Информация
            </h4>
            <ul className="admin-xs-info-m-0-pl-16-flex-col-gap-4">
              <li>• Коды верификации хранятся в памяти сервера</li>
              <li>• Для production рекомендуется использовать Redis</li>
              <li>• Истекшие коды автоматически удаляются</li>
              <li>• Лимит частоты предотвращает спам</li>
            </ul>
          </div>
        </div>
      </MacOSCard>
    </div>;


  const tabs = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'admin-tools', label: 'Инструменты', icon: Send },
  { id: 'settings', label: 'Настройки', icon: Settings }];


  return (
    <div className="admin-p-24-bg-bg-primary-minh-100vh">
      {/* Заголовок */}
      <div className="admin-flex-ai-center-jc-between-mb-24">
        <div className="admin-flex-center-12">
          <Phone className="admin-w-32-h-32-blue" />
          <div>
            <h1 className="admin-2xl-semi-primary-m-0">
              Верификация телефонов
            </h1>
            <p className="admin-secondary-sm-m-0">
              Управление SMS верификацией
            </p>
          </div>
        </div>
        
        <Button onClick={loadStatistics} disabled={loading} variant="outline">
          <RefreshCw className="admin-w-16-h-16-mr-8" style={{ '--admin-animation': loading ? 'spin 1s linear infinite' : 'none' }} />
          Обновить
        </Button>
      </div>

      {/* Вкладки */}
      <div className="admin-flex-mb-24">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-p-12px20-bd-none-bg-transparent-cursor-pointer-flex-ai-center-gap-8-sm-tra-ea233b09" style={{ '--admin-color': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)', '--admin-fontWeight': isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)' }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-secondary)';
                }
              }}>
              
              <Icon className="admin-w-16-h-16" style={{ '--admin-color': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' }} />
              {tab.label}
              {isActive &&
              <div className="admin-pos-absolute-bottom-0-left-0-right-0-h-3-bg-blue-radius-2px2px00" />
              }
            </button>);

        })}
      </div>
      
      {/* Разделительная линия */}
      <div className="admin-borderbottom-0a48a6-mb-24" />

      {/* Контент вкладок */}
      {loading && !statistics ?
      <div className="flex flex-col gap-4">
          <Skeleton height="128px" className="w-full" />
          <Skeleton height="256px" className="w-full" />
        </div> :

      <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'admin-tools' && renderAdminTools()}
          {activeTab === 'settings' && renderSettings()}
        </>
      }
    </div>);

};

export default PhoneVerificationManager;
