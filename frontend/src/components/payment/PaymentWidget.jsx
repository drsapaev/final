/**
 * PaymentWidget - Виджет для обработки платежей
 * Поддерживает провайдеры: Click, Payme, Kaspi
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions } from

'../ui/macos';

// MUI imports - using MUI Select for compatibility with FormControl/MenuItem
import {
  Divider,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip } from
'@mui/material';

import {
  CreditCard,
  Banknote,
  Building,
  CheckCircle,
  XCircle,
  Info } from
'lucide-react';

// API клиент
import { api as apiClient, getToken } from '../../api/client';
import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';

const PaymentWidget = ({
  visitId,
  amount,
  currency = 'UZS',
  description = 'Оплата медицинских услуг',
  onSuccess,
  onError,
  onCancel
}) => {
  const theme = useTheme();

  // Icon aliases
  const CreditCardIcon = CreditCard;
  const PaymentIcon = Banknote;
  const BankIcon = Building;
  const CheckIcon = CheckCircle;
  const ErrorIcon = XCircle;
  const InfoIcon = Info;

  // Состояния
  const [providers, setProviders] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [loading, setLoading] = useState(false);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [error, setError] = useState(null);
  const [paymentData, setPaymentData] = useState(null);
  const [paymentStatus, setPaymentStatus] = useState('pending');
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  // Иконки провайдеров
  const providerIcons = {
    click: <CreditCardIcon style={{ color: '#00AAFF' }} />,
    payme: <PaymentIcon style={{ color: '#00C851' }} />,
    kaspi: <BankIcon style={{ color: '#FF6B35' }} />
  };

  // Цвета провайдеров
  const providerColors = {
    click: '#00AAFF',
    payme: '#00C851',
    kaspi: '#FF6B35'
  };

  const loadProviders = useCallback(async () => {
    try {
      setProvidersLoading(true);
      const response = await apiClient.get('/payments/providers');

      if (response.data?.providers) {
        // Фильтруем активные провайдеры по валюте
        const availableProviders = response.data.providers.filter(
          (provider) => provider.is_active &&
          provider.supported_currencies.includes(currency)
        );
        setProviders(availableProviders);

        // Автовыбор первого доступного провайдера
        if (availableProviders.length > 0) {
          setSelectedProvider(availableProviders[0].code);
        }
      }
    } catch (err) {
      logger.error('Ошибка загрузки провайдеров:', err);
      setError('Не удалось загрузить способы оплаты');
    } finally {
      setProvidersLoading(false);
    }
  }, [currency]);

  // Загрузка доступных провайдеров
  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  // Инициализация платежа
  const initializePayment = async () => {
    if (!selectedProvider || !visitId || !amount) {
      setError('Не все данные для платежа заполнены');
      return;
    }

    // Проверяем наличие токена авторизации
    const token = getToken();
    logger.log('🔑 Проверяем токен для платежа:', {
      hasToken: !!token,
      tokenLength: token ? token.length : 0,
      tokenStart: token ? token.substring(0, 20) + '...' : 'null'
    });

    if (!token) {
      setError('Для оплаты требуется авторизация. Пожалуйста, войдите в систему.');
      if (onError) {
        onError('Требуется авторизация');
      }
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const paymentRequest = {
        visit_id: visitId,
        provider: selectedProvider,
        amount: parseFloat(amount),
        currency: currency,
        description: description,
        return_url: `${window.location.origin}/payment/success`,
        cancel_url: `${window.location.origin}/payment/cancel`
      };

      // Используем тестовый endpoint если токен демо
      const currentToken = getToken();
      const isTestToken = currentToken === 'demo_token_for_ui_testing';
      const endpoint = isTestToken ? '/payments/test-init' : '/payments/init';

      logger.log('📤 Отправляем запрос платежа:', {
        endpoint,
        isTestToken,
        hasAuthHeader: !!apiClient.defaults.headers.common['Authorization'],
        authHeader: apiClient.defaults.headers.common['Authorization'] ?
        apiClient.defaults.headers.common['Authorization'].substring(0, 30) + '...' : 'none',
        paymentRequest
      });

      const response = await apiClient.post(endpoint, paymentRequest);

      if (response.data?.success) {
        setPaymentData(response.data);
        setPaymentStatus('initialized');

        // Если есть URL для оплаты, открываем его
        if (response.data.payment_url) {
          window.open(response.data.payment_url, '_blank');
          setPaymentStatus('redirected');
        }

        // Уведомляем родительский компонент
        if (onSuccess) {
          onSuccess(response.data);
        }
      } else {
        throw new Error(response.data?.error_message || 'Ошибка инициализации платежа');
      }
    } catch (err) {
      logger.error('Ошибка инициализации платежа:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка обработки платежа';
      setError(errorMessage);

      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  // Проверка статуса платежа
  const checkPaymentStatus = async () => {
    if (!paymentData?.payment_id) return;

    try {
      const response = await apiClient.get(`/payments/${paymentData.payment_id}/status`);

      if (response.data?.status) {
        setPaymentStatus(response.data.status);

        if (response.data.status === 'completed' && onSuccess) {
          onSuccess(response.data);
        }
      }
    } catch (err) {
      logger.error('Ошибка проверки статуса:', err);
    }
  };

  // Отмена платежа
  const cancelPayment = () => {
    setPaymentData(null);
    setPaymentStatus('pending');
    setError(null);

    if (onCancel) {
      onCancel();
    }
  };

  // Подтверждение платежа
  const confirmPayment = () => {
    setShowConfirmDialog(true);
  };

  // Форматирование суммы
  const formatAmount = (amountValue, currencyCode) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: currencyCode === 'UZS' ? 'UZS' : currencyCode === 'KZT' ? 'KZT' : 'USD',
      minimumFractionDigits: 0
    }).format(amountValue);
  };

  // Рендер статуса платежа
  const renderPaymentStatus = () => {
    switch (paymentStatus) {
      case 'pending':
        return (
          <Alert severity="info" icon={<InfoIcon />}>
            Выберите способ оплаты и нажмите «Оплатить»
          </Alert>);

      case 'initialized':
        return (
          <Alert severity="success" icon={<CheckIcon />}>
            Платеж инициализирован. ID: {paymentData?.payment_id}
          </Alert>);

      case 'redirected':
        return (
          <Alert severity="info" icon={<InfoIcon />}>
            Перенаправление на страницу оплаты...
            <Button
              size="small"
              onClick={checkPaymentStatus}
              style={{ marginLeft: 16 }}>
              
              Проверить статус
            </Button>
          </Alert>);

      case 'completed':
        return (
          <Alert severity="success" icon={<CheckIcon />}>
            Платеж успешно завершен!
          </Alert>);

      case 'failed':
        return (
          <Alert severity="error" icon={<ErrorIcon />}>
            Платеж не удался. Попробуйте еще раз.
          </Alert>);

      default:
        return null;
    }
  };

  if (providersLoading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" style={{ padding: 24 }}>
            <CircularProgress />
            <Typography variant="body1" style={{ marginLeft: 16 }}>
              Загрузка способов оплаты...
            </Typography>
          </Box>
        </CardContent>
      </Card>);

  }

  if (providers.length === 0) {
    return (
      <Card>
        <CardContent>
          <Alert severity="warning">
            Нет доступных способов оплаты для валюты {currency}
          </Alert>
        </CardContent>
      </Card>);

  }

  return (
    <Card elevation={3}>
      <CardContent>
        {/* Заголовок */}
        <Box display="flex" alignItems="center" style={{ marginBottom: 24 }}>
          <PaymentIcon style={{ marginRight: 8, color: theme?.palette?.primary?.main || '#007AFF' }} />
          <Typography variant="h6" component="h2">
            Оплата услуг
          </Typography>
        </Box>

        {/* Информация о платеже */}
        <Box style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ flex: '1 1 200px' }}>
              <Typography variant="body2" color="textSecondary">
                Сумма к оплате:
              </Typography>
              <Typography variant="h5" color="primary" style={{ fontWeight: 'bold' }}>
                {formatAmount(amount, currency)}
              </Typography>
            </div>
            <div style={{ flex: '1 1 200px' }}>
              <Typography variant="body2" color="textSecondary">
                Описание:
              </Typography>
              <Typography variant="body1">
                {description}
              </Typography>
            </div>
          </div>
        </Box>

        <Divider style={{ marginBottom: 24 }} />

        {/* Выбор провайдера */}
        <FormControl fullWidth style={{ marginBottom: 24 }}>
          <InputLabel id="payment-provider-label">Способ оплаты</InputLabel>
          <Select
            labelId="payment-provider-label"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            label="Способ оплаты"
            disabled={loading}>
            
            {providers.map((provider) =>
            <MenuItem key={provider.code} value={provider.code}>
                <Box display="flex" alignItems="center">
                  {providerIcons[provider.code]}
                  <Typography style={{ marginLeft: 8, textTransform: 'capitalize' }}>
                    {provider.name}
                  </Typography>
                  <Chip
                  label={provider.supported_currencies.join(', ')}
                  size="small"
                  style={{
                    marginLeft: 'auto',
                    backgroundColor: providerColors[provider.code] + '20',
                    color: providerColors[provider.code]
                  }} />
                
                </Box>
              </MenuItem>
            )}
          </Select>
        </FormControl>

        {/* Статус платежа */}
        {renderPaymentStatus()}

        {/* Ошибки */}
        {error &&
        <Alert severity="error" style={{ marginBottom: 24 }}>
            {error}
          </Alert>
        }

        {/* Кнопки действий */}
        <Box display="flex" style={{ gap: 16, marginTop: 24 }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            fullWidth
            onClick={confirmPayment}
            disabled={loading || !selectedProvider || paymentStatus === 'completed'}>
            
            {loading ?
            <>
                <CircularProgress size={20} style={{ marginRight: 8 }} />
                Обработка...
              </> :

            `Оплатить ${formatAmount(amount, currency)}`
            }
          </Button>

          {paymentStatus !== 'pending' &&
          <Button
            variant="outlined"
            color="secondary"
            size="large"
            onClick={cancelPayment}
            disabled={loading}>
            
              Отмена
            </Button>
          }
        </Box>

        {/* Диалог подтверждения */}
        <Dialog open={showConfirmDialog} onClose={() => setShowConfirmDialog(false)}>
          <DialogTitle>Подтверждение оплаты</DialogTitle>
          <DialogContent>
            <Typography variant="body1" gutterBottom>
              Вы собираетесь оплатить:
            </Typography>
            <Box style={{ padding: 16, backgroundColor: '#f5f5f5', borderRadius: 4, marginBottom: 16 }}>
              <Typography variant="h6" color="primary">
                {formatAmount(amount, currency)}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                через {providers.find((p) => p.code === selectedProvider)?.name}
              </Typography>
            </Box>
            <Typography variant="body2" color="textSecondary">
              После нажатия «Продолжить» вы будете перенаправлены на страницу оплаты.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowConfirmDialog(false)}>
              Отмена
            </Button>
            <Button
              variant="contained"
              onClick={() => {
                setShowConfirmDialog(false);
                initializePayment();
              }}
              disabled={loading}>
              
              Продолжить
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>);

};

export default PaymentWidget;
