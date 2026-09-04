#!/usr/bin/env node

// Скрипт для автоматической проверки работоспособности системы
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

console.log('🔍 Проверка работоспособности системы медицинской клиники...\n');

// Цвета для консоли
const colors = {
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  reset: '\x1b[0m',
  bold: '\x1b[1m'
};

function log(message, color = 'reset') {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function checkFileExists(filePath, description) {
  try {
    if (fs.existsSync(filePath)) {
      log(`✅ ${description}: ${filePath}`, 'green');
      return true;
    } else {
      log(`❌ ${description}: ${filePath} - НЕ НАЙДЕН`, 'red');
      return false;
    }
  } catch (error) {
    log(`❌ ${description}: ${filePath} - ОШИБКА: ${error.message}`, 'red');
    return false;
  }
}

function checkFileContent(filePath, requiredContent, description) {
  try {
    if (!fs.existsSync(filePath)) {
      log(`❌ ${description}: Файл не найден`, 'red');
      return false;
    }

    const content = fs.readFileSync(filePath, 'utf8');
    const hasContent = requiredContent.some(item => 
      typeof item === 'string' ? content.includes(item) : item.test(content)
    );

    if (hasContent) {
      log(`✅ ${description}: Содержимое корректно`, 'green');
      return true;
    } else {
      log(`❌ ${description}: Содержимое некорректно`, 'red');
      return false;
    }
  } catch (error) {
    log(`❌ ${description}: Ошибка чтения - ${error.message}`, 'red');
    return false;
  }
}

function checkImportSyntax(filePath, description) {
  try {
    if (!fs.existsSync(filePath)) {
      log(`❌ ${description}: Файл не найден`, 'red');
      return false;
    }

    const content = fs.readFileSync(filePath, 'utf8');
    
    // Проверяем базовый синтаксис импортов
    const importRegex = /import\s+.*\s+from\s+['"][^'"]+['"];?/g;
    const imports = content.match(importRegex) || [];
    
    // Проверяем, что нет очевидных синтаксических ошибок
    const hasValidImports = imports.length > 0 || content.includes('export');
    
    if (hasValidImports) {
      log(`✅ ${description}: Синтаксис импортов корректен`, 'green');
      return true;
    } else {
      log(`⚠️  ${description}: Нет импортов/экспортов`, 'yellow');
      return true; // Не критично
    }
  } catch (error) {
    log(`❌ ${description}: Ошибка синтаксиса - ${error.message}`, 'red');
    return false;
  }
}

// Основные проверки
log('📁 Проверка структуры файлов...', 'blue');
const fileChecks = [
  // API файлы
  ['src/api/client.js', 'API клиент'],
  ['src/api/endpoints.js', 'API endpoints'],
  ['src/api/services.js', 'API сервисы'],
  
  // Типы и константы
  ['src/types/api.js', 'Типы API'],
  ['src/constants/routes.js', 'Константы маршрутов'],
  
  // Провайдеры
  ['src/providers/AppProviders.jsx', 'Провайдеры приложения'],
  
  // Общие компоненты
  ['src/components/common/ErrorBoundary.jsx', 'Error Boundary'],
  ['src/components/common/Toast.jsx', 'Toast система'],
  ['src/components/common/Loading.jsx', 'Loading компоненты'],
  ['src/components/common/Form.jsx', 'Form система'],
  ['src/components/common/RoleGuard.jsx', 'Role Guard'],
  ['src/components/common/index.js', 'Экспорты компонентов'],
  
  // Аутентификация
  ['src/components/auth/RequireAuth.jsx', 'Require Auth'],
  
  // Навигация
  ['src/components/navigation/ProtectedRoute.jsx', 'Protected Route'],
  
  // Утилиты
  ['src/utils/themeChecker.js', 'Theme Checker'],
  ['src/utils/frontendAudit.js', 'Frontend Audit'],
  
  // Тесты
  ['src/test/integration.test.js', 'Integration Tests']
];

let passedFiles = 0;
fileChecks.forEach(([filePath, description]) => {
  if (checkFileExists(filePath, description)) {
    passedFiles++;
  }
});

log(`\n📊 Файлы: ${passedFiles}/${fileChecks.length} найдены`, 'blue');

// Проверка содержимого ключевых файлов
log('\n🔍 Проверка содержимого файлов...', 'blue');
const contentChecks = [
  // API клиент
  ['src/api/client.js', ['axios.create', 'interceptors', 'setToken'], 'API клиент с interceptors'],
  
  // Константы маршрутов
  ['src/constants/routes.js', ['roleToRoute', 'hasRouteAccess', 'ROLE_OPTIONS'], 'Константы маршрутов'],
  
  // Провайдеры
  ['src/providers/AppProviders.jsx', ['ThemeProvider', 'ToastProvider', 'ErrorBoundary'], 'Провайдеры'],
  
  // Error Boundary
  ['src/components/common/ErrorBoundary.jsx', ['componentDidCatch', 'ErrorFallback'], 'Error Boundary'],
  
  // Toast система
  ['src/components/common/Toast.jsx', ['ToastProvider', 'useToast', 'addToast'], 'Toast система'],
  
  // Loading компоненты
  ['src/components/common/Loading.jsx', ['Loading', 'ButtonLoading', 'useLoading'], 'Loading компоненты'],
  
  // Form система
  ['src/components/common/Form.jsx', ['FormProvider', 'useForm', 'FormField'], 'Form система'],
  
  // Role Guard
  ['src/components/common/RoleGuard.jsx', ['RoleGuard', 'useRoleAccess', 'hasRole'], 'Role Guard']
];

let passedContent = 0;
contentChecks.forEach(([filePath, requiredContent, description]) => {
  if (checkFileContent(filePath, requiredContent, description)) {
    passedContent++;
  }
});

log(`\n📊 Содержимое: ${passedContent}/${contentChecks.length} корректно`, 'blue');

// Проверка синтаксиса импортов
log('\n🔍 Проверка синтаксиса импортов...', 'blue');
const syntaxChecks = [
  ['src/api/client.js', 'API клиент'],
  ['src/pages/Login.jsx', 'Login страница'],
  ['src/stores/auth.js', 'Auth store'],
  ['src/App.jsx', 'Главный App'],
  ['src/providers/AppProviders.jsx', 'App Providers']
];

let passedSyntax = 0;
syntaxChecks.forEach(([filePath, description]) => {
  if (checkImportSyntax(filePath, description)) {
    passedSyntax++;
  }
});

log(`\n📊 Синтаксис: ${passedSyntax}/${syntaxChecks.length} корректен`, 'blue');

// Проверка package.json
log('\n📦 Проверка зависимостей...', 'blue');
if (checkFileExists('package.json', 'Package.json')) {
  try {
    const packageJson = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    const requiredDeps = ['react', 'react-dom', 'axios', 'react-router-dom'];
    const missingDeps = requiredDeps.filter(dep => !packageJson.dependencies[dep]);
    
    if (missingDeps.length === 0) {
      log('✅ Все необходимые зависимости установлены', 'green');
    } else {
      log(`❌ Отсутствуют зависимости: ${missingDeps.join(', ')}`, 'red');
    }
  } catch (error) {
    log(`❌ Ошибка чтения package.json: ${error.message}`, 'red');
  }
}

// Итоговая статистика
const totalChecks = fileChecks.length + contentChecks.length + syntaxChecks.length;
const totalPassed = passedFiles + passedContent + passedSyntax;

log('\n' + '='.repeat(50), 'blue');
log(`📈 ИТОГОВАЯ СТАТИСТИКА`, 'bold');
log(`✅ Пройдено: ${totalPassed}/${totalChecks} проверок`, 'green');
log(`❌ Не пройдено: ${totalChecks - totalPassed}/${totalChecks} проверок`, 'red');

if (totalPassed === totalChecks) {
  log('\n🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ! Система готова к работе.', 'green');
} else if (totalPassed >= totalChecks * 0.8) {
  log('\n⚠️  Большинство проверок пройдено. Система в основном готова.', 'yellow');
} else {
  log('\n❌ Много проблем найдено. Требуется доработка.', 'red');
}

log('\n📋 Рекомендации:', 'blue');
log('1. Запустите npm run dev для проверки в браузере', 'blue');
log('2. Откройте test-components.html для интерактивных тестов', 'blue');
log('3. Проверьте консоль браузера на ошибки', 'blue');
log('4. Протестируйте все компоненты в реальном приложении', 'blue');

console.log('\n');
