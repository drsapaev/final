/**
 * CARDHIST-FE-001 (audit 3886, ledger group "cardiology history tab") —
 * honest attachment preview transport.
 *
 * Pre-fix behavior (inline in CardiologistPanelUnified.previewPatientFile):
 * the panel awaited the full `/files/{id}/preview` response, created a
 * blob: URL and called `window.open(url, '_blank', 'noopener,noreferrer')`.
 * Per MDN (Window.open, `noopener` option), that call returns `null` ON
 * SUCCESS, so the immediately following `if (!previewWindow) throw`
 * reported a false "preview blocked" error for every successfully opened
 * clinical attachment; and because the popup attempt happened after an
 * asynchronous fetch, browsers could legitimately block it as a
 * non-gesture popup (transient user activation lost).
 *
 * Contract implemented here (the finding's repair direction):
 *  1. Reserve a controlled browsing context SYNCHRONOUSLY inside the
 *     click gesture — `window.open('', '_blank')` before any await.
 *  2. A null reservation IS an honest popup-block signal (no `noopener`
 *     feature is passed, so null genuinely means blocked) and is
 *     reported without any fetch.
 *  3. Preserve opener isolation: sever `opener` on the reserved context
 *     before navigating it (the manual equivalent of `noopener`) — never
 *     switch to opener-enabled popups just to make a return-value check
 *     pass.
 *  4. On any failure after reservation, close the reserved context —
 *     never leave a blank tab behind and never report success for a
 *     failed preview.
 *  5. Blob URL lifecycle: revoked on the same bounded 60 s budget as
 *     before (unchanged scope; a dedicated lifecycle pass is out of
 *     scope for this finding).
 */

export interface PatientFilePreviewMessages {
  /** Shown when the backend refuses/fails to return the preview bytes. */
  previewUnavailable: string;
  /** Shown when the browser genuinely refuses the popup reservation. */
  previewBlocked: string;
  /** Fallback shown when opening the file fails for an unexpected reason. */
  openFailed: string;
}

export interface PatientFilePreviewRequest {
  /** Configured API origin + version prefix (e.g. `https://api.example/api/v1`). */
  apiBase: string;
  fileId: string | number;
  getAccessToken: () => string | null | undefined;
  onNotifyError: (message: string) => void;
  messages: PatientFilePreviewMessages;
}

export async function openPatientFilePreview(request: PatientFilePreviewRequest): Promise<void> {
  const { apiBase, fileId, getAccessToken, onNotifyError, messages } = request;

  // (1) Synchronous reservation inside the user gesture — must happen
  // before the first await so the browser cannot classify the popup as
  // a non-gesture open.
  const reserved = window.open('', '_blank');
  if (!reserved) {
    // (2) Honest blocked signal — no fetch, no blob, no false success.
    onNotifyError(messages.previewBlocked);
    return;
  }

  try {
    const token = getAccessToken();
    const response = await fetch(`${apiBase}/files/${fileId}/preview`, {
      headers: { Authorization: `Bearer ${token || ''}` },
    });

    if (!response.ok) {
      throw new Error(messages.previewUnavailable);
    }

    const blob = await response.blob();
    const blobUrl = window.URL.createObjectURL(blob);
    // (5) Same bounded revocation budget as the pre-fix implementation.
    window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60_000);

    // (3) Opener isolation preserved: sever the opener BEFORE navigating
    // the reserved context (manual `noopener` equivalent).
    reserved.opener = null;
    reserved.location.href = blobUrl;
  } catch (error: unknown) {
    // (4) Never leave a blank reserved tab behind a failure.
    reserved.close();
    const message =
      error instanceof Error && error.message ? error.message : messages.openFailed;
    onNotifyError(message);
  }
}
