import { toast } from 'react-toastify';
import { getErrorMessage } from '../utils/type-guards';

type ToastOptions = Record<string, unknown>;

const DEFAULT_OPTIONS: ToastOptions = {
  autoClose: 4000,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: true
};

const buildOptions = (options: ToastOptions = {}): ToastOptions => ({
  ...DEFAULT_OPTIONS,
  ...options
});

export const notify = {
  success(message: string, options: ToastOptions = {}): ReturnType<typeof toast.success> {
    return toast.success(message, buildOptions(options) as never);
  },

  error(message: string, options: ToastOptions = {}): ReturnType<typeof toast.error> {
    return toast.error(message, buildOptions(options) as never);
  },

  info(message: string, options: ToastOptions = {}): ReturnType<typeof toast.info> {
    return toast.info(message, buildOptions(options) as never);
  },

  warning(message: string, options: ToastOptions = {}): ReturnType<typeof toast.warning> {
    return toast.warning(message, buildOptions(options) as never);
  },

  fromError(
    error: { response?: { data?: { detail?: string } }; message?: string } | unknown,
    fallbackMessage: string = 'Произошла ошибка',
    options: ToastOptions = {}
  ): ReturnType<typeof toast.error> {
    const message = getErrorMessage(error) || fallbackMessage;
    return toast.error(message, buildOptions(options) as never);
  }
};

export default notify;
