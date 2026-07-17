// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useCallback } from 'react';
import { toast } from 'react-toastify';

import logger from '../utils/logger';
/**
 * Универсальный хук для async действий с обработкой ошибок
 * Устраняет дублирование async обработчиков в панелях
 */
export const useAsyncAction = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeAction = useCallback(async (
    actionFn, 
    {
      loadingMessage = null,
      successMessage = null as unknown,
      errorMessage = 'Произошла ошибка',
      onSuccess = null as unknown,
      onError = null as unknown,
      showToast = true as boolean
    } = {}
  ) => {
    setLoading(true);
    setError(null);

    if (loadingMessage && showToast) {
      toast.loading(loadingMessage);
    }

    try {
      const result = await actionFn();
      
      if (successMessage && showToast) {
        toast.dismiss();
        toast.success(successMessage);
      }

      if (onSuccess) {
        (onSuccess as (...args: unknown[]) => void)(result);
      }

      return result;
    } catch (err) {
      logger.error('AsyncAction error:', err);
      setError(String(err));

      if (showToast) {
        toast.dismiss();
        toast.error(errorMessage);
      }

      if (onError) {
        (onError as (...args: unknown[]) => void)(err);
      }

      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    error,
    executeAction
  };
};

export default useAsyncAction;

