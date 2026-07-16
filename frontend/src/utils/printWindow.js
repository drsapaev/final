import DOMPurify from 'dompurify';

export const sanitizePrintableHtml = (html) => DOMPurify.sanitize(String(html ?? ''), {
  WHOLE_DOCUMENT: true,
  ADD_TAGS: ['html', 'head', 'body', 'style'],
  ADD_ATTR: ['style', 'class', 'id', 'role', 'aria-label', 'colspan', 'rowspan']
});

export const finalizePrintableWindow = (printWindow, html, logger) => {
  if (!printWindow) {
    return false;
  }

  printWindow.document.open();
  printWindow.document.write(sanitizePrintableHtml(html));
  printWindow.document.close();

  let finalized = false;

  const finalizePrint = () => {
    if (finalized || printWindow.closed) {
      return;
    }

    finalized = true;

    try {
      printWindow.focus();
      printWindow.print();
    } catch (error) {
      logger?.warn?.('Не удалось запустить печать в popup-окне', error);
    } finally {
      printWindow.close();
    }
  };

  if (printWindow.document.readyState === 'complete') {
    finalizePrint();
  } else {
    printWindow.onload = finalizePrint;
    setTimeout(finalizePrint, 300);
  }

  return true;
};

interface OpenPrintableWindowOptions {
  html: string;
  features?: string;
  logger?: unknown;
  onOpenFailure?: () => void;
}

export const openPrintableWindow = ({
  html,
  features = 'width=900,height=700',
  logger,
  onOpenFailure,
}: OpenPrintableWindowOptions): boolean => {
  const printWindow = window.open('', '_blank', features);

  if (!printWindow) {
    if (onOpenFailure) {
      onOpenFailure();
    }
    return false;
  }

  return finalizePrintableWindow(printWindow, html, logger);
};
