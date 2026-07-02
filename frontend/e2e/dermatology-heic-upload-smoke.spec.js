// @ts-check
import fs from 'fs';
import { test, expect } from '@playwright/test';
import { installAuthenticatedQaHarness } from './support/authenticatedQa.js';

const heicSmokeFile = process.env.HEIC_SMOKE_FILE;

test.describe('Dermatology HEIC upload manual smoke', () => {
  test.skip(!heicSmokeFile, 'Set HEIC_SMOKE_FILE to a local .heic/.heif file to run this manual smoke.');

  test('converts a local HEIC fixture to JPEG multipart upload', async ({ page }) => {
    test.setTimeout(180_000);

    expect(fs.existsSync(heicSmokeFile), `HEIC fixture should exist at ${heicSmokeFile}`).toBe(true);
    const expectedJpegName = heicSmokeFile.replace(/^.*[\\/]/, '').replace(/\.(heic|heif)$/i, '.jpg');

    const pageErrors = [];
    const uploadRequests = [];

    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    await installAuthenticatedQaHarness(page, { role: 'Doctor' });
    await page.route('**/api/v1/visits/*/files', async (route) => {
      const request = route.request();
      const bodyText = (request.postDataBuffer() || Buffer.from('')).toString('latin1');

      uploadRequests.push({
        url: request.url(),
        method: request.method(),
        contentType: request.headers()['content-type'] || '',
        hasPhotoBeforeKind: bodyText.includes('photo_before'),
        hasVisitId: bodyText.includes('4242'),
        hasExpectedJpegName: bodyText.includes(expectedJpegName),
        hasJpegContentType: bodyText.includes('Content-Type: image/jpeg'),
        bodyLength: bodyText.length,
      });

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'qa-heic-photo',
          url: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2w==',
        }),
      });
    });

    await page.goto('/doctor/dermatology?patientId=42&visitId=4242&tab=photos', {
      waitUntil: 'domcontentloaded',
    });
    await expect(page.locator('.app-shell[data-route-id="doctor-dermatology"]')).toBeVisible({
      timeout: 15_000,
    });

    const startedAt = Date.now();
    await page.locator('input[type="file"]').first().setInputFiles(heicSmokeFile);

    await expect.poll(() => uploadRequests.length, {
      timeout: 120_000,
      message: 'HEIC upload should post converted JPEG FormData',
    }).toBe(1);

    const upload = uploadRequests[0];
    expect(upload).toMatchObject({
      method: 'POST',
      hasPhotoBeforeKind: true,
      hasVisitId: true,
      hasExpectedJpegName: true,
      hasJpegContentType: true,
    });
    expect(upload.url).toContain('/api/v1/visits/4242/files');
    expect(upload.contentType).toContain('multipart/form-data');
    expect(upload.bodyLength).toBeGreaterThan(0);
    expect(pageErrors).toEqual([]);

    test.info().annotations.push({
      type: 'duration-ms',
      description: String(Date.now() - startedAt),
    });
  });
});
