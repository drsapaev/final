#!/usr/bin/env node
/**
 * G8 helper: remove PropTypes blocks from ui/macos/*.tsx files.
 * PropTypes is a legacy runtime validation library. With TypeScript props
 * interfaces, it's redundant. The `...(Component.propTypes || {})` self-ref
 * pattern causes TS7022 errors under strict mode.
 *
 * Strategy: for each .tsx file in src/components/ui/macos/, remove:
 *   1. `import PropTypes from 'prop-types';` lines
 *   2. `Component.propTypes = { ... };` blocks (multi-line)
 *   3. Trailing whitespace
 *
 * This is mechanical — TypeScript interfaces already validate props.
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIR = '/home/z/my-project/final/frontend/src/components/ui/macos';
const files = readdirSync(DIR).filter(f => f.endsWith('.tsx'));

let totalModified = 0;
let totalPropTypesRemoved = 0;
let totalImportsRemoved = 0;

for (const file of files) {
  const path = join(DIR, file);
  let content = readFileSync(path, 'utf8');
  const original = content;
  let propTypesRemoved = 0;
  let importsRemoved = 0;

  // 1. Remove `import PropTypes from 'prop-types';` (and variations)
  const importPattern = /import\s+PropTypes\s+from\s+['"]prop-types['"];\s*\n?/g;
  const importMatches = content.match(importPattern);
  if (importMatches) {
    content = content.replace(importPattern, '');
    importsRemoved = importMatches.length;
    totalImportsRemoved += importsRemoved;
  }

  // 2. Remove `Component.propTypes = { ... };` blocks (greedy multi-line)
  // Pattern: identifier.propTypes = { ... }; (allow }; on its own line or inline)
  const propTypesPattern = /\n\s*\w+\.propTypes\s*=\s*\{[\s\S]*?\};[ \t]*\n/g;
  const propTypesMatches = content.match(propTypesPattern);
  if (propTypesMatches) {
    content = content.replace(propTypesPattern, '\n');
    propTypesRemoved = propTypesMatches.length;
    totalPropTypesRemoved += propTypesRemoved;
  }

  if (content !== original) {
    writeFileSync(path, content);
    totalModified++;
    console.log(`  ${file}: -${importsRemoved} imports, -${propTypesRemoved} propTypes blocks`);
  }
}

console.log(`\nTotal: ${totalModified} files modified`);
console.log(`Total: ${totalImportsRemoved} prop-types imports removed`);
console.log(`Total: ${totalPropTypesRemoved} propTypes blocks removed`);
