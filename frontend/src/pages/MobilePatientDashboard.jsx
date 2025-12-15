import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  User,
  Bell,
  Activity,
  Phone,
  MapPin,
  Heart,
  Stethoscope,
  TestTube,
  CreditCard,
  Settings
} from 'lucide-react';
import { Card, Button, Badge } from '../components/ui/macos';
import { usePWA } from '../hooks/usePWA';
import MobileNotifications from '../components/mobile/MobileNotifications';
import OfflineIndicator from '../components/mobile/OfflineIndicator';
import QueuePositionCard from '../components/mobile/QueuePositionCard';

import logger from '../utils/logger';

/**
 * Мобильная панель пациента для PWA
 */
const MobilePatientDashboard = () => {
  const [patientData, setPatientData] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');

  const { isOnline, getConnectionDetails } = usePWA();

  useEffect(() => {
    loadPatientData();
  }, []);

  const loadPatientData = async () => {
    try {
      setLoading(true);

      // Загружаем данные пациента
      const response = await fetch('/api/v1/mobile/auth/profile', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPatientData(data);
      }

      // Загружаем записи
      const appointmentsResponse = await fetch('/api/v1/mobile/appointments', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (appointmentsResponse.ok) {
        const appointmentsData = await appointmentsResponse.json();
        setAppointments(appointmentsData);
      }

    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  };

  const getUpcomingAppointments = () => {
    const now = new Date();
    return appointments.filter(apt =>
      new Date(apt.appointment_date) > now && apt.status === 'scheduled'
    ).slice(0, 3);
  };

  const getRecentAppointments = () => {
    const now = new Date();
    return appointments.filter(apt =>
      new Date(apt.appointment_date) < now
    ).slice(0, 3);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'scheduled': return 'blue';
      case 'completed': return 'green';
      case 'cancelled': return 'red';
      default: return 'gray';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'scheduled': return 'Запланировано';
      case 'completed': return 'Завершено';
      case 'cancelled': return 'Отменено';
      default: return status;
    }
  };

  // Найти первую активную запись в очереди (на сегодня)
  const activeQueueEntry = appointments.find(a =>
    (a.status === 'waiting' || a.status === 'called') &&
    new Date(a.appointment_date).toDateString() === new Date().toDateString()
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-4">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
          <div className="h-24 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Заголовок */}
      <div className="bg-white shadow-sm border-b">
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Добро пожаловать!
              </h1>
              <p className="text-sm text-gray-600">
                {patientData?.name || 'Пациент'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <Bell className="w-5 h-5 text-gray-400" />
              <Settings className="w-5 h-5 text-gray-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Навигация */}
      <div className="bg-white border-b">
        <div className="flex space-x-1 p-2">
          {[
            { id: 'dashboard', label: 'Главная', icon: Activity },
            { id: 'appointments', label: 'Записи', icon: Calendar },
            { id: 'notifications', label: 'Уведомления', icon: Bell },
            { id: 'profile', label: 'Профиль', icon: User }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex flex-col items-center py-2 px-1 rounded-lg transition-colors ${activeTab === tab.id
                  ? 'bg-blue-50 text-blue-600'
                  : 'text-gray-600 hover:bg-gray-50'
                }`}
            >
              <tab.icon className="w-5 h-5 mb-1" />
              <span className="text-xs font-medium">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Контент */}
      <div className="p-4 space-y-4">
        {activeTab === 'dashboard' && (
          <>
            {/* ✅ Карточка позиции в очереди */}
            {activeQueueEntry && (
              <div className="mb-2">
                <QueuePositionCard
                  queueEntry={{
                    id: activeQueueEntry.id,
                    number: activeQueueEntry.queue_number || activeQueueEntry.id,
                    status: activeQueueEntry.status,
                    peopleBefore: activeQueueEntry.people_before,
                    estimatedWaitTime: activeQueueEntry.estimated_wait_time,
                    doctorName: activeQueueEntry.doctor_name,
                    specialty: activeQueueEntry.specialty || 'Приём врача',
                    cabinet: activeQueueEntry.cabinet
                  }}
                  onRefresh={loadPatientData}
                />
              </div>
            )}

            {/* Быстрые действия */}
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Быстрые действия</h3>
              <div className="grid grid-cols-2 gap-3">
                <Button className="flex flex-col items-center py-3 h-auto">
                  <Calendar className="w-6 h-6 mb-2" />
                  <span className="text-sm">Записаться</span>
                </Button>
                <Button variant="outline" className="flex flex-col items-center py-3 h-auto">
                  <Phone className="w-6 h-6 mb-2" />
                  <span className="text-sm">Позвонить</span>
                </Button>
              </div>
            </Card>

            {/* Ближайшие записи */}
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Ближайшие записи</h3>
              {getUpcomingAppointments().length > 0 ? (
                <div className="space-y-3">
                  {getUpcomingAppointments().map(appointment => (
                    <div key={appointment.id} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                          <Stethoscope className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{appointment.doctor_name}</p>
                          <p className="text-xs text-gray-600">{formatDate(appointment.appointment_date)}</p>
                        </div>
                      </div>
                      <Badge color={getStatusColor(appointment.status)}>
                        {getStatusLabel(appointment.status)}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm text-center py-4">
                  Нет предстоящих записей
                </p>
              )}
            </Card>

            {/* Статистика */}
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Статистика</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {appointments.filter(a => a.status === 'completed').length}
                  </div>
                  <div className="text-xs text-gray-600">Визитов</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {getUpcomingAppointments().length}
                  </div>
                  <div className="text-xs text-gray-600">Записей</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">
                    {patientData?.total_spent || 0}₽
                  </div>
                  <div className="text-xs text-gray-600">Потрачено</div>
                </div>
              </div>
            </Card>
          </>
        )}

        {activeTab === 'appointments' && (
          <div className="space-y-4">
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Все записи</h3>
              {appointments.length > 0 ? (
                <div className="space-y-3">
                  {appointments.map(appointment => (
                    <div key={appointment.id} className="border rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          <Stethoscope className="w-4 h-4 text-gray-400" />
                          <span className="font-medium text-sm">{appointment.doctor_name}</span>
                        </div>
                        <Badge color={getStatusColor(appointment.status)}>
                          {getStatusLabel(appointment.status)}
                        </Badge>
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-gray-600">
                        <div className="flex items-center space-x-1">
                          <Calendar className="w-3 h-3" />
                          <span>{formatDate(appointment.appointment_date)}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <MapPin className="w-3 h-3" />
                          <span>{appointment.location || 'Клиника'}</span>
                        </div>
                      </div>
                      {appointment.complaint && (
                        <p className="text-xs text-gray-500 mt-2">
                          {appointment.complaint}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500 text-sm text-center py-4">
                  Нет записей
                </p>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'notifications' && (
          <MobileNotifications />
        )}

        {activeTab === 'profile' && (
          <div className="space-y-4">
            <Card className="p-4">
              <h3 className="font-semibold mb-3">Личная информация</h3>
              <div className="space-y-3">
                <div className="flex items-center space-x-3">
                  <User className="w-4 h-4 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium">{patientData?.name || 'Не указано'}</p>
                    <p className="text-xs text-gray-600">Имя</p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <Phone className="w-4 h-4 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium">{patientData?.phone || 'Не указано'}</p>
                    <p className="text-xs text-gray-600">Телефон</p>
                  </div>
                </div>
              </div>
            </Card>

            <Card className="p-4">
              <h3 className="font-semibold mb-3">Настройки</h3>
              <div className="space-y-2">
                <Button variant="outline" className="w-full justify-start">
                  <Bell className="w-4 h-4 mr-2" />
                  Уведомления
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  <Settings className="w-4 h-4 mr-2" />
                  Общие настройки
                </Button>
              </div>
            </Card>
          </div>
        )}
      </div>

      {/* Индикатор подключения */}
      <OfflineIndicator />
    </div>
  );
};

export default MobilePatientDashboard;
