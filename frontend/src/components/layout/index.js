// Экспорт всех компонентов layout
export { default as ModernContainer } from './ModernContainer';
export { default as ModernGrid, GridItem } from './ModernGrid';
export { default as ModernFlex, FlexItem } from './ModernFlex';
export { 
  default as ModernCard, 
  CardHeader, 
  CardBody, 
  CardFooter, 
  CardTitle, 
  CardDescription 
} from './ModernCard';

// Утилиты для layout
export const layoutUtils = {
  // Брейкпоинты
  breakpoints: {
    xs: '480px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px'
  },

  // Отступы
  spacing: {
    none: '0',
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '48px',
    '3xl': '64px'
  },

  // Радиусы скругления
  borderRadius: {
    none: '0',
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    '2xl': '24px',
    full: '9999px'
  },

  // Тени
  shadows: {
    none: 'none',
    sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
    md: '0 4px 6px rgba(0, 0, 0, 0.1)',
    lg: '0 10px 15px rgba(0, 0, 0, 0.1)',
    xl: '0 20px 25px rgba(0, 0, 0, 0.1)',
    '2xl': '0 25px 50px rgba(0, 0, 0, 0.25)'
  },

  // Создание адаптивных значений
  createResponsiveValue: (values) => {
    const { xs, sm, md, lg, xl } = values;
    return {
      default: xs || sm || md || lg || xl,
      xs,
      sm,
      md,
      lg,
      xl
    };
  },

  // Получение значения для текущего размера экрана
  getResponsiveValue: (responsiveValue, currentBreakpoint) => {
    if (typeof responsiveValue !== 'object') {
      return responsiveValue;
    }
    
    const breakpointOrder = ['xs', 'sm', 'md', 'lg', 'xl'];
    const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
    
    // Ищем ближайшее доступное значение
    for (let i = currentIndex; i >= 0; i--) {
      const bp = breakpointOrder[i];
      if (responsiveValue[bp] !== undefined) {
        return responsiveValue[bp];
      }
    }
    
    return responsiveValue.default || responsiveValue[breakpointOrder[0]];
  },

  // Создание CSS Grid шаблона
  createGridTemplate: (columns, rows) => {
    const formatValue = (value) => {
      if (typeof value === 'number') {
        return `repeat(${value}, 1fr)`;
      }
      if (Array.isArray(value)) {
        return value.join(' ');
      }
      return value;
    };

    return {
      gridTemplateColumns: formatValue(columns),
      gridTemplateRows: rows ? formatValue(rows) : undefined
    };
  },

  // Создание Flexbox стилей
  createFlexStyles: (options = {}) => {
    const {
      direction = 'row',
      wrap = 'nowrap',
      justify = 'flex-start',
      align = 'stretch',
      gap = '16px'
    } = options;

    return {
      display: 'flex',
      flexDirection: direction,
      flexWrap: wrap,
      justifyContent: justify,
      alignItems: align,
      gap
    };
  },

  // Проверка размера экрана
  isBreakpoint: (breakpoint, width) => {
    const breakpointValues = {
      xs: 480,
      sm: 640,
      md: 768,
      lg: 1024,
      xl: 1280,
      '2xl': 1536
    };
    
    return width >= breakpointValues[breakpoint];
  }
};

// Хуки для layout
export const useResponsive = () => {
  const [windowSize, setWindowSize] = React.useState({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768
  });

  React.useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleResize = () => {
      setWindowSize({
        width: window.innerWidth,
        height: window.innerHeight
      });
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const getCurrentBreakpoint = () => {
    const { width } = windowSize;
    if (width >= 1536) return '2xl';
    if (width >= 1280) return 'xl';
    if (width >= 1024) return 'lg';
    if (width >= 768) return 'md';
    if (width >= 640) return 'sm';
    return 'xs';
  };

  const isBreakpoint = (breakpoint) => {
    return layoutUtils.isBreakpoint(breakpoint, windowSize.width);
  };

  return {
    windowSize,
    currentBreakpoint: getCurrentBreakpoint(),
    isBreakpoint,
    isMobile: windowSize.width < 768,
    isTablet: windowSize.width >= 768 && windowSize.width < 1024,
    isDesktop: windowSize.width >= 1024
  };
};

// Хук для создания адаптивных стилей
export const useResponsiveStyles = (styles) => {
  const { currentBreakpoint } = useResponsive();
  
  return React.useMemo(() => {
    const result = {};
    
    Object.keys(styles).forEach(property => {
      const value = styles[property];
      result[property] = layoutUtils.getResponsiveValue(value, currentBreakpoint);
    });
    
    return result;
  }, [styles, currentBreakpoint]);
};

// Константы
export const BREAKPOINTS = layoutUtils.breakpoints;
export const SPACING = layoutUtils.spacing;
export const BORDER_RADIUS = layoutUtils.borderRadius;
export const SHADOWS = layoutUtils.shadows;