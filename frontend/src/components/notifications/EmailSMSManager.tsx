import { useTranslation } from '../../i18n/useTranslation';
import { api } from '../../api/client';
import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import {
  AlertCircle,
  BarChart3,
  CheckCircle,
  Edit,
  Eye,
  FileText,
  Mail,
  MessageSquare,
  Settings,
  Users
} from 'lucide-react';

import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';
import { tokenManager } from '../../utils/tokenManager';
import {
  AppEmpty,
  AppLoading,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Table,
  SegmentedControl,
  Select,
  Textarea,
} from '../ui/macos';

const pageStyles: CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--mac-spacing-4)',
  width: '100%',
  minWidth: 0,
  padding: 'clamp(12px, 2vw, 20px)'
};

const headerStyles: CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 'var(--mac-spacing-3)',
  flexWrap: 'wrap'
};

const gridStyles: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
  gap: 'var(--mac-spacing-3)'
};

const formGridStyles: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
  gap: 'var(--mac-spacing-3)'
};

const stackStyles: CSSProperties = {
  display: 'grid',
  gap: 'var(--mac-spacing-3)'
};

const iconButtonStyle = {
  width: '32px',
  height: '32px',
  padding: 0
};

const priorityOptions = (t) => [
  { value: 'normal', label: t('misc.esm_priority_normal') },
  { value: 'high', label: t('misc.esm_priority_high') }
];

const bulkTypeOptions = [
  { value: 'email', label: 'Email' },
  { value: 'sms', label: 'SMS' }
];

const parseRecipients = (value) =>
  value
    .split(/[\n,;]+/)
    .map((recipient) => recipient.trim())
    .filter(Boolean);

const EmailSMSManager = () => {
  useTheme();
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState(null);
  const [templates, setTemplates] = useState({ email: [], sms: [] });
  const [testResults, setTestResults] = useState(null);

  const [emailForm, setEmailForm] = useState({
    to: '',
    subject: '',
    template: '',
    message: '',
    priority: 'normal'
  });

  const [smsForm, setSmsForm] = useState({
    phone: '',
    message: '',
    template: '',
    sender: '',
    priority: 'normal'
  });

  const [bulkForm, setBulkForm] = useState({
    type: 'email',
    recipients: [],
    recipientsText: '',
    subject: '',
    template: '',
    message: '',
    batchSize: 50,
    delay: 1.0
  });

  useEffect(() => {
    loadStatistics();
    loadTemplates();
  }, []);

  const loadStatistics = async () => {
    try {
      setLoading(true);
      const response = await fetch('/email-sms/statistics', {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      if (data.success) {
        setStatistics(data.statistics);
      }
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const response = await fetch('/email-sms/templates', {
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      if (data.success) {
        setTemplates(data.templates || { email: [], sms: [] });
      }
    } catch (error) {
      logger.error('Ошибка загрузки шаблонов:', error);
    }
  };

  const sendTestEmail = async () => {
    try {
      setLoading(true);
      const response = await fetch('/email-sms/test-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          to_email: emailForm.to,
          subject: emailForm.subject || t('misc.esm_test_email_subject_default'),
          message: emailForm.message || t('misc.esm_test_email_message_default')
        })
      });
      const data = await response.json();
      setTestResults({ type: 'email', ...data });
    } catch (error) {
      logger.error('Ошибка отправки тестового email:', error);
      setTestResults({ type: 'email', success: false, message: t('misc.esm_error_sending') });
    } finally {
      setLoading(false);
    }
  };

  const sendTestSMS = async () => {
    try {
      setLoading(true);
      const response = await fetch('/email-sms/test-sms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          phone: smsForm.phone,
          message: smsForm.message || t('misc.esm_test_sms_message_default')
        })
      });
      const data = await response.json();
      setTestResults({ type: 'sms', ...data });
    } catch (error) {
      logger.error('Ошибка отправки тестового SMS:', error);
      setTestResults({ type: 'sms', success: false, message: t('misc.esm_error_sending') });
    } finally {
      setLoading(false);
    }
  };

  const sendBulkNotification = async () => {
    try {
      setLoading(true);
      const endpoint = bulkForm.type === 'email' ? 'send-bulk-email' : 'send-bulk-sms';
      const response = await fetch(`/email-sms/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          recipients: bulkForm.recipients,
          subject: bulkForm.subject,
          message: bulkForm.message,
          template_name: bulkForm.template,
          batch_size: bulkForm.batchSize,
          delay_between_batches: bulkForm.delay
        })
      });
      const data = await response.json();
      setTestResults({ type: 'bulk', ...data });
    } catch (error) {
      logger.error('Ошибка массовой рассылки:', error);
      setTestResults({ type: 'bulk', success: false, message: t('misc.esm_error_bulk') });
    } finally {
      setLoading(false);
    }
  };

  const resetStatistics = async () => {
    try {
      setLoading(true);
      const response = await fetch('/email-sms/reset-statistics', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      if (data.success) {
        await loadStatistics();
      }
    } catch (error) {
      logger.error('Ошибка сброса статистики:', error);
    } finally {
      setLoading(false);
    }
  };

  const tabs = useMemo(() => [
    { value: 'overview', label: <TabLabel icon={BarChart3} text={t('misc.esm_tab_overview')} /> },
    { value: 'email', label: <TabLabel icon={Mail} text="Email" /> },
    { value: 'sms', label: <TabLabel icon={MessageSquare} text="SMS" /> },
    { value: 'bulk', label: <TabLabel icon={Users} text={t('misc.esm_tab_bulk')} /> },
    { value: 'templates', label: <TabLabel icon={FileText} text={t('misc.esm_tab_templates')} /> },
    { value: 'settings', label: <TabLabel icon={Settings} text={t('misc.esm_tab_settings')} /> }
  ], [t]);

  const emailTemplateOptions = useMemo(() => [
    { value: '', label: t('misc.esm_select_template') },
    ...templates.email.map((template) => ({ value: template.name, label: template.title }))
  ], [templates.email, t]);

  const smsTemplateOptions = useMemo(() => [
    { value: '', label: t('misc.esm_select_template') },
    ...templates.sms.map((template) => ({ value: template.name, label: template.title }))
  ], [templates.sms, t]);

  const currentBulkTemplates = bulkForm.type === 'email' ? emailTemplateOptions : smsTemplateOptions;

  const updateBulkRecipients = (value) => {
    setBulkForm((prev) => ({
      ...prev,
      recipientsText: value,
      recipients: parseRecipients(value)
    }));
  };

  const clearEmailForm = () => {
    setEmailForm({ to: '', subject: '', template: '', message: '', priority: 'normal' });
  };

  const clearSMSForm = () => {
    setSmsForm({ phone: '', message: '', template: '', sender: '', priority: 'normal' });
  };

  const clearBulkForm = () => {
    setBulkForm({
      type: 'email',
      recipients: [],
      recipientsText: '',
      subject: '',
      template: '',
      message: '',
      batchSize: 50,
      delay: 1.0
    });
  };

  const renderTestResult = () => {
    if (!testResults) return null;

    const isSuccess = Boolean(testResults.success);
    const Icon = isSuccess ? CheckCircle : AlertCircle;
    const label = testResults.type === 'email' ? 'Email' : testResults.type === 'sms' ? 'SMS' : t('misc.esm_bulk_label');

    return (
      <Card
        padding="small"
        style={{
          borderColor: isSuccess ? 'var(--mac-success)' : 'var(--mac-danger)',
          background: isSuccess ? 'rgba(52, 199, 89, 0.08)' : 'rgba(255, 59, 48, 0.08)'
        }}
      >
        <CardContent style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <Icon size={20} style={{ color: isSuccess ? 'var(--mac-success)' : 'var(--mac-danger)', marginTop: '2px' }} />
          <div>
            <strong>{label}</strong>
            <p style={{ margin: '4px 0 0', color: 'var(--mac-text-secondary)' }}>
              {testResults.message}
            </p>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderStatCard = ({ title, value, detail, icon: Icon, tone = 'blue' }: {
    title: string;
    value: unknown;
    detail?: string;
    icon: import('lucide-react').LucideIcon;
    tone?: 'blue' | 'green' | 'red' | 'orange' | string;
  }) => {
    const toneColor = {
      blue: 'var(--mac-accent-blue)',
      green: 'var(--mac-success)',
      red: 'var(--mac-danger)',
      orange: 'var(--mac-warning)'
    }[tone];

    return (
      <Card padding="small" shadow="small">
        <CardContent style={{ display: 'flex', justifyContent: 'space-between', gap: 'var(--mac-spacing-3)', alignItems: 'flex-start' }}>
          <div>
            <p style={{ margin: 0, color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-semibold)' }}>{title}</p>
            <strong style={{ display: 'block', marginTop: 'var(--mac-spacing-2)', fontSize: '26px', color: 'var(--mac-text-primary)' }}>
              {String(value ?? '')}
            </strong>
            {detail && (
              <span style={{ display: 'block', marginTop: 'var(--mac-spacing-1)', color: toneColor, fontSize: 'var(--mac-font-size-xs)' }}>
                {detail}
              </span>
            )}
          </div>
          <Icon size={30} style={{ color: toneColor }} />
        </CardContent>
      </Card>
    );
  };

  const renderOverview = () => (
    <div style={stackStyles}>
      {loading && !statistics ? (
        <Card padding="small">
          <AppLoading title={t('misc.esm_loading_stats')} />
        </Card>
      ) : statistics ? (
        <div style={gridStyles}>
          {renderStatCard({
            title: t('misc.esm_stat_email_sent'),
            value: statistics.emails_sent || 0,
            detail: t('misc.esm_stat_success_rate', { rate: statistics.email_success_rate?.toFixed(1) || 0 }),
            icon: Mail,
            tone: 'blue'
          })}
          {renderStatCard({
            title: t('misc.esm_stat_sms_sent'),
            value: statistics.sms_sent || 0,
            detail: t('misc.esm_stat_success_rate', { rate: statistics.sms_success_rate?.toFixed(1) || 0 }),
            icon: MessageSquare,
            tone: 'green'
          })}
          {renderStatCard({
            title: t('misc.esm_stat_email_errors'),
            value: statistics.emails_failed || 0,
            icon: AlertCircle,
            tone: 'red'
          })}
          {renderStatCard({
            title: t('misc.esm_stat_sms_errors'),
            value: statistics.sms_failed || 0,
            icon: AlertCircle,
            tone: 'orange'
          })}
        </div>
      ) : (
        <Card padding="small">
          <AppEmpty title={t('misc.esm_stat_unavailable_title')} description={t('misc.esm_stat_unavailable_desc')} />
        </Card>
      )}

      <div style={gridStyles}>
        <ActionCard
          icon={Mail}
          title={t('misc.esm_action_test_email_title')}
          description={t('misc.esm_action_test_email_desc')}
          actionLabel={t('misc.esm_action_go_to_test')}
          onAction={() => setActiveTab('email')}
          variant="primary"
        />
        <ActionCard
          icon={MessageSquare}
          title={t('misc.esm_action_test_sms_title')}
          description={t('misc.esm_action_test_sms_desc')}
          actionLabel={t('misc.esm_action_go_to_test')}
          onAction={() => setActiveTab('sms')}
          variant="success"
        />
        <ActionCard
          icon={Users}
          title={t('misc.esm_action_bulk_title')}
          description={t('misc.esm_action_bulk_desc')}
          actionLabel={t('misc.esm_action_go_to_bulk')}
          onAction={() => setActiveTab('bulk')}
          variant="secondary"
        />
      </div>

      {renderTestResult()}
    </div>
  );

  const renderEmailForm = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>{t('misc.esm_email_form_title')}</CardTitle>
        <CardDescription>{t('misc.esm_email_form_desc')}</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Input
            type="email"
            label={t('misc.esm_label_recipient')}
            aria-label="Email recipient"
            value={emailForm.to}
            onChange={(event) => setEmailForm({ ...emailForm, to: event.target.value })}
            placeholder="example@email.com"
          />
          <Input
            type="text"
            label={t('misc.esm_label_subject')}
            aria-label="Email subject"
            value={emailForm.subject}
            onChange={(event) => setEmailForm({ ...emailForm, subject: event.target.value })}
            placeholder={t('misc.esm_placeholder_subject')}
          />
          <Select
            label={t('misc.esm_label_template')}
            value={emailForm.template}
            onChange={(value: unknown) => setEmailForm({ ...emailForm, template: String(value) })}
            options={emailTemplateOptions}
          />
          <Select
            label={t('misc.esm_label_priority')}
            value={emailForm.priority}
            onChange={(value: unknown) => setEmailForm({ ...emailForm, priority: String(value) })}
            options={priorityOptions(t)}
          />
        </div>
        <Textarea
          label={t('misc.esm_label_message')}
          aria-label="Email message"
          value={emailForm.message}
          onChange={(event) => setEmailForm({ ...emailForm, message: event.target.value })}
          minRows={4}
          placeholder={t('misc.esm_placeholder_message')}
        />
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="primary" onClick={sendTestEmail} disabled={loading || !emailForm.to} loading={loading && activeTab === 'email'}>
            {loading && activeTab === 'email' ? t('misc.esm_sending') : t('misc.esm_send_test')}
          </Button>
          <Button variant="secondary" onClick={clearEmailForm}>
            {t('misc.esm_clear')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderSMSForm = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>{t('misc.esm_sms_form_title')}</CardTitle>
        <CardDescription>{t('misc.esm_sms_form_desc')}</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Input
            type="tel"
            label={t('misc.esm_label_phone')}
            aria-label="SMS phone number"
            value={smsForm.phone}
            onChange={(event) => setSmsForm({ ...smsForm, phone: event.target.value })}
            placeholder="+998901234567"
          />
          <Input
            type="text"
            label={t('misc.esm_label_sender')}
            aria-label="SMS sender"
            value={smsForm.sender}
            onChange={(event) => setSmsForm({ ...smsForm, sender: event.target.value })}
            placeholder="Clinic"
          />
          <Select
            label={t('misc.esm_label_template')}
            value={smsForm.template}
            onChange={(value: unknown) => setSmsForm({ ...smsForm, template: String(value) })}
            options={smsTemplateOptions}
          />
          <Select
            label={t('misc.esm_label_priority')}
            value={smsForm.priority}
            onValueChange={(value) => setSmsForm({ ...smsForm, priority: String(value) })}
            options={priorityOptions(t)}
          />
        </div>
        <Textarea
          label={t('misc.esm_label_message')}
          aria-label="SMS message"
          value={smsForm.message}
          onChange={(event) => setSmsForm({ ...smsForm, message: event.target.value })}
          minRows={3}
          placeholder={t('misc.esm_placeholder_sms_message')}
        />
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="success" onClick={sendTestSMS} disabled={loading || !smsForm.phone} loading={loading && activeTab === 'sms'}>
            {loading && activeTab === 'sms' ? t('misc.esm_sending') : t('misc.esm_send_test')}
          </Button>
          <Button variant="secondary" onClick={clearSMSForm}>
            {t('misc.esm_clear')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderBulkForm = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>{t('misc.esm_bulk_form_title')}</CardTitle>
        <CardDescription>{t('misc.esm_bulk_form_desc')}</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Select
            label={t('misc.esm_label_bulk_type')}
            value={bulkForm.type}
            onValueChange={(value) => setBulkForm({ ...bulkForm, type: String(value), template: '' })}
            options={bulkTypeOptions}
          />
          <Input
            type="number"
            label={t('misc.esm_label_batch_size')}
            aria-label="Bulk batch size"
            value={bulkForm.batchSize}
            onChange={(event) => setBulkForm({ ...bulkForm, batchSize: Number.parseInt(event.target.value, 10) || 1 })}
            min="1"
            max="1000"
          />
          <Input
            type="number"
            step="0.1"
            label={t('misc.esm_label_batch_delay')}
            aria-label="Bulk delay between batches"
            value={bulkForm.delay}
            onChange={(event) => setBulkForm({ ...bulkForm, delay: Number.parseFloat(event.target.value) || 0 })}
            min="0"
            max="10"
          />
          <Select
            label={t('misc.esm_label_template')}
            value={bulkForm.template}
            onValueChange={(value) => setBulkForm({ ...bulkForm, template: String(value) })}
            options={currentBulkTemplates}
          />
        </div>

        {bulkForm.type === 'email' && (
          <Input
            type="text"
            label={t('misc.esm_label_subject')}
            aria-label="Bulk email subject"
            value={bulkForm.subject}
            onChange={(event) => setBulkForm({ ...bulkForm, subject: event.target.value })}
            placeholder={t('misc.esm_placeholder_subject')}
          />
        )}

        <Textarea
          label={t('misc.esm_label_recipients', { count: bulkForm.recipients.length })}
          aria-label="Bulk recipients"
          value={bulkForm.recipientsText}
          onChange={(event) => updateBulkRecipients(event.target.value)}
          minRows={4}
          placeholder={bulkForm.type === 'email' ? 'patient@example.com, team@example.com' : '+998901234567, +998901234568'}
        />

        <Textarea
          label={t('misc.esm_label_message')}
          aria-label="Bulk message"
          value={bulkForm.message}
          onChange={(event) => setBulkForm({ ...bulkForm, message: event.target.value })}
          minRows={4}
          placeholder={t('misc.esm_placeholder_message')}
        />

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button
            variant="primary"
            onClick={sendBulkNotification}
            disabled={loading || bulkForm.recipients.length === 0}
            loading={loading && activeTab === 'bulk'}
          >
            {loading && activeTab === 'bulk' ? t('misc.esm_sending') : t('misc.esm_start_bulk')}
          </Button>
          <Button variant="secondary" onClick={clearBulkForm}>
            {t('misc.esm_clear')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderTemplates = () => (
    <div style={gridStyles}>
      <TemplateColumn title={t('misc.esm_templates_email_title')} icon={Mail} templates={templates.email} tone="var(--mac-accent-blue)" />
      <TemplateColumn title={t('misc.esm_templates_sms_title')} icon={MessageSquare} templates={templates.sms} tone="var(--mac-success)" />
    </div>
  );

  const renderSettings = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>{t('misc.esm_settings_title')}</CardTitle>
        <CardDescription>{t('misc.esm_settings_desc')}</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={gridStyles}>
          <Card padding="small" shadow="small">
            <CardHeader>
              <CardTitle>{t('misc.esm_settings_email_title')}</CardTitle>
            </CardHeader>
            <CardContent style={stackStyles}>
              <Input type="text" label={t('misc.esm_label_smtp_server')} aria-label="SMTP server" placeholder="smtp.gmail.com" />
              <Input type="number" label={t('misc.esm_label_port')} aria-label="SMTP port" placeholder="587" />
              <Input type="email" label="Email" aria-label="SMTP email" placeholder="clinic@example.com" />
            </CardContent>
          </Card>

          <Card padding="small" shadow="small">
            <CardHeader>
              <CardTitle>{t('misc.esm_settings_sms_title')}</CardTitle>
            </CardHeader>
            <CardContent style={stackStyles}>
              <Input type="url" label="API URL" aria-label="SMS API URL" placeholder="https://api.sms-provider.com" />
              <Input type="password" label={t('misc.esm_label_api_key')} aria-label="SMS API key" placeholder="••••••••••••••••" />
              <Input type="text" label={t('misc.esm_label_sender')} aria-label="SMS default sender" placeholder="Clinic" />
            </CardContent>
          </Card>
        </div>

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="primary">{t('misc.esm_save_settings')}</Button>
          <Button variant="danger" onClick={resetStatistics} disabled={loading}>
            {t('misc.esm_reset_stats')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverview();
      case 'email':
        return renderEmailForm();
      case 'sms':
        return renderSMSForm();
      case 'bulk':
        return renderBulkForm();
      case 'templates':
        return renderTemplates();
      case 'settings':
        return renderSettings();
      default:
        return renderOverview();
    }
  };

  return (
    <div style={pageStyles}>
      <div style={headerStyles}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--mac-font-size-3xl)', lineHeight: 1.15, color: 'var(--mac-text-primary)' }}>
            {t('misc.esm_page_title')}
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
            {t('misc.esm_page_subtitle')}
          </p>
        </div>
        <Button variant="secondary" onClick={loadStatistics} disabled={loading}>
          <BarChart3 size={16} />
          {t('misc.esm_refresh_stats')}
        </Button>
      </div>

      <Card padding="small" shadow="small">
        <CardContent style={{ overflowX: 'auto' }}>
          <SegmentedControl value={activeTab} onChange={(v: unknown) => setActiveTab(String(v))} options={tabs} />
        </CardContent>
      </Card>

      {renderTabContent()}
    </div>
  );
};

const TabLabel = ({ icon: Icon, text }) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
    <Icon size={14} />
    {text}
  </span>
);

TabLabel.propTypes = {
  icon: PropTypes.elementType.isRequired,
  text: PropTypes.string.isRequired
};

const ActionCard = ({ icon: Icon, title, description, actionLabel, onAction, variant }) => (
  <Card padding="default" shadow="small">
    <CardContent style={{ display: 'grid', gap: 'var(--mac-spacing-3)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <Icon size={24} style={{ color: variant === 'success' ? 'var(--mac-success)' : 'var(--mac-accent-blue)' }} />
        <h3 style={{ margin: 0, fontSize: 'var(--mac-font-size-xl)' }}>{title}</h3>
      </div>
      <p style={{ margin: 0, color: 'var(--mac-text-secondary)' }}>{description}</p>
      <Button variant={variant} onClick={onAction} fullWidth>
        {actionLabel}
      </Button>
    </CardContent>
  </Card>
);

ActionCard.propTypes = {
  actionLabel: PropTypes.string.isRequired,
  description: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  onAction: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  variant: PropTypes.string.isRequired
};

const TemplateColumn = ({ title, icon: Icon, templates, tone }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const columns = [
    {
      key: 'title',
      title: t('final.col_template'),
      render: (_value, template) => (
        <div style={{ minWidth: '180px' }}>
          <strong>{template.title}</strong>
          <p style={{ margin: '4px 0 0', color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-xs)' }}>
            {template.description}
          </p>
        </div>
      )
    },
    {
      key: 'variables',
      title: t('final.col_variables'),
      render: (_value, template) => (
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-1)', flexWrap: 'wrap' }}>
          {(template.variables || []).map((variable) => (
            <Badge key={variable} size="small" variant="outline">
              {variable}
            </Badge>
          ))}
        </div>
      )
    },
    {
      key: 'actions',
      title: t('misc.esm_col_actions'),
      render: (_value, template) => (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--mac-spacing-2)' }}>
          <Button variant="ghost" size="small" aria-label={`View template ${template.title}`} style={iconButtonStyle}>
            <Eye size={16} />
          </Button>
          <Button variant="ghost" size="small" aria-label={`Edit template ${template.title}`} style={iconButtonStyle}>
            <Edit size={16} />
          </Button>
        </div>
      )
    }
  ];

  return (
    <Card padding="default" shadow="small">
      <CardHeader>
        <CardTitle style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
          <Icon size={20} style={{ color: tone }} />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {templates.length === 0 ? (
          <AppEmpty title={t('misc.esm_templates_empty_title')} description={t('misc.esm_templates_empty_desc')} />
        ) : (
          <Table columns={columns} data={templates} sortable={false} />
        )}
      </CardContent>
    </Card>
  );
};

TemplateColumn.propTypes = {
  icon: PropTypes.elementType.isRequired,
  templates: PropTypes.arrayOf(
    PropTypes.shape({
      description: PropTypes.node,
      name: PropTypes.string,
      title: PropTypes.node,
      variables: PropTypes.arrayOf(PropTypes.string)
    })
  ).isRequired,
  title: PropTypes.string.isRequired,
  tone: PropTypes.string.isRequired
};

export default EmailSMSManager;
