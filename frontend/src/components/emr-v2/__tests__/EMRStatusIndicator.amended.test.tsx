
/**
 * EMRSTATUS-FE-001 (audit 3886, round 30).
 *
 * Red-first contract suite for the EMR primary status indicator.
 * On pre-fix source the "signed" display branch only fired for `isSigned`
 * and nested `isAmended` INSIDE it. The flags arrive from useEMR as mutually
 * exclusive booleans (status === 'signed' | 'amended'), so a clean amended
 * record fell through to the ordinary green "✓ saved" indicator and the
 * signed-with-amendments provenance was hidden from the primary status UI.
 *
 * Post-fix contract:
 *  - `amended` renders the signed-with-amendments label with the signed
 *    CSS posture and the timestamp tooltip (finalized provenance visible);
 *  - `signed` keeps its own label;
 *  - a plain unsaved draft keeps the "new document" label;
 *  - an amended record with NO timestamps keeps the explicit signed tooltip
 *    instead of a relative "saved N min ago" message.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import EMRStatusIndicator from '../EMRStatusIndicator';

vi.mock('@/i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      (params ? `${key}:${JSON.stringify(params)}` : key),
  }),
}));

describe('EMRSTATUS-FE-001 — amended records display signed-with-amendments provenance', () => {
  it('status "amended" (isAmended=true, isSigned=false) shows the signed-with-amendments label', () => {
    const { container } = render(
      <EMRStatusIndicator isAmended lastSaved="2026-11-10T12:00:00Z" />,
    );
    // Pre-fix this branch was the ordinary green "✓ <relative time>" save state.
    expect(screen.getByText('misc.esi_podpisana_s_popravkami')).toBeTruthy();
    expect(screen.queryByText(/✓/)).toBeNull();
    // Signed posture class is applied (not the saved/dirty/new ones).
    expect(container.firstElementChild?.className).toContain('emr-status-indicator--signed');
    expect(container.firstElementChild?.className).not.toContain('emr-status-indicator--saved');
  });

  it('amended tooltip carries the signed absolute-time provenance, not the autosave text', () => {
    const { container } = render(
      <EMRStatusIndicator isAmended lastSaved="2026-11-10T12:00:00Z" />,
    );
    const title = container.firstElementChild?.getAttribute('title') || '';
    expect(title.startsWith('misc.esi_podpisana_formatabsolutetime')).toBe(true);
    expect(title).toContain('lastSaved');
  });

  it('amended without timestamps keeps the explicit signed tooltip (never a relative "saved")', () => {
    const { container } = render(<EMRStatusIndicator isAmended />);
    expect(screen.getByText('misc.esi_podpisana_s_popravkami')).toBeTruthy();
    const title = container.firstElementChild?.getAttribute('title') || '';
    expect(title).toBe('misc.esi_dokument_podpisan_i_zaschisc');
  });

  it('CONTROL: status "signed" keeps its own label', () => {
    render(<EMRStatusIndicator isSigned lastSaved="2026-11-10T12:00:00Z" />);
    expect(screen.getByText('misc.esi_podpisana')).toBeTruthy();
  });

  it('CONTROL: signed + amended flags together still resolve to the amendments label', () => {
    render(<EMRStatusIndicator isSigned isAmended lastSaved="2026-11-10T12:00:00Z" />);
    expect(screen.getByText('misc.esi_podpisana_s_popravkami')).toBeTruthy();
  });

  it('CONTROL: unsaved draft keeps the new-document label', () => {
    render(<EMRStatusIndicator />);
    expect(screen.getByText('misc.esi_novyy_dokument')).toBeTruthy();
  });
});
