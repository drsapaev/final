#!/usr/bin/env node

/**
 * Скрипт для поиска и исправления CSS конфликтов после миграции дизайн-системы
 * Ищет конфликты между shorthand и non-shorthand CSS свойствами
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Конфликтующие пары CSS свойств
const CSS_CONFLICTS = [
  {
    shorthand: 'border',
    longhand: ['borderTop', 'borderRight', 'borderBottom', 'borderLeft', 'borderWidth', 'borderStyle', 'borderColor']
  },
  {
    shorthand: 'margin',
    longhand: ['marginTop', 'marginRight', 'marginBottom', 'marginLeft']
  },
  {
    shorthand: 'padding',
    longhand: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft']
  },
  {
    shorthand: 'background',
    longhand: ['backgroundColor', 'backgroundImage', 'backgroundRepeat', 'backgroundPosition', 'backgroundSize']
  },
  {
    shorthand: 'font',
    longhand: ['fontSize', 'fontWeight', 'fontFamily', 'fontStyle', 'lineHeight']
  },
  {
    shorthand: 'borderRadius',
    longhand: ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomLeftRadius', 'borderBottomRightRadius']
  }
];

// Счетчики
let filesScanned = 0;
let conflictsFound = 0;
let conflictsFixed = 0;

/**
 * Проверить файл на CSS конфликты
 */
function checkFileForConflicts(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.split('\n');
    const conflicts = [];

    // Поиск style объектов в JSX
    const styleRegex = /style\s*=\s*\{\{([^}]+)\}\}/g;
    let match;

    while ((match = styleRegex.exec(content)) !== null) {
      const styleContent = match[1];
      const styleLines = styleContent.split(',');
      
      // Проверяем каждую пару конфликтов
      CSS_CONFLICTS.forEach(conflict => {
        const hasShorthand = styleLines.some(line => 
          line.trim().startsWith(conflict.shorthand + ':')
        );
        
        const hasLonghand = conflict.longhand.some(prop =>
          styleLines.some(line => line.trim().startsWith(prop + ':'))
        );

        if (hasShorthand && hasLonghand) {
          conflicts.push({
            type: 'style_object',
            shorthand: conflict.shorthand,
            longhand: conflict.longhand.filter(prop =>
              styleLines.some(line => line.trim().startsWith(prop + ':'))
            ),
            match: match[0],
            position: match.index
          });
        }
      });
    }

    // Поиск CSS-in-JS объектов
    const cssObjectRegex = /\{\s*([^}]*(?:border|margin|padding|background|font)[^}]*)\s*\}/g;
    while ((match = cssObjectRegex.exec(content)) !== null) {
      const cssContent = match[1];
      
      CSS_CONFLICTS.forEach(conflict => {
        const hasShorthand = new RegExp(`\\b${conflict.shorthand}\\s*:`).test(cssContent);
        const hasLonghand = conflict.longhand.some(prop =>
          new RegExp(`\\b${prop}\\s*:`).test(cssContent)
        );

        if (hasShorthand && hasLonghand) {
          conflicts.push({
            type: 'css_object',
            shorthand: conflict.shorthand,
            longhand: conflict.longhand.filter(prop =>
              new RegExp(`\\b${prop}\\s*:`).test(cssContent)
            ),
            match: match[0],
            position: match.index
          });
        }
      });
    }

    return conflicts;
  } catch (error) {
    console.error(`Ошибка чтения файла ${filePath}:`, error.message);
    return [];
  }
}

/**
 * Исправить конфликты в файле
 */
function fixConflictsInFile(filePath, conflicts) {
  if (conflicts.length === 0) return false;

  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let fixed = 0;

    // Сортируем конфликты по позиции (с конца, чтобы не сбить индексы)
    conflicts.sort((a, b) => b.position - a.position);

    conflicts.forEach(conflict => {
      if (conflict.shorthand === 'border' && conflict.longhand.includes('borderBottom')) {
        // Специальная обработка для border/borderBottom конфликта
        const beforeMatch = content.substring(0, conflict.position);
        const afterMatch = content.substring(conflict.position + conflict.match.length);
        
        // Заменяем border на отдельные свойства
        let fixedMatch = conflict.match.replace(
          /border\s*:\s*([^,}]+)/g,
          (match, value) => {
            if (value.includes('none') || value.includes('transparent')) {
              return `borderTop: ${value}, borderLeft: ${value}, borderRight: ${value}`;
            } else {
              return `borderTop: ${value}, borderLeft: ${value}, borderRight: ${value}`;
            }
          }
        );

        content = beforeMatch + fixedMatch + afterMatch;
        fixed++;
      }
    });

    if (fixed > 0) {
      fs.writeFileSync(filePath, content, 'utf8');
      return true;
    }

    return false;
  } catch (error) {
    console.error(`Ошибка исправления файла ${filePath}:`, error.message);
    return false;
  }
}

/**
 * Сканировать директорию рекурсивно
 */
function scanDirectory(dirPath, extensions = ['.jsx', '.js', '.tsx', '.ts']) {
  const results = [];

  try {
    const items = fs.readdirSync(dirPath);

    items.forEach(item => {
      const itemPath = path.join(dirPath, item);
      const stat = fs.statSync(itemPath);

      if (stat.isDirectory()) {
        // Пропускаем node_modules и другие служебные папки
        if (!['node_modules', '.git', 'dist', 'build', '.next'].includes(item)) {
          results.push(...scanDirectory(itemPath, extensions));
        }
      } else if (stat.isFile()) {
        const ext = path.extname(item);
        if (extensions.includes(ext)) {
          results.push(itemPath);
        }
      }
    });
  } catch (error) {
    console.error(`Ошибка сканирования директории ${dirPath}:`, error.message);
  }

  return results;
}

/**
 * Главная функция
 */
function main() {
  console.log('🔍 Поиск CSS конфликтов после миграции дизайн-системы...\n');

  const srcPath = path.join(__dirname, 'src');
  const files = scanDirectory(srcPath);

  console.log(`📁 Найдено ${files.length} файлов для проверки\n`);

  const problemFiles = [];

  files.forEach(filePath => {
    filesScanned++;
    const conflicts = checkFileForConflicts(filePath);
    
    if (conflicts.length > 0) {
      conflictsFound += conflicts.length;
      problemFiles.push({ filePath, conflicts });
      
      console.log(`⚠️  ${path.relative(__dirname, filePath)}`);
      conflicts.forEach(conflict => {
        console.log(`   - ${conflict.shorthand} конфликтует с ${conflict.longhand.join(', ')}`);
      });
      console.log();
    }
  });

  if (problemFiles.length === 0) {
    console.log('✅ CSS конфликтов не найдено!');
    return;
  }

  console.log(`\n📊 Статистика:`);
  console.log(`   Файлов проверено: ${filesScanned}`);
  console.log(`   Файлов с конфликтами: ${problemFiles.length}`);
  console.log(`   Всего конфликтов: ${conflictsFound}`);

  // Предлагаем исправить
  console.log(`\n🔧 Исправляем конфликты...`);

  problemFiles.forEach(({ filePath, conflicts }) => {
    const fixed = fixConflictsInFile(filePath, conflicts);
    if (fixed) {
      conflictsFixed += conflicts.length;
      console.log(`✅ Исправлен: ${path.relative(__dirname, filePath)}`);
    } else {
      console.log(`❌ Не удалось исправить: ${path.relative(__dirname, filePath)}`);
    }
  });

  console.log(`\n🎉 Исправление завершено:`);
  console.log(`   Конфликтов исправлено: ${conflictsFixed}/${conflictsFound}`);
  
  if (conflictsFixed < conflictsFound) {
    console.log(`\n⚠️  Некоторые конфликты требуют ручного исправления`);
  }
}

// Запуск скрипта
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}


