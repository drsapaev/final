import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import i18n from '@/i18n';
import AdminRouteSwitcher from '../AdminRouteSwitcher';

const switcherRoutes = [
  { current: 'admin-dashboard', path: '/admin' },
  { current: 'admin-analytics', path: '/admin/analytics' },
] as const;

describe('AdminRouteSwitcher active route', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('ru');
  });

  it.each(switcherRoutes)('marks canonical route $current as current', ({ current, path }) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <AdminRouteSwitcher current={current} />
      </MemoryRouter>,
    );

    const activeButtons = screen.getAllByRole('button').filter(
      (button) => button.getAttribute('aria-current') === 'page',
    );

    expect(activeButtons).toHaveLength(1);
    expect(activeButtons[0]).toHaveAttribute('aria-current', 'page');
  });
});
