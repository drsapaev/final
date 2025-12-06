import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Badge
} from '../components/ui/macos';
import { CheckCircle as CheckIcon, Download as DownloadIcon, Home as HomeIcon, Receipt as ReceiptIcon, Printer as PrintIcon, Share as ShareIcon } from 'lucide-react';

// API клиент
import { api as apiClient } from '../api/client';

import logger from '../utils/logger';
const PaymentSuccess = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  // Состояния
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [paymentData, setPaymentData] = useState(null);
  const [receiptUrl, setReceiptUrl] = useState(null);

  // Получаем параметры из URL
  const paymentId = searchParams.get('payment_id');
  const transactionId = searchParams.get('transaction_id');
  const status = searchParams.get('status');

  useEffect(() => {
    if (paymentId) {
      loadPaymentDetails();
    } else {
      setError('Не указан ID платежа');
      setLoading(false);
    }
  }, [paymentId]);

  const loadPaymentDetails = async () => {
    try {
      setLoading(true);
      
      const response = await apiClient.get(`/payments/${paymentId}`);
      
      if (response.data) {
        setPaymentData(response.data);
        
        // Если платеж успешен, генерируем квитанцию
        if (response.data.status === 'completed') {
          generateReceipt();
        }
      } else {
        setError('Данные платежа не найдены');
      }
    } catch (err) {
      logger.error('Ошибка загрузки платежа:', err);
      setError('Не удалось загрузить информацию о платеже');
    } finally {
      setLoading(false);
    }
  };

  const generateReceipt = async () => {
    try {
      const response = await apiClient.post(`/payments/${paymentId}/receipt`, {
        format: 'pdf'
      });
      
      if (response.data?.receipt_url) {
        setReceiptUrl(response.data.receipt_url);
      }
    } catch (err) {
      logger.warn('Не удалось сгенерировать квитанцию:', err);
    }
  };

  const downloadReceipt = () => {
    if (receiptUrl) {
      window.open(receiptUrl, '_blank');
    } else {
      // Генерируем простую квитанцию
      const receiptContent = generateSimpleReceipt();
      const blob = new Blob([receiptContent], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `receipt_${paymentId}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    }
  };

  const generateSimpleReceipt = () => {
    if (!paymentData) return '';
    
    return `
КВИТАНЦИЯ ОБ ОПЛАТЕ
===================

Номер платежа: ${paymentId}
Дата: ${new Date(paymentData.created_at).toLocaleString('ru-RU')}
Сумма: ${formatAmount(paymentData.amount, paymentData.currency)}
Провайдер: ${getProviderName(paymentData.provider)}
Статус: ${getStatusText(paymentData.status)}

Описание: ${paymentData.description || 'Оплата медицинских услуг'}

Спасибо за использование наших услуг!
    `.trim();
  };

  const printReceipt = () => {
    const receiptContent = generateSimpleReceipt();
    const printWindow = window.open('', '_blank');
    printWindow.document.write(`
      <html>
        <head>
          <title>Квитанция ${paymentId}</title>
          <style>
            body { font-family: monospace; margin: 20px; }
            pre { white-space: pre-wrap; }
          </style>
        </head>
        <body>
          <pre>${receiptContent}</pre>
        </body>
      </html>
    `);
    printWindow.document.close();
    printWindow.print();
  };

  const shareReceipt = async () => {
    if (navigator.share && paymentData) {
      try {
        await navigator.share({
          title: `Квитанция об оплате ${paymentId}`,
          text: `Оплата на сумму ${formatAmount(paymentData.amount, paymentData.currency)} успешно завершена`,
          url: window.location.href
        });
      } catch (err) {
        logger.log('Ошибка при шаринге:', err);
      }
    } else {
      // Fallback - копируем в буфер обмена
      navigator.clipboard.writeText(window.location.href);
      alert('Ссылка скопирована в буфер обмена');
    }
  };

  const formatAmount = (amount, currency) => {
    const numAmount = parseFloat(amount);
    if (currency === 'UZS') {
      return `${(numAmount / 100).toLocaleString('ru-RU')} сум`;
    } else if (currency === 'KZT') {
      return `${(numAmount / 100).toLocaleString('ru-RU')} тенге`;
    } else {
      return `${numAmount} ${currency}`;
    }
  };

  const getProviderName = (provider) => {
    const names = {
      click: 'Click',
      payme: 'Payme',
      kaspi: 'Kaspi Pay'
    };
    return names[provider] || provider;
  };

  const getStatusText = (status) => {
    const texts = {
      pending: 'Ожидает',
      processing: 'Обработка',
      completed: 'Завершен',
      failed: 'Неудачно',
      cancelled: 'Отменен'
    };
    return texts[status] || status;
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: 'warning',
      processing: 'info',
      completed: 'success',
      failed: 'error',
      cancelled: 'default'
    };
    return colors[status] || 'default';
  };

  if (loading) {
    return (
      <Box 
        display="flex" 
        justifyContent="center" 
        alignItems="center" 
        minHeight="60vh"
      >
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box maxWidth="md" mx="auto" mt={4} px={2}>
        <Card>
          <CardContent>
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
            <Button 
              variant="contained" 
              startIcon={<HomeIcon />}
              onClick={() => navigate('/')}
            >
              На главную
            </Button>
          </CardContent>
        </Card>
      </Box>
    );
  }

  const isSuccess = paymentData?.status === 'completed';

  return (
    <Box maxWidth="md" mx="auto" mt={4} px={2}>
      {/* Заголовок результата */}
      <Card elevation={3} sx={{ mb: 3 }}>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          {isSuccess ? (
            <>
              <CheckIcon 
                sx={{ 
                  fontSize: 80, 
                  color: 'success.main', 
                  mb: 2 
                }} 
              />
              <Typography variant="h4" color="success.main" gutterBottom>
                Оплата успешно завершена!
              </Typography>
              <Typography variant="h6" color="textSecondary">
                Спасибо за использование наших услуг
              </Typography>
            </>
          ) : (
            <>
              <Typography variant="h4" color="warning.main" gutterBottom>
                Статус платежа: {getStatusText(paymentData?.status)}
              </Typography>
              <Typography variant="body1" color="textSecondary">
                Информация о вашем платеже
              </Typography>
            </>
          )}
        </CardContent>
      </Card>

      {/* Детали платежа */}
      {paymentData && (
        <Card elevation={2} sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
              <ReceiptIcon sx={{ mr: 1 }} />
              Детали платежа
            </Typography>
            
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12} sm={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="textSecondary">
                    Номер платежа
                  </Typography>
                  <Typography variant="h6" fontWeight="bold">
                    #{paymentId}
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="textSecondary">
                    Сумма
                  </Typography>
                  <Typography variant="h6" fontWeight="bold" color="primary">
                    {formatAmount(paymentData.amount, paymentData.currency)}
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="textSecondary">
                    Способ оплаты
                  </Typography>
                  <Typography variant="body1">
                    {getProviderName(paymentData.provider)}
                  </Typography>
                </Paper>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="textSecondary">
                    Статус
                  </Typography>
                  <Chip 
                    label={getStatusText(paymentData.status)}
                    color={getStatusColor(paymentData.status)}
                    size="small"
                  />
                </Paper>
              </Grid>
              
              <Grid item xs={12}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                  <Typography variant="body2" color="textSecondary">
                    Дата и время
                  </Typography>
                  <Typography variant="body1">
                    {new Date(paymentData.created_at).toLocaleString('ru-RU')}
                  </Typography>
                </Paper>
              </Grid>
              
              {paymentData.description && (
                <Grid item xs={12}>
                  <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="body2" color="textSecondary">
                      Описание
                    </Typography>
                    <Typography variant="body1">
                      {paymentData.description}
                    </Typography>
                  </Paper>
                </Grid>
              )}
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Действия */}
      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Действия
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="contained"
                fullWidth
                startIcon={<DownloadIcon />}
                onClick={downloadReceipt}
                disabled={!paymentData}
              >
                Скачать квитанцию
              </Button>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<PrintIcon />}
                onClick={printReceipt}
                disabled={!paymentData}
              >
                Печать
              </Button>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<ShareIcon />}
                onClick={shareReceipt}
                disabled={!paymentData}
              >
                Поделиться
              </Button>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<HomeIcon />}
                onClick={() => navigate('/')}
              >
                На главную
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Дополнительная информация */}
      <Box mt={4} textAlign="center">
        <Typography variant="body2" color="textSecondary">
          При возникновении вопросов обратитесь в службу поддержки
        </Typography>
      </Box>
    </Box>
  );
};

export default PaymentSuccess;
