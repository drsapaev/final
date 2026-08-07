import js from '@eslint/js';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tseslint from '@typescript-eslint/eslint-plugin';
import noHardcodedColors from './scripts/no-hardcoded-colors.js';
import noDomainTypeDuplication from './scripts/no-domain-type-duplication.js';
import noDtoImportInComponents from './scripts/no-dto-import-in-components.js';
import noApiLooseReturn from './scripts/no-api-loose-return.js';
import noFakeTimersWithoutCleanup from './scripts/no-fake-timers-without-cleanup.js';

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
          'no-domain-type-duplication': noDomainTypeDuplication,
          'no-dto-import-in-components': noDtoImportInComponents,
          'no-api-loose-return': noApiLooseReturn,
          'no-fake-timers-without-cleanup': noFakeTimersWithoutCleanup,
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

      // Wave 5 — Domain Adoption 100% regression guards
      // Error-level: these are architectural invariants, not style.
      'custom/no-domain-type-duplication': 'error',
      'custom/no-dto-import-in-components': 'error',
      'custom/no-api-loose-return': 'error',

      // Custom: require vi.useRealTimers() when vi.useFakeTimers() is used
      // Prevents vitest process hang in singleFork mode (commit 9706ecda)
      'custom/no-fake-timers-without-cleanup': 'error',

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
      // Разрешённые файлы: api/client.ts, api/runtime.ts, api/setup.ts
      // (последний — legacy, мигрируется отдельно).
      // audit/phase-7b, BS-49: added `fetch()` selector — previously the
      // comment claimed "Запрет raw fetch()" but no selector existed.
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
        {
          selector: "CallExpression[callee.name='fetch']",
          message: 'Используйте api.get/api.post из api/client вместо raw fetch() (UX Audit 10.1). Разрешено только в api/client.ts, api/runtime.ts, api/setup.ts.',
        },
      ],

      // audit/phase-7b, BS-49: ban direct imports from generated OpenAPI types.
      // Consumers should import from types/api.ts (which re-exports with
      // friendly names) or types/domain/*.ts (hand-written domain types).
      // Direct imports from types/generated/api.ts couple consumer code to
      // the raw OpenAPI schema shape and break on schema regeneration.
      'no-restricted-imports': [
        'warn',
        {
          paths: [
            {
              name: '@/types/generated/api',
              message: 'Import from types/api.ts or types/domain/*.ts instead. Direct imports from generated OpenAPI types couple consumer code to the raw schema shape.',
            },
            {
              name: '../types/generated/api',
              message: 'Import from types/api.ts or types/domain/*.ts instead. Direct imports from generated OpenAPI types couple consumer code to the raw schema shape.',
            },
            {
              name: '../../types/generated/api',
              message: 'Import from types/api.ts or types/domain/*.ts instead. Direct imports from generated OpenAPI types couple consumer code to the raw schema shape.',
            },
          ],
        },
      ],

      // Sprint C4: ban DTO-shaped interfaces (Response/Request/DTO suffix) in types/domain/.
      // Domain types should not mirror backend DTO shapes — they should represent
      // domain concepts. DTOs belong in types/api.ts or types/generated/api.ts.
      // Applied via a separate config block below (files: types/domain/**).

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
        // Stabilization Sprint B2: provide project so @typescript-eslint/parser
        // resolves TS DOM lib types (BodyInit, RequestInit, NotificationOptions,
        // etc.) via lib.dom.d.ts. ESLint doesn't need these re-declared as
        // globals — that would duplicate what tsc already knows and create
        // a maintenance burden (the list drifts from lib.dom.d.ts).
        project: './tsconfig.json',
      },
      globals: {
        ...globals.browser,
        ...globals.es2022,
        ...globals.node,
      },
    },
    rules: {
      'no-unused-vars': 'off',
      // Stabilization Sprint B2: turn off no-undef for .ts/.tsx — TypeScript
      // already does this check via tsc (TS2304: Cannot find name). ESLint's
      // no-undef doesn't understand TS type declarations (interfaces, types,
      // DOM lib globals). Verified equivalent: see MIGRATION_BLOCKERS.md B2.
      'no-undef': 'off',
      // Phase 0 — TS rules (lenient at start; strict at Phase 9)
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
      '@typescript-eslint/no-explicit-any': 'off',                       // ← off at start; warn at Phase 9
      '@typescript-eslint/explicit-function-return-type': 'off',         // ← off at start; warn at Phase 9
      '@typescript-eslint/explicit-module-boundary-types': 'off',
    },
  },
  {
    // Специальные правила для тестовых файлов
    // audit/phase-7, BS-48: extended patterns to include .ts/.tsx test files.
    // Previously matched only .test.{js,jsx} (0 such files in the project)
    // and __tests__/**/*.{js,jsx} — but the project has 149 .test.ts/.test.tsx
    // files that weren't receiving the test globals block. The block was
    // effectively dead code. Now covers .ts/.tsx variants for both patterns.
    files: [
      '**/*.test.{js,jsx,ts,tsx}',
      '**/*.spec.{js,jsx,ts,tsx}',
      '**/__tests__/**/*.{js,jsx,ts,tsx}',
      '**/test/**/*.{js,jsx,ts,tsx}',
    ],
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
      'src/api/client.ts',
      'src/api/runtime.js',
      'src/api/runtime.ts',
      'src/api/setup.js',
      'src/api/setup.ts',
      'src/api/mcpClient.js',
      'src/api/mcpClient.ts',
      'src/api/patients.js',
      'src/api/patients.ts',
      'src/api/payments.js',
      'src/api/payments.ts',
      'src/utils/tokenManager.js',
      'src/utils/tokenManager.ts',
      'src/utils/navigation.js',
      'src/utils/navigation.ts',
      'src/utils/navigationReact.js',
      'src/utils/navigationReact.ts',
      'src/contexts/ThemeContext.jsx',
      'src/contexts/ThemeContext.tsx',
      'src/theme/colorScheme.js',
      'src/theme/colorScheme.ts',
    ],
    rules: {
      'no-restricted-properties': 'off',
      'no-restricted-syntax': 'off',
      'no-console': 'off',
    },
  },
  {
    // Sprint C4: ban DTO-shaped interfaces (Response/Request/DTO suffix) in types/domain/.
    // Domain types should not mirror backend DTO shapes — they should represent
    // domain concepts. DTOs belong in types/api.ts or types/generated/api.ts.
    files: ['src/types/domain/**/*.{ts,tsx}'],
    plugins: {
      '@typescript-eslint': tseslint,
    },
    languageOptions: {
      parser: tsParser,
      ecmaVersion: 2022,
      sourceType: 'module',
      parserOptions: {
        project: './tsconfig.json',
      },
    },
    rules: {
      'no-restricted-syntax': [
        'warn',
        {
          selector: "TSInterfaceDeclaration[id.name=/Response$/]",
          message: 'DTO-shaped interfaces (suffix Response) are not allowed in types/domain/. Use types/api.ts for DTOs.',
        },
        {
          selector: "TSInterfaceDeclaration[id.name=/Request$/]",
          message: 'DTO-shaped interfaces (suffix Request) are not allowed in types/domain/. Use types/api.ts for DTOs.',
        },
        {
          selector: "TSInterfaceDeclaration[id.name=/DTO$/]",
          message: 'DTO-shaped interfaces (suffix DTO) are not allowed in types/domain/. Use types/api.ts for DTOs.',
        },
      ],
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
      // Phase 0.5: generated OpenAPI types — do not lint (75K lines, auto-regenerated)
      'src/types/generated/**',
    ],
  },
];
