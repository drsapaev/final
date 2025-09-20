import React, { useState, useEffect } from 'react';
import { Printer, Check, AlertCircle, Wifi, WifiOff } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-hot-toast';

const PrintDialog = ({ 
  isOpen, 
  onClose, 
  documentType = 'ticket',
  documentData,
  onPrint
}) => {
  const { theme, getColor } = useTheme();
  const [printers, setPrinters] = useState([]);
  const [selectedPrinter, setSelectedPrinter] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPrinting, setIsPrinting] = useState(false);
  const [error, setError] = useState('');

  // Загрузка списка принтеров
  useEffect(() => {
    if (isOpen) {
      loadPrinters();
    }
  }, [isOpen]);

  const loadPrinters = async () => {
    setIsLoading(true);
    setError('');
    
    try {
      // Заглушка для принтеров (как в оригинальном коде)
      const mockPrinters = [
        { 
          id: 'default', 
          name: 'Принтер по умолчанию', 
          status: 'online',
          type: 'thermal'
        },
        { 
          id: 'hp_laser', 
          name: 'HP LaserJet Pro', 
          status: 'online',
          type: 'laser'
        },
        { 
          id: 'receipt_printer', 
          name: 'Чековый принтер', 
          status: 'offline',
          type: 'thermal'
        }
      ];
      
      setPrinters(mockPrinters);
      
      // Автовыбор первого доступного принтера
      const onlinePrinter = mockPrinters.find(p => p.status === 'online');
      if (onlinePrinter) {
        setSelectedPrinter(onlinePrinter.id);
      }
    } catch (error) {
      console.error('Error loading printers:', error);
      setError('Не удалось загрузить список принтеров');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrint = async () => {
    if (!selectedPrinter) {
      toast.error('Выберите принтер');
      return;
    }

    const printer = printers.find(p => p.id === selectedPrinter);
    if (printer?.status !== 'online') {
      toast.error('Выбранный принтер недоступен');
      return;
    }

    setIsPrinting(true);
    
    try {
      // Имитация печати
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      if (onPrint) {
        await onPrint(selectedPrinter, documentType, documentData);
      }
      
      toast.success('Документ отправлен на печать');
      onClose();
    } catch (error) {
      console.error('Print error:', error);
      toast.error('Ошибка при печати: ' + error.message);
    } finally {
      setIsPrinting(false);
    }
  };

  const getDocumentTitle = () => {
    switch (documentType) {
      case 'ticket': return 'Талон пациента';
      case 'receipt': return 'Чек об оплате';
      case 'report': return 'Отчет';
      default: return 'Документ';
    }
  };

  const getDocumentIcon = () => {
    switch (documentType) {
      case 'ticket': return '🎫';
      case 'receipt': return '🧾';
      case 'report': return '📄';
      default: return '📄';
    }
  };

  const actions = [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: isPrinting
    },
    {
      label: isPrinting ? 'Печатаем...' : 'Печать',
      variant: 'primary',
      icon: isPrinting ? null : <Printer size={16} />,
      onClick: handlePrint,
      disabled: isPrinting || !selectedPrinter || isLoading
    }
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={`${getDocumentIcon()} Печать документа`}
      actions={actions}
      closeOnBackdrop={!isPrinting}
      closeOnEscape={!isPrinting}
    >
      <div>
        {/* Информация о документе */}
        <div style={{ 
          marginBottom: '24px',
          padding: '16px',
          backgroundColor: theme === 'dark' ? '#374151' : '#f3f4f6',
          borderRadius: '8px'
        }}>
          <h4 style={{ 
            color: getColor('textPrimary'),
            margin: '0 0 8px 0',
            fontSize: '16px',
            fontWeight: '600'
          }}>
            {getDocumentTitle()}
          </h4>
          
          {documentData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {documentData.patient_fio && (
                <p style={{ 
                  color: getColor('textSecondary'),
                  margin: 0,
                  fontSize: '14px'
                }}>
                  Пациент: <strong>{documentData.patient_fio}</strong>
                </p>
              )}
              
              {documentData.services && (
                <p style={{ 
                  color: getColor('textSecondary'),
                  margin: 0,
                  fontSize: '14px'
                }}>
                  Услуги: {Array.isArray(documentData.services) 
                    ? documentData.services.join(', ') 
                    : documentData.services}
                </p>
              )}
              
              {documentData.cost && (
                <p style={{ 
                  color: getColor('textSecondary'),
                  margin: 0,
                  fontSize: '14px'
                }}>
                  Сумма: <strong>{documentData.cost.toLocaleString()} ₽</strong>
                </p>
              )}
            </div>
          )}
        </div>

        {/* Выбор принтера */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: '500',
            marginBottom: '12px',
            color: getColor('textPrimary')
          }}>
            Выберите принтер
          </label>

          {isLoading ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '40px',
              color: getColor('textSecondary')
            }}>
              <div className="loading-spinner" style={{ marginRight: '12px' }}></div>
              Загрузка принтеров...
            </div>
          ) : error ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px',
              backgroundColor: theme === 'dark' ? '#451a03' : '#fef2f2',
              border: `1px solid ${theme === 'dark' ? '#dc2626' : '#fecaca'}`,
              borderRadius: '8px',
              color: theme === 'dark' ? '#fca5a5' : '#dc2626'
            }}>
              <AlertCircle size={20} />
              <div>
                <p style={{ margin: '0 0 8px 0', fontWeight: '500' }}>
                  Ошибка загрузки принтеров
                </p>
                <p style={{ margin: 0, fontSize: '14px' }}>
                  {error}
                </p>
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
                    cursor: 'pointer'
                  }}
                >
                  Повторить
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {printers.map((printer) => (
                <div
                  key={printer.id}
                  onClick={() => {
                    if (printer.status === 'online') {
                      setSelectedPrinter(printer.id);
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px',
                    border: `2px solid ${selectedPrinter === printer.id 
                      ? '#3b82f6' 
                      : theme === 'dark' ? '#374151' : '#d1d5db'}`,
                    borderRadius: '8px',
                    backgroundColor: selectedPrinter === printer.id
                      ? theme === 'dark' ? '#1e3a8a' : '#dbeafe'
                      : theme === 'dark' ? '#374151' : 'white',
                    cursor: printer.status === 'online' ? 'pointer' : 'not-allowed',
                    opacity: printer.status === 'online' ? 1 : 0.6,
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Радио кнопка */}
                  <div style={{
                    width: '16px',
                    height: '16px',
                    borderRadius: '50%',
                    border: `2px solid ${selectedPrinter === printer.id ? '#3b82f6' : '#9ca3af'}`,
                    backgroundColor: selectedPrinter === printer.id ? '#3b82f6' : 'transparent',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}>
                    {selectedPrinter === printer.id && (
                      <div style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: 'white'
                      }} />
                    )}
                  </div>

                  {/* Иконка принтера */}
                  <Printer size={20} style={{ 
                    color: getColor('textSecondary'),
                    flexShrink: 0
                  }} />

                  {/* Информация о принтере */}
                  <div style={{ flex: 1 }}>
                    <div style={{
                      color: getColor('textPrimary'),
                      fontSize: '14px',
                      fontWeight: '500'
                    }}>
                      {printer.name}
                    </div>
                    <div style={{
                      color: getColor('textSecondary'),
                      fontSize: '12px',
                      marginTop: '2px'
                    }}>
                      {printer.type === 'thermal' ? 'Термопринтер' : 'Лазерный принтер'}
                    </div>
                  </div>

                  {/* Статус */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                    fontWeight: '500',
                    color: printer.status === 'online' ? '#10b981' : '#ef4444'
                  }}>
                    {printer.status === 'online' ? (
                      <>
                        <Wifi size={14} />
                        Онлайн
                      </>
                    ) : (
                      <>
                        <WifiOff size={14} />
                        Офлайн
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {printers.length === 0 && !isLoading && !error && (
            <div style={{
              textAlign: 'center',
              padding: '40px',
              color: getColor('textSecondary')
            }}>
              <Printer size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <p style={{ margin: 0 }}>Принтеры не найдены</p>
            </div>
          )}
        </div>
      </div>
    </ModernDialog>
  );
};

export default PrintDialog;
