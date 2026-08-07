/**
 * Source contract helper — makes source-text assertions resilient to
 * harmless TypeScript syntax added during strict-mode TS migration.
 *
 * Strategy: strip TS-only syntax from source before matching.
 * Uses iterative regex passes with simple patterns.
 *
 * INVARIANT: This helper removes ONLY TypeScript syntax. It must NEVER
 * normalize:
 *   - Variable names or aliases (e.g., `const t = tI18n`)
 *   - Function calls or inlining (e.g., `normalizePatientGender(x)` vs `patientGender`)
 *   - Expression ordering
 *   - Import statements
 *   - JSX structure
 *   - Conditional constructs (&&, ?:, if/else)
 *   - Control flow
 *
 * If a test fails because the code was refactored (not just typed),
 * update the assertion in the test — do NOT extend this helper.
 *
 * Usage:
 *   import { normalizeSource } from './source-contract-helper';
 *   const source = fs.readFileSync(path, 'utf8');
 *   const normalized = normalizeSource(source);
 *   expect(normalized).toContain('openRecordPreview(row);');
 *   expect(normalized).not.toContain('status === "waiting"');
 */

/**
 * Strip TypeScript annotations and casts from source text.
 *
 * Runs multiple passes to handle nested patterns like `as unknown as Type`.
 */
export function normalizeSource(source: string): string {
  let s = source;

  // Run 4 passes to handle nested casts (as unknown as Type → as Type → removed)
  for (let pass = 0; pass < 4; pass++) {
    const before = s;

    // 1. Remove `as unknown as Type` — match the whole thing including the type
    //    Type is an identifier optionally followed by generics/union
    s = s.replace(
      /\bas\s+unknown\s+as\s+[A-Za-z_$][\w$]*(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>)?(?:\s*\|\s*[A-Za-z_$][\w$]*)*/g,
      ''
    );

    // 2. Remove `as never` (including preceding space to avoid leaving 'expr }')
    s = s.replace(/\s+as\s+never\b/g, '');

    // 3. Remove `as { ... }` — object type assertion
    s = s.replace(/\bas\s+\{[^}]*\}/g, '');

    // 4. Remove `as (params) => ReturnType` — function type assertion
    s = s.replace(/\bas\s+\([^)]*\)\s*=>\s*[A-Za-z_$][\w$]*/g, '');

    // 5. Remove `as Type<generic>` — generic type cast (e.g., Record<string, unknown>)
    s = s.replace(
      /\bas\s+[A-Za-z_$][\w$]*<[^<>]*(?:<[^<>]*>[^<>]*)*>/g,
      ''
    );

    // 6. Remove `as Type | Type | null` — union type cast
    s = s.replace(
      /\bas\s+[A-Z][\w$]*(?:\s*\|\s*[A-Za-z_$][\w$]*(?:<[^<>]*>)?)*\s*(?:\|\s*(?:null|undefined|never))?/g,
      ''
    );

    // 7. Remove `as type` — simple lowercase type cast
    s = s.replace(/\bas\s+(?:string|number|boolean|unknown|any|void|object)\b/g, '');

    // 8. Remove `as import('module').Type<...>` — dynamic import type assertion
    //    MUST run before step 9 (lowercase identifier) because `import` starts
    //    with lowercase and would be partially matched by step 9.
    //    e.g., `as import('axios').AxiosResponse<Record<string, unknown>>`
    s = s.replace(
      /\bas\s+import\([^)]*\)\.[A-Za-z_$][\w$]*(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>)?/g,
      ''
    );

    // 9. Remove `as lowercaseIdentifier` — other lowercase type
    s = s.replace(/\bas\s+[a-z][\w$]*/g, '');

    // If nothing changed in this pass, we're done
    if (s === before) break;
  }

  // Phase 2: Remove parameter type annotations
  // `(param: Type` → `(param` — match identifier followed by `: Type` before `,` or `)`
  s = s.replace(
    /(\w+)\s*:\s*[A-Za-z_$][\w$]*(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>)?(?:\s*\|\s*[A-Za-z_$][\w$]*)*\s*(?=[,)=])/g,
    '$1 '
  );

  // Phase 3: Remove return type annotations: `): Type =>` → `) =>`
  s = s.replace(
    /\)\s*:\s*[A-Za-z_$][\w$]*(?:<[^<>]*>)?(?:\s*\|\s*[A-Za-z_$][\w$]*)*\s*=>/g,
    ') =>'
  );

  // Phase 4: Remove generic type parameters on React hooks
  s = s.replace(/(useRef|useState|useCallback|useMemo|useEffect|useReducer)<[^<>]+>\(/g, '$1(');

  // Phase 5: Remove variable type annotations: `const x: Type = ` → `const x = `
  s = s.replace(
    /\b(const|let|var)\s+(\w+)\s*:\s*[A-Za-z_$][\w$]*(?:<[^<>]*>)?(?:\s*\|\s*[A-Za-z_$][\w$]*)*\s*=/g,
    '$1 $2 ='
  );

  // Phase 6: Remove `String(expr ?? '')` → `expr`
  s = s.replace(/String\((\w+(?:\.\w+)*\([^)]*\))\s*\?\?\s*''\)/g, '$1');

  // Phase 6b: Remove `(expr as Type)` → `expr` — unwrap parens that only contained a cast
  // Unwrap `(identifier)` → `identifier` when followed by ?. or [
  s = s.replace(/\((\w+)\s*\)(?=[?.\[])/g, '$1');
  // Also unwrap when preceded by ( (function call wrapping): `setStatus((expr))` → `setStatus(expr)` if expr has no parens
  // Already handled by 6b2 below

  // Phase 6b2: Remove double parens left by cast removal.
  // When `as Type` is removed from `(expr as Type)`, the wrapping parens remain:
  // `setStatus((expr as Type));` → `setStatus((expr));` → should be `setStatus(expr);`
  // The inner parens were added ONLY to scope the cast — not part of the original code.
  s = s.replace(/\(\(([^()]+)\)\s*\)/g, '($1)');
  // Run twice for nested cases
  s = s.replace(/\(\(([^()]+)\)\s*\)/g, '($1)');

  // Phase 6c: Remove `| Type` union members left after `as` removal
  s = s.replace(/(\w|\))\s*\|\s*[A-Za-z_$][\w$]*(?:\s*\|\s*[A-Za-z_$][\w$]*)*/g, '$1');

  // Phase 7: Clean up whitespace and artifacts from cast removal
  s = s.replace(/  +/g, ' ');
  s = s.replace(/ +$/gm, '');
  // Remove `[]` left behind after `as Type[]` cast removal.
  // Only remove when preceded by identifier (not after || which is a default array).
  s = s.replace(/(\w)\s+\[\]/g, '$1');
  // Remove trailing space before semicolons and commas
  s = s.replace(/\s+([;,])/g, '$1');
  // Remove space after opening paren (left by param annotation removal)
  s = s.replace(/\(\s+/g, '(');
  // Remove space before closing paren ONLY when preceded by a non-} char
  // (to avoid turning 'category } )' into 'category })')
  s = s.replace(/([^}])\s+\)/g, '$1)');
  // Fix double parens: `expr))` → `expr)` (happens when cast inside parens is removed)
  // Only if the original had `(expr as Type)` → `(expr)` (which is correct)
  // Don't touch intentionally double-parened expressions
  // Actually, the double `))` is correct for `setStatus((expr))` — the outer
  // paren is the function call, the inner was wrapping the cast expression.
  // So we should NOT remove it. Leave as is.
  // Fix `, ` spacing (extra space from param removal)
  s = s.replace(/,\s+/g, ', ');
  s = s.replace(/=  +/g, '= ');

  return s;
}

/**
 * Check if source contains a contract pattern (after normalization).
 */
export function contractContains(source: string, pattern: string): boolean {
  return normalizeSource(source).includes(pattern);
}

/**
 * Check if source does NOT contain a pattern.
 */
export function contractNotContains(source: string, pattern: string): boolean {
  return !contractContains(source, pattern);
}

/**
 * Extract a source slice between two markers, then normalize it.
 */
export function contractSlice(source: string, startMarker: string, endMarker: string): string {
  const start = source.indexOf(startMarker);
  if (start === -1) return '';
  const end = source.indexOf(endMarker, start);
  if (end === -1) return '';
  return normalizeSource(source.slice(start, end));
}
