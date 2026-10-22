import { describe, expect, it } from 'vitest';

describe('AnalyticsPage module initialization', () => {
  it('loads the route module and its chart dependencies without throwing', async () => {
    const analyticsPage = await import('./AnalyticsPage');

    expect(analyticsPage.default).toEqual(expect.any(Function));
  });
});
