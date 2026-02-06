import React, { useState, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';
import { tokenManager } from '../../utils/tokenManager';
import {
  Mail,
  MessageSquare,
  Send,
  Users,
  BarChart3,
  Settings,
  TestTube,
  CreditCard,
  Calendar,
  FileText,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw,
  Download,
  Upload,
  Eye,
  Edit,
  Trash2,
  Plus,
  Search,
  Filter,
  MoreVertical
} from 'lucide-react';

/**
 * Менеджер Email/SMS уведомлений
 * Управление массовыми рассылками, шаблонами и статистикой
 */
const EmailSMSManager = () => {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState(null);
  const [templates, setTemplates] = useState({ email: [], sms: [] });
  const [testResults, setTestResults] = useState(null);

  // Состояние для форм
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
      const response = await fetch('/api/v1/email-sms/statistics', {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
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
      const response = await fetch('/api/v1/email-sms/templates', {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });
      const data = await response.json();
      if (data.success) {
        setTemplates(data.templates);
      }
    } catch (error) {
      logger.error('Ошибка загрузки шаблонов:', error);
    }
  };

  const sendTestEmail = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/email-sms/test-email', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
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
      const response = await fetch('/api/v1/email-sms/test-sms', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
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
      const response = await fetch(`/api/v1/email-sms/${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
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
      const response = await fetch('/api/v1/email-sms/reset-statistics', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
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

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'email', label: 'Email', icon: Mail },
    { id: 'sms', label: 'SMS', icon: MessageSquare },
    { id: 'bulk', label: 'Массовые рассылки', icon: Users },
    { id: 'templates', label: 'Шаблоны', icon: FileText },
    { id: 'settings', label: 'Настройки', icon: Settings }
  ];

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статистика */}
      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600">Email отправлено</p>
                <p className="text-2xl font-bold text-blue-900">{statistics.emails_sent || 0}</p>
              </div>
              <Mail className="w-8 h-8 text-blue-600" />
            </div>
            <div className="mt-2">
              <span className="text-sm text-blue-600">
                Успешность: {statistics.email_success_rate?.toFixed(1) || 0}%
              </span>
            </div>
          </div>

          <div className="bg-green-50 border border-green-200 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">SMS отправлено</p>
                <p className="text-2xl font-bold text-green-900">{statistics.sms_sent || 0}</p>
              </div>
              <MessageSquare className="w-8 h-8 text-green-600" />
            </div>
            <div className="mt-2">
              <span className="text-sm text-green-600">
                Успешность: {statistics.sms_success_rate?.toFixed(1) || 0}%
              </span>
            </div>
          </div>

          <div className="bg-red-50 border border-red-200 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-600">Email ошибки</p>
                <p className="text-2xl font-bold text-red-900">{statistics.emails_failed || 0}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-red-600" />
            </div>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600">SMS ошибки</p>
                <p className="text-2xl font-bold text-orange-900">{statistics.sms_failed || 0}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-orange-600" />
            </div>
          </div>
        </div>
      )}

      {/* Быстрые действия */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Mail className="w-6 h-6 text-blue-600" />
            <h3 className="text-lg font-semibold">Тест Email</h3>
          </div>
          <p className="text-gray-600 mb-4">Отправить тестовое письмо</p>
          <button
            onClick={() => setActiveTab('email')}
            className="w-full bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            Перейти к тестированию
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <MessageSquare className="w-6 h-6 text-green-600" />
            <h3 className="text-lg font-semibold">Тест SMS</h3>
          </div>
          <p className="text-gray-600 mb-4">Отправить тестовое SMS</p>
          <button
            onClick={() => setActiveTab('sms')}
            className="w-full bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            Перейти к тестированию
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Users className="w-6 h-6 text-purple-600" />
            <h3 className="text-lg font-semibold">Массовые рассылки</h3>
          </div>
          <p className="text-gray-600 mb-4">Отправить уведомления группе</p>
          <button
            onClick={() => setActiveTab('bulk')}
            className="w-full bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors"
          >
            Перейти к рассылкам
          </button>
        </div>
      </div>

      {/* Результаты тестов */}
      {testResults && (
        <div className={`p-4 rounded-lg ${testResults.success
          ? 'bg-green-50 border border-green-200'
          : 'bg-red-50 border border-red-200'
          }`}>
          <div className="flex items-center space-x-2">
            {testResults.success ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600" />
            )}
            <span className={`font-medium ${testResults.success ? 'text-green-800' : 'text-red-800'
              }`}>
              {testResults.type === 'email' ? 'Email' :
                testResults.type === 'sms' ? 'SMS' : 'Массовая рассылка'}
            </span>
          </div>
          <p className={`mt-1 ${testResults.success ? 'text-green-700' : 'text-red-700'
            }`}>
            {testResults.message}
          </p>
        </div>
      )}
    </div>
  );

  const renderEmailForm = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Отправка Email</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Получатель
            </label>
            <input
              type="email"
              value={emailForm.to}
              onChange={(e) => setEmailForm({ ...emailForm, to: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="example@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Тема
            </label>
            <input
              type="text"
              value={emailForm.subject}
              onChange={(e) => setEmailForm({ ...emailForm, subject: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="Тема письма"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Шаблон
            </label>
            <select
              value={emailForm.template}
              onChange={(e) => setEmailForm({ ...emailForm, template: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Выберите шаблон</option>
              {templates.email.map(template => (
                <option key={template.name} value={template.name}>
                  {template.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Приоритет
            </label>
            <select
              value={emailForm.priority}
              onChange={(e) => setEmailForm({ ...emailForm, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="normal">Обычный</option>
              <option value="high">Высокий</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Сообщение
          </label>
          <textarea
            value={emailForm.message}
            onChange={(e) => setEmailForm({ ...emailForm, message: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            placeholder="Текст сообщения"
          />
        </div>

        <div className="mt-6 flex space-x-4">
          <button
            onClick={sendTestEmail}
            disabled={loading || !emailForm.to}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Отправка...' : 'Отправить тест'}
          </button>

          <button
            onClick={() => setEmailForm({
              to: '', subject: '', template: '', message: '', priority: 'normal'
            })}
            className="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600 transition-colors"
          >
            Очистить
          </button>
        </div>
      </div>
    </div>
  );

  const renderSMSForm = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Отправка SMS</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Номер телефона
            </label>
            <input
              type="tel"
              value={smsForm.phone}
              onChange={(e) => setSmsForm({ ...smsForm, phone: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              placeholder="+998901234567"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Отправитель
            </label>
            <input
              type="text"
              value={smsForm.sender}
              onChange={(e) => setSmsForm({ ...smsForm, sender: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
              placeholder="Clinic"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Шаблон
            </label>
            <select
              value={smsForm.template}
              onChange={(e) => setSmsForm({ ...smsForm, template: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
            >
              <option value="">Выберите шаблон</option>
              {templates.sms.map(template => (
                <option key={template.name} value={template.name}>
                  {template.title}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Приоритет
            </label>
            <select
              value={smsForm.priority}
              onChange={(e) => setSmsForm({ ...smsForm, priority: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
            >
              <option value="normal">Обычный</option>
              <option value="high">Высокий</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Сообщение
          </label>
          <textarea
            value={smsForm.message}
            onChange={(e) => setSmsForm({ ...smsForm, message: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
            placeholder="Текст SMS сообщения"
          />
        </div>

        <div className="mt-6 flex space-x-4">
          <button
            onClick={sendTestSMS}
            disabled={loading || !smsForm.phone}
            className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Отправка...' : 'Отправить тест'}
          </button>

          <button
            onClick={() => setSmsForm({
              phone: '', message: '', template: '', sender: '', priority: 'normal'
            })}
            className="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600 transition-colors"
          >
            Очистить
          </button>
        </div>
      </div>
    </div>
  );

  const renderBulkForm = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Массовые рассылки</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Тип рассылки
            </label>
            <select
              value={bulkForm.type}
              onChange={(e) => setBulkForm({ ...bulkForm, type: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            >
              <option value="email">Email</option>
              <option value="sms">SMS</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Размер батча
            </label>
            <input
              type="number"
              value={bulkForm.batchSize}
              onChange={(e) => setBulkForm({ ...bulkForm, batchSize: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              min="1"
              max="1000"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Задержка между батчами (сек)
            </label>
            <input
              type="number"
              step="0.1"
              value={bulkForm.delay}
              onChange={(e) => setBulkForm({ ...bulkForm, delay: parseFloat(e.target.value) })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              min="0"
              max="10"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Шаблон
            </label>
            <select
              value={bulkForm.template}
              onChange={(e) => setBulkForm({ ...bulkForm, template: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            >
              <option value="">Выберите шаблон</option>
              {(bulkForm.type === 'email' ? templates.email : templates.sms).map(template => (
                <option key={template.name} value={template.name}>
                  {template.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {bulkForm.type === 'email' && (
          <div className="mt-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Тема письма
            </label>
            <input
              type="text"
              value={bulkForm.subject}
              onChange={(e) => setBulkForm({ ...bulkForm, subject: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
              placeholder="Тема письма"
            />
          </div>
        )}

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Сообщение
          </label>
          <textarea
            value={bulkForm.message}
            onChange={(e) => setBulkForm({ ...bulkForm, message: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            placeholder="Текст сообщения"
          />
        </div>

        <div className="mt-6 flex space-x-4">
          <button
            onClick={sendBulkNotification}
            disabled={loading || bulkForm.recipients.length === 0}
            className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Отправка...' : 'Запустить рассылку'}
          </button>

          <button
            onClick={() => setBulkForm({
              type: 'email', recipients: [], subject: '', template: '', message: '', batchSize: 50, delay: 1.0
            })}
            className="bg-gray-500 text-white px-6 py-2 rounded-lg hover:bg-gray-600 transition-colors"
          >
            Очистить
          </button>
        </div>
      </div>
    </div>
  );

  const renderTemplates = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Email шаблоны */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <Mail className="w-5 h-5 mr-2 text-blue-600" />
            Email шаблоны
          </h3>
          <div className="space-y-3">
            {templates.email.map(template => (
              <div key={template.name} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">{template.title}</h4>
                    <p className="text-sm text-gray-600">{template.description}</p>
                  </div>
                  <div className="flex space-x-2">
                    <button className="p-2 text-gray-400 hover:text-blue-600">
                      <Eye className="w-4 h-4" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-blue-600">
                      <Edit className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="mt-2">
                  <span className="text-xs text-gray-500">
                    Переменные: {template.variables.join(', ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* SMS шаблоны */}
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <MessageSquare className="w-5 h-5 mr-2 text-green-600" />
            SMS шаблоны
          </h3>
          <div className="space-y-3">
            {templates.sms.map(template => (
              <div key={template.name} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">{template.title}</h4>
                    <p className="text-sm text-gray-600">{template.description}</p>
                  </div>
                  <div className="flex space-x-2">
                    <button className="p-2 text-gray-400 hover:text-green-600">
                      <Eye className="w-4 h-4" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-green-600">
                      <Edit className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="mt-2">
                  <span className="text-xs text-gray-500">
                    Переменные: {template.variables.join(', ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Настройки Email/SMS</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium mb-3">Email настройки</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  SMTP сервер
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="smtp.gmail.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Порт
                </label>
                <input
                  type="number"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="587"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="clinic@example.com"
                />
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium mb-3">SMS настройки</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API URL
                </label>
                <input
                  type="url"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="https://api.sms-provider.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API ключ
                </label>
                <input
                  type="password"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="••••••••••••••••"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Отправитель
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="Clinic"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex space-x-4">
          <button className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors">
            Сохранить настройки
          </button>

          <button
            onClick={resetStatistics}
            className="bg-red-600 text-white px-6 py-2 rounded-lg hover:bg-red-700 transition-colors"
          >
            Сбросить статистику
          </button>
        </div>
      </div>
    </div>
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
    <div className="space-y-6">
      {/* Навигация */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === tab.id
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Контент */}
      {renderTabContent()}
    </div>
  );
};

export default EmailSMSManager;

