import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import Landing from '../Landing';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { TranslationProvider } from '../../hooks/useTranslation';
import { MacOSThemeProvider } from '../../theme/macosTheme.jsx';

function renderLanding() {
  return render(
    <MemoryRouter>
      <MacOSThemeProvider>
        <ThemeProvider>
          <TranslationProvider>
            <Landing />
          </TranslationProvider>
        </ThemeProvider>
      </MacOSThemeProvider>
    </MemoryRouter>
  );
}

describe('Landing', () => {
  beforeEach(() => {
    localStorage.getItem.mockImplementation(() => null);
    localStorage.setItem.mockImplementation(() => undefined);
  });

  it('renders a strong hero, repeated CTA and contact details', () => {
    renderLanding();

    expect(
      screen.getByRole('heading', {
        name: /Единая операционная панель клиники, которая ускоряет каждый прием/i
      })
    ).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Войти в систему/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /Активировать лицензию/i }).length).toBeGreaterThan(0);
    expect(
      screen.getByRole('heading', {
        name: /Одна система вместо десяти разрозненных инструментов/i
      })
    ).toBeInTheDocument();
    expect(screen.getByText(/\+998 \(95\) 104-34-34/i)).toBeInTheDocument();
  });

  it('cycles localized hero copy when the language button is pressed', async () => {
    const user = userEvent.setup();

    renderLanding();

    await user.click(screen.getByRole('button', { name: /Сменить язык/i }));

    expect(
      screen.getByRole('heading', {
        name: /Klinikaning har bir qabuli tezlashadigan yagona operatsion panel/i
      })
    ).toBeInTheDocument();
  });
});
