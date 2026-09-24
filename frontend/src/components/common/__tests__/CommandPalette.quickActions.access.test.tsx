/**
 * NURSE-V2 N2-5 (owner review P2) — the Command Palette quick actions
 * must pass the SAME canonical route gate as the palette's route items.
 *
 * The pin scenario: a Nurse opens Cmd+K on the tablet workspace and
 * sees «Поиск пациента» — but its target /clinical/search is
 * role-scoped WITHOUT Nurse, so the jump landed on /forbidden. The
 * quick-action list must derive from isRouteAccessibleToProfile of the
 * TARGET ROUTE, not from a hardcoded role shortcut.
 */

import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { CommandPalette } from '../CommandPalette';
import { renderWithProviders } from '@/test/renderWithProviders';

function openPalette() {
  fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
}

describe('CommandPalette quick actions — canonical route gate', () => {
  it('Nurse: no «Поиск пациента» and no «Новая запись» (targets are role-scoped without Nurse)', async () => {
    renderWithProviders(
      <CommandPalette profile={{ role: 'Nurse' }} navigate={vi.fn()} />,
    );
    openPalette();
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Поиск пациента')).not.toBeInTheDocument();
    expect(screen.queryByText('Новая запись')).not.toBeInTheDocument();
  });

  it('Doctor: «Поиск пациента» stays (clinical-search allows Doctor)', async () => {
    renderWithProviders(
      <CommandPalette profile={{ role: 'Doctor' }} navigate={vi.fn()} />,
    );
    openPalette();
    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument();
    });
    expect(screen.getByText('Поиск пациента')).toBeInTheDocument();
    // the registrar-only quick action stays hidden for a Doctor
    expect(screen.queryByText('Новая запись')).not.toBeInTheDocument();
  });

  it('Registrar: both quick actions stay (registrar + clinical-search allow it)', async () => {
    renderWithProviders(
      <CommandPalette profile={{ role: 'Registrar' }} navigate={vi.fn()} />,
    );
    openPalette();
    await waitFor(() => {
      expect(screen.getByText('Поиск пациента')).toBeInTheDocument();
    });
    expect(screen.getByText('Новая запись')).toBeInTheDocument();
  });
});
