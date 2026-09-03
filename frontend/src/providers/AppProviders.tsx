import { TranslationProvider } from '../i18n/useTranslation';
import { AppDataProvider } from '../contexts/AppDataContext';
import { ChatProvider } from '../contexts/ChatContext';
import { ToastProvider } from '../components/common/Toast';
import { FormProvider } from '../components/common/Form';
import ErrorBoundary from '../components/common/ErrorBoundary';
import { NotificationPrompt } from '../components/chat/NotificationPrompt';
import { NotificationCenterProvider } from '../contexts/NotificationCenterContext';
import { NotificationWebSocketProvider } from '../contexts/NotificationWebSocketContext';

/**
 * Главный провайдер для всех контекстов.
 * ThemeProvider находится уровнем выше, в App.jsx, чтобы не плодить независимые theme-state.
 */
export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <TranslationProvider>
      <AppDataProvider>
        <ChatProvider>
          <ErrorBoundary>
            <ToastProvider>
              <NotificationCenterProvider>
                <NotificationWebSocketProvider>
                  <FormProvider>
                    {children}
                    <NotificationPrompt />
                  </FormProvider>
                </NotificationWebSocketProvider>
              </NotificationCenterProvider>
            </ToastProvider>
          </ErrorBoundary>
        </ChatProvider>
      </AppDataProvider>
    </TranslationProvider>);

}


// audit/strict: removed self-referencing propTypes spread

export default AppProviders;
