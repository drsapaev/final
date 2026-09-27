// @ts-check
import fs from 'fs';
import { test, expect } from '@playwright/test';
import { installAuthenticatedQaHarness } from './support/authenticatedQa';

const heicSmokeFile = process.env.HEIC_SMOKE_FILE;

interface UploadRequestEvidence {
  url: string;
  method: string;
  contentType: string;
  hasCategoryTags: boolean;
  hasPrivatePermission: boolean;
  hasPatientId: boolean;
  hasVisitId: boolean;
  hasExpectedJpegName: boolean;
  hasJpegContentType: boolean;
  bodyLength: number;
}

test.describe('Dermatology HEIC upload manual smoke', () => {
  test.skip(!heicSmokeFile, 'Set HEIC_SMOKE_FILE to a local .heic/.heif file to run this manual smoke.');

  test('converts a local HEIC fixture to JPEG multipart upload', async ({ page }) => {
    test.setTimeout(180_000);

    expect(fs.existsSync(heicSmokeFile!), `HEIC fixture should exist at ${heicSmokeFile}`).toBe(true);
    const expectedJpegName = heicSmokeFile!.replace(/^.*[\\/]/, '').replace(/\.(heic|heif)$/i, '.jpg');

    const pageErrors: string[] = [];
    const uploadRequests: UploadRequestEvidence[] = [];

    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    await installAuthenticatedQaHarness(page, { role: 'Doctor' });

    // Derma audit item 8: gallery lives in the ACTIVE VISIT screen and uploads
    // through the canonical file API POST /files/upload (previously the retired
    // photos tab posted to /visits/{id}/files). Resolve the deep-linked visit
    // from a mocked derma queue so the visit screen (and its gallery) renders.
    await page.route('**/api/v1/registrar/queues/today', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          queues: [{
            queue_id: 1,
            specialist_id: 98001,
            specialist_name: 'SYNTHETIC-QA Doctor',
            specialty: 'derma',
            cabinet: '12',
            entries: [{
              id: 4242,
              record_type: 'appointment',
              source_type: 'manual',
              appointment_id: 4242,
              patient_id: 42,
              patient_last_name: 'СИНТЕТИК',
              patient_first_name: 'Пациент',
              patient_fio: 'СИНТЕТИК Пациент Тестович',
              patient_name: 'СИНТЕТИК Пациент Тестович',
              patient_phone: '+998900000000',
              doctor_id: 98001,
              doctor_name: 'SYNTHETIC-QA Doctor',
              department: 'derma',
              services: [],
              cost: 0,
              total_amount: 0,
              payment_status: 'unpaid',
              payment_type: 'cash',
              canonical_status: 'in_cabinet',
              status: 'in_cabinet',
              queue_position: 1,
              queue_tag: 'derma',
              visit_id: 4242,
              appointment_date: '2026-09-27',
              appointment_time: '10:00',
              created_at: '2026-09-27T09:00:00+05:00',
              available_actions: ['in_cabinet', 'complete'],
              queue_entry_id: 4242,
              can_start_visit: true,
              record_kind: 'appointment',
              source_kind: 'manual',
            }],
            stats: { total: 1, waiting: 0, called: 1, served: 0, online_entries: 0 },
            opened_at: '2026-09-27T09:00:00+05:00',
          }],
          total_queues: 1,
          date: '2026-09-27',
          timezone: 'Asia/Tashkent',
        }),
      });
    });

    await page.route('**/api/v1/files/upload', async (route) => {
      const request = route.request();
      const bodyText = (request.postDataBuffer() || Buffer.from('')).toString('latin1');

      uploadRequests.push({
        url: request.url(),
        method: request.method(),
        contentType: request.headers()['content-type'] || '',
        hasCategoryTags: bodyText.includes('dermatology,photo,examination'),
        hasPrivatePermission: bodyText.includes('private'),
        hasPatientId: bodyText.includes('42'),
        hasVisitId: bodyText.includes('4242'),
        hasExpectedJpegName: bodyText.includes(expectedJpegName),
        hasJpegContentType: bodyText.includes('Content-Type: image/jpeg'),
        bodyLength: bodyText.length,
      });

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 777,
          filename: expectedJpegName,
          mime_type: 'image/jpeg',
          file_type: 'image',
          permission: 'private',
          patient_id: 42,
          visit_id: 4242,
          tags: ['dermatology', 'photo', 'examination'],
          file_path: 'synthetic/path.jpg',
          file_size: 1024,
          status: 'active',
          owner_id: 98001,
          created_at: '2026-09-27T09:05:00+05:00',
          updated_at: '2026-09-27T09:05:00+05:00',
        }),
      });
    });

    await page.goto('/doctor/dermatology?patientId=42&visitId=4242', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.locator('.app-shell[data-route-id="doctor-dermatology"]')).toBeVisible({
      timeout: 15_000,
    });

    // Derma audit item 8: the visit gallery (visit screen) owns photo upload.
    const gallery = page.locator('.derma-gallery');
    await expect(gallery).toBeVisible({ timeout: 20_000 });

    const startedAt = Date.now();
    await gallery.locator('input[type="file"]').setInputFiles(heicSmokeFile!);

    await expect.poll(() => uploadRequests.length, {
      timeout: 120_000,
      message: 'HEIC upload should post converted JPEG FormData',
    }).toBe(1);

    const upload = uploadRequests[0];
    expect(upload).toMatchObject({
      method: 'POST',
      hasCategoryTags: true,
      hasPrivatePermission: true,
      hasPatientId: true,
      hasVisitId: true,
      hasExpectedJpegName: true,
      hasJpegContentType: true,
    });
    expect(upload.url).toContain('/api/v1/files/upload');
    expect(upload.contentType).toContain('multipart/form-data');
    expect(upload.bodyLength).toBeGreaterThan(0);
    expect(pageErrors).toEqual([]);

    test.info().annotations.push({
      type: 'duration-ms',
      description: String(Date.now() - startedAt),
    });
  });
});
