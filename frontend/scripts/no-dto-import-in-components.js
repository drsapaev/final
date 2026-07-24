/**
 * ESLint custom rule: no-dto-import-in-components
 *
 * Bans importing names ending in `Dto` (transport types from src/types/api.ts)
 * inside component / page / context files. Components must consume the
 * canonical domain types from src/types/domain/ instead.
 *
 * Allowed locations for Dto imports:
 *   - src/api/            (the boundary layer — mappers and api clients)
 *   - src/types/          (type definitions themselves)
 *   - test files          (tests may inspect raw DTO shapes)
 *
 * Rationale: Wave 4 of Domain Adoption 100% established the architecture
 *     Server JSON  ->  DTO (types/api.ts)  ->  mapper (api/mappers/)  ->  Domain (types/domain/)
 *                                                                                   |
 *                                                                              React components
 *
 * If a component imports a `Dto` type, it's reaching past the mapper
 * boundary and coupling to the transport shape. When the backend changes
 * the DTO, the component breaks — exactly the failure mode the mapper
 * layer exists to prevent.
 *
 * This rule makes that architectural violation an explicit lint error.
 */

function isTestFile(filename) {
  const normalized = filename.replace(/\\/g, '/');
  return (
    /\.test\.[jt]sx?$/.test(normalized) ||
    normalized.includes('/__tests__/') ||
    normalized.includes('/test/')
  );
}

function isApiLayer(filename) {
  const normalized = filename.replace(/\\/g, '/');
  // src/api/** — mappers, clients, interceptors all live here.
  return normalized.includes('/src/api/');
}

function isTypesLayer(filename) {
  const normalized = filename.replace(/\\/g, '/');
  // src/types/** — type definitions themselves (api.ts, domain/*, etc.)
  return normalized.includes('/src/types/');
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Ban importing *Dto transport types in components/pages/contexts — use domain types instead',
      category: 'Best Practices',
      recommended: true,
    },
    messages: {
      dtoImport:
        'Component/page/context must not import transport type "{{name}}" ' +
        '(*Dto suffix = raw OpenAPI shape). Import the canonical domain ' +
        'type from "@/types/domain/*" instead. Mapper layer (src/api/mappers/) ' +
        'is the only place that should touch DTOs. ' +
        '(Wave 5: Domain Adoption 100% regression guard)',
    },
    schema: [],
  },
  create(context) {
    const filename = context.getFilename();

    // Only enforce in component / page / context / hook code.
    if (
      isTestFile(filename) ||
      isApiLayer(filename) ||
      isTypesLayer(filename)
    ) {
      return {};
    }

    return {
      // Catch: import type { PatientDto } from '@/types/api'
      // Catch: import { PatientDto } from '@/types/api'
      // Catch: import { PatientDto, OtherThing } from '@/types'
      ImportDeclaration(node) {
        const source = node.source.value;
        // Only flag DTOs imported from the transport layer.
        const isTransportSource =
          source.includes('/types/api') ||
          source === '@/types/api' ||
          source === '@/types' ||
          source.endsWith('/types') ||
          source.includes('/types/generated/');

        if (!isTransportSource) return;

        for (const specifier of node.specifiers) {
          if (specifier.type !== 'ImportSpecifier') continue;
          const importedName = specifier.imported.name;
          if (/Dto$/.test(importedName)) {
            context.report({
              node: specifier,
              messageId: 'dtoImport',
              data: { name: importedName },
            });
          }
        }
      },
    };
  },
};
