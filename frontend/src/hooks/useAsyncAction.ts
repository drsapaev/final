import { useCallback, useState } from 'react';
import { toast } from 'react-toastify';

import logger from '../utils/logger';

interface AsyncActionOptions {
  loadingMessage?: string | null;
  successMessage?: string | null;
  errorMessage?: string;
  onSuccess?: (result: unknown) => void;
  onError?: (err: unknown) => void;
  showToast?: boolean;
}

interface UseAsyncActionReturn {
  loading: boolean;
  error: string | null;
  executeAction: (
    actionFn: () => Promise<unknown>,
    options?: AsyncActionOptions,
  ) => Promise<unknown>;
}

/**
 * Универсальный хук для async действий с обработкой ошибок.
 * Устраняет дублирование async обработчиков в панелях.
 */
export const useAsyncAction = (): UseAsyncActionReturn => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const executeAction = useCallback(
    async (
      actionFn: () => Promise<unknown>,
      {
        loadingMessage = null,
        successMessage = null,
        errorMessage = 'Произошла ошибка',
        onSuccess,
        onError,
        showToast = true,
      }: AsyncActionOptions = {},
    ): Promise<unknown> => {
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
        setError(String(err));

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
    },
    [],
  );

  return {
    loading,
    error,
    executeAction,
  };
};

export default useAsyncAction;
