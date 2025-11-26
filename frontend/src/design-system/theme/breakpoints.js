/**
 * Брейкпоинты дизайн-системы
 * Согласно MASTER_TODO_LIST строки 220-224
 */

// Базовые брейкпоинты (в пикселях)
export const breakpointValues = {
  xs: 0,     // Мобильные устройства
  sm: 600,   // Планшеты портрет
  md: 900,   // Планшеты ландшафт / маленькие ноутбуки
  lg: 1200,  // Десктопы
  xl: 1536,  // Большие экраны
  
  // Дополнительные брейкпоинты для медицинских интерфейсов
  mobile: 480,   // Маленькие мобильные
  tablet: 768,   // Стандартные планшеты
  desktop: 1024, // Стандартные десктопы
  wide: 1440,    // Широкие экраны
  ultrawide: 1920, // Ультраширокие экраны
};

// Media queries
export const mediaQueries = {
  up: (breakpoint) => `@media (min-width: ${breakpointValues[breakpoint]}px)`,
  down: (breakpoint) => `@media (max-width: ${breakpointValues[breakpoint] - 1}px)`,
  between: (start, end) => `@media (min-width: ${breakpointValues[start]}px) and (max-width: ${breakpointValues[end] - 1}px)`,
  only: (breakpoint) => {
    const keys = Object.keys(breakpointValues);
    const index = keys.indexOf(breakpoint);
    
    if (index === -1) return '';
    if (index === keys.length - 1) return mediaQueries.up(breakpoint);
    
    const nextBreakpoint = keys[index + 1];
    return mediaQueries.between(breakpoint, nextBreakpoint);
  },
};

// Контейнеры для разных размеров экрана
export const containerSizes = {
  xs: '100%',
  sm: '540px',
  md: '720px',
  lg: '960px',
  xl: '1140px',
  
  // Специальные контейнеры
  mobile: '100%',
  tablet: '750px',
  desktop: '1200px',
  wide: '1400px',
  
  // Медицинские интерфейсы (обычно требуют больше места)
  medical: {
    mobile: '100%',
    tablet: '100%',
    desktop: '1300px',
    wide: '1500px',
  }
};

// Адаптивные настройки для компонентов
export const componentBreakpoints = {
  // Таблицы - когда переключаться на мобильный вид
  table: {
    stackAt: 'md', // Стэкинг колонок на экранах меньше md
  },
  
  // Навигация - когда показывать мобильное меню
  navigation: {
    collapseAt: 'lg', // Сворачивание меню на экранах меньше lg
  },
  
  // Формы - количество колонок
  form: {
    singleColumn: 'sm', // Одна колонка на экранах меньше sm
    twoColumns: 'md',   // Две колонки начиная с md
    threeColumns: 'lg', // Три колонки начиная с lg
  },
  
  // Карточки - сетка
  cards: {
    perRow: {
      xs: 1,
      sm: 2,
      md: 3,
      lg: 4,
      xl: 5,
    }
  },
  
  // Медицинские панели
  medicalPanels: {
    sidebarCollapse: 'lg',
    fullWidth: 'xl',
  }
};

// Утилиты для работы с брейкпоинтами
export const breakpointUtils = {
  /**
   * Проверка текущего брейкпоинта
   */
  getCurrentBreakpoint() {
    const width = window.innerWidth;
    
    for (const [key, value] of Object.entries(breakpointValues).reverse()) {
      if (width >= value) {
        return key;
      }
    }
    
    return 'xs';
  },
  
  /**
   * Проверка, больше ли текущий экран указанного брейкпоинта
   */
  isUp(breakpoint) {
    return window.innerWidth >= breakpointValues[breakpoint];
  },
  
  /**
   * Проверка, меньше ли текущий экран указанного брейкпоинта
   */
  isDown(breakpoint) {
    return window.innerWidth < breakpointValues[breakpoint];
  },
  
  /**
   * Проверка, находится ли экран между брейкпоинтами
   */
  isBetween(start, end) {
    const width = window.innerWidth;
    return width >= breakpointValues[start] && width < breakpointValues[end];
  },
  
  /**
   * Получение размера контейнера для текущего брейкпоинта
   */
  getContainerSize(type = 'default') {
    const currentBreakpoint = this.getCurrentBreakpoint();
    
    if (type === 'medical') {
      return containerSizes.medical[currentBreakpoint] || containerSizes.medical.desktop;
    }
    
    return containerSizes[currentBreakpoint] || containerSizes.lg;
  }
};

// CSS переменные для использования в стилях
export const cssVariables = {
  // Брейкпоинты
  '--breakpoint-xs': `${breakpointValues.xs}px`,
  '--breakpoint-sm': `${breakpointValues.sm}px`,
  '--breakpoint-md': `${breakpointValues.md}px`,
  '--breakpoint-lg': `${breakpointValues.lg}px`,
  '--breakpoint-xl': `${breakpointValues.xl}px`,
  
  // Контейнеры
  '--container-xs': containerSizes.xs,
  '--container-sm': containerSizes.sm,
  '--container-md': containerSizes.md,
  '--container-lg': containerSizes.lg,
  '--container-xl': containerSizes.xl,
};

// Экспорт
export default {
  values: breakpointValues,
  mediaQueries,
  containerSizes,
  componentBreakpoints,
  utils: breakpointUtils,
  cssVariables,
};
