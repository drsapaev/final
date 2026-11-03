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
import './PaymentWidget.css';
import { useTranslation } from '../../i18n/useTranslation';

// UX Audit #4 regression fix: dividerStyle, providerOptionStyle, providerNameStyle
// вынесены в CSS-классы .pw-divider, .pw-provider-option, .pw-provider-name.

// Local payment-provider list shape for the picker dropdown. Named
// `PaymentProviderDto` because `PaymentProvider` is a canonical domain type
// in @/types/domain/billing.
interface PaymentProviderDto {
  code: string;
  name: string;
  is_active?: boolean;
  supported_currencies: string[];
}

interface PaymentData {
  payment_id?: string | number;
  payment_url?: string;
  provider?: string;
  status?: string;
  success?: boolean;
  [key: string]: unknown;
}

// CSH-FE-037: statuses that end the payment lifecycle. The polling-budget
// branch must never overwrite one of these observed by the very poll that
// exhausted the attempt count.
const TERMINAL_PAYMENT_STATUSES: readonly string[] = [
  'paid',
  'failed',
  'cancelled',
  'canceled',
  'refunded',
];

// PR-3854 review follow-up: a CONFIRMED terminal status is authoritative —
// nothing may roll it back to a non-terminal observation arriving later.
const isTerminalPaymentStatus = (status: string): boolean =>
  TERMINAL_PAYMENT_STATUSES.includes(status);

const PaymentWidget = ({
  visitId,
  amount,
  currency = 'UZS',
  description,
  onSuccess,
  onError,
  onCancel
}: {
  visitId?: string | number;
  amount?: string | number;
  currency?: string;
  description?: string;
  onSuccess?: (data: unknown) => void;
  onError?: (message: string) => void;
  onCancel?: () => void;
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  // UX Audit #4 regression fix: useTheme() удалён — больше не нужен.
  // i18n: fallback description is resolved at render time so t() is available.
  const effectiveDescription = description ?? t('payment.pay_widg_default_description');

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
  const [providers, setProviders] = useState<PaymentProviderDto[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [loading, setLoading] = useState(false);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // PR-3854 review follow-up: provider-LOAD failures get their own state so
  // they can be rendered in the empty-providers branch (the generic `error`
  // alert only exists in the main card, which is not rendered when the
  // list is empty).
  const [providersError, setProvidersError] = useState<string | null>(null);
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [paymentStatus, setPaymentStatus] = useState('pending');

  // CSH-FE-029: the polling interval is created once per payment and
  // closes over the first-render closure where paymentData is still null —
  // the status GET then never fires. A ref keeps the polling path pointed at
  // the CURRENT payment data regardless of which render created the timer.
  const paymentDataRef = useRef<PaymentData | null>(null);
  useEffect(() => {
    paymentDataRef.current = paymentData;
  }, [paymentData]);

  // CSH-FE-030: the translation wrapper returns a new t identity on
  // every render; keeping t in loadProviders deps made the providers effect
  // refetch in a loop after every state update. tRef gives loadProviders a
  // stable dependency surface ([currency] only).
  const tRef = useRef(t);
  useEffect(() => {
    tRef.current = t;
  });

  // CSH-FE-038: a currency switch can overlap two provider requests; a late
  // stale response (previous currency) must not overwrite the state resolved
  // by the newer one. Every load takes the next sequence number and only the
  // holder of the CURRENT number is allowed to commit state.
  const providersRequestSeqRef = useRef(0);

  // HIGH #7 fix: auto-polling for online payment status.
  // Previously the cashier had to click "Проверить статус" manually.
  // Now we poll every 5 seconds for up to 5 minutes (60 attempts),
  // matching the behavior of PaymentClick/PaymentPayMe.
  const MAX_POLLING_ATTEMPTS = 60;
  const POLLING_INTERVAL_MS = 5000;
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);
  const [pollingAttempts, setPollingAttempts] = useState(0);
  // PR-3854 review follow-up (single-flight): `setInterval(async () => …)` let
  // a slow status GET overlap with the next 5s tick — two concurrent GETs
  // whose responses could then land OUT OF ORDER. While the guard is held,
  // ticks are skipped entirely (no request, no attempt consumed).
  const statusCheckInFlightRef = useRef(false);
  // PR-3854 re-review follow-up (polling session epoch): stopping tracking
  // does NOT cancel the session's already-sent status GET, and restarting
  // tracking force-resets the single-flight guard — when the OLD GET then
  // settled, its `finally` released the lock held by the NEW session's
  // in-flight GET and its budget branch read the new session's attempt
  // counter, so the next tick stacked a concurrent request (single-flight
  // broken again after a stop → start cycle). Every polling session (and
  // every stop) now takes a monotonically increasing epoch; only the
  // CURRENT epoch may release the guard, consume the budget or clear the
  // interval — a superseded session's continuation is fully inert.
  const pollingSessionRef = useRef(0);

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
    const requestSeq = ++providersRequestSeqRef.current;
    setProvidersError(null);
    try {
      setProvidersLoading(true);
      const response = await apiClient.get('/payments/providers');

      // CSH-FE-038: a newer load (another currency) superseded this one —
      // discard the stale response entirely.
      if (requestSeq !== providersRequestSeqRef.current) {
        return;
      }

      if (Array.isArray(response.data?.providers)) {
        // Фильтруем активные провайдеры по валюте
        const availableProviders = response.data.providers.filter(
          (provider: PaymentProviderDto) => provider.is_active &&
          provider.supported_currencies.includes(currency)
        );
        setProviders(availableProviders);

        // Автовыбор первого доступного провайдера.
        // CSH-FE-030: ручной выбор кассира не сбрасывается при повторной
        // загрузке (смена валюты/рефреш) — автозамена только если текущий
        // выбор пуст или отсутствует в новом списке.
        if (availableProviders.length > 0) {
          setSelectedProvider((current) =>
            current && availableProviders.some((provider: PaymentProviderDto) => provider.code === current)
              ? current
              : availableProviders[0].code
          );
        } else {
          // CSH-FE-038: an empty list must not keep a selection made for
          // another currency — the leftover code could later be paired with
          // a provider/currency combination the list never offered.
          setSelectedProvider('');
        }
      } else {
        // PR-3854 review follow-up: a malformed payload (no providers array)
        // must not keep the previous currency's list rendered either.
        setProviders([]);
        setSelectedProvider('');
      }
    } catch (err) {
      // CSH-FE-038: only the current request may surface errors; a stale
      // rejection belongs to an abandoned currency load.
      if (requestSeq !== providersRequestSeqRef.current) {
        return;
      }
      logger.error('Ошибка загрузки провайдеров:', err);
      // PR-3854 review follow-up: a failed reload must INVALIDATE the list of
      // the previous currency — otherwise the widget keeps rendering (and
      // paying with) a provider/currency pair the new currency never
      // offered. Payment stays disabled until a reload succeeds.
      setProviders([]);
      setSelectedProvider('');
      setProvidersError(getErrorMessage(err, tRef.current('payment.pay_widg_load_providers_error')));
    } finally {
      // CSH-FE-038: let the CURRENT request own the loading flag — a stale
      // finally must not cancel the loading state of the newer in-flight load.
      if (requestSeq === providersRequestSeqRef.current) {
        setProvidersLoading(false);
      }
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
    // PR-3854 re-review follow-up: invalidate the stopped session so its
    // still-in-flight GET (if any) can neither release the single-flight
    // lock nor run the budget branch against whatever session runs next.
    pollingSessionRef.current += 1;
    attemptsRef.current = 0;
    setPollingAttempts(0);
  }, []);

  const startPolling = useCallback(() => {
    // Don't start if already polling.
    if (pollingRef.current) return;
    attemptsRef.current = 0;
    setPollingAttempts(0);
    // PR-3854 re-review follow-up: a fresh session takes the NEXT epoch and
    // a clean single-flight guard. A previous session's unsettled GET can
    // neither block this one (guard reset) nor release its lock later (the
    // epoch check in its finally fails) — see pollingSessionRef above.
    pollingSessionRef.current += 1;
    const session = pollingSessionRef.current;
    statusCheckInFlightRef.current = false;

    pollingRef.current = setInterval(() => {
      // PR-3854 review follow-up (single-flight): the previous status GET has
      // not settled yet — skip this tick instead of stacking a concurrent
      // request whose response may land after a newer observation.
      if (statusCheckInFlightRef.current) return;
      statusCheckInFlightRef.current = true;
      void (async () => {
        attemptsRef.current += 1;
        setPollingAttempts(attemptsRef.current);
        let observedStatus: string | null = null;
        try {
          observedStatus = await checkPaymentStatus();
        } catch (err) {
          logger.error('Polling error:', err);
        } finally {
          // PR-3854 re-review follow-up (epoch guard): only the CURRENT
          // session may release the single-flight lock — a stopped or
          // superseded session's late-settling GET must not unlock the guard
          // held by the new session's in-flight request.
          if (pollingSessionRef.current === session) {
            statusCheckInFlightRef.current = false;
          }
        }
        // PR-3854 re-review follow-up (epoch guard): the budget branch
        // likewise belongs to the current session only — a superseded
        // session's continuation must not consume the new session's attempt
        // counter nor clear its interval via clearPolling().
        if (pollingSessionRef.current === session && attemptsRef.current >= MAX_POLLING_ATTEMPTS) {
          clearPolling();
          // CSH-FE-031: five minutes of frontend polling is an
          // observation limit, NOT provider failure — the payment may still
          // complete. Surface an explicit monitoring-timeout state with a
          // manual check instead of inventing a 'failed' payment status.
          // CSH-FE-037: …but the poll that exhausts the budget may itself
          // observe a TERMINAL status (paid/failed/…) — the timeout state
          // must never overwrite it, or a paid visit renders as timed out.
          // PR-3854 review follow-up: the same no-rollback rule applies when
          // ANOTHER observation (e.g. a manual status check that raced this
          // hanging poll) already confirmed a terminal status.
          const observedTerminal =
            observedStatus !== null && isTerminalPaymentStatus(observedStatus);
          if (!observedTerminal) {
            setPaymentStatus((previous) =>
              isTerminalPaymentStatus(previous) ? previous : 'status_check_timeout');
          }
        }
      })();
    }, POLLING_INTERVAL_MS);
  }, [clearPolling, t]);

  // Инициализация платежа
  const initializePayment = async () => {
    // CSH-FE-038: truthiness alone is not enough — the selected code must
    // actually be offered by the CURRENT provider list, otherwise a stale
    // selection could POST a provider/currency pair the list never offered.
    // PR-3854 review follow-up: list membership alone is still not enough —
    // the selected provider must support the CURRENT currency AT POST
    // TIME, not the currency of the list snapshot (guards the render window
    // between a currency prop change and the provider reload effect).
    const selectedProviderDto = providers.find(
      (provider: PaymentProviderDto) => provider.code === selectedProvider
    );
    const selectedProviderSupportsCurrency =
      !!selectedProviderDto && selectedProviderDto.supported_currencies.includes(currency);
    if (!selectedProvider || !selectedProviderSupportsCurrency || !visitId || !amount) {
      setError(t('payment.pay_widg_missing_data'));
      return;
    }

    // Проверяем наличие токена авторизации
    const token = getToken();
    logger.log('Checking auth token for payment', {
      hasToken: !!token,
      tokenLength: token ? token.length : 0,
    });

    if (!token) {
      setError(t('payment.pay_widg_auth_required'));
      if (onError) {
        onError(t('payment.pay_widg_auth_required_short'));
      }
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const paymentRequest = {
        visit_id: visitId,
        provider: selectedProvider,
        amount: parseFloat(String(amount)),
        currency: currency,
        description: effectiveDescription,
        return_url: `${window.location.origin}/payment/success`,
        cancel_url: `${window.location.origin}/payment/cancel`
      };

      // PAY-REAUDIT-28 P1-4: удалён hardcoded test-token bypass — строка
      // `demo_token_for_ui_testing` была в JS-бандле, и любой пользователь
      // мог поставить такой токен через devtools, чтобы перенаправить
      // платежи на /payments/test-init. Test-init должен вызываться только
      // через прямой API-вызов в dev/staging.
      const endpoint = '/payments/init';

      logger.log('Sending payment request', {
        endpoint,
        hasAuthHeader: !!apiClient.defaults.headers.common['Authorization'],
        authHeaderLength: (apiClient.defaults.headers.common['Authorization'] as string | undefined)?.length || 0,
      });

      const response = await apiClient.post(endpoint, paymentRequest);

      if (response.data?.success) {
        const nextPaymentData: PaymentData = {
          ...(response.data as Record<string, unknown>),
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

            const confirmedPaymentData: PaymentData = {
              ...nextPaymentData,
              ...(confirmResponse.data as Record<string, unknown>),
              payment_id: response.data.payment_id,
              provider: selectedProvider,
              status: (confirmResponse.data?.status as string) ?? null,
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
            t('payment.pay_widg_init_error')
          )
        );
      }
    } catch (err) {
      logger.error('Ошибка инициализации платежа:', err);
      const errorMessage = getErrorMessage(err, t('payment.pay_widg_process_error'));
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
  // CSH-FE-037: returns the observed payment status (or null when unknown /
  // errored) so the polling-budget branch can tell whether the last
  // observation was terminal before applying the monitoring-timeout state.
  const checkPaymentStatus = async (): Promise<string | null> => {
    // CSH-FE-029: polling reads the CURRENT payment data from the ref —
    // the interval's closure cannot go stale.
    const currentPaymentData = paymentDataRef.current;
    if (!currentPaymentData?.payment_id) return null;

    // PR-3854 review follow-up (payment identity): pin the payment this GET
    // belongs to — a response that settles after the session was cancelled
    // or replaced must be discarded, not applied to the new session.
    const paymentId = currentPaymentData.payment_id;

    try {
      const response = await apiClient.get(`/payments/${paymentId}`);

      if (paymentDataRef.current?.payment_id !== paymentId) {
        // The payment session changed while this GET was in flight.
        return null;
      }

      if (response.data?.status) {
        // Keep exact backend payment status; frontend must not collapse provider/status aliases.
        const nextStatus = String(response.data.status);
        // PR-3854 review follow-up (no terminal rollback): a confirmed
        // TERMINAL status is authoritative — a later-arriving non-terminal
        // observation (e.g. a slow poll that raced a manual 'paid' check)
        // must not resurrect a payable state for an already paid visit.
        setPaymentStatus((previous) =>
          isTerminalPaymentStatus(previous) && !isTerminalPaymentStatus(nextStatus)
            ? previous
            : nextStatus
        );

        if (nextStatus === 'paid' && onSuccess) {
          onSuccess({
            ...currentPaymentData,
            ...(response.data as Record<string, unknown>),
            status: response.data.status
          });
        }
        return nextStatus;
      }
    } catch (err) {
      logger.error('Ошибка проверки статуса:', err);
    }
    return null;
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

  // UX Audit #1.5: confirmPayment() и showConfirmDialog state удалены —
  // двойное подтверждение убрано. initializePayment() вызывается напрямую.

  // Форматирование суммы
  const formatAmount = (amountValue: string | number | undefined, currencyCode: string) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: currencyCode === 'UZS' ? 'UZS' : currencyCode === 'KZT' ? 'KZT' : 'USD',
      minimumFractionDigits: 0
    }).format(Number(amountValue ?? 0));
  };

  // Рендер статуса платежа
  const renderPaymentStatus = () => {
    switch (paymentStatus) {
      case 'pending':
        return (
          <Alert severity="info" icon={<InfoIcon />}>
            {t('payment.pay_widg_select_method')}
          </Alert>);

      case 'initialized':
        return (
          <Alert severity="success" icon={<CheckIcon />}>
            {t('payment.pay_widg_initialized', { id: paymentData?.payment_id })}
          </Alert>);

      case 'redirected':
      case 'processing':
        return (
          <Alert severity="info" icon={<InfoIcon />}>
            <div className="pw-provider-option-row">
              <span>{t('payment.pay_widg_redirecting')}</span>
              {pollingRef.current && (
                <span className="pw-provider-option-name">
                  {t('payment.pay_widg_auto_check', { current: pollingAttempts, max: MAX_POLLING_ATTEMPTS })}
                </span>
              )}
              <div className="pw-provider-option-badges">
                <Button
                  size="small"
                  onClick={checkPaymentStatus}>
                  {t('payment.pay_widg_check_status')}
                </Button>
                {pollingRef.current ? (
                  <Button
                    size="small"
                    variant="outline"
                    onClick={clearPolling}>
                    {t('payment.pay_widg_stop_tracking')}
                  </Button>
                ) : (
                  <Button
                    size="small"
                    variant="outline"
                    onClick={startPolling}>
                    {t('payment.pay_widg_start_tracking')}
                  </Button>
                )}
              </div>
            </div>
          </Alert>);

      case 'status_check_timeout':
        // CSH-FE-031: мониторинг остановлен по лимиту наблюдения — платёж
        // НЕ считается проваленным; предупреждение + ручная сверка статуса.
        return (
          <Alert severity="warning" icon={<InfoIcon />}>
            <div className="pw-provider-option-row">
              <span>{t('payment.pay_widg_timeout')}</span>
              <div className="pw-provider-option-badges">
                <Button
                  size="small"
                  onClick={checkPaymentStatus}>
                  {t('payment.pay_widg_check_status')}
                </Button>
                <Button
                  size="small"
                  variant="outline"
                  onClick={startPolling}>
                  {t('payment.pay_widg_start_tracking')}
                </Button>
              </div>
            </div>
          </Alert>);

      case 'paid':
        return (
          <Alert severity="success" icon={<CheckIcon />}>
            {t('payment.pay_widg_paid_success')}
          </Alert>);

      case 'failed':
      case 'cancelled':
      case 'canceled':
        return (
          <Alert severity="error" icon={<ErrorIcon />}>
            {t('payment.pay_widg_payment_failed')}
          </Alert>);

      case 'refunded':
      case 'void':
        return (
          <Alert severity="warning" icon={<ErrorIcon />}>
            {t('payment.pay_widg_status_label', { status: paymentStatus })}
          </Alert>);

      default:
        return paymentStatus ? (
          <Alert severity="info" icon={<InfoIcon />}>
            {t('payment.pay_widg_status_label', { status: paymentStatus })}
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
              {t('payment.pay_widg_loading_methods')}
            </Typography>
          </Box>
        </CardContent>
      </Card>);

  }

  if (providers.length === 0) {
    return (
      <Card>
        <CardContent>
          {/* PR-3854 review follow-up: an empty list after a FAILED reload is a
              load error, not "no methods configured" — surface the real
              reason; either way no payment can start from this state. */}
          {providersError ? (
            <Alert severity="error">{providersError}</Alert>
          ) : (
            <Alert severity="warning">
              {t('payment.pay_widg_no_methods', { currency })}
            </Alert>
          )}
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
            {t('payment.pay_widg_payment_for_services')}
          </Typography>
        </Box>

        {/* Информация о платеже */}
        <Box className="pw-payment-info-box">
          <div className="pw-payment-info-row">
            <div className="pw-payment-info-cell">
              <Typography variant="body2" color="textSecondary">
                {t('payment.pay_widg_amount_due')}
              </Typography>
              <Typography variant="h5"  className="pw-amount-bold">
                {formatAmount(amount, currency)}
              </Typography>
            </div>
            <div className="pw-payment-info-cell">
              <Typography variant="body2" color="textSecondary">
                {t('payment.pay_widg_description')}
              </Typography>
              <Typography variant="body1">
                {effectiveDescription}
              </Typography>
            </div>
          </div>
        </Box>

        <div className="pw-divider" />

        {/* Выбор провайдера */}
        <Select
          id="payment-provider"
          label={t('payment.pay_widg_method_label')}
          value={selectedProvider}
          onValueChange={(value: unknown) => setSelectedProvider(String(value))}
          disabled={loading}
          className="pw-select-margin"
          options={providers.map((provider: PaymentProviderDto) => ({
            value: provider.code,
            label: (
              <span className="pw-provider-option">
                {providerIcons[provider.code as keyof typeof providerIcons]}
                <span className="pw-provider-name">
                  {provider.name}
                </span>
                <Badge
                  size="small"
                  variant="outline"
                  style={{
                    marginLeft: 'auto',
                    backgroundColor: providerColors[provider.code as keyof typeof providerColors] + '20',
                    color: providerColors[provider.code as keyof typeof providerColors]
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
        {/* UX Audit #1.5: убран двойной confirm-dialog (Nielsen #7 — flexibility & efficiency).
            Раньше: click «Оплатить» → модалка подтверждения → click «Продолжить» → реальная инициализация.
            Теперь: click «Оплатить» сразу инициализирует платёж. Защита от случайного клика —
            через `loading` state (кнопка дизейблится на время инициализации). */}
        <Box display="flex" className="pw-actions-row">
          <Button
            variant="primary"
            size="large"
            fullWidth
            onClick={initializePayment}
            disabled={loading || !selectedProvider || paymentStatus === 'paid'}>

            {loading ?
            <>
                <CircularProgress size={20} className="pw-submit-spinner" />
                {t('payment.pay_widg_processing')}
              </> :

            t('payment.pay_widg_pay_amount', { amount: formatAmount(amount, currency) })
            }
          </Button>

          {paymentStatus !== 'pending' &&
          <Button
            variant="outline"
            size="large"
            onClick={cancelPayment}
            disabled={loading}>

              {t('payment.pay_widg_cancel')}
            </Button>
          }
        </Box>
      </CardContent>
    </Card>);

};



export default PaymentWidget;
