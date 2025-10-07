#!/usr/bin/env node

/**
 * Тест консолидации цветовой системы
 * Проверяет, что новая цветовая палитра работает корректно
 */

import { colors, medical } from './src/theme/tokens.js';

// Тестовые данные для проверки цветов
const testCases = [
  // Проверка основных цветов
  { name: 'Primary 500', color: colors.primary[500], expected: '#0ea5e9' },
  { name: 'Success', color: colors.status.success, expected: '#10b981' },
  { name: 'Warning', color: colors.status.warning, expected: '#f59e0b' },
  { name: 'Danger', color: colors.status.danger, expected: '#ef4444' },

  // Проверка медицинских цветов
  { name: 'Cardiology', color: colors.medical.cardiology, expected: '#dc2626' },
  { name: 'Dermatology', color: colors.medical.dermatology, expected: '#7c3aed' },
  { name: 'Dentistry', color: colors.medical.dentistry, expected: '#059669' },

  // Проверка статусов пациентов
  { name: 'Patient waiting', color: medical.patientStatus.waiting, expected: '#f59e0b' },
  { name: 'Patient completed', color: medical.patientStatus.completed, expected: '#10b981' },
  { name: 'Patient emergency', color: medical.patientStatus.emergency, expected: '#ef4444' },

  // Проверка приоритетов
  { name: 'Priority normal', color: medical.priority.normal, expected: '#3b82f6' },
  { name: 'Priority high', color: medical.priority.high, expected: '#f59e0b' },
  { name: 'Priority urgent', color: medical.priority.urgent, expected: '#ef4444' },

  // Проверка отделений
  { name: 'Department cardiology', color: medical.departments.cardiology, expected: '#dc2626' },
  { name: 'Department dermatology', color: medical.departments.dermatology, expected: '#7c3aed' },
  { name: 'Department general', color: medical.departments.general, expected: '#0ea5e9' }
];

function runTests() {
  console.log('🧪 ТЕСТИРОВАНИЕ КОНСОЛИДАЦИИ ЦВЕТОВОЙ СИСТЕМЫ\n');
  console.log('=' .repeat(60));

  let passed = 0;
  let failed = 0;

  testCases.forEach((test, index) => {
    const success = test.color === test.expected;
    const status = success ? '✅' : '❌';

    console.log(`${status} Тест ${index + 1}: ${test.name}`);
    console.log(`   Ожидаемый: ${test.expected}`);
    console.log(`   Полученный: ${test.color}`);
    console.log(`   Результат: ${success ? 'ПРОЙДЕН' : 'ПРОВАЛЕН'}`);

    if (success) {
      passed++;
    } else {
      failed++;
      console.log(`   ❌ НЕ СОВПАДАЕТ!`);
    }

    console.log('');
  });

  console.log('=' .repeat(60));
  console.log(`📊 РЕЗУЛЬТАТЫ:`);
  console.log(`   ✅ Пройдено: ${passed}`);
  console.log(`   ❌ Провалено: ${failed}`);
  console.log(`   📈 Успешность: ${((passed / testCases.length) * 100).toFixed(1)}%`);

  if (failed === 0) {
    console.log('\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Цветовая система консолидирована успешно.');
    return true;
  } else {
    console.log(`\n⚠️  ОБНАРУЖЕНО ${failed} ПРОБЛЕМ. Нужно исправить цвета.`);
    return false;
  }
}

// Функция для генерации CSS переменных
function generateCSSVariables() {
  console.log('\n🎨 ГЕНЕРАЦИЯ CSS ПЕРЕМЕННЫХ:');
  console.log('=' .repeat(60));

  const cssVars = [];

  // Основные цвета
  Object.entries(colors.primary).forEach(([key, value]) => {
    cssVars.push(`  --color-primary-${key}: ${value};`);
  });

  // Статусные цвета
  Object.entries(colors.status).forEach(([key, value]) => {
    cssVars.push(`  --color-status-${key}: ${value};`);
  });

  // Медицинские цвета
  Object.entries(colors.medical).forEach(([key, value]) => {
    cssVars.push(`  --color-medical-${key}: ${value};`);
  });

  // Семантические цвета
  Object.entries(colors.semantic.background).forEach(([key, value]) => {
    cssVars.push(`  --color-background-${key}: ${value};`);
  });

  Object.entries(colors.semantic.text).forEach(([key, value]) => {
    cssVars.push(`  --color-text-${key}: ${value};`);
  });

  console.log(':root {');
  cssVars.forEach(cssVar => console.log(cssVar));
  console.log('}');

  return cssVars;
}

function main() {
  const testsPassed = runTests();
  generateCSSVariables();

  if (testsPassed) {
    console.log('\n🚀 ГОТОВО К СЛЕДУЮЩЕМУ ЭТАПУ!');
  } else {
    console.log('\n🔧 НУЖНО ИСПРАВИТЬ ОШИБКИ ПЕРЕД ПРОДОЛЖЕНИЕМ.');
    process.exit(1);
  }
}

main();
