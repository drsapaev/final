import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'src/pages/TelegramMiniAppPatientShell.tsx'), 'utf8').replace(/\r\n/g, '\n');

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram Mini App protected runtime guardrails', () => {
  it('supports initData and entryToken auth without exposing raw identifiers in links', () => {
    const authBuilder = sourceBetween(
      appSource,
      'function getTelegramMiniAppAuthPayload(search, section) {',
      'function getTelegramMiniAppSelectedSection(search) {'
    );

    expect(authBuilder).toContain('const initData = getTelegramMiniAppInitData();');
    expect(authBuilder).toContain('const entryToken = getTelegramMiniAppEntryToken(search);');
    expect(authBuilder).toContain('initData,');
    expect(authBuilder).toContain('entryToken,');
    expect(authBuilder).toContain('section: selectedSection || undefined');
    expect(authBuilder).not.toContain('patientId');
    expect(authBuilder).not.toContain('telegramUserId');
    expect(authBuilder).not.toContain('chatId');
  });

  it('keeps protected section data behind Mini App auth payloads and handled errors', () => {
    const shellSource = sourceBetween(
      appSource,
      'function TelegramMiniAppPatientShell() {',
      'const miniAppPageStyle = {'
    );

    [
      '/telegram/mini-app/patient/manifest',
      '/telegram/mini-app/cabinet/summary',
      '/telegram/mini-app/forms/preview',
      '/telegram/mini-app/forms/submissions',
      '/telegram/mini-app/reports/download',
      '/telegram/mini-app/appointments/preview',
      '/telegram/mini-app/appointments',
    ].forEach((endpoint) => {
      expect(shellSource).toContain(endpoint);
    });

    expect(shellSource).toContain('authPayload');
    expect(shellSource).toContain('MINI_APP_HANDLED_ERROR_REQUEST_CONFIG');
    expect(shellSource).not.toContain('/patient?tab=');
    expect(shellSource).not.toContain('WebAppInfo');
  });

  it('keeps queue summary read-only from the patient Mini App surface', () => {
    const queuePanel = sourceBetween(
      appSource,
      '{selectedSection === \'queue\' && cabinetSummary.status === \'loading\' && (',
      '{selectedSection === \'visits\' && cabinetSummary.status === \'loading\' && ('
    );

    expect(queuePanel).toContain('currentQueueEntry');
    expect(queuePanel).toContain('t(\'queueInactive\')');
    expect(queuePanel).toContain('t(\'queueEmptyRecovery\')');
    expect(queuePanel).toContain('t(\'queuePrivacyNote\')');
    expect(queuePanel).not.toContain('api.post(');
    expect(queuePanel).not.toMatch(/queue_time|call_next|skip|cancel|move|mutat/i);
  });

  it('keeps report download protected and avoids provider/payment payload drift', () => {
    const reportDownloadHandler = sourceBetween(
      appSource,
      'const handleReportDownload = (report) => () => {',
      'const previewAppointment = appointmentPreview.payload?.appointment || null;'
    );

    expect(reportDownloadHandler).toContain('getTelegramMiniAppAuthPayload(location.search, \'results\')');
    expect(reportDownloadHandler).toContain('/telegram/mini-app/reports/download');
    expect(reportDownloadHandler).toContain('reportId: report.id');
    expect(reportDownloadHandler).toContain('responseType: \'blob\'');
    expect(reportDownloadHandler).toContain('getMiniAppReportFileName(report)');
    expect(reportDownloadHandler).not.toMatch(/payment_provider|provider_payload|providerPayload|transaction|webhook|invoice/i);
  });
});
