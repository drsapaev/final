/**
 * Система отступов дизайн-системы
 * Согласно MASTER_TODO_LIST строки 220-224
 */

// Базовая единица измерения (в rem)
export const baseUnit = 0.25; // 4px при font-size: 16px

// Шкала отступов
export const spacing = {
  0: '0',
  px: '1px',
  0.5: `${baseUnit * 0.5}rem`, // 2px
  1: `${baseUnit * 1}rem`,     // 4px
  1.5: `${baseUnit * 1.5}rem`, // 6px
  2: `${baseUnit * 2}rem`,     // 8px
  2.5: `${baseUnit * 2.5}rem`, // 10px
  3: `${baseUnit * 3}rem`,     // 12px
  3.5: `${baseUnit * 3.5}rem`, // 14px
  4: `${baseUnit * 4}rem`,     // 16px
  5: `${baseUnit * 5}rem`,     // 20px
  6: `${baseUnit * 6}rem`,     // 24px
  7: `${baseUnit * 7}rem`,     // 28px
  8: `${baseUnit * 8}rem`,     // 32px
  9: `${baseUnit * 9}rem`,     // 36px
  10: `${baseUnit * 10}rem`,   // 40px
  11: `${baseUnit * 11}rem`,   // 44px
  12: `${baseUnit * 12}rem`,   // 48px
  14: `${baseUnit * 14}rem`,   // 56px
  16: `${baseUnit * 16}rem`,   // 64px
  20: `${baseUnit * 20}rem`,   // 80px
  24: `${baseUnit * 24}rem`,   // 96px
  28: `${baseUnit * 28}rem`,   // 112px
  32: `${baseUnit * 32}rem`,   // 128px
  36: `${baseUnit * 36}rem`,   // 144px
  40: `${baseUnit * 40}rem`,   // 160px
  44: `${baseUnit * 44}rem`,   // 176px
  48: `${baseUnit * 48}rem`,   // 192px
  52: `${baseUnit * 52}rem`,   // 208px
  56: `${baseUnit * 56}rem`,   // 224px
  60: `${baseUnit * 60}rem`,   // 240px
  64: `${baseUnit * 64}rem`,   // 256px
  72: `${baseUnit * 72}rem`,   // 288px
  80: `${baseUnit * 80}rem`,   // 320px
  96: `${baseUnit * 96}rem`,   // 384px
};

// Семантические отступы для UI элементов
export const componentSpacing = {
  // Кнопки
  button: {
    paddingX: spacing[4],
    paddingY: spacing[2],
    gap: spacing[2],
  },
  
  // Карточки
  card: {
    padding: spacing[6],
    margin: spacing[4],
    gap: spacing[4],
  },
  
  // Формы
  form: {
    fieldGap: spacing[4],
    sectionGap: spacing[8],
    labelMargin: spacing[1],
  },
  
  // Таблицы
  table: {
    cellPadding: spacing[3],
    headerPadding: spacing[4],
    rowGap: spacing[1],
  },
  
  // Модальные окна
  modal: {
    padding: spacing[6],
    headerPadding: spacing[6],
    footerPadding: spacing[4],
  },
  
  // Навигация
  navigation: {
    itemPadding: spacing[3],
    sectionGap: spacing[6],
    iconMargin: spacing[2],
  },
  
  // Медицинские панели
  medical: {
    sectionGap: spacing[8],
    fieldGap: spacing[4],
    cardPadding: spacing[6],
  },
};

// Адаптивные отступы
export const responsiveSpacing = {
  // Контейнеры
  container: {
    mobile: spacing[4],
    tablet: spacing[6],
    desktop: spacing[8],
  },
  
  // Секции
  section: {
    mobile: spacing[8],
    tablet: spacing[12],
    desktop: spacing[16],
  },
  
  // Элементы
  element: {
    mobile: spacing[2],
    tablet: spacing[3],
    desktop: spacing[4],
  },
};

// Утилиты для работы с отступами
export const spacingUtils = {
  /**
   * Получение значения отступа
   */
  getSpacing(key) {
    return spacing[key] || spacing[4];
  },
  
  /**
   * Получение отступа компонента
   */
  getComponentSpacing(component, property) {
    return componentSpacing[component]?.[property] || spacing[4];
  },
  
  /**
   * Получение адаптивного отступа
   */
  getResponsiveSpacing(type, breakpoint) {
    return responsiveSpacing[type]?.[breakpoint] || spacing[4];
  },
  
  /**
   * Создание CSS стилей для отступов
   */
  createSpacingStyles(margins = {}, paddings = {}) {
    const styles = {};
    
    // Margins
    if (margins.top) styles.marginTop = this.getSpacing(margins.top);
    if (margins.right) styles.marginRight = this.getSpacing(margins.right);
    if (margins.bottom) styles.marginBottom = this.getSpacing(margins.bottom);
    if (margins.left) styles.marginLeft = this.getSpacing(margins.left);
    if (margins.x) {
      styles.marginLeft = this.getSpacing(margins.x);
      styles.marginRight = this.getSpacing(margins.x);
    }
    if (margins.y) {
      styles.marginTop = this.getSpacing(margins.y);
      styles.marginBottom = this.getSpacing(margins.y);
    }
    if (margins.all) styles.margin = this.getSpacing(margins.all);
    
    // Paddings
    if (paddings.top) styles.paddingTop = this.getSpacing(paddings.top);
    if (paddings.right) styles.paddingRight = this.getSpacing(paddings.right);
    if (paddings.bottom) styles.paddingBottom = this.getSpacing(paddings.bottom);
    if (paddings.left) styles.paddingLeft = this.getSpacing(paddings.left);
    if (paddings.x) {
      styles.paddingLeft = this.getSpacing(paddings.x);
      styles.paddingRight = this.getSpacing(paddings.x);
    }
    if (paddings.y) {
      styles.paddingTop = this.getSpacing(paddings.y);
      styles.paddingBottom = this.getSpacing(paddings.y);
    }
    if (paddings.all) styles.padding = this.getSpacing(paddings.all);
    
    return styles;
  }
};

// Экспорт
export default {
  baseUnit,
  spacing,
  componentSpacing,
  responsiveSpacing,
  utils: spacingUtils,
};
