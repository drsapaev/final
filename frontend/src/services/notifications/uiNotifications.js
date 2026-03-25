import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

const DEFAULT_TYPE = 'info';
const VALID_TYPES = new Set(['success', 'error', 'info', 'warning']);

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

export function normalizeNotificationPayload(input, fallback = {}) {
  const payload = isObject(input) ? input : { message: input };
  const message = payload.message || payload.title || fallback.message || '';

  return {
    title: payload.title || fallback.title || '',
    message,
    type: VALID_TYPES.has(payload.type) ? payload.type : (fallback.type || DEFAULT_TYPE),
    source: payload.source || fallback.source || 'ui',
    entity_type: payload.entity_type || fallback.entity_type || null,
    entity_id: payload.entity_id || fallback.entity_id || null,
    action_url: payload.action_url || fallback.action_url || null,
    action: payload.action || fallback.action || null,
  };
}

function buildToastMessage(payload) {
  return payload.title && payload.title !== payload.message
    ? `${payload.title}: ${payload.message}`
    : payload.message;
}

function mapOptions(payload, options = {}) {
  const onClick = payload.action?.onClick
    ? () => payload.action.onClick(payload)
    : options.onClick;

  return {
    autoClose: options.duration ?? options.autoClose ?? 5000,
    ...(payload.action_url ? { onClick: () => window.location.assign(payload.action_url) } : {}),
    ...(onClick ? { onClick } : {}),
    ...options,
  };
}

function push(payload, options = {}) {
  const normalized = normalizeNotificationPayload(payload);
  const method = toast[normalized.type] || toast.info;
  return method(buildToastMessage(normalized), mapOptions(normalized, options));
}

export const notify = {
  success(message, options = {}) {
    return push({ message, type: 'success' }, options);
  },
  error(message, options = {}) {
    return push({ message, type: 'error' }, options);
  },
  info(message, options = {}) {
    return push({ message, type: 'info' }, options);
  },
  warning(message, options = {}) {
    return push({ message, type: 'warning' }, options);
  },
  system(payload) {
    return push(payload, { autoClose: 7000 });
  },
  fromPayload(payload, options = {}) {
    return push(payload, options);
  },
};

export function NotificationsViewport() {
  return <ToastContainer position="bottom-right" newestOnTop closeOnClick pauseOnHover draggable />;
}

export default notify;
