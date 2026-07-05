/**
 * ESLint custom rule: no-hardcoded-colors
 * Bans hex colors and rgba() in JSX/JS files (except token definition files).
 * Forces usage of macos CSS variables (var(--mac-*)) instead.
 */

const TOKEN_FILES = [
  'theme/tokens',
  'theme/colorScheme',
  'theme/colorUtils',
  'theme/globalStyles',
  'theme/macosTheme',
  'theme/themes',
  'constants/a11yTokens',
  'components/ui/macos/',
  'utils/designValidator',
  'utils/frontendAudit',
  'utils/themeChecker',
  'services/panelPrint',
  'pages/landingContent',
];

const HEX_PATTERN = /#[0-9a-fA-F]{3,8}\b/g;
const RGBA_PATTERN = /rgba?\(\s*\d+/g;

export default {
  meta: {
    type: 'problem',
    docs: {
      description: 'Ban hardcoded hex/rgba colors — use var(--mac-*) tokens instead',
      category: 'Best Practices',
      recommended: true,
    },
    messages: {
      hexColor: 'Hardcoded hex color "{{value}}" found — use var(--mac-*) token instead',
      rgbaColor: 'Hardcoded rgba() color found — use var(--mac-*) token or color-mix() instead',
    },
    schema: [],
  },

  create(context) {
    const filename = context.getFilename();

    // Skip token definition files
    if (TOKEN_FILES.some(pattern => filename.includes(pattern))) {
      return {};
    }

    // Skip test files
    if (filename.includes('__tests__') || filename.includes('/test/')) {
      return {};
    }

    return {
      Literal(node) {
        if (typeof node.value !== 'string') return;
        const value = node.value;

        let match;
        HEX_PATTERN.lastIndex = 0;
        while ((match = HEX_PATTERN.exec(value)) !== null) {
          if (value.startsWith('http') || value.startsWith('#/') || value.length > 100) continue;
          context.report({
            node,
            messageId: 'hexColor',
            data: { value: match[0] },
          });
          break;
        }

        RGBA_PATTERN.lastIndex = 0;
        if (RGBA_PATTERN.test(value) && !value.includes('var(')) {
          context.report({
            node,
            messageId: 'rgbaColor',
          });
        }
      },

      TemplateElement(node) {
        const value = node.value.raw || '';
        if (!value) return;

        HEX_PATTERN.lastIndex = 0;
        let match;
        while ((match = HEX_PATTERN.exec(value)) !== null) {
          if (value.includes('var(') && value.indexOf('var(', match.index) < match.index + 20) continue;
          context.report({
            node,
            messageId: 'hexColor',
            data: { value: match[0] },
          });
          break;
        }
      },
    };
  },
};
