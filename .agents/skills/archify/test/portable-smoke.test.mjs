import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cliPath = path.join(packageRoot, 'bin', 'archify.mjs');

function runCli(...args) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd: packageRoot,
    encoding: 'utf8',
    timeout: 30_000,
  });
}

test('doctor reports that the vendored Archify package is ready', () => {
  const result = runCli('doctor');

  assert.equal(result.error, undefined, result.error?.message);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /Archify is ready\./);
});

test('demo renders a standalone HTML artifact outside the package', (t) => {
  const outputDirectory = mkdtempSync(path.join(os.tmpdir(), 'archify-portable-smoke-'));
  t.after(() => rmSync(outputDirectory, { recursive: true, force: true }));

  const result = runCli('demo', outputDirectory);

  assert.equal(result.error, undefined, result.error?.message);
  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout, /Demo ready:/);

  const artifact = readFileSync(path.join(outputDirectory, 'archify-demo.html'), 'utf8');
  assert.match(artifact, /<!doctype html>/i);
  assert.ok(artifact.length > 1_000, 'demo HTML should contain the rendered viewer');
});
