// Утилиты для аудита frontend структуры
import { useTheme } from '../contexts/ThemeContext';

/**
 * Карта файлов frontend с их назначением и рекомендуемым местом
 */
export const FRONTEND_FILE_MAP = {
  // Core и layout
  'src/App.jsx': {
    purpose: 'Главный компонент приложения, роутинг, провайдеры',
    currentLocation: 'src/',
    recommendedLocation: 'src/',
    status: 'correct',
    issues: ['Использует старый ThemeProvider вместо AppProviders']
  },
  
  'src/main.jsx': {
    purpose: 'Точка входа приложения',
    currentLocation: 'src/',
    recommendedLocation: 'src/',
    status: 'correct'
  },

  // API и данные
  'src/api/client.js': {
    purpose: 'Централизованный API клиент с axios',
    currentLocation: 'src/api/',
    recommendedLocation: 'src/api/',
    status: 'correct'
  },
  
  'src/api/endpoints.js': {
    purpose: 'Централизованные API endpoints',
    currentLocation: 'src/api/',
    recommendedLocation: 'src/api/',
    status: 'correct'
  },
  
  'src/api/services.js': {
    purpose: 'Централизованные API сервисы',
    currentLocation: 'src/api/',
    recommendedLocation: 'src/api/',
    status: 'correct'
  },

  // Типы и константы
  'src/types/api.js': {
    purpose: 'Типы данных для API интеграции',
    currentLocation: 'src/types/',
    recommendedLocation: 'src/types/',
    status: 'correct'
  },
  
  'src/constants/routes.js': {
    purpose: 'Конфигурация маршрутов и ролей',
    currentLocation: 'src/constants/',
    recommendedLocation: 'src/constants/',
    status: 'correct'
  },

  // Провайдеры
  'src/providers/AppProviders.jsx': {
    purpose: 'Главный провайдер для всех контекстов',
    currentLocation: 'src/providers/',
    recommendedLocation: 'src/providers/',
    status: 'correct'
  },

  // Контексты
  'src/contexts/ThemeContext.jsx': {
    purpose: 'Контекст темы',
    currentLocation: 'src/contexts/',
    recommendedLocation: 'src/contexts/',
    status: 'correct'
  },

  // Общие компоненты
  'src/components/common/ErrorBoundary.jsx': {
    purpose: 'Обработка ошибок React',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/Toast.jsx': {
    purpose: 'Система уведомлений',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/Loading.jsx': {
    purpose: 'Компоненты загрузки',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/Modal.jsx': {
    purpose: 'Система модальных окон',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/Form.jsx': {
    purpose: 'Система форм с валидацией',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/Table.jsx': {
    purpose: 'Система таблиц',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },
  
  'src/components/common/RoleGuard.jsx': {
    purpose: 'Ролевые ограничения доступа',
    currentLocation: 'src/components/common/',
    recommendedLocation: 'src/components/common/',
    status: 'correct'
  },

  // Аутентификация
  'src/components/auth/RequireAuth.jsx': {
    purpose: 'Ролевые ограничения маршрутов',
    currentLocation: 'src/components/auth/',
    recommendedLocation: 'src/components/auth/',
    status: 'correct'
  },

  // Навигация
  'src/components/navigation/ProtectedRoute.jsx': {
    purpose: 'Защищенные маршруты',
    currentLocation: 'src/components/navigation/',
    recommendedLocation: 'src/components/navigation/',
    status: 'correct'
  },

  // Утилиты
  'src/utils/themeChecker.js': {
    purpose: 'Проверка и исправление темы',
    currentLocation: 'src/utils/',
    recommendedLocation: 'src/utils/',
    status: 'correct'
  },
  
  'src/utils/frontendAudit.js': {
    purpose: 'Аудит frontend структуры',
    currentLocation: 'src/utils/',
    recommendedLocation: 'src/utils/',
    status: 'correct'
  },

  // Хуки
  'src/hooks/useAdminData.js': {
    purpose: 'Хук для данных администратора',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useAnimation.js': {
    purpose: 'Хук для анимаций',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useAppointments.js': {
    purpose: 'Хук для записей на прием',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useDoctors.js': {
    purpose: 'Хук для врачей',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useFinance.js': {
    purpose: 'Хук для финансов',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useHotkeys.js': {
    purpose: 'Хук для горячих клавиш',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useMediaQuery.js': {
    purpose: 'Хук для медиа-запросов',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useOptimizedData.js': {
    purpose: 'Хук для оптимизированных данных',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/usePatients.js': {
    purpose: 'Хук для пациентов',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/usePWA.js': {
    purpose: 'Хук для PWA',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useReports.js': {
    purpose: 'Хук для отчетов',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useSecurity.js': {
    purpose: 'Хук для безопасности',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useSettings.js': {
    purpose: 'Хук для настроек',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },
  
  'src/hooks/useUsers.js': {
    purpose: 'Хук для пользователей',
    currentLocation: 'src/hooks/',
    recommendedLocation: 'src/hooks/',
    status: 'correct'
  },

  // Стили
  'src/styles/theme.css': {
    purpose: 'Основные стили темы',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/admin.css': {
    purpose: 'Стили административной панели',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/admin-dark-theme.css': {
    purpose: 'Темная тема административной панели',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/animations.css': {
    purpose: 'Анимации',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/cursor-effects.css': {
    purpose: 'Эффекты курсора',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/full-width.css': {
    purpose: 'Полноширинные стили',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/responsive.css': {
    purpose: 'Адаптивные стили',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/sidebar-buttons.css': {
    purpose: 'Стили кнопок сайдбара',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },
  
  'src/styles/unified-sidebar.css': {
    purpose: 'Унифицированные стили сайдбара',
    currentLocation: 'src/styles/',
    recommendedLocation: 'src/styles/',
    status: 'correct'
  },

  // Страницы
  'src/pages/AdminPanel.jsx': {
    purpose: 'Панель администратора',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/AdminPanelNew.jsx': {
    purpose: 'Новая панель администратора',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/AnalyticsPage.jsx': {
    purpose: 'Страница аналитики',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/Audit.jsx': {
    purpose: 'Страница аудита',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/SecurityPage.jsx': {
    purpose: 'Страница безопасности',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/Settings.jsx': {
    purpose: 'Страница настроек',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/admin/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/admin/']
  },
  
  'src/pages/DoctorPanel.jsx': {
    purpose: 'Панель врача',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/doctor/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/doctor/']
  },
  
  'src/pages/CardiologistPanelUnified.jsx': {
    purpose: 'Панель кардиолога',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/doctor/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/doctor/']
  },
  
  'src/pages/DermatologistPanelUnified.jsx': {
    purpose: 'Панель дерматолога',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/doctor/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/doctor/']
  },
  
  'src/pages/DentistPanelUnified.jsx': {
    purpose: 'Панель стоматолога',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/doctor/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/doctor/']
  },
  
  'src/pages/RegistrarPanel.jsx': {
    purpose: 'Панель регистратуры',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/registrar/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/registrar/']
  },
  
  'src/pages/CashierPanel.jsx': {
    purpose: 'Панель кассы',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/cashier/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/cashier/']
  },
  
  'src/pages/LabPanel.jsx': {
    purpose: 'Панель лаборатории',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/lab/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/lab/']
  },
  
  'src/pages/PatientPanel.jsx': {
    purpose: 'Панель пациента',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/patient/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/patient/']
  },
  
  'src/pages/QueueBoard.jsx': {
    purpose: 'Доска очереди',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/public/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/public/']
  },
  
  'src/pages/DisplayBoardUnified.jsx': {
    purpose: 'Доска отображения',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/public/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/public/']
  },
  
  'src/pages/Login.jsx': {
    purpose: 'Страница входа',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/auth/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/auth/']
  },
  
  'src/pages/UserSelect.jsx': {
    purpose: 'Выбор пользователя',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/auth/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/auth/']
  },
  
  'src/pages/Activation.jsx': {
    purpose: 'Активация',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/auth/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/auth/']
  },
  
  'src/pages/Landing.jsx': {
    purpose: 'Главная страница',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/Health.jsx': {
    purpose: 'Страница здоровья системы',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/Search.jsx': {
    purpose: 'Поиск',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/Appointments.jsx': {
    purpose: 'Записи на прием',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/Scheduler.jsx': {
    purpose: 'Планировщик',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/VisitDetails.jsx': {
    purpose: 'Детали визита',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/',
    status: 'correct'
  },
  
  'src/pages/MobilePatientDashboard.jsx': {
    purpose: 'Мобильная панель пациента',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/mobile/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/mobile/']
  },
  
  'src/pages/MediLabDemo.jsx': {
    purpose: 'Демо MediLab',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/demo/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/demo/']
  },
  
  'src/pages/NewApp.jsx': {
    purpose: 'Новое приложение',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/demo/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/demo/']
  },
  
  'src/pages/AppOld.jsx': {
    purpose: 'Старое приложение',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/demo/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/demo/']
  },
  
  'src/pages/AppNew.jsx': {
    purpose: 'Новое приложение',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/demo/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/demo/']
  },
  
  'src/pages/TestComponent.jsx': {
    purpose: 'Тестовый компонент',
    currentLocation: 'src/pages/',
    recommendedLocation: 'src/pages/test/',
    status: 'needs_move',
    issues: ['Следует переместить в src/pages/test/']
  },

  // Компоненты
  'src/components/Header.jsx': {
    purpose: 'Заголовок приложения',
    currentLocation: 'src/components/',
    recommendedLocation: 'src/components/layout/',
    status: 'needs_move',
    issues: ['Следует переместить в src/components/layout/']
  },
  
  'src/components/Sidebar.jsx': {
    purpose: 'Боковая панель',
    currentLocation: 'src/components/',
    recommendedLocation: 'src/components/layout/',
    status: 'needs_move',
    issues: ['Следует переместить в src/components/layout/']
  },
  
  'src/components/Footer.jsx': {
    purpose: 'Подвал приложения',
    currentLocation: 'src/components/',
    recommendedLocation: 'src/components/layout/',
    status: 'needs_move',
    issues: ['Следует переместить в src/components/layout/']
  },
  
  'src/components/Navbar.jsx': {
    purpose: 'Навигационная панель',
    currentLocation: 'src/components/',
    recommendedLocation: 'src/components/layout/',
    status: 'needs_move',
    issues: ['Следует переместить в src/components/layout/']
  },
  
  'src/components/AppShell.jsx': {
    purpose: 'Оболочка приложения',
    currentLocation: 'src/components/',
    recommendedLocation: 'src/components/layout/',
    status: 'needs_move',
    issues: ['Следует переместить в src/components/layout/']
  }
};

/**
 * Получает статистику по файлам
 */
export function getFileStats() {
  const files = Object.values(FRONTEND_FILE_MAP);
  const stats = {
    total: files.length,
    correct: files.filter(f => f.status === 'correct').length,
    needsMove: files.filter(f => f.status === 'needs_move').length,
    needsFix: files.filter(f => f.status === 'needs_fix').length,
    hasIssues: files.filter(f => f.issues && f.issues.length > 0).length
  };
  
  return stats;
}

/**
 * Получает файлы по статусу
 */
export function getFilesByStatus(status) {
  return Object.entries(FRONTEND_FILE_MAP)
    .filter(([_, file]) => file.status === status)
    .map(([path, file]) => ({ path, ...file }));
}

/**
 * Получает файлы с проблемами
 */
export function getFilesWithIssues() {
  return Object.entries(FRONTEND_FILE_MAP)
    .filter(([_, file]) => file.issues && file.issues.length > 0)
    .map(([path, file]) => ({ path, ...file }));
}

/**
 * Получает рекомендуемую структуру папок
 */
export function getRecommendedStructure() {
  return {
    'src/': [
      'App.jsx',
      'main.jsx'
    ],
    'src/api/': [
      'client.js',
      'endpoints.js',
      'services.js'
    ],
    'src/types/': [
      'api.js'
    ],
    'src/constants/': [
      'routes.js'
    ],
    'src/providers/': [
      'AppProviders.jsx'
    ],
    'src/contexts/': [
      'ThemeContext.jsx'
    ],
    'src/components/common/': [
      'ErrorBoundary.jsx',
      'Toast.jsx',
      'Loading.jsx',
      'Modal.jsx',
      'Form.jsx',
      'Table.jsx',
      'RoleGuard.jsx'
    ],
    'src/components/auth/': [
      'RequireAuth.jsx'
    ],
    'src/components/navigation/': [
      'ProtectedRoute.jsx'
    ],
    'src/components/layout/': [
      'Header.jsx',
      'Sidebar.jsx',
      'Footer.jsx',
      'Navbar.jsx',
      'AppShell.jsx'
    ],
    'src/hooks/': [
      'useAdminData.js',
      'useAnimation.js',
      'useAppointments.js',
      'useDoctors.js',
      'useFinance.js',
      'useHotkeys.js',
      'useMediaQuery.js',
      'useOptimizedData.js',
      'usePatients.js',
      'usePWA.js',
      'useReports.js',
      'useSecurity.js',
      'useSettings.js',
      'useUsers.js'
    ],
    'src/pages/admin/': [
      'AdminPanel.jsx',
      'AdminPanelNew.jsx',
      'AnalyticsPage.jsx',
      'Audit.jsx',
      'SecurityPage.jsx',
      'Settings.jsx'
    ],
    'src/pages/doctor/': [
      'DoctorPanel.jsx',
      'CardiologistPanelUnified.jsx',
      'DermatologistPanelUnified.jsx',
      'DentistPanelUnified.jsx'
    ],
    'src/pages/registrar/': [
      'RegistrarPanel.jsx'
    ],
    'src/pages/cashier/': [
      'CashierPanel.jsx'
    ],
    'src/pages/lab/': [
      'LabPanel.jsx'
    ],
    'src/pages/patient/': [
      'PatientPanel.jsx'
    ],
    'src/pages/public/': [
      'QueueBoard.jsx',
      'DisplayBoardUnified.jsx'
    ],
    'src/pages/auth/': [
      'Login.jsx',
      'UserSelect.jsx',
      'Activation.jsx'
    ],
    'src/pages/mobile/': [
      'MobilePatientDashboard.jsx'
    ],
    'src/pages/demo/': [
      'MediLabDemo.jsx',
      'NewApp.jsx',
      'AppOld.jsx',
      'AppNew.jsx'
    ],
    'src/pages/test/': [
      'TestComponent.jsx'
    ],
    'src/pages/': [
      'Landing.jsx',
      'Health.jsx',
      'Search.jsx',
      'Appointments.jsx',
      'Scheduler.jsx',
      'VisitDetails.jsx'
    ],
    'src/styles/': [
      'theme.css',
      'admin.css',
      'admin-dark-theme.css',
      'animations.css',
      'cursor-effects.css',
      'full-width.css',
      'responsive.css',
      'sidebar-buttons.css',
      'unified-sidebar.css'
    ],
    'src/utils/': [
      'themeChecker.js',
      'frontendAudit.js'
    ]
  };
}

/**
 * Компонент для отображения аудита frontend
 */
export function FrontendAuditDisplay() {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  const stats = getFileStats();
  const filesWithIssues = getFilesWithIssues();
  const recommendedStructure = getRecommendedStructure();

  const containerStyle = {
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'primary'),
    borderRadius: '8px',
    marginBottom: getSpacing('md')
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('lg')
  };

  const statsStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: getSpacing('md'),
    marginBottom: getSpacing('lg')
  };

  const statCardStyle = {
    padding: getSpacing('md'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px',
    border: `1px solid ${getColor('border', 'light')}`
  };

  const statTitleStyle = {
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('xs')
  };

  const statValueStyle = {
    fontSize: getFontSize('lg'),
    fontWeight: '600',
    color: getColor('text', 'primary')
  };

  const issuesStyle = {
    marginBottom: getSpacing('lg')
  };

  const issueItemStyle = {
    padding: getSpacing('sm'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '4px',
    marginBottom: getSpacing('xs'),
    borderLeft: `4px solid ${getColor('warning', 'main')}`
  };

  const issuePathStyle = {
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('xs')
  };

  const issueTextStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('text', 'secondary')
  };

  const structureStyle = {
    marginTop: getSpacing('lg')
  };

  const folderStyle = {
    marginBottom: getSpacing('md')
  };

  const folderTitleStyle = {
    fontSize: getFontSize('md'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('sm')
  };

  const fileListStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('text', 'secondary'),
    marginLeft: getSpacing('md')
  };

  return (
    <div style={containerStyle}>
      <h2 style={titleStyle}>Аудит Frontend Структуры</h2>
      
      <div style={statsStyle}>
        <div style={statCardStyle}>
          <div style={statTitleStyle}>Всего файлов</div>
          <div style={statValueStyle}>{stats.total}</div>
        </div>
        <div style={statCardStyle}>
          <div style={statTitleStyle}>Правильно размещены</div>
          <div style={statValueStyle}>{stats.correct}</div>
        </div>
        <div style={statCardStyle}>
          <div style={statTitleStyle}>Требуют перемещения</div>
          <div style={statValueStyle}>{stats.needsMove}</div>
        </div>
        <div style={statCardStyle}>
          <div style={statTitleStyle}>С проблемами</div>
          <div style={statValueStyle}>{stats.hasIssues}</div>
        </div>
      </div>

      {filesWithIssues.length > 0 && (
        <div style={issuesStyle}>
          <h3 style={{ fontSize: getFontSize('lg'), marginBottom: getSpacing('md') }}>
            Файлы с проблемами
          </h3>
          {filesWithIssues.map((file, index) => (
            <div key={index} style={issueItemStyle}>
              <div style={issuePathStyle}>{file.path}</div>
              {file.issues.map((issue, issueIndex) => (
                <div key={issueIndex} style={issueTextStyle}>
                  • {issue}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <div style={structureStyle}>
        <h3 style={{ fontSize: getFontSize('lg'), marginBottom: getSpacing('md') }}>
          Рекомендуемая структура
        </h3>
        {Object.entries(recommendedStructure).map(([folder, files]) => (
          <div key={folder} style={folderStyle}>
            <div style={folderTitleStyle}>{folder}</div>
            <div style={fileListStyle}>
              {files.map((file, index) => (
                <div key={index}>• {file}</div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
