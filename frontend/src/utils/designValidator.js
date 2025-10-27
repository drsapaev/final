/**
 * Система проверки дизайна для панелей
 * Проверяет соответствие компонентов унифицированной дизайн-системе
 */

/**
 * Правила валидации дизайн-системы
 */
export const designRules = {
  colors: {
    // Запрещенные цвета (жестко заданные)
    forbiddenColors: [
      '#60a5fa', '#3b82f6', '#2563eb', '#1d4ed8', // Синие
      '#10b981', '#f59e0b', '#ef4444', '#06b6d4', // Зеленые, желтые, красные, голубые
      '#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1', // Серые светлые
      '#64748b', '#475569', '#334155', '#1e293b', '#0f172a', // Серые темные
      '#ffffff', '#000000', '#gray', '#red', '#blue', '#green' // Базовые цвета
    ],

    // Разрешенные функции цветов
    allowedColorFunctions: [
      'getColor',
      'isDark',
      'theme'
    ]
  },

  spacing: {
    // Запрещенные отступы (жестко заданные)
    forbiddenSpacing: [
      '4px', '8px', '12px', '16px', '20px', '24px', '32px',
      '2px', '6px', '10px', '14px', '18px', '22px', '26px', '30px',
      '1rem', '1.5rem', '2rem', '2.5rem', '3rem'
    ],

    // Разрешенные функции отступов
    allowedSpacingFunctions: [
      'getSpacing'
    ]
  },

  typography: {
    // Запрещенные размеры шрифтов
    forbiddenFontSizes: [
      '14px', '16px', '18px', '20px', '24px', '32px',
      '12px', '10px', '8px', '36px', '48px',
      '0.875rem', '1rem', '1.125rem', '1.25rem', '1.5rem', '2rem'
    ],

    // Разрешенные функции типографии
    allowedTypographyFunctions: [
      'getFontSize'
    ]
  },

  shadows: {
    // Запрещенные тени
    forbiddenShadows: [
      '0 1px 3px rgba(0, 0, 0, 0.1)',
      '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
      '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
      '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
    ],

    // Разрешенные функции теней
    allowedShadowFunctions: [
      'getShadow'
    ]
  }
};

/**
 * Проверяет использование цветов в коде
 */
export const validateColors = (code) => {
  const errors = [];
  const warnings = [];

  // Проверяем запрещенные цвета
  designRules.colors.forbiddenColors.forEach(color => {
    if (code.includes(color)) {
      errors.push(`Найден запрещенный цвет: ${color}`);
    }
  });

  // Проверяем отсутствие функций цветов
  const hasColorFunctions = designRules.colors.allowedColorFunctions.some(func =>
    code.includes(func)
  );

  if (!hasColorFunctions) {
    warnings.push('Не найдены функции дизайн-системы для цветов');
  }

  return { errors, warnings };
};

/**
 * Проверяет использование отступов в коде
 */
export const validateSpacing = (code) => {
  const errors = [];
  const warnings = [];

  // Проверяем запрещенные отступы
  designRules.spacing.forbiddenSpacing.forEach(spacing => {
    if (code.includes(spacing)) {
      errors.push(`Найден запрещенный отступ: ${spacing}`);
    }
  });

  // Проверяем отсутствие функций отступов
  const hasSpacingFunctions = designRules.spacing.allowedSpacingFunctions.some(func =>
    code.includes(func)
  );

  if (!hasSpacingFunctions) {
    warnings.push('Не найдены функции дизайн-системы для отступов');
  }

  return { errors, warnings };
};

/**
 * Проверяет использование типографии в коде
 */
export const validateTypography = (code) => {
  const errors = [];
  const warnings = [];

  // Проверяем запрещенные размеры шрифтов
  designRules.typography.forbiddenFontSizes.forEach(fontSize => {
    if (code.includes(fontSize)) {
      errors.push(`Найден запрещенный размер шрифта: ${fontSize}`);
    }
  });

  // Проверяем отсутствие функций типографии
  const hasTypographyFunctions = designRules.typography.allowedTypographyFunctions.some(func =>
    code.includes(func)
  );

  if (!hasTypographyFunctions) {
    warnings.push('Не найдены функции дизайн-системы для типографии');
  }

  return { errors, warnings };
};

/**
 * Проверяет использование теней в коде
 */
export const validateShadows = (code) => {
  const errors = [];
  const warnings = [];

  // Проверяем запрещенные тени
  designRules.shadows.forbiddenShadows.forEach(shadow => {
    if (code.includes(shadow)) {
      errors.push(`Найдена запрещенная тень: ${shadow}`);
    }
  });

  // Проверяем отсутствие функций теней
  const hasShadowFunctions = designRules.shadows.allowedShadowFunctions.some(func =>
    code.includes(func)
  );

  if (!hasShadowFunctions) {
    warnings.push('Не найдены функции дизайн-системы для теней');
  }

  return { errors, warnings };
};

/**
 * Основная функция валидации компонента
 */
export const validateComponentDesign = (code, componentName = 'Component') => {
  const results = {
    component: componentName,
    colors: validateColors(code),
    spacing: validateSpacing(code),
    typography: validateTypography(code),
    shadows: validateShadows(code),
    summary: {
      totalErrors: 0,
      totalWarnings: 0
    }
  };

  // Подсчитываем общее количество ошибок и предупреждений
  Object.keys(results).forEach(category => {
    if (category !== 'component' && category !== 'summary') {
      results.summary.totalErrors += results[category].errors.length;
      results.summary.totalWarnings += results[category].warnings.length;
    }
  });

  return results;
};

/**
 * Генерирует отчет о соответствии дизайн-системе
 */
export const generateDesignReport = (validationResults) => {
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      totalComponents: validationResults.length,
      totalErrors: 0,
      totalWarnings: 0,
      complianceScore: 0
    },
    components: validationResults
  };

  // Подсчитываем общую статистику
  validationResults.forEach(result => {
    report.summary.totalErrors += result.summary.totalErrors;
    report.summary.totalWarnings += result.summary.totalWarnings;
  });

  // Вычисляем общий балл соответствия (0-100)
  const totalIssues = report.summary.totalErrors + report.summary.totalWarnings;
  report.summary.complianceScore = Math.max(0, 100 - (totalIssues * 10));

  return report;
};

/**
 * Проверяет конкретный файл на соответствие дизайн-системе
 */
export const validateFile = async (filePath) => {
  try {
    const response = await fetch(`/api/validate-design?file=${filePath}`);
    return await response.json();
  } catch (error) {
    console.error('Ошибка при валидации файла:', error);
    return null;
  }
};

export default {
  validateComponentDesign,
  generateDesignReport,
  validateFile,
  rules: designRules
};
