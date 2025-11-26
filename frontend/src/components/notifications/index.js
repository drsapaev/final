// Экспорт всех компонентов уведомлений
export { default as ModernToast } from './ModernToast';
export { default as ModernAlert } from './ModernAlert';
export { default as ModernProgressBar, CircularProgressBar } from './ModernProgressBar';

// Менеджер Toast уведомлений
export class ToastManager {
  constructor() {
    this.toasts = [];
    this.listeners = [];
    this.nextId = 1;
  }

  // Добавление toast
  add(toast) {
    const id = this.nextId++;
    const newToast = {
      id,
      timestamp: Date.now(),
      ...toast
    };
    
    this.toasts.push(newToast);
    this.notify();
    
    return id;
  }

  // Удаление toast
  remove(id) {
    this.toasts = this.toasts.filter(toast => toast.id !== id);
    this.notify();
  }

  // Очистка всех toast
  clear() {
    this.toasts = [];
    this.notify();
  }

  // Подписка на изменения
  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  // Уведомление слушателей
  notify() {
    this.listeners.forEach(listener => listener(this.toasts));
  }

  // Методы для различных типов toast
  success(message, options = {}) {
    return this.add({
      type: 'success',
      message,
      ...options
    });
  }

  error(message, options = {}) {
    return this.add({
      type: 'error',
      message,
      duration: 0, // Ошибки не исчезают автоматически
      ...options
    });
  }

  warning(message, options = {}) {
    return this.add({
      type: 'warning',
      message,
      ...options
    });
  }

  info(message, options = {}) {
    return this.add({
      type: 'info',
      message,
      ...options
    });
  }

  // Промис toast (для асинхронных операций)
  promise(promise, messages = {}) {
    const {
      loading = 'Загрузка...',
      success = 'Успешно!',
      error = 'Произошла ошибка'
    } = messages;

    const loadingToastId = this.add({
      type: 'info',
      message: loading,
      persistent: true
    });

    return promise
      .then((result) => {
        this.remove(loadingToastId);
        this.success(typeof success === 'function' ? success(result) : success);
        return result;
      })
      .catch((err) => {
        this.remove(loadingToastId);
        this.error(typeof error === 'function' ? error(err) : error);
        throw err;
      });
  }
}

// Глобальный экземпляр менеджера
export const toastManager = new ToastManager();

// Утилиты для уведомлений
export const notificationUtils = {
  // Создание конфигурации toast
  createToastConfig: (type, message, options = {}) => ({
    type,
    message,
    duration: type === 'error' ? 0 : 5000,
    position: 'bottom-right',
    showProgress: true,
    ...options
  }),

  // Создание конфигурации alert
  createAlertConfig: (type, title, content, options = {}) => ({
    type,
    title,
    children: content,
    dismissible: true,
    variant: 'filled',
    size: 'medium',
    ...options
  }),

  // Валидация типа уведомления
  validateNotificationType: (type) => {
    const validTypes = ['success', 'error', 'warning', 'info'];
    return validTypes.includes(type);
  },

  // Получение иконки для типа
  getTypeIcon: (type) => {
    const icons = {
      success: 'CheckCircle',
      error: 'AlertCircle',
      warning: 'AlertTriangle',
      info: 'Info'
    };
    return icons[type] || icons.info;
  },

  // Форматирование времени для уведомлений
  formatTimestamp: (timestamp) => {
    const now = Date.now();
    const diff = now - timestamp;
    
    if (diff < 60000) return 'только что';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} мин назад`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} ч назад`;
    
    return new Date(timestamp).toLocaleDateString();
  }
};

// Хуки для уведомлений
export const useToast = () => {
  const [toasts, setToasts] = React.useState([]);

  React.useEffect(() => {
    const unsubscribe = toastManager.subscribe(setToasts);
    setToasts(toastManager.toasts);
    return unsubscribe;
  }, []);

  return {
    toasts,
    toast: {
      success: (message, options) => toastManager.success(message, options),
      error: (message, options) => toastManager.error(message, options),
      warning: (message, options) => toastManager.warning(message, options),
      info: (message, options) => toastManager.info(message, options),
      promise: (promise, messages) => toastManager.promise(promise, messages),
      dismiss: (id) => toastManager.remove(id),
      clear: () => toastManager.clear()
    }
  };
};

// Хук для прогресс-бара
export const useProgress = (initialValue = 0, max = 100) => {
  const [value, setValue] = React.useState(initialValue);
  const [isComplete, setIsComplete] = React.useState(false);

  const setProgress = React.useCallback((newValue) => {
    const clampedValue = Math.min(Math.max(newValue, 0), max);
    setValue(clampedValue);
    setIsComplete(clampedValue >= max);
  }, [max]);

  const increment = React.useCallback((amount = 1) => {
    setValue(prev => {
      const newValue = Math.min(prev + amount, max);
      setIsComplete(newValue >= max);
      return newValue;
    });
  }, [max]);

  const decrement = React.useCallback((amount = 1) => {
    setValue(prev => {
      const newValue = Math.max(prev - amount, 0);
      setIsComplete(newValue >= max);
      return newValue;
    });
  }, [max]);

  const reset = React.useCallback(() => {
    setValue(initialValue);
    setIsComplete(initialValue >= max);
  }, [initialValue, max]);

  const complete = React.useCallback(() => {
    setValue(max);
    setIsComplete(true);
  }, [max]);

  return {
    value,
    percentage: (value / max) * 100,
    isComplete,
    setProgress,
    increment,
    decrement,
    reset,
    complete
  };
};

// Константы
export const NOTIFICATION_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info'
};

export const TOAST_POSITIONS = {
  TOP_LEFT: 'top-left',
  TOP_RIGHT: 'top-right',
  TOP_CENTER: 'top-center',
  BOTTOM_LEFT: 'bottom-left',
  BOTTOM_RIGHT: 'bottom-right',
  BOTTOM_CENTER: 'bottom-center'
};

export const ALERT_VARIANTS = {
  FILLED: 'filled',
  OUTLINED: 'outlined',
  MINIMAL: 'minimal'
};

export const PROGRESS_VARIANTS = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  SUCCESS: 'success',
  WARNING: 'warning',
  DANGER: 'danger',
  INFO: 'info'
};

