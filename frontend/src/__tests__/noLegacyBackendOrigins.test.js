import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const SOURCE_ROOT = path.resolve(process.cwd(), 'src');
const LEGACY_BACKEND_ORIGIN_PATTERN = /http:\/\/(?:127\.0\.0\.1|localhost):8000\b/;
const EXCLUDED_DIR_SEGMENTS = ['__tests__'];
const EXCLUDED_FILE_SUFFIXES = ['.test.js', '.test.tsx', '.spec.js', '.spec.tsx'];

function collectSourceFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (EXCLUDED_DIR_SEGMENTS.some((segment) => fullPath.includes(segment))) {
        continue;
      }
      files.push(...collectSourceFiles(fullPath));
      continue;
    }

    if (!/\.(js|jsx|ts|tsx)$/.test(entry.name)) {
      continue;
    }

    if (EXCLUDED_FILE_SUFFIXES.some((suffix) => entry.name.endsWith(suffix))) {
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

describe('frontend network origin guardrails', () => {
  it('does not hardcode legacy backend origin 8000 in runtime source files', () => {
    const runtimeFiles = collectSourceFiles(SOURCE_ROOT);
    const matches = [];

    for (const filePath of runtimeFiles) {
      const content = fs.readFileSync(filePath, 'utf8');
      if (LEGACY_BACKEND_ORIGIN_PATTERN.test(content)) {
        matches.push(path.relative(SOURCE_ROOT, filePath));
      }
    }

    expect(matches).toEqual([]);
  });
});
