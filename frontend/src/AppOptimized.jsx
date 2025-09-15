import React, { useEffect, useState, Suspense, lazy } from 'react';
import { Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AppProviders } from './providers/AppProviders';
import { PWAInstallPrompt, ConnectionStatus } from './components/pwa';
import usePWA from './hooks/usePWA.js';
import './styles/theme.css';

// Компоненты которые нужны сразу (критичные)
import Header from './components/layout/Header.jsx';
import Sidebar from './components/layout/Sidebar.jsx';
import Health from './pages/Health.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';

// Lazy loading для всех остальных страниц
const CashierPanel = lazy(() => import('./pages/CashierPanel.jsx'));
const Settings = lazy(() => import('./pages/Settings.jsx'));
const Audit = lazy(() => import('./pages/Audit.jsx'));
const Scheduler = lazy(() => import('./pages/Scheduler.jsx'));
const Appointments = lazy(() => import('./pages/Appointments.jsx'));
const VisitDetails = lazy(() => import('./pages/VisitDetails.jsx'));
const AdminPanel = lazy(() => import('./pages/AdminPanel.jsx'));
const RegistrarPanel = lazy(() => import('./pages/RegistrarPanel.jsx'));
const DoctorPanel = lazy(() => import('./pages/DoctorPanel.jsx'));

// Специализированные панели
const CardiologistPanelUnified = lazy(() => import('./pages/CardiologistPanelUnified.jsx'));
const DermatologistPanelUnified = lazy(() => import('./pages/DermatologistPanelUnified.jsx'));
const DentistPanelUnified = lazy(() => import('./pages/DentistPanelUnified.jsx'));
const LabPanel = lazy(() => import('./pages/LabPanel.jsx'));

// Остальные страницы
const UserSelect = lazy(() => import('./pages/UserSelect.jsx'));
const Search = lazy(() => import('./pages/Search.jsx'));
const PatientPanel = lazy(() => import('./pages/PatientPanel.jsx'));
const QueueBoard = lazy(() => import('./pages/QueueBoard.jsx'));
const DisplayBoardUnified = lazy(() => import('./pages/DisplayBoardUnified.jsx'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage.jsx'));
const MediLabDemo = lazy(() => import('./pages/MediLabDemo.jsx'));

// Платежные страницы
const QueueJoin = lazy(() => import('./pages/QueueJoin.jsx'));
const PaymentSuccess = lazy(() => import('./pages/PaymentSuccess.jsx'));
const PaymentCancel = lazy(() => import('./pages/PaymentCancel.jsx'));
const PaymentTest = lazy(() => import('./pages/PaymentTest.jsx'));

// Новые компоненты
const TestComponent = lazy(() => import('./components/TestComponent.jsx'));
const SimpleDashboard = lazy(() => import('./components/dashboard/SimpleDashboard.jsx'));
const SimpleUserManagement = lazy(() => import('./components/admin/SimpleUserManagement.jsx'));
const SimpleEMR = lazy(() => import('./components/medical/SimpleEMR.jsx'));
const SimpleFileManager = lazy(() => import('./components/SimpleFileManager.jsx'));
const LoginFormStyled = lazy(() => import('./components/auth/LoginFormStyled.jsx'));
const NewComponentsNav = lazy(() => import('./components/NewComponentsNav.jsx'));

// Мобильные страницы
const MobilePatientDashboard = lazy(() => import('./pages/MobilePatientDashboard.jsx'));

// Новые страницы
const Activation = lazy(() => import('./pages/Activation.jsx'));
const AdminPanelNew = lazy(() => import('./pages/AdminPanelNew.jsx'));
const EmailSMSPage = lazy(() => import('./pages/EmailSMSPage.jsx'));
const FileSystemPage = lazy(() => import('./pages/FileSystemPage.jsx'));
const NewApp = lazy(() => import('./pages/NewApp.jsx'));
const SecurityPage = lazy(() => import('./pages/SecurityPage.jsx'));
const TelegramPage = lazy(() => import('./pages/TelegramPage.jsx'));

// Компонент загрузки
const LoadingSpinner = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
    <div className="ml-4 text-lg text-gray-600">Загрузка...</div>
  </div>
);

// Компонент ошибки
const ErrorBoundary = ({ children }) => {
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const handleError = (error) => {
      console.error('Chunk load error:', error);
      setHasError(true);
    };

    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  if (hasError) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-4">
            Ошибка загрузки
          </h2>
          <p className="text-gray-600 mb-4">
            Не удалось загрузить компонент. Попробуйте обновить страницу.
          </p>
          <button 
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Обновить страницу
          </button>
        </div>
      </div>
    );
  }

  return children;
};

// Обертка для lazy компонентов
const LazyWrapper = ({ children }) => (
  <ErrorBoundary>
    <Suspense fallback={<LoadingSpinner />}>
      {children}
    </Suspense>
  </ErrorBoundary>
);

function AppContent() {
  const { shouldShowInstallPrompt } = usePWA();

  return (
    <>
      <ConnectionStatus />
      {shouldShowInstallPrompt() && <PWAInstallPrompt />}
      <Routes>
        {/* Критичные маршруты без lazy loading */}
        <Route path="/login" element={<Login />} />
        <Route path="/health" element={<Health />} />
        <Route path="/" element={<Landing />} />

        {/* Lazy loaded маршруты */}
        <Route path="/new-login" element={
          <LazyWrapper><LoginFormStyled /></LazyWrapper>
        } />
        
        <Route path="/components" element={
          <LazyWrapper><NewComponentsNav /></LazyWrapper>
        } />

        {/* Основные панели */}
        <Route path="/admin" element={
          <LazyWrapper><AdminPanel /></LazyWrapper>
        } />
        
        <Route path="/admin-new" element={
          <LazyWrapper><AdminPanelNew /></LazyWrapper>
        } />
        
        <Route path="/doctor" element={
          <LazyWrapper><DoctorPanel /></LazyWrapper>
        } />
        
        <Route path="/registrar" element={
          <LazyWrapper><RegistrarPanel /></LazyWrapper>
        } />
        
        <Route path="/cashier" element={
          <LazyWrapper><CashierPanel /></LazyWrapper>
        } />

        {/* Специализированные панели */}
        <Route path="/cardiologist" element={
          <LazyWrapper><CardiologistPanelUnified /></LazyWrapper>
        } />
        
        <Route path="/dermatologist" element={
          <LazyWrapper><DermatologistPanelUnified /></LazyWrapper>
        } />
        
        <Route path="/dentist" element={
          <LazyWrapper><DentistPanelUnified /></LazyWrapper>
        } />
        
        <Route path="/lab" element={
          <LazyWrapper><LabPanel /></LazyWrapper>
        } />

        {/* Пациентские панели */}
        <Route path="/patient" element={
          <LazyWrapper><PatientPanel /></LazyWrapper>
        } />
        
        <Route path="/mobile" element={
          <LazyWrapper><MobilePatientDashboard /></LazyWrapper>
        } />

        {/* Очереди и табло */}
        <Route path="/queue" element={
          <LazyWrapper><QueueBoard /></LazyWrapper>
        } />
        
        <Route path="/display" element={
          <LazyWrapper><DisplayBoardUnified /></LazyWrapper>
        } />
        
        <Route path="/queue-join" element={
          <LazyWrapper><QueueJoin /></LazyWrapper>
        } />

        {/* Платежи */}
        <Route path="/payment/success" element={
          <LazyWrapper><PaymentSuccess /></LazyWrapper>
        } />
        
        <Route path="/payment/cancel" element={
          <LazyWrapper><PaymentCancel /></LazyWrapper>
        } />
        
        <Route path="/payment/test" element={
          <LazyWrapper><PaymentTest /></LazyWrapper>
        } />

        {/* Управление */}
        <Route path="/settings" element={
          <LazyWrapper><Settings /></LazyWrapper>
        } />
        
        <Route path="/audit" element={
          <LazyWrapper><Audit /></LazyWrapper>
        } />
        
        <Route path="/security" element={
          <LazyWrapper><SecurityPage /></LazyWrapper>
        } />

        {/* Коммуникации */}
        <Route path="/email-sms" element={
          <LazyWrapper><EmailSMSPage /></LazyWrapper>
        } />
        
        <Route path="/telegram" element={
          <LazyWrapper><TelegramPage /></LazyWrapper>
        } />

        {/* Файлы и данные */}
        <Route path="/files" element={
          <LazyWrapper><FileSystemPage /></LazyWrapper>
        } />
        
        <Route path="/analytics" element={
          <LazyWrapper><AnalyticsPage /></LazyWrapper>
        } />

        {/* Расписание и визиты */}
        <Route path="/scheduler" element={
          <LazyWrapper><Scheduler /></LazyWrapper>
        } />
        
        <Route path="/appointments" element={
          <LazyWrapper><Appointments /></LazyWrapper>
        } />
        
        <Route path="/visit/:id" element={
          <LazyWrapper><VisitDetails /></LazyWrapper>
        } />

        {/* Поиск и навигация */}
        <Route path="/search" element={
          <LazyWrapper><Search /></LazyWrapper>
        } />
        
        <Route path="/user-select" element={
          <LazyWrapper><UserSelect /></LazyWrapper>
        } />

        {/* Демо и тестирование */}
        <Route path="/demo" element={
          <LazyWrapper><MediLabDemo /></LazyWrapper>
        } />
        
        <Route path="/test" element={
          <LazyWrapper><TestComponent /></LazyWrapper>
        } />
        
        <Route path="/new-app" element={
          <LazyWrapper><NewApp /></LazyWrapper>
        } />

        {/* Активация */}
        <Route path="/activation" element={
          <LazyWrapper><Activation /></LazyWrapper>
        } />

        {/* Новые компоненты */}
        <Route path="/simple-dashboard" element={
          <LazyWrapper><SimpleDashboard /></LazyWrapper>
        } />
        
        <Route path="/simple-users" element={
          <LazyWrapper><SimpleUserManagement /></LazyWrapper>
        } />
        
        <Route path="/simple-emr" element={
          <LazyWrapper><SimpleEMR /></LazyWrapper>
        } />
        
        <Route path="/simple-files" element={
          <LazyWrapper><SimpleFileManager /></LazyWrapper>
        } />

        {/* Редирект по умолчанию */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <AppProviders>
      <AppContent />
    </AppProviders>
  );
}

export default App;
