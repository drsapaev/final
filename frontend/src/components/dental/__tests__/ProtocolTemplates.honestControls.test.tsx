/**
 * Audit 3892 round 3 — fail-first regression for DENTTMPL-FE-001:
 * the ProtocolTemplates "Create" and "Edit" controls used to toggle state
 * that no render path ever consumed — no editor appeared and nothing was
 * persisted. Until template editing is actually implemented, the controls
 * are honestly disabled with an explicit "not supported" notice.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ProtocolTemplates from '../ProtocolTemplates';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

describe('ProtocolTemplates honest controls (DENTTMPL-FE-001, audit 3892 round 3)', () => {
  it('the Create control is disabled with an explicit not-supported notice', () => {
    render(
      <ProtocolTemplates onSelectTemplate={vi.fn()} onClose={vi.fn()} />,
    );

    const createButton = screen.getByText('dental.dental_pt_btn_create').closest('button');
    expect(createButton).not.toBeNull();
    expect(createButton).toHaveProperty('disabled', true);
    expect(createButton?.getAttribute('title')).toBe('dental.dental_pt_create_unsupported');
    expect(screen.getByText('dental.dental_pt_create_unsupported')).toBeTruthy();
  });

  it('the Edit control is disabled in the card grid and the details view, and opens no editor', () => {
    const { container } = render(
      <ProtocolTemplates onSelectTemplate={vi.fn()} onClose={vi.fn()} />,
    );

    // Card-level edit controls are disabled.
    const cardEditButtons = screen.getAllByRole('button', {
      name: 'dental.dental_pt_create_unsupported',
    }).filter((button) => !button.textContent?.includes('dental.dental_pt_btn_create'));
    expect(cardEditButtons.length).toBeGreaterThan(0);
    for (const editButton of cardEditButtons) {
      expect(editButton).toHaveProperty('disabled', true);
    }

    // Open the first template's details — that surface stays functional.
    fireEvent.click(container.querySelectorAll('div[role="button"]')[0]);
    const detailsEdit = screen.getByText('dental.dental_pt_btn_edit').closest('button');
    expect(detailsEdit).not.toBeNull();
    expect(detailsEdit).toHaveProperty('disabled', true);
    // No template editor form ever mounts.
    expect(screen.queryByRole('form')).toBeNull();
  });
});
