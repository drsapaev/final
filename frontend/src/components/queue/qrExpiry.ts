/**
 * RQ-11: honest QR expiry presentation helpers.
 *
 * F-10: the downloadable QR is treated as a poster, but the join token has
 * a server-defined lifetime. The dialog already showed
 * "Действует до: {time}", but the downloaded PNG carried no lifetime
 * information and there was no expired state, so a stale poster silently
 * promised unlimited access.
 *
 * This module is pure (no React, no DOM): resolveQrExpiryView classifies the
 * server-provided expires_at against a caller-supplied `now` (fake-clock
 * friendly), buildQrDownloadCaptions maps the classification to honest
 * caption lines for the downloaded PNG. Formatting uses the canonical
 * registrar timestamp contract (Asia/Tashkent) from utils/dateUtils.
 *
 * Scope guard (RQ-11): presentation only. No TTL change, no token/protection
 * change, no server contract change (a constant D-03 link is out of scope).
 */

import { formatRegistrarDateTime, parseRegistrarTimestamp } from '../../utils/dateUtils';

export type QrExpiryState = 'valid' | 'expired' | 'unspecified';

export interface QrExpiryView {
  state: QrExpiryState;
  /**
   * Formatted expiry timestamp in the clinic timezone; null when the expiry
   * is unknown or already due.
   */
  formattedExpiresAt: string | null;
}

/**
 * Classify the server-provided expires_at against `now`.
 *
 * - 'valid'       — expiry exists and is still in the future
 * - 'expired'     — expiry exists and is already due (<= now)
 * - 'unspecified' — no parseable expiry; the code must NOT be presented as
 *   unlimited, the UI shows a limited-lifetime note instead
 */
export const resolveQrExpiryView = (
  expiresAt: unknown,
  now: Date = new Date(),
): QrExpiryView => {
  const parsed = parseRegistrarTimestamp(expiresAt);
  if (!parsed) {
    return { state: 'unspecified', formattedExpiresAt: null };
  }
  if (parsed.getTime() <= now.getTime()) {
    return { state: 'expired', formattedExpiresAt: null };
  }
  return {
    state: 'valid',
    formattedExpiresAt: formatRegistrarDateTime(expiresAt),
  };
};

/** Caption lines rendered onto the downloaded QR PNG. */
export interface QrDownloadCaptions {
  /**
   * Primary line: "valid until …" or the expired explanation; null when the
   * expiry is unspecified (only the temporary-note line is drawn).
   */
  primaryLine: string | null;
  /** Always-present note: the code is temporary, not a permanent pass. */
  noteLine: string;
}

export interface QrDownloadCaptionsInput {
  state: QrExpiryState;
  formattedExpiresAt: string | null;
  /**
   * i18n labels already resolved by the caller via t(): validUntil must
   * include the formatted time (t('misc.mqm_qr_valid_until', { time })).
   */
  labels: {
    validUntil: string;
    expired: string;
    temporaryNote: string;
  };
}

/**
 * Build honest caption lines for the downloaded PNG:
 * - valid       → "Действует до: {time}" + temporary note
 * - expired     → expired explanation + temporary note
 * - unspecified → only the temporary note (never implies unlimited access)
 */
export const buildQrDownloadCaptions = (
  input: QrDownloadCaptionsInput,
): QrDownloadCaptions => {
  const { state, formattedExpiresAt, labels } = input;
  let primaryLine: string | null = null;
  if (state === 'valid' && formattedExpiresAt) {
    primaryLine = labels.validUntil;
  } else if (state === 'expired') {
    primaryLine = labels.expired;
  }
  return { primaryLine, noteLine: labels.temporaryNote };
};
