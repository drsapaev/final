import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import Landing from '../Landing';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { TranslationProvider } from '../../i18n/useTranslation';

function renderLanding() {
  let root = document.getElementById('root');
  if (!root) {
    root = document.createElement('div');
    root.id = 'root';
    document.body.appendChild(root);
  }

  return render(
    <MemoryRouter>
              <ThemeProvider>
          <TranslationProvider>
            <Landing />
          </TranslationProvider>
        </ThemeProvider>
    </MemoryRouter>,
    { container: root }
  );
}

describe('Landing', () => {
  beforeEach(() => {
    (localStorage.getItem as unknown as { mockImplementation: (cb: () => null) => void }).mockImplementation(() => null);
    (localStorage.setItem as unknown as { mockImplementation: (cb: () => undefined) => void }).mockImplementation(() => undefined);
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

  // PR-UI-16-4 (plan §PR-UI-16 AC: workflow diagram shows 7 steps): the flow
  // overview and the detail steps share one data source (workflow.stages),
  // so this pins both the 7-node diagram AND the 7 numbered detail steps,
  // plus their 1:1 node correspondence in rendering order.
  it('renders the 7-stage workflow with matching nodes and detail steps', () => {
    const { container } = renderLanding();

    const chips = Array.from(container.querySelectorAll('.landing-flow-chip'));
    const steps = Array.from(container.querySelectorAll('.landing-workflow-step'));

    expect(chips).toHaveLength(7);
    expect(steps).toHaveLength(7);

    const chipNodes = chips.map((chip) => chip.textContent?.trim());
    const stepNodes = steps.map((step) => step.querySelector('.landing-workflow-node')?.textContent?.trim());
    expect(stepNodes).toEqual(chipNodes);

    // Numbered markers 01..07 in order.
    const markers = steps.map((step) => step.querySelector('.landing-workflow-marker')?.textContent?.trim());
    expect(markers).toEqual(['01', '02', '03', '04', '05', '06', '07']);

    // Every stage carries a substantive title (workflow node + detail step).
    steps.forEach((step) => {
      expect(step.querySelector('h3')).not.toBeNull();
      expect(step.querySelector('p')).not.toBeNull();
    });
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
