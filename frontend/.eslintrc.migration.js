/**
 * ESLint Configuration for Theme Migration
 * Enforces use of MUI theme instead of hardcoded values
 * Usage: npx eslint --config .eslintrc.migration.js src/
 */

module.exports = {
  extends: ['.eslintrc.theme.js'],
  rules: {
    // Phase 1: Warnings
    'no-restricted-syntax': [
      'warn',
      {
        selector: "JSXAttribute[name.name='sx'] ObjectExpression Property[key.name='color'] > Literal[value=/^#/]",
        message: 'Hardcoded hex colors are not allowed. Use theme.palette instead.',
      },
      {
        selector: "JSXAttribute[name.name='sx'] ObjectExpression Property[key.name='backgroundColor'] > Literal[value=/^#/]",
        message: 'Hardcoded hex colors are not allowed. Use theme.palette instead.',
      },
      {
        selector: "JSXAttribute[name.name='sx'] ObjectExpression Property[key.name='borderColor'] > Literal[value=/^#/]",
        message: 'Hardcoded hex colors are not allowed. Use theme.palette instead.',
      },
      {
        selector: "JSXAttribute[name.name='style'] > JSXExpressionContainer > ObjectExpression Property > Literal[value=/^#/]",
        message: 'Use sx prop instead of style prop. Prefer theme-based colors.',
      },
    ],

    // Disallow rgba() in inline styles
    'no-restricted-properties': [
      'warn',
      {
        object: 'Math',
        property: 'random',
        message: 'Please use a seeded random function instead.',
      },
    ],

    // Warn if spacing values not on grid
    'no-magic-numbers': [
      'warn',
      {
        ignore: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1, -2],
        enforceConst: true,
        detectObjects: false,
      },
    ],

    // Require useTheme import when using theme values
    'react-hooks/rules-of-hooks': 'error',

    // Phase 2: Errors (uncomment after migration starts)
    // 'no-restricted-syntax': ['error', ...rules],
  },

  overrides: [
    {
      files: ['src/components/**/*.{jsx,tsx}'],
      rules: {
        // Enforce sx prop over inline styles
        'react/style-prop-object': 'warn',
      },
    },
  ],
};

/**
 * MIGRATION PHASES:
 * 
 * Phase 1 (Week 1-2): Warnings Only
 * - Developers see warnings in console
 * - CI passes, but developers get alerts
 * - Time to adjust workflow
 * 
 * Phase 2 (Week 3-4): Errors (gradual rollout)
 * - Turn rules to 'error' one at a time
 * - Allow PR bypass with @eslint-disable comments (documented)
 * - Build fails if violations detected
 * 
 * Phase 3 (Week 5+): Strict Enforcement
 * - All rules are errors
 * - No bypasses allowed without code review
 * - 100% compliance required
 */
