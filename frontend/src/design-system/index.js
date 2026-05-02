/**
 * Улучшенная система экспорта для медицинских интерфейсов
 * Основана на принципах производительности и медицинских стандартах
 */

// Локальные импорты для использования внутри DESIGN_SYSTEM и реэкспорты ниже
import designTokens, { getColor, getSpacing, getFontSize, getFontWeight, getBorderRadius, getShadow, getBreakpoint } from './tokens/design-tokens';
import cn, { conditionalClasses, stateClasses, responsiveClasses } from '../utils/cn';

// Экспорт дизайн-токенов
export { default as designTokens } from './tokens/design-tokens';
export { getColor, getSpacing, getFontSize, getFontWeight, getBorderRadius, getShadow, getBreakpoint } from './tokens/design-tokens';

// Экспорт компонентов
export { default as EnhancedComponents } from './components/EnhancedComponents';
export { 
  Button, 
  Card, 
  Input, 
  Badge, 
  FormField, 
  Tab, 
  Tabs, 
  Table, 
  TableHeader, 
  TableBody, 
  TableRow, 
  TableCell, 
  Page, 
  Grid 
} from './components/EnhancedComponents';

// Экспорт темизации
export { default as EnhancedThemeProvider } from './theme/EnhancedThemeProvider';
export { useTheme } from './theme/EnhancedThemeProvider';

// Экспорт хуков
export { default as useMediaQuery } from '../hooks/useMediaQuery';
export { 
  useBreakpoint, 
  useDevice, 
  useOrientation, 
  useTouchDevice, 
  useHoverSupport, 
  useReducedMotion, 
  useHighContrast 
} from '../hooks/useEnhancedMediaQuery';

export { default as useAI } from '../hooks/useAI.jsx';
export {
  useAIAssistant,
  useAISuggestions,
  useAITranslation,
  useAIImageAnalysis,
  AIAssistant
} from '../hooks/useAI.jsx';

export { default as useAnimation } from '../hooks/useAnimation.jsx';
export {
  animations,
  useListAnimation,
  useProgressAnimation,
  AnimatedTransition,
  AnimatedList,
  AnimatedProgress,
  AnimatedCounter,
  createAnimation
} from '../hooks/useAnimation.jsx';

export { default as useNotifications } from '../hooks/useNotifications.jsx';
export {
  notificationTypes,
  notificationConfig,
  Notification,
  NotificationContainer
} from '../hooks/useNotifications.jsx';

export { default as useForm } from '../hooks/useForm.jsx';
export {
  validators,
} from '../hooks/useForm.jsx';

export { default as useTable } from '../hooks/useTable.jsx';
export {
} from '../hooks/useTable.jsx';

export { default as useModal } from '../hooks/useModal.jsx';
export {
  useModals,
  Modal,
  ModalWithActions,
  ConfirmModal,
  FormModal,
  InfoModal
} from '../hooks/useModal.jsx';

export { default as useNavigation } from '../hooks/useNavigation.jsx';
export {
  useTabs
} from '../hooks/useNavigation.jsx';

export { default as useUtils } from '../hooks/useUtils';
export { 
  useDebounce, 
  useThrottle, 
  usePrevious, 
  useIsFirstRender, 
  useIsMounted, 
  useLocalStorage, 
  useSessionStorage, 
  useClipboard, 
  useGeolocation, 
  useOnlineStatus, 
  usePageVisibility, 
  useWindowSize, 
  useScroll, 
  useFocus, 
  useHover, 
  useClickOutside, 
  useKeyPress, 
  useKeyCombo, 
  useInterval, 
  useTimeout, 
  useAsync, 
  useMemoizedCallback, 
  useMemoizedValue, 
  useDateUtils, 
  useNumberUtils 
} from '../hooks/useUtils';

// Экспорт утилит
export { default as cn } from '../utils/cn';
export { conditionalClasses, stateClasses, responsiveClasses } from '../utils/cn';

// Экспорт констант
export const MEDICAL_COLORS = {
  CARDIOLOGY: '#dc2626',
  DERMATOLOGY: '#059669',
  DENTISTRY: '#7c3aed',
  LABORATORY: '#0891b2',
  EMERGENCY: '#dc2626',
  SUCCESS: '#10b981',
  WARNING: '#f59e0b',
  DANGER: '#ef4444',
  INFO: '#06b6d4'
};

export const MEDICAL_STATUSES = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  NO_SHOW: 'no_show'
};

export const MEDICAL_PRIORITIES = {
  LOW: 'low',
  NORMAL: 'normal',
  HIGH: 'high',
  URGENT: 'urgent',
  EMERGENCY: 'emergency'
};

export const MEDICAL_DEPARTMENTS = {
  CARDIOLOGY: 'cardiology',
  DERMATOLOGY: 'dermatology',
  DENTISTRY: 'dentistry',
  LABORATORY: 'laboratory',
  GENERAL: 'general'
};

// Экспорт типов
export const COMPONENT_SIZES = {
  XS: 'xs',
  SM: 'sm',
  MD: 'md',
  LG: 'lg',
  XL: 'xl'
};

export const COMPONENT_VARIANTS = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  SUCCESS: 'success',
  WARNING: 'warning',
  DANGER: 'danger',
  INFO: 'info',
  OUTLINE: 'outline',
  GHOST: 'ghost'
};

export const ANIMATION_TYPES = {
  FADE: 'fade',
  SLIDE_UP: 'slideUp',
  SLIDE_DOWN: 'slideDown',
  SLIDE_LEFT: 'slideLeft',
  SLIDE_RIGHT: 'slideRight',
  PULSE: 'pulse',
  HEARTBEAT: 'heartbeat',
  NOTIFICATION: 'notification',
  MODAL: 'modal',
  TABLE_ROW: 'tableRow'
};

export const NOTIFICATION_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
  MEDICAL: 'medical',
  EMERGENCY: 'emergency'
};

// Экспорт конфигурации
export const DEFAULT_CONFIG = {
  theme: 'light',
  language: 'ru',
  timezone: 'Asia/Tashkent',
  currency: 'UZS',
  dateFormat: 'DD.MM.YYYY',
  timeFormat: 'HH:mm',
  pageSize: 10,
  maxNotifications: 5,
  animationDuration: 300,
  debounceDelay: 500,
  throttleDelay: 100
};

// Экспорт медиа-запросов
export const MEDIA_QUERIES = {
  XS: '(max-width: 639px)',
  SM: '(min-width: 640px)',
  MD: '(min-width: 768px)',
  LG: '(min-width: 1024px)',
  XL: '(min-width: 1280px)',
  '2XL': '(min-width: 1536px)',
  MOBILE: '(max-width: 767px)',
  TABLET: '(min-width: 768px) and (max-width: 1023px)',
  DESKTOP: '(min-width: 1024px)',
  TOUCH: '(hover: none) and (pointer: coarse)',
  HOVER: '(hover: hover)',
  REDUCED_MOTION: '(prefers-reduced-motion: reduce)',
  HIGH_CONTRAST: '(prefers-contrast: high)'
};

// Экспорт z-индексов
export const Z_INDEX = {
  HIDE: -1,
  AUTO: 'auto',
  BASE: 0,
  DOCKED: 10,
  DROPDOWN: 1000,
  STICKY: 1100,
  BANNER: 1200,
  OVERLAY: 1300,
  MODAL: 1400,
  POPOVER: 1500,
  SKIP_LINK: 1600,
  TOAST: 1700,
  TOOLTIP: 1800
};

// Экспорт анимаций
export const ANIMATION_DURATIONS = {
  FAST: 150,
  NORMAL: 300,
  SLOW: 500
};

export const ANIMATION_EASINGS = {
  LINEAR: 'linear',
  EASE: 'ease',
  EASE_IN: 'ease-in',
  EASE_OUT: 'ease-out',
  EASE_IN_OUT: 'ease-in-out'
};

// Экспорт размеров
export const SPACING = {
  XS: '4px',
  SM: '8px',
  MD: '16px',
  LG: '24px',
  XL: '32px',
  '2XL': '48px',
  '3XL': '64px',
  '4XL': '96px'
};

export const FONT_SIZES = {
  XS: '12px',
  SM: '14px',
  BASE: '16px',
  LG: '18px',
  XL: '20px',
  '2XL': '24px',
  '3XL': '30px',
  '4XL': '36px',
  '5XL': '48px'
};

export const FONT_WEIGHTS = {
  LIGHT: 300,
  NORMAL: 400,
  MEDIUM: 500,
  SEMIBOLD: 600,
  BOLD: 700,
  EXTRABOLD: 800
};

export const BORDER_RADIUS = {
  NONE: '0',
  SM: '4px',
  MD: '8px',
  LG: '12px',
  XL: '16px',
  '2XL': '24px',
  FULL: '9999px'
};

export const BOX_SHADOWS = {
  SM: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  MD: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  LG: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  XL: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2XL': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  INNER: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)'
};

// Экспорт цветов
export const COLORS = {
  PRIMARY: {
    50: '#e6f2ff',
    100: '#b3d9ff',
    200: '#80bfff',
    300: '#4da6ff',
    400: '#1a8cff',
    500: '#0066cc',
    600: '#0052a3',
    700: '#003d7a',
    800: '#002952',
    900: '#001429'
  },
  GRAY: {
    50: '#f9fafb',
    100: '#f3f4f6',
    200: '#e5e7eb',
    300: '#d1d5db',
    400: '#9ca3af',
    500: '#6b7280',
    600: '#4b5563',
    700: '#374151',
    800: '#1f2937',
    900: '#111827'
  },
  SUCCESS: {
    50: '#ecfdf5',
    100: '#d1fae5',
    200: '#a7f3d0',
    300: '#6ee7b7',
    400: '#34d399',
    500: '#10b981',
    600: '#059669',
    700: '#047857',
    800: '#065f46',
    900: '#064e3b'
  },
  WARNING: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f'
  },
  DANGER: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    300: '#fca5a5',
    400: '#f87171',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    800: '#991b1b',
    900: '#7f1d1d'
  },
  INFO: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#06b6d4',
    600: '#0891b2',
    700: '#0e7490',
    800: '#155e75',
    900: '#164e63'
  }
};

// Экспорт брейкпоинтов
export const BREAKPOINTS = {
  XS: '360px',
  SM: '640px',
  MD: '768px',
  LG: '1024px',
  XL: '1280px',
  '2XL': '1536px'
};

// Экспорт конфигурации по умолчанию
export const DEFAULT_THEME_CONFIG = {
  colors: COLORS,
  spacing: SPACING,
  fontSizes: FONT_SIZES,
  fontWeights: FONT_WEIGHTS,
  borderRadius: BORDER_RADIUS,
  boxShadows: BOX_SHADOWS,
  breakpoints: BREAKPOINTS,
  zIndex: Z_INDEX,
  animations: {
    durations: ANIMATION_DURATIONS,
    easings: ANIMATION_EASINGS
  }
};

// Экспорт всех компонентов и хуков
export const DESIGN_SYSTEM = {
  // Токены
  tokens: {
    designTokens,
    getColor,
    getSpacing,
    getFontSize,
    getFontWeight,
    getBorderRadius,
    getShadow,
    getBreakpoint
  },
  
  // Компоненты
  components: {},
  
  // Хуки
  hooks: {},
  
  // Утилиты
  utils: {
    cn,
    conditionalClasses,
    stateClasses,
    responsiveClasses
  },
  
  // Константы
  constants: {
    MEDICAL_COLORS,
    MEDICAL_STATUSES,
    MEDICAL_PRIORITIES,
    MEDICAL_DEPARTMENTS,
    COMPONENT_SIZES,
    COMPONENT_VARIANTS,
    ANIMATION_TYPES,
    NOTIFICATION_TYPES,
    DEFAULT_CONFIG,
    MEDIA_QUERIES,
    Z_INDEX,
    ANIMATION_DURATIONS,
    ANIMATION_EASINGS,
    SPACING,
    FONT_SIZES,
    FONT_WEIGHTS,
    BORDER_RADIUS,
    BOX_SHADOWS,
    COLORS,
    BREAKPOINTS,
    DEFAULT_THEME_CONFIG
  }
};

export default DESIGN_SYSTEM;