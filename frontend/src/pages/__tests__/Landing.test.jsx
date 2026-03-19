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
    expect(screen.getByRole('button', { name: /Открыть демо/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Смотреть 2-минутный обзор/i })).toBeInTheDocument();
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

  it('cycles localized hero copy when the language button is pressed', async () => {
    const user = userEvent.setup();

    renderLanding();

    await user.click(screen.getByRole('button', { name: /Сменить язык/i }));

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
