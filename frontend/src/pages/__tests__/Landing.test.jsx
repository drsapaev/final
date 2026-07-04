import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import Landing from '../Landing';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { TranslationProvider } from '../../hooks/useTranslation';
import { MacOSThemeProvider } from '../../theme/macosTheme.jsx';

function renderLanding() {
  let root = document.getElementById('root');
  if (!root) {
    root = document.createElement('div');
    root.id = 'root';
    document.body.appendChild(root);
  }

  return render(
    <MemoryRouter>
      <MacOSThemeProvider>
        <ThemeProvider>
          <TranslationProvider>
            <Landing />
          </TranslationProvider>
        </ThemeProvider>
      </MacOSThemeProvider>
    </MemoryRouter>,
    { container: root }
  );
}

describe('Landing', () => {
  beforeEach(() => {
    localStorage.getItem.mockImplementation(() => null);
    localStorage.setItem.mockImplementation(() => undefined);
  });

  it('renders a multi-section SaaS landing with hero, modules, pricing and contacts', () => {
    renderLanding();

    expect(
      screen.getByRole('heading', {
        name: /Единая система управления клиникой, которая держит EMR, очередь и платежи в одном ритме/i
      })
    ).toBeInTheDocument();
    // UX Audit Stage 2: Hero primary CTA changed from "Открыть демо" to "Войти"
    // (uses copy.headerLogin now). There are 2 "Войти" buttons (header + hero).
    expect(screen.getAllByRole('button', { name: /^Войти$/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: /Посмотреть интерфейс/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Модули/i })).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /Модульная архитектура под реальные направления клиники/i
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /Три тарифа для малых клиник, растущих команд и сетей/i
      })
    ).toBeInTheDocument();
    expect(screen.getByText(/\+998 \(95\) 104-34-34/i)).toBeInTheDocument();
  });

  // UX Audit Stage 2: language cycle replaced with dropdown.
  // Test now: open dropdown → click UZ option → verify heading changed.
  it('switches to Uzbek when UZ option is selected in language dropdown', async () => {
    const user = userEvent.setup();

    renderLanding();

    // Click trigger button to open dropdown
    await user.click(screen.getByRole('button', { name: /Сменить язык/i }));

    // Find the UZ option in the dropdown listbox
    const listbox = screen.getByRole('listbox');
    const uzOption = within(listbox).getByText('O\'zbek');
    await user.click(uzOption);

    expect(
      screen.getByRole('heading', {
        name: /EMR, navbat va tolovlarni bitta ritmda ushlab turadigan yagona klinika boshqaruv tizimi/i
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        name: /Klinikaning real yonalishlari uchun modulli arxitektura/i
      })
    ).toBeInTheDocument();
  });

  it('applies landing-specific layout classes and cleans them up on unmount', () => {
    const root = document.createElement('div');
    root.id = 'root';
    document.body.appendChild(root);

    expect(root).not.toHaveClass('landing-root');
    expect(document.body).not.toHaveClass('landing-body');

    const { unmount } = renderLanding();

    expect(document.getElementById('root')).toHaveClass('landing-root');
    expect(document.body).toHaveClass('landing-body');

    unmount();

    expect(document.getElementById('root')).not.toHaveClass('landing-root');
    expect(document.body).not.toHaveClass('landing-body');
  });
});
