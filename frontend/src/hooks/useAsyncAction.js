import { useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';

/**
 * Универсальный хук для async действий с обработкой ошибок
 * Устраняет дублирование async обработчиков в AdminPanel
 */
export const useAsyncAction = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeAction = useCallback(async (
    actionFn, 
    {
      loadingMessage = null,
      successMessage = null,
      errorMessage = 'Произошла ошибка',
      onSuccess = null,
      onError = null,
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
      console.error('AsyncAction error:', err);
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

