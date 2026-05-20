#!/usr/bin/env node
/**
 * Скрипт анализа и оптимизации бандла
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

console.log('🔍 Анализ бандла приложения...\n');

// Функция для выполнения команд
function runCommand(command, description) {
  console.log(`📋 ${description}...`);
  try {
    const output = execSync(command, { 
      cwd: projectRoot, 
      encoding: 'utf8',
      stdio: 'pipe'
    });
    return output;
  } catch (error) {
    console.error(`❌ Ошибка: ${error.message}`);
    return null;
  }
}

// Функция для анализа размера файлов
function analyzeFileSize(filePath) {
  try {
    const stats = fs.statSync(filePath);
    const sizeInMB = (stats.size / 1024 / 1024).toFixed(2);
    return {
      size: stats.size,
      sizeFormatted: `${sizeInMB} MB`,
      exists: true
    };
  } catch {
    return { exists: false };
  }
}

// Функция для получения размера директории
function getDirectorySize(dirPath) {
  let totalSize = 0;
  
  try {
    const files = fs.readdirSync(dirPath, { withFileTypes: true });
    
    for (const file of files) {
      const fullPath = path.join(dirPath, file.name);
      
      if (file.isDirectory()) {
        totalSize += getDirectorySize(fullPath);
      } else {
        const stats = fs.statSync(fullPath);
        totalSize += stats.size;
      }
    }
  } catch (error) {
    console.warn(`Не удалось прочитать директорию ${dirPath}: ${error.message}`);
  }
  
  return totalSize;
}

function sourceFilesContain(dirPath, matcher) {
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dirPath, entry.name);

      if (entry.isDirectory()) {
        if (sourceFilesContain(fullPath, matcher)) {
          return true;
        }
        continue;
      }

      if (!/\.(js|jsx|ts|tsx)$/.test(entry.name)) {
        continue;
      }

      const content = fs.readFileSync(fullPath, 'utf8');
      if (matcher(content)) {
        return true;
      }
    }
  } catch (error) {
    console.warn(`Не удалось просканировать ${dirPath}: ${error.message}`);
  }

  return false;
}

// Current optimization signal checks
function hasReactLazyDynamicImport() {
  return sourceFilesContain(path.join(projectRoot, 'src'), content =>
    /(?:React\.)?lazy\s*\(\s*\(\s*\)\s*=>\s*import\s*\(/.test(content)
  );
}

function hasViteProductionOptimization() {
  const viteConfig = path.join(projectRoot, 'vite.config.js');

  if (!fs.existsSync(viteConfig)) {
    return false;
  }

  const content = fs.readFileSync(viteConfig, 'utf8');
  return (
    content.includes('chunkSizeWarningLimit') &&
    content.includes('terserOptions') &&
    content.includes("minify: 'terser'") &&
    content.includes('drop_console') &&
    content.includes('drop_debugger')
  );
}

// Анализ текущего состояния
function analyzeCurrentBundle() {
  console.log('📊 Анализ текущего бандла:\n');
  
  const distPath = path.join(projectRoot, 'dist');
  const nodeModulesPath = path.join(projectRoot, 'node_modules');
  
  // Проверяем существование dist
  if (!fs.existsSync(distPath)) {
    console.log('❌ Папка dist не найдена. Запустите сборку: npm run build');
    return false;
  }
  
  // Анализируем размеры
  const distSize = getDirectorySize(distPath);
  const nodeModulesSize = getDirectorySize(nodeModulesPath);
  
  console.log(`📁 Размер dist: ${(distSize / 1024 / 1024).toFixed(2)} MB`);
  console.log(`📦 Размер node_modules: ${(nodeModulesSize / 1024 / 1024).toFixed(2)} MB`);
  
  // Анализируем файлы в dist
  const assetsPath = path.join(distPath, 'assets');
  if (fs.existsSync(assetsPath)) {
    console.log('\n📋 Файлы в assets:');
    
    const files = fs.readdirSync(assetsPath)
      .map(file => {
        const filePath = path.join(assetsPath, file);
        const stats = fs.statSync(filePath);
        return {
          name: file,
          size: stats.size,
          sizeFormatted: `${(stats.size / 1024).toFixed(1)} KB`
        };
      })
      .sort((a, b) => b.size - a.size);
    
    files.forEach(file => {
      console.log(`   ${file.name}: ${file.sizeFormatted}`);
    });
  }
  
  return true;
}

// Проверка зависимостей
function analyzeDependencies() {
  console.log('\n📦 Анализ зависимостей:\n');
  
  const packageJsonPath = path.join(projectRoot, 'package.json');
  
  try {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    
    const dependencies = Object.keys(packageJson.dependencies || {});
    const devDependencies = Object.keys(packageJson.devDependencies || {});
    
    console.log(`📋 Производственные зависимости: ${dependencies.length}`);
    console.log(`🔧 Dev зависимости: ${devDependencies.length}`);
    
    // Крупные зависимости
    const largeDependencies = [
      'react',
      'react-dom',
      'react-router-dom',
      'recharts',
      'chart.js',
      'jspdf',
      'heic2any'
    ];
    
    console.log('\n📊 Крупные зависимости:');
    largeDependencies.forEach(dep => {
      if (dependencies.includes(dep)) {
        console.log(`   ✅ ${dep}`);
      } else {
        console.log(`   ❌ ${dep} (не найдена)`);
      }
    });
    
  } catch (error) {
    console.error(`❌ Ошибка чтения package.json: ${error.message}`);
  }
}

// Рекомендации по оптимизации
function generateOptimizationRecommendations() {
  console.log('\n💡 Рекомендации по оптимизации:\n');
  
  const recommendations = [
    {
      title: 'Code Splitting',
      description: 'Используйте React.lazy() для ленивой загрузки компонентов',
      implemented: hasReactLazyDynamicImport(),
      priority: 'Высокий'
    },
    {
      title: 'Tree Shaking',
      description: 'Импортируйте только нужные компоненты из библиотек',
      check: () => {
        // Проверяем, что удалённые heavy UI packages не вернулись в runtime deps.
        const removedHeavyUiDeps = ['@mui/material', '@mui/icons-material'];
        const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
        const dependencies = Object.keys(packageJson.dependencies || {});
        const devDependencies = Object.keys(packageJson.devDependencies || {});
        return removedHeavyUiDeps.every(dep => !dependencies.includes(dep) && !devDependencies.includes(dep));
      },
      priority: 'Средний'
    },
    {
      title: 'Named Library Imports',
      description: 'Проверяйте named imports для библиотек, которые поддерживают tree shaking',
      check: () => {
        return sourceFilesContain(path.join(projectRoot, 'src'), content =>
          content.includes("import { ") && (
            content.includes("} from 'lucide-react'") ||
            content.includes('} from "lucide-react"')
          )
        );
      },
      priority: 'Средний'
    },
    {
      title: 'Bundle Analysis',
      description: 'Установите webpack-bundle-analyzer для детального анализа',
      check: () => {
        const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf8'));
        return packageJson.devDependencies && packageJson.devDependencies['rollup-plugin-visualizer'];
      },
      priority: 'Низкий'
    },
    {
      title: 'Image Optimization',
      description: 'Оптимизируйте изображения и используйте современные форматы',
      check: () => {
        const publicPath = path.join(projectRoot, 'public');
        if (fs.existsSync(publicPath)) {
          const files = fs.readdirSync(publicPath);
          return files.some(file => file.endsWith('.webp') || file.endsWith('.avif'));
        }
        return false;
      },
      priority: 'Средний'
    },
    {
      title: 'Service Worker',
      description: 'Используйте Service Worker для кэширования',
      implemented: fs.existsSync(path.join(projectRoot, 'public', 'sw.js')),
      priority: 'Высокий'
    }
  ];
  
  recommendations.forEach(rec => {
    const status = rec.implemented !== undefined 
      ? (rec.implemented ? '✅' : '❌')
      : (rec.check && rec.check() ? '✅' : '❌');
    
    console.log(`${status} ${rec.title} (${rec.priority})`);
    console.log(`   ${rec.description}\n`);
  });
}

// Проверка производительности
function checkPerformance() {
  console.log('\n⚡ Проверка производительности:\n');
  
  const checks = [
    {
      name: 'Lazy Loading компонентов',
      check: () => hasReactLazyDynamicImport()
    },
    {
      name: 'Vite оптимизация',
      check: () => hasViteProductionOptimization()
    },
    {
      name: 'API кэширование',
      check: () => {
        const apiCache = path.join(projectRoot, 'src', 'utils', 'apiCache.js');
        return fs.existsSync(apiCache);
      }
    },
    {
      name: 'PWA оптимизация',
      check: () => {
        const manifest = path.join(projectRoot, 'public', 'manifest.json');
        const sw = path.join(projectRoot, 'public', 'sw.js');
        return fs.existsSync(manifest) && fs.existsSync(sw);
      }
    }
  ];
  
  checks.forEach(check => {
    const status = check.check() ? '✅' : '❌';
    console.log(`${status} ${check.name}`);
  });
}

// Генерация отчета
function generateReport() {
  console.log('\n📄 Генерация отчета оптимизации...\n');
  
  const report = {
    timestamp: new Date().toISOString(),
    analysis: {
      bundleExists: fs.existsSync(path.join(projectRoot, 'dist')),
      lazyLoadedRoutesPresent: hasReactLazyDynamicImport(),
      viteProductionOptimized: hasViteProductionOptimization(),
      apiCacheExists: fs.existsSync(path.join(projectRoot, 'src', 'utils', 'apiCache.js')),
      serviceWorkerExists: fs.existsSync(path.join(projectRoot, 'public', 'sw.js'))
    }
  };
  
  // Размеры файлов
  if (report.analysis.bundleExists) {
    const distSize = getDirectorySize(path.join(projectRoot, 'dist'));
    report.bundleSize = {
      bytes: distSize,
      mb: (distSize / 1024 / 1024).toFixed(2)
    };
  }
  
  const reportDir = path.join(projectRoot, 'test-results', 'bundle-analysis');
  fs.mkdirSync(reportDir, { recursive: true });

  const reportPath = path.join(reportDir, 'bundle-analysis-report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  
  console.log(`📊 Отчет сохранен: ${reportPath}`);
  
  return report;
}

// Главная функция
function main() {
  console.log('🚀 Запуск анализа бандла приложения\n');
  
  try {
    // Анализируем текущий бандл
    const bundleExists = analyzeCurrentBundle();
    
    // Анализируем зависимости
    analyzeDependencies();
    
    // Проверяем производительность
    checkPerformance();
    
    // Генерируем рекомендации
    generateOptimizationRecommendations();
    
    // Создаем отчет
    const report = generateReport();
    
    console.log('\n✅ Анализ завершен!');
    
    if (!bundleExists) {
      console.log('\n💡 Для полного анализа выполните:');
      console.log('   npm run build');
      console.log('   npm run analyze');
    }
    
  } catch (error) {
    console.error(`❌ Ошибка анализа: ${error.message}`);
    process.exit(1);
  }
}

// Запуск если файл выполняется напрямую
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
