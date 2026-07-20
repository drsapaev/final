import { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import {
  Shield,
  Lock,
  Key,
  Eye,
  EyeOff,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  User,
  Clock,
  Trash2,


  Ban } from
'lucide-react';
import {
  Input as RawInput,
  Select as RawSelect,
  Button as RawButton,
  Checkbox as RawCheckbox,
  Badge as RawBadge,
  SegmentedControl as RawSegmentedControl,
  MacOSCard,
} from '../ui/macos';
const Input = RawInput as unknown as React.ComponentType<Record<string, unknown>>;
const Select = RawSelect as unknown as React.ComponentType<Record<string, unknown>>;
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Checkbox = RawCheckbox as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const SegmentedControl = RawSegmentedControl as unknown as React.ComponentType<Record<string, unknown>>;
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const SecuritySettings = ({
  settings = {},
  onSave,
  loading = false
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState({
    // Пароль
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',

    // Двухфакторная аутентификация
    twoFactorEnabled: false,
    twoFactorMethod: 'sms', // sms, email, app

    // Сессии
    maxSessions: 5,
    sessionTimeout: 30, // минуты
    autoLogout: true,

    // Безопасность
    passwordMinLength: 8,
    passwordRequireUppercase: true,
    passwordRequireNumbers: true,
    passwordRequireSymbols: true,
    passwordExpiryDays: 90,

    // IP ограничения
    allowedIPs: [],
    blockSuspiciousIPs: true,
    maxLoginAttempts: 5,
    lockoutDuration: 15, // минуты

    // Аудит
    logAllActions: true,
    logRetentionDays: 365,
    alertOnSuspiciousActivity: true,

    // Резервное копирование
    autoBackup: true,
    backupFrequency: 'daily', // daily, weekly, monthly
    backupRetention: 30, // дни
    encryptBackups: true
  } as any);

  const [errors, setErrors] = useState({} as any);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('password');
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });

  const [activeSessions] = useState([]);
  const [securityLogs] = useState([]);

  // Инициализация формы
  useEffect(() => {
    if (settings && Object.keys(settings).length > 0) {
      setFormData((prev) => ({ ...prev, ...settings }));
    }
  }, [settings]);

  const validatePasswordForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.currentPassword) {
      newErrors.currentPassword = t('admin2.ss_err_current_required');
    }

    if (!formData.newPassword) {
      newErrors.newPassword = t('admin2.ss_err_new_required');
    } else if (formData.newPassword.length < formData.passwordMinLength) {
      newErrors.newPassword = t('admin2.ss_err_new_min_length', { min: formData.passwordMinLength });
    } else if (formData.passwordRequireUppercase && !/[A-Z]/.test(formData.newPassword)) {
      newErrors.newPassword = t('admin2.ss_err_new_uppercase');
    } else if (formData.passwordRequireNumbers && !/\d/.test(formData.newPassword)) {
      newErrors.newPassword = t('admin2.ss_err_new_numbers');
    } else if (formData.passwordRequireSymbols && !/[!@#$%^&*(),.?":{}|<>]/.test(formData.newPassword)) {
      newErrors.newPassword = t('admin2.ss_err_new_symbols');
    }

    if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = t('admin2.ss_err_confirm_mismatch');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (activeTab === 'password' && !validatePasswordForm()) return;

    // Defensive check for onSave prop
    if (typeof onSave !== 'function') {
      logger.warn('SecuritySettings: onSave prop is not provided or not a function');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSave(formData, activeTab);
    } catch (error) {
      logger.error('Ошибка сохранения настроек безопасности:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => ({ ...prev, [field]: null }));
    }
  };

  const togglePasswordVisibility = (field) => {
    setShowPasswords((prev) => ({ ...prev, [field]: !prev[field] }));
  };

  const terminateSession = (sessionId) => {
    // Логика завершения сессии
    logger.log('Terminating session:', sessionId);
  };

  const terminateAllOtherSessions = () => {
    // Логика завершения всех других сессий
    logger.log('Terminating all other sessions');
  };

  const getStatusIcon = (status) => {
    const iconMap = {
      success: CheckCircle,
      failed: AlertCircle,
      blocked: Ban
    };
    return iconMap[status] || AlertCircle;
  };

  const getStatusColor = (status) => {
    const colorMap = {
      success: 'var(--mac-success)',
      failed: 'var(--mac-danger)',
      blocked: 'var(--mac-warning)'
    };
    return colorMap[status] || 'var(--mac-text-secondary)';
  };

  const getStatusLabel = (status) => {
    const labelMap = {
      success: t('admin2.ss_status_success'),
      failed: t('admin2.ss_status_failed'),
      blocked: t('admin2.ss_status_blocked')
    };
    return labelMap[status] || status;
  };

  const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const tabs = [
  { id: 'password', label: t('admin2.ss_tab_password'), icon: Lock },
  { id: 'two-factor', label: '2FA', icon: Shield },
  { id: 'sessions', label: t('admin2.ss_tab_sessions'), icon: User },
  { id: 'security', label: t('admin2.ss_tab_policies'), icon: Key }, // Sprint 5: was 'Безопасность' (tautology inside SecuritySettings)
  { id: 'audit', label: t('admin2.ss_tab_audit'), icon: Clock }];


  return (
    <div className="flex flex-col gap-6">
      {/* Вкладки */}
      <SegmentedControl
        value={activeTab}
        onChange={(v: unknown) => setActiveTab(String(v))}
        options={tabs.map(({ id, label, icon: TabIcon }) => ({
          value: id,
          label: (
            <span className="admin-inline-flex-ai-center-gap-6">
              <TabIcon className="w-3.5 h-3.5" />
              {label}
            </span>
          )
        }))}
        size="large"
        className="admin-wrap-rgap-4" />
      

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* Смена пароля */}
        {activeTab === 'password' &&
        <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-mb-20-primary">
              {t('admin2.ss_title_change_password')}
            </h3>
            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_current_password')}
                </label>
                <div className="admin-pos-relative">
                  <Input
                  type={showPasswords.current ? 'text' : 'password'}
                  value={formData.currentPassword}
                  onChange={(e) => handleChange('currentPassword', e.target.value)}
                  placeholder={t('admin2.ss_ph_current_password')}
                  autoComplete="current-password"
                  className="admin-pl-40-pr-40" />
                
                  <Lock className="admin-pos-absolute-left-12-top-50pct-transform-translateY-50-w-16-h-16-tertiary" />
                  <button
                  type="button"
                  onClick={() => togglePasswordVisibility('current')}
                  aria-label={showPasswords.current ? t('admin2.ss_aria_hide_current') : t('admin2.ss_aria_show_current')}
                  className="admin-pos-absolute-right-12-top-50pct-transform-translateY-50-background-785252--35889c36">
                  
                    {showPasswords.current ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.currentPassword &&
              <p className="admin-sm-danger-mt-4-flex-ai-center-gap-4">
                    <AlertCircle className="w-4 h-4" />
                    {errors.currentPassword}
                  </p>
              }
              </div>

              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_new_password')}
                </label>
                <div className="admin-pos-relative">
                  <Input
                  type={showPasswords.new ? 'text' : 'password'}
                  value={formData.newPassword}
                  onChange={(e) => handleChange('newPassword', e.target.value)}
                  placeholder={t('admin2.ss_ph_new_password')}
                  autoComplete="new-password"
                  className="admin-pl-40-pr-40" />
                
                  <Key className="admin-pos-absolute-left-12-top-50pct-transform-translateY-50-w-16-h-16-tertiary" />
                  <button
                  type="button"
                  onClick={() => togglePasswordVisibility('new')}
                  aria-label={showPasswords.new ? t('admin2.ss_aria_hide_new') : t('admin2.ss_aria_show_new')}
                  className="admin-pos-absolute-right-12-top-50pct-transform-translateY-50-background-785252--35889c36">
                  
                    {showPasswords.new ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.newPassword &&
              <p className="admin-sm-danger-mt-4-flex-ai-center-gap-4">
                    <AlertCircle className="w-4 h-4" />
                    {errors.newPassword}
                  </p>
              }
              </div>

              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_confirm_password')}
                </label>
                <div className="admin-pos-relative">
                  <Input
                  type={showPasswords.confirm ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={(e) => handleChange('confirmPassword', e.target.value)}
                  placeholder={t('admin2.ss_ph_confirm_password')}
                  autoComplete="new-password"
                  className="admin-pl-40-pr-40" />
                
                  <Key className="admin-pos-absolute-left-12-top-50pct-transform-translateY-50-w-16-h-16-tertiary" />
                  <button
                  type="button"
                  onClick={() => togglePasswordVisibility('confirm')}
                  aria-label={showPasswords.confirm ? t('admin2.ss_aria_hide_confirm') : t('admin2.ss_aria_show_confirm')}
                  className="admin-pos-absolute-right-12-top-50pct-transform-translateY-50-background-785252--35889c36">
                  
                    {showPasswords.confirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.confirmPassword &&
              <p className="admin-sm-danger-mt-4-flex-ai-center-gap-4">
                    <AlertCircle className="w-4 h-4" />
                    {errors.confirmPassword}
                  </p>
              }
              </div>
            </div>
          </MacOSCard>
        }

        {/* Двухфакторная аутентификация */}
        {activeTab === 'two-factor' &&
        <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-mb-20-primary">
              {t('admin2.ss_title_2fa')}
            </h3>
            <div className="flex flex-col gap-4">
              <div className="admin-flex-ai-center-jc-between-p-16-radius-var--mac-radius-md-bd-1solidvar-mac--d38da58b">
                <div>
                  <h4 className="admin-base-med-primary-mb-4">
                    {t('admin2.ss_2fa_enable_title')}
                  </h4>
                  <p className="admin-sm-secondary-m-0">
                    {t('admin2.ss_2fa_enable_desc')}
                  </p>
                </div>
                <Checkbox
                checked={formData.twoFactorEnabled}
                onChange={(checked) => handleChange('twoFactorEnabled', checked)} />
              
              </div>

              {formData.twoFactorEnabled &&
            <div>
                  <label className="admin-block-sm-med-mb-8-primary">
                    {t('admin2.ss_label_2fa_method')}
                  </label>
                  <Select
                value={formData.twoFactorMethod}
                onChange={(value) => handleChange('twoFactorMethod', value)}
                options={[
                { value: 'sms', label: 'SMS' },
                { value: 'email', label: 'Email' },
                { value: 'app', label: t('admin2.ss_2fa_method_app') }]
                }
                placeholder={t('admin2.ss_ph_2fa_method')}></Select>
              
                </div>
            }
            </div>
          </MacOSCard>
        }

        {/* Активные сессии */}
        {activeTab === 'sessions' &&
        <MacOSCard className="p-6">
            <div className="admin-flex-ai-center-jc-between-mb-20">
              <h3 className="admin-lg-semi-primary-m-0">
                {t('admin2.ss_title_sessions')}
              </h3>
              <Button
              variant="outline"
              onClick={terminateAllOtherSessions}
              disabled={activeSessions.length === 0}
              size="small">
              
                <Trash2 className="w-4 h-4 mr-2" />
                {t('admin2.ss_btn_terminate_all_others')}
              </Button>
            </div>

            <div className="flex flex-col gap-3">
              {activeSessions.length === 0 &&
              <p className="admin-sm-secondary-m-0">
                {t('admin2.ss_sessions_empty')}
              </p>
              }
              {activeSessions.map((session) =>
            <div key={session.id} className="admin-flex-ai-center-jc-between-p-16-radius-var--mac-radius-md-bd-1solidvar-mac--d38da58b">
                  <div className="admin-flex-ai-center-gap-16">
                    <div className="admin-w-40-h-40-radius-50pct-flex-ai-center-jc-center-bg-blue">
                      <User className="admin-w-20-h-20-white" />
                    </div>
                    <div>
                      <p className="admin-base-med-primary-m-0-flex-ai-center-gap-8">
                        {session.device}
                        {session.current &&
                    <Badge variant="success" size="small">{t('admin2.ss_session_current_badge')}</Badge>
                    }
                      </p>
                      <p className="admin-sm-secondary-m-4px000">
                        {session.location} • {session.ip}
                      </p>
                      <p className="admin-xs-tertiary-m-4px000">
                        {t('admin2.ss_session_last_activity', { datetime: formatDateTime(session.lastActive) })}
                      </p>
                    </div>
                  </div>

                  {!session.current &&
              <Button
                variant="outline"
                size="small"
                onClick={() => terminateSession(session.id)}
                title="Terminate this session"
                aria-label="Terminate this session"
                className="admin-danger-bd-danger">
                
                      <Trash2 className="w-4 h-4" />
                    </Button>
              }
                </div>
            )}
            </div>
          </MacOSCard>
        }

        {/* Настройки безопасности */}
        {activeTab === 'security' &&
        <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-mb-20-primary">
              {t('admin2.ss_title_security_settings')}
            </h3>
            <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16-mb-24">
              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_password_min_length')}
                </label>
                <Input
                type="number"
                value={formData.passwordMinLength}
                onChange={(e) => handleChange('passwordMinLength', parseInt(e.target.value))}
                min="6"
                max="32" />
              
              </div>

              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_password_expiry_days')}
                </label>
                <Input
                type="number"
                value={formData.passwordExpiryDays}
                onChange={(e) => handleChange('passwordExpiryDays', parseInt(e.target.value))}
                min="30"
                max="365" />
              
              </div>

              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_max_login_attempts')}
                </label>
                <Input
                type="number"
                value={formData.maxLoginAttempts}
                onChange={(e) => handleChange('maxLoginAttempts', parseInt(e.target.value))}
                min="3"
                max="10" />
              
              </div>

              <div>
                <label className="admin-block-sm-med-mb-8-primary">
                  {t('admin2.ss_label_lockout_duration')}
                </label>
                <Input
                type="number"
                value={formData.lockoutDuration}
                onChange={(e) => handleChange('lockoutDuration', parseInt(e.target.value))}
                min="5"
                max="60" />
              
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <Checkbox
              checked={formData.passwordRequireUppercase}
              onChange={(checked) => handleChange('passwordRequireUppercase', checked)}
              label={t('admin2.ss_label_require_uppercase')} />
            

              <Checkbox
              checked={formData.passwordRequireNumbers}
              onChange={(checked) => handleChange('passwordRequireNumbers', checked)}
              label={t('admin2.ss_label_require_numbers')} />
            

              <Checkbox
              checked={formData.passwordRequireSymbols}
              onChange={(checked) => handleChange('passwordRequireSymbols', checked)}
              label={t('admin2.ss_label_require_symbols')} />
            

              <Checkbox
              checked={formData.blockSuspiciousIPs}
              onChange={(checked) => handleChange('blockSuspiciousIPs', checked)}
              label={t('admin2.ss_label_block_suspicious_ips')} />
            
            </div>
          </MacOSCard>
        }

        {/* Логи безопасности */}
        {activeTab === 'audit' &&
        <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-mb-20-primary">
              {t('admin2.ss_title_audit_logs')}
            </h3>

            <div className="flex flex-col gap-3">
              {securityLogs.length === 0 &&
              <p className="admin-sm-secondary-m-0">
                {t('admin2.ss_audit_logs_empty')}
              </p>
              }
              {securityLogs.map((log) => {
              const StatusIcon = getStatusIcon(log.status);
              return (
                <div key={log.id} className="admin-flex-ai-center-jc-between-p-16-radius-var--mac-radius-md-bd-1solidvar-mac--d38da58b">
                    <div className="admin-flex-ai-center-gap-16">
                      <StatusIcon className="admin-w-20-h-20" style={{ '--admin-color': getStatusColor(log.status) }} />
                      <div>
                        <p className="admin-base-med-primary-m-0">
                          {log.action}
                        </p>
                        <p className="admin-sm-secondary-m-4px000">
                          {log.user} • {log.ip}
                        </p>
                        <p className="admin-xs-tertiary-m-4px000">
                          {formatDateTime(log.timestamp)}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center justify-center gap-2">
                      <Badge
                      variant={log.status === 'success' ? 'success' : log.status === 'failed' ? 'error' : 'warning'}
                      size="small">
                      
                        {getStatusLabel(log.status)}
                      </Badge>
                      <span className="admin-xs-tertiary">
                        {log.details}
                      </span>
                    </div>
                  </div>);

            })}
            </div>
          </MacOSCard>
        }

        {/* Кнопки действий */}
        <div className="admin-flex-ai-center-jc-between-pt-24-bordertop-6787ca">
          <div className="text-sm text-[var(--mac-text-secondary)]">
            {t('admin2.ss_save_hint')}
          </div>

          <div className="admin-flex-center-12">
            <Button
              variant="outline"
              onClick={() => {
                // P1 fix: was window.location.reload() — killed SPA state.
                // Now resets the form to the last-loaded settings.
                setFormData(settings || {});
              }}
              disabled={isSubmitting}>
              
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('admin2.ss_btn_reset')}
            </Button>

            <Button
              type="submit"
              disabled={isSubmitting || loading}
              loading={isSubmitting}>
              
              <Save className="w-4 h-4 mr-2" />
              {t('admin2.ss_btn_save')}
            </Button>
          </div>
        </div>
      </form>
    </div>);

};

export default SecuritySettings;

SecuritySettings.propTypes = {
  settings: PropTypes.object,
  onSave: PropTypes.func,
  loading: PropTypes.bool,
};
