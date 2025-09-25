/**
 * Пример унифицированной панели с использованием новой дизайн-системы
 * Демонстрирует, как должны выглядеть панели после миграции
 */

import React, { useState, useEffect } from 'react';
import { 
  ResponsiveLayout, 
  SidebarNav, 
  QuickActions,
  MedicalCard,
  medicalTheme,
  getDepartmentStyle,
  useBreakpoint 
} from '../design-system';
import { 
  User, 
  Calendar, 
  Clock, 
  Activity,
  Plus,
  Search,
  Filter,
  Printer,
  Download,
  Settings,
  Heart,
  Stethoscope,
  FileText
} from 'lucide-react';

const UnifiedPanelExample = () => {
  const { isMobile, isTablet } = useBreakpoint();
  const [activeTab, setActiveTab] = useState('patients');
  const [theme, setTheme] = useState('medical');
  
  // Моковые данные
  const [patients] = useState([
    {
      id: 1,
      name: "Иванов Иван Иванович",
      phone: "+998901234567",
      email: "ivan@example.com",
      address: "г. Ташкент, ул. Навои 15",
      status: "healthy",
      lastVisit: "2025-01-10",
      nextAppointment: {
        date: "2025-01-20",
        time: "10:30",
        totalAmount: 150000
      }
    },
    {
      id: 2,
      name: "Петрова Анна Сергеевна", 
      phone: "+998907654321",
      email: "anna@example.com",
      status: "sick",
      priority: "urgent",
      lastVisit: "2025-01-12",
      nextAppointment: {
        date: "2025-01-15",
        time: "14:00",
        totalAmount: 200000
      }
    },
    {
      id: 3,
      name: "Сидоров Петр Алексеевич",
      phone: "+998901111111",
      status: "recovery",
      priority: "normal",
      lastVisit: "2025-01-08"
    }
  ]);
  
  const [appointments] = useState([
    {
      id: 1,
      patient: { name: "Иванов И.И.", phone: "+998901234567" },
      date: "2025-01-15",
      time: "10:30",
      doctor: "Кардиолог Смирнов А.В.",
      services: [
        { name: "Консультация кардиолога", price: 100000 },
        { name: "ЭКГ", price: 50000 }
      ],
      status: "confirmed",
      totalAmount: 150000
    },
    {
      id: 2,
      patient: { name: "Петрова А.С.", phone: "+998907654321" },
      date: "2025-01-15",
      time: "14:00", 
      doctor: "Кардиолог Смирнов А.В.",
      services: [
        { name: "Консультация кардиолога", price: 100000 },
        { name: "ЭхоКГ", price: 120000 }
      ],
      status: "scheduled",
      priority: "urgent",
      totalAmount: 220000
    }
  ]);
  
  // Навигация sidebar
  const sidebarItems = [
    { 
      id: 'patients', 
      label: 'Пациенты', 
      icon: User,
      badge: patients.length 
    },
    { 
      id: 'appointments', 
      label: 'Записи', 
      icon: Calendar,
      badge: appointments.filter(a => a.status === 'scheduled').length
    },
    { 
      id: 'queue', 
      label: 'Очередь', 
      icon: Clock,
      badge: 5
    },
    { 
      id: 'analytics', 
      label: 'Аналитика', 
      icon: Activity 
    },
    { 
      id: 'settings', 
      label: 'Настройки', 
      icon: Settings 
    }
  ];
  
  // Быстрые действия
  const quickActions = [
    { 
      label: 'Новый пациент', 
      icon: Plus, 
      onClick: () => alert('Создание нового пациента'),
      variant: 'primary' 
    },
    { 
      label: 'Поиск', 
      icon: Search, 
      onClick: () => alert('Поиск пациентов') 
    },
    { 
      label: 'Фильтр', 
      icon: Filter, 
      onClick: () => alert('Фильтрация') 
    },
    { 
      label: 'Печать', 
      icon: Printer, 
      onClick: () => alert('Печать отчета') 
    }
  ];
  
  // Хлебные крошки
  const breadcrumbs = [
    { label: 'Главная', active: false },
    { label: 'Кардиология', active: false },
    { label: 'Панель врача', active: true }
  ];
  
  // Обработчики
  const handleNavClick = (item) => {
    setActiveTab(item.id);
  };
  
  const handlePatientClick = (data) => {
    alert(`Открытие карточки пациента: ${data.patient?.name || data.name}`);
  };
  
  const handleEditPatient = (patient) => {
    alert(`Редактирование пациента: ${patient.name}`);
  };
  
  const handleDeletePatient = (patient) => {
    alert(`Удаление пациента: ${patient.name}`);
  };
  
  // Рендер контента в зависимости от активной вкладки
  const renderContent = () => {
    switch (activeTab) {
      case 'patients':
        return (
          <div className="patients-content">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Пациенты кардиологии
              </h2>
              <p className="text-gray-600">
                Управление пациентами и их медицинскими картами
              </p>
            </div>
            
            <div className={`grid gap-4 ${
              isMobile ? 'grid-cols-1' : 
              isTablet ? 'grid-cols-2' : 
              'grid-cols-3'
            }`}>
              {patients.map(patient => (
                <MedicalCard
                  key={patient.id}
                  patient={patient}
                  appointment={patient.nextAppointment}
                  department="cardiology"
                  status={patient.status}
                  priority={patient.priority}
                  variant="detailed"
                  actions={[
                    { 
                      label: "Редактировать", 
                      onClick: () => handleEditPatient(patient),
                      icon: FileText
                    },
                    { 
                      label: "История", 
                      onClick: () => alert(`История пациента: ${patient.name}`),
                      icon: Clock
                    }
                  ]}
                  onCardClick={handlePatientClick}
                />
              ))}
            </div>
          </div>
        );
        
      case 'appointments':
        return (
          <div className="appointments-content">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Записи на сегодня
              </h2>
              <p className="text-gray-600">
                Управление записями и расписанием приема
              </p>
            </div>
            
            <div className={`grid gap-4 ${
              isMobile ? 'grid-cols-1' : 
              isTablet ? 'grid-cols-1' : 
              'grid-cols-2'
            }`}>
              {appointments.map(appointment => (
                <MedicalCard
                  key={appointment.id}
                  title={`Прием ${appointment.time}`}
                  subtitle={appointment.doctor}
                  patient={appointment.patient}
                  appointment={appointment}
                  services={appointment.services}
                  department="cardiology"
                  status={appointment.status}
                  priority={appointment.priority}
                  variant="detailed"
                  actions={[
                    { 
                      label: "Начать прием", 
                      onClick: () => alert(`Начало приема: ${appointment.patient.name}`),
                      variant: "primary",
                      icon: Stethoscope
                    },
                    { 
                      label: "Перенести", 
                      onClick: () => alert(`Перенос записи: ${appointment.patient.name}`),
                      icon: Calendar
                    }
                  ]}
                  onCardClick={handlePatientClick}
                />
              ))}
            </div>
          </div>
        );
        
      case 'queue':
        return (
          <div className="queue-content">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Очередь кардиологии
              </h2>
              <p className="text-gray-600">
                Текущая очередь и управление приемом пациентов
              </p>
            </div>
            
            <div className="bg-white rounded-lg p-6 shadow-sm border">
              <div className="text-center">
                <Heart className="mx-auto h-12 w-12 text-red-500 mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Очередь пуста
                </h3>
                <p className="text-gray-500">
                  В данный момент нет пациентов в очереди
                </p>
              </div>
            </div>
          </div>
        );
        
      default:
        return (
          <div className="default-content">
            <div className="text-center py-12">
              <Activity className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Раздел в разработке
              </h3>
              <p className="text-gray-500">
                Выберите другой раздел из меню
              </p>
            </div>
          </div>
        );
    }
  };
  
  return (
    <ResponsiveLayout
      title="Панель кардиолога"
      subtitle="Смирнов Александр Владимирович"
      breadcrumbs={breadcrumbs}
      theme={theme}
      onThemeChange={setTheme}
      sidebar={
        <SidebarNav 
          items={sidebarItems} 
          activeItem={activeTab}
          onItemClick={handleNavClick}
        />
      }
      headerActions={<QuickActions actions={quickActions} />}
    >
      {renderContent()}
    </ResponsiveLayout>
  );
};

export default UnifiedPanelExample;
