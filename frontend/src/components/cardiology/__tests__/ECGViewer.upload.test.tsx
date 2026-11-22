/**
 * ECGVIEW-FE-001 / ECGVIEW-FE-002 / ECGVIEW-FE-003 (audit 3886 round 20).
 *
 * Red-first: on pre-fix source
 *  - ECGVIEW-FE-001: `formData.append('file', String(file))` uploaded the
 *    literal text "[object File]" instead of a multipart File part, so the
 *    backend's `UploadFile` contract could never be satisfied;
 *  - ECGVIEW-FE-002: the viewer kept the previous patient's local file
 *    list/preview/analysis across prop changes and let their in-flight
 *    async callbacks commit into the new context;
 *  - ECGVIEW-FE-003: parsing was gated on the single `text/xml` MIME, so a
 *    `.xml` tagged `application/xml` (or with an empty MIME) was uploaded
 *    but never parsed.
 */
import React from 'react';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
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
import { renderWithProviders } from '../../../test/renderWithProviders';

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function uploadResponse(file: File) {
  return {
    status: 201,
    data: {
      id: 501,
      original_filename: file.name,
      mime_type: file.type || 'text/xml',
      file_size: file.size,
      created_at: '2026-11-08T08:00:00Z',
    },
  };
}

/** Minimal valid HL7 aECG XML so the real parser produces parameters. */
const VALID_ECG_XML = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <prInterval value="160"/>
  <qrsInterval value="90"/>
  <qtInterval value="400"/>
  <qtcInterval value="440"/>
  <pAxis value="40"/>
  <rhythm code="sinus"/>
  <interpretation>Норма</interpretation>
</ECG>`;

function makeXmlFile(name: string, mime: string): File {
  return new File([VALID_ECG_XML], name, { type: mime });
}

/** Drop files onto the react-dropzone root element. */
function dropFiles(files: File[]) {
  const dropzone = document.querySelector('[role="presentation"]') ?? document.body.firstElementChild!;
  // react-dropzone's isEvtWithFiles reads dataTransfer.types via
  // Array.prototype.some, so a minimal jsdom DataTransfer stand-in must
  // include it alongside the files list.
  fireEvent.drop(dropzone, { dataTransfer: { files, types: ['Files'] } });
}

/** jsdom's File lacks Blob.text() (used by ECGParser.parseXMLFile and the
 * content assertions) — polyfill it via FileReader for this suite only. */
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

describe('ECGVIEW-FE-001: the upload must send a real multipart File part', () => {
  it('appends the dropped File itself (not its stringification) with its filename', async () => {
    apiMocks.post.mockResolvedValueOnce(uploadResponse(makeXmlFile('ecg.xml', 'text/xml')));
    renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    const file = makeXmlFile('ecg.xml', 'text/xml');
    await act(async () => {
      dropFiles([file]);
    });

    await waitFor(() => {
      expect(apiMocks.post).toHaveBeenCalled();
    });

    const [url, formData] = apiMocks.post.mock.calls[0];
    expect(url).toBe('/files/upload');
    expect(formData).toBeInstanceOf(FormData);

    const sentPart = formData.get('file');
    // The part must be the binary File, never the string "[object File]".
    expect(sentPart).toBeInstanceOf(File);
    expect((sentPart as File).name).toBe('ecg.xml');
    expect((sentPart as File).size).toBe(file.size);
    expect((sentPart as File).text ? await (sentPart as File).text() : '').toContain('heartRate');
    expect(formData.get('patient_id')).toBe('7');
    expect(formData.get('visit_id')).toBe('11');
  });
});

describe('ECGVIEW-FE-003: parsing dispatches by extension, not one MIME subtype', () => {
  it.each([
    ['application/xml', 'ecg-app.xml'],
    ['', 'ecg-empty-mime.xml'],
    ['text/xml', 'ecg-text.xml'],
  ])('parses a .xml file reported as MIME %j', async (mime, name) => {
    const file = makeXmlFile(name, mime);
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload' ? Promise.resolve(uploadResponse(file)) : Promise.resolve({ status: 201 }),
    );
    renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });

    // The parsed parameters must be persisted to /cardio/ecg (the parser
    // gate is the code path under test: pre-fix, application/xml and empty
    // MIME uploads never reached the parser).
    await waitFor(() => {
      const ecgCall = apiMocks.post.mock.calls.find((call) => call[0] === '/cardio/ecg');
      expect(ecgCall).toBeDefined();
    });
    const [, payload] = apiMocks.post.mock.calls.find((call) => call[0] === '/cardio/ecg')!;
    // The XML parser returns attribute values as strings; the backend
    // pydantic DTO coerces them to floats.
    expect(String(payload.heart_rate)).toBe('75');
    expect(payload.source).toBe('device');
  });

  it('does not attempt to parse a non-ECG extension (pdf)', async () => {
    const file = new File(['%PDF-1.4 fake'], 'report.pdf', { type: 'application/pdf' });
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload' ? Promise.resolve(uploadResponse(file)) : Promise.resolve({ status: 201 }),
    );
    renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post.mock.calls.find((call) => call[0] === '/cardio/ecg')).toBeUndefined();
  });
});

describe('ECGVIEW-FE-002: local state belongs to one patient context', () => {
  it('clears the previous patient file list when the owner context changes', async () => {
    const file = makeXmlFile('ecg.xml', 'text/xml');
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload' ? Promise.resolve(uploadResponse(file)) : Promise.resolve({ status: 201 }),
    );

    const { rerender } = renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });
    // File is listed for patient A.
    await waitFor(() => {
      expect(screen.getByText('ecg.xml')).toBeInTheDocument();
    });

    // Same mounted viewer, new patient context.
    rerender(<ECGViewer patientId={8} visitId={12} onDataUpdate={vi.fn()} />);

    // A's file must no longer be visible under B's context.
    await waitFor(() => {
      expect(screen.queryByText('ecg.xml')).toBeNull();
    });
  });

  it('drops an in-flight upload response that resolves after the context changed', async () => {
    const file = makeXmlFile('late-a.xml', 'text/xml');
    const gate = deferred<ReturnType<typeof uploadResponse>>();
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload' ? gate.promise : Promise.resolve({ status: 201 }),
    );

    const { rerender } = renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });

    // Switch to patient B while A's upload is still in flight.
    rerender(<ECGViewer patientId={8} visitId={12} onDataUpdate={vi.fn()} />);

    await act(async () => {
      gate.resolve(uploadResponse(file));
      await Promise.resolve();
    });
    await act(async () => {
      await Promise.resolve();
    });

    // A's late response must not list A's file under B's context.
    expect(screen.queryByText('late-a.xml')).toBeNull();
  });
});
