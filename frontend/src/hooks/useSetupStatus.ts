import { useEffect, useState } from 'react';
import logger from '../utils/logger';
import { fetchSetupStatus } from '../api/setup';

export function useSetupStatus() {
  interface SetupStatus {
  initialized: boolean;
  isLoading: boolean;
  error: string | null;
}

  const [status, setStatus] = useState<SetupStatus>({
    initialized: true,
    isLoading: true,
    error: null as string | null
  });

  useEffect(() => {
    let isActive = true;

    const loadStatus = async () => {
      try {
        const payload = await fetchSetupStatus();
        if (!isActive) {
          return;
        }

        setStatus({
          initialized: Boolean(payload?.initialized),
          isLoading: false,
          error: null as string | null
        });
      } catch (error) {
        logger.warn('[setup] failed to load setup status', {
          error: error?.message || 'unknown error'
        });

        if (!isActive) {
          return;
        }

        setStatus({
          initialized: true,
          isLoading: false,
          error
        });
      }
    };

    void loadStatus();

    return () => {
      isActive = false;
    };
  }, []);

  return status;
}
