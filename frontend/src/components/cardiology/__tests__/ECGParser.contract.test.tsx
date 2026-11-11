/**
 * ECGPARSER-FE-001 / ECGPARSER-FE-002 / ECGPARSER-FE-003 (audit 3886 round 25).
 *
 * Red-first: on pre-fix source
 *  - ECGPARSER-FE-001: parseXMLFile returned success:true for ANY
 *    well-formed XML — <unrelated/> or an empty <ClinicalDocument/> was
 *    "parsed" with every measurement null, and the viewer silently
 *    persisted a source:'device' /cardio/ecg record for it (no warning,
 *    no structured values, false-normal findings);
 *  - ECGPARSER-FE-002: analyzeECGParameters classified measurements with
 *    parseInt(); parseInt(null) === NaN failed BOTH range checks, so an
 *    absent heart rate fell into the unconditional else-branch labeled
 *    "normal HR" (same for the axis) — a clinical false reassurance — and
 *    parseInt('120bad') === 120 accepted garbage as a measurement;
 *  - ECGPARSER-FE-003: the /cardio/ecg payload mapped qrs_duration from
 *    `qrs_duration ?? qrsDuration` and qt_corrected from
 *    `qt_corrected ?? qtCorrected`, but the parser emits `qrsInterval` /
 *    `qtcInterval` — parsed QRS/QTc never reached the structured columns.
 */
import React from 'react';
import { act, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, beforeAll, beforeEach, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn(),
  delete: vi.fn(),
}));
const notifyMocks = vi.hoisted(() => ({
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    post: (...args: unknown[]) => apiMocks.post(...args),
    get: (...args: unknown[]) => apiMocks.get(...args),
    delete: (...args: unknown[]) => apiMocks.delete(...args),
  },
  apiClient: {
    post: (...args: unknown[]) => apiMocks.post(...args),
    get: (...args: unknown[]) => apiMocks.get(...args),
    delete: (...args: unknown[]) => apiMocks.delete(...args),
  },
  // stores/auth registers a session-invalidation listener at import time.
  setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../../../services/notify', () => ({
  default: notifyMocks,
}));

import ECGViewer from '../ECGViewer';
import { parseECGFile, analyzeECGParameters } from '../ECGParser';
import i18n from '../../../i18n';
import { renderWithProviders } from '../../../test/renderWithProviders';

/** Locale-agnostic expected strings (the parser resolves keys through the
 * same i18n singleton the component under test uses). */
const T = (key: string) => String(i18n.t(key));

function uploadResponse(file: File) {
  return {
    status: 201,
    data: {
      id: 601,
      original_filename: file.name,
      mime_type: file.type || 'text/xml',
      file_size: file.size,
      created_at: '2026-11-09T09:00:00Z',
    },
  };
}

/** Drop files onto the react-dropzone root element. */
function dropFiles(files: File[]) {
  const dropzone = document.querySelector('[role="presentation"]') ?? document.body.firstElementChild!;
  fireEvent.drop(dropzone, { dataTransfer: { files, types: ['Files'] } });
}

/** jsdom's File lacks Blob.text() (used by ECGParser.parseXMLFile) —
 * polyfill it via FileReader for this suite only. */
beforeAll(() => {
  if (typeof File.prototype.text !== 'function') {
    File.prototype.text = function (): Promise<string> {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(this);
      });
    };
  }
});

beforeEach(() => {
  apiMocks.post.mockReset();
  apiMocks.get.mockReset();
  apiMocks.delete.mockReset();
  Object.values(notifyMocks).forEach((m) => m.mockReset());
});

/** Render the viewer with the upload endpoint mocked; every non-upload
 * POST resolves successfully so persistence is observable. */
function renderViewer(file: File) {
  apiMocks.post.mockImplementation((url: string) =>
    url === '/files/upload' ? Promise.resolve(uploadResponse(file)) : Promise.resolve({ status: 201 }),
  );
  return renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);
}

async function dropAndViewer(file: File) {
  const utils = renderViewer(file);
  await act(async () => {
    dropFiles([file]);
  });
  return utils;
}

/** The /cardio/ecg persistence call captured from the api mock, if any. */
function ecgPersistCall(): [string, Record<string, unknown>] | undefined {
  return apiMocks.post.mock.calls.find((call) => call[0] === '/cardio/ecg') as
    | [string, Record<string, unknown>]
    | undefined;
}

describe('ECGPARSER-FE-001: well-formed XML without ECG measurements is not a parsed ECG', () => {
  it.each([
    ['<unrelated/>', 'unrelated.xml'],
    ['<?xml version="1.0"?><ClinicalDocument/>', 'empty-clinical-document.xml'],
  ])('rejects %s (%s) with an explicit unrecognized-format error', async (xml, name) => {
    const result = (await parseECGFile(new File([xml], name, { type: 'text/xml' }))) as Record<string, unknown>;
    expect(result.success).toBe(false);
    expect(result.parameters).toBeUndefined();
    expect(String(result.error)).toContain(T('cardio.cardio_parser_xml_not_ecg'));
  });

  it('a free-text <interpretation> alone is not a recognized ECG measurement', async () => {
    const xml = '<?xml version="1.0"?><report><interpretation>хорошая книга</interpretation></report>';
    const result = (await parseECGFile(new File([xml], 'review.xml', { type: 'text/xml' }))) as Record<string, unknown>;
    expect(result.success).toBe(false);
  });

  it('a minimal valid aECG document is parsed with its measurement', async () => {
    const xml = '<?xml version="1.0"?><ECG><heartRate value="75"/></ECG>';
    const result = (await parseECGFile(new File([xml], 'minimal.xml', { type: 'text/xml' }))) as Record<string, unknown>;
    expect(result.success).toBe(true);
    expect((result.parameters as Record<string, unknown>).heartRate).toBe(75);
  });

  it('a rhythm code alone is a recognized ECG document (all numerics stay null)', async () => {
    const xml = '<?xml version="1.0"?><ECG><rhythm code="sinus"/></ECG>';
    const result = (await parseECGFile(new File([xml], 'rhythm-only.xml', { type: 'text/xml' }))) as Record<string, unknown>;
    expect(result.success).toBe(true);
    const parameters = result.parameters as Record<string, unknown>;
    expect(parameters.heartRate).toBeNull();
    expect(parameters.rhythm).toBe('sinus');
  });

  it('viewer does NOT persist /cardio/ecg for an unrelated XML and warns the doctor', async () => {
    const file = new File(['<unrelated/>'], 'unrelated.xml', { type: 'text/xml' });
    await dropAndViewer(file);

    // The upload itself succeeds (the file stays as an attachment)…
    await waitFor(() => {
      expect(apiMocks.post).toHaveBeenCalledWith('/files/upload', expect.any(FormData), expect.anything());
    });
    // …but no structured ECG record is persisted…
    await act(async () => {
      await Promise.resolve();
    });
    expect(ecgPersistCall()).toBeUndefined();
    // …and the doctor sees an explicit unrecognized-format warning
    // (pre-fix: completely silent).
    expect(notifyMocks.warning).toHaveBeenCalled();
    const warningText = String(notifyMocks.warning.mock.calls[0]?.[0] ?? '');
    expect(warningText).toContain(T('cardio.cardio_parser_xml_not_ecg'));
  });
});

describe('ECGPARSER-FE-002: absent/invalid measurements are never classified as normal', () => {
  it('null heart rate and axis produce explicit not-measured findings, never normal labels', () => {
    const { findings, summary } = analyzeECGParameters({ heartRate: null, axis: null });
    const normalHr = T('cardio.cardio_parser_normal_hr');
    const normalAxis = T('cardio.cardio_parser_axis_normal');
    expect(findings).not.toContain(normalHr);
    expect(findings).not.toContain(normalAxis);
    expect(summary).not.toContain(normalHr);
    expect(summary).not.toContain(normalAxis);
    expect(findings).toContain(T('cardio.cardio_parser_hr_not_measured'));
    expect(findings).toContain(T('cardio.cardio_parser_axis_not_measured'));
  });

  it.each([
    ['malformed values', { heartRate: '120bad', axis: 'garbage' }],
    ['empty strings', { heartRate: '', axis: '' }],
    ['absent keys', {}],
  ])('%s are not verified measurements', (_label, params) => {
    const { findings, summary } = analyzeECGParameters(params);
    // '120bad' must NOT become tachycardia (parseInt('120bad') === 120)…
    expect(findings).not.toContain(T('cardio.cardio_parser_tachycardia'));
    // …and nothing may be labeled normal…
    expect(summary).not.toContain(T('cardio.cardio_parser_normal_hr'));
    expect(summary).not.toContain(T('cardio.cardio_parser_axis_normal'));
    // …the honest state is explicit not-measured.
    expect(findings).toContain(T('cardio.cardio_parser_hr_not_measured'));
    expect(findings).toContain(T('cardio.cardio_parser_axis_not_measured'));
  });

  it('valid finite numbers are still classified (HR 75 / axis 0 = normal only after validation)', () => {
    const { findings } = analyzeECGParameters({ heartRate: '75', axis: '0' });
    expect(findings).toContain(T('cardio.cardio_parser_normal_hr'));
    expect(findings).toContain(T('cardio.cardio_parser_axis_normal'));
  });

  it('valid boundaries still classify (HR 151 severe tachycardia, HR 39 severe bradycardia)', () => {
    const tachy = analyzeECGParameters({ heartRate: 151, axis: 40 });
    expect(tachy.findings).toContain(T('cardio.cardio_parser_tachycardia'));
    expect(tachy.alerts).toContain(T('cardio.cardio_parser_severe_tachycardia'));

    const brady = analyzeECGParameters({ heartRate: 39, axis: 40 });
    expect(brady.findings).toContain(T('cardio.cardio_parser_bradycardia'));
    expect(brady.alerts).toContain(T('cardio.cardio_parser_severe_bradycardia'));
  });

  it('malformed intervals are not accepted as measurements (PR "120bad" is not short PR)', () => {
    const { findings, alerts } = analyzeECGParameters({ heartRate: 75, prInterval: '120bad', axis: 40 });
    expect(findings).not.toContain(T('cardio.cardio_parser_pr_short'));
    expect(alerts).not.toContain(T('cardio.cardio_parser_wpw_possible'));
  });

  it('a device XML without HR/axis tags persists explicit not-measured findings, not normal', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <qrsInterval value="124"/>
  <rhythm code="sinus"/>
</ECG>`;
    await dropAndViewer(new File([xml], 'no-hr.xml', { type: 'application/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    expect(payload.heart_rate).toBeNull();
    const parameters = payload.parameters as Record<string, unknown>;
    const findings = parameters.findings as string[];
    expect(findings).toContain(T('cardio.cardio_parser_hr_not_measured'));
    expect(findings).toContain(T('cardio.cardio_parser_axis_not_measured'));
    expect(findings).not.toContain(T('cardio.cardio_parser_normal_hr'));
    expect(findings).not.toContain(T('cardio.cardio_parser_axis_normal'));
  });
});

describe('ECGPARSER-FE-003: parsed QRS/QTc reach the structured /cardio/ecg columns', () => {
  it('maps qrsInterval/qtcInterval into qrs_duration/qt_corrected as finite numbers', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <prInterval value="160"/>
  <qrsInterval value="124"/>
  <qtInterval value="420"/>
  <qtcInterval value="470"/>
  <rhythm code="sinus"/>
</ECG>`;
    // application/xml MIME doubles as the ECGVIEW-FE-003 round-20 control:
    // extension-driven dispatch must still reach the parser.
    await dropAndViewer(new File([xml], 'intervals.xml', { type: 'application/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    expect(payload.qrs_duration).toBe(124);
    expect(payload.qt_corrected).toBe(470);
    expect(payload.qt_interval).toBe(420);
    expect(payload.heart_rate).toBe(75);
    expect(payload.pr_interval).toBe(160);
    expect(payload.source).toBe('device');
  });

  it('does not invent QTc when the source did not measure one', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <qrsInterval value="96"/>
  <qtInterval value="400"/>
</ECG>`;
    await dropAndViewer(new File([xml], 'no-qtc.xml', { type: 'text/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    expect(payload.qrs_duration).toBe(96);
    expect(payload.qt_interval).toBe(400);
    expect(payload.qt_corrected).toBeNull();
  });

  it('prefers the QRS electrical axis over the P axis when both are present', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <pAxis value="10"/>
  <qrsAxis value="90"/>
</ECG>`;
    await dropAndViewer(new File([xml], 'two-axes.xml', { type: 'text/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    // The generic axis is the QRS electrical axis (−30…+90 scale), not the
    // P-wave axis.
    expect(payload.axis).toBe('90');
  });
});

describe('RETRO-3965-01: a P-wave axis is never relabeled as the QRS electrical axis', () => {
  // Post-merge review 3968 (origin #3965): the parser used pAxis as a
  // fallback for the generic `axis`, so a P-only document (e.g.
  // <pAxis value="-55"/> with no qrsAxis) was classified on the QRS
  // −30…+90 scale (spurious left-axis) and persisted axis="-55" into the
  // structured /cardio/ecg record instead of null.

  it('parser-level: a P-only document keeps axis null and exposes pAxis separately', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <pAxis value="-55"/>
  <rhythm code="sinus"/>
</ECG>`;
    const result = (await parseECGFile(new File([xml], 'p-only.xml', { type: 'text/xml' }))) as {
      success: boolean;
      parameters: Record<string, unknown>;
    };
    expect(result.success).toBe(true);
    expect(result.parameters.axis).toBeNull();
    expect(result.parameters.pAxis).toBe(-55);
  });

  it('parser-level: both axes present keeps them distinct (axis=QRS, pAxis=P)', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <pAxis value="10"/>
  <qrsAxis value="90"/>
</ECG>`;
    const result = (await parseECGFile(new File([xml], 'two-axes.xml', { type: 'text/xml' }))) as {
      success: boolean;
      parameters: Record<string, unknown>;
    };
    expect(result.success).toBe(true);
    expect(result.parameters.axis).toBe(90);
    expect(result.parameters.pAxis).toBe(10);
  });

  it('viewer-level: a P-only document persists axis=null, never the P value as QRS', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <pAxis value="-55"/>
  <rhythm code="sinus"/>
</ECG>`;
    await dropAndViewer(new File([xml], 'p-only.xml', { type: 'text/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    // The structured column is the QRS electrical axis: absent qrsAxis →
    // explicit null, never "-55".
    expect(payload.axis).toBeNull();
    // The P-wave axis survives only inside the raw parameters dict.
    const parameters = payload.parameters as Record<string, unknown>;
    expect(parameters.pAxis).toBe(-55);
    expect(parameters.axis).toBeNull();
  });

  it('findings: a P-only document reports axis-not-measured, never a QRS left-axis label', async () => {
    const xml = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <pAxis value="-55"/>
  <rhythm code="sinus"/>
</ECG>`;
    await dropAndViewer(new File([xml], 'p-only-findings.xml', { type: 'text/xml' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    const parameters = payload.parameters as Record<string, unknown>;
    const findings = parameters.findings as string[];
    expect(findings).toContain(T('cardio.cardio_parser_axis_not_measured'));
    expect(findings).not.toContain(T('cardio.cardio_parser_axis_left'));
    expect(findings).not.toContain(T('cardio.cardio_parser_axis_normal'));
    expect(findings).not.toContain(T('cardio.cardio_parser_axis_right'));
  });

  it('unit-level control: analyzeECGParameters still classifies a true QRS axis value', () => {
    // A genuine qrsAxis of -55 (both-tags document where qrsAxis itself is
    // negative) is still classified as left-axis — the fix removes only
    // the P→QRS relabeling, not the QRS classification itself.
    const { findings } = analyzeECGParameters({ heartRate: 75, axis: -55 });
    expect(findings).toContain(T('cardio.cardio_parser_axis_left'));
  });
});

describe('controls: previously fixed contracts stay intact', () => {
  it('C-1 control: SCP parsing still refuses to fabricate parameters', async () => {
    const scpBytes = new Uint8Array(16);
    const result = (await parseECGFile(new File([scpBytes], 'ecg.scp', { type: 'application/scp' }))) as Record<string, unknown>;
    expect(result.success).toBe(false);
    expect(result.parameters).toBeUndefined();
  });

  it('ECGVIEW-FE-003 control: an empty-MIME .xml still reaches the parser and persists', async () => {
    const xml = '<?xml version="1.0"?><ECG><heartRate value="75"/></ECG>';
    await dropAndViewer(new File([xml], 'empty-mime.xml', { type: '' }));

    await waitFor(() => {
      expect(ecgPersistCall()).toBeDefined();
    });
    const [, payload] = ecgPersistCall()!;
    // Type-agnostic on purpose: this control asserts the round-20 contract
    // (extension-driven dispatch reaches the parser and persists); the
    // strict number type of the new mapping is asserted in the FE-003
    // block above.
    expect(Number(payload.heart_rate)).toBe(75);
  });
});
