import { toast } from 'react-toastify';

const DEFAULT_OPTIONS = {
  autoClose: 4000,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: true
};

const buildOptions = (options = {}) => ({
  ...DEFAULT_OPTIONS,
  ...options
});

export const notify = {
  success(message, options = {}) {
    return toast.success(message, buildOptions(options));
  },

  error(message, options = {}) {
    return toast.error(message, buildOptions(options));
  },

  info(message, options = {}) {
    return toast.info(message, buildOptions(options));
  },

  warning(message, options = {}) {
    return toast.warning(message, buildOptions(options));
  },

  fromError(error, fallbackMessage = 'Произошла ошибка', options = {}) {
    const message = error?.response?.data?.detail || error?.message || fallbackMessage;
    return toast.error(message, buildOptions(options));
  }
};

export default notify;
