/**
 * EMRSectionSkeleton tests (PR-UI-12-3, plan §PR-UI-12 item 1:
 * "EMR sections — skeleton loading").
 *
 * Covers the presentational skeleton component AND the EMRContainerV2 wiring
 * contract (source-level — the container's hook graph is too heavy to mount
 * in a unit test; the repo's established contract-test pattern reads the
 * source, cf. QueueManager.contract.test.tsx).
 */

import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

import EMRSectionSkeleton from '../EMRSectionSkeleton';

describe('EMRSectionSkeleton — presentation (PR-UI-12-3)', () => {
  it('renders the requested number of section skeletons', () => {
    const { container } = render(<EMRSectionSkeleton sections={6} />);
    expect(container.querySelectorAll('.emr-skeleton-section')).toHaveLength(6);
  });

  it('defaults to 6 sections (mirrors the EMR section stack)', () => {
    const { container } = render(<EMRSectionSkeleton />);
    expect(container.querySelectorAll('.emr-skeleton-section')).toHaveLength(6);
  });

  it('exposes a polite loading status with aria-busy and a label', () => {
    render(<EMRSectionSkeleton ariaLabel="Загрузка карты приёма…" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveAttribute('aria-label', 'Загрузка карты приёма…');
  });

  it('marks every decorative skeleton block aria-hidden', () => {
    const { container } = render(<EMRSectionSkeleton sections={2} />);
    const sections = container.querySelectorAll('.emr-skeleton-section');
    expect(sections).toHaveLength(2);
    sections.forEach((section) => {
      expect(section).toHaveAttribute('aria-hidden', 'true');
    });
    // Bones exist (header icon/title/badge + 3 body lines per section).
    expect(container.querySelectorAll('.emr-skeleton-bone').length).toBeGreaterThanOrEqual(12);
  });
});

describe('EMRContainerV2 — skeleton wiring contract (PR-UI-12-3)', () => {
  const read = (rel: string): string =>
    fs.readFileSync(path.join(process.cwd(), rel), 'utf-8');

  it('renders the skeleton stack on FIRST load only (isLoading && !data)', () => {
    const src = read('src/components/emr-v2/EMRContainerV2.tsx');
    // The loading signal is consumed from the EMR hook.
    expect(src).toContain('isLoading,');
    // The skeleton branch is guarded to initial load (no data yet) so
    // autosave/saving never flashes skeletons over in-progress input.
    expect(src).toContain('if (isLoading && !data)');
    expect(src).toContain('<EMRSectionSkeleton');
  });

  it('labels the skeleton via the i18n contract (5 locales)', () => {
    const locales = ['ru', 'en', 'kk', 'uz-Latn', 'uz-Cyrl'];
    for (const locale of locales) {
      const src = read(`src/i18n/locales/${locale}.ts`);
      const match = src.match(/emr_skeleton_aria: '(.+?)'/);
      expect(match, `locale ${locale} must define misc.emr_skeleton_aria`).not.toBeNull();
      expect(match?.[1]?.trim().length, `locale ${locale}: non-empty label`).toBeGreaterThan(0);
    }
    // The container resolves the label through t(), not a hardcoded string.
    const container = read('src/components/emr-v2/EMRContainerV2.tsx');
    expect(container).toContain('t(\'misc.emr_skeleton_aria\')');
  });
});
