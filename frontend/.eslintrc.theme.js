/**
 * ESLint Configuration for Design System Enforcement
 * Prevents hardcoded colors, spacing, and font sizes
 * Run: eslint . --config .eslintrc.theme.js
 */

module.exports = {
  rules: {
    // ========================================================================
    // CUSTOM RULES: NO HARDCODED COLORS
    // ========================================================================
    'no-hardcoded-colors': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Disallow hardcoded color values in JSX/CSS',
          category: 'Design System',
        },
      },
      create(context) {
        return {
          JSXAttribute(node) {
            const { value } = node;
            // Check for color prop values like color="#fff" or bgcolor="red"
            if (
              (node.name.name === 'color' ||
                node.name.name === 'bgcolor' ||
                node.name.name === 'background' ||
                node.name.name === 'sx') &&
              value?.type === 'Literal'
            ) {
              const strValue = String(value.value);
              if (
                /#[0-9a-f]{3,6}/i.test(strValue) ||
                /rgb\(|rgba\(/i.test(strValue)
              ) {
                context.report({
                  node,
                  message: `Hardcoded color "${strValue}" found. Use theme.palette instead.`,
                  fix(fixer) {
                    return fixer.replaceText(value, '{theme.palette.primary.main}');
                  },
                });
              }
            }
          },
        };
      },
    },

    // ========================================================================
    // CUSTOM RULES: NO INLINE STYLES WITH COLORS
    // ========================================================================
    'no-inline-color-styles': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Disallow inline color styles',
          category: 'Design System',
        },
      },
      create(context) {
        return {
          JSXAttribute(node) {
            if (node.name.name === 'style' && node.value?.type === 'JSXExpressionContainer') {
              const code = context.getSourceCode().getText(node.value);
              if (
                /color:|backgroundColor:|background:|borderColor:|fill:|stroke:/i.test(code) &&
                /#[0-9a-f]{3,6}|rgb\(|rgba\(/i.test(code)
              ) {
                context.report({
                  node,
                  message: 'Inline color styles detected. Use sx prop with theme tokens instead.',
                });
              }
            }
          },
        };
      },
    },

    // ========================================================================
    // CUSTOM RULES: ENFORCE THEME SPACING
    // ========================================================================
    'no-magic-spacing': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Disallow magic spacing numbers - use spacing scale',
          category: 'Design System',
        },
      },
      create(context) {
        const validSpacing = [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 80, 96];

        return {
          JSXAttribute(node) {
            if (
              (node.name.name === 'padding' ||
                node.name.name === 'margin' ||
                node.name.name === 'gap') &&
              node.value?.type === 'Literal'
            ) {
              const value = node.value.value;
              if (typeof value === 'number' && !validSpacing.includes(value)) {
                context.report({
                  node,
                  message: `Magic spacing value "${value}px" detected. Use spacing scale: ${validSpacing.join(
                    ', '
                  )}`,
                });
              }
            }
          },
        };
      },
    },

    // ========================================================================
    // CUSTOM RULES: REQUIRE THEME IMPORT
    // ========================================================================
    'theme-import-required': {
      meta: {
        type: 'problem',
        docs: {
          description: 'Require useTheme() hook in components using styled-components',
          category: 'Design System',
        },
      },
      create(context) {
        let hasThemeImport = false;
        let hasStyledComponent = false;

        return {
          ImportDeclaration(node) {
            if (node.source.value.includes('styled')) {
              hasStyledComponent = true;
            }
            if (node.source.value.includes('useTheme')) {
              hasThemeImport = true;
            }
          },
          'Program:exit'() {
            if (hasStyledComponent && !hasThemeImport) {
              context.report({
                node: context.getSourceCode().ast,
                message: 'Styled components detected without useTheme() import',
              });
            }
          },
        };
      },
    },
  },

  // ========================================================================
  // ESLint CONFIGURATION WITH RULES
  // ========================================================================
  overrides: [
    {
      files: ['src/components/**/*.tsx', 'src/pages/**/*.tsx'],
      rules: {
        'no-hardcoded-colors': 'error',
        'no-inline-color-styles': 'warn',
        'no-magic-spacing': 'warn',
        'theme-import-required': 'warn',

        // Existing rules
        'react/no-unstable-nested-components': 'warn',
        'react-hooks/rules-of-hooks': 'error',
        'react-hooks/exhaustive-deps': 'warn',
      },
    },
  ],
};
