// Экспорт всех компонентов кнопок
export { default as ModernButton } from './ModernButton';
export { default as ButtonGroup } from './ButtonGroup';
export { default as IconButton } from './IconButton';
export { default as FloatingActionButton } from './FloatingActionButton';

// Медицинские компоненты кнопок
export {
  default as MedicalButton,
  EmergencyButton,
  DiagnoseButton,
  TreatButton,
  ApproveButton,
  RejectButton,
  CardiologyButton,
  LabButton
} from './MedicalButton';

// Утилиты для кнопок
export const buttonUtils = {
  // Получение размера иконки для кнопки
  getIconSize: (buttonSize) => {
    const sizes = {
      small: 14,
      medium: 16,
      large: 20
    };
    return sizes[buttonSize] || sizes.medium;
  },

  // Создание конфигурации кнопки
  createButtonConfig: (type, options = {}) => {
    const configs = {
      primary: {
        variant: 'primary',
        size: 'medium',
        ...options
      },
      secondary: {
        variant: 'secondary',
        size: 'medium',
        ...options
      },
      success: {
        variant: 'success',
        size: 'medium',
        ...options
      },
      warning: {
        variant: 'warning',
        size: 'medium',
        ...options
      },
      danger: {
        variant: 'danger',
        size: 'medium',
        ...options
      },
      ghost: {
        variant: 'primary',
        ghost: true,
        size: 'medium',
        ...options
      },
      outlined: {
        variant: 'primary',
        outlined: true,
        size: 'medium',
        ...options
      }
    };
    
    return configs[type] || configs.primary;
  },

  // Создание группы кнопок
  createButtonGroup: (buttons, groupOptions = {}) => {
    return {
      buttons,
      size: 'medium',
      variant: 'primary',
      orientation: 'horizontal',
      spacing: 'none',
      ...groupOptions
    };
  },

  // Валидация пропсов кнопки
  validateButtonProps: (props) => {
    const warnings = [];
    
    if (props.disabled && props.loading) {
      warnings.push('Button should not be both disabled and loading');
    }
    
    if (props.children && typeof props.children !== 'string' && !React.isValidElement(props.children)) {
      warnings.push('Button children should be string or React element');
    }
    
    if (props.size && !['small', 'medium', 'large'].includes(props.size)) {
      warnings.push('Invalid button size. Use: small, medium, large');
    }
    
    // Расширенная валидация вариантов с медицинскими
    const validVariants = [
      'primary', 'secondary', 'success', 'warning', 'danger', 'info', 'light', 'dark',
      'cardiology', 'dermatology', 'dentistry', 'laboratory',
      'emergency', 'diagnose', 'treat', 'approve', 'reject'
    ];

    if (props.variant && !validVariants.includes(props.variant)) {
      warnings.push('Invalid button variant');
    }
    
    return warnings;
  }
};

// Хуки для кнопок
export const useButtonState = (initialState = {}) => {
  const [state, setState] = React.useState({
    loading: false,
    disabled: false,
    pressed: false,
    ...initialState
  });

  const setLoading = (loading) => setState(prev => ({ ...prev, loading }));
  const setDisabled = (disabled) => setState(prev => ({ ...prev, disabled }));
  const setPressed = (pressed) => setState(prev => ({ ...prev, pressed }));
  
  const reset = () => setState({
    loading: false,
    disabled: false,
    pressed: false,
    ...initialState
  });

  return {
    ...state,
    setLoading,
    setDisabled,
    setPressed,
    reset
  };
};

// Хук для асинхронных действий кнопки
export const useAsyncButton = (asyncAction) => {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const execute = async (...args) => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await asyncAction(...args);
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return {
    execute,
    loading,
    error,
    reset: () => {
      setLoading(false);
      setError(null);
    }
  };
};

// Константы для кнопок
export const BUTTON_VARIANTS = {
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  SUCCESS: 'success',
  WARNING: 'warning',
  DANGER: 'danger',
  INFO: 'info',
  LIGHT: 'light',
  DARK: 'dark',

  // Медицинские отделы
  CARDIOLOGY: 'cardiology',
  DERMATOLOGY: 'dermatology',
  DENTISTRY: 'dentistry',
  LABORATORY: 'laboratory',

  // Медицинские действия
  EMERGENCY: 'emergency',
  DIAGNOSE: 'diagnose',
  TREAT: 'treat',
  APPROVE: 'approve',
  REJECT: 'reject'
};

export const BUTTON_SIZES = {
  SMALL: 'small',
  MEDIUM: 'medium',
  LARGE: 'large'
};

export const BUTTON_POSITIONS = {
  TOP_LEFT: 'top-left',
  TOP_RIGHT: 'top-right',
  BOTTOM_LEFT: 'bottom-left',
  BOTTOM_RIGHT: 'bottom-right'
};

// Медицинские приоритеты для кнопок
export const MEDICAL_PRIORITIES = {
  LOW: 'low',
  NORMAL: 'normal',
  HIGH: 'high',
  URGENT: 'urgent',
  CRITICAL: 'critical'
};

// Статусы медицинских кнопок
export const MEDICAL_STATUSES = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  LOADING: 'loading',
  SUCCESS: 'success',
  ERROR: 'error'
};

// Медицинские действия
export const MEDICAL_ACTIONS = {
  DIAGNOSE: 'diagnose',
  TREAT: 'treat',
  PRESCRIBE: 'prescribe',
  EMERGENCY: 'emergency',
  APPROVE: 'approve',
  REJECT: 'reject',
  MONITOR: 'monitor',
  EXAMINE: 'examine',
  TEST: 'test',
  SCHEDULE: 'schedule'
};

// Медицинские отделы
export const MEDICAL_DEPARTMENTS = {
  CARDIOLOGY: 'cardiology',
  DERMATOLOGY: 'dermatology',
  DENTISTRY: 'dentistry',
  LABORATORY: 'laboratory',
  NEUROLOGY: 'neurology',
  GYNECOLOGY: 'gynecology',
  PEDIATRICS: 'pediatrics',
  SURGERY: 'surgery',
  PSYCHIATRY: 'psychiatry',
  RADIOLOGY: 'radiology'
};

