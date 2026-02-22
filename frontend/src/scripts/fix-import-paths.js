#!/usr/bin/env node

/**
 * Скрипт для исправления путей импортов после миграции
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

import logger from '../utils/logger';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Функция для рекурсивного поиска файлов
function findFiles(dir, extension = '.jsx') {
  let results = [];
  const list = fs.readdirSync(dir);
  
  list.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);
    
    if (stat && stat.isDirectory()) {
      if (!['node_modules', '.git', 'dist', 'build'].includes(file)) {
        results = results.concat(findFiles(filePath, extension));
      }
    } else if (file.endsWith(extension)) {
      results.push(filePath);
    }
  });
  
  return results;
}

// Функция для исправления путей в файле
function fixImportPaths(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    let changed = false;
    
    // Определяем правильный путь на основе расположения файла
    const relativePath = path.relative(path.join(__dirname, '../'), filePath);
    const depth = relativePath.split(path.sep).length - 1;
    
    let correctPath;
    if (depth === 1) {
      // Файлы в src/ -> components/ui/native
      correctPath = 'components/ui/native';
    } else if (depth === 2) {
      // Файлы в src/pages/, src/components/ -> ../components/ui/native
      correctPath = '../components/ui/native';
    } else if (depth === 3) {
      // Файлы в src/components/admin/ -> ../../components/ui/native
      correctPath = '../../components/ui/native';
    } else {
      // Для более глубокой вложенности
      const upLevels = '../'.repeat(depth - 1);
      correctPath = `${upLevels}components/ui/native`;
    }
    
    // Исправляем импорты
    const patterns = [
      /from\s+['"]\.\.\/ui\/native['"]/g,
      /from\s+['"]\.\.\/\.\.\/ui\/native['"]/g,
      /from\s+['"]\.\.\/\.\.\/\.\.\/ui\/native['"]/g,
    ];
    
    patterns.forEach(pattern => {
      if (pattern.test(content)) {
        content = content.replace(pattern, `from '${correctPath}'`);
        changed = true;
      }
    });
    
    if (changed) {
      fs.writeFileSync(filePath, content, 'utf8');
      logger.log(`✅ Fixed paths in: ${filePath}`);
      return true;
    }
    
    return false;
  } catch (error) {
    logger.error(`❌ Error fixing ${filePath}:`, error.message);
    return false;
  }
}

// Основная функция
function main() {
  logger.log('🔧 Fixing import paths...\n');
  
  const srcDir = path.join(__dirname, '../');
  const files = findFiles(srcDir, '.jsx').concat(findFiles(srcDir, '.js'));
  
  let fixedCount = 0;
  let totalFiles = 0;
  
  files.forEach(file => {
    // Пропускаем файлы дизайн-системы и нативных компонентов
    if (file.includes('/design-system/') || file.includes('/ui/native/')) {
      return;
    }
    
    totalFiles++;
    if (fixImportPaths(file)) {
      fixedCount++;
    }
  });
  
  logger.log('\n📊 Path Fix Summary:');
  logger.log(`   Total files checked: ${totalFiles}`);
  logger.log(`   Files fixed: ${fixedCount}`);
  logger.log(`   Files unchanged: ${totalFiles - fixedCount}`);
  
  if (fixedCount > 0) {
    logger.log('\n✨ Path fixes completed successfully!');
  } else {
    logger.log('\n💡 No files needed path fixes.');
  }
}

// Запуск скрипта
const currentFile = fileURLToPath(import.meta.url);
const scriptFile = process.argv[1];

if (currentFile === scriptFile) {
  main();
}

export { fixImportPaths, findFiles };


