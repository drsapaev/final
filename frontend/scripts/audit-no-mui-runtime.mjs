#!/usr/bin/env node

import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, '..');

const scanRoots = [
  path.join(frontendRoot, 'src', 'pages'),
  path.join(frontendRoot, 'src', 'components'),
];

const runtimeExtensions = new Set(['.js', '.jsx', '.ts', '.tsx']);
const ignoredFilePatterns = [
  /\.test\.[jt]sx?$/i,
  /\.spec\.[jt]sx?$/i,
  /\.stories\.[jt]sx?$/i,
];

const disallowedPatterns = [
  {
    name: '@mui package import',
    pattern: /['"]@mui\//,
  },
  {
    name: '@material-ui package import',
    pattern: /['"]@material-ui\//,
  },
  {
    name: 'Mui-prefixed runtime symbol',
    pattern: /\bMui[A-Z0-9_][A-Za-z0-9_]*/,
  },
];

function shouldScanFile(filePath) {
  const ext = path.extname(filePath);
  if (!runtimeExtensions.has(ext)) {
    return false;
  }
  const basename = path.basename(filePath);
  return !ignoredFilePatterns.some((pattern) => pattern.test(basename));
}

function walk(directory) {
  const entries = readdirSync(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(fullPath));
      continue;
    }
    if (entry.isFile() && shouldScanFile(fullPath)) {
      files.push(fullPath);
    }
  }

  return files;
}

function lineAndColumn(source, index) {
  const before = source.slice(0, index);
  const lines = before.split(/\r?\n/);
  const line = lines.length;
  const column = lines[lines.length - 1].length + 1;
  return { line, column };
}

const findings = [];

for (const root of scanRoots) {
  for (const filePath of walk(root)) {
    const source = readFileSync(filePath, 'utf8');
    for (const { name, pattern } of disallowedPatterns) {
      const match = pattern.exec(source);
      if (!match) {
        continue;
      }
      const { line, column } = lineAndColumn(source, match.index);
      findings.push({
        file: path.relative(frontendRoot, filePath).replaceAll(path.sep, '/'),
        line,
        column,
        rule: name,
        value: match[0],
      });
    }
  }
}

if (findings.length > 0) {
  console.error('No-new-MUI runtime gate failed.');
  console.error('MUI imports/usages are not allowed in frontend/src/pages or frontend/src/components.');
  console.error('Use existing clinic design-system primitives instead, or create a dedicated approved migration plan.');
  console.error('');
  for (const finding of findings) {
    console.error(
      `- ${finding.file}:${finding.line}:${finding.column} ${finding.rule} (${finding.value})`,
    );
  }
  process.exit(1);
}

console.log('No-new-MUI runtime gate passed: 0 MUI imports/usages in pages/components.');
