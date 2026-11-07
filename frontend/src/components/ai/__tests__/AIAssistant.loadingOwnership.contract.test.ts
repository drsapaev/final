/**
 * LABAI-FE-002 (post-merge review of #3909, source contract) — the AI
 * analysis loading flag has a single owner:
 *
 * - the LATEST analyzeData invocation owns `loading` — an older run's
 *   finally must not clear the flag a newer run raised (double-submit
 *   overlap between the click and the re-render that disables the
 *   trigger);
 * - the staleness of a published result is decided by the input CONTENT
 *   fingerprint, not by input object identity (parents pass inline data
 *   literals — identity changes on every incidental re-render).
 *
 * Red-first: on the pre-fix source the finally is an unconditional
 * `setLoading(false)` and the stale guard compares `dataRef.current !==
 * input` by identity, so both assertions below fail.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const readSource = (relative: string) =>
  fs.readFileSync(path.join(__dirname, relative), 'utf8');

describe('LABAI-FE-002 — loading-flag ownership and content-based staleness (source contract)', () => {
  const source = readSource('../AIAssistant.tsx');
  const analyzeBlock =
    source.match(/const analyzeData = async[\s\S]*?\n {2}\};/)?.[0] ?? '';

  it('pins the analyzeData block', () => {
    expect(analyzeBlock).not.toBe('');
    expect(analyzeBlock).toContain('setLoading(true)');
  });

  it('the finally releases the loading flag only for the LATEST run', () => {
    // A run/generation ref compared inside the finally, guarding the
    // setLoading(false) release.
    expect(analyzeBlock).toMatch(
      /finally\s*\{[\s\S]*?Ref\.current === (?:runId|generation)[\s\S]*?setLoading\(false\)/,
    );
  });

  it('staleness is decided by the input CONTENT fingerprint, not object identity', () => {
    // The captured input key is compared against the live fingerprint of
    // the input — no dataRef object-identity comparison remains.
    expect(analyzeBlock).not.toMatch(/dataRef\.current !== input/);
    expect(analyzeBlock).toMatch(/fingerprint/i);
  });
});
