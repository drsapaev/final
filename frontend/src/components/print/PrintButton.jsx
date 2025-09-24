import React, { useState } from 'react';
import { Printer, Download, FileText, Receipt, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { Button } from '../../design-system/components';

/**
 * Компонент кнопки печати с поддержкой разных типов документов
 * Основа: detail.md стр. 3721-3888
 */
const PrintButton = ({
  documentType,
  documentData,
  printerName = null,
  variant = 'outline',
  size = 'sm',
  children,
  onPrintStart,
  onPrintComplete,
  onPrintError,
  className = ''
}) => {
  const [printing, setPrinting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  // Иконки для разных типов документов
  const documentIcons = {
    ticket: Receipt,
    prescription: FileText,
    certificate: FileText,
    payment_receipt: Receipt,
    lab_results: FileText
  };

  // Названия документов
  const documentNames = {
    ticket: 'Талон',
    prescription: 'Рецепт',
    certificate: 'Справка',
    payment_receipt: 'Чек',
    lab_results: 'Результаты анализов'
  };

  const IconComponent = documentIcons[documentType] || Printer;
  const documentName = documentNames[documentType] || 'Документ';

  const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';

  const handlePrint = async () => {
    try {
      setPrinting(true);
      setLastResult(null);
      
      if (onPrintStart) onPrintStart();

      // Определяем API endpoint в зависимости от типа документа
      const endpoints = {
        ticket: '/api/v1/print/ticket',
        prescription: '/api/v1/print/prescription',
        certificate: '/api/v1/print/certificate',
        payment_receipt: '/api/v1/print/receipt',
        lab_results: '/api/v1/print/lab-results'
      };

      const endpoint = `${API_BASE}${endpoints[documentType]}`;
      if (!endpoint) {
        throw new Error(`Неподдерживаемый тип документа: ${documentType}`);
      }

      // Подготавливаем данные для отправки
      const printData = {
        ...documentData,
        printer_name: printerName
      };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(printData)
      });

      const result = await response.json();

      if (response.ok && result.success) {
        setLastResult({ type: 'success', message: result.message });
        if (onPrintComplete) onPrintComplete(result);
      } else {
        const errorMessage = result.error || result.detail || 'Ошибка печати';
        setLastResult({ type: 'error', message: errorMessage });
        if (onPrintError) onPrintError(new Error(errorMessage));
      }

    } catch (error) {
      console.error('Ошибка печати:', error);
      const errorMessage = error.message || 'Ошибка печати';
      setLastResult({ type: 'error', message: errorMessage });
      if (onPrintError) onPrintError(error);
    } finally {
      setPrinting(false);
    }
  };

  const buttonContent = children || (
    <>
      {printing ? (
        <Loader size={16} className="animate-spin mr-1" />
      ) : (
        <IconComponent size={16} className="mr-1" />
      )}
      {printing ? 'Печать...' : `Печать ${documentName.toLowerCase()}`}
    </>
  );

  return (
    <div className={`relative ${className}`}>
      <Button
        variant={variant}
        size={size}
        onClick={handlePrint}
        disabled={printing || !documentData}
        className="relative"
      >
        {buttonContent}
      </Button>

      {/* Результат печати */}
      {lastResult && (
        <div 
          className={`absolute top-full left-0 right-0 mt-2 p-2 rounded text-xs z-50 ${
            lastResult.type === 'success' 
              ? 'bg-green-100 text-green-700 border border-green-200' 
              : 'bg-red-100 text-red-700 border border-red-200'
          }`}
        >
          <div className="flex items-center">
            {lastResult.type === 'success' ? (
              <CheckCircle size={12} className="mr-1" />
            ) : (
              <AlertCircle size={12} className="mr-1" />
            )}
            {lastResult.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default PrintButton;
