import { TranslationProvider } from '../hooks/useTranslation';
import { AppDataProvider } from '../contexts/AppDataContext';
import { ChatProvider } from '../contexts/ChatContext';
import { ToastProvider } from '../components/common/Toast';
import { ModalProvider } from '../components/common/Modal';
import { FormProvider } from '../components/common/Form';
import ErrorBoundary from '../components/common/ErrorBoundary';
import { NotificationPrompt } from '../components/chat/NotificationPrompt';
import { NotificationWebSocketProvider } from '../contexts/NotificationWebSocketContext';

/**
 * Главный провайдер для всех контекстов.
 * ThemeProvider находится уровнем выше, в App.jsx, чтобы не плодить независимые theme-state.
 */
export function AppProviders({ children }) {
  return (
    <TranslationProvider>
      <AppDataProvider>
        <ChatProvider>
          <ErrorBoundary>
            <ToastProvider>
              <NotificationWebSocketProvider>
                <ModalProvider>
                  <FormProvider>
                    {children}
                    <NotificationPrompt />
                  </FormProvider>
                </ModalProvider>
              </NotificationWebSocketProvider>
            </ToastProvider>
          </ErrorBoundary>
        </ChatProvider>
      </AppDataProvider>
    </TranslationProvider>);

}

export default AppProviders;
