import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import '../styles/dark-theme-visibility-fix.css';
import { useTheme } from '../contexts/ThemeContext';
import AIAssistant from '../components/ai/AIAssistant';
import { 
  User, 
  Calendar, 
  Clock, 
  Stethoscope, 
  FileText, 
  Pill, 
  Activity,
  Brain, 
  Heart,
  Eye,
  Zap,
  Search,
  Filter,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Printer,
  Download,
  Settings,
  Bell,
  LogOut
} from 'lucide-react';
import '../styles/animations.css';

// UI компоненты
import { Button, Card, Badge, AnimatedTransition } from '../components/ui/native';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal';
import { useBreakpoint, useTouchDevice } from '../hooks/useMediaQuery';
import ScheduleNextModal from '../components/common/ScheduleNextModal';

const DoctorPanel = () => {
  const location = useLocation();
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();
  
  // Состояние
  const [activeTab, setActiveTab] = useState('dashboard');
  const [patients, setPatients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  // ✅ УЛУЧШЕНИЕ: Универсальный хук вместо дублированных состояний
  const patientModal = useModal();
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  
  // Refs
  const headerRef = useRef(null);
  const [headerHeight, setHeaderHeight] = useState(0);

  // Используем централизованную систему темизации
  const { 
    isDark, 
    isLight, 
    getColor, 
    getSpacing, 
    getFontSize, 
    getShadow,
    designTokens 
  } = useTheme();

  // Цвета и стили
  const primaryColor = getColor('primary', 500);
  const successColor = getColor('success', 500);
  const warningColor = getColor('warning', 500);
  const dangerColor = getColor('danger', 500);
  const accentColor = getColor('info', 500);
  // Используем централизованные функции темизации вместо прямых designTokens

  // Загрузка данных
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Симуляция загрузки данных
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Тестовые данные
      const mockPatients = [
        {
          id: 1,
          name: 'Ахмедов Алишер',
          age: 45,
          gender: 'М',
          phone: '+998 90 123 45 67',
          diagnosis: 'Гипертония',
          status: 'active',
          lastVisit: '2024-01-15',
          nextAppointment: '2024-01-20'
        },
        {
          id: 2,
          name: 'Каримова Зухра',
          age: 32,
          gender: 'Ж',
          phone: '+998 91 234 56 78',
          diagnosis: 'Диабет 2 типа',
          status: 'active',
          lastVisit: '2024-01-14',
          nextAppointment: '2024-01-18'
        },
        {
          id: 3,
          name: 'Тошматов Бахтиёр',
          age: 28,
          gender: 'М',
          phone: '+998 93 345 67 89',
          diagnosis: 'Астма',
          status: 'recovery',
          lastVisit: '2024-01-12',
          nextAppointment: '2024-01-25'
        }
      ];

      const mockAppointments = [
        {
          id: 1,
          patientId: 1,
          patientName: 'Ахмедов Алишер',
          time: '09:00',
          type: 'Консультация',
          status: 'scheduled',
          notes: 'Плановый осмотр'
        },
        {
          id: 2,
          patientId: 2,
          patientName: 'Каримова Зухра',
          time: '10:30',
          type: 'Повторный прием',
          status: 'in_progress',
          notes: 'Контроль сахара'
        },
        {
          id: 3,
          patientId: 3,
          patientName: 'Тошматов Бахтиёр',
          time: '14:00',
          type: 'Экстренный',
          status: 'completed',
          notes: 'Обострение астмы'
        }
      ];

      setPatients(mockPatients);
      setAppointments(mockAppointments);
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Измерение высоты заголовка
  useEffect(() => {
    if (headerRef.current) {
      setHeaderHeight(headerRef.current.offsetHeight);
    }
  }, [isMobile, isTablet]);

  // Стили
  const pageStyle = {
    minHeight: '100vh',
    background: `linear-gradient(135deg, ${getColor('primary', 50)} 0%, ${getColor('secondary', 50)} 100%)`,
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    lineHeight: '1.5',
    color: getColor('secondary', 800)
  };

  const headerStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1000,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    backdropFilter: 'blur(20px)',
    borderBottom: `1px solid ${getColor('primary', 200)}`,
    boxShadow: getShadow('lg')
  };

  const headerContentStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: '0 auto'
  };

  const logoStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    color: 'white',
    fontSize: isMobile ? getFontSize('lg') : getFontSize('xl'),
    fontWeight: '700',
    textDecoration: 'none'
  };

  const headerActionsStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: isMobile ? getSpacing('sm') : getSpacing('md')
  };

  const contentStyle = {
    marginTop: `${headerHeight + 20}px`,
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: `${headerHeight + 20}px auto 0 auto`
  };

  const tabsStyle = {
    display: 'flex',
    gap: isMobile ? getSpacing('sm') : getSpacing('md'),
    marginBottom: getSpacing('xl'),
    overflowX: 'auto',
    paddingBottom: getSpacing('sm')
  };

  const tabStyle = {
    padding: isMobile ? `${getSpacing('sm')} ${getSpacing('md')}` : `${getSpacing('md')} ${getSpacing('lg')}`,
    borderRadius: '12px',
    background: 'rgba(255, 255, 255, 0.8)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    color: getColor('secondary', 700),
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    fontWeight: '500',
    cursor: 'pointer',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    whiteSpace: 'nowrap',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    minWidth: isMobile ? 'auto' : '120px',
    justifyContent: isMobile ? 'center' : 'flex-start'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    boxShadow: `0 4px 14px 0 ${primaryColor}30`,
    transform: 'translateY(-2px)'
  };

  const dashboardGridStyle = {
    display: 'grid',
    gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
    gap: getSpacing('lg'),
    marginBottom: getSpacing('xl')
  };

  const statCardStyle = {
    background: 'rgba(255, 255, 255, 0.9)',
    borderRadius: '20px',
    padding: getSpacing('lg'),
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'pointer'
  };

  const statCardHoverStyle = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: getShadow('2xl')
  };

  const patientsTableStyle = {
    background: 'rgba(255, 255, 255, 0.9)',
    borderRadius: '20px',
    overflow: 'hidden',
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    border: '1px solid rgba(255, 255, 255, 0.2)'
  };

  const tableHeaderStyle = {
    background: `linear-gradient(135deg, ${getColor('secondary', 50)} 0%, ${getColor('secondary', 100)} 100%)`,
    padding: getSpacing('lg'),
    borderBottom: `1px solid ${getColor('secondary', 200)}`
  };

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  const thStyle = {
    padding: getSpacing('md'),
    textAlign: 'left',
    fontWeight: '600',
    color: getColor('secondary', 700),
    fontSize: getFontSize('sm'),
    borderBottom: `1px solid ${getColor('secondary', 200)}`
  };

  const tdStyle = {
    padding: getSpacing('md'),
    borderBottom: `1px solid ${getColor('secondary', 100)}`,
    fontSize: getFontSize('sm'),
    color: getColor('secondary', 600)
  };

  const actionButtonStyle = {
    padding: getSpacing('xs'),
    borderRadius: '8px',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: getSpacing('xs')
  };

  // Функции
  const getStatusVariant = (status) => {
    const statusMap = {
      'active': 'success',
      'recovery': 'warning',
      'critical': 'danger',
      'scheduled': 'primary',
      'in_progress': 'warning',
      'completed': 'success',
      'cancelled': 'danger'
    };
    return statusMap[status] || 'default';
  };

  const getStatusText = (status) => {
    const statusMap = {
      'active': 'Активен',
      'recovery': 'Выздоравливает',
      'critical': 'Критический',
      'scheduled': 'Запланирован',
      'in_progress': 'В процессе',
      'completed': 'Завершен',
      'cancelled': 'Отменен'
    };
    return statusMap[status] || status;
  };

  // ✅ УЛУЧШЕНИЕ: Обработчик с универсальным хуком
  const handlePatientClick = (patient) => {
    patientModal.openModal(patient);
  };

  const filteredPatients = patients.filter(patient => {
    const matchesSearch = patient.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         patient.phone.includes(searchQuery);
    const matchesFilter = filterStatus === 'all' || patient.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const filteredAppointments = appointments.filter(appointment => {
    const matchesSearch = appointment.patientName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterStatus === 'all' || appointment.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  // Рендер
  return (
    <div style={pageStyle}>
      {/* Заголовок */}
      <header ref={headerRef} style={headerStyle}>
        <div style={headerContentStyle}>
          <div style={logoStyle}>
            <Stethoscope size={isMobile ? 24 : 28} />
            {!isMobile && <span>Панель врача</span>}
          </div>
          
          <div style={headerActionsStyle}>
            <Button variant="ghost" size={isMobile ? 'sm' : 'md'} style={{ color: 'white' }}>
              <Bell size={isMobile ? 16 : 20} />
              {!isMobile && <span>Уведомления</span>}
            </Button>
            <Button variant="ghost" size={isMobile ? 'sm' : 'md'} style={{ color: 'white' }}>
              <Settings size={isMobile ? 16 : 20} />
              {!isMobile && <span>Настройки</span>}
            </Button>
            <Button variant="ghost" size={isMobile ? 'sm' : 'md'} style={{ color: 'white' }}>
              <LogOut size={isMobile ? 16 : 20} />
              {!isMobile && <span>Выход</span>}
            </Button>
          </div>
        </div>
      </header>

      {/* Основной контент */}
      <main style={contentStyle}>
        {/* Вкладки */}
        <div style={tabsStyle}>
          <button
            style={activeTab === 'dashboard' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('dashboard')}
            onMouseEnter={(e) => {
              if (activeTab !== 'dashboard') {
                e.target.style.background = 'rgba(255, 255, 255, 0.9)';
                e.target.style.transform = 'translateY(-2px)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'dashboard') {
                e.target.style.background = 'rgba(255, 255, 255, 0.8)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            <Activity size={isMobile ? 16 : 20} />
            {!isMobile && <span>Панель</span>}
          </button>
          
          <button
            style={activeTab === 'patients' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('patients')}
            onMouseEnter={(e) => {
              if (activeTab !== 'patients') {
                e.target.style.background = 'rgba(255, 255, 255, 0.9)';
                e.target.style.transform = 'translateY(-2px)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'patients') {
                e.target.style.background = 'rgba(255, 255, 255, 0.8)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            <User size={isMobile ? 16 : 20} />
            {!isMobile && <span>Пациенты</span>}
          </button>
          
          <button
            style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('appointments')}
            onMouseEnter={(e) => {
              if (activeTab !== 'appointments') {
                e.target.style.background = 'rgba(255, 255, 255, 0.9)';
                e.target.style.transform = 'translateY(-2px)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'appointments') {
                e.target.style.background = 'rgba(255, 255, 255, 0.8)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            <Calendar size={isMobile ? 16 : 20} />
            {!isMobile && <span>Записи</span>}
          </button>
          
          <button
            style={activeTab === 'ai' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('ai')}
            onMouseEnter={(e) => {
              if (activeTab !== 'ai') {
                e.target.style.background = 'rgba(255, 255, 255, 0.9)';
                e.target.style.transform = 'translateY(-2px)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'ai') {
                e.target.style.background = 'rgba(255, 255, 255, 0.8)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            <Brain size={isMobile ? 16 : 20} />
            {!isMobile && <span>AI Помощник</span>}
          </button>
          
          <button
            style={activeTab === 'reports' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('reports')}
            onMouseEnter={(e) => {
              if (activeTab !== 'reports') {
                e.target.style.background = 'rgba(255, 255, 255, 0.9)';
                e.target.style.transform = 'translateY(-2px)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== 'reports') {
                e.target.style.background = 'rgba(255, 255, 255, 0.8)';
                e.target.style.transform = 'translateY(0)';
              }
            }}
          >
            <FileText size={isMobile ? 16 : 20} />
            {!isMobile && <span>Отчеты</span>}
          </button>
        </div>

        {/* Контент вкладок */}
        {activeTab === 'dashboard' && (
          <AnimatedTransition type="fade" delay={100}>
            <div>
              {/* Статистика */}
              <div style={dashboardGridStyle}>
                <AnimatedTransition type="scale" delay={200}>
                  <Card
                    style={statCardStyle}
                    onMouseEnter={(e) => {
                      Object.assign(e.currentTarget.style, statCardHoverStyle);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0) scale(1)';
                      e.currentTarget.style.boxShadow = getShadow('lg');
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white'
                      }}>
                        <User size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {patients.length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
                          Активных пациентов
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={300}>
                  <Card
                    style={statCardStyle}
                    onMouseEnter={(e) => {
                      Object.assign(e.currentTarget.style, statCardHoverStyle);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0) scale(1)';
                      e.currentTarget.style.boxShadow = getShadow('lg');
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: `linear-gradient(135deg, ${successColor} 0%, ${getColor('success', 600)} 100%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white'
                      }}>
                        <Calendar size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter(a => a.status === 'scheduled').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
                          Записей на сегодня
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={400}>
                  <Card
                    style={statCardStyle}
                    onMouseEnter={(e) => {
                      Object.assign(e.currentTarget.style, statCardHoverStyle);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0) scale(1)';
                      e.currentTarget.style.boxShadow = getShadow('lg');
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: `linear-gradient(135deg, ${warningColor} 0%, ${getColor('warning', 600)} 100%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white'
                      }}>
                        <Clock size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter(a => a.status === 'in_progress').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
                          В процессе
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={500}>
                  <Card
                    style={statCardStyle}
                    onMouseEnter={(e) => {
                      Object.assign(e.currentTarget.style, statCardHoverStyle);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.transform = 'translateY(0) scale(1)';
                      e.currentTarget.style.boxShadow = getShadow('lg');
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: `linear-gradient(135deg, ${accentColor} 0%, ${getColor('info', 600)} 100%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white'
                      }}>
                        <CheckCircle size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter(a => a.status === 'completed').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
                          Завершено сегодня
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>
              </div>

              {/* Быстрые действия */}
              <AnimatedTransition type="fade" delay={600}>
                <Card style={{ marginBottom: getSpacing('xl') }}>
                  <Card.Header>
                    <h2 style={{ 
                      fontSize: getFontSize('xl'), 
                      fontWeight: '700',
                      color: getColor('secondary', 800),
                      margin: 0
                    }}>
                      Быстрые действия
                    </h2>
                  </Card.Header>
                  <Card.Content>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
                      gap: getSpacing('md')
                    }}>
                      <Button variant="primary" fullWidth>
                        <Plus size={20} />
                        Новый пациент
                      </Button>
                      <Button variant="secondary" fullWidth>
                        <Calendar size={20} />
                        Записать на прием
                      </Button>
                      <Button variant="success" fullWidth>
                        <FileText size={20} />
                        Создать отчет
                      </Button>
                      <Button variant="info" fullWidth>
                        <Download size={20} />
                        Экспорт данных
                      </Button>
                    </div>
                  </Card.Content>
                </Card>
              </AnimatedTransition>
            </div>
          </AnimatedTransition>
        )}

        {activeTab === 'patients' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <Card.Header style={tableHeaderStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: getSpacing('md') }}>
                  <h2 style={{ 
                    fontSize: getFontSize('xl'), 
                    fontWeight: '700',
                    color: getColor('secondary', 800),
                    margin: 0
                  }}>
                    Пациенты
                  </h2>
                  <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={20} style={{ position: 'absolute', left: getSpacing('sm'), top: '50%', transform: 'translateY(-50%)', color: getColor('secondary', 400) }} />
                      <input
                        type="text"
                        placeholder="Поиск пациентов..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('sm')} ${getSpacing('sm')} 40px`,
                          border: `1px solid ${getColor('secondary', 200)}`,
                          borderRadius: '12px',
                          fontSize: getFontSize('sm'),
                          width: isMobile ? '200px' : '250px',
                          background: 'white'
                        }}
                      />
                    </div>
                    <select
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                      style={{
                        padding: getSpacing('sm'),
                        border: `1px solid ${getColor('secondary', 200)}`,
                        borderRadius: '12px',
                        fontSize: getFontSize('sm'),
                        background: 'white'
                      }}
                    >
                      <option value="all">Все статусы</option>
                      <option value="active">Активные</option>
                      <option value="recovery">Выздоравливающие</option>
                      <option value="critical">Критические</option>
                    </select>
                    <Button variant="primary">
                      <Plus size={16} />
                      {!isMobile && <span>Добавить</span>}
                    </Button>
                  </div>
                </div>
              </Card.Header>
              <Card.Content style={{ padding: 0 }}>
                {loading ? (
                  <Skeleton.Table rows={5} columns={6} />
                ) : (
                  <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th style={thStyle}>Пациент</th>
                        <th style={thStyle}>Возраст</th>
                        <th style={thStyle}>Телефон</th>
                        <th style={thStyle}>Диагноз</th>
                        <th style={thStyle}>Статус</th>
                        <th style={thStyle}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPatients.map((patient, index) => (
                        <tr
                          key={patient.id}
                          style={{
                            cursor: 'pointer',
                            transition: 'background-color 0.2s ease'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = getColor('primary', 50);
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          onClick={() => handlePatientClick(patient)}
                        >
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
                              <div style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '50%',
                                background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: 'white',
                                fontSize: getFontSize('sm'),
                                fontWeight: '700'
                              }}>
                                {patient.name.split(' ').map(n => n[0]).join('')}
                              </div>
                              <div>
                                <div style={{ fontWeight: '500', color: getColor('secondary', 800) }}>
                                  {patient.name}
                                </div>
                                <div style={{ fontSize: getFontSize('xs'), color: getColor('secondary', 500) }}>
                                  {patient.gender}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td style={tdStyle}>{patient.age} лет</td>
                          <td style={tdStyle}>{patient.phone}</td>
                          <td style={tdStyle}>{patient.diagnosis}</td>
                          <td style={tdStyle}>
                            <Badge variant={getStatusVariant(patient.status)} size="md">
                              {getStatusText(patient.status)}
                            </Badge>
                          </td>
                          <td style={tdStyle}>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('primary', 100), color: primaryColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                handlePatientClick(patient);
                              }}
                            >
                              <Edit size={16} />
                            </button>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                console.log('View patient', patient.id);
                              }}
                            >
                              <Eye size={16} />
                            </button>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                console.log('Delete patient', patient.id);
                              }}
                            >
                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card.Content>
            </Card>
          </AnimatedTransition>
        )}

        {activeTab === 'appointments' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <Card.Header style={tableHeaderStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: getSpacing('md') }}>
                  <h2 style={{ 
                    fontSize: getFontSize('xl'), 
                    fontWeight: '700',
                    color: getColor('secondary', 800),
                    margin: 0
                  }}>
                    Записи на прием
                  </h2>
                  <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={20} style={{ position: 'absolute', left: getSpacing('sm'), top: '50%', transform: 'translateY(-50%)', color: getColor('secondary', 400) }} />
                      <input
                        type="text"
                        placeholder="Поиск записей..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('sm')} ${getSpacing('sm')} 40px`,
                          border: `1px solid ${getColor('secondary', 200)}`,
                          borderRadius: '12px',
                          fontSize: getFontSize('sm'),
                          width: isMobile ? '200px' : '250px',
                          background: 'white'
                        }}
                      />
                    </div>
                    <select
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value)}
                      style={{
                        padding: getSpacing('sm'),
                        border: `1px solid ${getColor('secondary', 200)}`,
                        borderRadius: '12px',
                        fontSize: getFontSize('sm'),
                        background: 'white'
                      }}
                    >
                      <option value="all">Все статусы</option>
                      <option value="scheduled">Запланированы</option>
                      <option value="in_progress">В процессе</option>
                      <option value="completed">Завершены</option>
                      <option value="cancelled">Отменены</option>
                    </select>
                    <Button 
                      variant="primary"
                      onClick={() => setScheduleNextModal({ open: true, patient: null })}
                    >
                      <Plus size={16} />
                      {!isMobile && <span>Назначить следующий визит</span>}
                    </Button>
                  </div>
                </div>
              </Card.Header>
              <Card.Content style={{ padding: 0 }}>
                {loading ? (
                  <Skeleton.Table rows={5} columns={6} />
                ) : (
                  <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th style={thStyle}>Время</th>
                        <th style={thStyle}>Пациент</th>
                        <th style={thStyle}>Тип</th>
                        <th style={thStyle}>Статус</th>
                        <th style={thStyle}>Примечания</th>
                        <th style={thStyle}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAppointments.map((appointment, index) => (
                        <tr
                          key={appointment.id}
                          style={{
                            cursor: 'pointer',
                            transition: 'background-color 0.2s ease'
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = getColor('primary', 50);
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = 'transparent';
                          }}
                        >
                          <td style={tdStyle}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
                              <Clock size={16} style={{ color: getColor('secondary', 400) }} />
                              {appointment.time}
                            </div>
                          </td>
                          <td style={tdStyle}>{appointment.patientName}</td>
                          <td style={tdStyle}>{appointment.type}</td>
                          <td style={tdStyle}>
                            <Badge variant={getStatusVariant(appointment.status)} size="md">
                              {getStatusText(appointment.status)}
                            </Badge>
                          </td>
                          <td style={tdStyle}>{appointment.notes}</td>
                          <td style={tdStyle}>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('primary', 100), color: primaryColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                console.log('Edit appointment', appointment.id);
                              }}
                            >
                              <Edit size={16} />
                            </button>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                console.log('Complete appointment', appointment.id);
                              }}
                            >
                              <CheckCircle size={16} />
                            </button>
                            <button
                              style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                              onClick={(e) => {
                                e.stopPropagation();
                                console.log('Cancel appointment', appointment.id);
                              }}
                            >
                              <XCircle size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card.Content>
            </Card>
          </AnimatedTransition>
        )}

        {activeTab === 'ai' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card>
              <Card.Header>
                <h2 style={{ 
                  fontSize: getFontSize('xl'), 
                  fontWeight: '700',
                  color: getColor('secondary', 800),
                  margin: 0
                }}>
                  AI Помощник врача
                </h2>
              </Card.Header>
              <Card.Content>
                <AIAssistant
                  specialty="general"
                  onSuggestionSelect={(type, suggestion) => {
                    console.log('AI предложение для общего врача:', type, suggestion);
                  }}
                />
              </Card.Content>
            </Card>
          </AnimatedTransition>
        )}

        {activeTab === 'reports' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card>
              <Card.Header>
                <h2 style={{ 
                  fontSize: getFontSize('xl'), 
                  fontWeight: '700',
                  color: getColor('secondary', 800),
                  margin: 0
                }}>
                  Отчеты и аналитика
                </h2>
              </Card.Header>
              <Card.Content>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)',
                  gap: getSpacing('lg')
                }}>
                  <Button variant="primary" fullWidth>
                    <FileText size={20} />
                    Отчет по пациентам
                  </Button>
                  <Button variant="secondary" fullWidth>
                    <Calendar size={20} />
                    Отчет по записям
                  </Button>
                  <Button variant="success" fullWidth>
                    <Activity size={20} />
                    Статистика работы
                  </Button>
                  <Button variant="warning" fullWidth>
                    <Pill size={20} />
                    Отчет по лекарствам
                  </Button>
                  <Button variant="info" fullWidth>
                    <Heart size={20} />
                    Медицинская статистика
                  </Button>
                  <Button variant="ghost" fullWidth>
                    <Download size={20} />
                    Экспорт всех данных
                  </Button>
                </div>
              </Card.Content>
            </Card>
          </AnimatedTransition>
        )}
      </main>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пациента с универсальным хуком */}
      {patientModal.isOpen && patientModal.selectedItem && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '12px',
            padding: '24px',
            width: '100%',
            maxWidth: '500px',
            margin: '16px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '20px', fontWeight: '600', color: '#111827', margin: 0 }}>
                Информация о пациенте
              </h3>
              <button 
                onClick={patientModal.closeModal}
                style={{ 
                  color: '#9CA3AF', 
                  cursor: 'pointer', 
                  border: 'none', 
                  background: 'none',
                  padding: '4px',
                  borderRadius: '4px'
                }}
              >
                <XCircle size={24} />
              </button>
            </div>
            
            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                <div style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: '#3B82F6',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: '18px',
                  fontWeight: '600'
                }}>
                  {patientModal.selectedItem.name?.charAt(0) || 'П'}
                </div>
                <div>
                  <h4 style={{ fontSize: '18px', fontWeight: '600', color: '#111827', margin: 0 }}>
                    {patientModal.selectedItem.name || 'Неизвестно'}
                  </h4>
                  <p style={{ fontSize: '14px', color: '#6B7280', margin: 0 }}>
                    {patientModal.selectedItem.phone || 'Телефон не указан'}
                  </p>
                </div>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 4px 0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Возраст
                  </p>
                  <p style={{ fontSize: '16px', color: '#111827', margin: 0, fontWeight: '500' }}>
                    {patientModal.selectedItem.age || 'Не указан'}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: '12px', color: '#6B7280', margin: '0 0 4px 0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Статус
                  </p>
                  <p style={{ fontSize: '16px', color: '#111827', margin: 0, fontWeight: '500' }}>
                    {patientModal.selectedItem.status === 'active' ? 'Активный' : 
                     patientModal.selectedItem.status === 'waiting' ? 'Ожидает' : 
                     patientModal.selectedItem.status || 'Неизвестно'}
                  </p>
                </div>
              </div>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button
                onClick={patientModal.closeModal}
                style={{
                  padding: '8px 16px',
                  border: '1px solid #D1D5DB',
                  borderRadius: '6px',
                  backgroundColor: 'white',
                  color: '#374151',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Закрыть
              </button>
              <button
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  borderRadius: '6px',
                  backgroundColor: '#3B82F6',
                  color: 'white',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: '500'
                }}
              >
                Редактировать
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open && (
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
        />
      )}
    </div>
  );
};

export default DoctorPanel;
