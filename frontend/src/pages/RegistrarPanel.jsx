import React, { useState, useEffect, useCallback } from 'react';
import InputMask from 'react-input-mask';
import AppointmentsTable from '../components/AppointmentsTable';
import ServiceChecklist from '../components/ServiceChecklist';

const RegistrarPanel = () => {
  // Основные состояния
  const [activeTab, setActiveTab] = useState('welcome');
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [showAddressColumn, setShowAddressColumn] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  
  // Состояния мастера
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardData, setWizardData] = useState({
    patient: {},
    visit: {},
    payment: {}
  });
  
  // Тема и язык
  const [theme, setTheme] = useState(() => localStorage.getItem('ui_theme') || 'light');
  const [language, setLanguage] = useState(() => localStorage.getItem('ui_lang') || 'ru');
  
  useEffect(() => { localStorage.setItem('ui_theme', theme); }, [theme]);
  useEffect(() => { localStorage.setItem('ui_lang', language); }, [language]);

  // Переводы
  const translations = {
    ru: {
      // Основные
      welcome: 'Добро пожаловать',
      start_work: 'Начать работу',
      quick_start: 'Быстрый старт',
      
      // Вкладки
      tabs_welcome: 'Главная',
      tabs_appointments: 'Все записи',
      tabs_cardio: 'Кардиолог',
      tabs_echokg: 'ЭхоКГ',
      tabs_derma: 'Дерматолог',
      tabs_dental: 'Стоматолог',
      tabs_lab: 'Лаборатория',
      tabs_procedures: 'Процедуры',
      
      // Действия
      new_appointment: 'Новая запись',
      export_csv: 'Экспорт CSV',
      today: 'Сегодня',
      reset: 'Сбросить',
      confirm: 'Подтвердить',
      cancel: 'Отменить',
      no_show: 'Неявка',
      reason: 'Причина',
      bulk_actions: 'Массовые действия',
      
      // Мастер
      patient: 'Пациент',
      details: 'Детали',
      payment: 'Оплата',
      next: 'Далее',
      back: 'Назад',
      save: 'Сохранить',
      close: 'Закрыть',
      add_to_queue: 'Добавить в очередь',
      priority: 'Приоритет',
      available_slots: 'Доступные слоты',
      tomorrow: 'Завтра',
      select_date: 'Выбрать дату',
      online_payment: 'Онлайн оплата',
      
      // Статистика
      total_patients: 'Всего пациентов',
      today_appointments: 'Записей сегодня',
      pending_payments: 'Ожидают оплаты',
      active_queues: 'Активные очереди'
    },
    uz: {
      // Основные
      welcome: 'Xush kelibsiz',
      start_work: 'Ishni boshlash',
      quick_start: 'Tezkor start',
      
      // Вкладки
      tabs_welcome: 'Asosiy',
      tabs_appointments: 'Barcha yozuvlar',
      tabs_cardio: 'Kardiolog',
      tabs_echokg: 'EchoKG',
      tabs_derma: 'Dermatolog',
      tabs_dental: 'Stomatolog',
      tabs_lab: 'Laboratoriya',
      tabs_procedures: 'Protseduralar',
      
      // Действия
      new_appointment: 'Yangi yozuv',
      export_csv: 'CSV eksport',
      today: 'Bugun',
      reset: 'Tozalash',
      confirm: 'Tasdiqlash',
      cancel: 'Bekor qilish',
      no_show: 'Kelmaslik',
      reason: 'Sabab',
      bulk_actions: 'Ommaviy amallar',
      
      // Мастер
      patient: 'Bemor',
      details: 'Tafsilotlar',
      payment: 'To\'lov',
      next: 'Keyingi',
      back: 'Orqaga',
      save: 'Saqlash',
      close: 'Yopish',
      add_to_queue: 'Navbatga qo\'shish',
      priority: 'Ustuvorlik',
      available_slots: 'Mavjud vaqtlar',
      tomorrow: 'Ertaga',
      select_date: 'Sanani tanlash',
      online_payment: 'Onlayn to\'lov',
      
      // Статистика
      total_patients: 'Jami bemorlar',
      today_appointments: 'Bugungi yozuvlar',
      pending_payments: 'To\'lovni kutmoqda',
      active_queues: 'Faol navbatlar'
    }
  };
  const t = (key) => (translations[language] && translations[language][key]) || translations.ru[key] || key;

  // Стили
  const cardBg = theme === 'light' ? '#ffffff' : '#111827';
  const textColor = theme === 'light' ? '#111827' : '#f9fafb';
  const borderColor = theme === 'light' ? '#e5e5e5' : '#374151';
  const accentColor = '#007bff';
  const successColor = '#28a745';
  const warningColor = '#ffc107';
  const dangerColor = '#dc3545';

  const pageStyle = {
    padding: '0',
    maxWidth: 'none',
    margin: '0',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: theme === 'light' ? '#f8f9fa' : '#1f2937',
    minHeight: '100vh'
  };

  const cardStyle = {
    background: cardBg,
    color: textColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '12px',
    margin: '0 20px 20px 20px',
    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
    overflow: 'hidden'
  };

  const cardHeaderStyle = {
    padding: '24px',
    borderBottom: `1px solid ${borderColor}`,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    color: textColor,
    background: `linear-gradient(135deg, ${accentColor} 0%, #0056b3 100%)`,
    color: 'white'
  };

  const cardContentStyle = {
    padding: '20px',
    color: textColor
  };

  const buttonStyle = {
    padding: '12px 20px',
    backgroundColor: accentColor,
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    marginRight: '12px',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.2s',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    backgroundColor: '#6c757d'
  };

  const buttonSuccessStyle = {
    ...buttonStyle,
    backgroundColor: successColor
  };

  const buttonDangerStyle = {
    ...buttonStyle,
    backgroundColor: dangerColor
  };

  const buttonWarningStyle = {
    ...buttonStyle,
    backgroundColor: warningColor,
    color: '#212529'
  };

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    fontSize: '14px',
    marginBottom: '16px',
    transition: 'border-color 0.2s'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '8px',
    fontWeight: '500',
    fontSize: '14px'
  };

  const tabStyle = {
    padding: '16px 24px',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    color: textColor,
    borderBottom: '3px solid transparent',
    transition: 'all 0.3s',
    borderRadius: '8px 8px 0 0'
  };

  const activeTabStyle = {
    ...tabStyle,
    borderBottom: `3px solid ${accentColor}`,
    color: accentColor,
    background: theme === 'light' ? '#f8f9fa' : '#374151'
  };

  // Загрузка данных
  const loadAppointments = async () => {
    try {
      setAppointmentsLoading(true);
      const response = await fetch('/api/v1/appointments/?limit=50', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setAppointments(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки записей:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  };

  useEffect(() => {
    loadAppointments();
  }, []);

  // Обработчики событий
  const updateAppointmentStatus = useCallback(async (appointmentId, status, reason = '') => {
    try {
      const response = await fetch(`/api/v1/appointments/${appointmentId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ status, reason })
      });
      if (response.ok) {
        await loadAppointments();
      }
    } catch (error) {
      console.error('Ошибка обновления статуса:', error);
    }
  }, []);

  const handleBulkAction = useCallback(async (action, reason = '') => {
    if (appointmentsSelected.size === 0) return;
    
    const promises = Array.from(appointmentsSelected).map(id => 
      updateAppointmentStatus(id, action, reason)
    );
    
    await Promise.all(promises);
    setAppointmentsSelected(new Set());
  }, [appointmentsSelected, updateAppointmentStatus]);

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      
      if (e.key === 'Enter') {
        if (showWizard) {
          if (wizardStep < 3) {
            setWizardStep(wizardStep + 1);
          } else {
            setShowWizard(false);
            setWizardStep(1);
            loadAppointments();
          }
        }
      } else if (e.ctrlKey) {
        if (e.key === 'p') {
          e.preventDefault();
        } else if (e.key === 'k') {
          e.preventDefault();
          setShowWizard(true);
        } else if (e.key === '1') setActiveTab('welcome');
        else if (e.key === '2') setActiveTab('appointments');
        else if (e.key === '3') setActiveTab('cardio');
        else if (e.key === '4') setActiveTab('derma');
        else if (e.key === 'a') {
          e.preventDefault();
          setAppointmentsSelected(new Set(appointments.map(a => a.id)));
        } else if (e.key === 'd') {
          e.preventDefault();
          setAppointmentsSelected(new Set());
        }
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (showSlotsModal) setShowSlotsModal(false);
        if (showQRModal) setShowQRModal(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, showSlotsModal, showQRModal, wizardStep, appointments]);

  // Фильтрация записей по вкладке
  const filteredAppointments = appointments.filter(appointment => {
    if (activeTab === 'welcome' || activeTab === 'appointments') return true;
    if (activeTab === 'cardio') return appointment.department?.toLowerCase().includes('cardio');
    if (activeTab === 'echokg') return appointment.department?.toLowerCase().includes('echo');
    if (activeTab === 'derma') return appointment.department?.toLowerCase().includes('derma');
    if (activeTab === 'dental') return appointment.department?.toLowerCase().includes('dental');
    if (activeTab === 'lab') return appointment.department?.toLowerCase().includes('lab');
    if (activeTab === 'procedures') return appointment.department?.toLowerCase().includes('proc');
    return true;
  });

  // Статистика для экрана приветствия
  const stats = {
    totalPatients: appointments.length,
    todayAppointments: appointments.filter(a => a.date === new Date().toISOString().split('T')[0]).length,
    pendingPayments: appointments.filter(a => a.status === 'paid_pending').length,
    activeQueues: appointments.filter(a => a.status === 'queued').length
  };

  return (
    <div style={{ ...pageStyle, overflow: 'hidden' }} role="main" aria-label="Панель регистратора">
      {/* Фиксированная верхняя часть */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        background: theme === 'light' ? '#f8f9fa' : '#1f2937',
        padding: '16px',
        borderBottom: '1px solid #e5e5e5',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        {/* Верхнее меню */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          border: '1px solid #e5e5e5',
          borderRadius: '16px',
          marginBottom: '16px',
          background: theme === 'light' ? '#ffffff' : '#1f2937',
          color: theme === 'light' ? '#111827' : '#f9fafb',
          boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ fontWeight: 700, fontSize: '24px' }}>🏥 Clinic</div>
            <div style={{ opacity: 0.7, fontSize: '16px' }}>|</div>
            <div style={{ fontSize: '18px' }}>{language === 'ru' ? 'Панель регистратора' : 'Registrar Panel'}</div>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Основные функции */}
            <button style={buttonStyle}>
              📅 Расписание
            </button>
            <button style={buttonStyle}>
              🔍 Поиск пациента
            </button>
            <button style={buttonStyle}>
              💬 Сообщения
            </button>
            <button style={buttonStyle}>
              ❓ Справка
            </button>
            
            {/* Разделитель */}
            <div style={{ 
              width: '1px', 
              height: '24px', 
              background: '#e5e5e5', 
              margin: '0 8px' 
            }} />
            
            {/* Быстрые действия */}
            <button style={buttonStyle} onClick={() => setShowWizard(true)}>
              ➕ {t('new_appointment')}
            </button>
            <button style={buttonSecondaryStyle}>
              📊 {t('export_csv')}
            </button>
            
            {/* Разделитель */}
            <div style={{ 
              width: '1px', 
              height: '24px', 
              background: '#e5e5e5', 
              margin: '0 8px' 
            }} />
            
            {/* Настройки */}
            <select
              aria-label="Язык интерфейса"
              value={language}
              onChange={(e)=>setLanguage(e.target.value)}
              style={{ 
                padding: '8px 12px', 
                border: '1px solid #e5e5e5', 
                borderRadius: '8px', 
                background: 'inherit', 
                color: 'inherit',
                fontSize: '14px'
              }}
            >
              <option value="ru">🇷🇺 RU</option>
              <option value="uz">🇺🇿 UZ</option>
            </select>
            <button
              aria-label="Переключить тему"
              onClick={()=>setTheme(theme === 'light' ? 'dark' : 'light')}
              style={{ 
                padding: '8px 12px', 
                border: '1px solid #e5e5e5', 
                borderRadius: '8px', 
                background: 'inherit', 
                color: 'inherit',
                fontSize: '16px'
              }}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
            <button
              aria-label="Выход"
              onClick={()=>{ localStorage.removeItem('auth_token'); window.location.href = '/login'; }}
              style={{ 
                padding: '8px 12px', 
                border: `1px solid #dc3545`, 
                color: '#dc3545', 
                borderRadius: '8px', 
                background: 'inherit',
                fontSize: '14px'
              }}
            >
              ↩︎ Выход
            </button>
          </div>
        </div>

        {/* Вкладки */}
        <div style={{ 
          display: 'flex', 
          gap: '4px', 
          borderBottom: `2px solid ${borderColor}`,
          background: cardBg,
          borderRadius: '12px 12px 0 0',
          padding: '0 16px',
          marginBottom: '0'
        }}>
          <button
            style={activeTab === 'welcome' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('welcome')}
            aria-selected={activeTab === 'welcome'}
          >
            🏠 {t('tabs_welcome')}
          </button>
          <button
            style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('appointments')}
            aria-selected={activeTab === 'appointments'}
          >
            📋 {t('tabs_appointments')} ({filteredAppointments.length})
          </button>
          <button
            style={activeTab === 'cardio' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('cardio')}
            aria-selected={activeTab === 'cardio'}
          >
            ❤️ {t('tabs_cardio')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('cardio')).length})
          </button>
          <button
            style={activeTab === 'echokg' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('echokg')}
            aria-selected={activeTab === 'echokg'}
          >
            📊 {t('tabs_echokg')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('echo')).length})
          </button>
          <button
            style={activeTab === 'derma' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('derma')}
            aria-selected={activeTab === 'derma'}
          >
            🩺 {t('tabs_derma')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('derma')).length})
          </button>
          <button
            style={activeTab === 'dental' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('dental')}
            aria-selected={activeTab === 'dental'}
          >
            🦷 {t('tabs_dental')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('dental')).length})
          </button>
          <button
            style={activeTab === 'lab' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('lab')}
            aria-selected={activeTab === 'lab'}
          >
            🧪 {t('tabs_lab')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('lab')).length})
          </button>
          <button
            style={activeTab === 'procedures' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('procedures')}
            aria-selected={activeTab === 'procedures'}
          >
            💉 {t('tabs_procedures')} ({filteredAppointments.filter(a => a.department?.toLowerCase().includes('proc')).length})
          </button>
        </div>
      </div> {/* Закрытие фиксированного контейнера */}

      {/* Скроллируемый контент с отступом сверху */}
      <div style={{ marginTop: '280px', overflow: 'hidden' }}>
        {/* Экран приветствия */}
        {activeTab === 'welcome' && (
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h1 style={{ margin: 0, fontSize: '32px', fontWeight: '300' }}>
                {t('welcome')} в панель регистратора! 👋
              </h1>
              <div style={{ fontSize: '18px', opacity: 0.9 }}>
                {new Date().toLocaleDateString(language === 'ru' ? 'ru-RU' : 'uz-UZ', { 
                  weekday: 'long', 
                  year: 'numeric', 
                  month: 'long', 
                  day: 'numeric' 
                })}
              </div>
            </div>
            
            <div style={cardContentStyle}>
              {/* Статистика */}
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
                gap: '20px', 
                marginBottom: '32px' 
              }}>
                <div style={{
                  background: `linear-gradient(135deg, ${accentColor} 0%, #0056b3 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.totalPatients}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('total_patients')}
                  </div>
                </div>
                
                <div style={{
                  background: `linear-gradient(135deg, ${successColor} 0%, #1e7e34 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.todayAppointments}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('today_appointments')}
                  </div>
                </div>
                
                <div style={{
                  background: `linear-gradient(135deg, ${warningColor} 0%, #e0a800 100%)`,
                  color: '#212529',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.pendingPayments}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('pending_payments')}
                  </div>
                </div>
                
                <div style={{
                  background: `linear-gradient(135deg, ${dangerColor} 0%, #c82333 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.activeQueues}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('active_queues')}
                  </div>
                </div>
              </div>

              {/* Быстрый старт */}
              <div style={{ marginBottom: '32px' }}>
                <h2 style={{ fontSize: '24px', marginBottom: '20px', color: accentColor }}>
                  🚀 {t('quick_start')}
                </h2>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                  gap: '16px' 
                }}>
                  <button 
                    style={buttonStyle}
                    onClick={() => setShowWizard(true)}
                  >
                    ➕ {t('new_appointment')}
                  </button>
                  <button style={buttonSecondaryStyle}>
                    📊 {t('export_csv')}
                  </button>
                  <button style={buttonWarningStyle}>
                    📅 {t('today')}
                  </button>
                  <button style={buttonSecondaryStyle}>
                    🔄 {t('reset')}
                  </button>
                </div>
              </div>

              {/* Недавние записи */}
              {appointments.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '20px', marginBottom: '16px', color: accentColor }}>
                    📋 Недавние записи
                  </h3>
                  <div style={{ 
                    background: cardBg,
                    border: `1px solid ${borderColor}`,
                    borderRadius: '8px',
                    padding: '16px'
                  }}>
                    <AppointmentsTable
                      appointments={appointments.slice(0, 5)}
                      appointmentsSelected={appointmentsSelected}
                      setAppointmentsSelected={setAppointmentsSelected}
                      updateAppointmentStatus={updateAppointmentStatus}
                      setShowWizard={setShowWizard}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Основная панель с записями */}
        {activeTab !== 'welcome' && (
          <div style={cardStyle}>
            <div style={cardContentStyle}>
              
              {/* Массовые действия */}
              {appointmentsSelected.size > 0 && (
                <div style={{ 
                  display: 'flex', 
                  gap: '12px', 
                  alignItems: 'center',
                  padding: '16px',
                  background: theme === 'light' ? '#f8f9fa' : '#374151',
                  borderRadius: '8px'
                }}>
                  <span style={{ fontWeight: 600, marginRight: '12px' }}>
                    🎯 {t('bulk_actions')} ({appointmentsSelected.size}):
                  </span>
                  <button style={buttonSuccessStyle} onClick={() => handleBulkAction('confirmed')}>
                    ✅ {t('confirm')}
                  </button>
                  <button style={buttonDangerStyle} onClick={() => {
                    const reason = prompt(t('reason'));
                    if (reason) handleBulkAction('cancelled', reason);
                  }}>
                    ❌ {t('cancel')}
                  </button>
                  <button style={buttonWarningStyle} onClick={() => handleBulkAction('no_show')}>
                    ⚠️ {t('no_show')}
                  </button>
                </div>
              )}
              
              {/* Таблица записей */}
              {appointmentsLoading ? (
                <div style={{ textAlign: 'center', padding: '40px' }} aria-busy="true">
                  Загрузка записей...
                </div>
              ) : (
                <AppointmentsTable
                  appointments={filteredAppointments}
                  appointmentsSelected={appointmentsSelected}
                  setAppointmentsSelected={setAppointmentsSelected}
                  updateAppointmentStatus={updateAppointmentStatus}
                  setShowWizard={setShowWizard}
                />
              )}
            </div>
          </div>
        )}
      </div> {/* Закрытие скроллируемого контента */}

      {/* Мастер создания записи */}
      {showWizard && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} role="dialog" aria-modal="true">
          <div style={{
            background: cardBg,
            padding: '32px',
            borderRadius: '16px',
            maxWidth: '700px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0 }}>➕ {t('new_appointment')}</h2>
              <button onClick={() => setShowWizard(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            
            {/* Шаг 1: Пациент */}
            {wizardStep === 1 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>👤 {t('patient')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>ФИО пациента</label>
                    <input
                      type="text"
                      style={inputStyle}
                      placeholder="Введите ФИО"
                      value={wizardData.patient.fio || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, fio: e.target.value }
                      })}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Год рождения</label>
                    <input
                      type="number"
                      style={inputStyle}
                      placeholder="1985"
                      min="1900"
                      max={new Date().getFullYear() - 1}
                      value={wizardData.patient.birthYear || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, birthYear: e.target.value }
                      })}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Телефон</label>
                    <InputMask
                      mask="+7 (999) 999-99-99"
                      style={inputStyle}
                      placeholder="+7 (999) 123-45-67"
                      value={wizardData.patient.phone || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, phone: e.target.value }
                      })}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonStyle} onClick={() => setWizardStep(2)}>
                    {t('next')} →
                  </button>
                  <button style={buttonSecondaryStyle} onClick={() => setShowWizard(false)}>
                    {t('close')}
                  </button>
                </div>
              </div>
            )}
            
            {/* Шаг 2: Детали */}
            {wizardStep === 2 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>📋 {t('details')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>Услуги</label>
                    <ServiceChecklist
                      selectedServices={wizardData.visit.services || []}
                      onServicesChange={(services) => setWizardData({
                        ...wizardData,
                        visit: { ...wizardData.visit, services }
                      })}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Тип обращения</label>
                    <select
                      style={inputStyle}
                      value={wizardData.visit.type || 'paid'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        visit: { ...wizardData.visit, type: e.target.value }
                      })}
                    >
                      <option value="paid">Платный</option>
                      <option value="repeat">Повторный</option>
                      <option value="free">Льготный</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Приоритет</label>
                    <select
                      style={inputStyle}
                      value={wizardData.visit.priority || 'normal'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        visit: { ...wizardData.visit, priority: e.target.value }
                      })}
                    >
                      <option value="normal">Обычный</option>
                      <option value="high">Высокий</option>
                      <option value="urgent">Срочный</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(1)}>
                    ← {t('back')}
                  </button>
                  <button style={buttonStyle} onClick={() => setWizardStep(3)}>
                    {t('next')} →
                  </button>
                </div>
              </div>
            )}
            
            {/* Шаг 3: Оплата */}
            {wizardStep === 3 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>💳 {t('payment')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>Способ оплаты</label>
                    <select
                      style={inputStyle}
                      value={wizardData.payment.method || 'cash'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        payment: { ...wizardData.payment, method: e.target.value }
                      })}
                    >
                      <option value="cash">Наличные</option>
                      <option value="card">Банковская карта</option>
                      <option value="online">Онлайн</option>
                    </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Стоимость (₽)</label>
                    <input
                      type="number"
                      style={inputStyle}
                      placeholder="1000"
                      min="0"
                      value={wizardData.payment.amount || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        payment: { ...wizardData.payment, amount: e.target.value }
                      })}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(2)}>
                    ← {t('back')}
                  </button>
                  <button style={buttonStyle} onClick={() => {
                    // Здесь будет логика сохранения записи
                    setShowWizard(false);
                    setWizardStep(1);
                    loadAppointments();
                  }}>
                    ✅ {t('save')}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Модальное окно слотов */}
      {showSlotsModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} role="dialog" aria-modal="true">
          <div style={{
            background: cardBg,
            padding: '24px',
            borderRadius: '12px',
            maxWidth: '500px',
            width: '90%'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>📅 {t('available_slots')}</h3>
              <button onClick={() => setShowSlotsModal(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ display: 'grid', gap: '8px' }}>
              <button style={buttonStyle} onClick={() => {
                setShowSlotsModal(false);
              }}>
                🌅 {t('tomorrow')}
              </button>
              <button style={buttonSecondaryStyle} onClick={() => {
                setShowSlotsModal(false);
              }}>
                📅 {t('select_date')}
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Модальное окно QR */}
      {showQRModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} role="dialog" aria-modal="true">
          <div style={{
            background: cardBg,
            padding: '24px',
            borderRadius: '12px',
            maxWidth: '400px',
            width: '90%',
            textAlign: 'center'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>💳 {t('online_payment')}</h3>
              <button onClick={() => setShowQRModal(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ 
              width: '200px', 
              height: '200px', 
              background: '#f0f0f0', 
              margin: '0 auto 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              color: '#666',
              borderRadius: '8px'
            }}>
              QR код для оплаты
            </div>
            <p>Сумма: Не указано</p>
            <button style={buttonStyle} onClick={() => setShowQRModal(false)}>
              {t('close')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RegistrarPanel; 