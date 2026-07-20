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

describe('Telegram Mini App expired link guardrails', () => {
  it('maps expired entry-token reasons to patient-safe copy', () => {
    const sessionMapping = sourceBetween(
      appSource,
      'const MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS = new Set',
      'function isMiniAppCapabilityEnabled(capability)'
    );

    expect(sessionMapping).toContain('\'entry_token_invalid\'');
    expect(sessionMapping).toContain('\'entry_token_expired\'');
    expect(appSource).toContain('Ссылка устарела. Откройте Mini App заново из Telegram');
    expect(sessionMapping).toContain('MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS.has(reason)');
    expect(sessionMapping).toContain('return translateMiniAppText(languageCode, \'sessionExpired\');');
    expect(sessionMapping).toContain('return translateMiniAppText(languageCode, \'sessionNotConfirmed\');');
    expect(sessionMapping).not.toContain('Request failed with status code');
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
      'const miniAppPageStyle = {'
    );

    expect(handledConfig).toContain('silent: true');
    expect(handledConfig).toContain('expectedErrorStatuses: [400, 403, 503]');

    [
      'api.post(\'/telegram/mini-app/patient/manifest\', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'api.post(\'/telegram/mini-app/cabinet/summary\', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'api.post(\'/telegram/mini-app/forms/preview\', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'api.post(\'/telegram/mini-app/appointments/preview\', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'api.post(\'/telegram/mini-app/appointments\', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'MINI_APP_HANDLED_ERROR_REQUEST_CONFIG',
    ].forEach((expectedSnippet) => {
      expect(miniAppShell).toContain(expectedSnippet);
    });
  });

  it('keeps the session error state visually and accessibly distinct', () => {
    const statusBadge = sourceBetween(
      appSource,
      'function getMiniAppStatusBadge(status, languageCode) {',
      'function isMiniAppCapabilityEnabled(capability)'
    );
    const heroMarkup = sourceBetween(
      appSource,
      '<Badge\n            variant={statusBadge.variant}',
      '{state.status === \'ready\' && ('
    );

    expect(statusBadge).toContain('case \'error\':');
    expect(statusBadge).toContain('variant: \'danger\'');
    expect(statusBadge).toContain('\'sessionUnavailableBadge\'');
    expect(heroMarkup).toContain('aria-live={state.status === \'error\' ? \'assertive\' : \'polite\'}');
    expect(heroMarkup).toContain('<Alert severity="error" style={miniAppNoticeStyle} {...MINI_APP_ERROR_ALERT_PROPS}>');
    expect(appSource).toContain('role: \'alert\'');
    expect(appSource).toContain('\'aria-live\': \'assertive\'');
  });

  it('allows the status badge to wrap instead of crowding the mobile title', () => {
    const heroStyle = sourceBetween(
      appSource,
      'const miniAppHeroStyle = {',
      'const miniAppKickerStyle = {'
    );
    const heroTitleGroupStyle = sourceBetween(
      appSource,
      'const miniAppHeroTitleGroupStyle = {',
      'const miniAppKickerStyle = {'
    );
    const badgeStyle = sourceBetween(
      appSource,
      'const miniAppStatusBadgeStyle = {',
      'const miniAppNoticeStyle = {'
    );
    const heroMarkup = sourceBetween(
      appSource,
      '<section style={miniAppHeroStyle}>',
      '</section>'
    );

    expect(heroStyle).toContain('flexWrap: \'wrap\'');
    expect(heroStyle).toContain('rowGap: \'10px\'');
    expect(heroTitleGroupStyle).toContain('flex: \'1 1 220px\'');
    expect(heroTitleGroupStyle).toContain('minWidth: 0');
    expect(heroMarkup).toContain('<div style={miniAppHeroTitleGroupStyle}>');
    expect(badgeStyle).toContain('maxWidth: \'min(100%, 220px)\'');
    expect(badgeStyle).toContain('whiteSpace: \'normal\'');
    expect(badgeStyle).toContain('textAlign: \'center\'');
  });
});
