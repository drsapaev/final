import DOMPurify from 'dompurify';

export const sanitizePrintableHtml = (html: string) => DOMPurify.sanitize(String(html ?? ''), {
  WHOLE_DOCUMENT: true,
  ADD_TAGS: ['html', 'head', 'body', 'style'],
  ADD_ATTR: ['style', 'class', 'id', 'role', 'aria-label', 'colspan', 'rowspan']
});

// CSH-FE-044 (follow-up audit 2026-11-02): типизированный исход печати.
// Прежний контракт возвращал `true` ВСЕГДА — даже когда print() бросил
// исключение (jsdom/отключённый предпросмотр) или печать была отложена
// на onload/timeout. Кассирный путь (useCashierActions) пропускал
// серверный PDF-fallback на «открывшемся» диалоге, который не открывался.
// Теперь исход честный:
//   opened       — popup открыт и документ записан;
//   printInvoked — print() завершился без исключения (синхронно);
//   deferred     — печать отложена (onload/300ms): окно открыто, но
//                  печать ещё НЕ подтверждена — вызывающий не должен
//                  заявлять «диалог печати открыт» как свершившийся факт
//                  и обязан оставить пользователю путь восстановления.
export interface PrintableWindowResult {
  opened: boolean;
  printInvoked: boolean;
  deferred: boolean;
}

export const finalizePrintableWindow = (
  printWindow: Window,
  html: string,
  logger: { log: (...args: unknown[]) => void; warn: (...args: unknown[]) => void }
): PrintableWindowResult => {
  if (!printWindow) {
    return { opened: false, printInvoked: false, deferred: false };
  }

  printWindow.document.open();
  printWindow.document.write(sanitizePrintableHtml(html));
  printWindow.document.close();

  let finalized = false;
  let printInvoked = false;

  const finalizePrint = () => {
    if (finalized || printWindow.closed) {
      return;
    }

    finalized = true;

    try {
      printWindow.focus();
      printWindow.print();
      printInvoked = true;
    } catch (error) {
      // CSH-FE-044: исключение печати больше не глотается молча —
      // вызывающий увидит printInvoked=false и сможет упасть в PDF.
      logger?.warn?.('Не удалось запустить печать в popup-окне', error);
    } finally {
      printWindow.close();
    }
  };

  if (printWindow.document.readyState === 'complete') {
    finalizePrint();
    // Синхронный путь: printInvoked уже известен точно.
    return { opened: true, printInvoked, deferred: false };
  }

  // Отложенный путь: print() сработает позже (onload/300ms) — исход
  // честно помечается как «окно открыто, печать не подтверждена».
  printWindow.onload = finalizePrint;
  setTimeout(finalizePrint, 300);
  return { opened: true, printInvoked: false, deferred: true };
};

interface OpenPrintableWindowOptions {
  html: string;
  features?: string;
  logger?: { log: (...args: unknown[]) => void; warn: (...args: unknown[]) => void };
  onOpenFailure?: () => void;
}

export const openPrintableWindow = ({
  html,
  features = 'width=900,height=700',
  logger,
  onOpenFailure,
}: OpenPrintableWindowOptions): PrintableWindowResult => {
  const printWindow = window.open('', '_blank', features);

  if (!printWindow) {
    if (onOpenFailure) {
      onOpenFailure();
    }
    return { opened: false, printInvoked: false, deferred: false };
  }

  return finalizePrintableWindow(printWindow, html, logger || { log: () => {}, warn: () => {} });
};
