import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const appSource = fs.readFileSync(
  path.resolve(process.cwd(), 'src/pages/TelegramMiniAppPatientShell.tsx'),
  'utf8'
).replace(/\r\n/g, '\n');

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram Mini App onboarding guardrails', () => {
  it('keeps onboarding requests away from confirmed appointment creation', () => {
    const onboardingHandler = sourceBetween(
      appSource,
      'const handleOnboardingRequestSubmit = (event) => {',
      'const handlePatientFormFieldChange = (formId, field) => (event) => {'
    );

    expect(onboardingHandler).toContain('/telegram/mini-app/onboarding/requests');
    expect(onboardingHandler).toContain('buildMiniAppOnboardingRequestBody');
    expect(onboardingHandler).not.toContain('/telegram/mini-app/appointments');
    expect(onboardingHandler).not.toMatch(/patientId|payment|invoice|diagnosis|lab|emr/i);
  });

  it('does not fetch protected patient sections for onboarding scope manifests', () => {
    const manifestEffect = sourceBetween(
      appSource,
      'api.post(\'/telegram/mini-app/patient/manifest\', authPayload, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)',
      'const capabilities = state.manifest?.capabilities || {};'
    );

    expect(manifestEffect).toContain('manifest?.scope?.type === \'onboarding\'');
    expect(manifestEffect).toContain('if (isOnboardingManifest) {');
    expect(manifestEffect).toContain('status: \'idle\'');
    expect(manifestEffect.indexOf('if (isOnboardingManifest) {')).toBeLessThan(
      manifestEffect.indexOf('api.post(\'/telegram/mini-app/cabinet/summary\'')
    );
  });

  it('blocks protected onboarding sections with a safe CTA', () => {
    const onboardingBlockedPanel = sourceBetween(
      appSource,
      '{isOnboardingScope && selectedSection && selectedSection !== \'appointments\' && (',
      '{isOnboardingScope && (selectedSection === \'appointments\' || !selectedSection) && ('
    );

    expect(onboardingBlockedPanel).toContain('t(\'onboardingBlockedText\')');
    expect(onboardingBlockedPanel).toContain('handleMiniAppCapabilitySelect(\'appointments\')');
    expect(onboardingBlockedPanel).toContain('handleMiniAppSupportClick');
    expect(onboardingBlockedPanel).not.toContain('api.post(');
    expect(onboardingBlockedPanel).not.toMatch(/403|Request failed|entryToken|patientId/);
  });

  it('adds safe retry and support actions for unavailable and token-error states', () => {
    const statusAlerts = sourceBetween(
      appSource,
      '{state.status === \'unavailable\' && (',
      '{state.status === \'ready\' && ('
    );

    expect(statusAlerts).toContain('handleMiniAppRetry');
    expect(statusAlerts).toContain('handleMiniAppSupportClick');
    expect(statusAlerts).toContain('t(\'onboardingRetry\')');
    expect(statusAlerts).not.toMatch(/AxiosError|Traceback|entryToken=pma_|entryToken=pmo_/);
  });

  it('keeps approved onboarding states out of the editable request form until the patient reopens Telegram', () => {
    const onboardingGate = sourceBetween(
      appSource,
      'const canSubmitOnboardingRequest = Boolean(',
      'const handleMiniAppCapabilitySelect = (section) => {'
    );
    const onboardingSummary = sourceBetween(
      appSource,
      '{shouldShowMiniAppOnboardingSummary(onboardingStatus) && (',
      '{canSubmitOnboardingRequest && ('
    );

    expect(onboardingGate).toContain('canEditOnboardingRequest');
    expect(onboardingSummary).toContain('[\'linked_existing\', \'created_patient\'].includes(onboardingStatus)');
    expect(onboardingSummary).toContain('handleMiniAppReturnToTelegram');
    expect(onboardingSummary).toContain('t(\'onboardingSupport\')');
  });

  it('emits onboarding telemetry with a safe minimal payload', () => {
    const telemetryHelper = sourceBetween(
      appSource,
      'function emitMiniAppOnboardingTelemetry(event, meta = {}) {',
      'function emitMiniAppOnboardingStatusTelemetry(status, meta = {}) {'
    );

    expect(telemetryHelper).toContain('api.post(\'/telemetry\'');
    expect(telemetryHelper).toContain('role: \'patient\'');
    expect(telemetryHelper).toContain('scope: \'onboarding\'');
    expect(telemetryHelper).toContain('reason_code: getMiniAppTelemetryReasonCode');
    expect(telemetryHelper).not.toMatch(/entryToken|raw|phone|fullName|payment|invoice|diagnosis|lab|emr/i);
  });
});
