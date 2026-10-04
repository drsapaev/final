import React from 'react';
import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatCard from '../StatCard';

describe('StatCard loading accessibility', () => {
  it('exposes a polite busy status and hides decorative skeletons', () => {
    render(<StatCard loading title="Patients" value="42" />);

    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveAttribute('aria-busy', 'true');

    const decorativeSkeletons = status.querySelectorAll('[aria-hidden="true"]');
    expect(decorativeSkeletons).toHaveLength(3);
  });
});
