/**
 * Утилита для работы с классами CSS
 * Встроенная реализация clsx для избежания внешних зависимостей.
 */

function toVal(mix) {
    var k, y, str='';

    if (typeof mix === 'string' || typeof mix === 'number') {
        str += mix;
    } else if (typeof mix === 'object') {
        if (Array.isArray(mix)) {
            for (k=0; k < mix.length; k++) {
                if (mix[k]) {
                    if (y = toVal(mix[k])) {
                        str && (str += ' ');
                        str += y;
                    }
                }
            }
        } else {
            for (k in mix) {
                if (mix[k]) {
                    str && (str += ' ');
                    str += k;
                }
            }
        }
    }

    return str;
}

export function clsx() {
    var i=0, tmp, x, str='';
    while (i < arguments.length) {
        if (tmp = arguments[i++]) {
            if (x = toVal(tmp)) {
                str && (str += ' ');
                str += x;
            }
        }
    }
    return str;
}

/**
 * Объединяет классы CSS в одну строку
 * @param {...any} inputs - Классы для объединения
 * @returns {string} - Объединенная строка классов
 */
export function cn(...inputs) {
  return clsx(...inputs);
}

/**
 * Создает условные классы на основе условий
 * @param {Object} conditions - Объект с условиями и классами
 * @returns {string} - Строка классов
 */
export function conditionalClasses(conditions) {
  const classes = [];

  for (const [condition, className] of Object.entries(conditions)) {
    if (condition && className) {
      classes.push(className);
    }
  }

  return classes.join(' ');
}

/**
 * Создает классы для состояний компонента
 * @param {string} base - Базовый класс
 * @param {Object} states - Состояния компонента
 * @returns {string} - Строка классов
 */
export function stateClasses(base, states = {}) {
  const classes = [base];

  for (const [state, className] of Object.entries(states)) {
    if (state && className) {
      classes.push(className);
    }
  }

  return classes.join(' ');
}

/**
 * Создает responsive классы
 * @param {Object} breakpoints - Классы для разных брейкпоинтов
 * @returns {string} - Строка responsive классов
 */
export function responsiveClasses(breakpoints = {}) {
  const classes = [];

  const breakpointMap = {
    xs: 'xs:',
    sm: 'sm:',
    md: 'md:',
    lg: 'lg:',
    xl: 'xl:',
    '2xl': '2xl:'
  };

  for (const [breakpoint, className] of Object.entries(breakpoints)) {
    if (breakpoint && className) {
      const prefix = breakpointMap[breakpoint] || '';
      classes.push(`${prefix}${className}`);
    }
  }

  return classes.join(' ');
}

export default cn;
