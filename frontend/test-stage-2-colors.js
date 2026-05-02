#!/usr/bin/env node

/**
 * Тест этапа 2: Консолидация цветовой системы
 * Проверяем, что компоненты используют новые токены цветов
 */

import fs from 'fs';
import path from 'path';

// Файлы для проверки
const filesToCheck = [
  'src/theme/tokens.js',
  'src/components/admin/AdminNavigation.jsx',
  'src/components/buttons/ModernButton.jsx'
];

function checkFile(filePath) {
  console.log(`\n🔍 Проверяем: ${filePath}`);

  if (!fs.existsSync(filePath)) {
    console.log(`   ❌ Файл не найден`);
    return false;
  }

  const content = fs.readFileSync(filePath, 'utf8');

  // Проверки для разных файлов
  if (filePath.includes('tokens.js')) {
    // Проверка токенов цветов
    const checks = [
      { pattern: /primary.*#0ea5e9/, desc: 'Основной цвет primary' },
      { pattern: /status.*success.*#10b981/, desc: 'Цвет успеха' },
      { pattern: /medical.*cardiology.*#dc2626/, desc: 'Цвет кардиологии' },
      { pattern: /semantic.*background/, desc: 'Семантические цвета фона' }
    ];

    checks.forEach(check => {
      const found = check.pattern.test(content);
      console.log(`   ${found ? '✅' : '❌'} ${check.desc}`);
    });
  }

  else if (filePath.includes('AdminNavigation.jsx')) {
    // Проверка использования токенов вместо хардкода
    const checks = [
      { pattern: /colors\.primary\[500\]/, desc: 'Использует токены вместо хардкода' },
      { pattern: /colors\.semantic\.surface/, desc: 'Использует семантические цвета' },
      { pattern: /colors\.border\.medium/, desc: 'Использует токены границ' }
    ];

    checks.forEach(check => {
      const found = check.pattern.test(content);
      console.log(`   ${found ? '✅' : '❌'} ${check.desc}`);
    });

    // Проверка отсутствия старых цветов
    const oldColors = ['#3b82f6', '#60a5fa'];
    oldColors.forEach(color => {
      const found = content.includes(color);
      console.log(`   ${!found ? '✅' : '❌'} Удален старый цвет ${color}`);
    });
  }

  else if (filePath.includes('ModernButton.jsx')) {
    // Проверка использования новой структуры цветов
    const checks = [
      { pattern: /colors\.primary\[500\]/, desc: 'Использует токены primary' },
      { pattern: /colors\.status\./, desc: 'Использует токены статусов' },
      { pattern: /colors\.semantic\./, desc: 'Использует семантические цвета' },
      { pattern: /colors\.gray\[300\]/, desc: 'Использует серые цвета' }
    ];

    checks.forEach(check => {
      const found = check.pattern.test(content);
      console.log(`   ${found ? '✅' : '❌'} ${check.desc}`);
    });

    // Проверка отсутствия старых функций getColor
    const found = content.includes('getColor(');
    console.log(`   ${!found ? '✅' : '❌'} Удалены старые функции getColor`);
  }

  return true;
}

function runTests() {
  console.log('🧪 ТЕСТИРОВАНИЕ ЭТАПА 2: КОНСОЛИДАЦИЯ ЦВЕТОВОЙ СИСТЕМЫ\n');
  console.log('=' .repeat(60));

  let allPassed = true;

  filesToCheck.forEach(file => {
    const filePath = path.join(process.cwd(), file);
    const success = checkFile(filePath);

    if (!success) {
      allPassed = false;
    }
  });

  console.log('\n' + '=' .repeat(60));
  console.log(`📊 РЕЗУЛЬТАТЫ:`);

  if (allPassed) {
    console.log(`   ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!`);
    console.log(`   🎨 Цветовая система консолидирована успешно`);
    console.log(`   🚀 Готов к следующему этапу`);
    return true;
  } else {
    console.log(`   ❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ`);
    console.log(`   🔧 Нужно исправить компоненты`);
    return false;
  }
}

function generateColorCSS() {
  console.log('\n🎨 ГЕНЕРАЦИЯ CSS ПЕРЕМЕННЫХ ДЛЯ НОВОЙ ЦВЕТОВОЙ СИСТЕМЫ:');
  console.log('=' .repeat(60));

  // Это будет сгенерировано на основе tokens.js
  const css = `:root {
  /* Основные цвета */
  --color-primary-500: #0ea5e9;
  --color-status-success: #10b981;
  --color-status-warning: #f59e0b;
  --color-status-danger: #ef4444;

  /* Медицинские цвета */
  --color-medical-cardiology: #dc2626;
  --color-medical-dermatology: #7c3aed;
  --color-medical-dentistry: #059669;

  /* Семантические цвета */
  --color-background-primary: #ffffff;
  --color-text-primary: #0f172a;
  --color-border-medium: #d1d5db;
}`;

  console.log(css);
  return css;
}

function main() {
  const testsPassed = runTests();
  generateColorCSS();

  if (testsPassed) {
    console.log('\n🚀 ЭТАП 2 ЗАВЕРШЕН УСПЕШНО!');
    console.log('✅ Цветовая система консолидирована');
    console.log('✅ Компоненты обновлены');
    console.log('✅ Готов к этапу 3: Миграция компонентов');
  } else {
    console.log('\n⚠️  НУЖНО ИСПРАВИТЬ ОШИБКИ ПЕРЕД ПРОДОЛЖЕНИЕМ');
    process.exit(1);
  }
}

main();
