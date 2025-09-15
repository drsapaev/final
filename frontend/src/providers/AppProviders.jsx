// Главный провайдер для всех контекстов приложения
import React from 'react';
import { ThemeProvider } from '../contexts/ThemeContext';
import { ToastProvider } from '../components/common/Toast';
import { ModalProvider } from '../components/common/Modal';
import { FormProvider } from '../components/common/Form';
import ErrorBoundary from '../components/common/ErrorBoundary';

/**
 * Главный провайдер для всех контекстов
 */
export function AppProviders({ children }) {
  return (
    <ThemeProvider>
      <ErrorBoundary>
        <ToastProvider>
          <ModalProvider>
            <FormProvider>
              {children}
            </FormProvider>
          </ModalProvider>
        </ToastProvider>
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default AppProviders;
