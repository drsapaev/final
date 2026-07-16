import { useState, useEffect } from 'react';
import {
  MacOSCard, Button, Badge, Input, Select, Textarea,
} from '../ui/macos';
import {
  Bell,
  Users,
  Send,




  BarChart3,
  MessageSquare,
  Phone,
  Mail,
  RefreshCw,

  Calendar,
  Activity } from
'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
const RegistrarNotificationManager = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('send');
  const [loading, setLoading] = useState(false);
  const [registrars, setRegistrars] = useState([]);
  const [stats, setStats] = useState(null);

  // Состояние для отправки уведомлений
  const [notificationForm, setNotificationForm] = useState({
    type: 'system_alert',
    alert_type: 'system_error',
    message: '',
    priority: 'normal',
    department: ''
  });

  // Состояние для тестирования
  const [testMessage, setTestMessage] = useState(t('admin2.rnm_default_test_message'));

  useEffect(() => {
    loadRegistrars();
    loadStats();
  }, []);

  const loadRegistrars = async () => {
    try {
      const response = await api.get('/registrar/notifications/registrars');
      setRegistrars(response.data.registrars || []);
    } catch (error) {
      logger.error('Ошибка загрузки регистраторов:', error);
      toast.error(t('admin2.rnm_load_registrars_error'));
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/registrar/notifications/stats');
      setStats(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      toast.error(t('admin2.rnm_load_stats_error'));
    }
  };

  const handleSendNotification = async () => {
    if (!notificationForm.message.trim()) {
      toast.error(t('admin2.rnm_message_required'));
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/system-alert', {
        alert_type: notificationForm.alert_type,
        message: notificationForm.message,
        priority: notificationForm.priority,
        department: notificationForm.department || null
      });

      if (response.data.success) {
        toast.success(t('admin2.rnm_notification_sent', { count: response.data.sent_count }));
        setNotificationForm({
          ...notificationForm,
          message: ''
        });
        loadStats(); // Обновляем статистику
      } else {
        toast.error(t('admin2.rnm_send_notification_error'));
      }
    } catch (error) {
      logger.error('Ошибка отправки уведомления:', error);
      toast.error(t('admin2.rnm_send_notification_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleSendDailySummary = async () => {
    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/daily-summary');

      if (response.data.success) {
        toast.success(t('admin2.rnm_daily_summary_sent', { count: response.data.sent_count }));
        loadStats();
      } else {
        toast.error(t('admin2.rnm_send_summary_error'));
      }
    } catch (error) {
      logger.error('Ошибка отправки сводки:', error);
      toast.error(t('admin2.rnm_send_daily_summary_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async () => {
    if (!testMessage.trim()) {
      toast.error(t('admin2.rnm_test_message_required'));
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/registrar/notifications/test?message=${encodeURIComponent(testMessage)}`);

      if (response.data.success) {
        toast.success(t('admin2.rnm_test_notification_sent', { count: response.data.sent_count }));
        loadStats();
      } else {
        toast.error(t('admin2.rnm_send_test_notification_error'));
      }
    } catch (error) {
      logger.error('Ошибка отправки тестового уведомления:', error);
      toast.error(t('admin2.rnm_send_test_notification_error'));
    } finally {
      setLoading(false);
    }
  };

  const renderSendTab = () =>
  <div className="admin-flex-col-24">
      {/* Форма отправки уведомления */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-m-0016px0-primary-flex-ai-center-gap-8-lg-med">
          <Send className="admin-icon-20" />
          {t('admin2.rnm_send_notification_title')}
        </h3>

        <div className="admin-grid-gtc-1fr1fr-gap-16-mb-16">
          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              {t('admin2.rnm_label_type')}
            </label>
            <Select
            value={notificationForm.alert_type}
            onChange={(value) => setNotificationForm({ ...notificationForm, alert_type: value })}
            options={[
            { value: 'system_error', label: t('admin2.rnm_type_system_error') },
            { value: 'payment_issue', label: t('admin2.rnm_type_payment_issue') },
            { value: 'queue_overflow', label: t('admin2.rnm_type_queue_overflow') },
            { value: 'equipment_failure', label: t('admin2.rnm_type_equipment_failure') },
            { value: 'security_alert', label: t('admin2.rnm_type_security_alert') },
            { value: 'maintenance', label: t('admin2.rnm_type_maintenance') }]
            }
            size="large"
            className="admin-w-full" />
          
          </div>

          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              {t('admin2.rnm_label_priority')}
            </label>
            <Select
            value={notificationForm.priority}
            onChange={(value) => setNotificationForm({ ...notificationForm, priority: value })}
            options={[
            { value: 'normal', label: t('admin2.rnm_priority_normal') },
            { value: 'warning', label: t('admin2.rnm_priority_warning') },
            { value: 'critical', label: t('admin2.rnm_priority_critical') }]
            }
            size="large"
            className="admin-w-full" />
          
          </div>
        </div>

        <div className="admin-mb-16">
          <label className="admin-block-sm-med-primary-mb-8">
            {t('admin2.rnm_label_department')}
          </label>
          <Input
          placeholder={t('admin2.rnm_department_placeholder')}
          value={notificationForm.department}
          onChange={(e) => setNotificationForm({ ...notificationForm, department: e.target.value })}
          className="admin-w-full" />
        
        </div>

        <div className="admin-mb-16">
          <label className="admin-block-sm-med-primary-mb-8">
            {t('admin2.rnm_label_message')}
          </label>
          <Textarea
          placeholder={t('admin2.rnm_message_placeholder')}
          value={notificationForm.message}
          onChange={(e) => setNotificationForm({ ...notificationForm, message: e.target.value })}
          rows={4}
          className="admin-w-full" />
        
        </div>

        <Button
        onClick={handleSendNotification}
        disabled={loading || !notificationForm.message.trim()}
        className="admin-flex-center-8">
        
          {loading ? <RefreshCw className="admin-w-16-h-16-anim-spin1slinearinfinite" /> : <Send className="admin-icon-16" />}
          {t('admin2.rnm_send_notification_title')}
        </Button>
      </MacOSCard>

      {/* Быстрые действия */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-m-0016px0-primary-flex-ai-center-gap-8-lg-med">
          <Activity className="admin-icon-20" />
          {t('admin2.rnm_quick_actions_title')}
        </h3>

        <div className="admin-flex-gap-16-wrap">
          <Button
          onClick={handleSendDailySummary}
          disabled={loading}
          className="admin-flex-center-8">
          
            <Calendar className="admin-icon-16" />
            {t('admin2.rnm_send_daily_summary_btn')}
          </Button>

          <div className="admin-flex-gap-8-ai-center">
            <Input
            placeholder={t('admin2.rnm_test_message_placeholder')}
            value={testMessage}
            onChange={(e) => setTestMessage(e.target.value)}
            className="admin-minw-200" />
          
            <Button
            onClick={handleTestNotification}
            disabled={loading || !testMessage.trim()}
            className="admin-flex-center-8">
            
              <MessageSquare className="admin-icon-16" />
              {t('admin2.rnm_test_btn')}
            </Button>
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderRegistrarsTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-flex-jc-between-ai-center-mb-24">
        <h3 className="admin-m-0-primary-flex-ai-center-gap-8-lg-med">
          <Users className="admin-icon-20" />
          {t('admin2.rnm_active_registrars_title', { count: registrars.length })}
        </h3>
        <Button
        onClick={loadRegistrars}
        className="admin-flex-center-8">
        
          <RefreshCw className="admin-icon-16" />
          {t('admin2.rnm_refresh_btn')}
        </Button>
      </div>

      <div className="admin-grid-gap-16">
        {registrars.map((registrar) =>
      <div
        key={registrar.id}
        className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-flex-jc-between-ai-center">
        
            <div>
              <div className="admin-semi-primary-mb-4-sm">
                {registrar.full_name || registrar.username}
              </div>
              <div className="admin-sm-secondary-flex-ai-center-gap-16">
                {registrar.email &&
            <span className="admin-flex-center admin-gap-4">
                    <Mail className="admin-icon-14" />
                    {registrar.email}
                  </span>
            }
                {registrar.phone &&
            <span className="admin-flex-center admin-gap-4">
                    <Phone className="admin-w-16-h-16-blue" />
                    {registrar.phone}
                  </span>
            }
              </div>
            </div>
            <div className="admin-flex-center-8">
              {registrar.telegram_id &&
          <Badge variant="info">
                  Telegram
                </Badge>
          }
              <Badge
            variant={registrar.is_active ? 'success' : 'error'}>
            
                {registrar.is_active ? t('admin2.rnm_status_active') : t('admin2.rnm_status_inactive')}
              </Badge>
            </div>
          </div>
      )}
      </div>

      {registrars.length === 0 &&
    <div className="admin-ta-center-p-32-secondary-sm">
          {t('admin2.rnm_no_registrars')}
        </div>
    }
    </MacOSCard>;


  const renderStatsTab = () =>
  <MacOSCard className="admin-p-24">
      <div className="admin-flex-jc-between-ai-center-mb-24">
        <h3 className="admin-m-0-primary-flex-ai-center-gap-8-lg-med">
          <BarChart3 className="admin-icon-20" />
          {t('admin2.rnm_stats_title')}
        </h3>
        <Button
        onClick={loadStats}
        className="admin-flex-center-8">
        
          <RefreshCw className="admin-icon-16" />
          {t('admin2.rnm_refresh_btn')}
        </Button>
      </div>

      {stats ?
    <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
          <div className="admin-p-16-bg-info-bg-radius-var--mac-radius-md-ta-center-bd-1solidvar-mac-info-border">
            <div className="admin-2xl-bold-blue">
              {stats.total_sent}
            </div>
            <div className="admin-secondary-sm">{t('admin2.rnm_stat_total_sent')}</div>
          </div>

          <div className="admin-p-16-bg-success-bg-radius-var--mac-radius-md-ta-center-bd-1solidvar-mac-su-76b6ec4f">
            <div className="admin-2xl-bold-success">
              {stats.successful_deliveries}
            </div>
            <div className="admin-secondary-sm">{t('admin2.rnm_stat_successful')}</div>
          </div>

          <div className="admin-p-16-bg-error-bg-radius-var--mac-radius-md-ta-center-bd-1solidvar-mac-error-border">
            <div className="admin-2xl-bold-error">
              {stats.failed_deliveries}
            </div>
            <div className="admin-secondary-sm">{t('admin2.rnm_stat_failed')}</div>
          </div>
        </div> :

    <div className="admin-ta-center-p-32-secondary-sm">
          {t('admin2.rnm_stats_loading')}
        </div>
    }

      {stats && stats.channels_stats &&
    <div className="admin-mt-24">
          <h4 className="admin-m-0016px0-primary-base-med">
            {t('admin2.rnm_channels_stats_title')}
          </h4>
          <div className="admin-grid-gtc-rauto-fitcminmax150pxc1fr-gap-16">
            <div className="admin-p-12-bd-1solidvar-mac-border-radius-var--mac-radius-sm-ta-center">
              <div className="admin-semi-blue-lg">
                {stats.channels_stats.telegram}
              </div>
              <div className="admin-text-sm admin-text-secondary">Telegram</div>
            </div>

            <div className="admin-p-12-bd-1solidvar-mac-border-radius-var--mac-radius-sm-ta-center">
              <div className="admin-semi-success-lg">
                {stats.channels_stats.email}
              </div>
              <div className="admin-text-sm admin-text-secondary">Email</div>
            </div>

            <div className="admin-p-12-bd-1solidvar-mac-border-radius-var--mac-radius-sm-ta-center">
              <div className="admin-semi-warning-lg">
                {stats.channels_stats.sms}
              </div>
              <div className="admin-text-sm admin-text-secondary">SMS</div>
            </div>
          </div>
        </div>
    }
    </MacOSCard>;


  const tabs = [
  { id: 'send', label: t('admin2.rnm_tab_send'), icon: Send },
  { id: 'registrars', label: t('admin2.rnm_tab_registrars'), icon: Users },
  { id: 'stats', label: t('admin2.rnm_tab_stats'), icon: BarChart3 }];


  return (
    <div className="admin-p-24">
      <div className="admin-flex-ai-center-gap-16-mb-24">
        <Bell className="admin-w-24-h-24-blue" />
        <h2 className="admin-m-0-primary-2xl-semi">
          {t('admin2.rnm_page_title')}
        </h2>
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

      {/* Содержимое вкладок */}
      {activeTab === 'send' && renderSendTab()}
      {activeTab === 'registrars' && renderRegistrarsTab()}
      {activeTab === 'stats' && renderStatsTab()}
    </div>);

};

export default RegistrarNotificationManager;
