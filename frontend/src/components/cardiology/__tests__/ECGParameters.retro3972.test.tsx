/**
 * RETRO-3972-01 / RETRO-3972-02 (post-merge review 4000 — P3 residuals
 * inside PR #3972's claim perimeter).
 *
 * Red-first: on pre-fix source
 *  - RETRO-3972-01: exportECGParameters exported the QRS axis as the
 *    P-wave axis whenever `pAxis` was absent (null/undefined) or legally
 *    measured as exactly 0 — `p: parameters.pAxis || parameters.axis` —
 *    and read a `qrsAxis` key the parser never emits on the qrs line;
 *  - RETRO-3972-02: a measured 0° QRS axis is falsy — `{axis && (...)}` hid
 *    the «Электрическая ось сердца» card and leaked a bare "0" text node
 *    into the metric grid instead of rendering «0°».
 *
 * Post-fix contract:
 *  - the exported P axis is the P axis (null stays null, 0° stays 0°),
 *    never relabeled to the QRS scale; the QRS export preserves 0° too;
 *  - a measured 0° axis renders the heart-axis card with «0°» and leaves
 *    no stray "0" text node; an unmeasured axis (null/undefined) still
 *    renders no card at all.
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
  setSessionInvalidationListener: vi.fn(),
}));

vi.mock('../../../services/notify', () => ({
  default: notifyMocks,
}));

import ECGViewer from '../ECGViewer';
import { exportECGParameters } from '../ECGParser';
import { renderWithProviders } from '../../../test/renderWithProviders';

type ExportedAxes = { axis: { p: unknown; qrs: unknown; t: unknown } };

/** Minimal aECG XML whose QRS axis is the legal measured 0°. */
const ZERO_AXIS_ECG_XML = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <qrsAxis value="0"/>
  <rhythm code="sinus"/>
  <interpretation>Норма</interpretation>
</ECG>`;

function makeXmlFile(name: string): File {
  return new File([ZERO_AXIS_ECG_XML], name, { type: 'text/xml' });
}

function dropFiles(files: File[]) {
  const dropzone = document.querySelector('[role="presentation"]') ?? document.body.firstElementChild!;
  fireEvent.drop(dropzone, { dataTransfer: { files, types: ['Files'] } });
}

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

describe('RETRO-3972-01: exportECGParameters keeps the two axes distinct', () => {
  it('an absent or null P axis exports null — never the QRS axis', () => {
    const nullCase = exportECGParameters({ axis: 90, pAxis: null }) as ExportedAxes;
    expect(nullCase.axis.p).toBeNull();

    const absentCase = exportECGParameters({ axis: 90 }) as ExportedAxes;
    expect(absentCase.axis.p).toBeNull();
  });

  it('a legally measured 0° P axis exports 0 (||-coercion would relabel it)', () => {
    const zeroCase = exportECGParameters({ axis: 90, pAxis: 0 }) as ExportedAxes;
    expect(zeroCase.axis.p).toBe(0);
  });

  it('the QRS export preserves a measured 0° and never reads a fabricated key', () => {
    const zeroGeneric = exportECGParameters({ axis: 0 }) as ExportedAxes;
    expect(zeroGeneric.axis.qrs).toBe(0);

    const explicitKey = exportECGParameters({ axis: -30, qrsAxis: 0 }) as ExportedAxes;
    expect(explicitKey.axis.qrs).toBe(0);

    const normalCase = exportECGParameters({ axis: 45 }) as ExportedAxes;
    expect(normalCase.axis.qrs).toBe(45);
  });
});

describe('RETRO-3972-02: a measured 0° heart axis renders its card honestly', () => {
  it('renders «Электрическая ось сердца: 0°» and leaks no bare "0" node', async () => {
    const file = makeXmlFile('ecg-zero-axis.xml');
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload'
        ? Promise.resolve({
            status: 201,
            data: {
              id: 601,
              original_filename: file.name,
              mime_type: 'text/xml',
              file_size: file.size,
              created_at: '2026-11-12T08:00:00Z',
            },
          })
        : Promise.resolve({ status: 201 }),
    );
    // Preview fetch fails — the params grid renders regardless of the
    // preview pane (viewerError path), which is exactly the layout under test.
    apiMocks.get.mockRejectedValue(new Error('preview unavailable'));

    renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });

    await waitFor(() => {
      expect(screen.getByText('ecg-zero-axis.xml')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Просмотр' }));

    // The heart-axis card renders with the measured 0°…
    await waitFor(() => {
      expect(screen.getByText('Электрическая ось сердца')).toBeInTheDocument();
    });
    expect(screen.getByText('0°')).toBeInTheDocument();

    // …and no stray bare "0" text node leaked from the falsy-zero guard.
    expect(screen.queryByText(/^0$/)).toBeNull();
  });

  it('CONTROL: an unmeasured axis still renders no heart-axis card', async () => {
    const NO_AXIS_ECG_XML = `<?xml version="1.0"?>
<ECG>
  <heartRate value="75"/>
  <rhythm code="sinus"/>
</ECG>`;
    const file = new File([NO_AXIS_ECG_XML], 'ecg-no-axis.xml', { type: 'text/xml' });
    apiMocks.post.mockImplementation((url: string) =>
      url === '/files/upload'
        ? Promise.resolve({
            status: 201,
            data: {
              id: 602,
              original_filename: file.name,
              mime_type: 'text/xml',
              file_size: file.size,
              created_at: '2026-11-12T08:00:00Z',
            },
          })
        : Promise.resolve({ status: 201 }),
    );
    apiMocks.get.mockRejectedValue(new Error('preview unavailable'));

    renderWithProviders(<ECGViewer patientId={7} visitId={11} onDataUpdate={vi.fn()} />);

    await act(async () => {
      dropFiles([file]);
    });

    await waitFor(() => {
      expect(screen.getByText('ecg-no-axis.xml')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Просмотр' }));

    await waitFor(() => {
      expect(screen.getByText('Частота сердечных сокращений')).toBeInTheDocument();
    });
    expect(screen.queryByText('Электрическая ось сердца')).toBeNull();
    expect(screen.queryByText(/^0$/)).toBeNull();
  });
});
