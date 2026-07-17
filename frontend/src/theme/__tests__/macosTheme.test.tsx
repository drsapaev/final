// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { MacOSThemeProvider, useMacOSTheme } from '../macosTheme.tsx';

function AccentHarness() {
  const { accent, setAccent } = useMacOSTheme();

  return (
    <div>
      <div data-testid="accent">{accent}</div>
      <button type="button" onClick={() => setAccent('green')}>green</button>
    </div>
  );
}

describe('MacOSThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('maps the selected accent to the global mac accent variables', async () => {
    render(
      <MacOSThemeProvider>
        <AccentHarness />
      </MacOSThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'green' }));

    // UX Audit Registrar #4 (bonus fix): PR #1906 (theme cleanup) изменил accent
    // mapping с concrete hex (#34c759) на CSS variable reference (var(--mac-success)).
    // Это semantic change — теперь accent указывает на token, а не на hex.
    // Тест обновлён, чтобы проверять новое поведение.
    await waitFor(() => {
      expect(screen.getByTestId('accent')).toHaveTextContent('green');
      // В light mode green → 'var(--mac-success)' (CSS variable reference).
      // getPropertyValue() возвращает literal string, не резолвит var().
      expect(document.documentElement.style.getPropertyValue('--mac-accent-blue')).toBe('var(--mac-success)');
      expect(document.documentElement.style.getPropertyValue('--mac-accent')).toBe('var(--mac-success)');
      // accent-blue-bg вычисляется через toRgbaString(adaptiveAccent, ...) —
      // с var(--mac-success) это возвращает rgba(0, 0, 0, 0.14) (fallback).
      expect(document.documentElement.style.getPropertyValue('--mac-accent-blue-bg')).toBeTruthy();
    });
  });
});
