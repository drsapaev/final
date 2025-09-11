import React, { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import TwoFactorManager from '../components/security/TwoFactorManager';
import TwoFactorSetupWizard from '../components/security/TwoFactorSetupWizard';
import SMSEmail2FA from '../components/security/SMSEmail2FA';
import { 
  Shield, 
  Settings, 
  Key, 
  Smartphone, 
  Mail, 
  Lock,
  AlertTriangle,
  CheckCircle,
  Activity
} from 'lucide-react';

/**
 * Страница управления безопасностью
 * Централизованное управление всеми аспектами безопасности
 */
const SecurityPage = () => {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [activeTab, setActiveTab] = useState('overview');
  const [showSetupWizard, setShowSetupWizard] = useState(false);
  const [showSMSEmail, setShowSMSEmail] = useState(false);
  const [smsEmailMethod, setSmsEmailMethod] = useState('sms');

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Shield },
    { id: '2fa', label: '2FA', icon: Key },
    { id: 'devices', label: 'Устройства', icon: Smartphone },
    { id: 'sessions', label: 'Сессии', icon: Activity },
    { id: 'logs', label: 'Журнал', icon: AlertTriangle }
  ];

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статус безопасности */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <CheckCircle className="w-8 h-8 text-green-600" />
            <div>
              <h3 className="font-semibold text-green-800">Пароль</h3>
              <p className="text-sm text-green-600">Надежный пароль установлен</p>
            </div>
          </div>
        </div>

        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Key className="w-8 h-8 text-yellow-600" />
            <div>
              <h3 className="font-semibold text-yellow-800">2FA</h3>
              <p className="text-sm text-yellow-600">Рекомендуется включить</p>
            </div>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Smartphone className="w-8 h-8 text-blue-600" />
            <div>
              <h3 className="font-semibold text-blue-800">Устройства</h3>
              <p className="text-sm text-blue-600">2 доверенных устройства</p>
            </div>
          </div>
        </div>
      </div>

      {/* Рекомендации */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-800 mb-4">Рекомендации по безопасности</h3>
        <div className="space-y-3">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5" />
            <div>
              <h4 className="font-medium text-blue-800">Включите двухфакторную аутентификацию</h4>
              <p className="text-sm text-blue-700">
                Это добавит дополнительный уровень защиты к вашему аккаунту
              </p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
            <div>
              <h4 className="font-medium text-blue-800">Регулярно обновляйте пароль</h4>
              <p className="text-sm text-blue-700">
                Используйте уникальные пароли для разных сервисов
              </p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <Smartphone className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h4 className="font-medium text-blue-800">Проверяйте доверенные устройства</h4>
              <p className="text-sm text-blue-700">
                Удаляйте устройства, которыми больше не пользуетесь
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Быстрые действия */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Быстрые действия</h3>
          <div className="space-y-3">
            <button
              onClick={() => setShowSetupWizard(true)}
              className="w-full flex items-center space-x-3 p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
            >
              <Key className="w-5 h-5 text-blue-600" />
              <div>
                <div className="font-medium">Настроить 2FA</div>
                <div className="text-sm text-gray-600">Добавить двухфакторную аутентификацию</div>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('devices')}
              className="w-full flex items-center space-x-3 p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
            >
              <Smartphone className="w-5 h-5 text-green-600" />
              <div>
                <div className="font-medium">Управление устройствами</div>
                <div className="text-sm text-gray-600">Просмотр и управление доверенными устройствами</div>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className="w-full flex items-center space-x-3 p-3 text-left hover:bg-gray-50 rounded-lg transition-colors"
            >
              <AlertTriangle className="w-5 h-5 text-orange-600" />
              <div>
                <div className="font-medium">Журнал безопасности</div>
                <div className="text-sm text-gray-600">Просмотр активности и подозрительных действий</div>
              </div>
            </button>
          </div>
        </div>

        <div className="border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Статистика безопасности</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Последний вход</span>
              <span className="font-medium">2 часа назад</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Активные сессии</span>
              <span className="font-medium">3</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Доверенные устройства</span>
              <span className="font-medium">2</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Уровень безопасности</span>
              <span className="font-medium text-yellow-600">Средний</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverview();
      case '2fa':
        return <TwoFactorManager />;
      case 'devices':
        return <TwoFactorManager />; // Показываем менеджер 2FA с вкладкой устройств
      case 'sessions':
        return <TwoFactorManager />; // Показываем менеджер 2FA с вкладкой сессий
      case 'logs':
        return <TwoFactorManager />; // Показываем менеджер 2FA с вкладкой журнала
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
            <Shield className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">Безопасность</h1>
          </div>
          <p className="text-gray-600">
            Управление безопасностью аккаунта и двухфакторной аутентификацией
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

        {/* Модальные окна */}
        {showSetupWizard && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-screen overflow-y-auto">
              <TwoFactorSetupWizard
                onComplete={() => {
                  setShowSetupWizard(false);
                  setActiveTab('2fa');
                }}
                onCancel={() => setShowSetupWizard(false)}
              />
            </div>
          </div>
        )}

        {showSMSEmail && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg max-w-md w-full mx-4">
              <SMSEmail2FA
                method={smsEmailMethod}
                onSuccess={() => setShowSMSEmail(false)}
                onCancel={() => setShowSMSEmail(false)}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SecurityPage;
