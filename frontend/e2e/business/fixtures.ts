/**
 * Shared fixtures for E2E business scenario tests.
 *
 * Provides:
 * - Mock authentication (bypasses real login for speed)
 * - Test data factories (patient, appointment, payment, etc.)
 * - API helpers (create appointment, check status, etc.)
 *
 * These tests run against the Vite dev server (frontend) which mocks
 * API responses when no backend is available. This allows E2E tests
 * to run in CI without a live backend.
 */

import { test as base, expect, type Page, type APIRequestContext } from '@playwright/test';

// === Test data factories ===

export interface TestPatient {
  id: number;
  first_name: string;
  last_name: string;
  phone: string;
  birth_date: string;
}

export interface TestAppointment {
  id: number;
  patient_id: number;
  doctor_id: number;
  status: string;
  appointment_date: string;
  appointment_time: string;
}

export const testPatient: TestPatient = {
  id: 1,
  first_name: 'Test',
  last_name: 'Patient',
  phone: '+998901234567',
  birth_date: '1990-01-15',
};

export const testDoctor = {
  id: 1,
  name: 'Dr. Test',
  specialization: 'cardiology',
};

// === API helpers ===

/**
 * Mock the login API response to bypass real authentication.
 * Sets the auth token in localStorage.
 */
export async function mockLogin(page: Page, role: 'admin' | 'doctor' | 'patient' = 'admin') {
  // Set auth token directly in localStorage
  await page.addInitScript((role) => {
    const token = `test-token-${role}`;
    const profile = {
      id: 1,
      email: `${role}@clinic.com`,
      role,
      first_name: 'Test',
      last_name: 'User',
    };
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_profile', JSON.stringify(profile));
  }, role);
}

/**
 * Mock API response for a given endpoint.
 */
export async function mockApi(page: Page, url: string, response: unknown, status = 200) {
  await page.route(`**/api/v1${url}`, async (route) => {
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
}

/**
 * Wait for an element to be visible and contain text.
 */
export async function expectVisibleWithText(page: Page, selector: string, text: string) {
  const el = page.locator(selector);
  await expect(el).toBeVisible();
  await expect(el).toContainText(text);
}

// === Extended test fixture ===

export const test = base.extend<{
  mockAuthPage: Page;
}>({
  mockAuthPage: async ({ page }, use) => {
    await mockLogin(page, 'admin');
    await use(page);
  },
});

export { expect };
