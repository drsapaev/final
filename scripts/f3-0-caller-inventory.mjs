#!/usr/bin/env node
/**
 * Sprint F3-0 — Caller Inventory for components with `}: any)` cast.
 *
 * For each component file:
 *   1. Find the component declaration (function/const with `: any)` props)
 *   2. Extract the component name and its destructured prop names
 *   3. Find all JSX usages across the repo
 *   4. For each caller, collect prop names + raw expressions + inferred TS type
 *   5. Detect conflicting prop shapes (same prop name, different types)
 *
 * Output: docs/f3-0-caller-inventory.md
 *
 * Does NOT modify any source files. Read-only analysis.
 */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { Project, SyntaxKind } = require('/home/z/my-project/final/frontend/node_modules/ts-morph');
import { resolve, relative, dirname } from 'path';
import { fileURLToPath } from 'url';
import { mkdirSync, writeFileSync } from 'fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_SRC = resolve(__dirname, '..', 'frontend', 'src');
const DOCS_DIR = resolve(__dirname, '..', 'docs');

// 17 components with `}: any)` cast (collected via grep)
// [path, expectedLine]
const TARGET_FILES = [
  ['pages/registrar/views/WelcomeView.tsx', 102],
  ['components/wizard/CartStepV2.tsx', 42],
  ['components/auth/PhoneVerification.tsx', 28],
  ['components/cardiology/EchoForm.tsx', 147],
  ['components/dental/DentalPatientsTab.tsx', 19],
  ['components/dental/TeethChart.tsx', 44],
  ['components/mobile/QueuePositionCard.tsx', 9],
  ['components/doctor/DoctorServiceSelector.tsx', 39],
  ['components/notifications/EmailSMSManager.tsx', 342],
  ['components/medical/PatientCard.tsx', 20],
  ['components/common/Table.tsx', 26],
  ['components/AppointmentFlow.tsx', 13],
  ['components/queue/ModernQueueManager.tsx', 36],
  ['components/queue/QueueTable.tsx', 20],
  ['components/emr-v2/sections/EMRSmartFieldV2.tsx', 67],
  ['components/emr-v2/sections/ComplaintsField.tsx', 49],
  ['components/emr-v2/sections/PrescriptionEditor.tsx', 35],
];

const project = new Project({
  tsConfigFilePath: resolve(FRONTEND_SRC, '..', 'tsconfig.json'),
  skipAddingFilesFromTsConfig: false,
  compilerOptions: {
    skipLibCheck: true,
    noEmit: true,
  },
});

// Force-load every source file under frontend/src so callers can be resolved.
project.getSourceFiles(`${FRONTEND_SRC}/**/*.{ts,tsx}`);

function rel(p) {
  return relative(resolve(__dirname, '..', 'final'), p);
}

function getComponentName(file) {
  const base = file.getBaseNameWithoutExtension();
  // Default component name from filename
  return base;
}

function findComponentDeclarations(sourceFile) {
  // Find function declarations / variable statements whose initializer is an
  // arrow function or function expression with `: any` for props.
  const decls = [];

  // 1. const Name = (...) => { ... } with `: any` for props
  //    Also handles: const Name = React.memo((...) => { ... })
  //                  const Name = memo((...) => { ... })
  //    Also handles inner-scope render helpers: const renderX = ({...}: any) => ...
  //    (we walk ALL VariableDeclaration nodes, including those nested inside
  //    function bodies)
  const allVarDecls = sourceFile.getDescendantsOfKind(SyntaxKind.VariableDeclaration);
  for (const vd of allVarDecls) {
    const init = vd.getInitializer();
    if (!init) continue;

    // Unwrap CallExpression like React.memo(...), forwardRef(...)
    let fnNode = init;
    if (fnNode.getKind() === SyntaxKind.CallExpression) {
      const args = fnNode.getArguments();
      if (args.length > 0) {
        const first = args[0];
        if (first.getKind() === SyntaxKind.ArrowFunction ||
            first.getKind() === SyntaxKind.FunctionExpression) {
          fnNode = first;
        }
      }
    }

    const isArrowOrFn =
      fnNode.getKind() === SyntaxKind.ArrowFunction ||
      fnNode.getKind() === SyntaxKind.FunctionExpression;
    if (!isArrowOrFn) continue;
    const params = fnNode.getParameters();
    if (params.length === 0) continue;
    const p0 = params[0];
    const pType = p0.getTypeNode?.()?.getText() ?? '';
    const pText = p0.getText();
    // Match if param destructured with `: any` OR `: any)` in source
    if (pType === 'any' || /:\s*any\b/.test(pText) || /:\s*any\)/.test(pText)) {
      const destructuredNames = extractDestructuredNames(p0);
      decls.push({
        kind: 'variable',
        name: vd.getName(),
        paramText: pText,
        propNames: destructuredNames,
        line: vd.getStartLineNumber(),
      });
    }
  }

  // 2. function Name(...) { ... } with `: any` for props
  sourceFile.getFunctions().forEach((fd) => {
    const params = fd.getParameters();
    if (params.length === 0) return;
    const p0 = params[0];
    const pType = p0.getTypeNode?.()?.getText() ?? '';
    const pText = p0.getText();
    if (pType === 'any' || /:\s*any\b/.test(pText) || /:\s*any\)/.test(pText)) {
      const destructuredNames = extractDestructuredNames(p0);
      decls.push({
        kind: 'function',
        name: fd.getName() ?? '<anonymous>',
        paramText: pText,
        propNames: destructuredNames,
        line: fd.getStartLineNumber(),
      });
    }
  });

  // 3. Tag render helpers
  for (const d of decls) {
    if (/^render[A-Z]/.test(d.name) || /^renderStat/.test(d.name)) {
      d.kind = 'render-helper';
    }
  }

  return decls;
}

function extractDestructuredNames(param) {
  // param is a ParameterDeclaration. Get its name which might be an
  // ObjectBindingPattern like { a, b: c, d = 1 }
  const nameNode = param.getNameNode();
  if (nameNode.getKind() !== SyntaxKind.ObjectBindingPattern) return [];
  const pattern = nameNode;
  return pattern.getElements().map((el) => {
    // el is a BindingElement. The property name (if `prop: alias`) is the
    // canonical name; otherwise the binding name IS the property name.
    const propName = el.getPropertyNameNode()?.getText() ?? el.getNameNode().getText();
    const isRest = el.getDotDotDotToken() !== undefined;
    const defaultInit = el.getInitializer()?.getText();
    return { name: propName, isRest, default: defaultInit };
  });
}

function findJsxCallers(project, componentName, excludeFilePath) {
  const callers = [];
  for (const sf of project.getSourceFiles()) {
    // Only scan .tsx files for JSX
    if (!sf.getFilePath().endsWith('.tsx')) continue;
    // === JSX callers: <ComponentName ... /> ===
    const jsxElements = sf.getDescendantsOfKind(SyntaxKind.JsxOpeningElement)
      .concat(sf.getDescendantsOfKind(SyntaxKind.JsxSelfClosingElement));
    for (const jsx of jsxElements) {
      const tagName = jsx.getTagNameNode().getText();
      if (tagName !== componentName) continue;
      const attrs = jsx.getAttributes();
      const propMap = {};
      for (const attr of attrs) {
        if (attr.getKind() !== SyntaxKind.JsxAttribute) continue;
        const name = attr.getNameNode().getText();
        const init = attr.getInitializer();
        const propInfo = extractPropInfo(init);
        propMap[name] = propInfo;
      }
      callers.push({
        kind: 'jsx',
        file: rel(sf.getFilePath()),
        line: jsx.getStartLineNumber(),
        props: propMap,
      });
    }

    // === Function-call callers: renderName({...}) — for render helpers ===
    // Match `componentName({` to find call expressions passing object literals.
    const callExprs = sf.getDescendantsOfKind(SyntaxKind.CallExpression);
    for (const ce of callExprs) {
      const expr = ce.getExpression();
      if (expr.getText() !== componentName) continue;
      const args = ce.getArguments();
      if (args.length === 0) continue;
      const firstArg = args[0];
      // Only collect if first arg is an object literal
      if (firstArg.getKind() !== SyntaxKind.ObjectLiteralExpression) continue;
      const propMap = {};
      for (const prop of firstArg.getProperties()) {
        if (prop.getKind() !== SyntaxKind.PropertyAssignment) continue;
        const name = prop.getName();
        const init = prop.getInitializer();
        const propInfo = extractPropInfo(init);
        propMap[name] = propInfo;
      }
      callers.push({
        kind: 'call',
        file: rel(sf.getFilePath()),
        line: ce.getStartLineNumber(),
        props: propMap,
      });
    }
  }
  return callers;
}

function extractPropInfo(init) {
  let raw = '<none>';
  let typeStr = '<unknown>';
  let kindStr = 'shorthand';
  if (!init) {
    raw = 'true';
    kindStr = 'shorthand-true';
    typeStr = 'boolean (true)';
    return { raw, kind: kindStr, type: typeStr };
  }
  if (init.getKind() === SyntaxKind.StringLiteral) {
    raw = init.getText();
    kindStr = 'string-literal';
    typeStr = 'string';
    return { raw, kind: kindStr, type: typeStr };
  }
  if (init.getKind() === SyntaxKind.JsxExpression) {
    const expr = init.getExpression();
    if (!expr) {
      return { raw: '{...}', kind: 'empty-expr', type: '<unknown>' };
    }
    return extractExprInfo(expr);
  }
  // Direct expression (function-call style)
  return extractExprInfo(init);
}

function extractExprInfo(expr) {
  let typeStr = '<unknown>';
  try {
    const tsType = expr.getType();
    if (tsType) {
      typeStr = tsType.getText(expr, undefined);
    }
  } catch (e) {
    typeStr = '<unknown>';
  }
  return {
    raw: expr.getText(),
    kind: expr.getKindName(),
    type: typeStr,
  };
}

function detectConflicts(callers) {
  // For each prop name, collect distinct inferred types across callers.
  const propTypes = new Map();
  for (const c of callers) {
    for (const [name, info] of Object.entries(c.props)) {
      if (!propTypes.has(name)) propTypes.set(name, new Map());
      const typeMap = propTypes.get(name);
      const t = info.type || '<unknown>';
      if (!typeMap.has(t)) typeMap.set(t, { count: 0, sampleCaller: `${c.file}:${c.line}` });
      typeMap.get(t).count++;
    }
  }
  const conflicts = [];
  for (const [propName, typeMap] of propTypes) {
    if (typeMap.size > 1) {
      const variants = [];
      for (const [t, info] of typeMap) {
        variants.push({ type: t, count: info.count, sample: info.sampleCaller });
      }
      conflicts.push({ propName, variants });
    }
  }
  return { propTypes, conflicts };
}

function recommendDomain(name, propNames, callers, conflicts) {
  // Heuristic recommendation based on prop names.
  const has = (n) => propNames.some((p) => p.name === n);
  const callerCount = callers.length;
  const conflictCount = conflicts.length;

  if (has('patient') || has('patientId')) return { domain: 'Patients', suggestion: 'Patient' };
  if (has('appointment')) return { domain: 'Scheduling', suggestion: 'Appointment' };
  if (has('queueEntry') || has('queue') || has('entries') || has('specialists')) return { domain: 'Queue', suggestion: 'QueueEntry | QueueData' };
  if (has('onToothClick') || has('teeth') || has('toothId')) return { domain: 'Dental', suggestion: 'ToothChart domain types' };
  if (has('visitId') || has('onSave') || has('onDataUpdate')) return { domain: 'EMR', suggestion: 'EMR visit/section types' };
  if (has('cart') || has('services') || has('items')) return { domain: 'Wizard/Cart', suggestion: 'Cart domain types' };
  if (callerCount === 0) return { domain: 'Unused?', suggestion: 'No callers found — verify and possibly delete' };
  return { domain: 'Generic', suggestion: 'Build ad-hoc Props interface from observed prop names' };
}

// === Main ===
const results = [];

for (const [relPath, expectedLine] of TARGET_FILES) {
  const absPath = resolve(FRONTEND_SRC, relPath);
  let sf;
  try {
    sf = project.getSourceFile(absPath);
    if (!sf) {
      sf = project.addSourceFileAtPath(absPath);
    }
  } catch (e) {
    results.push({
      file: relPath,
      error: `Failed to load: ${e.message}`,
    });
    continue;
  }

  const decls = findComponentDeclarations(sf);
  if (decls.length === 0) {
    results.push({
      file: relPath,
      error: 'No component declaration with `: any)` props found',
    });
    continue;
  }

  // Pick the declaration whose line is closest to (or equals) expectedLine.
  // ts-morph line numbers are 1-indexed just like grep.
  let decl = decls[0];
  let bestDelta = Math.abs(decl.line - expectedLine);
  for (const d of decls) {
    const delta = Math.abs(d.line - expectedLine);
    if (delta < bestDelta) {
      decl = d;
      bestDelta = delta;
    }
  }

  const callers = findJsxCallers(project, decl.name, absPath);
  const { propTypes, conflicts } = detectConflicts(callers);
  const recommendation = recommendDomain(decl.name, decl.propNames, callers, conflicts);

  results.push({
    file: relPath,
    componentName: decl.name,
    componentKind: decl.kind,
    declarationLine: decl.line,
    declaredProps: decl.propNames.map((p) => p.name),
    callerCount: callers.length,
    callers,
    propTypes: Object.fromEntries(
      Array.from(propTypes.entries()).map(([k, v]) => [
        k,
        Array.from(v.entries()).map(([t, info]) => ({ type: t, count: info.count, sample: info.sampleCaller })),
      ])
    ),
    conflicts,
    recommendation,
  });
}

// === Generate markdown report ===
mkdirSync(DOCS_DIR, { recursive: true });
const reportPath = resolve(DOCS_DIR, 'f3-0-caller-inventory.md');

let md = '';
md += '# Sprint F3-0 — Caller Inventory\n\n';
md += '> Read-only analysis. No source files modified.\n';
md += `> Generated: ${new Date().toISOString()}\n\n`;
md += `> Scope: 17 components with \`}: any)\` cast.\n\n`;

md += '## Summary\n\n';
md += '| # | Component | File | Declared props | Callers | Conflicts | Domain |\n';
md += '|---|-----------|------|----------------|---------|-----------|--------|\n';
results.forEach((r, idx) => {
  if (r.error) {
    md += `| ${idx + 1} | — | ${r.file} | _error_ | — | — | — |\n`;
    return;
  }
  md += `| ${idx + 1} | ${r.componentName} | ${r.file}:${r.declarationLine} | ${r.declaredProps.length} | ${r.callerCount} | ${r.conflicts.length} | ${r.recommendation.domain} |\n`;
});
md += '\n';

md += '## Domain grouping (recommended F3 execution order)\n\n';
const byDomain = new Map();
for (const r of results) {
  if (r.error) continue;
  const d = r.recommendation.domain;
  if (!byDomain.has(d)) byDomain.set(d, []);
  byDomain.get(d).push(r);
}
// Sort domains by lowest-conflict sum first
const domainStats = Array.from(byDomain.entries()).map(([d, items]) => ({
  domain: d,
  items,
  totalConflicts: items.reduce((s, r) => s + r.conflicts.length, 0),
  totalCallers: items.reduce((s, r) => s + r.callerCount, 0),
}));
domainStats.sort((a, b) => a.totalConflicts - b.totalConflicts || a.totalCallers - b.totalCallers);

md += '| Domain | Components | Total callers | Total conflicts |\n';
md += '|--------|-----------|---------------|------------------|\n';
for (const ds of domainStats) {
  md += `| ${ds.domain} | ${ds.items.length} | ${ds.totalCallers} | ${ds.totalConflicts} |\n`;
}
md += '\n';

md += '## Detailed inventory per component\n\n';
for (const r of results) {
  if (r.error) {
    md += `### ${r.file}\n\n_ERROR: ${r.error}_\n\n`;
    continue;
  }
  md += `### ${r.componentName}\n\n`;
  md += `- **File:** \`${r.file}:${r.declarationLine}\`\n`;
  md += `- **Declared props:** ${r.declaredProps.length === 0 ? '_none / single prop_' : r.declaredProps.map((p) => `\`${p}\``).join(', ')}\n`;
  md += `- **JSX callers:** ${r.callerCount}\n`;
  md += `- **Conflicts:** ${r.conflicts.length === 0 ? '_none_' : r.conflicts.length}\n`;
  md += `- **Recommended domain:** ${r.recommendation.domain} → ${r.recommendation.suggestion}\n\n`;

  if (r.declaredProps.length > 0) {
    md += '#### Declared props (destructured in component signature)\n\n';
    md += '| Prop | Default |\n';
    md += '|------|--------|\n';
    const decl = results.find((x) => x === r);
    // Re-extract default values from declaredProps (we stored only name earlier)
    // Walk source file again to get defaults.
    const sf2 = project.getSourceFile(resolve(FRONTEND_SRC, r.file));
    const d2 = sf2 ? findComponentDeclarations(sf2)[0] : null;
    if (d2) {
      for (const p of d2.propNames) {
        md += `| \`${p.name}\` | ${p.default ?? '—'} |\n`;
      }
    }
    md += '\n';
  }

  if (r.callerCount > 0) {
    md += '#### Props observed in callers (with inferred TS types)\n\n';
    md += '| Prop | Distinct types observed | Sample |\n';
    md += '|------|--------------------------|--------|\n';
    const propRows = Object.entries(r.propTypes).sort(([a], [b]) => a.localeCompare(b));
    for (const [prop, variants] of propRows) {
      const types = variants.map((v) => `\`${v.type}\` ×${v.count}`).join('<br>');
      const sample = variants[0]?.sample ?? '—';
      md += `| \`${prop}\` | ${types} | ${sample} |\n`;
    }
    md += '\n';
  } else {
    md += '_No JSX callers found in scanned source files._\n\n';
  }

  if (r.conflicts.length > 0) {
    md += '#### ⚠ Conflicts\n\n';
    md += 'Same prop name receives different types across callers. Resolve before writing the Props interface:\n\n';
    for (const c of r.conflicts) {
      md += `**\`${c.propName}\`**\n\n`;
      for (const v of c.variants) {
        md += `- \`${v.type}\` ×${v.count} — sample: ${v.sample}\n`;
      }
      md += '\n';
    }
  }

  if (r.callerCount > 0) {
    md += '#### Caller files\n\n';
    const grouped = new Map();
    for (const c of r.callers) {
      if (!grouped.has(c.file)) grouped.set(c.file, []);
      grouped.get(c.file).push(c.line);
    }
    for (const [file, lines] of grouped) {
      md += `- \`${file}\` — line${lines.length > 1 ? 's' : ''}: ${lines.join(', ')}\n`;
    }
    md += '\n';
  }
}

md += '## Recommended execution order\n\n';
md += 'Sprint F3 sub-sprints, ordered by ascending conflict count. Start with the lowest-conflict domain to validate the Props-interface migration pattern before tackling harder domains.\n\n';
for (const ds of domainStats) {
  md += `### ${ds.domain} — ${ds.items.length} components, ${ds.totalConflicts} conflicts\n\n`;
  md += '| Component | Callers | Conflicts |\n';
  md += '|-----------|---------|-----------|\n';
  for (const r of ds.items) {
    md += `| ${r.componentName} | ${r.callerCount} | ${r.conflicts.length} |\n`;
  }
  md += '\n';
}

writeFileSync(reportPath, md, 'utf-8');
console.log(`Inventory written to ${reportPath}`);
console.log(`Total components analyzed: ${results.length}`);
console.log(`Total JSX callers found: ${results.reduce((s, r) => s + (r.callerCount ?? 0), 0)}`);
console.log(`Total conflicts detected: ${results.reduce((s, r) => s + (r.conflicts?.length ?? 0), 0)}`);
