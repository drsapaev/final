import { describe, expect, it } from 'vitest';

import {
  buildQrDownloadCaptions,
  resolveQrExpiryView,
} from '../qrExpiry';

// RQ-11 S-09: honest QR expiry classification (fake clock via explicit now).
const NOW = new Date('2026-09-12T12:00:00+05:00');

const LABELS = {
  validUntil: 'Действует до: 12.09 14:00',
  expired: 'Срок действия истек — сгенерируйте новый код',
  temporaryNote: 'Временный код для записи в очередь',
};

describe('resolveQrExpiryView (RQ-11)', () => {
  it('classifies a future ISO expiry as valid and formats it in the clinic timezone', () => {
    const view = resolveQrExpiryView('2099-01-15T10:30:00+05:00', NOW);
    expect(view.state).toBe('valid');
    expect(view.formattedExpiresAt).toBeTruthy();
    // Clinic timezone (Asia/Tashkent) canonical formatting keeps the minutes.
    expect(view.formattedExpiresAt).toContain('30');
  });

  it('classifies a past ISO expiry as expired without a display time', () => {
    const view = resolveQrExpiryView('2001-01-01T00:00:00+05:00', NOW);
    expect(view.state).toBe('expired');
    expect(view.formattedExpiresAt).toBeNull();
  });

  it('treats an expiry exactly equal to now as expired (inclusive boundary)', () => {
    const view = resolveQrExpiryView('2026-09-12T12:00:00+05:00', NOW);
    expect(view.state).toBe('expired');
  });

  it('parses legacy naive timestamps in the clinic timezone (+05:00 contract)', () => {
    // Backend legacy rows store naive timestamps that mean Asia/Tashkent.
    const view = resolveQrExpiryView('2099-01-15 10:30:00', NOW);
    expect(view.state).toBe('valid');
    expect(view.formattedExpiresAt).toBeTruthy();
  });

  it.each([
    ['missing', undefined],
    ['null', null],
    ['empty string', ''],
    ['garbage', 'not-a-date'],
  ])('treats %s expiry as unspecified (never unlimited)', (_name, value) => {
    const view = resolveQrExpiryView(value, NOW);
    expect(view.state).toBe('unspecified');
    expect(view.formattedExpiresAt).toBeNull();
  });
});

describe('buildQrDownloadCaptions (RQ-11)', () => {
  it('draws the valid-until line plus the temporary-code note', () => {
    const captions = buildQrDownloadCaptions({
      state: 'valid',
      formattedExpiresAt: '15.01.2099 10:30',
      labels: LABELS,
    });
    expect(captions.primaryLine).toBe(LABELS.validUntil);
    expect(captions.noteLine).toBe(LABELS.temporaryNote);
  });

  it('draws the expired explanation plus the temporary-code note', () => {
    const captions = buildQrDownloadCaptions({
      state: 'expired',
      formattedExpiresAt: null,
      labels: LABELS,
    });
    expect(captions.primaryLine).toBe(LABELS.expired);
    expect(captions.noteLine).toBe(LABELS.temporaryNote);
  });

  it('never implies unlimited access when the expiry is unspecified', () => {
    const captions = buildQrDownloadCaptions({
      state: 'unspecified',
      formattedExpiresAt: null,
      labels: LABELS,
    });
    expect(captions.primaryLine).toBeNull();
    expect(captions.noteLine).toBe(LABELS.temporaryNote);
  });

  it('guards against a valid state without a formatted time', () => {
    const captions = buildQrDownloadCaptions({
      state: 'valid',
      formattedExpiresAt: null,
      labels: LABELS,
    });
    expect(captions.primaryLine).toBeNull();
  });
});
