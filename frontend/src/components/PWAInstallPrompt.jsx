import React from 'react';
import { Download, X, Smartphone, Monitor } from 'lucide-react';
import { usePWA } from '../hooks/usePWA';
import { Button, Card } from '../design-system/components';

const PWAInstallPrompt = () => {
  const { isInstallable, isInstalled, isOnline, installApp } = usePWA();
  const [showPrompt, setShowPrompt] = React.useState(false);
  const [dismissed, setDismissed] = React.useState(false);

  React.useEffect(() => {
    if (isInstallable && !isInstalled && !dismissed) {
      // Показываем промпт через 3 секунды после загрузки
      const timer = setTimeout(() => {
        setShowPrompt(true);
      }, 3000);

      return () => clearTimeout(timer);
    }
  }, [isInstallable, isInstalled, dismissed]);

  const handleInstall = async () => {
    const success = await installApp();
    if (success) {
      setShowPrompt(false);
    }
  };

  const handleDismiss = () => {
    setShowPrompt(false);
    setDismissed(true);
    localStorage.setItem('pwa-install-dismissed', 'true');
  };

  // Не показываем промпт если уже установлено или не поддерживается
  if (!isInstallable || isInstalled || !showPrompt) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 md:left-auto md:w-96">
      <Card className="p-4 bg-white border-2 border-blue-500 shadow-lg">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-blue-600" />
            </div>
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">
              Установить приложение
            </h3>
            <p className="text-xs text-gray-600 mb-3">
              Установите Clinic на свое устройство для быстрого доступа и работы офлайн
            </p>
            
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={handleInstall}
                className="flex items-center gap-1"
              >
                <Download className="w-3 h-3" />
                Установить
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDismiss}
                className="flex items-center gap-1"
              >
                <X className="w-3 h-3" />
                Не сейчас
              </Button>
            </div>
          </div>
        </div>
        
        {/* Индикатор онлайн/офлайн */}
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="flex items-center gap-2 text-xs">
            <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-gray-600">
              {isOnline ? 'Онлайн' : 'Офлайн режим'}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default PWAInstallPrompt;

