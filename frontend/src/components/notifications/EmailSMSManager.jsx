import { useTranslation } from '../../i18n/useTranslation';
import { api } from '../../api/client';
import { useEffect, useMemo, useState } from 'react';
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

const pageStyles = {
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--mac-spacing-4)',
  width: '100%',
  minWidth: 0,
  padding: 'clamp(12px, 2vw, 20px)'
};

const headerStyles = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
  gap: 'var(--mac-spacing-3)',
  flexWrap: 'wrap'
};

const gridStyles = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
  gap: 'var(--mac-spacing-3)'
};

const formGridStyles = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
  gap: 'var(--mac-spacing-3)'
};

const stackStyles = {
  display: 'grid',
  gap: 'var(--mac-spacing-3)'
};

const iconButtonStyle = {
  width: '32px',
  height: '32px',
  padding: 0
};

const priorityOptions = [
  { value: 'normal', label: 'Обычный' },
  { value: 'high', label: 'Высокий' }
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
          subject: emailForm.subject || 'Тестовое письмо',
          message: emailForm.message || 'Это тестовое письмо от Programma Clinic'
        })
      });
      const data = await response.json();
      setTestResults({ type: 'email', ...data });
    } catch (error) {
      logger.error('Ошибка отправки тестового email:', error);
      setTestResults({ type: 'email', success: false, message: 'Ошибка отправки' });
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
          message: smsForm.message || 'Тестовое SMS от Programma Clinic'
        })
      });
      const data = await response.json();
      setTestResults({ type: 'sms', ...data });
    } catch (error) {
      logger.error('Ошибка отправки тестового SMS:', error);
      setTestResults({ type: 'sms', success: false, message: 'Ошибка отправки' });
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
      setTestResults({ type: 'bulk', success: false, message: 'Ошибка рассылки' });
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
    { value: 'overview', label: <TabLabel icon={BarChart3} text="Обзор" /> },
    { value: 'email', label: <TabLabel icon={Mail} text="Email" /> },
    { value: 'sms', label: <TabLabel icon={MessageSquare} text="SMS" /> },
    { value: 'bulk', label: <TabLabel icon={Users} text="Массовые" /> },
    { value: 'templates', label: <TabLabel icon={FileText} text="Шаблоны" /> },
    { value: 'settings', label: <TabLabel icon={Settings} text="Настройки" /> }
  ], []);

  const emailTemplateOptions = useMemo(() => [
    { value: '', label: 'Выберите шаблон' },
    ...templates.email.map((template) => ({ value: template.name, label: template.title }))
  ], [templates.email]);

  const smsTemplateOptions = useMemo(() => [
    { value: '', label: 'Выберите шаблон' },
    ...templates.sms.map((template) => ({ value: template.name, label: template.title }))
  ], [templates.sms]);

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
    const label = testResults.type === 'email' ? 'Email' : testResults.type === 'sms' ? 'SMS' : 'Массовая рассылка';

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

  const renderStatCard = ({ title, value, detail, icon: Icon, tone = 'blue' }) => {
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
              {value}
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
          <AppLoading title="Загрузка статистики..." />
        </Card>
      ) : statistics ? (
        <div style={gridStyles}>
          {renderStatCard({
            title: 'Email отправлено',
            value: statistics.emails_sent || 0,
            detail: `Успешность: ${statistics.email_success_rate?.toFixed(1) || 0}%`,
            icon: Mail,
            tone: 'blue'
          })}
          {renderStatCard({
            title: 'SMS отправлено',
            value: statistics.sms_sent || 0,
            detail: `Успешность: ${statistics.sms_success_rate?.toFixed(1) || 0}%`,
            icon: MessageSquare,
            tone: 'green'
          })}
          {renderStatCard({
            title: 'Email ошибки',
            value: statistics.emails_failed || 0,
            icon: AlertCircle,
            tone: 'red'
          })}
          {renderStatCard({
            title: 'SMS ошибки',
            value: statistics.sms_failed || 0,
            icon: AlertCircle,
            tone: 'orange'
          })}
        </div>
      ) : (
        <Card padding="small">
          <AppEmpty title="Статистика недоступна" description="Данные появятся после успешной загрузки." />
        </Card>
      )}

      <div style={gridStyles}>
        <ActionCard
          icon={Mail}
          title="Тест Email"
          description="Отправить тестовое письмо"
          actionLabel="Перейти к тестированию"
          onAction={() => setActiveTab('email')}
          variant="primary"
        />
        <ActionCard
          icon={MessageSquare}
          title="Тест SMS"
          description="Отправить тестовое SMS"
          actionLabel="Перейти к тестированию"
          onAction={() => setActiveTab('sms')}
          variant="success"
        />
        <ActionCard
          icon={Users}
          title="Массовые рассылки"
          description="Отправить уведомления группе"
          actionLabel="Перейти к рассылкам"
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
        <CardTitle>Отправка Email</CardTitle>
        <CardDescription>Проверьте доставку письма на один адрес</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Input
            type="email"
            label="Получатель"
            aria-label="Email recipient"
            value={emailForm.to}
            onChange={(event) => setEmailForm({ ...emailForm, to: event.target.value })}
            placeholder="example@email.com"
          />
          <Input
            type="text"
            label="Тема"
            aria-label="Email subject"
            value={emailForm.subject}
            onChange={(event) => setEmailForm({ ...emailForm, subject: event.target.value })}
            placeholder="Тема письма"
          />
          <Select
            label="Шаблон"
            value={emailForm.template}
            onChange={(value) => setEmailForm({ ...emailForm, template: value })}
            options={emailTemplateOptions}
          />
          <Select
            label="Приоритет"
            value={emailForm.priority}
            onChange={(value) => setEmailForm({ ...emailForm, priority: value })}
            options={priorityOptions}
          />
        </div>
        <Textarea
          label="Сообщение"
          aria-label="Email message"
          value={emailForm.message}
          onChange={(event) => setEmailForm({ ...emailForm, message: event.target.value })}
          minRows={4}
          placeholder="Текст сообщения"
        />
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="primary" onClick={sendTestEmail} disabled={loading || !emailForm.to} loading={loading && activeTab === 'email'}>
            {loading && activeTab === 'email' ? 'Отправка...' : 'Отправить тест'}
          </Button>
          <Button variant="secondary" onClick={clearEmailForm}>
            Очистить
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderSMSForm = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>Отправка SMS</CardTitle>
        <CardDescription>Проверьте доставку SMS на один номер</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Input
            type="tel"
            label="Номер телефона"
            aria-label="SMS phone number"
            value={smsForm.phone}
            onChange={(event) => setSmsForm({ ...smsForm, phone: event.target.value })}
            placeholder="+998901234567"
          />
          <Input
            type="text"
            label="Отправитель"
            aria-label="SMS sender"
            value={smsForm.sender}
            onChange={(event) => setSmsForm({ ...smsForm, sender: event.target.value })}
            placeholder="Clinic"
          />
          <Select
            label="Шаблон"
            value={smsForm.template}
            onChange={(value) => setSmsForm({ ...smsForm, template: value })}
            options={smsTemplateOptions}
          />
          <Select
            label="Приоритет"
            value={smsForm.priority}
            onChange={(value) => setSmsForm({ ...smsForm, priority: value })}
            options={priorityOptions}
          />
        </div>
        <Textarea
          label="Сообщение"
          aria-label="SMS message"
          value={smsForm.message}
          onChange={(event) => setSmsForm({ ...smsForm, message: event.target.value })}
          minRows={3}
          placeholder="Текст SMS сообщения"
        />
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="success" onClick={sendTestSMS} disabled={loading || !smsForm.phone} loading={loading && activeTab === 'sms'}>
            {loading && activeTab === 'sms' ? 'Отправка...' : 'Отправить тест'}
          </Button>
          <Button variant="secondary" onClick={clearSMSForm}>
            Очистить
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderBulkForm = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>Массовые рассылки</CardTitle>
        <CardDescription>Список получателей можно разделять строками, запятыми или точками с запятой</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={formGridStyles}>
          <Select
            label="Тип рассылки"
            value={bulkForm.type}
            onChange={(value) => setBulkForm({ ...bulkForm, type: value, template: '' })}
            options={bulkTypeOptions}
          />
          <Input
            type="number"
            label="Размер батча"
            aria-label="Bulk batch size"
            value={bulkForm.batchSize}
            onChange={(event) => setBulkForm({ ...bulkForm, batchSize: Number.parseInt(event.target.value, 10) || 1 })}
            min="1"
            max="1000"
          />
          <Input
            type="number"
            step="0.1"
            label="Задержка между батчами"
            aria-label="Bulk delay between batches"
            value={bulkForm.delay}
            onChange={(event) => setBulkForm({ ...bulkForm, delay: Number.parseFloat(event.target.value) || 0 })}
            min="0"
            max="10"
          />
          <Select
            label="Шаблон"
            value={bulkForm.template}
            onChange={(value) => setBulkForm({ ...bulkForm, template: value })}
            options={currentBulkTemplates}
          />
        </div>

        {bulkForm.type === 'email' && (
          <Input
            type="text"
            label="Тема письма"
            aria-label="Bulk email subject"
            value={bulkForm.subject}
            onChange={(event) => setBulkForm({ ...bulkForm, subject: event.target.value })}
            placeholder="Тема письма"
          />
        )}

        <Textarea
          label={`Получатели (${bulkForm.recipients.length})`}
          aria-label="Bulk recipients"
          value={bulkForm.recipientsText}
          onChange={(event) => updateBulkRecipients(event.target.value)}
          minRows={4}
          placeholder={bulkForm.type === 'email' ? 'patient@example.com, team@example.com' : '+998901234567, +998901234568'}
        />

        <Textarea
          label="Сообщение"
          aria-label="Bulk message"
          value={bulkForm.message}
          onChange={(event) => setBulkForm({ ...bulkForm, message: event.target.value })}
          minRows={4}
          placeholder="Текст сообщения"
        />

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button
            variant="primary"
            onClick={sendBulkNotification}
            disabled={loading || bulkForm.recipients.length === 0}
            loading={loading && activeTab === 'bulk'}
          >
            {loading && activeTab === 'bulk' ? 'Отправка...' : 'Запустить рассылку'}
          </Button>
          <Button variant="secondary" onClick={clearBulkForm}>
            Очистить
          </Button>
        </div>
      </CardContent>
    </Card>
  );

  const renderTemplates = () => (
    <div style={gridStyles}>
      <TemplateColumn title="Email шаблоны" icon={Mail} templates={templates.email} tone="var(--mac-accent-blue)" />
      <TemplateColumn title="SMS шаблоны" icon={MessageSquare} templates={templates.sms} tone="var(--mac-success)" />
    </div>
  );

  const renderSettings = () => (
    <Card padding="default">
      <CardHeader>
        <CardTitle>Настройки Email/SMS</CardTitle>
        <CardDescription>Параметры провайдеров и технические действия</CardDescription>
      </CardHeader>
      <CardContent style={stackStyles}>
        <div style={gridStyles}>
          <Card padding="small" shadow="small">
            <CardHeader>
              <CardTitle>Email настройки</CardTitle>
            </CardHeader>
            <CardContent style={stackStyles}>
              <Input type="text" label="SMTP сервер" aria-label="SMTP server" placeholder="smtp.gmail.com" />
              <Input type="number" label="Порт" aria-label="SMTP port" placeholder="587" />
              <Input type="email" label="Email" aria-label="SMTP email" placeholder="clinic@example.com" />
            </CardContent>
          </Card>

          <Card padding="small" shadow="small">
            <CardHeader>
              <CardTitle>SMS настройки</CardTitle>
            </CardHeader>
            <CardContent style={stackStyles}>
              <Input type="url" label="API URL" aria-label="SMS API URL" placeholder="https://api.sms-provider.com" />
              <Input type="password" label="API ключ" aria-label="SMS API key" placeholder="••••••••••••••••" />
              <Input type="text" label="Отправитель" aria-label="SMS default sender" placeholder="Clinic" />
            </CardContent>
          </Card>
        </div>

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
          <Button variant="primary">Сохранить настройки</Button>
          <Button variant="danger" onClick={resetStatistics} disabled={loading}>
            Сбросить статистику
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
            Email/SMS уведомления
          </h1>
          <p style={{ margin: '6px 0 0', color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-base)' }}>
            Управление тестовыми отправками, шаблонами и массовыми рассылками
          </p>
        </div>
        <Button variant="secondary" onClick={loadStatistics} disabled={loading}>
          <BarChart3 size={16} />
          Обновить статистику
        </Button>
      </div>

      <Card padding="small" shadow="small">
        <CardContent style={{ overflowX: 'auto' }}>
          <SegmentedControl value={activeTab} onChange={setActiveTab} options={tabs} />
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
      title: 'Действия',
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
          <AppEmpty title="Шаблоны не найдены" description="Список появится после загрузки шаблонов." />
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
