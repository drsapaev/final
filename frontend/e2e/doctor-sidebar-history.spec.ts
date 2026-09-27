// @ts-check
import { test, expect } from '@playwright/test';
import { installAuthenticatedQaHarness } from './support/authenticatedQa';

/**
 * PR 3351 (review round 5, P1): push-контракт query-sidebar doctor-панелей.
 *
 * Round 4 сделал replace БЕЗУСЛОВНЫМ для всех presets с
 * navigation === 'query' — включая doctor/cardiology/dermatology/dentistry.
 * Это прямо противоречило контракту P-029 (useDoctorPanelState):
 * browser Back обязан ходить МЕЖДУ вкладками панели, а replace
 * размонтировал панель целиком вместе с несохранёнными клиническими
 * черновиками (visitData, bloodTestForm, emr) — cross-panel clinical
 * regression. Round 5 вернул push для всех маршрутов, кроме LabPanel
 * (replace последней нужен для sentinel-инварианта «под sentinel ровно
 * одна /lab-запись»).
 *
 * Сценарий ревью (cardiology):
 *   /health → /doctor/cardiology?tab=visit
 *   → Sidebar patients
 *   → Back → снова tab=visit, панель не размонтирована
 *   → Back → /health (ровно одна запись добавлена переключением вкладки).
 */
test.describe('Doctor panel sidebar history contract (PR 3351 review round 5)', () => {
  test.use({ viewport: { width: 1440, height: 1100 } });

  test('cardiology sidebar tab switch pushes history: Back returns to the previous tab without unmounting the panel', async ({ page }) => {
    await installAuthenticatedQaHarness(page, { role: 'Doctor' });

    await page.goto('/health');
    await page.goto('/doctor/cardiology?tab=visit');
    const sidebarNav = page.locator('.mac-sidebar-nav');
    await expect(sidebarNav).toBeVisible();
    // Панель смонтировалась (данные — QA-моки, достаточно settle).
    await page.waitForTimeout(700);
    expect(new URL(page.url()).searchParams.get('tab')).toBe('visit');

    // Sidebar → 'Пациенты': query-навигация — PUSH (контракт P-029).
    await sidebarNav.getByRole('button', { name: 'Пациенты' }).click();
    await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('patients');

    // Back #1: возврат на tab=visit ВНУТРИ панели — панель не размонтирована
    // (replace-поведение round 4 вытолкнуло бы на /health целиком).
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/doctor/cardiology');
    await expect.poll(() => new URL(page.url()).searchParams.get('tab'), { timeout: 4000 }).toBe('visit');
    await expect(sidebarNav).toBeVisible();

    // Back #2: выход на предыдущую страницу — переключение вкладки добавило
    // ровно ОДНУ history-запись.
    await page.evaluate(() => window.history.back());
    await expect.poll(() => new URL(page.url()).pathname, { timeout: 4000 }).toBe('/health');
  });
});
