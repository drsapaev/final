import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { TranslationProvider } from './i18n/useTranslation';
import { MacOSThemeProvider } from './theme/macosTheme';
import Landing from './pages/Landing';
import Login from './pages/Login';
import LoginFormStyled from './components/auth/LoginFormStyled';
import PropTypes from 'prop-types';

const App = lazy(() => import('./App'));

function PublicProviders({ children }) {
  return (
    <MacOSThemeProvider>
      <ThemeProvider>
        <TranslationProvider>{children}</TranslationProvider>
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}


// audit/strict: removed self-referencing propTypes spread
PublicProviders.propTypes = {
  children: PropTypes.any,
};

function AppBridge() {
  return (
    <Suspense
      fallback={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
          Загрузка...
        </div>
      }
    >
      <App />
    </Suspense>
  );
}

export default function PublicApp() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <PublicProviders>
            <Landing />
          </PublicProviders>
        }
      />
      <Route
        path="/login"
        element={
          <PublicProviders>
            <LoginFormStyled />
          </PublicProviders>
        }
      />
      <Route
        path="/old-login"
        element={
          <PublicProviders>
            <Login />
          </PublicProviders>
        }
      />
      <Route path="/health" element={<Navigate to="/" replace />} />
      <Route path="*" element={<AppBridge />} />
    </Routes>
  );
}
