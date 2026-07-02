#!/usr/bin/env node
/**
 * Скрипт для автоматической замены console на logger
 * Часть задачи 1.3: Remove medical data logging
 *
 * HIPAA Compliance: Заменяет console.log на безопасный logger с PHI санитизацией
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const srcDir = path.join(__dirname, '../src');
const excludeDirs = ['node_modules', 'dist', 'build', '.git'];
const fileExtensions = ['.js', '.jsx', '.ts', '.tsx'];

let filesProcessed = 0;
let consolesReplaced = 0;

/**
 * Проверка, нужно ли обработать файл
 */
function shouldProcessFile(filePath) {
  const ext = path.extname(filePath);
  if (!fileExtensions.includes(ext)) return false;

  // Исключаем уже обработанные файлы
  const excludeFiles = ['logger.js', 'fix-console-logs.js'];
  const filename = path.basename(filePath);
  if (excludeFiles.includes(filename)) return false;

  return true;
}

/**
 * Обработка одного файла
 */
function processFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const originalContent = content;

    // Проверяем, есть ли в файле console
    if (!content.includes('console.')) {
      return; // Файл не содержит console
    }

    // Проверяем, импортирован ли уже logger
    const hasLoggerImport = content.includes("import logger from") ||
                           content.includes('import { logger }') ||
                           content.includes('import logger,');

    // Определяем стиль импорта (относительный путь зависит от глубины вложенности)
    const depth = filePath.split(path.sep).filter(p => p === 'src').length > 0
      ? filePath.split(path.sep).slice(filePath.split(path.sep).indexOf('src') + 1).length
      : 0;

    const importPath = '../'.repeat(depth) + (depth === 0 ? './' : '') + 'utils/logger';

    // Добавляем импорт logger если его нет
    if (!hasLoggerImport) {
      // Находим последний импорт
      const importRegex = /import\s+.*?from\s+['"][^'"]+['"];?\s*\n/g;
      const imports = content.match(importRegex);

      if (imports && imports.length > 0) {
        const lastImport = imports[imports.length - 1];
        const lastImportIndex = content.lastIndexOf(lastImport);
        const insertPosition = lastImportIndex + lastImport.length;

        content = content.slice(0, insertPosition) +
                 `import logger from '${importPath}';\n` +
                 content.slice(insertPosition);
      } else {
        // Если нет импортов, добавляем в начало файла
        content = `import logger from '${importPath}';\n\n` + content;
      }
    }

    // Заменяем console на logger
    const consolePatterns = [
      { from: /console\.log\(/g, to: 'logger.log(' },
      { from: /console\.info\(/g, to: 'logger.info(' },
      { from: /console\.warn\(/g, to: 'logger.warn(' },
      { from: /console\.error\(/g, to: 'logger.error(' },
      { from: /console\.debug\(/g, to: 'logger.debug(' },
      { from: /console\.table\(/g, to: 'logger.table(' },
      { from: /console\.group\(/g, to: 'logger.group(' },
      { from: /console\.groupEnd\(/g, to: 'logger.groupEnd(' },
      { from: /console\.time\(/g, to: 'logger.time(' },
      { from: /console\.timeEnd\(/g, to: 'logger.timeEnd(' },
    ];

    let replacements = 0;
    consolePatterns.forEach(({ from, to }) => {
      const matches = content.match(from);
      if (matches) {
        replacements += matches.length;
        content = content.replace(from, to);
      }
    });

    // Записываем только если были изменения
    if (content !== originalContent) {
      fs.writeFileSync(filePath, content, 'utf8');
      filesProcessed++;
      consolesReplaced += replacements;
      console.log(`✅ ${path.relative(srcDir, filePath)} - заменено: ${replacements}`);
    }

  } catch (error) {
    console.error(`❌ Ошибка обработки ${filePath}:`, error.message);
  }
}

/**
 * Рекурсивный обход директории
 */
function walkDir(dir) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      if (!excludeDirs.includes(file)) {
        walkDir(filePath);
      }
    } else if (stat.isFile()) {
      if (shouldProcessFile(filePath)) {
        processFile(filePath);
      }
    }
  });
}

// Запуск скрипта
console.log('🔍 Начинаем поиск и замену console.log на logger...\n');
console.log(`📂 Директория: ${srcDir}\n`);

walkDir(srcDir);

console.log('\n✨ Готово!');
console.log(`📊 Статистика:`);
console.log(`   - Обработано файлов: ${filesProcessed}`);
console.log(`   - Заменено console.*: ${consolesReplaced}`);

if (consolesReplaced > 0) {
  console.log('\n⚠️  Не забудьте проверить изменения перед коммитом!');
  console.log('   Запустите: npm run lint для проверки');
}
