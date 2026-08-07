/**
 * ESLint custom rule: require-useRealTimers-after-useFakeTimers
 *
 * Ensures that any file using vi.useFakeTimers() also calls
 * vi.useRealTimers() in an afterEach or afterAll hook.
 *
 * Background: In vitest singleFork mode, fake timers persist across
 * test files in the same worker process. If a test file enables
 * fake timers but doesn't restore real timers in cleanup, subsequent
 * files (and vitest's own shutdown code) may hang indefinitely.
 *
 * This rule was added after a multi-day investigation (v5-v10)
 * traced a CI process hang to exactly this pattern in
 * useDebouncedCallback.test.ts.
 */

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require vi.useRealTimers() in afterEach/afterAll when vi.useFakeTimers() is used',
      category: 'Possible Errors',
      recommended: true,
    },
    schema: [],
    messages: {
      missingUseRealTimers:
        'vi.useFakeTimers() is used in this file but vi.useRealTimers() is not called in any afterEach or afterAll hook. ' +
        'In singleFork mode, fake timers leak across files and can cause the vitest process to hang indefinitely. ' +
        'Add vi.useRealTimers() to your afterEach or afterAll hook.',
    },
  },

  create(context) {
    let hasUseFakeTimers = false;
    let hasUseRealTimersInCleanup = false;

    // Track whether we're inside an afterEach/afterAll callback
    let inCleanupHook = false;

    return {
      // Detect vi.useFakeTimers() anywhere in the file
      CallExpression(node) {
        const { callee } = node;

        // Check for vi.useFakeTimers()
        if (
          callee.type === 'MemberExpression' &&
          callee.object?.name === 'vi' &&
          callee.property?.name === 'useFakeTimers'
        ) {
          hasUseFakeTimers = true;
        }

        // Check for vi.useRealTimers() inside afterEach/afterAll
        if (inCleanupHook) {
          if (
            callee.type === 'MemberExpression' &&
            callee.object?.name === 'vi' &&
            callee.property?.name === 'useRealTimers'
          ) {
            hasUseRealTimersInCleanup = true;
          }
        }
      },

      // Track entry into afterEach/afterAll callbacks
      'CallExpression[callee.name="afterEach"]'(node) {
        if (node.arguments.length > 0 && node.arguments[0].type === 'ArrowFunctionExpression') {
          inCleanupHook = true;
        }
      },

      'CallExpression[callee.name="afterAll"]'(node) {
        if (node.arguments.length > 0 && node.arguments[0].type === 'ArrowFunctionExpression') {
          inCleanupHook = true;
        }
      },

      // Reset cleanup flag when leaving the callback
      'CallExpression[callee.name="afterEach"]:exit'() {
        inCleanupHook = false;
      },

      'CallExpression[callee.name="afterAll"]:exit'() {
        inCleanupHook = false;
      },

      // Report at end of file
      'Program:exit'() {
        if (hasUseFakeTimers && !hasUseRealTimersInCleanup) {
          context.report({
            loc: { line: 1, column: 0 },
            messageId: 'missingUseRealTimers',
          });
        }
      },
    };
  },
};
