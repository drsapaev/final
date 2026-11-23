/**
 * CARDHIST-FE-001 (audit 3886, ledger group "cardiology history tab",
 * round 28) — fail-first runtime regressions for the honest attachment
 * preview transport (utils/patientFilePreview).
 *
 * Pre-fix behavior (inline in CardiologistPanelUnified.previewPatientFile):
 * the panel awaited the full `/files/{id}/preview` response, created a
 * blob: URL and called `window.open(url, '_blank', 'noopener,noreferrer')`.
 * Per MDN, the `noopener` feature makes window.open return `null` ON
 * SUCCESS, so the immediately following `if (!previewWindow) throw`
 * reported a false "preview blocked" error for every successfully opened
 * clinical attachment; and because the popup attempt happened after an
 * asynchronous fetch, browsers could legitimately block it as a
 * non-gesture popup.
 *
 * Contract under test (the finding's repair direction):
 *  1. the browsing context is reserved synchronously inside the click
 *     gesture, before any await;
 *  2. a null reservation is an honest popup-block signal (reported
 *     without any fetch);
 *  3. opener isolation is preserved (opener severed before navigation) —
 *     the fix must NOT switch to opener-enabled popups;
 *  4. failures after reservation close the reserved context and surface
 *     an honest error;
 *  5. the blob URL revocation budget is unchanged (60 s timer).
 */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { openPatientFilePreview } from '../patientFilePreview';

const MESSAGES = {
  previewUnavailable: 'Предпросмотр недоступен',
  previewBlocked: 'Открытие предпросмотра заблокировано',
  openFailed: 'Не удалось открыть файл',
};

interface FakePreviewWindow {
  opener: unknown;
  location: { href: string };
  close: ReturnType<typeof vi.fn>;
}

function makeFakeWindow(): FakePreviewWindow {
  return {
    opener: { marker: 'parent-window' },
    location: { href: 'about:blank' },
    close: vi.fn(),
  };
}

let notifyError: Mock;
let fetchMock: Mock;
let createObjectURL: Mock;
let revokeObjectURL: Mock;
let windowOpenSpy: ReturnType<typeof vi.spyOn>;

const REQUEST = {
  apiBase: 'https://api.example/api/v1',
  fileId: 42,
  getAccessToken: () => 'token-1',
  onNotifyError: (message: string) => notifyError(message),
  messages: MESSAGES,
};

beforeEach(() => {
  vi.useRealTimers();
  notifyError = vi.fn();
  fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  createObjectURL = vi.fn(() => 'blob:preview-1');
  revokeObjectURL = vi.fn();
  window.URL.createObjectURL = createObjectURL as unknown as typeof URL.createObjectURL;
  window.URL.revokeObjectURL = revokeObjectURL as unknown as typeof URL.revokeObjectURL;
});

afterEach(() => {
  // custom/no-fake-timers-without-cleanup: fake timers must never leak
  // into other test files in singleFork mode.
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('CARDHIST-FE-001: successful preview', () => {
  it('navigates the reserved window and reports NO false failure (noopener null-return regression)', async () => {
    const fakeWindow = makeFakeWindow();
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    fetchMock.mockResolvedValue({ ok: true, blob: async () => ({ size: 2048 }) } as unknown as Response);

    await openPatientFilePreview(REQUEST);

    // THE core regression: a successful noopener-style open must not be
    // reported as blocked.
    expect(notifyError).not.toHaveBeenCalled();
    expect(fakeWindow.close).not.toHaveBeenCalled();

    // Authorized transport to the configured API origin.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('https://api.example/api/v1/files/42/preview', {
      headers: { Authorization: 'Bearer token-1' },
    });

    // Opener isolation preserved; the reserved context got the blob.
    expect(fakeWindow.opener).toBeNull();
    expect(fakeWindow.location.href).toBe('blob:preview-1');
  });

  it('reserves the browsing context before the first await (user-gesture popup)', () => {
    const fakeWindow = makeFakeWindow();
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    // The fetch never resolves: the reservation must still have happened.
    fetchMock.mockReturnValue(new Promise(() => { /* pending */ }) as Promise<Response>);

    void openPatientFilePreview(REQUEST);

    expect(windowOpenSpy).toHaveBeenCalledTimes(1);
    expect(windowOpenSpy).toHaveBeenCalledWith('', '_blank');
  });

  it('keeps the 60-second blob URL revocation budget (lifecycle unchanged)', async () => {
    vi.useFakeTimers();
    const fakeWindow = makeFakeWindow();
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    fetchMock.mockResolvedValue({ ok: true, blob: async () => ({ size: 8 }) } as unknown as Response);

    await openPatientFilePreview(REQUEST);
    expect(revokeObjectURL).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:preview-1');
  });
});

describe('CARDHIST-FE-001: honest failures', () => {
  it('reports the blocked message without fetching when the reservation itself is refused', async () => {
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(null);

    await openPatientFilePreview(REQUEST);

    expect(notifyError).toHaveBeenCalledTimes(1);
    expect(notifyError).toHaveBeenCalledWith(MESSAGES.previewBlocked);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  it('closes the reserved window and surfaces the error when the preview HTTP response fails', async () => {
    const fakeWindow = makeFakeWindow();
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    fetchMock.mockResolvedValue({ ok: false } as unknown as Response);

    await openPatientFilePreview(REQUEST);

    expect(fakeWindow.close).toHaveBeenCalledTimes(1);
    expect(notifyError).toHaveBeenCalledTimes(1);
    expect(notifyError).toHaveBeenCalledWith(MESSAGES.previewUnavailable);
    expect(fakeWindow.location.href).toBe('about:blank');
  });

  it('closes the reserved window and surfaces the error on a network rejection', async () => {
    const fakeWindow = makeFakeWindow();
    windowOpenSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    fetchMock.mockRejectedValue(new Error('network down'));

    await openPatientFilePreview(REQUEST);

    expect(fakeWindow.close).toHaveBeenCalledTimes(1);
    expect(notifyError).toHaveBeenCalledTimes(1);
    expect(notifyError).toHaveBeenCalledWith('network down');
  });
});
