#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import tsParser from '@typescript-eslint/parser';

const SOURCE_EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx']);
const TEST_FILE_PATTERN = /\.(test|spec)\.[jt]sx?$/;
const EXCLUDED_DIRS = new Set([
  '__mocks__',
  '__tests__',
  'dist',
  'node_modules',
  'test',
  'tests',
]);

const ACCESSIBLE_NAME_ATTRIBUTES = new Set([
  'aria-label',
  'aria-labelledby',
]);

const CUSTOM_CONTROL_COMPONENTS = new Set([
  'Button',
  'MacOSButton',
]);

const INTERACTIVE_ROLES = new Set([
  'button',
  'checkbox',
  'link',
  'menuitem',
  'menuitemcheckbox',
  'menuitemradio',
  'option',
  'radio',
  'switch',
  'tab',
]);

const TEXT_LIKE_COMPONENTS = new Set([
  'ScreenReaderOnly',
  'SrOnly',
  'VisuallyHidden',
  'VisuallyHiddenText',
]);

const PARSER_OPTIONS = {
  ecmaFeatures: {
    jsx: true,
  },
  ecmaVersion: 2022,
  loc: true,
  range: true,
  sourceType: 'module',
};

function parseArgs(argv) {
  const options = {
    baseline: null,
    root: path.resolve(process.cwd(), 'src'),
    includeComponents: false,
    strict: false,
    format: 'text',
    writeBaseline: null,
  };

  for (const arg of argv) {
    if (arg === '--strict') {
      options.strict = true;
    } else if (arg.startsWith('--baseline=')) {
      options.baseline = path.resolve(process.cwd(), arg.slice('--baseline='.length));
    } else if (arg.startsWith('--root=')) {
      options.root = path.resolve(process.cwd(), arg.slice('--root='.length));
    } else if (arg === '--include-components') {
      options.includeComponents = true;
    } else if (arg.startsWith('--format=')) {
      options.format = arg.slice('--format='.length);
    } else if (arg.startsWith('--write-baseline=')) {
      options.writeBaseline = path.resolve(process.cwd(), arg.slice('--write-baseline='.length));
    }
  }

  return options;
}

function isSourceFile(filePath) {
  const ext = path.extname(filePath);
  return SOURCE_EXTENSIONS.has(ext) && !TEST_FILE_PATTERN.test(path.basename(filePath));
}

export function listSourceFiles(rootDir) {
  const files = [];

  function visit(currentDir) {
    if (!fs.existsSync(currentDir)) {
      return;
    }

    for (const entry of fs.readdirSync(currentDir, { withFileTypes: true })) {
      const fullPath = path.join(currentDir, entry.name);

      if (entry.isDirectory()) {
        if (!EXCLUDED_DIRS.has(entry.name)) {
          visit(fullPath);
        }
        continue;
      }

      if (entry.isFile() && isSourceFile(fullPath)) {
        files.push(fullPath);
      }
    }
  }

  visit(rootDir);
  return files.sort();
}

function parseSource(code, filePath) {
  try {
    if (typeof tsParser.parseForESLint === 'function') {
      return tsParser.parseForESLint(code, PARSER_OPTIONS).ast;
    }

    return tsParser.parse(code, PARSER_OPTIONS);
  } catch (error) {
    throw new Error(`${filePath}: ${error.message}`);
  }
}

function jsxNameToString(name) {
  if (!name) {
    return '';
  }

  if (name.type === 'JSXIdentifier') {
    return name.name;
  }

  if (name.type === 'JSXMemberExpression') {
    return `${jsxNameToString(name.object)}.${jsxNameToString(name.property)}`;
  }

  if (name.type === 'JSXNamespacedName') {
    return `${jsxNameToString(name.namespace)}:${jsxNameToString(name.name)}`;
  }

  return '';
}

function getAttribute(openingElement, attrName) {
  return openingElement.attributes.find((attribute) => {
    return attribute.type === 'JSXAttribute' && jsxNameToString(attribute.name) === attrName;
  });
}

function attributeHasValue(attribute) {
  if (!attribute) {
    return false;
  }

  if (attribute.value == null) {
    return true;
  }

  if (attribute.value.type === 'Literal' || attribute.value.type === 'StringLiteral') {
    return String(attribute.value.value || '').trim().length > 0;
  }

  if (attribute.value.type === 'JSXExpressionContainer') {
    return expressionHasText(attribute.value.expression);
  }

  return true;
}

function literalValueFromAttribute(attribute) {
  if (!attribute || attribute.value == null) {
    return '';
  }

  if (attribute.value.type === 'Literal' || attribute.value.type === 'StringLiteral') {
    return String(attribute.value.value || '').trim();
  }

  return '';
}

function hasAccessibleNameAttribute(openingElement) {
  return openingElement.attributes.some((attribute) => {
    return (
      attribute.type === 'JSXAttribute' &&
      ACCESSIBLE_NAME_ATTRIBUTES.has(jsxNameToString(attribute.name)) &&
      attributeHasValue(attribute)
    );
  });
}

function expressionHasText(expression) {
  if (!expression) {
    return false;
  }

  switch (expression.type) {
    case 'Literal':
    case 'StringLiteral':
      return String(expression.value || '').trim().length > 0;
    case 'TemplateLiteral':
      return expression.quasis.some((quasi) => quasi.value.cooked.trim().length > 0);
    case 'ConditionalExpression':
      return expressionHasText(expression.consequent) || expressionHasText(expression.alternate);
    case 'LogicalExpression':
      return expressionHasText(expression.left) || expressionHasText(expression.right);
    case 'Identifier':
    case 'CallExpression':
    case 'MemberExpression':
    case 'OptionalCallExpression':
    case 'ChainExpression':
      return true;
    default:
      return false;
  }
}

function elementHasText(node) {
  if (!node || node.type !== 'JSXElement') {
    return false;
  }

  const elementName = jsxNameToString(node.openingElement.name);
  if (TEXT_LIKE_COMPONENTS.has(elementName)) {
    return true;
  }

  for (const child of node.children || []) {
    if (child.type === 'JSXText' && child.value.trim().length > 0) {
      return true;
    }

    if (child.type === 'JSXExpressionContainer' && expressionHasText(child.expression)) {
      return true;
    }

    if (child.type === 'JSXElement' && elementHasText(child)) {
      return true;
    }
  }

  return false;
}

function hasInteractiveRole(openingElement) {
  const role = getAttribute(openingElement, 'role');
  return INTERACTIVE_ROLES.has(literalValueFromAttribute(role));
}

function isAuditedControl(openingElement, options = {}) {
  const elementName = jsxNameToString(openingElement.name);
  return (
    elementName === 'button' ||
    hasInteractiveRole(openingElement) ||
    (options.includeComponents && CUSTOM_CONTROL_COMPONENTS.has(elementName))
  );
}

function classifyControl(node) {
  const openingElement = node.openingElement;

  if (hasAccessibleNameAttribute(openingElement) || elementHasText(node)) {
    return null;
  }

  if (attributeHasValue(getAttribute(openingElement, 'title'))) {
    return 'title-only';
  }

  return 'missing-accessible-name';
}

function visitAst(node, visitor) {
  if (!node || typeof node !== 'object') {
    return;
  }

  visitor(node);

  for (const [key, value] of Object.entries(node)) {
    if (
      key === 'loc' ||
      key === 'range' ||
      key === 'parent' ||
      key === 'tokens' ||
      key === 'comments'
    ) {
      continue;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        visitAst(item, visitor);
      }
      continue;
    }

    if (value && typeof value === 'object') {
      visitAst(value, visitor);
    }
  }
}

export function auditCode(code, filePath = '<inline>', options = {}) {
  const ast = parseSource(code, filePath);
  const findings = [];

  visitAst(ast, (node) => {
    if (node.type !== 'JSXElement' || !isAuditedControl(node.openingElement, options)) {
      return;
    }

    const reason = classifyControl(node);
    if (!reason) {
      return;
    }

    findings.push({
      file: filePath,
      line: node.openingElement.loc?.start?.line || 1,
      column: (node.openingElement.loc?.start?.column || 0) + 1,
      element: jsxNameToString(node.openingElement.name),
      reason,
    });
  });

  return findings;
}

export function findingSignature(finding) {
  return [
    finding.file,
    finding.line,
    finding.column,
    finding.element,
    finding.reason,
  ].join(':');
}

function normalizeFinding(finding) {
  const normalized = {
    ...finding,
    file: relativePath(finding.file),
  };
  normalized.signature = findingSignature(normalized);
  return normalized;
}

export function auditProject(rootDir, options = {}) {
  const files = listSourceFiles(rootDir);
  const findings = [];
  const parseErrors = [];

  for (const file of files) {
    const code = fs.readFileSync(file, 'utf8');
    try {
      findings.push(...auditCode(code, file, options).map(normalizeFinding));
    } catch (error) {
      parseErrors.push({
        file,
        message: error.message,
      });
    }
  }

  return {
    filesScanned: files.length,
    findings,
    parseErrors,
  };
}

function loadBaseline(baselinePath) {
  if (!baselinePath || !fs.existsSync(baselinePath)) {
    return [];
  }

  const baseline = JSON.parse(fs.readFileSync(baselinePath, 'utf8'));
  const entries = Array.isArray(baseline) ? baseline : baseline.entries || [];
  return entries.map((entry) => entry.signature || findingSignature(entry));
}

export function applyBaseline(result, baselineEntries) {
  const baselineSet = new Set(baselineEntries);
  const findingSet = new Set(result.findings.map((finding) => finding.signature));

  return {
    ...result,
    baselineTotal: baselineSet.size,
    newFindings: result.findings.filter((finding) => !baselineSet.has(finding.signature)),
    staleBaselineEntries: [...baselineSet].filter((signature) => !findingSet.has(signature)),
  };
}

function writeBaselineFile(result, baselinePath) {
  const payload = {
    version: 1,
    description: 'Temporary baseline for icon-only control accessible-name findings. Remove entries as the UI is cleaned up.',
    generatedAt: new Date().toISOString(),
    entries: result.findings.map((finding) => ({
      signature: finding.signature,
      file: finding.file,
      line: finding.line,
      column: finding.column,
      element: finding.element,
      reason: finding.reason,
    })),
  };

  fs.mkdirSync(path.dirname(baselinePath), { recursive: true });
  fs.writeFileSync(baselinePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function relativePath(filePath) {
  return path.relative(process.cwd(), filePath).replaceAll(path.sep, '/');
}

function printTextReport(result) {
  console.log('Icon-only controls accessibility audit');
  console.log(`Files scanned: ${result.filesScanned}`);
  console.log(`Findings: ${result.findings.length}`);
  console.log(`Parse errors: ${result.parseErrors.length}`);

  if (typeof result.baselineTotal === 'number') {
    console.log(`Baseline entries: ${result.baselineTotal}`);
    console.log(`New findings: ${result.newFindings.length}`);
    console.log(`Stale baseline entries: ${result.staleBaselineEntries.length}`);
  }

  if (result.parseErrors.length > 0) {
    console.log('\nParse errors:');
    for (const error of result.parseErrors) {
      console.log(`- ${relativePath(error.file)}: ${error.message}`);
    }
  }

  const reportedFindings = result.newFindings || result.findings;

  if (reportedFindings.length > 0) {
    console.log('\nControls missing a robust accessible name:');
    for (const finding of reportedFindings) {
      console.log(
        `- ${relativePath(finding.file)}:${finding.line}:${finding.column} ` +
          `${finding.element} (${finding.reason})`,
      );
    }
  }

  if (reportedFindings.length === 0 && result.parseErrors.length === 0) {
    if (typeof result.baselineTotal === 'number') {
      console.log('\nAudit passed: no new icon-only control accessibility findings.');
      return;
    }
    console.log('\nAudit passed: no icon-only control accessibility findings.');
  }
}

function runCli() {
  const options = parseArgs(process.argv.slice(2));
  let result = auditProject(options.root, { includeComponents: options.includeComponents });

  if (options.writeBaseline) {
    writeBaselineFile(result, options.writeBaseline);
  }

  if (options.baseline) {
    result = applyBaseline(result, loadBaseline(options.baseline));
  }

  if (options.format === 'json') {
    console.log(JSON.stringify(result, null, 2));
  } else {
    printTextReport(result);
  }

  const failingFindings = result.newFindings || result.findings;
  if (result.parseErrors.length > 0 || (options.strict && failingFindings.length > 0)) {
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  runCli();
}
