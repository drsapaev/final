import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Badge,
} from '../ui/macos';
import {
  Download,
  X,
  Smartphone,
  WifiOff,
  Bell,
  RefreshCw,
  CheckCircle,
} from 'lucide-react';
import { usePWA } from '../../hooks/usePWA';

import logger from '../../utils/logger';
const PWAInstallPrompt = ({ onClose }) => {
  const {
    isInstallable,
    isInstalled,
    isOnline,
    updateAvailable,
    installPWA,
    updateServiceWorker,
    requestNotificationPermission,
    capabilities
  } = usePWA();

  const [isInstalling, setIsInstalling] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState(
    'Notification' in window ? Notification.permission : 'not-supported'
  );

  const handleInstall = async () => {
    setIsInstalling(true);
    try {
      const success = await installPWA();
      if (success && onClose) {
        setTimeout(onClose, 1000);
      }
    } catch (error) {
      logger.error('Installation failed:', error);
    } finally {
      setIsInstalling(false);
    }
  };

  const handleUpdate = () => {
    updateServiceWorker();
  };

  const handleNotificationPermission = async () => {
    const permission = await requestNotificationPermission();
    setNotificationPermission(permission);
  };

  // Если приложение уже установлено и нет обновлений, не показываем
  if (isInstalled && !updateAvailable) {
    return null;
  }

  return (
    <Slide direction="up" in={true} mountOnEnter unmountOnExit>
      <Box
        position="fixed"
        bottom={16}
        left={16}
        right={16}
        zIndex={1300}
        sx={{ maxWidth: 400, mx: 'auto' }}
      >
        <Card elevation={8}>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
              <Box display="flex" alignItems="center" gap={1}>
                <Smartphone color="primary" />
                <Typography variant="h6" component="div">
                  {updateAvailable ? 'Обновление доступно' : 'Установить приложение'}
                </Typography>
              </Box>
              {onClose && (
                <IconButton size="small" onClick={onClose}>
                  <Close />
                </IconButton>
              )}
            </Box>

            {updateAvailable ? (
              <Box>
                <Typography variant="body2" color="text.secondary" mb={2}>
                  Доступна новая версия приложения с улучшениями и исправлениями.
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<Update />}
                  onClick={handleUpdate}
                  fullWidth
                >
                  Обновить приложение
                </Button>
              </Box>
            ) : isInstallable ? (
              <Box>
                <Typography variant="body2" color="text.secondary" mb={2}>
                  Установите приложение на домашний экран для быстрого доступа и работы офлайн.
                </Typography>

                <Stack spacing={1} mb={2}>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip
                      icon={isOnline ? <CheckCircle /> : <WifiOff />}
                      label={isOnline ? 'Онлайн' : 'Офлайн режим'}
                      color={isOnline ? 'success' : 'warning'}
                      size="small"
                    />
                    {capabilities.notifications && (
                      <Chip
                        icon={<Notifications />}
                        label="Push уведомления"
                        color={notificationPermission === 'granted' ? 'success' : 'default'}
                        size="small"
                        onClick={notificationPermission !== 'granted' ? handleNotificationPermission : undefined}
                        clickable={notificationPermission !== 'granted'}
                      />
                    )}
                  </Box>
                </Stack>

                <Stack spacing={1}>
                  <Button
                    variant="contained"
                    startIcon={<GetApp />}
                    onClick={handleInstall}
                    disabled={isInstalling}
                    fullWidth
                  >
                    {isInstalling ? 'Установка...' : 'Установить приложение'}
                  </Button>
                  
                  {capabilities.notifications && notificationPermission === 'default' && (
                    <Button
                      variant="outlined"
                      startIcon={<Notifications />}
                      onClick={handleNotificationPermission}
                      size="small"
                    >
                      Разрешить уведомления
                    </Button>
                  )}
                </Stack>
              </Box>
            ) : (
              <Alert severity="info">
                Приложение уже установлено или не поддерживается вашим браузером.
              </Alert>
            )}

            {/* Показываем возможности PWA */}
            <Box mt={2}>
              <Typography variant="caption" color="text.secondary" display="block" mb={1}>
                Возможности приложения:
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap">
                {capabilities.serviceWorker && (
                  <Chip label="Офлайн работа" size="small" variant="outlined" />
                )}
                {capabilities.notifications && (
                  <Chip label="Уведомления" size="small" variant="outlined" />
                )}
                {capabilities.backgroundSync && (
                  <Chip label="Синхронизация" size="small" variant="outlined" />
                )}
                {capabilities.webShare && (
                  <Chip label="Быстрый доступ" size="small" variant="outlined" />
                )}
              </Stack>
            </Box>
          </CardContent>
        </Card>
      </Box>
    </Slide>
  );
};

export default PWAInstallPrompt;

