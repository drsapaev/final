/**
 * CSH-FE-044 (follow-up audit 2026-11-02): честный исход печати из
 * printWindow.ts.
 *
 * Прежде finalizePrintableWindow возвращал `true` ВСЕГДА: print() бросал
 * исключение — возвращалось true; печать откладывалась на onload/300ms —
 * возвращалось true. Кассирный путь (useCashierActions) на этом «успехе»
 * пропускал серверный PDF-fallback, а пользователь видел тост «диалог
 * печати открыт», который не открывался.
 *
 * Red-first (до фикса): все 4 сценария ниже проваливались — функция
 * возвращала булево `true`, на котором `.printInvoked`/`.deferred`
 * не определены (undefined !== ожидаемого значения).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  finalizePrintableWindow,
  openPrintableWindow,
  sanitizePrintableHtml,
} from '../printWindow';

const noopLogger = { log: () => {}, warn: () => {} };

type FakeWindowOptions = {
  readyState?: string;
  printImpl?: () => void;
};

const makeFakeWindow = ({ readyState = 'complete', printImpl }: FakeWindowOptions = {}) => {
  const win: Record<string, unknown> = {
    closed: false,
    document: {
      open: vi.fn(),
      write: vi.fn(),
      close: vi.fn(),
      readyState,
    },
    focus: vi.fn(),
    print: vi.fn(printImpl ?? (() => {})),
    close: vi.fn(),
  };
  return win as unknown as Window & typeof globalThis;
};

describe('sanitizePrintableHtml — DOMPurify WHOLE_DOCUMENT (unchanged boundary)', () => {
  it('keeps a full html document and strips scripts', () => {
    const out = sanitizePrintableHtml('<html><head></head><body><script>alert(1)</script><p>ok</p></body></html>');
    expect(out).toContain('<p>ok</p>');
    expect(out).not.toContain('<script');
  });
});

describe('finalizePrintableWindow — CSH-FE-044 typed outcome', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('null window → { opened: false } (not a boolean lie)', () => {
    const result = finalizePrintableWindow(null as unknown as Window, '<html></html>', noopLogger);
    expect(result).toEqual({ opened: false, printInvoked: false, deferred: false });
  });

  it('sync path: print() succeeds → printInvoked: true, deferred: false', () => {
    const win = makeFakeWindow({ readyState: 'complete' });
    const result = finalizePrintableWindow(win, '<html><body>talón</body></html>', noopLogger);
    expect(result).toEqual({ opened: true, printInvoked: true, deferred: false });
    expect(win.print).toHaveBeenCalledTimes(1);
    expect(win.close).toHaveBeenCalledTimes(1);
  });

  it('sync path: print() THROWS → printInvoked: false — exception is not swallowed', () => {
    const warn = vi.fn();
    const logger = { log: () => {}, warn };
    const win = makeFakeWindow({
      readyState: 'complete',
      printImpl: () => {
        throw new Error('print preview is disabled');
      },
    });
    const result = finalizePrintableWindow(win, '<html></html>', logger);
    // CSH-FE-044: провал вызова печати виден вызывающему (раньше — true).
    expect(result).toEqual({ opened: true, printInvoked: false, deferred: false });
    expect(result.printInvoked).toBe(false);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(win.close).toHaveBeenCalledTimes(1);
  });

  it('deferred path: readyState !== complete → deferred: true, print not yet confirmed', () => {
    const win = makeFakeWindow({ readyState: 'loading' });
    const result = finalizePrintableWindow(win, '<html></html>', noopLogger);
    expect(result).toEqual({ opened: true, printInvoked: false, deferred: true });
    expect(win.print).not.toHaveBeenCalled();
  });
});

describe('openPrintableWindow — CSH-FE-044 propagates the typed outcome', () => {
  const originalOpen = window.open;

  afterEach(() => {
    window.open = originalOpen;
    vi.restoreAllMocks();
  });

  it('popup blocked → { opened: false } + onOpenFailure', () => {
    window.open = vi.fn(() => null);
    const onOpenFailure = vi.fn();
    const result = openPrintableWindow({
      html: '<html></html>',
      logger: noopLogger,
      onOpenFailure,
    });
    expect(result).toEqual({ opened: false, printInvoked: false, deferred: false });
    expect(onOpenFailure).toHaveBeenCalledTimes(1);
  });

  it('opened + print throws → the receipt caller can fall back to PDF', () => {
    const win = makeFakeWindow({
      readyState: 'complete',
      printImpl: () => {
        throw new Error('printing not available');
      },
    });
    window.open = vi.fn(() => win);
    const result = openPrintableWindow({ html: '<html></html>', logger: noopLogger });
    expect(result.opened).toBe(true);
    expect(result.printInvoked).toBe(false);
    expect(result.deferred).toBe(false);
  });
});
