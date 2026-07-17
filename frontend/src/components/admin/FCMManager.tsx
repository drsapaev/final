// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect, useCallback } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Skeleton,
  Input,
  Select,
  Textarea,
  Checkbox,
} from '../ui/macos';
import {
  Bell,
  Send,
  Users,

  CheckCircle,
  AlertTriangle,
  Activity,
  Smartphone,

  RefreshCw,
  TestTube,
  Zap } from
'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
const formatFcmTokenStatus = (user, t) => {
  const fallbackLength = typeof user.fcm_token === 'string' ? user.fcm_token.length : 0;
  const tokenLength = Number.isFinite(user.fcm_token_length) ? user.fcm_token_length : fallbackLength;

  return tokenLength > 0 ? t('admin2.fcm_token_hidden', { count: tokenLength }) : t('admin2.fcm_token_not_registered');
};

const FCMManager = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [fcmStatus, setFcmStatus] = useState(null);
  const [usersWithTokens, setUsersWithTokens] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [notificationForm, setNotificationForm] = useState({
    title: '',
    body: '',
    user_ids: [],
    data: {},
    image: '',
    sound: 'default'
  });

  const loadFCMStatus = useCallback(async () => {
    try {
      const response = await api.get('/fcm/status');
      setFcmStatus(response.data.fcm_service);
    } catch (error) {
      logger.error('Error loading FCM status:', error);
    }
  }, []);

  const loadUsersWithTokens = useCallback(async () => {
    try {
      const response = await api.get('/fcm/user-tokens');
      setUsersWithTokens(response.data.users || []);
    } catch (error) {
      logger.error('Error loading users with tokens:', error);
    }
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
      loadFCMStatus(),
      loadUsersWithTokens()]
      );
    } catch (error) {
      logger.error('Error loading FCM data:', error);
      toast.error(t('admin2.fcm_err_load_data'));
    } finally {
      setLoading(false);
    }
  }, [loadFCMStatus, loadUsersWithTokens]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const testFCMNotification = async () => {
    try {
      setLoading(true);
      const response = await api.post('/fcm/send-test-notification');

      if (response.data.success) {
        toast.success(t('admin2.fcm_toast_test_sent'));
      } else {
        toast.error(t('admin2.fcm_err_with_message', { message: response.data.message }));
      }
    } catch (error) {
      logger.error('Error testing FCM:', error);
      toast.error(t('admin2.fcm_err_test'));
    } finally {
      setLoading(false);
    }
  };

  const sendNotification = async () => {
    if (!notificationForm.title.trim() || !notificationForm.body.trim()) {
      toast.error(t('admin2.fcm_err_form_required'));
      return;
    }

    try {
      setLoading(true);

      const payload = {
        title: notificationForm.title,
        body: notificationForm.body,
        sound: notificationForm.sound
      };

      // Добавляем пользователей если выбраны
      if (notificationForm.user_ids.length > 0) {
        payload.user_ids = notificationForm.user_ids;
      }

      // Добавляем дополнительные данные
      if (Object.keys(notificationForm.data).length > 0) {
        payload.data = notificationForm.data;
      }

      // Добавляем изображение если указано
      if (notificationForm.image.trim()) {
        payload.image = notificationForm.image;
      }

      const response = await api.post('/fcm/send-notification', payload);

      if (response.data.success) {
        toast.success(t('admin2.fcm_toast_sent', { message: response.data.message }));
        setNotificationForm({
          title: '',
          body: '',
          user_ids: [],
          data: {},
          image: '',
          sound: 'default'
        });
      } else {
        toast.error(t('admin2.fcm_err_send', { message: response.data.message }));
      }
    } catch (error) {
      logger.error('Error sending FCM notification:', error);
      toast.error(t('admin2.fcm_err_send_fcm'));
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () =>
  <div className="admin-flex-col-24">
      {/* Статус FCM */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-fs-lg-fw-med-primary-m-0-0-16px-0-d-flex-ai-center-gap-8-3">
          <Activity className="admin-icon-20" />
          {t('admin2.fcm_heading_status')}
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-3">
          <div className="admin-d-flex-ai-center-jc-between-p-16-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary-2">
            <div>
              <p className="admin-fs-sm-secondary-m-0-0-8px-0-2">
                {t('admin2.fcm_label_service_status')}
              </p>
              <p className="admin-fw-med-m-0-1">
                {fcmStatus?.active ?
              <Badge variant="success" className="admin-flex-center admin-gap-4">
                    <CheckCircle className="admin-w-12-h-12" />
                    {t('admin2.fcm_status_active')}
                  </Badge> :

              <Badge variant="secondary" className="admin-flex-center admin-gap-4">
                    <AlertTriangle className="admin-w-12-h-12" />
                    {t('admin2.fcm_status_inactive')}
                  </Badge>
              }
              </p>
            </div>
          </div>

          <div className="admin-d-flex-ai-center-jc-between-p-16-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary-1">
            <div>
              <p className="admin-fs-sm-secondary-m-0-0-8px-0-1">
                Server Key
              </p>
              <p className="admin-fw-med-m-0">
                {fcmStatus?.server_key_configured ?
              <Badge variant="success">{t('admin2.fcm_status_configured')}</Badge> :

              <Badge variant="secondary">{t('admin2.fcm_status_not_configured')}</Badge>
              }
              </p>
            </div>
          </div>

          <div className="admin-d-flex-ai-center-jc-between-p-16-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary">
            <div>
              <p className="admin-fs-sm-secondary-m-0-0-8px-0">
                {t('admin2.fcm_label_users_with_tokens')}
              </p>
              <p className="admin-fs-2xl-fw-bold-primary-m-0">
                {usersWithTokens.length}
              </p>
            </div>
            <Smartphone className="admin-w-24-h-24-blue" />
          </div>
        </div>
      </MacOSCard>

      {/* Быстрые действия */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-fs-lg-fw-med-primary-m-0-0-16px-0-d-flex-ai-center-gap-8-2">
          <Zap className="admin-icon-20" />
          {t('admin2.fcm_heading_quick_actions')}
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-2">
          <Button
          onClick={testFCMNotification}
          disabled={loading || !fcmStatus?.active}
          className="admin-flex-center-8">
          
            <TestTube className="admin-icon-16" />
            {t('admin2.fcm_btn_test')}
          </Button>

          <Button
          onClick={loadData}
          disabled={loading}
          variant="outline"
          className="admin-flex-center-8">
          
            <RefreshCw className="admin-icon-16" />
            {t('admin2.fcm_btn_refresh')}
          </Button>

          <Button
          onClick={() => setActiveTab('notifications')}
          variant="outline"
          className="admin-flex-center-8">
          
            <Send className="admin-icon-16" />
            {t('admin2.fcm_btn_send_notification')}
          </Button>
        </div>
      </MacOSCard>
    </div>;


  const renderNotifications = () =>
  <div className="admin-flex-col-24">
      <MacOSCard className="admin-p-24">
        <h3 className="admin-fs-lg-fw-med-primary-m-0-0-16px-0-d-flex-ai-center-gap-8-1">
          <Send className="admin-icon-20" />
          {t('admin2.fcm_heading_send')}
        </h3>
        <div className="admin-flex-col-16">
          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-14">
              {t('admin2.fcm_label_title')}
            </label>
            <Input
            type="text"
            value={notificationForm.title}
            onChange={(e) => setNotificationForm((prev) => ({ ...prev, title: e.target.value }))}
            placeholder={t('admin2.fcm_placeholder_title')}
            className="admin-w-full" />
          
          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-13">
              {t('admin2.fcm_label_body')}
            </label>
            <Textarea
            value={notificationForm.body}
            onChange={(e) => setNotificationForm((prev) => ({ ...prev, body: e.target.value }))}
            placeholder={t('admin2.fcm_placeholder_body')}
            className="admin-w-100pct-minh-100" />
          
          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-12">
              {t('admin2.fcm_label_image')}
            </label>
            <Input
            type="url"
            value={notificationForm.image}
            onChange={(e) => setNotificationForm((prev) => ({ ...prev, image: e.target.value }))}
            placeholder="https://example.com/image.jpg"
            className="admin-w-full" />
          
          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-11">
              {t('admin2.fcm_label_sound')}
            </label>
            <Select
            value={notificationForm.sound}
            onChange={(value) => setNotificationForm((prev) => ({ ...prev, sound: value }))}
            options={[
            { value: 'default', label: t('admin2.fcm_sound_default') },
            { value: 'notification', label: t('admin2.fcm_sound_notification') },
            { value: 'alert', label: t('admin2.fcm_sound_alert') },
            { value: 'chime', label: t('admin2.fcm_sound_chime') }]
            }
            size="large"
            className="admin-w-full" />
          
          </div>

          <div>
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-10">
              {t('admin2.fcm_label_recipients')}
            </label>
            <div className="admin-flex-col-8">
              <p className="admin-fs-xs-secondary-m-0">
                {t('admin2.fcm_recipients_hint')}
              </p>
              
              <div className="admin-maxh-160-ovy-auto-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-p-8-bgc-bg-secondary">
                {usersWithTokens.map((user) =>
              <label key={user.user_id} className="admin-d-flex-ai-center-gap-8-p-8-radius-var-mac-radius-sm-cur-pointer-tr-background-color-var"
              onMouseEnter={(e) => e.target.style.backgroundColor = 'var(--mac-bg-tertiary)'}
              onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}>
                
                    <Checkbox
                  checked={notificationForm.user_ids.includes(user.user_id)}
                  onChange={(checked) => {
                    if (checked) {
                      setNotificationForm((prev) => ({
                        ...prev,
                        user_ids: [...prev.user_ids, user.user_id]
                      }));
                    } else {
                      setNotificationForm((prev) => ({
                        ...prev,
                        user_ids: prev.user_ids.filter((id) => id !== user.user_id)
                      }));
                    }
                  }} />
                
                    <span className="admin-fs-sm-primary">
                      {user.full_name || user.username}
                    </span>
                    <Badge variant={user.push_enabled ? 'success' : 'secondary'} className="admin-ml-auto">
                      {user.device_type}
                    </Badge>
                  </label>
              )}
              </div>
            </div>
          </div>

          <Button
          onClick={sendNotification}
          disabled={loading || !fcmStatus?.active || !notificationForm.title.trim() || !notificationForm.body.trim()}
          className="admin-w-full">
          
            {loading ? t('admin2.fcm_btn_sending') : t('admin2.fcm_btn_send')}
          </Button>
        </div>
      </MacOSCard>
    </div>;


  const renderUsers = () =>
  <div className="admin-flex-col-24">
      <MacOSCard className="admin-p-24">
        <h3 className="admin-fs-lg-fw-med-primary-m-0-0-16px-0-d-flex-ai-center-gap-8">
          <Users className="admin-icon-20" />
          {t('admin2.fcm_heading_users', { count: usersWithTokens.length })}
        </h3>
        <div className="admin-flex-col-16">
          {usersWithTokens.map((user) =>
        <div key={user.user_id} className="admin-d-flex-ai-center-jc-between-p-16-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary-tr-all-var-mac-duration"
        onPointerEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
        }}
        onPointerLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
        }}>
          
              <div className="admin-flex-center-12">
                <Smartphone className="admin-w-20-h-20-tertiary" />
                <div>
                  <p className="admin-fw-med-fs-sm-primary-m-0-0-4px-0">
                    {user.full_name || user.username}
                  </p>
                  <p className="admin-fs-xs-secondary-m-0-0-4px-0">
                    {t('admin2.fcm_label_token')} {formatFcmTokenStatus(user, t)}
                  </p>
                  {user.last_login &&
              <p className="admin-fs-xs-tertiary-m-0">
                      {t('admin2.fcm_label_last_login')} {new Date(user.last_login).toLocaleString()}
                    </p>
              }
                </div>
              </div>
              
              <div className="admin-flex-center-8">
                <Badge variant={user.push_enabled ? 'success' : 'secondary'}>
                  {user.push_enabled ? t('admin2.fcm_push_on') : t('admin2.fcm_push_off')}
                </Badge>
                
                <Badge variant="outline">
                  {user.device_type || 'web'}
                </Badge>
              </div>
            </div>
        )}
          
          {usersWithTokens.length === 0 &&
        <div className="admin-ta-center-p-32px-0-secondary-fs-sm">
              {t('admin2.fcm_empty_users')}
            </div>
        }
        </div>
      </MacOSCard>
    </div>;


  const tabs = [
  { id: 'overview', label: t('admin2.fcm_tab_overview'), icon: Activity },
  { id: 'notifications', label: t('admin2.fcm_tab_notifications'), icon: Bell },
  { id: 'users', label: t('admin2.fcm_tab_users'), icon: Users }];


  return (
    <div className="admin-p-24-bgc-bg-primary-minh-100vh">
      {/* Заголовок */}
      <div className="admin-d-flex-ai-center-jc-between-mb-24">
        <div className="admin-flex-center-12">
          <Bell className="admin-w-32-h-32-warning" />
          <div>
            <h1 className="admin-fs-2xl-fw-semi-primary-m-0-2">
              Firebase Cloud Messaging
            </h1>
            <p className="admin-secondary-fs-sm-m-0-3">
              {t('admin2.fcm_subtitle')}
            </p>
          </div>
        </div>
        
        <div className="admin-flex-center-8">
          {fcmStatus?.active ?
          <Badge variant="success" className="admin-flex-center admin-gap-4">
              <CheckCircle className="admin-w-12-h-12" />
              {t('admin2.fcm_status_active_short')}
            </Badge> :

          <Badge variant="secondary" className="admin-flex-center admin-gap-4">
              <AlertTriangle className="admin-w-12-h-12" />
              {t('admin2.fcm_status_inactive_short')}
            </Badge>
          }
        </div>
      </div>

      {/* Вкладки */}
      <div className="admin-d-flex-mb-24">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-p-12px-20px-bd-none-bg-transparent-cur-pointer-d-flex-ai-center-gap-8-fs-sm-tr-all-var-mac-duration-pos-relative-mb-n1-col-dyn-fw-dyn" style={{ '--admin-col0': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)', '--admin-fw1': isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)' }}
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
              
              <Icon className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' }} />
              {tab.label}
              {isActive &&
              <div className="admin-pos-absolute-bottom-0-left-0-right-0-h-3-bgc-blue-radius-2px-2px-0-0" />
              }
            </button>);

        })}
      </div>
      
      {/* Разделительная линия */}
      <div className="admin-bd-b-1px-solid-var-mac-bo-mb-24" />

      {/* Контент вкладок */}
      {loading && !fcmStatus ?
      <div className="admin-flex-col-16">
          <Skeleton height="128px" className="admin-w-full" />
          <Skeleton height="256px" className="admin-w-full" />
        </div> :

      <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'notifications' && renderNotifications()}
          {activeTab === 'users' && renderUsers()}
        </>
      }
    </div>);

};

export default FCMManager;
