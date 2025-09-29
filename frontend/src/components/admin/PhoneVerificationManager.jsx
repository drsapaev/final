import React, { useState, useEffect } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Badge,
  Skeleton,
  Input,
  Label,
  Select,
  Option,
  Textarea
} from '../ui/native';
import {
  Phone,
  Shield,
  Send,
  BarChart3,
  Users,
  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Settings,
  MessageSquare
} from 'lucide-react';
import api from '../../utils/api';
import { toast } from 'react-toastify';

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
      console.error('Error loading verification statistics:', error);
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
      console.error('Error sending admin verification code:', error);
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

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Основная статистика */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Активные коды</p>
                <p className="text-2xl font-bold">{statistics?.total_active_codes || 0}</p>
              </div>
              <Shield className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Подтверждено</p>
                <p className="text-2xl font-bold text-green-600">{statistics?.verified_codes || 0}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Ожидают</p>
                <p className="text-2xl font-bold text-orange-600">{statistics?.pending_codes || 0}</p>
              </div>
              <Clock className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Истекают скоро</p>
                <p className="text-2xl font-bold text-red-600">{statistics?.expiring_soon || 0}</p>
              </div>
              <AlertTriangle className="h-8 w-8 text-red-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Статистика по целям */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Статистика по целям верификации
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {statistics?.by_purpose && Object.entries(statistics.by_purpose).map(([purpose, count]) => (
              <div key={purpose} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                <div>
                  <p className="font-medium capitalize">{purpose}</p>
                  <p className="text-sm text-gray-600">
                    {purpose === 'verification' && 'Подтверждение номера'}
                    {purpose === 'password_reset' && 'Сброс пароля'}
                    {purpose === 'phone_change' && 'Смена номера'}
                    {purpose === 'registration' && 'Регистрация'}
                  </p>
                </div>
                <Badge variant="outline">{count}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Статистика по провайдерам */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Статистика по SMS провайдерам
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {statistics?.by_provider && Object.entries(statistics.by_provider).map(([provider, count]) => (
              <div key={provider} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
                <div>
                  <p className="font-medium capitalize">{provider}</p>
                </div>
                <Badge variant={provider === 'mock' ? 'secondary' : 'success'}>{count}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const renderAdminTools = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Отправка кода администратором
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="admin-phone">Номер телефона</Label>
            <Input
              id="admin-phone"
              type="tel"
              value={adminForm.phone}
              onChange={(e) => setAdminForm(prev => ({ ...prev, phone: formatPhone(e.target.value) }))}
              placeholder="+998XXXXXXXXX"
            />
          </div>

          <div>
            <Label htmlFor="admin-purpose">Цель верификации</Label>
            <Select
              value={adminForm.purpose}
              onValueChange={(value) => setAdminForm(prev => ({ ...prev, purpose: value }))}
            >
              <Option value="verification">Подтверждение номера</Option>
              <Option value="password_reset">Сброс пароля</Option>
              <Option value="phone_change">Смена номера</Option>
              <Option value="registration">Регистрация</Option>
            </Select>
          </div>

          <div>
            <Label htmlFor="admin-provider">SMS провайдер (опционально)</Label>
            <Select
              value={adminForm.provider}
              onValueChange={(value) => setAdminForm(prev => ({ ...prev, provider: value }))}
            >
              <Option value="">По умолчанию</Option>
              <Option value="eskiz">Eskiz</Option>
              <Option value="playmobile">PlayMobile</Option>
              <Option value="mock">Mock (тест)</Option>
            </Select>
          </div>

          <div>
            <Label htmlFor="admin-message">Кастомное сообщение (опционально)</Label>
            <Textarea
              id="admin-message"
              value={adminForm.message}
              onChange={(e) => setAdminForm(prev => ({ ...prev, message: e.target.value }))}
              placeholder="Ваш код подтверждения: {code}. Код действителен 5 минут."
              className="min-h-[80px]"
            />
            <p className="text-sm text-gray-600 mt-1">
              Используйте {'{code}'} для вставки кода верификации
            </p>
          </div>

          <Button
            onClick={sendAdminCode}
            disabled={loading || !adminForm.phone.trim()}
            className="w-full"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Отправка...
              </>
            ) : (
              <>
                <Send className="h-4 w-4 mr-2" />
                Отправить код
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Настройки верификации
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {statistics?.settings && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="font-medium">Длина кода</p>
                  <p className="text-2xl font-bold text-blue-600">{statistics.settings.code_length}</p>
                  <p className="text-sm text-gray-600">цифр</p>
                </div>

                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="font-medium">Время жизни кода</p>
                  <p className="text-2xl font-bold text-green-600">{statistics.settings.ttl_minutes}</p>
                  <p className="text-sm text-gray-600">минут</p>
                </div>

                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="font-medium">Максимум попыток</p>
                  <p className="text-2xl font-bold text-orange-600">{statistics.settings.max_attempts}</p>
                  <p className="text-sm text-gray-600">попыток</p>
                </div>

                <div className="p-4 border border-gray-200 rounded-lg">
                  <p className="font-medium">Лимит частоты</p>
                  <p className="text-2xl font-bold text-red-600">{statistics.settings.rate_limit_minutes}</p>
                  <p className="text-sm text-gray-600">минут</p>
                </div>
              </div>
            )}

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <h4 className="font-medium text-blue-800 mb-2">Информация</h4>
              <ul className="text-sm text-blue-700 space-y-1">
                <li>• Коды верификации хранятся в памяти сервера</li>
                <li>• Для production рекомендуется использовать Redis</li>
                <li>• Истекшие коды автоматически удаляются</li>
                <li>• Лимит частоты предотвращает спам</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'admin-tools', label: 'Инструменты', icon: Send },
    { id: 'settings', label: 'Настройки', icon: Settings }
  ];

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Phone className="h-8 w-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">Верификация телефонов</h1>
            <p className="text-gray-600">Управление SMS верификацией</p>
          </div>
        </div>
        
        <Button onClick={loadStatistics} disabled={loading} variant="outline">
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </Button>
      </div>

      {/* Вкладки */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Контент вкладок */}
      {loading && !statistics ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'admin-tools' && renderAdminTools()}
          {activeTab === 'settings' && renderSettings()}
        </>
      )}
    </div>
  );
};

export default PhoneVerificationManager;


