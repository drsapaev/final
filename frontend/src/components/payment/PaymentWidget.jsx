/**
 * PaymentWidget - Виджет для обработки платежей
 * Поддерживает провайдеры: Click, Payme, Kaspi
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Badge,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
} from '../ui/macos';

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
import { getErrorMessage } from '../../utils/errorHandler';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';

const dividerStyle = {
  height: 1,
  marginBottom: 24,
  background: 'var(--mac-border)'
};

const providerOptionStyle = {
  display: 'flex',
  alignItems: 'center',
  width: '100%',
  gap: 8
};

const providerNameStyle = {
  textTransform: 'capitalize',
  flex: '1 1 auto',
  minWidth: 0
};

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
  const isLocalSmokeMode =
    import.meta.env.DEV ||
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1';

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
      setError(getErrorMessage(err, 'Не удалось загрузить способы оплаты. Проверьте соединение и попробуйте снова.'));
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
        authHeader: apiClient.defaults.headers.common['Authorization'] ? '[redacted]' : 'none',
        authHeaderLength: apiClient.defaults.headers.common['Authorization']?.length || 0,
        paymentRequest
      });

      const response = await apiClient.post(endpoint, paymentRequest);

      if (response.data?.success) {
        const nextPaymentData = {
          ...response.data,
          provider: selectedProvider
        };
        setPaymentData(nextPaymentData);
        setPaymentStatus('initialized');

        // Если есть URL для оплаты, открываем его
        if (response.data.payment_url) {
          if (isLocalSmokeMode) {
            logger.info('[FIX:CASH-02] Local smoke mode: auto-confirming online payment', {
              paymentId: response.data.payment_id,
              provider: selectedProvider
            });

            const confirmResponse = await apiClient.post(
              `/cashier/payments/${response.data.payment_id}/confirm`
            );

            const confirmedPaymentData = {
              ...nextPaymentData,
              ...confirmResponse.data,
              payment_id: response.data.payment_id,
              provider: selectedProvider,
              status: confirmResponse.data?.status ?? null,
              confirmed: true
            };

            setPaymentData(confirmedPaymentData);
            const confirmedStatus = String(confirmResponse.data?.status || '');
            setPaymentStatus(confirmedStatus || 'initialized');

            if (confirmedStatus === 'paid' && onSuccess) {
              onSuccess(confirmedPaymentData);
            }

            return;
          }

          window.open(response.data.payment_url, '_blank');
          setPaymentStatus('redirected');
        }
      } else {
        throw new Error(
          getErrorMessage(
            response.data?.error_message || '',
            'Не удалось инициализировать платёж. Проверьте соединение и попробуйте снова.'
          )
        );
      }
    } catch (err) {
      logger.error('Ошибка инициализации платежа:', err);
      const errorMessage = getErrorMessage(err, 'Не удалось обработать платёж. Проверьте соединение и попробуйте снова.');
      setError(errorMessage);
      setPaymentStatus('failed');

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
      const response = await apiClient.get(`/payments/${paymentData.payment_id}`);

      if (response.data?.status) {
        // Keep exact backend payment status; frontend must not collapse provider/status aliases.
        const nextStatus = String(response.data.status);
        setPaymentStatus(nextStatus);

        if (nextStatus === 'paid' && onSuccess) {
          onSuccess({
            ...paymentData,
            ...response.data,
            status: response.data.status
          });
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
      case 'processing':
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

      case 'paid':
        return (
          <Alert severity="success" icon={<CheckIcon />}>
            Платеж успешно завершен!
          </Alert>);

      case 'failed':
      case 'cancelled':
      case 'canceled':
        return (
          <Alert severity="error" icon={<ErrorIcon />}>
            Платеж не удался. Попробуйте еще раз.
          </Alert>);

      case 'refunded':
      case 'void':
        return (
          <Alert severity="warning" icon={<ErrorIcon />}>
            Status: {paymentStatus}
          </Alert>);

      default:
        return paymentStatus ? (
          <Alert severity="info" icon={<InfoIcon />}>
            Status: {paymentStatus}
          </Alert>) : null;
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

        <div style={dividerStyle} />

        {/* Выбор провайдера */}
        <Select
          id="payment-provider"
          label="Способ оплаты"
          value={selectedProvider}
          onChange={(value) => setSelectedProvider(value)}
          disabled={loading}
          style={{ marginBottom: 24 }}
          options={providers.map((provider) => ({
            value: provider.code,
            label: (
              <span style={providerOptionStyle}>
                {providerIcons[provider.code]}
                <span style={providerNameStyle}>
                  {provider.name}
                </span>
                <Badge
                  size="small"
                  variant="outline"
                  style={{
                    marginLeft: 'auto',
                    backgroundColor: providerColors[provider.code] + '20',
                    color: providerColors[provider.code]
                  }}
                >
                  {provider.supported_currencies.join(', ')}
                </Badge>
              </span>
            )
          }))}
        />

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
            disabled={loading || !selectedProvider || paymentStatus === 'paid'}>
            
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
            <Box style={{ padding: 16, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 4, marginBottom: 16 }}>
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


PaymentWidget.propTypes = {
  ...(PaymentWidget.propTypes || {}),
  amount: PropTypes.any,
  currency: PropTypes.any,
  description: PropTypes.any,
  onCancel: PropTypes.any,
  onError: PropTypes.any,
  onSuccess: PropTypes.any,
  visitId: PropTypes.any,
};

export default PaymentWidget;
