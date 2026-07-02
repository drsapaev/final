import { useState, useEffect } from 'react';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { fetchWizardSettings } from '../api/adminSettings';
const useWizardSettings = () => {
  const [settings, setSettings] = useState({
    use_new_wizard: true,  // 🎯 По умолчанию используем НОВЫЙ мастер (V2)
    loading: true,
    error: null
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setSettings(prev => ({ ...prev, loading: true, error: null }));

      const token = tokenManager.getAccessToken();
      if (!token) {
        logger.warn('No auth token found, using default wizard settings');
        setSettings({
          use_new_wizard: true, // 🎯 По умолчанию используем НОВЫЙ мастер (V2)
          loading: false,
          error: null
        });
        return;
      }

      try {
        const data = await fetchWizardSettings();

        setSettings({
          use_new_wizard: data.use_new_wizard !== undefined ? data.use_new_wizard : true,
          loading: false,
          error: null
        });
      } catch (error) {
        const status = error?.response?.status;
        if (status === 401) {
          logger.warn('Unauthorized access to wizard settings, using default');
          setSettings({
            use_new_wizard: true, // 🎯 По умолчанию используем НОВЫЙ мастер (V2)
            loading: false,
            error: null
          });
          return;
        }
        throw error;
      }
    } catch (error) {
      logger.error('Error fetching wizard settings:', error);
      setSettings({
        use_new_wizard: true, // 🎯 По умолчанию используем НОВЫЙ мастер (V2)
        loading: false,
        error: null // Не показываем ошибку пользователю, просто используем дефолт
      });
    }
  };

  return {
    useNewWizard: settings.use_new_wizard,
    loading: settings.loading,
    error: settings.error,
    refetch: fetchSettings
  };
};

export default useWizardSettings;
