#!/usr/bin/env node

/**
 * 🎨 Скрипт для проверки соблюдения принципов централизованной темизации
 * 
 * Использование:
 * npm run check-theme
 * или
 * node scripts/check-theme-compliance.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Паттерны для поиска нарушений
const PATTERNS = {
  duplicatedTokens: /const\s+designTokens\s*=\s*\{/,
  hardcodedHex: /#([0-9a-fA-F]{3,6})(?![0-9a-fA-F])/g,
  hardcodedSpacing: /padding:\s*['"](\d+px|[\d.]+rem)/g,
  hardcodedFonts: /fontSize:\s*['"](\d+px|[\d.]+rem)/g,
  missingThemeImport: /useTheme.*ThemeContext/,
  cssVarsUsage: /var\(--[\w-]+\)/g
};

const SRC_DIR = path.join(__dirname, '../src');
const IGNORE_DIRS = ['test', 'tests', '__tests__', 'node_modules', '.git'];
const FILE_EXTENSIONS = ['.jsx', '.js', '.tsx', '.ts'];

// Рекурсивное сканирование файлов
function scanDirectory(dir) {
  const files = [];
  
  try {
    const entries = fs.readdirSync(dir);
    
    for (const entry of entries) {
      const fullPath = path.join(dir, entry);
      const stat = fs.statSync(fullPath);
      
      if (stat.isDirectory()) {
        if (!IGNORE_DIRS.includes(entry)) {
          files.push(...scanDirectory(fullPath));
        }
      } else {
        const ext = path.extname(entry);
        if (FILE_EXTENSIONS.includes(ext)) {
          files.push(fullPath);
        }
      }
    }
  } catch (error) {
    console.warn(`⚠️ Не удалось прочитать директорию: ${dir}`);
  }
  
  return files;
}

// Анализ файла
function analyzeFile(filePath) {
  const relativePath = path.relative(SRC_DIR, filePath);
  const content = fs.readFileSync(filePath, 'utf-8');
  
  const analysis = {
    file: relativePath,
    issues: [],
    score: 100
  };
  
  // Проверка на дублированные токены
  if (PATTERNS.duplicatedTokens.test(content)) {
    analysis.issues.push({
      type: 'error',
      message: '🚨 Найдены дублированные designTokens',
      suggestion: 'Используйте const { getColor, designTokens } = useTheme();'
    });
    analysis.score -= 30;
  }
  
  // Проверка хардкод цветов
  const hexColors = content.match(PATTERNS.hardcodedHex);
  if (hexColors && hexColors.length > 3) {
    analysis.issues.push({
      type: 'warning',
      message: `⚠️ Найдено ${hexColors.length} хардкод цветов`,
      suggestion: 'Замените на getColor() или CSS переменные'
    });
    analysis.score -= 15;
  }
  
  // Проверка отсутствия useTheme
  const hasStyles = content.includes('background:') || content.includes('color:');
  const hasThemeImport = PATTERNS.missingThemeImport.test(content);
  
  if (hasStyles && !hasThemeImport) {
    analysis.issues.push({
      type: 'warning',
      message: '📦 Компонент использует стили, но не импортирует useTheme',
      suggestion: 'Добавьте import { useTheme } from "../contexts/ThemeContext";'
    });
    analysis.score -= 20;
  }
  
  // Проверка использования CSS переменных (положительный показатель)
  const cssVars = content.match(PATTERNS.cssVarsUsage);
  if (cssVars && cssVars.length > 0) {
    analysis.score += 5; // Бонус за использование CSS переменных
  }
  
  analysis.score = Math.max(0, Math.min(100, analysis.score));
  
  return analysis;
}

// Основная функция
function checkThemeCompliance() {
  console.log('🎨 Проверка соблюдения принципов централизованной темизации\n');
  
  const files = scanDirectory(SRC_DIR);
  console.log(`📂 Найдено ${files.length} файлов для анализа\n`);
  
  const results = files.map(analyzeFile);
  
  // Статистика
  const totalFiles = results.length;
  const errorFiles = results.filter(r => r.issues.some(i => i.type === 'error')).length;
  const warningFiles = results.filter(r => r.issues.some(i => i.type === 'warning')).length;
  const cleanFiles = results.filter(r => r.issues.length === 0).length;
  
  const avgScore = results.reduce((sum, r) => sum + r.score, 0) / totalFiles;
  
  // Отчет
  console.log('📊 ИТОГОВАЯ СТАТИСТИКА:');
  console.log(`✅ Чистые файлы: ${cleanFiles}/${totalFiles} (${Math.round(cleanFiles/totalFiles*100)}%)`);
  console.log(`⚠️ Файлы с предупреждениями: ${warningFiles}`);
  console.log(`🚨 Файлы с ошибками: ${errorFiles}`);
  console.log(`📈 Средний балл: ${avgScore.toFixed(1)}/100\n`);
  
  // Детальные результаты
  const problemFiles = results.filter(r => r.issues.length > 0);
  
  if (problemFiles.length === 0) {
    console.log('🎉 ОТЛИЧНО! Все файлы соответствуют принципам централизованной темизации!');
    console.log('✅ Система темизации полностью унифицирована');
    console.log('✅ Готова для дальнейшей разработки\n');
  } else {
    console.log('🔍 ФАЙЛЫ, ТРЕБУЮЩИЕ ВНИМАНИЯ:\n');
    
    problemFiles.forEach(result => {
      console.log(`📄 ${result.file} (балл: ${result.score}/100)`);
      result.issues.forEach(issue => {
        const emoji = issue.type === 'error' ? '🚨' : '⚠️';
        console.log(`  ${emoji} ${issue.message}`);
        console.log(`     💡 ${issue.suggestion}\n`);
      });
    });
  }
  
  // Рекомендации
  console.log('🎯 РЕКОМЕНДАЦИИ ДЛЯ УЛУЧШЕНИЯ:');
  
  if (errorFiles > 0) {
    console.log('🔥 КРИТИЧНО: Устранить дублированные designTokens');
  }
  
  if (warningFiles > 0) {
    console.log('⚡ РЕКОМЕНДУЕТСЯ: Заменить хардкод стили на централизованные функции');
  }
  
  if (avgScore < 80) {
    console.log('📖 ИЗУЧИТЬ: Документацию THEME_SYSTEM_GUIDE.md');
  } else {
    console.log('✨ ОТЛИЧНО: Система темизации в хорошем состоянии!');
  }
  
  return {
    totalFiles,
    cleanFiles,
    errorFiles,
    warningFiles,
    avgScore,
    compliant: avgScore >= 85 && errorFiles === 0
  };
}

// Запуск при прямом вызове
if (import.meta.url === `file://${process.argv[1]}`) {
  const result = checkThemeCompliance();
  process.exit(result.compliant ? 0 : 1);
}

export { checkThemeCompliance, analyzeFile, PATTERNS };
