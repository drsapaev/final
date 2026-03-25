import { toast } from '../components/common/Toast';

const normalizeMessage = (message) => {
  if (typeof message === 'string') return message;
  if (message === null || message === undefined) return '';
  return String(message);
};

const notify = {
  success(message, options = {}) {
    return toast.success(normalizeMessage(message), options);
  },

  error(message, options = {}) {
    return toast.error(normalizeMessage(message), options);
  },

  info(message, options = {}) {
    return toast.info(normalizeMessage(message), options);
  },

  warning(message, options = {}) {
    return toast.warning(normalizeMessage(message), options);
  }
};

export const { success, error, info, warning } = notify;
export default notify;
