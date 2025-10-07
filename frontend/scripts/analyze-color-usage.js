#!/usr/bin/env node

/**
 * Анализатор использования цветов в проекте
 * Помогает выявить конфликты между цветовыми системами
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Цвета из разных систем
const colorSystems = {
  'design-system': {
    primary: '#2196f3',
    success: '#4caf50',
    warning: '#ffc107',
    danger: '#f44336',
    cardiology: '#e91e63'
  },
  'main-theme': {
    primary: '#0ea5e9',
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    cardiology: '#dc2626'
  }
};

// Функция поиска цветов в файлах
function findColorsInFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const results = {};

  Object.entries(colorSystems).forEach(([system, colors]) => {
    Object.entries(colors).forEach(([colorName, colorValue]) => {
      const regex = new RegExp(colorValue, 'g');
      const matches = content.match(regex);

      if (matches) {
        if (!results[colorValue]) {
          results[colorValue] = {
            count: 0,
            files: [],
            systems: []
          };
        }

        results[colorValue].count += matches.length;
        results[colorValue].files.push(filePath);
        results[colorValue].systems.push(system);
      }
    });
  });

  return results;
}

// Анализ всех файлов в директории
function analyzeDirectory(dirPath) {
  const results = {};

  function walkDir(currentPath) {
    const files = fs.readdirSync(currentPath);

    files.forEach(file => {
      const filePath = path.join(currentPath, file);
      const stat = fs.statSync(filePath);

      if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
        walkDir(filePath);
      } else if (stat.isFile() && (file.endsWith('.jsx') || file.endsWith('.js') || file.endsWith('.css'))) {
        const fileResults = findColorsInFile(filePath);

        Object.entries(fileResults).forEach(([color, data]) => {
          if (!results[color]) {
            results[color] = {
              count: 0,
              files: [],
              systems: []
            };
          }

          results[color].count += data.count;
          results[color].files.push(...data.files);
          results[color].systems.push(...data.systems);
        });
      }
    });
  }

  walkDir(dirPath);
  return results;
}

// Генерация отчета
function generateReport(results) {
  console.log('🎨 АНАЛИЗ ИСПОЛЬЗОВАНИЯ ЦВЕТОВ В ПРОЕКТЕ\n');
  console.log('=' .repeat(60));

  Object.entries(results).forEach(([color, data]) => {
    const uniqueFiles = [...new Set(data.files)];
    const uniqueSystems = [...new Set(data.systems)];

    console.log(`\n🔍 Цвет: ${color}`);
    console.log(`   Использований: ${data.count}`);
    console.log(`   Файлов: ${uniqueFiles.length}`);
    console.log(`   Систем: ${uniqueSystems.join(', ')}`);

    if (uniqueFiles.length <= 5) {
      console.log(`   Файлы: ${uniqueFiles.join(', ')}`);
    } else {
      console.log(`   Первые 5 файлов: ${uniqueFiles.slice(0, 5).join(', ')}...`);
    }

    // Рекомендации по замене
    if (uniqueSystems.length > 1) {
      console.log(`   ⚠️  КОНФЛИКТ: Используется в ${uniqueSystems.length} системах`);
    }
  });

  console.log('\n' + '=' .repeat(60));
  console.log('📊 СТАТИСТИКА КОНФЛИКТОВ:');

  const conflicts = Object.values(results).filter(r => r.systems.length > 1);
  console.log(`   Цветов с конфликтами: ${conflicts.length}`);
  console.log(`   Общее количество конфликтов: ${conflicts.reduce((sum, c) => sum + c.systems.length, 0)}`);
}

// Основная функция
function main() {
  const frontendPath = path.join(__dirname, '..', 'src');

  if (!fs.existsSync(frontendPath)) {
    console.error('❌ Директория frontend/src не найдена');
    return;
  }

  console.log('🔍 Анализирую использование цветов...');
  const results = analyzeDirectory(frontendPath);

  generateReport(results);

  // Сохранить результаты в файл
  const reportPath = path.join(__dirname, '..', 'color-usage-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
  console.log(`\n💾 Детальный отчет сохранен в: ${reportPath}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { analyzeDirectory, findColorsInFile };
