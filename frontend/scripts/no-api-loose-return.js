/**
 * ESLint custom rule: no-api-loose-return
 *
 * Bans functions in src/api/*.ts (excluding mappers/ and __tests__/) from
 * returning `any`, `unknown`, or `Record<string, unknown>` without an
 * explicit `@api-transport` JSDoc tag on the function.
 *
 * Why these three types are suspicious in api/* return position:
 *   - `any`              → defeats the type system entirely
 *   - `unknown`          → forces every caller to do unsafe casts
 *   - `Record<string,unknown>` → "I gave up typing this" — usually a sign
 *                              the function should return a domain type
 *                              via a mapper
 *
 * Legitimate exceptions (allowed with `@api-transport` JSDoc tag):
 *   - Endpoints that return free-form dicts (queue settings, audit logs)
 *     where no domain type exists yet
 *   - Endpoints that return raw passthrough data (file uploads, etc.)
 *
 * Rationale: Wave 4 of Domain Adoption 100% migrated api/*.ts to return
 * domain types via mappers. Without enforcement, future PRs will quietly
 * re-introduce `Promise<Record<string, unknown>>` for "quick" endpoints,
 * undoing the architectural boundary.
 *
 * Usage in source:
 *   / ** @api-transport backend returns a free-form audit-log dict * /
 *   export async function getAuditLog(): Promise<Record<string, unknown>> { ... }
 */

function isApiFile(filename) {
  const normalized = filename.replace(/\\/g, '/');
  return (
    normalized.includes('/src/api/') &&
    !normalized.includes('/src/api/__tests__/') &&
    !normalized.includes('/src/api/mappers/')
  );
}

function isTestFile(filename) {
  const normalized = filename.replace(/\\/g, '/');
  return (
    /\.test\.[jt]sx?$/.test(normalized) ||
    normalized.includes('/__tests__/') ||
    normalized.includes('/test/')
  );
}

// Returns true if a TSTypeAnnotation node annotates the function's return
// as `any`, `unknown`, `Record<string, unknown>`, or arrays/promises of
// those.
function isLooseReturnType(typeAnnotation) {
  if (!typeAnnotation) return false;
  const typeNode = typeAnnotation.typeAnnotation;
  return isLooseTypeNode(typeNode);
}

function isLooseTypeNode(node) {
  if (!node) return false;

  // Promise<T> — unwrap and check T
  if (node.type === 'TSTypeReference') {
    const name = node.typeName;
    // Both `typeParameters` (older parser) and `typeArguments` (newer parser)
    // are used for generic params. Support both.
    const params = node.typeParameters?.params || node.typeArguments?.params;
    if (name && name.name === 'Promise' && params) {
      const inner = params[0];
      return isLooseTypeNode(inner);
    }
    // Record<string, unknown> — TSUtilityType or TSTypeReference
    if (name && name.name === 'Record' && params) {
      return true;
    }
    return false;
  }

  // `any` and `unknown` are TSAnyKeyword / TSUnknownKeyword
  if (node.type === 'TSAnyKeyword') return true;
  if (node.type === 'TSUnknownKeyword') return true;

  // Array<T> or T[] — unwrap and check T
  if (node.type === 'TSArrayType') {
    return isLooseTypeNode(node.elementType);
  }

  return false;
}

// Check if the function's JSDoc comment contains the `@api-transport` tag.
function hasApiTransportTag(node) {
  if (!node || !node.leadingComments) return false;
  for (const comment of node.leadingComments) {
    if (comment.type === 'Block' && /@api-transport\b/.test(comment.value)) {
      return true;
    }
  }
  return false;
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Ban api/*.ts functions from returning any/unknown/Record<string,unknown> without @api-transport JSDoc tag',
      category: 'Best Practices',
      recommended: true,
    },
    messages: {
      looseReturn:
        'API function "{{name}}" returns a loose type (any / unknown / ' +
        'Record<string, unknown>). Use a mapper to return a domain type ' +
        'from "@/types/domain/*", OR add an `@api-transport` JSDoc tag ' +
        'explaining why this endpoint returns a free-form shape. ' +
        '(Wave 5: Domain Adoption 100% regression guard)',
    },
    schema: [],
  },
  create(context) {
    const filename = context.getFilename();

    if (!isApiFile(filename) || isTestFile(filename)) {
      return {};
    }

    const sourceCode = context.getSourceCode();

    function checkFunction(node) {
      // Only functions with explicit return type annotations.
      if (!node.returnType) return;

      const name =
        node.id?.name ||
        node.key?.name ||
        (node.parent?.type === 'VariableDeclarator' ? node.parent.id.name : null) ||
        '<anonymous>';

      // Skip helper functions (not exported, lowercase first letter, used
      // internally). These aren't API endpoints — they're utilities.
      // We detect this by: not exported AND no leading underscore convention.
      const isExported =
        node.parent?.type === 'ExportNamedDeclaration' ||
        node.parent?.type === 'ExportDefaultDeclaration' ||
        (node.parent?.type === 'VariableDeclarator' &&
          (node.parent.parent?.type === 'ExportNamedDeclaration' ||
            node.parent.parent?.type === 'ExportDefaultDeclaration'));
      if (!isExported) return;

      // Allow if @api-transport JSDoc tag is present.
      // For exported functions, the JSDoc may attach to either the function
      // node itself OR its ExportNamedDeclaration parent — check both.
      const comments = sourceCode.getCommentsBefore(node);
      const parentComments = node.parent?.type === 'ExportNamedDeclaration'
        ? sourceCode.getCommentsBefore(node.parent)
        : [];
      const allComments = [...comments, ...parentComments];
      const hasTag = allComments.some(
        (c) => c.type === 'Block' && /@api-transport\b/.test(c.value)
      );
      if (hasTag) return;

      if (isLooseReturnType(node.returnType)) {
        context.report({
          node: node.returnType,
          messageId: 'looseReturn',
          data: { name },
        });
      }
    }

    return {
      FunctionDeclaration: checkFunction,
      FunctionExpression: checkFunction,
      ArrowFunctionExpression: checkFunction,
    };
  },
};
