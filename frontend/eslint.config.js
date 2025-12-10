import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import globals from 'globals';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      react,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
    },
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        ...globals.es2022,
        ...globals.node,
      },
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      // React правила
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      
      // Отключаем строгие правила для разработки
      'react/react-in-jsx-scope': 'off', // React 18+
      'react/prop-types': 'warn', // Только предупреждения для PropTypes
      
      // Общие правила
      'no-unused-vars': 'warn',
      'no-console': 'error', // HIPAA Compliance: запрещаем console.log для предотвращения утечки PHI
      'prefer-const': 'warn',
      'no-var': 'error',
      
      // Стиль кода
      'quotes': ['warn', 'single'],
      'semi': ['warn', 'always'],
      'comma-dangle': ['warn', 'only-multiline'],
      'object-curly-spacing': ['warn', 'always'],
      'array-bracket-spacing': ['warn', 'never'],
      
      // JSX правила
      'jsx-quotes': ['warn', 'prefer-double'],
      'react/jsx-uses-react': 'off',
      'react/jsx-uses-vars': 'error',
      'react/jsx-no-undef': 'error',
      
      // Accessibility (основные правила)
      'jsx-a11y/alt-text': 'warn',
      'jsx-a11y/aria-role': 'warn',
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
    },
  },
  {
    // Специальные правила для тестовых файлов
    files: ['**/*.test.{js,jsx}', '**/__tests__/**/*.{js,jsx}', '**/test/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        ...globals.jest,
        describe: 'readonly',
        it: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
        vi: 'readonly', // Vitest
        vitest: 'readonly',
        test: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': 'off', // Отключаем для тестов
      'no-undef': 'off', // Отключаем проверку undefined для тестовых файлов
    },
  },
  {
    // Игнорируемые файлы
    ignores: [
      'dist/**',
      'node_modules/**',
      'storybook-static/**',
      '*.config.js',
      '*.config.ts',
    ],
  },
];
