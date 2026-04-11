export const finalizePrintableWindow = (printWindow, html, logger) => {
  if (!printWindow) {
    return false;
  }

  printWindow.document.open();
  printWindow.document.write(html);
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

export const openPrintableWindow = ({
  html,
  features = 'width=900,height=700',
  logger,
  onOpenFailure
}) => {
  const printWindow = window.open('', '_blank', features);

  if (!printWindow) {
    if (onOpenFailure) {
      onOpenFailure();
    }
    return false;
  }

  return finalizePrintableWindow(printWindow, html, logger);
};
