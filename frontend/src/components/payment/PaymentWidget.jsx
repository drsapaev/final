/**
 * PaymentWidget - Виджет для обработки платежей
 * Поддерживает провайдеры: Click, Payme, Kaspi
 */

import { useState, useEffect, useCallback, useRef } from 'react';
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
// UX Audit #4 regression fix: useTheme удалён — theme?.palette?.primary?.main
// заменён на var(--mac-accent-blue) через CSS-класс .pw-header-icon.
import { getErrorMessage } from '../../utils/errorHandler';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import './PaymentWidget.css';

// UX Audit #4 regression fix: dividerStyle, providerOptionStyle, providerNameStyle
// вынесены в CSS-классы .pw-divider, .pw-provider-option, .pw-provider-name.

const PaymentWidget = ({
  visitId,
  amount,
  currency = 'UZS',
  description = 'Оплата медицинских услуг',
  onSuccess,
  onError,
  onCancel
}) => {
  // UX Audit #4 regression fix: useTheme() удалён — больше не нужен.

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

  // HIGH #7 fix: auto-polling for online payment status.
  // Previously the cashier had to click "Проверить статус" manually.
  // Now we poll every 5 seconds for up to 5 minutes (60 attempts),
  // matching the behavior of PaymentClick/PaymentPayMe.
  const MAX_POLLING_ATTEMPTS = 60;
  const POLLING_INTERVAL_MS = 5000;
  const pollingRef = useRef(null);
  const attemptsRef = useRef(0);
  const [pollingAttempts, setPollingAttempts] = useState(0);

  // Иконки провайдеров — UX Audit #4 regression fix: brand colors в CSS-классах.
  const providerIcons = {
    click: <CreditCardIcon className="pw-provider-icon--click" />,
    payme: <PaymentIcon className="pw-provider-icon--payme" />,
    kaspi: <BankIcon className="pw-provider-icon--kaspi" />
  };

  // Цвета провайдеров — оставлены для badge background computation.
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

  // HIGH #7: cleanup polling on unmount.
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, []);

  // HIGH #7: stop polling automatically when payment reaches a terminal state.
  useEffect(() => {
    if (
      paymentStatus === 'paid' ||
      paymentStatus === 'failed' ||
      paymentStatus === 'cancelled' ||
      paymentStatus === 'canceled' ||
      paymentStatus === 'refunded'
    ) {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }
  }, [paymentStatus]);

  const clearPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    attemptsRef.current = 0;
    setPollingAttempts(0);
  }, []);

  const startPolling = useCallback(() => {
    // Don't start if already polling.
    if (pollingRef.current) return;
    attemptsRef.current = 0;
    setPollingAttempts(0);

    pollingRef.current = setInterval(async () => {
      attemptsRef.current += 1;
      setPollingAttempts(attemptsRef.current);
      try {
        await checkPaymentStatus();
      } catch (err) {
        logger.error('Polling error:', err);
      }
      if (attemptsRef.current >= MAX_POLLING_ATTEMPTS) {
        clearPolling();
        setError('Время ожидания оплаты истекло. Проверьте статус платежа вручную.');
        setPaymentStatus('failed');
      }
    }, POLLING_INTERVAL_MS);
  }, [clearPolling]);

  // Инициализация платежа
  const initializePayment = async () => {
    if (!selectedProvider || !visitId || !amount) {
      setError('Не все данные для платежа заполнены');
      return;
    }

    // Проверяем наличие токена авторизации
    const token = getToken();
    logger.log('Checking auth token for payment', {
      hasToken: !!token,
      tokenLength: token ? token.length : 0,
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

      logger.log('Sending payment request', {
        endpoint,
        isTestToken,
        hasAuthHeader: !!apiClient.defaults.headers.common['Authorization'],
        authHeaderLength: apiClient.defaults.headers.common['Authorization']?.length || 0,
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
          // HIGH #7: auto-start polling 10s after redirect (matches
          // PaymentClick/PaymentPayMe UX — gives the user time to land
          // on the provider page before we start pinging).
          setTimeout(() => {
            startPolling();
          }, 10000);
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
    clearPolling();
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
            <div className="pw-provider-option-row">
              <span>Перенаправление на страницу оплаты...</span>
              {pollingRef.current && (
                <span className="pw-provider-option-name">
                  Автоматическая проверка статуса: попытка {pollingAttempts} из {MAX_POLLING_ATTEMPTS}
                </span>
              )}
              <div className="pw-provider-option-badges">
                <Button
                  size="small"
                  onClick={checkPaymentStatus}>
                  Проверить статус
                </Button>
                {pollingRef.current ? (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={clearPolling}>
                    Остановить отслеживание
                  </Button>
                ) : (
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={startPolling}>
                    Начать отслеживание
                  </Button>
                )}
              </div>
            </div>
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
            Статус: {paymentStatus}
          </Alert>);

      default:
        return paymentStatus ? (
          <Alert severity="info" icon={<InfoIcon />}>
            Статус: {paymentStatus}
          </Alert>) : null;
    }
  };

  if (providersLoading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" className="pw-loading-box">
            <CircularProgress />
            <Typography variant="body1" className="pw-loading-text">
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
        <Box display="flex" alignItems="center" className="pw-header-row">
          <PaymentIcon className="pw-header-icon" />
          <Typography variant="h6" component="h2">
            Оплата услуг
          </Typography>
        </Box>

        {/* Информация о платеже */}
        <Box className="pw-payment-info-box">
          <div className="pw-payment-info-row">
            <div className="pw-payment-info-cell">
              <Typography variant="body2" color="textSecondary">
                Сумма к оплате:
              </Typography>
              <Typography variant="h5" color="primary" className="pw-amount-bold">
                {formatAmount(amount, currency)}
              </Typography>
            </div>
            <div className="pw-payment-info-cell">
              <Typography variant="body2" color="textSecondary">
                Описание:
              </Typography>
              <Typography variant="body1">
                {description}
              </Typography>
            </div>
          </div>
        </Box>

        <div className="pw-divider" />

        {/* Выбор провайдера */}
        <Select
          id="payment-provider"
          label="Способ оплаты"
          value={selectedProvider}
          onChange={(value) => setSelectedProvider(value)}
          disabled={loading}
          className="pw-select-margin"
          options={providers.map((provider) => ({
            value: provider.code,
            label: (
              <span className="pw-provider-option">
                {providerIcons[provider.code]}
                <span className="pw-provider-name">
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
        <Alert severity="error" className="pw-error-alert">
            {error}
          </Alert>
        }

        {/* Кнопки действий */}
        <Box display="flex" className="pw-actions-row">
          <Button
            variant="contained"
            color="primary"
            size="large"
            fullWidth
            onClick={confirmPayment}
            disabled={loading || !selectedProvider || paymentStatus === 'paid'}>
            
            {loading ?
            <>
                <CircularProgress size={20} className="pw-submit-spinner" />
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
            <Box className="pw-confirm-amount-box">
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
