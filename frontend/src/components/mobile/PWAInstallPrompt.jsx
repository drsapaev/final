import React, { useState, useEffect } from 'react';
import { Download, X, Smartphone, Monitor } from 'lucide-react';
import { Button, Card } from '../ui/native';

/**
 * Компонент для предложения установки PWA
 */
const PWAInstallPrompt = () => {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showInstallPrompt, setShowInstallPrompt] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Проверяем, установлено ли уже PWA
    const checkIfInstalled = () => {
      const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
      const isIOSStandalone = window.navigator.standalone === true;
      setIsInstalled(isStandalone || isIOSStandalone);
    };

    checkIfInstalled();

    // Слушаем событие beforeinstallprompt
    const handleBeforeInstallPrompt = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setShowInstallPrompt(true);
    };

    // Слушаем событие appinstalled
    const handleAppInstalled = () => {
      console.log('PWA установлено');
      setIsInstalled(true);
      setShowInstallPrompt(false);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);

    // Автоматически скрываем промпт через 10 секунд
    const timer = setTimeout(() => {
      setShowInstallPrompt(false);
    }, 10000);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
      clearTimeout(timer);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;

    try {
      // Показываем промпт установки
      deferredPrompt.prompt();
      
      // Ждем результат
      const { outcome } = await deferredPrompt.userChoice;
      
      if (outcome === 'accepted') {
        console.log('Пользователь принял установку PWA');
      } else {
        console.log('Пользователь отклонил установку PWA');
      }
      
      // Очищаем промпт
      setDeferredPrompt(null);
      setShowInstallPrompt(false);
    } catch (error) {
      console.error('Ошибка при установке PWA:', error);
    }
  };

  const handleDismiss = () => {
    setShowInstallPrompt(false);
    // Сохраняем в localStorage, что пользователь отклонил установку
    localStorage.setItem('pwa-install-dismissed', 'true');
  };

  // Не показываем, если уже установлено или пользователь отклонил
  if (isInstalled || !showInstallPrompt) {
    return null;
  }

  // Проверяем, не отклонил ли пользователь ранее
  const wasDismissed = localStorage.getItem('pwa-install-dismissed');
  if (wasDismissed) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:left-auto md:right-4 md:max-w-sm">
      <Card className="bg-gradient-to-r from-blue-500 to-purple-600 text-white border-0 shadow-lg">
        <div className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Smartphone className="w-5 h-5" />
              <h3 className="font-semibold text-lg">Установить приложение</h3>
            </div>
            <button
              onClick={handleDismiss}
              className="text-white/70 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          
          <p className="text-white/90 text-sm mb-4">
            Установите приложение клиники для быстрого доступа и работы в офлайн режиме
          </p>
          
          <div className="flex space-x-2">
            <Button
              onClick={handleInstall}
              className="flex-1 bg-white text-blue-600 hover:bg-white/90 font-medium"
            >
              <Download className="w-4 h-4 mr-2" />
              Установить
            </Button>
            
            <Button
              onClick={handleDismiss}
              variant="outline"
              className="border-white/30 text-white hover:bg-white/10"
            >
              Позже
            </Button>
          </div>
          
          <div className="mt-3 text-xs text-white/70">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <Monitor className="w-3 h-3" />
                <span>Быстрый доступ</span>
              </div>
              <div className="flex items-center space-x-1">
                <Smartphone className="w-3 h-3" />
                <span>Офлайн режим</span>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default PWAInstallPrompt;

