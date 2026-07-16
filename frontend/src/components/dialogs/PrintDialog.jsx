import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Printer, AlertCircle, Wifi, WifiOff, Printer as PrinterIcon } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { printService } from '../../services/print';
import { toast } from 'react-toastify';
// UX Audit Registrar #5: все inline-стили перенесены в PrintDialog.css.
// useTheme удалён — больше не нужен (всё через macos tokens + [data-theme="dark"]).
// Также: emoji 🖨️ в ticket-count заменён на lucide Printer icon.
import './PrintDialog.css';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const formatPrintServiceLabel = (service) => {
  if (service == null) return '';

  if (
    typeof service === 'string' ||
    typeof service === 'number' ||
    typeof service === 'bigint'
  ) {
    return String(service).trim();
  }

  if (typeof service === 'object') {
    const candidate =
      service.service_name ||
      service.name ||
      service.code ||
      service.service_code ||
      service.label ||
      service.title ||
      service.value ||
      '';
    return String(candidate).trim();
  }

  return String(service).trim();
};

const formatPrintServices = (services) => {
  if (Array.isArray(services)) {
    return services.map(formatPrintServiceLabel).filter(Boolean).join(', ');
  }

  return formatPrintServiceLabel(services);
};

const PrintDialog = ({
  isOpen,
  onClose,
  documentType = 'ticket',
  documentData,
  onPrint,
}) => {
  const { t } = useTranslation();
  const [printers, setPrinters] = useState([]);
  const [selectedPrinter, setSelectedPrinter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPrinting, setIsPrinting] = useState(false);
  const [error, setError] = useState('');
  const usesBrowserPrint = documentType === 'ticket';

  // Загрузка списка принтеров
  useEffect(() => {
    if (isOpen && !usesBrowserPrint) {
      loadPrinters();
      return;
    }

    if (isOpen && usesBrowserPrint) {
      setPrinters([]);
      setSelectedPrinter('');
      setError('');
      setIsLoading(false);
    }
  }, [isOpen, usesBrowserPrint]);

  const loadPrinters = async () => {
    setIsLoading(true);
    setError('');

    try {
      const result = await printService.getPrinters();
      if (!result.success) {
        throw new Error(
          result.error || t('misc.pd_ne_udalos_zagruzit_spisok_pr'),
        );
      }

      const backendPrinters = Array.isArray(result.data) ? result.data : [];
      const normalizedPrinters = backendPrinters.map((printer) => ({
        id: printer.name || String(printer.id),
        name: printer.display_name || printer.name || t('misc.pd_printer'),
        status: printer.status || null,
        type: printer.printer_type || 'unknown',
        isDefault: Boolean(printer.is_default),
      }));

      setPrinters(normalizedPrinters);

      const defaultPrinter = normalizedPrinters.find((p) => p.isDefault);
      const firstOnline = normalizedPrinters.find((p) => p.status === 'online');
      setSelectedPrinter(
        defaultPrinter?.id || firstOnline?.id || normalizedPrinters[0]?.id || '',
      );
    } catch (err) {
      logger.error('Printers load error:', err);
      setError(err.message || t('misc.pd_ne_udalos_zagruzit_printery'));
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrint = async () => {
    if (usesBrowserPrint) {
      setIsPrinting(true);
      try {
        if (onPrint) {
          await onPrint(documentData);
        }
        toast.success(t('misc.pd_dokument_otpravlen_na_pechat'));
        onClose();
      } catch (err) {
        logger.error('Print error:', err);
        toast.error(err?.message || t('misc.pd_oshibka_pri_pechati_dokument'));
      } finally {
        setIsPrinting(false);
      }
      return;
    }

    if (!selectedPrinter) {
      toast.error(t('misc.pd_vyberite_printer'));
      return;
    }

    setIsPrinting(true);
    try {
      if (onPrint) {
        await onPrint(documentData, selectedPrinter);
      }
      toast.success(t('misc.pd_dokument_otpravlen_na_printe', { selectedPrinter: selectedPrinter }));
      onClose();
    } catch (err) {
      logger.error('Print error:', err);
      toast.error(err?.message || t('misc.pd_oshibka_pri_pechati_dokument'));
    } finally {
      setIsPrinting(false);
    }
  };

  const getDocumentTitle = () => {
    switch (documentType) {
      case 'ticket':
        return t('misc.pd_talon_patsienta');
      case 'receipt':
        return t('misc.pd_kvitantsiya_ob_oplate');
      case 'report':
        return t('misc.pd_otchyot');
      default:
        return t('misc.pd_dokument');
    }
  };

  const actions = [
    {
      label: t('misc.pd_otmena'),
      variant: 'secondary',
      onClick: onClose,
      disabled: isPrinting,
    },
    {
      label: isPrinting ? t('misc.pd_pechat') : t('misc.pd_pechat_2'),
      variant: 'primary',
      icon: <Printer size={16} />,
      onClick: handlePrint,
      disabled: isPrinting || (!usesBrowserPrint && !selectedPrinter),
    },
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={t('misc.pd_pechat_dokumenta')}
      actions={actions}
      dialogClassName="print-dialog--styled"
      closeOnBackdrop={!isPrinting}
      closeOnEscape={!isPrinting}
    >
      <div>
        {/* Информация о документе */}
        <div className="print-doc-card">
          <h4 className="print-doc-title">
            {getDocumentTitle()}
          </h4>

          {documentData && (
            <div className="print-doc-fields">
              {documentData.patient_fio && (
                <p className="print-doc-field">
                  Пациент: <strong>{documentData.patient_fio}</strong>
                </p>
              )}

              {documentData.services && (
                <p className="print-doc-field">
                  Услуги: {formatPrintServices(documentData.services)}
                </p>
              )}

              {documentData.cost && (
                <p className="print-doc-field">
                  {/* UX Audit Registrar #1: toLocaleString() без локали + валюта ₽ (рубли)
                      вместо UZS (сумы). Исправлено на ru-RU + UZS. */}
                  Сумма: <strong>{new Intl.NumberFormat('ru-RU').format(documentData.cost)} сум</strong>
                </p>
              )}

              {/* UX Audit Registrar #1: показываем количество талонов для multi-service записи. */}
              {(() => {
                const ticketCount =
                  (Array.isArray(documentData.print_tickets) ? documentData.print_tickets.length : 0) ||
                  (Array.isArray(documentData.queue_numbers) ? documentData.queue_numbers.length : 0);
                if (ticketCount > 1) {
                  return (
                    <p className="print-doc-ticket-count">
                      <PrinterIcon size={16} aria-hidden="true" />
                      <span>Будет напечатано талонов: {ticketCount}</span>
                    </p>
                  );
                }
                return null;
              })()}
            </div>
          )}
        </div>

        {usesBrowserPrint ? (
          <div className="print-browser-notice">
            <div className="print-browser-notice-header">
              <Printer size={20} />
              <strong>{t('misc.pd_pechat_cherez_brauzer')}</strong>
            </div>
            <p className="print-browser-notice-text">
              Будет открыт системный диалог печати на текущем компьютере.
            </p>
            <p className="print-browser-notice-hint">
              Список принтеров покажет устройства именно этого ПК, а не сервера.
            </p>
          </div>
        ) : (
          <>
            {/* Выбор принтера */}
            <div>
              <label className="print-field-label">
                Выберите принтер
              </label>

              {isLoading ? (
                <div className="print-loading">
                  <div className="loading-spinner print-loading-spinner"></div>
                  Загрузка принтеров...
                </div>
              ) : error ? (
                <div className="print-error-box">
                  <AlertCircle size={20} />
                  <div>
                    <p className="print-error-title">
                      Ошибка загрузки принтеров
                    </p>
                    <p className="print-error-message">{error}</p>
                    <button onClick={loadPrinters} className="print-retry-btn">
                      Повторить
                    </button>
                  </div>
                </div>
              ) : (
                <div className="print-printers-container">
                  {printers.map((printer) => (
                    <div
                      key={printer.id}
                      role="button"
                      tabIndex={printer.status === 'online' ? 0 : -1}
                      aria-disabled={printer.status !== 'online'}
                      onClick={() => {
                        if (printer.status === 'online') {
                          setSelectedPrinter(printer.id);
                        }
                      }}
                      onKeyDown={(event) => {
                        if (
                          (event.key === 'Enter' || event.key === ' ') &&
                          printer.status === 'online'
                        ) {
                          event.preventDefault();
                          setSelectedPrinter(printer.id);
                        }
                      }}
                      className={`print-printer-item ${selectedPrinter === printer.id ? 'print-printer-item--selected' : ''} ${printer.status !== 'online' ? 'print-printer-item--disabled' : ''}`}
                    >
                      {/* Радио кнопка */}
                      <div className={`print-radio ${selectedPrinter === printer.id ? 'print-radio--selected' : ''}`}>
                        {selectedPrinter === printer.id && <div className="print-radio-dot" />}
                      </div>

                      {/* Иконка принтера */}
                      <Printer size={20} className="print-printer-icon" />

                      {/* Информация о принтере */}
                      <div className="print-printer-info">
                        <div className="print-printer-name-text">
                          {printer.name}
                        </div>
                        <div className="print-printer-type">
                          {printer.type === 'thermal' ||
                          printer.type === 'ESC/POS'
                            ? t('misc.pd_termoprinter')
                            : printer.type === 'A4' ||
                                printer.type === 'A5' ||
                                printer.type === 'laser'
                              ? t('misc.pd_lazernyy_printer')
                              : printer.type}
                        </div>
                      </div>

                      {/* Статус */}
                      <div className={`print-status-badge ${printer.status === 'online' ? 'print-status-badge--online' : printer.status ? 'print-status-badge--error' : ''}`}>
                        {printer.status === 'online' ? (
                          <>
                            <Wifi size={14} />
                            Онлайн
                          </>
                        ) : printer.status ? (
                          <>
                            <WifiOff size={14} />
                            Офлайн
                          </>
                        ) : (
                          <>
                            <WifiOff size={14} />
                            Статус неизвестен
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {printers.length === 0 && !isLoading && !error && (
                <div className="print-empty-state-full">
                  <Printer size={48} className="print-empty-state-icon" />
                  <p className="print-empty-state-text">{t('misc.pd_printery_ne_naydeny')}</p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </ModernDialog>
  );
};

PrintDialog.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  documentType: PropTypes.oneOf(['ticket', 'receipt', 'report']),
  documentData: PropTypes.shape({
    patient_fio: PropTypes.string,
    services: PropTypes.oneOfType([
      PropTypes.arrayOf(
        PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
      ),
      PropTypes.string,
    ]),
    cost: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    // UX Audit Registrar #5: добавлены пропсы для multi-service ticket count.
    print_tickets: PropTypes.array,
    queue_numbers: PropTypes.array,
  }),
  onPrint: PropTypes.func,
};

export default PrintDialog;
