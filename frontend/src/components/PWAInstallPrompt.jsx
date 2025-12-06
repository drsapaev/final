import React, { useState, useEffect } from 'react';
import { Button, Card, CardContent, Typography, Box } from './ui/macos';
import { Download, X, Smartphone, Monitor } from 'lucide-react';

import logger from '../utils/logger';
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
      logger.log('Пользователь принял установку PWA');
    } else {
      logger.log('Пользователь отклонил установку PWA');
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
      style={{ 
        position: 'fixed', 
        bottom: 16, 
        right: 16, 
        zIndex: 1000,
        maxWidth: 350,
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
      }}
    >
      <CardContent>
        <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <Box style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Smartphone size={20} color="#007aff" />
            <Typography variant="h6" component="h3">
              Установить приложение
            </Typography>
          </Box>
          <Button
            variant="ghost"
            size="small"
            onClick={handleDismiss}
            style={{ padding: '4px', minWidth: 'auto' }}
          >
            <X size={16} />
          </Button>
        </Box>
        
        <Typography variant="body2" color="secondary" style={{ marginBottom: 16 }}>
          Установите наше приложение для быстрого доступа и лучшего опыта работы
        </Typography>
        
        <Box style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button
            variant="primary"
            onClick={handleInstallClick}
            size="small"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Download size={16} />
            Установить
          </Button>
          <Button
            variant="outline"
            onClick={handleDismiss}
            size="small"
          >
            Позже
          </Button>
        </Box>
        
        <Box style={{ marginTop: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Monitor size={14} color="#666" />
          <Typography variant="caption" color="secondary">
            Доступно для установки на мобильных устройствах
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PWAInstallPrompt;

