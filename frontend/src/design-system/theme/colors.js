/**
 * Палитра цветов дизайн-системы
 * Согласно MASTER_TODO_LIST строки 220-224
 */

// Основные цвета бренда
export const brandColors = {
  primary: {
    50: '#e3f2fd',
    100: '#bbdefb',
    200: '#90caf9',
    300: '#64b5f6',
    400: '#42a5f5',
    500: '#2196f3', // Основной синий
    600: '#1e88e5',
    700: '#1976d2',
    800: '#1565c0',
    900: '#0d47a1',
  },
  
  secondary: {
    50: '#f3e5f5',
    100: '#e1bee7',
    200: '#ce93d8',
    300: '#ba68c8',
    400: '#ab47bc',
    500: '#9c27b0', // Фиолетовый акцент
    600: '#8e24aa',
    700: '#7b1fa2',
    800: '#6a1b9a',
    900: '#4a148c',
  },
  
  success: {
    50: '#e8f5e8',
    100: '#c8e6c9',
    200: '#a5d6a7',
    300: '#81c784',
    400: '#66bb6a',
    500: '#4caf50', // Зеленый успех
    600: '#43a047',
    700: '#388e3c',
    800: '#2e7d32',
    900: '#1b5e20',
  },
  
  warning: {
    50: '#fff8e1',
    100: '#ffecb3',
    200: '#ffe082',
    300: '#ffd54f',
    400: '#ffca28',
    500: '#ffc107', // Желтый предупреждение
    600: '#ffb300',
    700: '#ffa000',
    800: '#ff8f00',
    900: '#ff6f00',
  },
  
  error: {
    50: '#ffebee',
    100: '#ffcdd2',
    200: '#ef9a9a',
    300: '#e57373',
    400: '#ef5350',
    500: '#f44336', // Красный ошибка
    600: '#e53935',
    700: '#d32f2f',
    800: '#c62828',
    900: '#b71c1c',
  },
  
  info: {
    50: '#e1f5fe',
    100: '#b3e5fc',
    200: '#81d4fa',
    300: '#4fc3f7',
    400: '#29b6f6',
    500: '#03a9f4', // Голубой информация
    600: '#039be5',
    700: '#0288d1',
    800: '#0277bd',
    900: '#01579b',
  }
};

// Нейтральные цвета
export const neutralColors = {
  white: '#ffffff',
  black: '#000000',
  
  gray: {
    50: '#fafafa',
    100: '#f5f5f5',
    200: '#eeeeee',
    300: '#e0e0e0',
    400: '#bdbdbd',
    500: '#9e9e9e',
    600: '#757575',
    700: '#616161',
    800: '#424242',
    900: '#212121',
  }
};

// Специальные цвета для медицинской тематики
export const medicalColors = {
  cardiology: '#e91e63', // Розовый для кардиологии
  dermatology: '#ff9800', // Оранжевый для дерматологии
  dentistry: '#00bcd4', // Бирюзовый для стоматологии
  laboratory: '#9c27b0', // Фиолетовый для лаборатории
  general: '#607d8b', // Серо-синий для общих врачей
  
  // Статусы
  paid: brandColors.success[500],
  pending: brandColors.warning[500],
  cancelled: brandColors.error[500],
  completed: brandColors.success[600],
  
  // Очередь
  waiting: brandColors.info[500],
  called: brandColors.warning[500],
  serving: brandColors.success[500],
};

// Темная тема
export const darkColors = {
  background: {
    default: '#121212',
    paper: '#1e1e1e',
    elevated: '#242424',
  },
  
  text: {
    primary: '#ffffff',
    secondary: '#b3b3b3',
    disabled: '#666666',
  },
  
  divider: '#333333',
  
  action: {
    hover: 'rgba(255, 255, 255, 0.08)',
    selected: 'rgba(255, 255, 255, 0.12)',
    disabled: 'rgba(255, 255, 255, 0.26)',
  }
};

// Светлая тема
export const lightColors = {
  background: {
    default: '#fafafa',
    paper: '#ffffff',
    elevated: '#ffffff',
  },
  
  text: {
    primary: '#212121',
    secondary: '#757575',
    disabled: '#bdbdbd',
  },
  
  divider: '#e0e0e0',
  
  action: {
    hover: 'rgba(0, 0, 0, 0.04)',
    selected: 'rgba(0, 0, 0, 0.08)',
    disabled: 'rgba(0, 0, 0, 0.26)',
  }
};

// Экспорт всех цветов
export const colors = {
  brand: brandColors,
  neutral: neutralColors,
  medical: medicalColors,
  dark: darkColors,
  light: lightColors,
};

export default colors;
