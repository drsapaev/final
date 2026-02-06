import React, { useState, useEffect } from 'react';
import {
  X,
  Printer,
  Settings,
  Eye,
  Download,
  AlertCircle,
  CheckCircle,
  RefreshCw
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';
import { tokenManager } from '../../utils/tokenManager';
import logger from '../../utils/logger';
import { createMarkup } from '../../utils/sanitizer';
/**
 * Диалог печати с выбором принтера и предварительным просмотром
 * Основа: passport.md стр. 1925-2063
 */
const PrintDialog = ({
  isOpen,
  onClose,
  documentType,
  documentData,
  onPrint
}) => {
  const [printers, setPrinters] = useState([]);
  const [selectedPrinter, setSelectedPrinter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      loadPrinters();
    }
  }, [isOpen]);

  const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';

  const loadPrinters = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/v1/print/printers`, {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const data = await response.json();
        setPrinters(data.printers);

        // Выбираем принтер по умолчанию
        const defaultPrinter = data.printers.find(p => p.is_default);
        if (defaultPrinter) {
          setSelectedPrinter(defaultPrinter);
        }
      }
    } catch (err) {
      logger.error('Ошибка загрузки принтеров:', err);
      setError('Ошибка загрузки принтеров');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!selectedPrinter) return;

    try {
      setLoading(true);

      // Получаем шаблон для предварительного просмотра
      const response = await fetch(`${API_BASE}/api/v1/print/templates/preview`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          document_type: documentType,
          printer_id: selectedPrinter.id,
          data: documentData
        })
      });

      if (response.ok) {
        const data = await response.json();
        setPreview(data.rendered_content);
      }
    } catch (err) {
      logger.error('Ошибка предварительного просмотра:', err);
      setError('Ошибка предварительного просмотра');
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = async () => {
    if (!selectedPrinter || !onPrint) return;

    try {
      setLoading(true);
      await onPrint(selectedPrinter.name);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      online: { variant: 'success', label: 'Онлайн' },
      offline: { variant: 'error', label: 'Офлайн' },
      disabled: { variant: 'warning', label: 'Отключен' },
      error: { variant: 'error', label: 'Ошибка' }
    };

    const config = statusConfig[status.status] || { variant: 'default', label: status.status };

    return (
      <Badge variant={config.variant} size="sm">
        {config.label}
      </Badge>
    );
  };

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 99999
    }}>
      <div style={{
        backgroundColor: 'white',
        borderRadius: '8px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        maxWidth: '56rem',
        width: '100%',
        margin: '0 1rem',
        maxHeight: '90vh',
        overflow: 'hidden'
      }}>
        {/* Заголовок */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '24px',
          borderBottom: '1px solid #e5e7eb'
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <Printer size={24} style={{ marginRight: '12px', color: '#2563eb' }} />
            <h2 style={{ fontSize: '20px', fontWeight: '600', margin: 0 }}>Печать документа</h2>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>

        {/* Контент */}
        <div style={{
          display: 'flex',
          flexDirection: 'row',
          maxHeight: 'calc(90vh - 120px)'
        }}>
          {/* Левая панель - настройки печати */}
          <div style={{
            width: '33.333333%',
            padding: '24px',
            borderRight: '1px solid #e5e7eb'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: '500', marginBottom: '16px' }}>Настройки печати</h3>

            {error && (
              <div style={{
                marginBottom: '16px',
                padding: '12px',
                backgroundColor: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                color: '#b91c1c',
                fontSize: '14px'
              }}>
                <AlertCircle size={16} style={{ display: 'inline', marginRight: '8px' }} />
                {error}
              </div>
            )}

            {/* Выбор принтера */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Принтер:
              </label>

              {loading && printers.length === 0 ? (
                <div className="flex items-center text-gray-500">
                  <RefreshCw size={16} className="animate-spin mr-2" />
                  Загрузка принтеров...
                </div>
              ) : (
                <div className="space-y-2">
                  {printers.map(printer => (
                    <div
                      key={printer.id}
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${selectedPrinter?.id === printer.id
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'
                        }`}
                      onClick={() => setSelectedPrinter(printer)}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{printer.display_name}</div>
                          <div className="text-sm text-gray-500">
                            {printer.printer_type} • {printer.connection_type}
                          </div>
                        </div>
                        {getStatusBadge(printer.status)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Информация о документе */}
            <div className="mb-6">
              <h4 className="font-medium mb-2">Тип документа:</h4>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {documentType === 'ticket' && 'Талон очереди'}
                {documentType === 'prescription' && 'Медицинский рецепт'}
                {documentType === 'certificate' && 'Медицинская справка'}
                {documentType === 'payment_receipt' && 'Чек об оплате'}
                {documentType === 'lab_results' && 'Результаты анализов'}
              </div>
            </div>

            {/* Действия */}
            <div className="space-y-3">
              <Button
                variant="outline"
                onClick={handlePreview}
                disabled={!selectedPrinter || loading}
                className="w-full"
              >
                <Eye size={16} className="mr-2" />
                Предварительный просмотр
              </Button>

              <Button
                onClick={handlePrint}
                disabled={!selectedPrinter || loading}
                className="w-full"
              >
                {loading ? (
                  <RefreshCw size={16} className="animate-spin mr-2" />
                ) : (
                  <Printer size={16} className="mr-2" />
                )}
                Печать
              </Button>
            </div>
          </div>

          {/* Правая панель - предварительный просмотр */}
          <div className="lg:w-2/3 p-6">
            <h3 className="text-lg font-medium mb-4">Предварительный просмотр</h3>

            <div className="border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 h-full min-h-[400px] overflow-auto">
              {preview ? (
                <div className="p-4">
                  {selectedPrinter?.printer_type === 'ESC/POS' ? (
                    // Предварительный просмотр для ESC/POS
                    <pre className="font-mono text-xs whitespace-pre-wrap bg-black text-green-400 p-4 rounded">
                      {preview}
                    </pre>
                  ) : (
                    // Предварительный просмотр для PDF (с XSS защитой)
                    <div
                      className="prose max-w-none"
                      {...createMarkup(preview)}
                    />
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <Eye size={48} className="mx-auto mb-4 opacity-50" />
                    <p>Нажмите "Предварительный просмотр"<br />для отображения документа</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Нижняя панель */}
        <div className="flex items-center justify-between p-6 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="text-sm text-gray-500">
            {selectedPrinter && (
              <>Выбран: {selectedPrinter.display_name} ({selectedPrinter.printer_type})</>
            )}
          </div>

          <div className="flex space-x-3">
            <Button variant="outline" onClick={onClose}>
              Отменить
            </Button>
            <Button
              onClick={handlePrint}
              disabled={!selectedPrinter || loading}
            >
              {loading ? 'Печать...' : 'Печать'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PrintDialog;

