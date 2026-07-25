#!/usr/bin/env node
/**
 * Domain Adoption Index (DAI) + Strict Readiness Score (SRS)
 *
 * Two new metrics proposed in the G8 strategy review:
 *
 * 1. DAI (Domain Adoption Index) — project-wide
 *    DAI = (files importing from types/domain) / (local interface declarations)
 *    Measures: is the domain layer actually being adopted, or just exists?
 *    Current baseline: ~5% (30 consumers / 580 local interfaces)
 *    Target: 80%
 *
 * 2. SRS (Strict Readiness Score) — per functional area (island)
 *    SRS = average of 4 sub-scores:
 *      - strictErrors:   100% if 0 errors, else 100 * (1 - errors/100) capped at 0
 *      - domainAdoption: % of files in island importing from types/domain
 *      - noDuplicates:   100% if 0 local domain-duplicate interfaces, else penalty
 *      - noDtoImports:   100% if 0 *Dto imports in island, else penalty
 *    SRS = 100% means the island is ready for strict gate.
 *
 * Usage:
 *   node scripts/adoption-index.mjs              # project-wide DAI + all islands SRS
 *   node scripts/adoption-index.mjs components/medical  # single island SRS
 */

import { readFileSync, readdirSync, statSync, writeFileSync, unlinkSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { execSync } from 'child_process';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, '..', 'frontend');
const SRC = join(FRONTEND_DIR, 'src');
const TSCONFIG_PATH = join(FRONTEND_DIR, 'tsconfig.json');

// Functional islands — cohesive feature areas that can be strict-cleaned
// independently. Each island is a self-contained feature vertical.
const ISLANDS = [
  'components/medical',
  'components/queue',
  'components/patient',
  'components/auth',
  'components/registrar',
  'components/emr-v2',
  'components/wizard',
  'components/payment',
  'components/laboratory',
  'components/admin',
  'components/common',
  'components/ui',
  'pages/registrar',
  'pages/__tests__',
];

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

// === DAI: project-wide Domain Adoption Index ===

function computeDAI() {
  const allFiles = walk(SRC);
  let consumers = 0;
  let localInterfaces = 0;

  for (const file of allFiles) {
    const rel = relative(SRC, file).split(sep).join('/');
    if (rel.startsWith('types/domain/')) continue;
    if (/\.test\./.test(rel) || rel.includes('__tests__/')) continue;

    const text = readFileSync(file, 'utf8');
    if (/from\s+['"][^'"]*(?:types\/domain|\/domain\/)/.test(text)) {
      consumers++;
    }

    // Count local interface/type declarations (excluding domain files)
    const code = stripComments(text);
    const declMatches = code.match(/(?:interface|type)\s+[A-Z][A-Za-z0-9_]+/g);
    if (declMatches) localInterfaces += declMatches.length;
  }

  const dai = localInterfaces === 0 ? 0 : (consumers / localInterfaces) * 100;
  return { consumers, localInterfaces, dai };
}

// === SRS: per-island Strict Readiness Score ===

function countStrictErrorsSync(dir) {
  const strictConfig = {
    extends: './tsconfig.json',
    compilerOptions: { strict: true, noImplicitAny: true, strictNullChecks: true },
    include: [`${dir}/**/*.ts`, `${dir}/**/*.tsx`],
    exclude: ['node_modules', 'dist', 'e2e'],
  };
  const strictConfigPath = join(FRONTEND_DIR, 'tsconfig.srs-tmp.json');
  writeFileSync(strictConfigPath, JSON.stringify(strictConfig, null, 2));
  try {
    try {
      execSync('npx tsc --noEmit --pretty false -p tsconfig.srs-tmp.json 2>&1', {
        cwd: FRONTEND_DIR,
        encoding: 'utf-8',
        maxBuffer: 1024 * 1024 * 20,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      return 0;
    } catch (e) {
      const output = e.stdout?.toString() || e.stderr?.toString() || '';
      return output.split('\n').filter(l => l.includes('error TS')).length;
    }
  } finally {
    try { unlinkSync(strictConfigPath); } catch {}
  }
}

function computeSRS(island) {
  const islandPath = join(SRC, island);
  const files = walk(islandPath);
  if (files.length === 0) return null;

  let domainImports = 0;
  let dtoImports = 0;
  let localDomainDuplicates = 0;

  // Domain names to check for duplicates (same list as ESLint rule)
  const DOMAIN_NAMES = new Set([
    'Patient', 'Doctor', 'Appointment', 'Service', 'Department', 'QueueEntry',
    'QueueStats', 'QueueData', 'QueueSpecialist', 'AuthState', 'AuthUser',
    'UserProfile', 'Role', 'RoleRecord', 'Invoice', 'Payment', 'ChatMessage',
    'ChatConversation', 'AIChatMessage', 'AISuggestion', 'EMRTemplate', 'EMRSection',
  ]);

  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    const code = stripComments(text);

    if (/from\s+['"][^'"]*(?:types\/domain|\/domain\/)/.test(text)) {
      domainImports++;
    }
    if (/from\s+['"][^'"]*(?:types\/api|@\/types['"])[^'"]*['"]/.test(text) && /\b\w+Dto\b/.test(text)) {
      dtoImports++;
    }

    // Count local declarations of domain names
    const declMatches = code.match(/(?:interface|type)\s+([A-Z][A-Za-z0-9_]+)/g) || [];
    for (const m of declMatches) {
      const name = m.match(/([A-Z][A-Za-z0-9_]+)/)[1];
      if (DOMAIN_NAMES.has(name)) localDomainDuplicates++;
    }
  }

  const totalFiles = files.length;
  const strictErrors = countStrictErrorsSync(island);

  // Sub-scores (0-100)
  const strictScore = strictErrors === 0 ? 100 : Math.max(0, 100 - strictErrors);
  const adoptionScore = totalFiles === 0 ? 0 : (domainImports / totalFiles) * 100;
  const duplicateScore = localDomainDuplicates === 0 ? 100 : Math.max(0, 100 - localDomainDuplicates * 10);
  const dtoScore = dtoImports === 0 ? 100 : Math.max(0, 100 - dtoImports * 10);

  const srs = (strictScore + adoptionScore + duplicateScore + dtoScore) / 4;

  return {
    island,
    totalFiles,
    strictErrors,
    domainImports,
    dtoImports,
    localDomainDuplicates,
    strictScore,
    adoptionScore,
    duplicateScore,
    dtoScore,
    srs,
  };
}

// === Run ===

console.log('=== Domain Adoption Index (DAI) — project-wide ===');
console.log('');
const dai = computeDAI();
console.log(`  Consumers (files importing types/domain):  ${dai.consumers}`);
console.log(`  Local interface declarations:              ${dai.localInterfaces}`);
console.log(`  DAI = consumers / localInterfaces:         ${dai.dai.toFixed(1)}%`);
console.log(`  Target:                                    80%`);
console.log('');

console.log('=== Strict Readiness Score (SRS) — per island ===');
console.log('');
console.log('  SRS = avg(strictScore, adoptionScore, duplicateScore, dtoScore)');
console.log('  SRS = 100% means island is ready for strict gate');
console.log('');
console.log(`  ${'Island'.padEnd(28)} ${'SRS'.padStart(6)}  ${'strict'.padStart(7)}  ${'adopt'.padStart(6)}  ${'dup'.padStart(4)}  ${'dto'.padStart(4)}  ${'files'.padStart(5)}  ${'errors'.padStart(6)}`);
console.log(`  ${'─'.repeat(28)} ${'─'.repeat(6)}  ${'─'.repeat(7)}  ${'─'.repeat(6)}  ${'─'.repeat(4)}  ${'─'.repeat(4)}  ${'─'.repeat(5)}  ${'─'.repeat(6)}`);

const targetIsland = process.argv[2];
const islands = targetIsland ? [targetIsland] : ISLANDS;
const results = [];

for (const island of islands) {
  const srs = computeSRS(island);
  if (!srs) continue;
  results.push(srs);
  console.log(`  ${srs.island.padEnd(28)} ${srs.srs.toFixed(0).padStart(5)}%  ${String(srs.strictScore).padStart(6)}%  ${srs.adoptionScore.toFixed(0).padStart(5)}%  ${String(srs.localDomainDuplicates).padStart(4)}  ${String(srs.dtoImports).padStart(4)}  ${String(srs.totalFiles).padStart(5)}  ${String(srs.strictErrors).padStart(6)}`);
}

console.log('');
const ready = results.filter(r => r.srs >= 90);
const close = results.filter(r => r.srs >= 50 && r.srs < 90);
const far = results.filter(r => r.srs < 50);
console.log(`Strict-ready (SRS >= 90%): ${ready.length}/${results.length}`);
for (const r of ready) console.log(`  ✅ ${r.island} (${r.srs.toFixed(0)}%)`);
console.log(`Close (50-89%): ${close.length}/${results.length}`);
for (const r of close) console.log(`  🟡 ${r.island} (${r.srs.toFixed(0)}%)`);
console.log(`Far (<50%): ${far.length}/${results.length}`);
for (const r of far) console.log(`  ❌ ${r.island} (${r.srs.toFixed(0)}%)`);
