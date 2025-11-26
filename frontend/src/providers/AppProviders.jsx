// Главный провайдер для всех контекстов приложения
import React from 'react';
import { ThemeProvider } from '../contexts/ThemeContext';
import { TranslationProvider } from '../hooks/useTranslation';
import { AppDataProvider } from '../contexts/AppDataContext';
import { ToastProvider } from '../components/common/Toast';
import { ModalProvider } from '../components/common/Modal';
import { FormProvider } from '../components/common/Form';
import ErrorBoundary from '../components/common/ErrorBoundary';

/**
 * Главный провайдер для всех контекстов
 */
export function AppProviders({ children }) {
  return (
    <TranslationProvider>
      <ThemeProvider>
        <AppDataProvider>
          <ErrorBoundary>
            <ToastProvider>
              <ModalProvider>
                <FormProvider>
                  {children}
                </FormProvider>
              </ModalProvider>
            </ToastProvider>
          </ErrorBoundary>
        </AppDataProvider>
      </ThemeProvider>
    </TranslationProvider>
  );
}

export default AppProviders;
