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
import { Card, Button, Badge } from '../../design-system/components';

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

  const loadPrinters = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/print/printers', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
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
      console.error('Ошибка загрузки принтеров:', err);
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
      const response = await fetch(`/api/v1/print/templates/preview`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
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
      console.error('Ошибка предварительного просмотра:', err);
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
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center">
            <Printer size={24} className="mr-3 text-blue-600" />
            <h2 className="text-xl font-semibold">Печать документа</h2>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>

        {/* Контент */}
        <div className="flex flex-col lg:flex-row max-h-[calc(90vh-120px)]">
          {/* Левая панель - настройки печати */}
          <div className="lg:w-1/3 p-6 border-r border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-medium mb-4">Настройки печати</h3>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                <AlertCircle size={16} className="inline mr-2" />
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
                      className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                        selectedPrinter?.id === printer.id
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
                    // Предварительный просмотр для PDF
                    <div 
                      className="prose max-w-none"
                      dangerouslySetInnerHTML={{ __html: preview }}
                    />
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <Eye size={48} className="mx-auto mb-4 opacity-50" />
                    <p>Нажмите "Предварительный просмотр"<br/>для отображения документа</p>
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
