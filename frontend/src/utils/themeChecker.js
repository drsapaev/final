/**
 * 🔍 Диагностический инструмент для проверки унификации темы
 * Обнаруживает файлы, которые не используют централизованную систему темизации
 */

// Паттерны, которые указывают на нарушения централизованной темы
const VIOLATION_PATTERNS = {
  // Дублированные designTokens
  duplicatedTokens: /const\s+designTokens\s*=\s*\{/g,
  
  // Хардкод цвета (hex коды)
  hardcodedColors: /#[0-9a-fA-F]{3,6}(?![0-9a-fA-F])/g,
  
  // Хардкод отступы 
  hardcodedSpacing: /padding:\s*['"][0-9]+px/g,
  
  // Хардкод шрифты
  hardcodedFonts: /fontSize:\s*['"][0-9]+px/g,
  
  // Хардкод тени
  hardcodedShadows: /boxShadow:\s*['"][^'"]*(rgba\([^)]+\))/g,
  
  // Отсутствие useTheme импорта
  missingThemeImport: /import.*useTheme.*from.*ThemeContext/g,
  
  // Проверка использования старых импортов
  oldDesignSystemImports: /import.*{.*getColor.*}.*design-system/g
};

// Проверка файла на соблюдение принципов централизованной темы
export const checkFileThemeCompliance = (fileContent, fileName) => {
  const violations = [];
  
  // Проверяем на дублированные tokens
  if (VIOLATION_PATTERNS.duplicatedTokens.test(fileContent)) {
    violations.push({
      type: 'duplicated_tokens',
      severity: 'error',
      message: 'Найдены дублированные designTokens. Используйте useTheme() вместо собственных токенов.',
      suggestion: 'Замените на: const { getColor, getSpacing, designTokens } = useTheme();'
    });
  }
  
  // Проверяем хардкод цвета
  const hardcodedColorMatches = fileContent.match(VIOLATION_PATTERNS.hardcodedColors);
  if (hardcodedColorMatches && hardcodedColorMatches.length > 5) { // Допускаем несколько для особых случаев
    violations.push({
      type: 'hardcoded_colors',
      severity: 'warning',
      message: `Найдено ${hardcodedColorMatches.length} хардкод цветов. Используйте getColor() или CSS переменные.`,
      suggestion: 'Замените #3b82f6 на getColor("primary", 500) или var(--accent-color)'
    });
  }
  
  // Проверяем отсутствие useTheme
  if (!VIOLATION_PATTERNS.missingThemeImport.test(fileContent) && 
      (fileContent.includes('background:') || fileContent.includes('color:'))) {
    violations.push({
      type: 'missing_theme_import',
      severity: 'warning', 
      message: 'Компонент использует стили, но не импортирует useTheme.',
      suggestion: 'Добавьте: import { useTheme } from "../contexts/ThemeContext";'
    });
  }
  
  return {
    fileName,
    compliant: violations.length === 0,
    violations,
    score: Math.max(0, 100 - violations.length * 20) // 100% если нет нарушений
  };
};

// Проверка всего проекта (для использования в скриптах)
export const generateThemeReport = (filesList) => {
  const results = filesList.map(file => 
    checkFileThemeCompliance(file.content, file.name)
  );
  
  const totalFiles = results.length;
  const compliantFiles = results.filter(r => r.compliant).length;
  const violationsCount = results.reduce((sum, r) => sum + r.violations.length, 0);
  
  return {
    summary: {
      totalFiles,
      compliantFiles,
      complianceRate: Math.round((compliantFiles / totalFiles) * 100),
      totalViolations: violationsCount
    },
    results,
    recommendations: generateRecommendations(results)
  };
};

// Генерирование рекомендаций на основе найденных нарушений
const generateRecommendations = (results) => {
  const recommendations = [];
  
  const hasDuplicatedTokens = results.some(r => 
    r.violations.some(v => v.type === 'duplicated_tokens')
  );
  
  if (hasDuplicatedTokens) {
    recommendations.push({
      priority: 'high',
      action: 'Удалить все дублированные designTokens и использовать централизованные',
      benefit: 'Уменьшит размер кода на 50%+ и обеспечит консистентность'
    });
  }
  
  return recommendations;
};

// Утилитарная функция для быстрой проверки в console
export const quickThemeCheck = () => {
  console.log('🎨 Быстрая проверка темизации проекта');
  console.log('Для полной проверки используйте generateThemeReport()');
  
  // Проверяем наличие CSS переменных
  const root = document.documentElement;
  const hasThemeVars = !!root.style.getPropertyValue('--accent-color');
  
  console.log(`✅ CSS переменные темы: ${hasThemeVars ? 'Активны' : 'НЕ активны'}`);
  console.log(`🌓 Текущая тема: ${document.documentElement.getAttribute('data-theme') || 'не задана'}`);
  
  return hasThemeVars;
};

export default {
  checkFileThemeCompliance,
  generateThemeReport,
  quickThemeCheck,
  VIOLATION_PATTERNS
};
