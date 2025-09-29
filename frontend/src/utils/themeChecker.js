// Утилиты для проверки и исправления темы
import { useTheme } from '../contexts/ThemeContext';

/**
 * Проверяет использование хардкодированных цветов в стилях
 */
export function checkHardcodedColors(styles) {
  const hardcodedColors = [
    '#000000', '#ffffff', '#000', '#fff',
    'rgb(0, 0, 0)', 'rgb(255, 255, 255)',
    'rgba(0, 0, 0, 0)', 'rgba(255, 255, 255, 1)',
    'black', 'white', 'red', 'blue', 'green', 'yellow'
  ];

  const issues = [];
  
  if (typeof styles === 'string') {
    hardcodedColors.forEach(color => {
      if (styles.includes(color)) {
        issues.push({
          type: 'hardcoded_color',
          value: color,
          suggestion: 'Используйте getColor() из useTheme()'
        });
      }
    });
  } else if (typeof styles === 'object') {
    Object.entries(styles).forEach(([key, value]) => {
      if (typeof value === 'string') {
        hardcodedColors.forEach(color => {
          if (value.includes(color)) {
            issues.push({
              type: 'hardcoded_color',
              property: key,
              value: color,
              suggestion: 'Используйте getColor() из useTheme()'
            });
          }
        });
      }
    });
  }

  return issues;
}

/**
 * Проверяет использование хардкодированных размеров
 */
export function checkHardcodedSizes(styles) {
  const hardcodedSizes = [
    'px', 'em', 'rem', '%', 'vh', 'vw'
  ];

  const issues = [];
  
  if (typeof styles === 'string') {
    const sizeRegex = /(\d+(?:\.\d+)?)(px|em|rem|%|vh|vw)/g;
    let match;
    while ((match = sizeRegex.exec(styles)) !== null) {
      issues.push({
        type: 'hardcoded_size',
        value: match[0],
        suggestion: 'Используйте getSpacing() или getFontSize() из useTheme()'
      });
    }
  } else if (typeof styles === 'object') {
    Object.entries(styles).forEach(([key, value]) => {
      if (typeof value === 'string') {
        const sizeRegex = /(\d+(?:\.\d+)?)(px|em|rem|%|vh|vw)/g;
        let match;
        while ((match = sizeRegex.exec(value)) !== null) {
          issues.push({
            type: 'hardcoded_size',
            property: key,
            value: match[0],
            suggestion: 'Используйте getSpacing() или getFontSize() из useTheme()'
          });
        }
      }
    });
  }

  return issues;
}

/**
 * Проверяет использование CSS переменных вместо темы
 */
export function checkCSSVariables(styles) {
  const cssVarRegex = /var\(--[^)]+\)/g;
  const issues = [];
  
  if (typeof styles === 'string') {
    let match;
    while ((match = cssVarRegex.exec(styles)) !== null) {
      issues.push({
        type: 'css_variable',
        value: match[0],
        suggestion: 'Используйте getColor() из useTheme() вместо CSS переменных'
      });
    }
  } else if (typeof styles === 'object') {
    Object.entries(styles).forEach(([key, value]) => {
      if (typeof value === 'string') {
        let match;
        while ((match = cssVarRegex.exec(value)) !== null) {
          issues.push({
            type: 'css_variable',
            property: key,
            value: match[0],
            suggestion: 'Используйте getColor() из useTheme() вместо CSS переменных'
          });
        }
      }
    });
  }

  return issues;
}

/**
 * Проверяет все проблемы с темой в стилях
 */
export function checkThemeIssues(styles) {
  const colorIssues = checkHardcodedColors(styles);
  const sizeIssues = checkHardcodedSizes(styles);
  const cssVarIssues = checkCSSVariables(styles);
  
  return {
    colors: colorIssues,
    sizes: sizeIssues,
    cssVariables: cssVarIssues,
    total: colorIssues.length + sizeIssues.length + cssVarIssues.length
  };
}

/**
 * Создает исправленные стили с использованием темы
 */
export function createThemedStyles(styles, theme) {
  const { getColor, getSpacing, getFontSize } = theme;
  
  if (typeof styles === 'function') {
    return styles(theme);
  }
  
  if (typeof styles === 'object') {
    const themedStyles = {};
    
    Object.entries(styles).forEach(([key, value]) => {
      if (typeof value === 'string') {
        // Заменяем хардкодированные цвета
        let themedValue = value
          .replace(/#000000|#000|black/gi, getColor('text', 'primary'))
          .replace(/#ffffff|#fff|white/gi, getColor('background', 'primary'))
          .replace(/#ff0000|red/gi, getColor('error', 'main'))
          .replace(/#0000ff|blue/gi, getColor('primary', 'main'))
          .replace(/#00ff00|green/gi, getColor('success', 'main'))
          .replace(/#ffff00|yellow/gi, getColor('warning', 'main'));
        
        // Заменяем хардкодированные размеры
        themedValue = themedValue
          .replace(/(\d+)px/g, (match, num) => {
            const size = parseInt(num);
            if (size <= 4) return getSpacing('xs');
            if (size <= 8) return getSpacing('sm');
            if (size <= 12) return getSpacing('md');
            if (size <= 16) return getSpacing('lg');
            if (size <= 24) return getSpacing('xl');
            return getSpacing('xxl');
          });
        
        themedStyles[key] = themedValue;
      } else {
        themedStyles[key] = value;
      }
    });
    
    return themedStyles;
  }
  
  return styles;
}

/**
 * Хук для создания тематических стилей
 */
export function useThemedStyles(styles) {
  const theme = useTheme();
  return createThemedStyles(styles, theme);
}

/**
 * Компонент для отображения проблем с темой
 */
export function ThemeIssuesDisplay({ issues, onFix }) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  if (issues.total === 0) {
    return null;
  }

  const containerStyle = {
    padding: getSpacing('md'),
    backgroundColor: getColor('warning', 'light'),
    border: `1px solid ${getColor('warning', 'main')}`,
    borderRadius: '8px',
    marginBottom: getSpacing('md')
  };

  const titleStyle = {
    fontSize: getFontSize('md'),
    fontWeight: '600',
    color: getColor('warning', 'dark'),
    marginBottom: getSpacing('sm')
  };

  const issueStyle = {
    fontSize: getFontSize('sm'),
    color: getColor('text', 'secondary'),
    marginBottom: getSpacing('xs'),
    padding: getSpacing('xs'),
    backgroundColor: getColor('background', 'primary'),
    borderRadius: '4px'
  };

  const fixButtonStyle = {
    padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    marginTop: getSpacing('sm')
  };

  return (
    <div style={containerStyle}>
      <div style={titleStyle}>
        Найдено {issues.total} проблем с темой
      </div>
      
      {issues.colors.map((issue, index) => (
        <div key={`color-${index}`} style={issueStyle}>
          <strong>Цвет:</strong> {issue.value} → {issue.suggestion}
        </div>
      ))}
      
      {issues.sizes.map((issue, index) => (
        <div key={`size-${index}`} style={issueStyle}>
          <strong>Размер:</strong> {issue.value} → {issue.suggestion}
        </div>
      ))}
      
      {issues.cssVariables.map((issue, index) => (
        <div key={`css-${index}`} style={issueStyle}>
          <strong>CSS переменная:</strong> {issue.value} → {issue.suggestion}
        </div>
      ))}
      
      {onFix && (
        <button style={fixButtonStyle} onClick={onFix}>
          Исправить автоматически
        </button>
      )}
    </div>
  );
}

/**
 * Утилита для автоматического исправления стилей
 */
export function autoFixStyles(styles, theme) {
  const { getColor, getSpacing, getFontSize } = theme;
  
  if (typeof styles === 'object') {
    const fixedStyles = {};
    
    Object.entries(styles).forEach(([key, value]) => {
      if (typeof value === 'string') {
        let fixedValue = value;
        
        // Заменяем хардкодированные цвета
        fixedValue = fixedValue
          .replace(/#000000|#000|black/gi, getColor('text', 'primary'))
          .replace(/#ffffff|#fff|white/gi, getColor('background', 'primary'))
          .replace(/#ff0000|red/gi, getColor('error', 'main'))
          .replace(/#0000ff|blue/gi, getColor('primary', 'main'))
          .replace(/#00ff00|green/gi, getColor('success', 'main'))
          .replace(/#ffff00|yellow/gi, getColor('warning', 'main'));
        
        // Заменяем хардкодированные размеры
        fixedValue = fixedValue
          .replace(/(\d+)px/g, (match, num) => {
            const size = parseInt(num);
            if (size <= 4) return getSpacing('xs');
            if (size <= 8) return getSpacing('sm');
            if (size <= 12) return getSpacing('md');
            if (size <= 16) return getSpacing('lg');
            if (size <= 24) return getSpacing('xl');
            return getSpacing('xxl');
          });
        
        fixedStyles[key] = fixedValue;
      } else {
        fixedStyles[key] = value;
      }
    });
    
    return fixedStyles;
  }
  
  return styles;
}
