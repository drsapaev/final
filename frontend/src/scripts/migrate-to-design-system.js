#!/usr/bin/env node

/**
 * Миграционный скрипт для обновления компонентов на дизайн-систему
 * Автоматически заменяет старые импорты и стили на новые компоненты дизайн-системы
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import logger from '../utils/logger';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Конфигурация миграции
const MIGRATION_CONFIG = {
  // Замена импортов
  imports: {
    // Старые импорты -> новые импорты
    '\'../ui\'': '\'../ui/native\'',
    '\'../../ui\'': '\'../../ui/native\'',
    '\'../../../ui\'': '\'../../../ui/native\'',
    '\'../../../../ui\'': '\'../../../../ui/native\'',
    '\'../../../../../ui\'': '\'../../../../../ui/native\''
  },

  // Замена цветов
  colors: {
    // Старые цвета -> функции дизайн-системы
    '\'#60a5fa\'': 'getColor(\'primary\', 400)',
    '\'#3b82f6\'': 'getColor(\'primary\', 500)',
    '\'#2563eb\'': 'getColor(\'primary\', 600)',
    '\'#1d4ed8\'': 'getColor(\'primary\', 700)',
    '\'#10b981\'': 'getColor(\'success\', 500)',
    '\'#f59e0b\'': 'getColor(\'warning\', 500)',
    '\'#ef4444\'': 'getColor(\'danger\', 500)',
    '\'#06b6d4\'': 'getColor(\'info\', 500)',
    '\'#f8fafc\'': 'getColor(\'surface\')',
    '\'#f1f5f9\'': 'getColor(\'background\')',
    '\'#e2e8f0\'': 'getColor(\'border\')',
    '\'#cbd5e1\'': 'getColor(\'border\')',
    '\'#64748b\'': 'getColor(\'textSecondary\')',
    '\'#475569\'': 'getColor(\'textSecondary\')',
    '\'#334155\'': 'getColor(\'text\')',
    '\'#1e293b\'': 'getColor(\'text\')',
    '\'#0f172a\'': 'getColor(\'text\')'
  },

  // Замена отступов
  spacing: {
    '\'4px\'': 'getSpacing(\'xs\')',
    '\'8px\'': 'getSpacing(\'sm\')',
    '\'12px\'': 'getSpacing(\'md\')',
    '\'16px\'': 'getSpacing(\'lg\')',
    '\'20px\'': 'getSpacing(\'lg\')',
    '\'24px\'': 'getSpacing(\'xl\')',
    '\'32px\'': 'getSpacing(\'xl\')'
  },

  // Замена размеров шрифтов
  fontSizes: {
    '\'14px\'': 'getFontSize(\'sm\')',
    '\'16px\'': 'getFontSize(\'base\')',
    '\'18px\'': 'getFontSize(\'lg\')',
    '\'20px\'': 'getFontSize(\'xl\')',
    '\'24px\'': 'getFontSize(\'xl\')'
  },

  // Замена теней
  shadows: {
    '\'0 1px 3px rgba(0, 0, 0, 0.1)\'': 'getShadow(\'sm\')',
    '\'0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)\'': 'getShadow(\'md\')',
    '\'0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)\'': 'getShadow(\'lg\')',
    '\'0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)\'': 'getShadow(\'xl\')'
  }
};

/**
 * Рекурсивно находит все файлы в директории
 */
function findFiles(dir, ext = '.jsx') {
  const files = [];

  const items = fs.readdirSync(dir);

  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
      files.push(...findFiles(fullPath, ext));
    } else if (item.endsWith(ext)) {
      files.push(fullPath);
    }
  }

  return files;
}

/**
 * Проверяет, нужно ли мигрировать файл
 */
function shouldMigrateFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');

  // Проверяем наличие старых импортов или цветов
  const hasOldImports = Object.keys(MIGRATION_CONFIG.imports).some(oldImport =>
    content.includes(oldImport)
  );

  const hasOldColors = Object.keys(MIGRATION_CONFIG.colors).some(oldColor =>
    content.includes(oldColor)
  );

  const hasOldSpacing = Object.keys(MIGRATION_CONFIG.spacing).some(oldSpacing =>
    content.includes(oldSpacing)
  );

  return hasOldImports || hasOldColors || hasOldSpacing;
}

/**
 * Мигрирует содержимое файла
 */
function migrateFile(filePath) {
  logger.log(`Мигрируем: ${filePath}`);

  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;

  // Заменяем импорты
  for (const [oldImport, newImport] of Object.entries(MIGRATION_CONFIG.imports)) {
    if (content.includes(oldImport)) {
      content = content.replace(new RegExp(oldImport.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newImport);
      modified = true;
    }
  }

  // Заменяем цвета
  for (const [oldColor, newColor] of Object.entries(MIGRATION_CONFIG.colors)) {
    if (content.includes(oldColor)) {
      content = content.replace(new RegExp(oldColor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newColor);
      modified = true;
    }
  }

  // Заменяем отступы
  for (const [oldSpacing, newSpacing] of Object.entries(MIGRATION_CONFIG.spacing)) {
    if (content.includes(oldSpacing)) {
      content = content.replace(new RegExp(oldSpacing.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newSpacing);
      modified = true;
    }
  }

  // Заменяем размеры шрифтов
  for (const [oldFontSize, newFontSize] of Object.entries(MIGRATION_CONFIG.fontSizes)) {
    if (content.includes(oldFontSize)) {
      content = content.replace(new RegExp(oldFontSize.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newFontSize);
      modified = true;
    }
  }

  // Заменяем тени
  for (const [oldShadow, newShadow] of Object.entries(MIGRATION_CONFIG.shadows)) {
    if (content.includes(oldShadow)) {
      content = content.replace(new RegExp(oldShadow.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newShadow);
      modified = true;
    }
  }

  // Добавляем импорты дизайн-системы, если используются её функции
  if (content.includes('getColor(') && !content.includes('import.*useTheme')) {
    // Добавляем импорт useTheme
    const importMatch = content.match(/import.*from.*react/i);
    if (importMatch) {
      const insertAfter = importMatch[0];
      const themeImport = 'import { useTheme } from \'../../../contexts/ThemeContext.jsx\';';
      content = content.replace(insertAfter, insertAfter + '\n' + themeImport);
      modified = true;
    }
  }

  if (modified) {
    fs.writeFileSync(filePath, content, 'utf8');
    logger.log(`✅ Успешно мигрирован: ${filePath}`);
  } else {
    logger.log(`⚠️  Нет изменений: ${filePath}`);
  }

  return modified;
}

/**
 * Создает резервные копии файлов
 */
function createBackup(filePath) {
  const backupPath = filePath + '.backup';
  if (!fs.existsSync(backupPath)) {
    fs.copyFileSync(filePath, backupPath);
    logger.log(`📦 Создана резервная копия: ${backupPath}`);
  }
}

/**
 * Основная функция миграции
 */
function runMigration() {
  logger.log('🚀 Запуск миграции дизайн-системы...\n');

  // Находим все файлы для миграции
  const filesToMigrate = findFiles(path.join(__dirname, '../../src')).filter(shouldMigrateFile);

  logger.log(`📋 Найдено файлов для миграции: ${filesToMigrate.length}\n`);

  let migratedCount = 0;
  let errorCount = 0;

  for (const filePath of filesToMigrate) {
    try {
      // Создаем резервную копию
      createBackup(filePath);

      // Мигрируем файл
      if (migrateFile(filePath)) {
        migratedCount++;
      }
    } catch (error) {
      logger.error(`❌ Ошибка миграции ${filePath}:`, error.message);
      errorCount++;
    }
  }

  // Выводим статистику
  logger.log('\n📊 Статистика миграции:');
  logger.log(`✅ Успешно мигрировано: ${migratedCount}`);
  logger.log(`❌ Ошибок: ${errorCount}`);
  logger.log(`📦 Резервных копий создано: ${filesToMigrate.length}`);

  if (migratedCount > 0) {
    logger.log('\n🎉 Миграция завершена! Не забудьте:');
    logger.log('1. Протестировать обновленные компоненты');
    logger.log('2. Проверить визуальное соответствие');
    logger.log('3. Запустить линтер для проверки ошибок');
  }
}

// Запускаем миграцию
runMigration();
