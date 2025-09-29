import React, { useState, useEffect } from 'react';

const useWizardSettings = () => {
  const [settings, setSettings] = useState({
    use_new_wizard: false,
    loading: true,
    error: null
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setSettings(prev => ({ ...prev, loading: true, error: null }));
      
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.warn('No auth token found, using default wizard settings');
        setSettings({
          use_new_wizard: false, // По умолчанию используем старый мастер
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
          console.warn('Unauthorized access to wizard settings, using default');
          setSettings({
            use_new_wizard: false, // По умолчанию используем старый мастер
            loading: false,
            error: null
          });
          return;
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      setSettings({
        use_new_wizard: data.use_new_wizard || false,
        loading: false,
        error: null
      });
    } catch (error) {
      console.error('Error fetching wizard settings:', error);
      setSettings({
        use_new_wizard: false, // По умолчанию используем старый мастер
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
