import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import EmailSMSManager from '../components/notifications/EmailSMSManager';
import { 
  Mail, 
  MessageSquare, 
  Settings, 
  BarChart3,
  Send,
  Users,
  FileText,
  Bell,
  AlertCircle,
  CheckCircle,
  Clock,
  RefreshCw
} from 'lucide-react';

/**
 * Страница управления Email/SMS уведомлениями
 * Централизованное управление уведомлениями и рассылками
 */
const EmailSMSPage = () => {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [activeTab, setActiveTab] = useState('overview');

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
      {/* Быстрые действия */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Mail className="w-8 h-8 text-blue-600" />
            <div>
              <h3 className="font-semibold text-blue-800">Отправить Email</h3>
              <p className="text-sm text-blue-600">Быстрая отправка письма</p>
            </div>
          </div>
        </div>

        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <MessageSquare className="w-8 h-8 text-green-600" />
            <div>
              <h3 className="font-semibold text-green-800">Отправить SMS</h3>
              <p className="text-sm text-green-600">Быстрая отправка SMS</p>
            </div>
          </div>
        </div>

        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Users className="w-8 h-8 text-purple-600" />
            <div>
              <h3 className="font-semibold text-purple-800">Массовые рассылки</h3>
              <p className="text-sm text-purple-600">Отправка группе получателей</p>
            </div>
          </div>
        </div>

        <div className="bg-orange-50 border border-orange-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <FileText className="w-8 h-8 text-orange-600" />
            <div>
              <h3 className="font-semibold text-orange-800">Шаблоны</h3>
              <p className="text-sm text-orange-600">Управление шаблонами</p>
            </div>
          </div>
        </div>
      </div>

      {/* Интеграция с EmailSMSManager */}
      <EmailSMSManager />
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverview();
      case 'email':
        return <EmailSMSManager />; // Показываем менеджер с вкладкой email
      case 'sms':
        return <EmailSMSManager />; // Показываем менеджер с вкладкой sms
      case 'bulk':
        return <EmailSMSManager />; // Показываем менеджер с вкладкой bulk
      case 'templates':
        return <EmailSMSManager />; // Показываем менеджер с вкладкой templates
      case 'settings':
        return <EmailSMSManager />; // Показываем менеджер с вкладкой settings
      default:
        return renderOverview();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <Bell className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">Email/SMS уведомления</h1>
          </div>
          <p className="text-gray-600">
            Управление уведомлениями, массовыми рассылками и шаблонами сообщений
          </p>
        </div>

        {/* Навигация */}
        <div className="border-b border-gray-200 mb-8">
          <nav className="flex space-x-8">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
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
    </div>
  );
};

export default EmailSMSPage;
