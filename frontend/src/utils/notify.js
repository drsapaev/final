import { toast } from 'react-toastify';

const defaultOptions = {
  position: 'bottom-right'
};

const withDefaults = (options = {}) => ({ ...defaultOptions, ...options });

const notify = {
  success: (message, options) => toast.success(message, withDefaults(options)),
  error: (message, options) => toast.error(message, withDefaults(options)),
  info: (message, options) => toast.info(message, withDefaults(options)),
  warning: (message, options) => toast.warning(message, withDefaults(options))
};

export default notify;
