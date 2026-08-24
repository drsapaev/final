#!/usr/bin/env node
/**
 * ui-baseline.mjs — Phase 0 machine-checkable UI baseline for UI_AUDIT_PLAN.md
 *
 * Measures the 16 metric families from the Phase 0 checklist:
 *   token systems / undefined CSS vars / hardcoded colors / inline styles /
 *   !important / modal implementations / toast systems / tab systems /
 *   empty-state APIs / breakpoints / duplicate keyframes / dead-code candidates /
 *   navigation i18n / a11y CSS / dark-theme behavior (+ import graph stats).
 *
 * Ratchet semantics (follows scripts/a11y/icon-only-controls-baseline.json pattern):
 *   - baseline JSON is committed (scripts/ui-baseline.json)
 *   - `--check` recomputes metrics and FAILS (exit 1) if any count-regression
 *     is detected vs the committed baseline; metrics may only improve (decrease)
 *   - intentional baseline moves require `--write-baseline` + justification in PR
 *
 * Usage:
 *   node scripts/ui-baseline.mjs                     # human-readable report
 *   node scripts/ui-baseline.mjs --json              # JSON to stdout
 *   node scripts/ui-baseline.mjs --write-baseline    # (re)write scripts/ui-baseline.json
 *   node scripts/ui-baseline.mjs --check             # ratchet gate (exit 1 on regression)
 *
 * Zero dependencies (pure node:fs / node:path), Node >= 18.
 */

import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { resolve, dirname, join, relative, extname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
/**
 * C-3-A.1: UI_BASELINE_ROOT lets tests point the scanner at a fixture
 * project instead of the real frontend (see uiBaselineScanner.test.ts).
 */
const FRONTEND = process.env.UI_BASELINE_ROOT || resolve(__dirname, '..');
const SRC = join(FRONTEND, 'src');
const DEFAULT_BASELINE = join(__dirname, 'ui-baseline.json');

// ─── CLI ─────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const modeJson = args.includes('--json');
const modeWrite = args.includes('--write-baseline') || args.some((a) => a.startsWith('--write-baseline='));
const modeCheck = args.includes('--check') || args.some((a) => a.startsWith('--check='));
const baselineArg = args.find((a) => a.startsWith('--check=') || a.startsWith('--write-baseline='));
const baselinePath = baselineArg ? resolve(FRONTEND, baselineArg.split('=')[1]) : DEFAULT_BASELINE;

// ─── File collection ─────────────────────────────────────────────────────────

const SKIP_DIRS = new Set(['node_modules', '__tests__', '__mocks__', 'dist', 'coverage']);
const CODE_EXT = new Set(['.ts', '.tsx', '.js', '.jsx']);
const CSS_EXT = new Set(['.css']);

function walk(dir, out) {
  for (const entry of readdirSync(dir).sort()) {
    if (entry.startsWith('.') || SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else {
      const ext = extname(entry);
      if (CODE_EXT.has(ext) || CSS_EXT.has(ext)) out.push(full);
    }
  }
  return out;
}

const allFiles = walk(SRC, []);
const cssFiles = allFiles.filter((f) => CSS_EXT.has(extname(f)));
const codeFiles = allFiles.filter((f) => {
  const ext = extname(f);
  if (!CODE_EXT.has(ext)) return false;
  const base = basename(f);
  if (base.endsWith('.d.ts')) return false;
  if (/\.(test|spec)\.[jt]sx?$/.test(base)) return false;
  if (base.endsWith('.stories.tsx') || base.endsWith('.stories.jsx')) return false;
  return true;
});
const tsxFiles = codeFiles.filter((f) => ['.tsx', '.jsx'].includes(extname(f)));

const rel = (f) => relative(FRONTEND, f).split('\\').join('/');
const fileText = new Map();
function text(f) {
  if (!fileText.has(f)) fileText.set(f, readFileSync(f, 'utf-8'));
  return fileText.get(f);
}
function stripCssComments(s) {
  return s.replace(/\/\*[\s\S]*?\*\//g, '');
}

/**
 * C-3-A.1 fix: strip JS/TS comments BEFORE token counting, so commented-out
 * `var(--foo)` no longer counts as a usage (scanner false-positive class 1).
 */
function stripJsComments(s) {
  return s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

// ─── 1. Token systems ────────────────────────────────────────────────────────

const TOKEN_DEF = /(--[A-Za-z0-9_-]+)\s*:\s*/g;
const definitionsByFile = new Map(); // cssFile -> Set(names)
const definitionCountByFile = new Map(); // cssFile -> total definitions

for (const f of cssFiles) {
  const body = stripCssComments(text(f));
  const names = new Set();
  let m;
  TOKEN_DEF.lastIndex = 0;
  let total = 0;
  while ((m = TOKEN_DEF.exec(body)) !== null) {
    names.add(m[1]);
    total++;
  }
  definitionsByFile.set(f, names);
  definitionCountByFile.set(f, total);
}

const tokenSourceFiles = [...definitionCountByFile.entries()]
  .filter(([, total]) => total >= 10)
  .map(([f, total]) => ({ file: rel(f), definitions: total }))
  .sort((a, b) => b.definitions - a.definitions || a.file.localeCompare(b.file));

const familyOf = (name) => {
  if (name.startsWith('--mac-')) return 'mac';
  if (name.startsWith('--color-')) return 'color';
  if (name.startsWith('--surface-')) return 'surface';
  if (name.startsWith('--admin-')) return 'admin';
  if (name.startsWith('--landing-')) return 'landing';
  if (name.startsWith('--board-')) return 'board';
  if (name.startsWith('--accent')) return 'accent-legacy';
  if (name.startsWith('--bg-')) return 'bg-legacy';
  if (name.startsWith('--text-')) return 'text-legacy';
  if (name.startsWith('--z-')) return 'z-emr';
  if (name.startsWith('--qj-')) return 'qj';
  if (name.startsWith('--pp-')) return 'pp';
  return 'other';
};
const allDefinedNames = new Set();
for (const names of definitionsByFile.values()) for (const n of names) allDefinedNames.add(n);
const tokenFamilies = {};
for (const n of allDefinedNames) {
  const fam = familyOf(n);
  tokenFamilies[fam] = (tokenFamilies[fam] || 0) + 1;
}

const defLocations = new Map(); // name -> Set(files)
for (const [f, names] of definitionsByFile) {
  for (const n of names) {
    if (!defLocations.has(n)) defLocations.set(n, new Set());
    defLocations.get(n).add(rel(f));
  }
}
const duplicateTokenNames = [...defLocations.entries()]
  .filter(([, files]) => files.size > 1)
  .map(([name, files]) => ({ name, files: [...files].sort() }))
  .sort((a, b) => b.files.length - a.files.length || a.name.localeCompare(b.name));

function importerCount(needle) {
  const re = new RegExp(`from\\s+['"][^'"]*${needle}['"]`);
  let count = 0;
  for (const f of codeFiles) if (re.test(text(f))) count++;
  return count;
}
const jsTokenSources = {
  'theme/tokens.ts': existsSync(join(SRC, 'theme/tokens.ts')) ? importerCount('theme/tokens') : -1,
  'theme/tokens-legacy.ts': existsSync(join(SRC, 'theme/tokens-legacy.ts')) ? importerCount('tokens-legacy') : -1,
  'theme/tokens/ dir': existsSync(join(SRC, 'theme/tokens')) ? importerCount('theme/tokens') : -1,
};

// ─── 2. Undefined CSS variables ──────────────────────────────────────────────

const VAR_USE = /var\(\s*(--[A-Za-z0-9_-]+)/g;
const VAR_USE_NO_FALLBACK = /var\(\s*--[A-Za-z0-9_-]+\s*\)/g;
const SETPROP = /setProperty\(\s*['"](--[A-Za-z0-9_-]+)['"]/g;

/**
 * C-3-A.1 fix: inline custom-property writers `style={{ '--foo': value }}`
 * are RUNTIME SLOTS intentionally undefined in CSS (written per-instance),
 * NOT missing tokens (false-positive class 2: e.g. --admin-col0 in
 * AdminFinanceOverview.tsx, --doctor-gradient-from/to in DoctorPanel.tsx).
 */
const INLINE_PROP_WRITER = /['"`](--[A-Za-z0-9_-]+)['"`]\s*:\s*[^;\n]*[,}]/g;
const bodyOf = (f) =>
  extname(f) === '.css' ? stripCssComments(text(f)) : stripJsComments(text(f));

const runtimeDefined = new Set(); // setProperty(...) writers
for (const f of codeFiles) {
  const body = bodyOf(f);
  let m;
  SETPROP.lastIndex = 0;
  while ((m = SETPROP.exec(body)) !== null) runtimeDefined.add(m[1]);
}
// inline `{'--foo': ...}` writers (style objects in TSX/TS)
for (const f of tsxFiles) {
  const body = bodyOf(f);
  let m;
  INLINE_PROP_WRITER.lastIndex = 0;
  while ((m = INLINE_PROP_WRITER.exec(body)) !== null) runtimeDefined.add(m[1]);
}

const usedVars = new Set();
let varUsages = 0;
for (const f of [...cssFiles, ...codeFiles]) {
  const body = bodyOf(f); // C-3-A.1: JS/TS comments stripped for code files
  let m;
  VAR_USE.lastIndex = 0;
  while ((m = VAR_USE.exec(body)) !== null) {
    usedVars.add(m[1]);
    varUsages++;
  }
}
let varUsagesNoFallback = 0;
for (const f of [...cssFiles, ...codeFiles]) {
  const body = bodyOf(f); // C-3-A.1: same comment-stripping as varUsages
  varUsagesNoFallback += (body.match(VAR_USE_NO_FALLBACK) || []).length;
}
const undefinedVarNames = [...usedVars]
  .filter((n) => !allDefinedNames.has(n) && !runtimeDefined.has(n))
  .sort();
let undefinedVarUsages = 0;
for (const n of undefinedVarNames) {
  const esc = n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`var\\(\\s*${esc}[\\s,)]`, 'g');
  for (const f of [...cssFiles, ...codeFiles]) {
    // C-3-A.1: count on comment-stripped bodies (was raw text)
    undefinedVarUsages += (bodyOf(f).match(re) || []).length;
  }
}

// ─── 3. Hardcoded colors ─────────────────────────────────────────────────────

const HEX = /#[0-9a-fA-F]{3,8}\b/g;
const TOKENS_CSS = rel(join(SRC, 'design-system/tokens.css'));
let cssHexOutsideTokens = 0;
for (const f of cssFiles) {
  if (rel(f) === TOKENS_CSS) continue;
  cssHexOutsideTokens += (stripCssComments(text(f)).match(HEX) || []).length;
}
let tsxHex = 0;
let tsxHexFiles = 0;
for (const f of tsxFiles) {
  const n = (text(f).match(HEX) || []).length;
  if (n) {
    tsxHex += n;
    tsxHexFiles++;
  }
}

// ─── 4. Inline styles ────────────────────────────────────────────────────────

let inlineStyles = 0;
let inlineStyleFiles = 0;
for (const f of tsxFiles) {
  const n = (text(f).match(/style=\{\{/g) || []).length;
  if (n) {
    inlineStyles += n;
    inlineStyleFiles++;
  }
}

// ─── 5. !important ───────────────────────────────────────────────────────────

let cssImportant = 0;
for (const f of cssFiles) cssImportant += (stripCssComments(text(f)).match(/!important/g) || []).length;
let tsxImportant = 0;
for (const f of tsxFiles) tsxImportant += (text(f).match(/!important/g) || []).length;

// ─── 6/7/8/9. Primitive adoption (modals, toasts, tabs, empty states) ────────

const KIT_DIR = join(SRC, 'components/ui/macos');
const modalFilesOutsideKit = codeFiles
  .filter((f) => !f.startsWith(KIT_DIR) && /(Modal|Dialog)\.tsx?$/.test(basename(f)))
  .map(rel)
  .sort();

// parse named imports from ui/macos per file
const kitImportsByFile = new Map(); // file -> Set(imported names)
for (const f of codeFiles) {
  const body = text(f);
  const re = /import\s+\{([^}]+)\}\s+from\s+['"][^'"]*ui\/macos[^'"]*['"]/g;
  let m;
  const names = new Set();
  while ((m = re.exec(body)) !== null) {
    for (const part of m[1].split(',')) {
      const n = part.trim().split(/\s+as\s+/)[0].trim();
      if (n) names.add(n);
    }
  }
  if (names.size) kitImportsByFile.set(f, names);
}
const kitImporters = (name) =>
  [...kitImportsByFile.entries()].filter(([, names]) => names.has(name)).map(([f]) => rel(f)).length;

const importersOf = (needle) => {
  const re = new RegExp(`from\\s+['"][^'"]*${needle}['"]`);
  let count = 0;
  for (const f of codeFiles) if (re.test(text(f))) count++;
  return count;
};

let tablistRoles = 0;
for (const f of tsxFiles) tablistRoles += (text(f).match(/role="tablist"/g) || []).length;

// ─── 10. Breakpoints ─────────────────────────────────────────────────────────

const bpSet = new Set();
for (const f of cssFiles) {
  const body = stripCssComments(text(f));
  // only @media preludes, not element min-width/max-width properties
  const mediaRe = /@media[^{]+/g;
  let mm;
  while ((mm = mediaRe.exec(body)) !== null) {
    const prelude = mm[0];
    const re = /(?:min|max)-width:\s*(\d+(?:\.\d+)?)(px|rem)/g;
    let m;
    while ((m = re.exec(prelude)) !== null) {
      const val = m[2] === 'rem' ? Math.round(parseFloat(m[1]) * 16) : parseFloat(m[1]);
      bpSet.add(val);
    }
  }
}
const breakpoints = [...bpSet].sort((a, b) => a - b);

// ─── 11. Duplicate @keyframes ────────────────────────────────────────────────

const keyframeFiles = new Map(); // name -> Set(files)
for (const f of cssFiles) {
  const body = stripCssComments(text(f));
  const re = /@keyframes\s+([A-Za-z0-9_-]+)/g;
  let m;
  while ((m = re.exec(body)) !== null) {
    if (!keyframeFiles.has(m[1])) keyframeFiles.set(m[1], new Set());
    keyframeFiles.get(m[1]).add(rel(f));
  }
}
const duplicateKeyframes = [...keyframeFiles.entries()]
  .filter(([, files]) => files.size > 1)
  .map(([name, files]) => ({ name, files: files.size }))
  .sort((a, b) => b.files - a.files || a.name.localeCompare(b.name));

// ─── 12. Dead-code candidates (import-graph reachability) ────────────────────

const IMPORT_SPEC = /(?:from\s+|import\(\s*|require\(\s*|import\s+)['"]([.@][^'"]+)['"]/g;
const RESOLVE_EXT = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'];

function resolveSpec(fromFile, spec) {
  // vite/tsconfig path alias: "@/*" -> "./src/*" (see vite.config.ts alias + tsconfig paths)
  const base = spec.startsWith('@/') ? join(SRC, spec.slice(2)) : resolve(dirname(fromFile), spec);
  const candidates = [base, ...RESOLVE_EXT.map((e) => base + e)];
  for (const e of RESOLVE_EXT) candidates.push(join(base, `index${e}`));
  for (const c of candidates) if (existsSync(c) && statSync(c).isFile()) return c;
  return null;
}

const graphRoots = [join(SRC, 'main.tsx')].filter(existsSync);
const reachable = new Set();
const queue = [...graphRoots];
while (queue.length) {
  const f = queue.pop();
  if (reachable.has(f)) continue;
  reachable.add(f);
  if (!codeFiles.includes(f)) continue;
  const body = text(f);
  let m;
  IMPORT_SPEC.lastIndex = 0;
  while ((m = IMPORT_SPEC.exec(body)) !== null) {
    const t = resolveSpec(f, m[1]);
    if (t) queue.push(t);
  }
}

// directories excluded from dead-metric: i18n locales (dynamic loading), type decls
const DEAD_EXCLUDE = [/src[\\/]i18n[\\/]/, /src[\\/]types[\\/]/, /src[\\/]test[\\/]/];
const unreferencedFiles = codeFiles
  .filter((f) => !reachable.has(f))
  .filter((f) => !DEAD_EXCLUDE.some((re) => re.test(f)))
  .map(rel)
  .sort();

// ─── 13. Navigation i18n ─────────────────────────────────────────────────────

const routeRegistryPath = join(SRC, 'routing/routeRegistry.ts');
let navCyrillicLabels = 0;
if (existsSync(routeRegistryPath)) {
  navCyrillicLabels = (text(routeRegistryPath).match(/label:\s*['"][^'"]*[\u0400-\u04FF]/g) || []).length;
}

// ─── 14. A11y CSS ────────────────────────────────────────────────────────────

let a11yCssImports = 0;
for (const f of [...codeFiles]) {
  a11yCssImports += (text(f).match(/['"][^'"]*accessibility\.css['"]/g) || []).length;
}
const indexHtmlPath = join(FRONTEND, 'index.html');
if (existsSync(indexHtmlPath)) {
  a11yCssImports += (readFileSync(indexHtmlPath, 'utf-8').match(/accessibility\.css/g) || []).length;
}

// ─── 15. Dark-theme behavior ─────────────────────────────────────────────────

let cssFilesWithDarkSelectors = 0;
for (const f of cssFiles) {
  if (/\.dark-theme|\[data-theme="dark"\]/.test(text(f))) cssFilesWithDarkSelectors++;
}
let prefersSchemeRootBlocks = 0;
for (const f of cssFiles) {
  const body = stripCssComments(text(f));
  if (/@media[^{]*prefers-color-scheme[^{]*\{\s*:root/.test(body)) prefersSchemeRootBlocks++;
}
let isDarkBranches = 0;
for (const f of tsxFiles) isDarkBranches += (text(f).match(/\bisDark\b/g) || []).length;
let inlineStyleAttributePatches = 0;
for (const f of cssFiles) {
  inlineStyleAttributePatches += (stripCssComments(text(f)).match(/\[style\*=/g) || []).length;
}

// ─── Assemble metrics ────────────────────────────────────────────────────────

function gitCommit() {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: FRONTEND, encoding: 'utf-8' }).trim();
  } catch {
    return 'unknown';
  }
}

const metrics = {
  // 1. token systems
  tokenSourceFiles: tokenSourceFiles,
  tokenSourceFileCount: tokenSourceFiles.length,
  tokenFamilies: tokenFamilies,
  tokenFamilyCount: Object.keys(tokenFamilies).length,
  duplicateTokenNameCount: duplicateTokenNames.length,
  jsTokenSources: jsTokenSources,
  // 2. undefined css vars
  undefinedVarNameCount: undefinedVarNames.length,
  undefinedVarUsages: undefinedVarUsages,
  undefinedVarNames: undefinedVarNames,
  varUsagesTotal: varUsages,
  varUsagesNoFallback: varUsagesNoFallback,
  // 3. hardcoded colors
  cssHexOutsideTokens: cssHexOutsideTokens,
  tsxHex: tsxHex,
  tsxHexFiles: tsxHexFiles,
  // 4. inline styles
  inlineStyles: inlineStyles,
  inlineStyleFiles: inlineStyleFiles,
  // 5. !important
  cssImportant: cssImportant,
  tsxImportant: tsxImportant,
  // 6. modals
  modalFilesOutsideKit: modalFilesOutsideKit,
  modalFilesOutsideKitCount: modalFilesOutsideKit.length,
  kitModalImporters: kitImporters('Modal'),
  kitDialogImporters: kitImporters('Dialog'),
  // 7. toasts
  reactToastifyImporters: importersOf('react-toastify'),
  notifyServiceImporters: importersOf('services/notify'),
  customToastProviderImporters: importersOf('common/Toast'),
  // 8. tabs
  macTabImporters: kitImporters('MacOSTab'),
  modernTabsImporters: importersOf('ModernTabs'),
  tablistRoles: tablistRoles,
  // 9. empty-state APIs
  macEmptyStateImporters: kitImporters('MacOSEmptyState'),
  appEmptyImporters: kitImporters('AppEmpty'),
  appLoadingImporters: kitImporters('AppLoading'),
  stateWrapperImporters: importersOf('StateWrapper'),
  // 10. breakpoints
  breakpointsUnique: breakpoints,
  breakpointsUniqueCount: breakpoints.length,
  // 11. duplicate keyframes
  duplicateKeyframes: duplicateKeyframes,
  duplicateKeyframesNameCount: duplicateKeyframes.length,
  // 12. dead code
  unreferencedFiles: unreferencedFiles,
  unreferencedFileCount: unreferencedFiles.length,
  // 13. nav i18n
  navCyrillicLabels: navCyrillicLabels,
  // 14. a11y css
  a11yCssImported: a11yCssImports > 0,
  // 15. dark theme
  cssFilesWithDarkSelectors: cssFilesWithDarkSelectors,
  prefersSchemeRootBlocks: prefersSchemeRootBlocks,
  isDarkBranches: isDarkBranches,
  inlineStyleAttributePatches: inlineStyleAttributePatches,
};

// ─── Ratchet comparators ─────────────────────────────────────────────────────
// "lower is better" numeric fields; list length is the ratchet value;
// a11yCssImported is "true is better".

const RATCHET_NUMERIC = [
  'tokenSourceFileCount',
  'duplicateTokenNameCount',
  'undefinedVarNameCount',
  'undefinedVarUsages',
  'varUsagesNoFallback',
  'cssHexOutsideTokens',
  'tsxHex',
  'tsxHexFiles',
  'inlineStyles',
  'inlineStyleFiles',
  'cssImportant',
  'tsxImportant',
  'modalFilesOutsideKitCount',
  'reactToastifyImporters',
  'customToastProviderImporters',
  'tablistRoles',
  'stateWrapperImporters',
  'breakpointsUniqueCount',
  'duplicateKeyframesNameCount',
  'unreferencedFileCount',
  'navCyrillicLabels',
  'cssFilesWithDarkSelectors',
  'prefersSchemeRootBlocks',
  'isDarkBranches',
  'inlineStyleAttributePatches',
];
const RATCHET_LIST_LEN = ['undefinedVarNames', 'unreferencedFiles', 'breakpointsUnique'];
// Note: for lists, growing length fails; individual entries are reported as info.

function compareMetrics(baseline, current) {
  const regressions = [];
  const improvements = [];
  for (const key of RATCHET_NUMERIC) {
    const b = baseline.metrics?.[key];
    const c = current[key];
    if (typeof b !== 'number' || typeof c !== 'number') continue;
    if (c > b) regressions.push(`${key}: ${b} → ${c} (+${c - b})`);
    else if (c < b) improvements.push(`${key}: ${b} → ${c} (-${b - c})`);
  }
  for (const key of RATCHET_LIST_LEN) {
    const b = baseline.metrics?.[key];
    const c = current[key];
    if (!Array.isArray(b) || !Array.isArray(c)) continue;
    if (c.length > b.length) {
      const added = c.filter((x) => !b.includes(x));
      regressions.push(`${key}: length ${b.length} → ${c.length}${added.length ? ` (added: ${added.slice(0, 5).join(', ')}${added.length > 5 ? ' …' : ''})` : ''}`);
    } else if (c.length < b.length) improvements.push(`${key}: length ${b.length} → ${c.length}`);
  }
  if (baseline.metrics?.a11yCssImported === true && current.a11yCssImported === false) {
    regressions.push('a11yCssImported: true → false');
  } else if (baseline.metrics?.a11yCssImported === false && current.a11yCssImported === true) {
    improvements.push('a11yCssImported: false → true');
  }
  return { regressions, improvements };
}

// ─── Output ──────────────────────────────────────────────────────────────────

const baselineDoc = {
  version: 1,
  description:
    'UI_AUDIT_PLAN.md Phase 0 baseline. Ratchet: values may only improve (decrease). ' +
    'To move the baseline intentionally run: node scripts/ui-baseline.mjs --write-baseline ' +
    'and justify the change in the PR description.',
  generatedAt: new Date().toISOString(),
  gitCommit: gitCommit(),
  metrics,
};

if (modeJson) {
  console.log(JSON.stringify(baselineDoc, null, 2));
} else if (!modeCheck && !modeWrite) {
  // human-readable report
  const p = (label, v) => console.log(String(label).padEnd(38) + String(v));
  console.log('UI baseline — UI_AUDIT_PLAN.md Phase 0');
  console.log('='.repeat(72));
  p('Token source files (>=10 defs)', tokenSourceFiles.length);
  for (const t of tokenSourceFiles) console.log(`   - ${t.file} (${t.definitions} defs)`);
  console.log(`   families: ${JSON.stringify(tokenFamilies)}`);
  p('Duplicate token names (def in >1 file)', duplicateTokenNames.length);
  p('JS token sources', JSON.stringify(jsTokenSources));
  p('Undefined CSS var names', `${undefinedVarNames.length} (usages: ${undefinedVarUsages})`);
  console.log(`   top: ${undefinedVarNames.slice(0, 10).join(', ')}${undefinedVarNames.length > 10 ? ' …' : ''}`);
  p('var() usages total / without fallback', `${varUsages} / ${varUsagesNoFallback}`);
  p('CSS hex outside tokens.css', cssHexOutsideTokens);
  p('TSX hex / files', `${tsxHex} / ${tsxHexFiles}`);
  p('Inline style={{}} / files', `${inlineStyles} / ${inlineStyleFiles}`);
  p('!important (css / tsx)', `${cssImportant} / ${tsxImportant}`);
  p('Modal/Dialog files outside kit', `${modalFilesOutsideKit.length}: ${modalFilesOutsideKit.join(', ')}`);
  p('Kit Modal / Dialog importers', `${kitImporters('Modal')} / ${kitImporters('Dialog')}`);
  p('Toast: react-toastify / notify / custom', `${importersOf('react-toastify')} / ${importersOf('services/notify')} / ${importersOf('common/Toast')}`);
  p('Tabs: MacOSTab / ModernTabs / role=tablist', `${kitImporters('MacOSTab')} / ${importersOf('ModernTabs')} / ${tablistRoles}`);
  p('Empty: MacOSEmptyState / AppEmpty / AppLoading / StateWrapper', `${kitImporters('MacOSEmptyState')} / ${kitImporters('AppEmpty')} / ${kitImporters('AppLoading')} / ${importersOf('StateWrapper')}`);
  p('Breakpoints unique', `${breakpoints.length}: ${breakpoints.join(', ')}`);
  p('Duplicate @keyframes names', duplicateKeyframes.length ? duplicateKeyframes.map((k) => `${k.name}×${k.files}`).join(', ') : 'none');
  p('Unreferenced files (import graph)', `${unreferencedFiles.length}`);
  console.log(`   ${unreferencedFiles.slice(0, 20).join('\n   ')}`);
  p('Cyrillic labels in routeRegistry', navCyrillicLabels);
  p('accessibility.css imported', a11yCssImports > 0 ? 'YES' : 'NO');
  p('Dark: css files w/ dark selectors', cssFilesWithDarkSelectors);
  p('Dark: prefers-color-scheme :root blocks', prefersSchemeRootBlocks);
  p('Dark: isDark branches in TSX', isDarkBranches);
  p('Dark: [style*=] attribute patches', inlineStyleAttributePatches);
}

if (modeWrite) {
  writeFileSync(baselinePath, JSON.stringify(baselineDoc, null, 2) + '\n');
  console.log(`\nBaseline written: ${relative(FRONTEND, baselinePath)} (commit ${baselineDoc.gitCommit})`);
}

if (modeCheck) {
  if (!existsSync(baselinePath)) {
    console.error(`FAIL: baseline not found: ${baselinePath}`);
    console.error('Generate it: node scripts/ui-baseline.mjs --write-baseline');
    process.exit(1);
  }
  const baseline = JSON.parse(readFileSync(baselinePath, 'utf-8'));
  const { regressions, improvements } = compareMetrics(baseline, metrics);
  console.log('UI baseline ratchet check (UI_AUDIT_PLAN.md Phase 0)');
  console.log('='.repeat(72));
  console.log(`Baseline: commit ${baseline.gitCommit} (${baseline.generatedAt})`);
  console.log(`Current:  commit ${baselineDoc.gitCommit}`);
  if (improvements.length) {
    console.log(`\nImprovements (${improvements.length}):`);
    for (const i of improvements) console.log(`  ↓ ${i}`);
  }
  if (regressions.length) {
    console.error(`\nREGRESSIONS (${regressions.length}):`);
    for (const r of regressions) console.error(`  ✗ ${r}`);
    console.error('\nRatchet policy: metrics may only improve. If the increase is intentional,');
    console.error('update the baseline via --write-baseline and justify it in the PR description.');
    process.exit(1);
  }
  console.log('\nPASS: no ratchet regressions.');
  process.exit(0);
}
