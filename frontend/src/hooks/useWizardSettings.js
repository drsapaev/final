import { useState, useEffect } from 'react';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
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

      // Используем абсолютный URL для обхода dev proxy
      const response = await fetch('http://localhost:8000/api/v1/admin/wizard-settings', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          logger.warn('Unauthorized access to wizard settings, using default');
          setSettings({
            use_new_wizard: true, // 🎯 По умолчанию используем НОВЫЙ мастер (V2)
            loading: false,
            error: null
          });
          return;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      setSettings({
        use_new_wizard: data.use_new_wizard !== undefined ? data.use_new_wizard : true, // 🎯 Дефолт - НОВЫЙ мастер
        loading: false,
        error: null
      });
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
