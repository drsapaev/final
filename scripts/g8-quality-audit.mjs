/**
 * G8 Quality Audit — measures type system QUALITY, not just error count.
 *
 * Dimensions:
 *   1. Type Quality: unknown, assertions, Record<string, unknown>, index sigs
 *   2. API Stability: export surface changes, callback signatures, generics
 *   3. Runtime Risk: typeof, if(!x), fallbacks, optional chaining, silent failures
 *   4. Inference: explicit generics, degraded inference
 *   5. Technical Debt: unsafe patterns
 *
 * Usage: node scripts/g8-quality-audit.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend');
const SRC = join(FRONTEND_DIR, 'src');

function walk(dir, out = []) {
  try {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      const st = statSync(full);
      if (st.isDirectory()) {
        if (entry === 'node_modules' || entry === 'dist') continue;
        walk(full, out);
      } else if (st.isFile() && (full.endsWith('.ts') || full.endsWith('.tsx'))) {
        out.push(full);
      }
    }
  } catch { /* dir doesn't exist */ }
  return out;
}

function stripComments(text) {
  let out = text.replace(/\/\*[\s\S]*?\*\//g, '');
  out = out.replace(/(^|[^:])\/\/.*$/gm, '$1');
  return out;
}

// === Directories that were modified in G8 (strict islands) ===
const G8_DIRS = [
  'components/medical',
  'components/ui/macos',
  'components/queue',
  'components/registrar',
  'components/auth',
  'components/dialogs',
  'components/common/Loading.tsx',
  'components/common/RoleGuard.tsx',
  'components/AnimatedLoader.tsx',
  'components/Icon.tsx',
  'components/TwoFactorVerify.tsx',
  'constants/routes.ts',
  'utils/sanitizer.ts',
  'hooks/useSetupStatus.ts',
];

// Collect all files in G8 scope
const g8Files = [];
for (const dir of G8_DIRS) {
  const fullPath = join(SRC, dir);
  const st = statSync(fullPath);
  if (st.isDirectory()) {
    for (const f of walk(fullPath)) {
      if (!f.includes('__tests__') && !f.endsWith('.test.ts') && !f.endsWith('.test.tsx') && !f.endsWith('.stories.tsx')) {
        g8Files.push(f);
      }
    }
  } else if (st.isFile()) {
    g8Files.push(fullPath);
  }
}

console.log('G8 Quality Audit');
console.log('=================');
console.log('');
console.log(`Files in G8 scope: ${g8Files.length}`);
console.log('');

// === 1. Type Quality ===

let unknownCount = 0;
let assertionCount = 0;
let recordUnknownCount = 0;
let indexSignatureCount = 0;
let asAnyCount = 0;
let asRecordCount = 0;
let asStringCount = 0;
let asNumberCount = 0;
let asHTMLElementCount = 0;
let asErrorCount = 0;
let unionStringCount = 0; // `| string` in type positions

for (const file of g8Files) {
  const text = readFileSync(file, 'utf8');
  const code = stripComments(text);

  // Count `unknown` type annotations (not `Record<string, unknown>`)
  const unknownMatches = code.match(/:\s*unknown\b/g);
  if (unknownMatches) unknownCount += unknownMatches.length;

  // Count `as` assertions
  const asMatches = code.match(/\bas\s+[A-Z]/g);
  if (asMatches) assertionCount += asMatches.length;

  // Count `as any`
  const asAnyMatches = code.match(/\bas\s+any\b/g);
  if (asAnyMatches) asAnyCount += asAnyMatches.length;

  // Count `as Record<string, unknown>`
  const asRecordMatches = code.match(/\bas\s+Record<string,\s*unknown>/g);
  if (asRecordMatches) asRecordCount += asRecordMatches.length;

  // Count `as string`
  const asStringMatches = code.match(/\bas\s+string\b/g);
  if (asStringMatches) asStringCount += asStringMatches.length;

  // Count `as number`
  const asNumberMatches = code.match(/\bas\s+number\b/g);
  if (asNumberMatches) asNumberCount += asNumberMatches.length;

  // Count `as HTMLElement`
  const asHtmlMatches = code.match(/\bas\s+HTMLElement/g);
  if (asHtmlMatches) asHTMLElementCount += asHtmlMatches.length;

  // Count `as Error`
  const asErrorMatches = code.match(/\bas\s+Error/g);
  if (asErrorMatches) asErrorCount += asErrorMatches.length;

  // Count `Record<string, unknown>` in type positions
  const recordMatches = code.match(/Record<string,\s*unknown>/g);
  if (recordMatches) recordUnknownCount += recordMatches.length;

  // Count index signatures `[key: string]: unknown`
  const indexMatches = code.match(/\[key:\s*string\]:\s*unknown/g);
  if (indexMatches) indexSignatureCount += indexMatches.length;

  // Count `| string` in type positions (widened unions)
  const unionMatches = code.match(/\|\s*string\b/g);
  if (unionMatches) unionStringCount += unionMatches.length;
}

console.log('=== 1. Type Quality ===');
console.log('');
console.log(`  unknown type annotations:           ${unknownCount}`);
console.log(`  as assertions (total):              ${assertionCount}`);
console.log(`    - as any:                         ${asAnyCount}`);
console.log(`    - as Record<string, unknown>:     ${asRecordCount}`);
console.log(`    - as string:                      ${asStringCount}`);
console.log(`    - as number:                      ${asNumberCount}`);
console.log(`    - as HTMLElement:                 ${asHTMLElementCount}`);
console.log(`    - as Error:                       ${asErrorCount}`);
console.log(`  Record<string, unknown> usages:     ${recordUnknownCount}`);
console.log(`  [key: string]: unknown signatures:  ${indexSignatureCount}`);
console.log(`  | string (widened unions):          ${unionStringCount}`);
console.log('');

// === 2. API Stability ===

let exportInterfaceCount = 0;
let exportTypeCount = 0;
let restParamCount = 0; // ...args: unknown[]
let optionalCallbackCount = 0; // onFoo?: (...args: unknown[]) => void

for (const file of g8Files) {
  const text = readFileSync(file, 'utf8');
  const code = stripComments(text);

  const exportInterfaceMatches = code.match(/export\s+interface\s+\w+/g);
  if (exportInterfaceMatches) exportInterfaceCount += exportInterfaceMatches.length;

  const exportTypeMatches = code.match(/export\s+type\s+\w+/g);
  if (exportTypeMatches) exportTypeCount += exportTypeMatches.length;

  const restMatches = code.match(/\.\.\.\w+:\s*unknown\[\]/g);
  if (restMatches) restParamCount += restMatches.length;

  const optionalCbMatches = code.match(/on\w+\?:\s*\(\.\.\.\w+:\s*unknown\[\]\)\s*=>/g);
  if (optionalCbMatches) optionalCallbackCount += optionalCbMatches.length;
}

console.log('=== 2. API Stability ===');
console.log('');
console.log(`  Exported interfaces:                ${exportInterfaceCount}`);
console.log(`  Exported types:                     ${exportTypeCount}`);
console.log(`  Rest params (...args: unknown[]):   ${restParamCount}`);
console.log(`  Widened callbacks (...args):        ${optionalCallbackCount}`);
console.log('');

// === 3. Runtime Risk ===

let typeofCount = 0;
let ifNotXCount = 0;
let fallbackCount = 0; // || 'fallback'
let optionalChainingCount = 0;
let silentFailCount = 0; // catch {} (empty catch)
let numberCastCount = 0; // Number(x) for type coercion
let stringCastCount = 0; // String(x) for type coercion

for (const file of g8Files) {
  const text = readFileSync(file, 'utf8');
  const code = stripComments(text);

  const typeofMatches = code.match(/typeof\s+\w+/g);
  if (typeofMatches) typeofCount += typeofMatches.length;

  const ifNotMatches = code.match(/if\s*\(!\w+\)/g);
  if (ifNotMatches) ifNotXCount += ifNotMatches.length;

  const fallbackMatches = code.match(/\|\|\s*['"]/g);
  if (fallbackMatches) fallbackCount += fallbackMatches.length;

  const optionalMatches = code.match(/\?\./g);
  if (optionalMatches) optionalChainingCount += optionalMatches.length;

  const silentMatches = code.match(/catch\s*\{\s*\}/g);
  if (silentMatches) silentFailCount += silentMatches.length;

  const numberMatches = code.match(/Number\(/g);
  if (numberMatches) numberCastCount += numberMatches.length;

  const stringMatches = code.match(/String\(/g);
  if (stringMatches) stringCastCount += stringMatches.length;
}

console.log('=== 3. Runtime Risk ===');
console.log('');
console.log(`  typeof checks:                      ${typeofCount}`);
console.log(`  if (!x) null guards:                ${ifNotXCount}`);
console.log(`  || 'fallback' patterns:             ${fallbackCount}`);
console.log(`  Optional chaining (?.):             ${optionalChainingCount}`);
console.log(`  Silent catch (catch {}):            ${silentFailCount}`);
console.log(`  Number() casts (coercion):          ${numberCastCount}`);
console.log(`  String() casts (coercion):          ${stringCastCount}`);
console.log('');

// === 4. Inference ===

let explicitGenericCount = 0; // useState<T>(...)
let asTypeAnnotationCount = 0; // const x: T = ...
let recordAnyCount = 0; // Record<string, any>

for (const file of g8Files) {
  const text = readFileSync(file, 'utf8');
  const code = stripComments(text);

  const genericMatches = code.match(/useState<[^>]+>/g);
  if (genericMatches) explicitGenericCount += genericMatches.length;

  const annotationMatches = code.match(/:\s*(?:Record|Partial|Readonly|Pick|Omit|Array|React\.)/g);
  if (annotationMatches) asTypeAnnotationCount += annotationMatches.length;

  const recordAnyMatches = code.match(/Record<string,\s*any>/g);
  if (recordAnyMatches) recordAnyCount += recordAnyMatches.length;
}

console.log('=== 4. Inference ===');
console.log('');
console.log(`  Explicit useState<T> generics:      ${explicitGenericCount}`);
console.log(`  Explicit type annotations:          ${asTypeAnnotationCount}`);
console.log(`  Record<string, any> (should be unknown): ${recordAnyCount}`);
console.log('');

// === 5. Technical Debt ===

let deprecatedCount = 0;
let todoCount = 0;
let eslintDisableCount = 0;
let anyInPropsCount = 0;
let componentTypeAnyCount = 0;

for (const file of g8Files) {
  const text = readFileSync(file, 'utf8');
  const code = stripComments(text);

  const deprecatedMatches = code.match(/@deprecated/g);
  if (deprecatedMatches) deprecatedCount += deprecatedMatches.length;

  const todoMatches = code.match(/TODO|FIXME|HACK/g);
  if (todoMatches) todoCount += todoMatches.length;

  const eslintMatches = code.match(/eslint-disable/g);
  if (eslintMatches) eslintDisableCount += eslintMatches.length;

  const anyPropsMatches = code.match(/\?\s*:\s*any\b/g);
  if (anyPropsMatches) anyInPropsCount += anyPropsMatches.length;

  const compAnyMatches = code.match(/ComponentType<any>/g);
  if (compAnyMatches) componentTypeAnyCount += compAnyMatches.length;
}

console.log('=== 5. Technical Debt ===');
console.log('');
console.log(`  @deprecated annotations:            ${deprecatedCount}`);
console.log(`  TODO/FIXME/HACK markers:             ${todoCount}`);
console.log(`  eslint-disable directives:           ${eslintDisableCount}`);
console.log(`  Props with 'any' type:              ${anyInPropsCount}`);
console.log(`  ComponentType<any>:                 ${componentTypeAnyCount}`);
console.log('');

// === Summary ===

console.log('=== Summary ===');
console.log('');
const totalAssertions = asAnyCount + asRecordCount + asStringCount + asNumberCount + asHTMLElementCount + asErrorCount;
console.log(`  Total unsafe assertions:            ${totalAssertions}`);
console.log(`  Total widened types (unknown/any):  ${unknownCount + asAnyCount + recordAnyCount}`);
console.log(`  Total coercion casts:               ${numberCastCount + stringCastCount}`);
console.log(`  Total widened callbacks:            ${restParamCount + optionalCallbackCount}`);
console.log('');
console.log('Risk assessment:');
const riskScore = (totalAssertions * 2) + (asAnyCount * 5) + (recordAnyCount * 3) + (silentFailCount * 3) + (componentTypeAnyCount * 2);
console.log(`  Risk score (lower is better):       ${riskScore}`);
if (riskScore < 20) console.log('  → LOW risk — type quality is good');
else if (riskScore < 50) console.log('  → MEDIUM risk — some quality debt');
else console.log('  → HIGH risk — significant quality debt');
