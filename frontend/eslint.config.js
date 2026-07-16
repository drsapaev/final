import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tseslint from '@typescript-eslint/eslint-plugin';
import noHardcodedColors from './scripts/no-hardcoded-colors.js';

export default [
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    plugins: {
      react,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
      custom: {
        rules: {
          'no-hardcoded-colors': noHardcodedColors,
        },
      },
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
      // Custom: ban hardcoded colors (prevent regressions)
      'custom/no-hardcoded-colors': 'warn',

      // React правила
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,

      // Отключаем строгие правила для разработки
      'react/react-in-jsx-scope': 'off', // React 18+
      'react/prop-types': 'warn', // Только предупреждения для PropTypes

      // Общие правила
      'no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
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
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/aria-unsupported-elements': 'error',
      'jsx-a11y/click-events-have-key-events': 'error',
      'jsx-a11y/control-has-associated-label': 'error',
      'jsx-a11y/interactive-supports-focus': 'error',
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/role-has-required-aria-props': 'error',

      // =================================================================
      // UX Audit Stage 1 — запреты обхода инфраструктуры
      // (cross-cutting issues 10.1 / 10.2 / 10.4)
      // =================================================================

      // 10.1: Запрет raw fetch() — использовать api/client.
      // Разрешённые файлы: api/client.js, api/runtime.js, api/setup.js
      // (последний — legacy, мигрируется отдельно).
      'no-restricted-syntax': [
        'warn',
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='window'][callee.property.name='confirm']",
          message: 'Используйте useConfirm() из common/ConfirmDialog вместо window.confirm() (UX Audit 10.10).',
        },
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='window'][callee.property.name='alert']",
          message: 'Используйте notify.warning/error из services/notify вместо window.alert() (UX Audit 10.10).',
        },
        {
          selector: "CallExpression[callee.type='MemberExpression'][callee.object.name='window'][callee.property.name='prompt']",
          message: 'Используйте useConfirm() или модальный диалог вместо window.prompt() (UX Audit 10.10).',
        },
      ],

      // 10.2 + 10.4: Запрет прямого localStorage.setItem и window.location.href.
      'no-restricted-properties': [
        'warn',
        {
          object: 'localStorage',
          property: 'setItem',
          message: "Не используйте localStorage.setItem напрямую для auth-токенов. Импортируйте tokenManager из utils/tokenManager (UX Audit 10.2). Допустимо только для не-auth ключей.",
        },
        {
          object: 'window.location',
          property: 'href',
          message: 'Не присваивайте window.location.href напрямую. Для SPA-навигации используйте useNavigateSafely() из utils/navigationReact. Для hard-redirect (не-React контекст) — hardRedirectTo() из utils/navigation (UX Audit 10.4).',
        },
      ],
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    plugins: {
      '@typescript-eslint': tseslint,
    },
    languageOptions: {
      parser: tsParser,
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
    rules: {
      'no-unused-vars': 'off',
      // Phase 0 — TS rules (lenient at start; strict at Phase 9)
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'off',                       // ← off at start; warn at Phase 9
      '@typescript-eslint/explicit-function-return-type': 'off',         // ← off at start; warn at Phase 9
      '@typescript-eslint/explicit-module-boundary-types': 'off',
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
    // =================================================================
    // UX Audit Stage 1 — инфраструктурные файлы, которым разрешено
    // использовать localStorage / window.location / fetch напрямую.
    // Эти файлы САМИ ЯВЛЯЮТСЯ абстракциями, которые остальные
    // компоненты должны использовать.
    // =================================================================
    files: [
      'src/api/client.js',
      'src/api/runtime.js',
      'src/api/setup.js',
      'src/api/mcpClient.js',
      'src/api/patients.js',
      'src/api/payments.js',
      'src/utils/tokenManager.js',
      'src/utils/navigation.js',
      'src/utils/navigationReact.js',
      'src/contexts/ThemeContext.jsx',
      'src/theme/colorScheme.js',
    ],
    rules: {
      'no-restricted-properties': 'off',
      'no-restricted-syntax': 'off',
      'no-console': 'off',
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
