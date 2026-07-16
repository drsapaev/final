import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import { TranslationProvider } from './i18n/useTranslation';
import { MacOSThemeProvider } from './theme/macosTheme.jsx';
import Landing from './pages/Landing.jsx';
import Login from './pages/Login.jsx';
import LoginFormStyled from './components/auth/LoginFormStyled.jsx';
import PropTypes from 'prop-types';

const App = lazy(() => import('./App.jsx'));

function PublicProviders({ children }) {
  return (
    <MacOSThemeProvider>
      <ThemeProvider>
        <TranslationProvider>{children}</TranslationProvider>
      </ThemeProvider>
    </MacOSThemeProvider>
  );
}


PublicProviders.propTypes = {
  ...(PublicProviders.propTypes || {}),
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
