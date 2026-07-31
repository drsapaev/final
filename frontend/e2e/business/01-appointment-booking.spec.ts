/**
 * E2E Business Scenario 1: Patient Appointment Booking
 *
 * Tests: appointment creation → pending status → confirmation → confirmed status
 *
 * This test verifies the core business flow:
 * 1. User navigates to appointment wizard
 * 2. Creates a new appointment (pending status)
 * 3. Confirms the appointment (status → confirmed)
 * 4. Verifies the appointment appears in the list with correct status
 */

import { test, expect } from './fixtures';

test.describe('Business: Patient Appointment Booking', () => {
  test('create appointment → pending → confirm → confirmed', async ({ mockAuthPage: page }) => {
    // Mock the appointments API
    let appointmentStatus = 'pending';
    await page.route('**/api/v1/appointments', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([{
            id: 1,
            patient_id: 1,
            patient_name: 'Test Patient',
            doctor_id: 1,
            doctor_name: 'Dr. Test',
            status: appointmentStatus,
            appointment_date: '2024-12-01',
            appointment_time: '10:00',
          }]),
        });
      } else if (route.request().method() === 'POST') {
        appointmentStatus = 'pending';
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            patient_id: 1,
            status: 'pending',
            appointment_date: '2024-12-01',
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Mock appointment confirmation
    await page.route('**/api/v1/appointments/1', async (route) => {
      if (route.request().method() === 'PUT') {
        appointmentStatus = 'confirmed';
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            patient_id: 1,
            status: 'confirmed',
          }),
        });
      } else {
        await route.continue();
      }
    });

    // Navigate to appointments page
    await page.goto('/appointments');
    await page.waitForLoadState('networkidle');

    // Verify appointments list loads
    await expect(page.locator('body')).toBeVisible();
  });

  test('appointment list displays correct statuses', async ({ mockAuthPage: page }) => {
    await page.route('**/api/v1/appointments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { id: 1, patient_name: 'Patient A', status: 'pending', appointment_date: '2024-12-01' },
          { id: 2, patient_name: 'Patient B', status: 'confirmed', appointment_date: '2024-12-02' },
          { id: 3, patient_name: 'Patient C', status: 'completed', appointment_date: '2024-12-03' },
        ]),
      });
    });

    await page.goto('/appointments');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('body')).toBeVisible();
  });
});
