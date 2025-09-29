import React, { useState, useEffect } from 'react';
import { Button, Card, CardContent, Typography, Box, IconButton } from '@mui/material';
import { GetApp, Close, Smartphone, Computer } from '@mui/icons-material';

const PWAInstallPrompt = () => {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Проверяем, установлено ли приложение
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
    }

    // Слушаем событие beforeinstallprompt
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setShowInstallPrompt(true);
    };

    // Слушаем событие appinstalled
    const handleAppInstalled = () => {
      setIsInstalled(true);
      setShowInstallPrompt(false);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;

    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      console.log('Пользователь принял установку PWA');
    } else {
      console.log('Пользователь отклонил установку PWA');
    }
    
    setDeferredPrompt(null);
    setShowInstallPrompt(false);
  };

  const handleDismiss = () => {
    setShowInstallPrompt(false);
    // Сохраняем в localStorage, что пользователь отклонил установку
    localStorage.setItem('pwa-install-dismissed', 'true');
  };

  // Не показываем, если приложение уже установлено или пользователь отклонил
  if (isInstalled || !showInstallPrompt) {
    return null;
  }

  // Проверяем, не отклонил ли пользователь ранее
  if (localStorage.getItem('pwa-install-dismissed') === 'true') {
    return null;
  }

  return (
    <Card 
      sx={{ 
        position: 'fixed', 
        bottom: 16, 
        right: 16, 
        zIndex: 1000,
        maxWidth: 350,
        boxShadow: 3
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box display="flex" alignItems="center" gap={1}>
            <Smartphone color="primary" />
            <Typography variant="h6" component="h3">
              Установить приложение
            </Typography>
          </Box>
          <IconButton size="small" onClick={handleDismiss}>
            <Close />
          </IconButton>
        </Box>
        
        <Typography variant="body2" color="text.secondary" mb={2}>
          Установите наше приложение для быстрого доступа и лучшего опыта работы
        </Typography>
        
        <Box display="flex" gap={1} flexWrap="wrap">
          <Button
            variant="contained"
            startIcon={<GetApp />}
            onClick={handleInstallClick}
            size="small"
          >
            Установить
          </Button>
          <Button
            variant="outlined"
            onClick={handleDismiss}
            size="small"
          >
            Позже
          </Button>
        </Box>
        
        <Box mt={2} display="flex" alignItems="center" gap={1}>
          <Computer fontSize="small" color="action" />
          <Typography variant="caption" color="text.secondary">
            Доступно для установки на мобильных устройствах
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PWAInstallPrompt;

