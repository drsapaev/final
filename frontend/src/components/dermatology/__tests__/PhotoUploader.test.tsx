// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/* eslint-disable react/display-name, react/prop-types */
import '@testing-library/jest-dom';
import { fireEvent, render, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { apiPostMock, convertHEICToJPEGMock, isHEICFileMock, loggerErrorMock } = vi.hoisted(() => ({
  apiPostMock: vi.fn(),
  convertHEICToJPEGMock: vi.fn(),
  isHEICFileMock: vi.fn(),
  loggerErrorMock: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  api: {
    post: apiPostMock,
    delete: vi.fn(),
  },
}));

vi.mock('../../../utils/heicConverter', () => ({
  convertHEICToJPEG: convertHEICToJPEGMock,
  isHEICFile: isHEICFileMock,
}));

vi.mock('../../../utils/logger', () => ({
  default: {
    error: loggerErrorMock,
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

vi.mock('../../ui/macos', async () => {
  const React = await import('react');

  const passthrough = (tag) => ({ children, color, gutterBottom, severity, variant, ...props }) => (
    React.createElement(tag, props, children)
  );
  const Button = ({ children, fullWidth, size, variant, ...props }) => (
    React.createElement('button', props, children)
  );
  const Input = ({ label, ...props }) => (
    React.createElement('input', { 'aria-label': label, ...props })
  );
  const Select = ({ children, label, ...props }) => (
    React.createElement('select', { 'aria-label': label, ...props }, children)
  );
  const Dialog = ({ children, open }) => (open ? React.createElement('div', {}, children) : null);

  return {
    Alert: passthrough('div'),
    Box: passthrough('div'),
    Button,
    Card: passthrough('section'),
    CardContent: passthrough('div'),
    Dialog,
    DialogActions: passthrough('div'),
    DialogContent: passthrough('div'),
    DialogTitle: passthrough('h2'),
    Input,
    Option: passthrough('option'),
    Progress: passthrough('progress'),
    Select,
    Typography: passthrough('span'),
  };
});

import PhotoUploader from '../PhotoUploader';

class TestFileReader {
  readAsDataURL(file) {
    setTimeout(() => {
      this.onload?.({
        target: {
          result: `data:${file.type};base64,test-preview`,
        },
      });
    }, 0);
  }
}

function renderUploader(props = {}) {
  return render(
    <PhotoUploader patientId="patient-7" visitId="visit-42" onDataUpdate={vi.fn()} {...props} />
  );
}

function getBeforeUploadInput(container) {
  const inputs = container.querySelectorAll('input[type="file"]');
  expect(inputs).toHaveLength(2);
  return inputs[0];
}

describe('PhotoUploader HEIC upload boundary', () => {
  beforeEach(() => {
    vi.stubGlobal('FileReader', TestFileReader);
    apiPostMock.mockReset();
    convertHEICToJPEGMock.mockReset();
    isHEICFileMock.mockReset();
    loggerErrorMock.mockReset();

    apiPostMock.mockResolvedValue({
      data: {
        id: 'photo-1',
        url: '/uploads/photo-1.jpg',
      },
    });
  });

  it('uploads non-HEIC photos without invoking the HEIC converter', async () => {
    isHEICFileMock.mockReturnValue(false);
    const onDataUpdate = vi.fn();
    const { container } = renderUploader({ onDataUpdate });
    const jpgFile = new File(['photo'], 'lesion.jpg', { type: 'image/jpeg' });

    fireEvent.change(getBeforeUploadInput(container), {
      target: { files: [jpgFile] },
    });

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(1);
    });

    expect(convertHEICToJPEGMock).not.toHaveBeenCalled();

    const [url, formData, config] = apiPostMock.mock.calls[0];
    expect(url).toBe('/files/upload');
    expect(formData.get('file')).toBe(jpgFile);
    expect(formData.get('file_type')).toBe('image');
    expect(formData.get('title')).toBe('lesion.jpg');
    expect(formData.get('tags')).toBe('dermatology,photo,before');
    expect(formData.get('patient_id')).toBe('patient-7');
    expect(formData.get('visit_id')).toBe('visit-42');
    expect(config.headers).toEqual({ 'Content-Type': 'multipart/form-data' });
    expect(onDataUpdate).toHaveBeenCalledTimes(1);
  });

  it('uploads converted JPEG output for HEIC photos', async () => {
    isHEICFileMock.mockReturnValue(true);
    const convertedFile = new File(['converted'], 'lesion.jpg', { type: 'image/jpeg' });
    convertHEICToJPEGMock.mockResolvedValue(convertedFile);

    const { container } = renderUploader();
    const heicFile = new File(['photo'], 'lesion.heic', { type: 'image/heic' });

    fireEvent.change(getBeforeUploadInput(container), {
      target: { files: [heicFile] },
    });

    await waitFor(() => {
      expect(apiPostMock).toHaveBeenCalledTimes(1);
    });

    expect(convertHEICToJPEGMock).toHaveBeenCalledWith(heicFile, 0.9);

    const [, formData] = apiPostMock.mock.calls[0];
    expect(formData.get('file')).toBe(convertedFile);
    expect(formData.get('file_type')).toBe('image');
    expect(formData.get('tags')).toBe('dermatology,photo,before');
  });
});
