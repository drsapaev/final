import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { MacOSThemeProvider, useMacOSTheme } from '../macosTheme.jsx';

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

    await waitFor(() => {
      expect(screen.getByTestId('accent')).toHaveTextContent('green');
      expect(document.documentElement.style.getPropertyValue('--mac-accent-blue')).toBe('#34c759');
      expect(document.documentElement.style.getPropertyValue('--mac-accent')).toBe('#34c759');
      expect(document.documentElement.style.getPropertyValue('--mac-accent-blue-bg')).toContain('rgba(52, 199, 89');
    });
  });
});
