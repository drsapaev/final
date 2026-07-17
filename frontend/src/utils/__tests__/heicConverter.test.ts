// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { heic2anyMock, loggerErrorMock } = vi.hoisted(() => ({
  heic2anyMock: vi.fn(),
  loggerErrorMock: vi.fn(),
}));

vi.mock('heic2any', () => ({
  default: heic2anyMock,
}));

vi.mock('../logger', () => ({
  default: {
    error: loggerErrorMock,
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    log: vi.fn(),
  },
}));

import { convertHEICToJPEG } from '../heicConverter';

function createLinkedPort() {
  return {
    onmessage: null,
    target: null,
    postMessage(data) {
      this.target?.onmessage?.({ data });
    },
  };
}

class TestMessageChannel {
  constructor() {
    this.port1 = createLinkedPort();
    this.port2 = createLinkedPort();
    this.port1.target = this.port2;
    this.port2.target = this.port1;
  }
}

function stubServiceWorker(postMessage) {
  vi.stubGlobal('navigator', {
    serviceWorker: {
      ready: Promise.resolve({
        active: {
          postMessage,
        },
      }),
    },
  });
  vi.stubGlobal('MessageChannel', TestMessageChannel);
}

describe('heicConverter service worker fallback', () => {
  beforeEach(() => {
    heic2anyMock.mockReset();
    loggerErrorMock.mockReset();
    heic2anyMock.mockResolvedValue(new Blob(['fallback'], { type: 'image/jpeg' }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('uses the service worker conversion result when it succeeds', async () => {
    const serviceWorkerBlob = new Blob(['worker'], { type: 'image/jpeg' });
    const postMessage = vi.fn((message, [port]) => {
      expect(message.type).toBe('CONVERT_HEIC');
      port.postMessage({
        success: true,
        convertedFile: serviceWorkerBlob,
      });
    });
    stubServiceWorker(postMessage);

    const heicFile = new File(['heic'], 'skin.heic', { type: 'image/heic' });
    const convertedFile = await convertHEICToJPEG(heicFile, 0.9);

    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(heic2anyMock).not.toHaveBeenCalled();
    expect(convertedFile).toBeInstanceOf(File);
    expect(convertedFile.name).toBe('skin.jpg');
    expect(convertedFile.type).toBe('image/jpeg');
  });

  it('falls back to local heic2any when service worker conversion fails', async () => {
    const postMessage = vi.fn((message, [port]) => {
      expect(message.type).toBe('CONVERT_HEIC');
      port.postMessage({
        success: false,
        error: 'cdn blocked',
      });
    });
    stubServiceWorker(postMessage);

    const heicFile = new File(['heic'], 'skin.heic', { type: 'image/heic' });
    const convertedFile = await convertHEICToJPEG(heicFile, 0.9);

    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(loggerErrorMock).toHaveBeenCalledWith(
      'HEIC conversion error:',
      expect.objectContaining({ message: 'cdn blocked' })
    );
    expect(heic2anyMock).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });
    expect(convertedFile).toBeInstanceOf(File);
    expect(convertedFile.name).toBe('skin.jpg');
    expect(convertedFile.type).toBe('image/jpeg');
  });

  it('falls back to local heic2any when the service worker does not respond', async () => {
    vi.useFakeTimers();
    const postMessage = vi.fn((message) => {
      expect(message.type).toBe('CONVERT_HEIC');
    });
    stubServiceWorker(postMessage);

    const heicFile = new File(['heic'], 'skin.heic', { type: 'image/heic' });
    const conversionPromise = convertHEICToJPEG(heicFile, 0.9);

    await vi.advanceTimersByTimeAsync(8000);
    const convertedFile = await conversionPromise;

    expect(postMessage).toHaveBeenCalledTimes(1);
    expect(loggerErrorMock).toHaveBeenCalledWith(
      'HEIC conversion error:',
      expect.objectContaining({ message: 'Service Worker HEIC conversion timed out' })
    );
    expect(heic2anyMock).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });
    expect(convertedFile).toBeInstanceOf(File);
    expect(convertedFile.name).toBe('skin.jpg');
    expect(convertedFile.type).toBe('image/jpeg');
  });

  it('falls back to local heic2any when no active service worker registration exists', async () => {
    const getRegistration = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      serviceWorker: {
        getRegistration,
        ready: new Promise(() => {}),
      },
    });

    const heicFile = new File(['heic'], 'skin.heic', { type: 'image/heic' });
    const convertedFile = await convertHEICToJPEG(heicFile, 0.9);

    expect(getRegistration).toHaveBeenCalledTimes(1);
    expect(loggerErrorMock).toHaveBeenCalledWith(
      'HEIC conversion error:',
      expect.objectContaining({ message: 'Service Worker is not active' })
    );
    expect(heic2anyMock).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });
    expect(convertedFile).toBeInstanceOf(File);
    expect(convertedFile.name).toBe('skin.jpg');
    expect(convertedFile.type).toBe('image/jpeg');
  });

  it('falls back to local heic2any when service worker readiness never resolves', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('navigator', {
      serviceWorker: {
        ready: new Promise(() => {}),
      },
    });
    vi.stubGlobal('MessageChannel', TestMessageChannel);

    const heicFile = new File(['heic'], 'skin.heic', { type: 'image/heic' });
    const conversionPromise = convertHEICToJPEG(heicFile, 0.9);

    await vi.advanceTimersByTimeAsync(8000);
    const convertedFile = await conversionPromise;

    expect(loggerErrorMock).toHaveBeenCalledWith(
      'HEIC conversion error:',
      expect.objectContaining({ message: 'Service Worker readiness timed out' })
    );
    expect(heic2anyMock).toHaveBeenCalledWith({
      blob: heicFile,
      toType: 'image/jpeg',
      quality: 0.9,
    });
    expect(convertedFile).toBeInstanceOf(File);
    expect(convertedFile.name).toBe('skin.jpg');
    expect(convertedFile.type).toBe('image/jpeg');
  });
});
