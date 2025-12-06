#!/usr/bin/env node
/**
 * Исправление неправильных путей к logger.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const srcDir = path.join(__dirname, '../src');

let fixed = 0;

function getCorrectLoggerPath(filePath) {
  // Получаем относительный путь от src
  const relativePath = path.relative(srcDir, filePath);
  const depth = relativePath.split(path.sep).length - 1;

  if (depth === 0) {
    return './utils/logger';
  }

  return '../'.repeat(depth) + 'utils/logger';
}

function fixFile(filePath) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const original = content;

    // Находим импорт logger
    const loggerImportRegex = /import logger from ['"]([^'"]+\/utils\/logger)['"]/;
    const match = content.match(loggerImportRegex);

    if (match) {
      const correctPath = getCorrectLoggerPath(filePath);
      const oldImport = match[0];
      const newImport = `import logger from '${correctPath}'`;

      if (oldImport !== newImport) {
        content = content.replace(oldImport, newImport);
        fs.writeFileSync(filePath, content, 'utf8');
        fixed++;
        console.log(`✅ ${path.relative(srcDir, filePath)}: ${match[1]} → ${correctPath}`);
      }
    }
  } catch (error) {
    console.error(`❌ Error fixing ${filePath}:`, error.message);
  }
}

function walkDir(dir) {
  const files = fs.readdirSync(dir);

  files.forEach(file => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory() && file !== 'node_modules' && file !== 'dist') {
      walkDir(filePath);
    } else if (stat.isFile() && (file.endsWith('.js') || file.endsWith('.jsx'))) {
      fixFile(filePath);
    }
  });
}

console.log('🔧 Исправление импортов logger...\n');
walkDir(srcDir);
console.log(`\n✨ Исправлено файлов: ${fixed}`);
