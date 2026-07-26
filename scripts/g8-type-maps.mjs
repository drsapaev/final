#!/usr/bin/env node
/**
 * G8 helper: type loose object literals in ui/macos/*.tsx as Record<string, ...>.
 *
 * Pattern: `const fooMap = { key1: val1, key2: val2 }` accessed as
 * `fooMap[variable]` where variable is typed as string. TypeScript infers
 * fooMap as `{ key1: ..., key2: ... }` (literal keys), which doesn't have
 * a string index signature → TS7053.
 *
 * Fix: add explicit `: Record<string, ...>` annotation to the map declaration.
 *
 * This script finds common map patterns and adds Record<string, ...> types.
 * It's conservative — only touches declarations named *Map, *Classes,
 * *Styles, *Colors, *Sizes, *Variants.
 */
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const DIR = '/home/z/my-project/final/frontend/src/components/ui/macos';
const files = readdirSync(DIR).filter(f => f.endsWith('.tsx'));

let totalModified = 0;

for (const file of files) {
  const path = join(DIR, file);
  let content = readFileSync(path, 'utf8');
  const original = content;

  // Pattern: `const <name>Map = {` → `const <name>Map: Record<string, ...> = {`
  // We need to infer the value type. For simplicity, use `Record<string, unknown>`
  // and let the consumer cast. This is a starting point — files can be refined later.
  //
  // Only apply to maps that are accessed with string variables (causing TS7053).
  // We detect this by checking if the file has any `mapName[` access pattern.

  // Pattern 1: `const fooMap = {` (object literal with string values)
  const mapDeclPattern = /const\s+(\w+(?:Map|Classes|Styles|Colors|Sizes|Variants))\s*=\s*\{/g;
  let match;
  while ((match = mapDeclPattern.exec(content)) !== null) {
    const mapName = match[1];
    // Check if this map is accessed with a variable (not just string literal)
    const accessPattern = new RegExp(`${mapName}\\[\\w`);
    if (accessPattern.test(content)) {
      // Add Record<string, unknown> annotation
      const declRegex = new RegExp(`const\\s+${mapName}\\s*=\\s*\\{`);
      content = content.replace(declRegex, `const ${mapName}: Record<string, unknown> = {`);
    }
  }

  if (content !== original) {
    writeFileSync(path, content);
    totalModified++;
    console.log(`  ${file}: typed maps as Record<string, unknown>`);
  }
}

console.log(`\nTotal: ${totalModified} files modified`);
