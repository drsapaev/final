#!/usr/bin/env node

/**
 * Массовый поиск и замена цветов во всем проекте
 * Заменяет старые цвета на новые токены цветов
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Старые цвета для замены
const oldColors = {
  // Старые цвета из дизайна-системы
  '#2196f3': 'colors.primary[500]',      // Старый primary синий
  '#4caf50': 'colors.status.success',    // Старый success зеленый
  '#ffc107': 'colors.status.warning',    // Старый warning желтый
  '#f44336': 'colors.status.danger',     // Старый danger красный
  '#e91e63': 'colors.medical.cardiology', // Старый кардиология розовый
  '#9c27b0': 'colors.medical.dermatology', // Старый дерматология фиолетовый

  // Старые цвета из LoginFormStyled.jsx
  '#667eea': 'colors.primary[500]',      // Старый градиент синий
  '#764ba2': 'colors.primary[700]',      // Старый градиент фиолетовый
  '#333': 'colors.semantic.text.primary', // Старый темный текст
  '#666': 'colors.semantic.text.secondary', // Старый серый текст
};

// Файлы для исключения из обработки
const excludePatterns = [
  'node_modules/**',
  'dist/**',
  'build/**',
  '*.min.js',
  '*.min.css',
  'package-lock.json',
  'yarn.lock',
  '.git/**'
];

// Функция для проверки, нужно ли исключить файл
function shouldExclude(filePath) {
  return excludePatterns.some(pattern => {
    const regex = new RegExp(pattern.replace(/\*\*/g, '.*').replace(/\*/g, '[^/]*'));
    return regex.test(filePath);
  });
}

// Функция для поиска и замены цветов в файле
function processFile(filePath) {
  if (shouldExclude(filePath)) {
    return { changed: false, errors: [] };
  }

  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let changed = false;
    const errors = [];

    // Заменяем цвета
    Object.entries(oldColors).forEach(([oldColor, newColor]) => {
      // Ищем точные совпадения цвета (не части слов)
      const regex = new RegExp(`\\b${oldColor.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g');

      if (regex.test(content)) {
        content = content.replace(regex, newColor);
        changed = true;
        console.log(`  ✓ ${filePath}: ${oldColor} → ${newColor}`);
      }
    });

    // Сохраняем файл если были изменения
    if (changed) {
      fs.writeFileSync(filePath, content, 'utf8');
    }

    return { changed, errors };
  } catch (error) {
    return { changed: false, errors: [error.message] };
  }
}

// Рекурсивный обход директории
function processDirectory(dirPath) {
  const results = {
    filesProcessed: 0,
    filesChanged: 0,
    errors: []
  };

  function walkDir(currentPath) {
    const files = fs.readdirSync(currentPath);

    files.forEach(file => {
      const filePath = path.join(currentPath, file);
      const stat = fs.statSync(filePath);

      if (stat.isDirectory() && !shouldExclude(filePath)) {
        walkDir(filePath);
      } else if (stat.isFile() && !shouldExclude(filePath)) {
        results.filesProcessed++;

        const { changed, errors } = processFile(filePath);
        if (changed) {
          results.filesChanged++;
        }
        results.errors.push(...errors);
      }
    });
  }

  walkDir(dirPath);
  return results;
}

// Основная функция
function main() {
  const projectRoot = path.join(__dirname, '..');
  const srcDir = path.join(projectRoot, 'src');

  console.log('🔄 МАССОВАЯ ЗАМЕНА ЦВЕТОВ В ПРОЕКТЕ');
  console.log('=' .repeat(50));
  console.log(`📁 Рабочая директория: ${srcDir}`);
  console.log('');

  console.log('🎨 Цвета для замены:');
  Object.entries(oldColors).forEach(([oldColor, newColor]) => {
    console.log(`   ${oldColor} → ${newColor}`);
  });
  console.log('');

  const results = processDirectory(srcDir);

  console.log('=' .repeat(50));
  console.log('📊 РЕЗУЛЬТАТЫ:');
  console.log(`   Файлов обработано: ${results.filesProcessed}`);
  console.log(`   Файлов изменено: ${results.filesChanged}`);
  console.log(`   Ошибок: ${results.errors.length}`);

  if (results.errors.length > 0) {
    console.log('\n❌ ОШИБКИ:');
    results.errors.forEach(error => console.log(`   ${error}`));
  }

  console.log('\n✅ Массовая замена цветов завершена!');
  console.log('🚀 Готов к следующему этапу');
}

// Запуск скрипта
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}
