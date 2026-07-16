// @ts-nocheck — Phase 2: file converted .js → .ts but not yet fully typed.
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
      loadingMessage: unknown = null,
      successMessage: unknown = null,
      errorMessage = 'Произошла ошибка',
      onSuccess: unknown = null,
      onError: unknown = null,
      showToast = true
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
        onSuccess(result);
      }

      return result;
    } catch (err) {
      logger.error('AsyncAction error:', err);
      setError(err);

      if (showToast) {
        toast.dismiss();
        toast.error(errorMessage);
      }

      if (onError) {
        onError(err);
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

