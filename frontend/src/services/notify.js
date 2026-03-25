import { toast } from '../components/common/Toast';

const mapType = (type = 'info') => {
  if (type === 'warn') return 'warning';
  return type;
};

const showToast = (type, message, options = {}) => {
  const normalizedType = mapType(type);
  const fn = toast[normalizedType] || toast.info;
  return fn(message, options);
};

const browserNotification = ({ title, message, options = {} }) => {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return false;
  }
  if (Notification.permission !== 'granted') {
    return false;
  }

  try {
    new Notification(title || 'Уведомление', {
      body: message || '',
      ...options
    });
    return true;
  } catch {
    return false;
  }
};

const notify = {
  success(message, options = {}) {
    return showToast('success', message, options);
  },
  error(message, options = {}) {
    return showToast('error', message, options);
  },
  warning(message, options = {}) {
    return showToast('warning', message, options);
  },
  info(message, options = {}) {
    return showToast('info', message, options);
  },
  system({ title, message, type = 'info', duration = 5000, browser = false, browserOptions = {} }) {
    const toastId = showToast(type, message, { title, duration });
    if (browser) {
      browserNotification({ title, message, options: browserOptions });
    }
    return toastId;
  },
  browserNotification
};

export default notify;
