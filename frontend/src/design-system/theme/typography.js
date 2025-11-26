/**
 * Типографика дизайн-системы
 * Согласно MASTER_TODO_LIST строки 220-224
 */

// Базовые настройки шрифтов
export const fontFamilies = {
  primary: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  secondary: '"Roboto", "Helvetica Neue", Arial, sans-serif',
  monospace: '"SF Mono", "Monaco", "Inconsolata", "Roboto Mono", "Source Code Pro", monospace',
  medical: '"Source Sans Pro", "Helvetica Neue", Arial, sans-serif', // Для медицинских документов
};

// Размеры шрифтов (в rem)
export const fontSizes = {
  xs: '0.75rem',    // 12px
  sm: '0.875rem',   // 14px
  base: '1rem',     // 16px
  lg: '1.125rem',   // 18px
  xl: '1.25rem',    // 20px
  '2xl': '1.5rem',  // 24px
  '3xl': '1.875rem', // 30px
  '4xl': '2.25rem', // 36px
  '5xl': '3rem',    // 48px
  '6xl': '3.75rem', // 60px
  '7xl': '4.5rem',  // 72px
  '8xl': '6rem',    // 96px
  '9xl': '8rem',    // 128px
};

// Веса шрифтов
export const fontWeights = {
  thin: 100,
  extralight: 200,
  light: 300,
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  extrabold: 800,
  black: 900,
};

// Высота строк
export const lineHeights = {
  none: 1,
  tight: 1.25,
  snug: 1.375,
  normal: 1.5,
  relaxed: 1.625,
  loose: 2,
  
  // Специальные для UI элементов
  button: 1.2,
  input: 1.4,
  heading: 1.2,
  body: 1.6,
};

// Межбуквенные интервалы
export const letterSpacings = {
  tighter: '-0.05em',
  tight: '-0.025em',
  normal: '0em',
  wide: '0.025em',
  wider: '0.05em',
  widest: '0.1em',
};

// Предустановленные стили текста
export const textStyles = {
  // Заголовки
  h1: {
    fontSize: fontSizes['4xl'],
    fontWeight: fontWeights.bold,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.tight,
  },
  
  h2: {
    fontSize: fontSizes['3xl'],
    fontWeight: fontWeights.semibold,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.tight,
  },
  
  h3: {
    fontSize: fontSizes['2xl'],
    fontWeight: fontWeights.semibold,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.normal,
  },
  
  h4: {
    fontSize: fontSizes.xl,
    fontWeight: fontWeights.medium,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.normal,
  },
  
  h5: {
    fontSize: fontSizes.lg,
    fontWeight: fontWeights.medium,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.normal,
  },
  
  h6: {
    fontSize: fontSizes.base,
    fontWeight: fontWeights.medium,
    lineHeight: lineHeights.heading,
    letterSpacing: letterSpacings.normal,
  },
  
  // Основной текст
  body1: {
    fontSize: fontSizes.base,
    fontWeight: fontWeights.normal,
    lineHeight: lineHeights.body,
    letterSpacing: letterSpacings.normal,
  },
  
  body2: {
    fontSize: fontSizes.sm,
    fontWeight: fontWeights.normal,
    lineHeight: lineHeights.body,
    letterSpacing: letterSpacings.normal,
  },
  
  // Подписи и мелкий текст
  caption: {
    fontSize: fontSizes.xs,
    fontWeight: fontWeights.normal,
    lineHeight: lineHeights.normal,
    letterSpacing: letterSpacings.wide,
  },
  
  overline: {
    fontSize: fontSizes.xs,
    fontWeight: fontWeights.medium,
    lineHeight: lineHeights.normal,
    letterSpacing: letterSpacings.widest,
    textTransform: 'uppercase',
  },
  
  // Кнопки
  button: {
    fontSize: fontSizes.sm,
    fontWeight: fontWeights.medium,
    lineHeight: lineHeights.button,
    letterSpacing: letterSpacings.wide,
    textTransform: 'uppercase',
  },
  
  // Специальные стили для медицинских документов
  medical: {
    fontSize: fontSizes.sm,
    fontWeight: fontWeights.normal,
    lineHeight: lineHeights.relaxed,
    letterSpacing: letterSpacings.normal,
    fontFamily: fontFamilies.medical,
  },
  
  // Код и технические данные
  code: {
    fontSize: fontSizes.sm,
    fontWeight: fontWeights.normal,
    lineHeight: lineHeights.normal,
    letterSpacing: letterSpacings.normal,
    fontFamily: fontFamilies.monospace,
  },
};

// Адаптивная типографика
export const responsiveTextStyles = {
  h1: {
    mobile: textStyles.h3,
    tablet: textStyles.h2,
    desktop: textStyles.h1,
  },
  
  h2: {
    mobile: textStyles.h4,
    tablet: textStyles.h3,
    desktop: textStyles.h2,
  },
  
  h3: {
    mobile: textStyles.h5,
    tablet: textStyles.h4,
    desktop: textStyles.h3,
  },
};

// Утилиты для работы с типографикой
export const typographyUtils = {
  /**
   * Получение стиля текста
   */
  getTextStyle(variant) {
    return textStyles[variant] || textStyles.body1;
  },
  
  /**
   * Получение адаптивного стиля
   */
  getResponsiveStyle(variant, breakpoint) {
    const responsive = responsiveTextStyles[variant];
    return responsive?.[breakpoint] || textStyles[variant] || textStyles.body1;
  },
  
  /**
   * Создание CSS стилей
   */
  createCSSStyle(variant) {
    const style = this.getTextStyle(variant);
    return {
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      lineHeight: style.lineHeight,
      letterSpacing: style.letterSpacing,
      fontFamily: style.fontFamily || fontFamilies.primary,
      textTransform: style.textTransform || 'none',
    };
  }
};

// Экспорт
export const typography = {
  fontFamilies,
  fontSizes,
  fontWeights,
  lineHeights,
  letterSpacings,
  textStyles,
  responsiveTextStyles,
  utils: typographyUtils,
};

export default typography;
