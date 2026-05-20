import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'src/App.jsx'), 'utf8');

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram Mini App expired link guardrails', () => {
  it('maps expired entry-token reasons to patient-safe copy', () => {
    const reasonMapping = sourceBetween(
      appSource,
      "const MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS = new Set",
      'function createMiniAppAppointmentPreviewForm()'
    );

    expect(reasonMapping).toContain("'entry_token_invalid'");
    expect(reasonMapping).toContain("'entry_token_expired'");
    expect(reasonMapping).toContain('Ссылка устарела. Откройте Mini App заново из Telegram');
    expect(reasonMapping).toContain('MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS.has(reason)');
    expect(reasonMapping).toContain('return MINI_APP_EXPIRED_ENTRY_TOKEN_MESSAGE;');
    expect(reasonMapping).toContain('return MINI_APP_SESSION_UNCONFIRMED_MESSAGE;');
    expect(reasonMapping).not.toContain('Request failed with status code');
  });

  it('keeps handled Mini App API errors out of the global raw-toast path', () => {
    const handledConfig = sourceBetween(
      appSource,
      'const MINI_APP_HANDLED_ERROR_REQUEST_CONFIG = {',
      'const MINI_APP_ERROR_ALERT_PROPS = {'
    );
    const miniAppShell = sourceBetween(
      appSource,
      'function TelegramMiniAppPatientShell() {',
      'const previewAppointment = appointmentPreview.payload?.appointment || null;'
    );

    expect(handledConfig).toContain('silent: true');
    expect(handledConfig).toContain('expectedErrorStatuses: [400, 403, 503]');

    [
      '/telegram/mini-app/patient/manifest',
      '/telegram/mini-app/forms/manifest',
      '/telegram/mini-app/cabinet/manifest',
      '/telegram/mini-app/payments/manifest',
      '/telegram/mini-app/results/manifest',
      '/telegram/mini-app/appointments/preview',
    ].forEach((endpoint) => {
      expect(miniAppShell).toContain(
        `api.post('${endpoint}', ${endpoint.endsWith('/preview') ? 'requestBody' : '{ initData }'}, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)`
      );
    });
  });

  it('keeps the session error state visually and accessibly distinct', () => {
    const statusBadge = sourceBetween(
      appSource,
      'function getMiniAppStatusBadge(status) {',
      'function createMiniAppAppointmentPreviewForm()'
    );
    const heroMarkup = sourceBetween(
      appSource,
      '<Badge\n            variant={statusBadge.variant}',
      '{state.status === \'ready\' && ('
    );

    expect(statusBadge).toContain("case 'error':");
    expect(statusBadge).toContain("variant: 'danger'");
    expect(statusBadge).toContain('Сессия недоступна');
    expect(heroMarkup).toContain("aria-live={state.status === 'error' ? 'assertive' : 'polite'}");
    expect(heroMarkup).toContain('<Alert severity="error" style={miniAppNoticeStyle} {...MINI_APP_ERROR_ALERT_PROPS}>');
    expect(appSource).toContain("role: 'alert'");
    expect(appSource).toContain("'aria-live': 'assertive'");
  });

  it('allows the status badge to wrap instead of crowding the mobile title', () => {
    const heroStyle = sourceBetween(
      appSource,
      'const miniAppHeroStyle = {',
      'const miniAppKickerStyle = {'
    );
    const badgeStyle = sourceBetween(
      appSource,
      'const miniAppStatusBadgeStyle = {',
      'const miniAppNoticeStyle = {'
    );

    expect(heroStyle).toContain("flexWrap: 'wrap'");
    expect(badgeStyle).toContain("maxWidth: '100%'");
    expect(badgeStyle).toContain("whiteSpace: 'normal'");
    expect(badgeStyle).toContain("textAlign: 'center'");
  });
});
