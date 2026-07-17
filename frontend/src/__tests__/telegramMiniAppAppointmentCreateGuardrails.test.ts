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

describe('Telegram Mini App appointment create guardrails', () => {
  it('keeps the create action behind a successful preview and create capability gate', () => {
    const createActionMarkup = sourceBetween(
      appSource,
      '{appointmentPreview.status === \'ready\' && previewAppointment && (',
      '{selectedSection === \'forms\' && formsPreview.status === \'loading\' && ('
    );

    expect(createActionMarkup).toContain('{canCreateAppointments && (');
    expect(createActionMarkup).toContain('onClick={handleAppointmentCreateSubmit}');
    expect(createActionMarkup).toContain(
      'disabled={appointmentCreate.status === \'loading\' || appointmentCreate.status === \'ready\'}'
    );
    expect(createActionMarkup).not.toContain('payment provider');
    expect(createActionMarkup).not.toContain('provider payload');
  });

  it('posts creates through the existing appointment endpoint with the preview request body shape', () => {
    const createHandler = sourceBetween(
      appSource,
      'const handleAppointmentCreateSubmit = () => {',
      'const handlePatientFormFieldChange = (formId, field) => (event) => {'
    );

    expect(createHandler).toContain('getTelegramMiniAppAuthPayload(location.search, \'appointments\')');
    expect(createHandler).toContain(
      'const requestBody = buildMiniAppAppointmentRequestBody(authPayload, appointmentPreviewForm);'
    );
    expect(createHandler).toContain(
      'api.post(\'/telegram/mini-app/appointments\', requestBody, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)'
    );
    expect(createHandler).not.toContain('/telegram/mini-app/appointments/preview');
    expect(createHandler).not.toMatch(/payment_provider|provider_payload|providerPayload|transaction|webhook|invoice|amount/i);
  });

  it('clears stale create state when the appointment draft or preview submission changes', () => {
    const fieldChangeHandler = sourceBetween(
      appSource,
      'const handleAppointmentPreviewFieldChange = (field) => (event) => {',
      'const handleAppointmentPreviewSubmit = (event) => {'
    );
    const previewSubmitHandler = sourceBetween(
      appSource,
      'const handleAppointmentPreviewSubmit = (event) => {',
      'const handleAppointmentCreateSubmit = () => {'
    );

    expect(fieldChangeHandler).toContain('setAppointmentCreate({');
    expect(fieldChangeHandler).toContain('status: \'idle\'');
    expect(previewSubmitHandler).toContain('setAppointmentCreate({');
    expect(previewSubmitHandler).toContain('status: \'idle\'');
  });
});
