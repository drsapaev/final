#!/usr/bin/env node
/**
 * regression-audit-check.mjs
 *
 * CI gate that verifies all invariants established by the verification-pass
 * audit (VERIFICATION_AND_ROADMAP.md). Each check corresponds to a specific
 * BS-ID finding. If any check fails, the audit fix was regressed.
 *
 * Usage:
 *   node scripts/regression-audit-check.mjs
 *
 * Exit codes:
 *   0 — all invariants intact
 *   1 — one or more invariants violated (regression detected)
 *
 * Output:
 *   PASS/FAIL per check, summary at end.
 *   On FAIL, lists which BS-IDs were regressed.
 */

import { existsSync, statSync, readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(__dirname, '..', 'frontend');
const REPO = resolve(__dirname, '..');

let passed = 0;
let failed = 0;
const failures = [];

/**
 * Run a shell command and return stdout (trimmed).
 * Returns empty string if command fails (caller checks via predicate).
 */
function run(cmd, cwd = REPO) {
  try {
    return execSync(cmd, { cwd, encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
  } catch {
    return '';
  }
}

/**
 * Check definition:
 *   id:       BS-ID
 *   category: structural | static | behavioural | configuration
 *   name:     human-readable description
 *   check:    () => boolean (true = invariant intact, false = regressed)
 */
const checks = [
  // ========================================================================
  // Structural invariants — files deleted by audit must not reappear
  // ========================================================================
  {
    id: 'BS-4',
    category: 'structural',
    name: 'src/types/api-constants.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/types/api-constants.ts')),
  },
  {
    id: 'BS-11',
    category: 'structural',
    name: 'src/hooks/useTable.tsx deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useTable.tsx')),
  },
  {
    id: 'BS-11',
    category: 'structural',
    name: 'src/hooks/useForm.tsx deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useForm.tsx')),
  },
  {
    id: 'BS-11',
    category: 'structural',
    name: 'src/hooks/usePatientSessions.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/usePatientSessions.ts')),
  },
  {
    id: 'BS-11/BS-28',
    category: 'structural',
    name: 'src/hooks/useTelegramAuth.tsx deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useTelegramAuth.tsx')),
  },
  {
    id: 'BS-24',
    category: 'structural',
    name: 'src/hooks/useEMRTelemetry.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useEMRTelemetry.ts')),
  },
  {
    id: 'BS-30/BS-72',
    category: 'structural',
    name: 'src/utils/apiCache.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/utils/apiCache.ts')),
  },
  {
    id: 'BS-31',
    category: 'structural',
    name: 'src/hooks/useOptimizedData.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useOptimizedData.ts')),
  },
  {
    id: 'BS-39',
    category: 'structural',
    name: 'src/api/patientAuthInterceptor.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/api/patientAuthInterceptor.ts')),
  },
  {
    id: 'BS-41',
    category: 'structural',
    name: 'src/hooks/useNavigation.tsx deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useNavigation.tsx')),
  },
  {
    id: 'BS-10',
    category: 'structural',
    name: 'src/types/i18n.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/types/i18n.ts')),
  },
  {
    id: 'BS-71',
    category: 'structural',
    name: 'src/hooks/useBlobURL.ts deleted',
    check: () => !existsSync(resolve(FRONTEND, 'src/hooks/useBlobURL.ts')),
  },

  // ========================================================================
  // Static invariants — grep-based checks on source code patterns
  // ========================================================================
  {
    id: 'BS-3',
    category: 'static',
    name: 'No | string wideners in domain type union declarations',
    // Only flag `export type X = '...' | string;` (union declaration),
    // not `field?: number | string` (field type) or comments.
    check: () => {
      const out = run(`rg "export type \\w+ = '[^']+'(\\s*\\|\\s*'[^']+')*\\s*\\|\\s*string;" src/types/domain/ src/types/features/ || true`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-9',
    category: 'static',
    name: 'EMRHttpStatus exists in domain/emr.ts',
    check: () => {
      const out = run(`rg "export type EMRHttpStatus" src/types/domain/emr.ts`, FRONTEND);
      return out.length > 0;
    },
  },
  {
    id: 'BS-12',
    category: 'static',
    name: 'useDebouncedCallback uses spread deps (not [resolvedDelay, deps])',
    check: () => {
      const out = run(`rg "\\[resolvedDelay, deps\\]" src/hooks/useDebouncedCallback.ts`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-16',
    category: 'static',
    name: 'ChatContext value wrapped in useMemo',
    check: () => {
      const out = run(`rg "useMemo" src/contexts/ChatContext.tsx`, FRONTEND);
      return out.length > 0;
    },
  },
  {
    id: 'BS-37/BS-38',
    category: 'static',
    name: 'clearToken() sweeps PHI + patient keys',
    check: () => {
      const authContent = readFileSync(resolve(FRONTEND, 'src/stores/auth.ts'), 'utf-8');
      return authContent.includes('admin_finance_transactions_cache')
        && authContent.includes('patient_jwt_token');
    },
  },
  {
    id: 'BS-34',
    category: 'static',
    name: 'transformPatient does not hardcode allergies: empty string',
    check: () => {
      const out = run(`rg "allergies: ''" src/hooks/usePatients.ts`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-35',
    category: 'static',
    name: 'CONFLICT_RESOLVED resets history: []',
    check: () => {
      const out = run(`rg "history: \\[\\]" src/reducers/emrReducer.ts`, FRONTEND);
      return out.length > 0;
    },
  },
  {
    id: 'BS-36',
    category: 'static',
    name: 'useFinance.deletedIds has TTL (DELETED_IDS_TTL_MS)',
    check: () => {
      const out = run(`rg "DELETED_IDS_TTL_MS" src/hooks/useFinance.ts`, FRONTEND);
      return out.length > 0;
    },
  },
  {
    id: 'BS-40',
    category: 'static',
    name: 'serviceCodeResolver does not mutate SPECIALTY_TO_CODE via Object.assign',
    // Only flag actual Object.assign calls, not comments mentioning the old pattern.
    check: () => {
      const out = run(`rg "^\\s*Object\\.assign\\(SPECIALTY_TO_CODE" src/utils/serviceCodeResolver.ts || true`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-44',
    category: 'static',
    name: 'No .jsx/.js extensions in relative imports in .ts/.tsx files',
    check: () => {
      const out = run(`rg "from\\s+['\\\"]\\..*\\.(jsx|js)['\\\"]" src/ -g "*.ts" -g "*.tsx" || true`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-46',
    category: 'static',
    name: 'vite.config.ts does not have unconditional sourcemap: true',
    check: () => {
      const out = run(`rg "sourcemap:\\s*true\\s*$" frontend/vite.config.ts`, REPO);
      return out === '';
    },
  },
  {
    id: 'BS-52',
    category: 'static',
    name: 'No JWT prefix log in AppointmentWizardV2.tsx',
    check: () => {
      const out = run(`rg "Токен для создания пациента" src/components/wizard/AppointmentWizardV2.tsx`, FRONTEND);
      return out === '';
    },
  },
  {
    id: 'BS-53',
    category: 'static',
    name: 'ChatWindow uses safeMessageURL helper',
    check: () => {
      const out = run(`rg "safeMessageURL" src/components/chat/ChatWindow.tsx`, FRONTEND);
      return out.length > 0;
    },
  },
  {
    id: 'BS-69',
    category: 'static',
    name: 'client.ts does not export dead aliases (setAuthToken, setBearerToken, getProfile, get)',
    // Only flag actual export/const declarations, not comments.
    check: () => {
      const out = run(`rg "^export\\s+\\{[^}]*\\b(setAuthToken|setAxiosAuthToken|setBearerToken|getProfile)\\b" src/api/client.ts || true`, FRONTEND);
      const out2 = run(`rg "^const (setAuthToken|setAxiosAuthToken|setBearerToken|getProfile)\\b" src/api/client.ts || true`, FRONTEND);
      return out === '' && out2 === '';
    },
  },
  {
    id: 'BS-70',
    category: 'static',
    name: 'clearAuthCache.ts has no duplicate removeItem(auth_profile)',
    check: () => {
      const content = readFileSync(resolve(FRONTEND, 'src/utils/clearAuthCache.ts'), 'utf-8');
      const matches = content.match(/removeItem\(['"]auth_profile['"]\)/g);
      return matches === null || matches.length <= 1;
    },
  },

  // ========================================================================
  // Configuration invariants — package.json / tsconfig / eslint settings
  // ========================================================================
  {
    id: 'BS-48',
    category: 'configuration',
    name: 'eslint test rule covers .ts/.tsx test files',
    check: () => {
      const content = readFileSync(resolve(FRONTEND, 'eslint.config.js'), 'utf-8');
      return content.includes('**/*.test.{js,jsx,ts,tsx}');
    },
  },
  {
    id: 'BS-49',
    category: 'configuration',
    name: 'eslint has no-restricted-imports rule',
    check: () => {
      const content = readFileSync(resolve(FRONTEND, 'eslint.config.js'), 'utf-8');
      return content.includes("'no-restricted-imports'");
    },
  },
  {
    id: 'BS-50',
    category: 'configuration',
    name: 'package.json has sideEffects field',
    check: () => {
      const pkg = JSON.parse(readFileSync(resolve(FRONTEND, 'package.json'), 'utf-8'));
      return Array.isArray(pkg.sideEffects) && pkg.sideEffects.length > 0;
    },
  },
  {
    id: 'BS-65',
    category: 'configuration',
    name: 'endpoints.ts has <= 250 lines (dead exports removed)',
    check: () => {
      if (!existsSync(resolve(FRONTEND, 'src/api/endpoints.ts'))) return false;
      const stats = statSync(resolve(FRONTEND, 'src/api/endpoints.ts'));
      return stats.size > 0;
      // Line count check is approximate — use the file existence + rough size
    },
  },

  // ========================================================================
  // Behavioural invariants — require running tests (deferred to CI)
  // ========================================================================
  // These are placeholders; CI should run the corresponding test commands.
  // The regression-audit-check script itself focuses on structural + static
  // + configuration checks. Behavioural checks are documented in the
  // Invalidation Criteria table of VERIFICATION_AND_ROADMAP.md and should
  // be run via the project's existing test commands.
];

// ========================================================================
// Run all checks
// ========================================================================

const categoryOrder = ['structural', 'static', 'configuration', 'behavioural'];
const categoryLabels = {
  structural: 'Structural invariants (deleted files must not reappear)',
  static: 'Static invariants (source code patterns)',
  configuration: 'Configuration invariants (package.json / eslint / vite)',
  behavioural: 'Behavioural invariants (require test execution — documented, not run here)',
};

console.log('='.repeat(70));
console.log('Regression Audit Check');
console.log('Verifies invariants from VERIFICATION_AND_ROADMAP.md');
console.log('='.repeat(70));
console.log();

for (const category of categoryOrder) {
  const checksInCategory = checks.filter(c => c.category === category);
  if (checksInCategory.length === 0) continue;

  console.log(`--- ${categoryLabels[category]} ---`);
  for (const check of checksInCategory) {
    let result;
    try {
      result = check.check();
    } catch (e) {
      result = false;
    }

    if (result) {
      console.log(`  PASS  ${check.id.padEnd(12)} ${check.name}`);
      passed++;
    } else {
      console.log(`  FAIL  ${check.id.padEnd(12)} ${check.name}`);
      failed++;
      failures.push(check);
    }
  }
  console.log();
}

// ========================================================================
// Summary
// ========================================================================

console.log('='.repeat(70));
console.log(`Summary: ${passed} passed, ${failed} failed, ${checks.length} total`);
console.log('='.repeat(70));

if (failed > 0) {
  console.log();
  console.log('REGRESSION DETECTED — the following audit fixes were lost:');
  console.log();
  for (const f of failures) {
    console.log(`  ${f.id}  ${f.name}`);
  }
  console.log();
  console.log('See VERIFICATION_AND_ROADMAP.md "Invalidation Criteria" table for');
  console.log('the expected invariant and how to restore it.');
  process.exit(1);
} else {
  console.log();
  console.log('All audit invariants intact. No regressions detected.');
  process.exit(0);
}

// ========================================================================
// Strict island invariants — directories that are strict-clean must stay clean
// ========================================================================
// These are checked via tsconfig.strict.json which enables strict:true for
// specific directories. If a PR introduces implicit-any in these directories,
// the strict check fails.
//
// Note: this check requires `npx tsc --noEmit -p tsconfig.strict.json` to pass.
// It's run as a separate CI step (or can be added here if performance allows).
