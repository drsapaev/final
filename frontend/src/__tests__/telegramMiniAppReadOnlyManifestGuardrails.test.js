import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const appSource = fs.readFileSync(path.resolve(process.cwd(), 'src/App.jsx'), 'utf8');

const READ_ONLY_MANIFESTS = [
  {
    section: 'forms',
    setter: 'setFormsManifest',
    endpoint: '/telegram/mini-app/forms/manifest',
    fallbackReason: 'forms_manifest_failed',
    panelStart: '{canShowFormsManifest && (',
    panelEnd: '{canPreviewAppointments && (',
    expectedLabels: [
      'capture on',
      'capture off',
      'submit on',
      'submit off',
      'medical data',
      'no medical data',
      'passport data',
      'no passport data',
    ],
  },
  {
    section: 'cabinet',
    setter: 'setCabinetManifest',
    endpoint: '/telegram/mini-app/cabinet/manifest',
    fallbackReason: 'cabinet_manifest_failed',
    panelStart: '{canShowCabinetManifest && (',
    panelEnd: '{canShowPaymentsManifest && (',
    expectedLabels: [
      'No records or edits',
      'read on',
      'read off',
      'write on',
      'write off',
      'medical data',
      'no medical data',
      'passport data',
      'no passport data',
      'billing records',
      'no billing records',
    ],
  },
  {
    section: 'payments',
    setter: 'setPaymentsManifest',
    endpoint: '/telegram/mini-app/payments/manifest',
    fallbackReason: 'payments_manifest_failed',
    panelStart: '{canShowPaymentsManifest && (',
    panelEnd: '{canShowResultsManifest && (',
    expectedLabels: [
      'No amounts or charges',
      'read on',
      'read off',
      'capture on',
      'capture off',
      'provider redirect on',
      'provider redirect off',
      'payment on',
      'payment off',
      'amounts present',
      'no amounts',
      'payment records',
      'no payment records',
      'provider payloads',
      'no provider payloads',
    ],
  },
  {
    section: 'results',
    setter: 'setResultsManifest',
    endpoint: '/telegram/mini-app/results/manifest',
    fallbackReason: 'results_manifest_failed',
    panelStart: '{canShowResultsManifest && (',
    panelEnd: '{canShowFormsManifest && (',
    expectedLabels: [
      'No reports or files',
      'view on',
      'view off',
      'download on',
      'download off',
      'PDFs present',
      'no PDFs',
      'medical results',
      'no medical results',
      'lab values',
      'no lab values',
      'report records',
      'no report records',
      'file URLs',
      'no file URLs',
      'diagnoses',
      'no diagnoses',
    ],
  },
];

const MUTATING_MARKERS = [
  '<input',
  '<textarea',
  '<select',
  '<button',
  'onSubmit=',
  'onClick=',
  'api.post(',
  'handleAppointmentCreate',
  'handleAppointmentPreviewSubmit',
  'payment_provider',
  'providerPayload',
  'provider_payload:',
  'invoice',
  'transaction',
  'webhook',
  'href=',
  'download=',
  'target=',
];

function sourceBetween(source, start, end) {
  const startIndex = source.indexOf(start);
  expect(startIndex).toBeGreaterThanOrEqual(0);

  const endIndex = source.indexOf(end, startIndex + start.length);
  expect(endIndex).toBeGreaterThan(startIndex);

  return source.slice(startIndex, endIndex);
}

describe('Telegram Mini App read-only manifest guardrails', () => {
  it('requests protected section manifests only after the trusted aggregate manifest is ready', () => {
    READ_ONLY_MANIFESTS.forEach(({ section, setter, endpoint, fallbackReason }) => {
      const effectSource = sourceBetween(
        appSource,
        `if (state.status !== 'ready' || selectedSection !== '${section}') {`,
        '}, [selectedSection, state.status]);'
      );

      expect(effectSource).toContain(`${setter}({`);
      expect(effectSource).toContain("status: 'idle'");
      expect(effectSource).toContain('payload: null');
      expect(effectSource).toContain('error: null');
      expect(effectSource).toContain('const initData = getTelegramMiniAppInitData();');
      expect(effectSource).toContain(
        `api.post('${endpoint}', { initData }, MINI_APP_HANDLED_ERROR_REQUEST_CONFIG)`
      );
      expect(effectSource).toContain(`'${fallbackReason}'`);
      expect(effectSource).not.toContain('/telegram/mini-app/appointments');
    });
  });

  it('keeps non-appointment sections behind manifest endpoint capability gates', () => {
    const manifestCapabilityGates = sourceBetween(
      appSource,
      'const canShowFormsManifest = Boolean(',
      'const statusBadge = getMiniAppStatusBadge(state.status);'
    );

    READ_ONLY_MANIFESTS.forEach(({ section }) => {
      expect(manifestCapabilityGates).toContain(`selectedSection === '${section}'`);
    });

    expect(manifestCapabilityGates.match(/selectedCapability\?\.manifest_endpoint/g)).toHaveLength(4);
    expect(manifestCapabilityGates).not.toContain('create_enabled');
    expect(manifestCapabilityGates).not.toContain('preview_enabled');
    expect(manifestCapabilityGates).not.toContain('payment_capture_enabled');
  });

  it('renders section manifests as status-only panels without mutating controls', () => {
    READ_ONLY_MANIFESTS.forEach(({ panelStart, panelEnd, expectedLabels }) => {
      const panelSource = sourceBetween(appSource, panelStart, panelEnd);

      expectedLabels.forEach((label) => {
        expect(panelSource).toContain(label);
      });

      MUTATING_MARKERS.forEach((marker) => {
        expect(panelSource).not.toContain(marker);
      });

      expect(panelSource).not.toMatch(
        /(?:payload|section|form)\?\.(?:records|record|amount|amounts|invoice|transaction|provider_payload|file_url|file_urls|pdf|pdfs|diagnosis|diagnoses|medical_results|lab_values|patient_id|passport_number)/i
      );
    });
  });

  it('keeps sensitive capability flags surfaced only as warning or safe badges', () => {
    const safetyFlags = sourceBetween(
      appSource,
      'const MINI_APP_CAPABILITY_SAFETY_FLAGS = [',
      'const MINI_APP_EXPIRED_ENTRY_TOKEN_REASONS = new Set'
    );
    const safetyBadgeBuilder = sourceBetween(
      appSource,
      'function getMiniAppCapabilitySafetyBadges(capability) {',
      'function notifyTelegramMiniAppReady() {'
    );

    [
      'contains_medical_data',
      'contains_payment_provider_data',
      'contains_passport_data',
      'contains_billing_records',
      'contains_amounts',
      'contains_payment_records',
      'contains_provider_payloads',
      'contains_medical_results',
      'contains_lab_values',
      'contains_report_records',
      'contains_file_urls',
      'contains_pdfs',
      'contains_diagnoses',
    ].forEach((flag) => {
      expect(safetyFlags).toContain(flag);
    });

    expect(safetyBadgeBuilder).toContain("variant: unsafe ? 'warning' : 'success'");
    expect(safetyBadgeBuilder).not.toContain('api.post');
    expect(safetyBadgeBuilder).not.toContain('onClick');
  });
});
