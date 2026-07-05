import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Printer, AlertCircle, Wifi, WifiOff } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { printService } from '../../services/print';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';

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
  const { theme } = useTheme();
  const surfaceStyle = {
    backgroundColor: 'var(--mac-bg-secondary)',
    border: `1px solid ${theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'var(--mac-border)'}`,
    borderRadius: '14px',
  };
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
          result.error || 'Не удалось загрузить список принтеров',
        );
      }

      const backendPrinters = Array.isArray(result.data) ? result.data : [];
      const normalizedPrinters = backendPrinters.map((printer) => ({
        id: printer.name || String(printer.id),
        name: printer.display_name || printer.name || 'Принтер',
        status: printer.status || null,
        type: printer.printer_type || 'unknown',
        isDefault: Boolean(printer.is_default),
      }));

      setPrinters(normalizedPrinters);

      // Автовыбор принтера по умолчанию или первого доступного онлайн
      const onlinePrinter =
        normalizedPrinters.find((p) => p.isDefault && p.status === 'online') ||
        normalizedPrinters.find((p) => p.status === 'online');
      if (onlinePrinter) {
        setSelectedPrinter(onlinePrinter.id);
      } else {
        setSelectedPrinter('');
      }
    } catch (error) {
      logger.error('Error loading printers:', error);
      setError(error.message || 'Не удалось загрузить список принтеров');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrint = async () => {
    if (!usesBrowserPrint && !selectedPrinter) {
      toast.error('Выберите принтер');
      return;
    }

    const printer = printers.find((p) => p.id === selectedPrinter);
    if (!usesBrowserPrint && printer?.status !== 'online') {
      toast.error('Выбранный принтер недоступен');
      return;
    }

    setIsPrinting(true);

    try {
      if (onPrint) {
        await onPrint(
          usesBrowserPrint ? null : selectedPrinter,
          documentType,
          documentData,
        );
      }

      toast.success(
        usesBrowserPrint
          ? 'Открыт диалог печати этого компьютера'
          : 'Документ отправлен на печать',
      );
      onClose();
    } catch (error) {
      logger.error('Print error:', error);
      toast.error('Ошибка при печати: ' + error.message);
    } finally {
      setIsPrinting(false);
    }
  };

  const getDocumentTitle = () => {
    switch (documentType) {
      case 'ticket':
        return 'Талон пациента';
      case 'receipt':
        return 'Чек об оплате';
      case 'report':
        return 'Отчет';
      default:
        return 'Документ';
    }
  };

  const getDocumentIcon = () => {
    switch (documentType) {
      case 'ticket':
        return '🎫';
      case 'receipt':
        return '🧾';
      case 'report':
        return '📄';
      default:
        return '📄';
    }
  };

  const actions = [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: isPrinting,
    },
    {
      label: isPrinting ? 'Печатаем...' : 'Печать',
      variant: 'primary',
      icon: isPrinting ? null : <Printer size={16} />,
      onClick: handlePrint,
      disabled:
        isPrinting || isLoading || (!usesBrowserPrint && !selectedPrinter),
    },
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={`${getDocumentIcon()} Печать документа`}
      actions={actions}
      dialogStyle={{
        backgroundColor: 'var(--mac-bg-primary)',
      }}
      closeOnBackdrop={!isPrinting}
      closeOnEscape={!isPrinting}
    >
      <div>
        {/* Информация о документе */}
        <div
          style={{
            marginBottom: '24px',
            padding: '16px',
            ...surfaceStyle,
          }}
        >
          <h4
            style={{
              color: 'var(--color-text-primary)',
              margin: '0 0 8px 0',
              fontSize: '16px',
              fontWeight: '600',
            }}
          >
            {getDocumentTitle()}
          </h4>

          {documentData && (
            <div
              style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}
            >
              {documentData.patient_fio && (
                <p
                  style={{
                    color: 'var(--color-text-secondary)',
                    margin: 0,
                    fontSize: '14px',
                  }}
                >
                  Пациент: <strong>{documentData.patient_fio}</strong>
                </p>
              )}

              {documentData.services && (
                <p
                  style={{
                    color: 'var(--color-text-secondary)',
                    margin: 0,
                    fontSize: '14px',
                  }}
                >
                  Услуги: {formatPrintServices(documentData.services)}
                </p>
              )}

              {documentData.cost && (
                <p
                  style={{
                    color: 'var(--color-text-secondary)',
                    margin: 0,
                    fontSize: '14px',
                  }}
                >
                  {/* UX Audit Registrar #1: toLocaleString() без локали + валюта ₽ (рубли)
                      вместо UZS (сумы). Исправлено на ru-RU + UZS. */}
                  Сумма: <strong>{new Intl.NumberFormat('ru-RU').format(documentData.cost)} сум</strong>
                </p>
              )}

              {/* UX Audit Registrar #1: показываем количество талонов для multi-service записи.
                  print_tickets и queue_numbers формируются в buildPostWizardPaymentRow.
                  printPanelTicketInBrowserAsync() уже печатает все талоны в одном окне
                  с page-break-after, но пользователь не знал, что их будет несколько. */}
              {(() => {
                const ticketCount =
                  (Array.isArray(documentData.print_tickets) ? documentData.print_tickets.length : 0) ||
                  (Array.isArray(documentData.queue_numbers) ? documentData.queue_numbers.length : 0);
                if (ticketCount > 1) {
                  return (
                    <p
                      style={{
                        color: 'var(--mac-accent-blue, #0ea5e9)',
                        margin: 0,
                        fontSize: '14px',
                        fontWeight: 600,
                      }}
                    >
                      🖨️ Будет напечатано талонов: {ticketCount}
                    </p>
                  );
                }
                return null;
              })()}
            </div>
          )}
        </div>

        {usesBrowserPrint ? (
          <div
            style={{
              padding: '16px',
              borderRadius: '14px',
              backgroundColor:
                theme === 'dark' ? 'rgba(59, 130, 246, 0.08)' : 'var(--mac-accent-bg)',
              border: `1px solid ${theme === 'dark' ? 'rgba(59, 130, 246, 0.24)' : '#bfdbfe'}`,
              color: 'var(--color-text-primary)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                marginBottom: '8px',
              }}
            >
              <Printer size={20} />
              <strong>Печать через браузер</strong>
            </div>
            <p
              style={{
                margin: '0 0 8px 0',
                fontSize: '14px',
                color: 'var(--color-text-secondary)',
              }}
            >
              Будет открыт системный диалог печати на текущем компьютере.
            </p>
            <p
              style={{
                margin: 0,
                fontSize: '14px',
                color: 'var(--color-text-secondary)',
              }}
            >
              Список принтеров покажет устройства именно этого ПК, а не сервера.
            </p>
          </div>
        ) : (
          <>
            {/* Выбор принтера */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: '500',
                  marginBottom: '12px',
                  color: 'var(--color-text-primary)',
                }}
              >
                Выберите принтер
              </label>

              {isLoading ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '40px',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <div
                    className="loading-spinner"
                    style={{ marginRight: '12px' }}
                  ></div>
                  Загрузка принтеров...
                </div>
              ) : error ? (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '16px',
                    backgroundColor:
                      theme === 'dark' ? 'rgba(239, 68, 68, 0.10)' : 'var(--mac-error-bg)',
                    border: `1px solid ${theme === 'dark' ? 'rgba(239, 68, 68, 0.24)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'}`,
                    borderRadius: '14px',
                    color: theme === 'dark' ? '#fca5a5' : 'var(--mac-error)',
                  }}
                >
                  <AlertCircle size={20} />
                  <div>
                    <p style={{ margin: '0 0 8px 0', fontWeight: '500' }}>
                      Ошибка загрузки принтеров
                    </p>
                    <p style={{ margin: 0, fontSize: '14px' }}>{error}</p>
                    <button
                      onClick={loadPrinters}
                      style={{
                        marginTop: '8px',
                        padding: '4px 8px',
                        fontSize: '12px',
                        backgroundColor: 'transparent',
                        border: '1px solid currentColor',
                        borderRadius: '4px',
                        color: 'inherit',
                        cursor: 'pointer',
                      }}
                    >
                      Повторить
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
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
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '12px 14px',
                        border: `1px solid ${
                          selectedPrinter === printer.id
                            ? 'var(--mac-accent-blue)'
                            : theme === 'dark'
                              ? 'rgba(255,255,255,0.10)'
                              : 'var(--mac-border)'
                        }`,
                        borderRadius: '12px',
                        backgroundColor:
                          selectedPrinter === printer.id
                            ? theme === 'dark'
                              ? 'rgba(59, 130, 246, 0.16)'
                              : 'var(--mac-accent-bg)'
                            : theme === 'dark'
                              ? 'rgba(255,255,255,0.04)'
                              : 'white',
                        cursor:
                          printer.status === 'online'
                            ? 'pointer'
                            : 'not-allowed',
                        opacity: printer.status === 'online' ? 1 : 0.6,
                        transition: 'all 0.2s ease',
                      }}
                    >
                      {/* Радио кнопка */}
                      <div
                        style={{
                          width: '16px',
                          height: '16px',
                          borderRadius: '50%',
                          border: `2px solid ${selectedPrinter === printer.id ? 'var(--mac-accent-blue)' : 'var(--mac-text-tertiary)'}`,
                          backgroundColor:
                            selectedPrinter === printer.id
                              ? 'var(--mac-accent-blue)'
                              : 'transparent',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                        }}
                      >
                        {selectedPrinter === printer.id && (
                          <div
                            style={{
                              width: '6px',
                              height: '6px',
                              borderRadius: '50%',
                              backgroundColor: 'white',
                            }}
                          />
                        )}
                      </div>

                      {/* Иконка принтера */}
                      <Printer
                        size={20}
                        style={{
                          color: 'var(--color-text-secondary)',
                          flexShrink: 0,
                        }}
                      />

                      {/* Информация о принтере */}
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            color: 'var(--color-text-primary)',
                            fontSize: '14px',
                            fontWeight: '500',
                          }}
                        >
                          {printer.name}
                        </div>
                        <div
                          style={{
                            color: 'var(--color-text-secondary)',
                            fontSize: '12px',
                            marginTop: '2px',
                          }}
                        >
                          {printer.type === 'thermal' ||
                          printer.type === 'ESC/POS'
                            ? 'Термопринтер'
                            : printer.type === 'A4' ||
                                printer.type === 'A5' ||
                                printer.type === 'laser'
                              ? 'Лазерный принтер'
                              : printer.type}
                        </div>
                      </div>

                      {/* Статус */}
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '12px',
                          fontWeight: '500',
                          color:
                            printer.status === 'online'
                              ? '#10b981'
                              : printer.status
                                ? 'var(--mac-error)'
                                : '#64748b',
                        }}
                      >
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
                <div
                  style={{
                    textAlign: 'center',
                    padding: '40px',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <Printer
                    size={48}
                    style={{ opacity: 0.3, marginBottom: '16px' }}
                  />
                  <p style={{ margin: 0 }}>Принтеры не найдены</p>
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
  }),
  onPrint: PropTypes.func,
};

export default PrintDialog;
