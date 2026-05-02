#!/usr/bin/env node

/**
 * Скрипт для автоматической миграции с дизайн-системы на нативные компоненты
 * 
 * Использование:
 * node frontend/src/scripts/migrate-design-system.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import logger from '../utils/logger';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Маппинг старых импортов на новые
const IMPORT_MAPPINGS = {
  // Компоненты
  'import { Card, Badge, Button, Skeleton } from \'../components/ui/native\';':
  'import { Card, Badge, Button, Skeleton } from \'../components/ui/native\';',

  'import { Card, Button, Badge } from \'../components/ui/native\';':
  'import { Card, Button, Badge } from \'../components/ui/native\';',

  'import { Button } from \'../components/ui/native\';':
  'import { Button } from \'../components/ui/native\';',

  'import { Card } from \'../components/ui/native\';':
  'import { Card } from \'../components/ui/native\';',

  'import { Badge } from \'../components/ui/native\';':
  'import { Badge } from \'../components/ui/native\';',

  'import { Skeleton } from \'../components/ui/native\';':
  'import { Skeleton } from \'../components/ui/native\';',

  // Хуки - основные
  'import { useBreakpoint, useTouchDevice } from \'../components/ui/native\';':
  'import { useBreakpoint, useTouchDevice } from \'../components/ui/native\';',

  'import { useBreakpoint } from \'../components/ui/native\';':
  'import { useBreakpoint } from \'../components/ui/native\';',

  'import { useTouchDevice } from \'../components/ui/native\';':
  'import { useTouchDevice } from \'../components/ui/native\';',

  // Хуки анимации
  'import { useFade, useSlide, useScale } from \'../components/ui/native\';':
  'import { useFade, useSlide, useScale } from \'../components/ui/native\';',

  'import { useFade, useScale } from \'../components/ui/native\';':
  'import { useFade, useScale } from \'../components/ui/native\';',

  'import { useFade, useSlide } from \'../components/ui/native\';':
  'import { useFade, useSlide } from \'../components/ui/native\';',

  // Смешанные импорты
  'export { useBreakpoint, useTouchDevice } from \'../components/ui/native\';\\nexport { useTheme } from \'../../contexts/ThemeContext\';':
  'export { useBreakpoint, useTouchDevice } from \'../components/ui/native\';\nexport { useTheme } from \'../../contexts/ThemeContext\';'
};

// Регулярные выражения для сложных случаев
const REGEX_MAPPINGS = [
{
  pattern: /import\s*{\s*([^}]+)\s*}\s*from\s*['"]\.\.\/design-system\/components['"];?/g,
  replacement: (match, imports) => {
    const cleanImports = imports.trim();
    return `import { ${cleanImports} } from '../components/ui/native';`;
  }
},
{
  pattern: /import\s*{\s*([^}]+)\s*}\s*from\s*['"]\.\.\/\.\.\/design-system\/components['"];?/g,
  replacement: (match, imports) => {
    const cleanImports = imports.trim();
    return `import { ${cleanImports} } from '../components/ui/native';`;
  }
}];


// Функция для рекурсивного поиска файлов
function findFiles(dir, extension = '.jsx') {
  let results = [];
  const list = fs.readdirSync(dir);

  list.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat && stat.isDirectory()) {
      // Пропускаем node_modules и другие служебные папки
      if (!['node_modules', '.git', 'dist', 'build'].includes(file)) {
        results = results.concat(findFiles(filePath, extension));
      }
    } else if (file.endsWith(extension)) {
      results.push(filePath);
    }
  });

  return results;
}

// Функция для миграции файла
function migrateFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let changed = false;
    const originalContent = content;

    // Применяем точные маппинги
    Object.entries(IMPORT_MAPPINGS).forEach(([oldImport, newImport]) => {
      if (content.includes(oldImport)) {
        content = content.replace(new RegExp(escapeRegExp(oldImport), 'g'), newImport);
        changed = true;
      }
    });

    // Применяем регулярные выражения для сложных случаев
    REGEX_MAPPINGS.forEach(({ pattern, replacement }) => {
      const matches = content.match(pattern);
      if (matches) {
        content = content.replace(pattern, replacement);
        changed = true;
      }
    });

    // Проверяем на потенциальные проблемы
    const issues = checkForIssues(content, filePath);
    if (issues.length > 0) {
      logger.warn(`⚠️  Potential issues in ${filePath}:`);
      issues.forEach((issue) => logger.warn(`   - ${issue}`));
    }

    // Сохраняем файл если были изменения
    if (changed) {
      fs.writeFileSync(filePath, content, 'utf8');
      logger.log(`✅ Migrated: ${filePath}`);

      // Показываем что изменилось
      if (process.env.VERBOSE) {
        logger.log(`   Old: ${originalContent.slice(0, 100)}...`);
        logger.log(`   New: ${content.slice(0, 100)}...`);
      }

      return true;
    }

    return false;
  } catch (error) {
    logger.error(`❌ Error migrating ${filePath}:`, error.message);
    return false;
  }
}

// Функция для экранирования специальных символов в регулярных выражениях
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Функция для проверки потенциальных проблем
function checkForIssues(content) {
  const issues = [];

  // Проверяем на дублированные импорты
  const importLines = content.match(/^import.*from.*$/gm) || [];
  const importSources = importLines.map((line) => {
    const match = line.match(/from\s+['"]([^'"]+)['"]/);
    return match ? match[1] : null;
  }).filter(Boolean);

  const duplicates = importSources.filter((item, index) => importSources.indexOf(item) !== index);
  if (duplicates.length > 0) {
    issues.push(`Duplicate imports detected: ${[...new Set(duplicates)].join(', ')}`);
  }

  // Проверяем на смешанные импорты из старой и новой системы
  const hasOldImports = /from\s+['"][^'"]*design-system[^'"]*['"]/.test(content);
  const hasNewImports = /from\s+['"][^'"]*ui\/native[^'"]*['"]/.test(content);

  if (hasOldImports && hasNewImports) {
    issues.push('Mixed old and new design system imports detected');
  }

  // Проверяем на неподдерживаемые компоненты
  const unsupportedComponents = ['Modal', 'Tooltip', 'Spinner', 'Dropdown'];
  unsupportedComponents.forEach((component) => {
    if (new RegExp(`\\b${component}\\b`).test(content) &&
    /from\s+['"][^'"]*ui\/native[^'"]*['"]/.test(content)) {
      issues.push(`Unsupported component '${component}' may need manual migration`);
    }
  });

  return issues;
}

// Основная функция
function main() {
  logger.log('🚀 Starting design system migration...\n');

  const srcDir = path.join(__dirname, '../');
  logger.log(`📂 Searching in directory: ${srcDir}`);

  const files = findFiles(srcDir, '.jsx').concat(findFiles(srcDir, '.js'));
  logger.log(`📄 Found ${files.length} files to check`);

  let migratedCount = 0;
  let totalFiles = 0;

  files.forEach((file) => {
    // Пропускаем файлы дизайн-системы и нативных компонентов
    if (file.includes('/design-system/') || file.includes('/ui/native/')) {
      return;
    }

    totalFiles++;
    if (migrateFile(file)) {
      migratedCount++;
    }
  });

  logger.log('\n📊 Migration Summary:');
  logger.log(`   Total files checked: ${totalFiles}`);
  logger.log(`   Files migrated: ${migratedCount}`);
  logger.log(`   Files unchanged: ${totalFiles - migratedCount}`);

  if (migratedCount > 0) {
    logger.log('\n✨ Migration completed successfully!');
    logger.log('\n📝 Next steps:');
    logger.log('   1. Test the migrated components');
    logger.log('   2. Remove old design-system imports');
    logger.log('   3. Update any remaining manual imports');
  } else {
    logger.log('\n💡 No files needed migration.');
  }
}

// Запуск скрипта
const currentFile = fileURLToPath(import.meta.url);
const scriptFile = process.argv[1];

if (currentFile === scriptFile) {
  main();
}

export { migrateFile, findFiles, IMPORT_MAPPINGS };