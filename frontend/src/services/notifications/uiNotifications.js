import { toast } from 'react-toastify';

const defaultOptions = {
  position: 'bottom-right'
};

const asString = (value) => {
  if (typeof value === 'string') return value;
  if (value === null || value === undefined) return '';
  return String(value);
};

export const notify = {
  success(message, options = {}) {
    return toast.success(asString(message), { ...defaultOptions, ...options });
  },

  error(message, options = {}) {
    return toast.error(asString(message), { ...defaultOptions, ...options });
  },

  info(message, options = {}) {
    return toast.info(asString(message), { ...defaultOptions, ...options });
  },

  warning(message, options = {}) {
    return toast.warning(asString(message), { ...defaultOptions, ...options });
  }
};

export default notify;
