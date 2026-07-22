import { useTranslation } from '../i18n/useTranslation';
import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle,
  Download,
  Home,
  Printer,
  Receipt,
  Share2,
} from 'lucide-react';
import {
  Alert, Badge, Button, Card, CardContent,
} from '../components/ui/macos';

// API клиент
import { api as apiClient } from '../api/client';

import logger from '../utils/logger';
import { openPrintableWindow } from '../utils/printWindow';
import { notify } from '../services/notify';

const pageStyle: CSSProperties = {
  maxWidth: '960px',
  margin: '32px auto',
  padding: '0 16px 40px',
  color: 'var(--mac-text-primary)',
};

const centeredCardStyle: CSSProperties = {
  textAlign: 'center',
  marginBottom: 'var(--mac-spacing-4)',
};

const statusIconWrapStyle: CSSProperties = {
  width: '88px',
  height: '88px',
  borderRadius: '50%',
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: '18px',
};

const detailGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: 'var(--mac-spacing-3)',
  marginTop: 'var(--mac-spacing-4)',
};

const detailItemStyle: CSSProperties = {
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-md)',
  background: 'var(--mac-bg-secondary)',
  padding: '14px',
  minWidth: 0,
};

const detailLabelStyle: CSSProperties = {
  margin: '0 0 6px',
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-sm)',
};

const detailValueStyle: CSSProperties = {
  margin: 0,
  color: 'var(--mac-text-primary)',
  fontSize: 'var(--mac-font-size-lg)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  lineHeight: 1.35,
  overflowWrap: 'anywhere',
};

const actionGridStyle: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
  gap: 'var(--mac-spacing-3)',
  marginTop: 'var(--mac-spacing-4)',
};

const buttonIconStyle: CSSProperties = {
  width: '18px',
  height: '18px',
  marginRight: 'var(--mac-spacing-2)',
  flexShrink: 0,
};

const loadingWrapStyle: CSSProperties = {
  minHeight: '60vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '32px 16px',
};

const spinnerStyle: CSSProperties = {
  width: '48px',
  height: '48px',
  borderRadius: '50%',
  border: '4px solid var(--mac-success-bg)',
  borderTopColor: 'var(--mac-success)',
  animation: 'payment-success-spin 0.9s linear infinite',
  margin: '0 auto 16px',
};

const PaymentSuccess = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Состояния
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [paymentData, setPaymentData] = useState(null);
  const [receiptUrl, setReceiptUrl] = useState(null);

  // Получаем параметры из URL
  const paymentId = searchParams.get('payment_id');

  const generateReceipt = useCallback(async () => {
    try {
      const response = await apiClient.get(`/payments/${paymentId}/receipt`, {
        params: { format_type: 'pdf' }
      });

      if (response.data?.receipt_url) {
        setReceiptUrl(response.data.receipt_url);
      }
    } catch (err) {
      logger.warn('Не удалось сгенерировать квитанцию:', err);
    }
  }, [paymentId]);

  const loadPaymentDetails = useCallback(async () => {
    try {
      setLoading(true);

      const response = await apiClient.get(`/payments/${paymentId}`);

      if (response.data) {
        setPaymentData(response.data);

        // Если платеж успешен, генерируем квитанцию
        if (response.data.status === 'paid') {
          generateReceipt();
        }
      } else {
        setError(t('misc.ps_dannye_platezha_ne_naydeny'));
      }
    } catch (err) {
      logger.error('Ошибка загрузки платежа:', err);
      setError(t('misc.ps_ne_udalos_zagruzit_informats'));
    } finally {
      setLoading(false);
    }
  }, [paymentId, generateReceipt]);

  useEffect(() => {
    if (paymentId) {
      loadPaymentDetails();
    } else {
      setError(t('misc.ps_ne_ukazan_id_platezha'));
      setLoading(false);
    }
  }, [loadPaymentDetails, paymentId]);

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

Описание: ${paymentData.description || t('misc.ps_oplata_meditsinskih_uslug')}

Спасибо за использование наших услуг!
    `.trim();
  };

  const printReceipt = () => {
    const receiptContent = generateSimpleReceipt();
    openPrintableWindow({
      html: `
      <html>
        <head>
          <title>Квитанция ${paymentId}</title>
          <style>
            body { font-family: monospace; margin: 24px; color: #111827; }
            h1 { font-size: 20px; margin-bottom: 12px; }
            .meta { margin-bottom: 16px; line-height: 1.6; }
            pre { white-space: pre-wrap; font-family: inherit; padding: 16px; border: 1px solid #d1d5db; border-radius: 8px; background: #f9fafb; }
          </style>
        </head>
        <body>
          <h1>{t('misc.ps_kvitantsiya_ob_oplate')}</h1>
          <div class="meta">
            <div><strong>{t('misc.ps_platezh')}</strong> ${paymentId}</div>
            <div><strong>{t('misc.ps_status')}</strong> ${getStatusText(paymentData.status)}</div>
          </div>
          <pre>${receiptContent}</pre>
        </body>
      </html>
    `
    });
  };

  const shareReceipt = async () => {
    if (navigator.share && paymentData) {
      try {
        await navigator.share({
          title: t('misc.ps_kvitantsiya_ob_oplate_paymen', { paymentId: paymentId }),
          text: t('misc.ps_oplata_na_summu_formatamount', { currency: formatAmount(paymentData.amount, paymentData.currency) }),
          url: window.location.href
        });
      } catch (err) {
        logger.log('Ошибка при шаринге:', err);
      }
    } else {
      // Fallback - копируем в буфер обмена
      navigator.clipboard.writeText(window.location.href);
      notify.info(t('final.link_copied'));
    }
  };

  const formatAmount = (amount, currency) => {
    const numAmount = parseFloat(amount);
    if (currency === 'UZS') {
      return t('misc.ps_numamount_100_tolocalestring', { RU: (numAmount / 100).toLocaleString('ru-RU') });
    } else if (currency === 'KZT') {
      return t('misc.ps_numamount_100_tolocalestring_2', { RU: (numAmount / 100).toLocaleString('ru-RU') });
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
      pending: t('misc.ps_ozhidaet'),
      processing: t('misc.ps_obrabotka'),
      paid: t('misc.ps_oplachen'),
      failed: t('misc.ps_neudachno'),
      cancelled: t('misc.ps_otmenen'),
      refunded: t('misc.ps_vozvraschen'),
      void: t('misc.ps_annulirovan')
    };
    return texts[status] || status;
  };

  const getStatusColor = (status) => {
    const colors = {
      pending: 'warning',
      processing: 'info',
      paid: 'success',
      failed: 'danger',
      cancelled: 'default',
      refunded: 'warning',
      void: 'default'
    };
    return colors[status] || 'default';
  };

  if (loading) {
    return (
      <main style={loadingWrapStyle} aria-busy="true" aria-live="polite">
        <Card padding="large" shadow="large" style={{ width: '100%', maxWidth: '420px', textAlign: 'center' }}>
          <div style={spinnerStyle} aria-hidden="true" />
          <h1 style={{ margin: '0 0 8px', fontSize: 'var(--mac-font-size-2xl)' }}>
            Проверяем платеж
          </h1>
          <p style={{ margin: 0, color: 'var(--mac-text-secondary)', lineHeight: 1.5 }}>
            Загружаем информацию и готовим квитанцию.
          </p>
          <style>{`
            @keyframes payment-success-spin {
              to { transform: rotate(360deg); }
            }
            @media (prefers-reduced-motion: reduce) {
              div[style*="payment-success-spin"] {
                animation: none !important;
              }
            }
          `}</style>
        </Card>
      </main>
    );
  }

  if (error) {
    return (
      <main style={pageStyle}>
        <Card padding="large" shadow="large">
          <Alert severity="error" role="alert" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
              <AlertCircle size={20} style={{ flexShrink: 0, color: 'var(--mac-danger)' }} />
              <div>
                <strong style={{ display: 'block', marginBottom: 'var(--mac-spacing-1)' }}>
                  Платеж не найден
                </strong>
                <span>{error}</span>
              </div>
            </div>
          </Alert>
          <Button
            variant="primary"
            onClick={() => navigate('/')}
          >
            <Home style={buttonIconStyle} />
            На главную
          </Button>
        </Card>
      </main>
    );
  }

  const isSuccess = paymentData?.status === 'paid';

  return (
    <main style={pageStyle}>
      <Card padding="large" shadow="large" style={centeredCardStyle}>
        {isSuccess ? (
          <>
            <div
              style={{
                ...statusIconWrapStyle,
                color: 'var(--mac-success)',
                background: 'var(--mac-success-bg)',
                border: '1px solid var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 72%))',
              }}
              aria-hidden="true"
            >
              <CheckCircle size={52} />
            </div>
            <h1 style={{ margin: '0 0 8px', fontSize: '26px', color: 'var(--mac-success)' }}>
              Оплата успешно завершена
            </h1>
            <p style={{ margin: 0, color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-lg)', lineHeight: 1.5 }}>
              Спасибо за использование наших услуг.
            </p>
          </>
        ) : (
          <>
            <div
              style={{
                ...statusIconWrapStyle,
                color: 'var(--mac-warning)',
                background: 'var(--mac-warning-bg)',
                border: '1px solid var(--mac-warning-border, color-mix(in srgb, var(--mac-warning), transparent 72%))',
              }}
              aria-hidden="true"
            >
              <AlertCircle size={52} />
            </div>
            <h1 style={{ margin: '0 0 8px', fontSize: '26px', color: 'var(--mac-warning)' }}>
              Статус платежа: {getStatusText(paymentData?.status)}
            </h1>
            <p style={{ margin: 0, color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-lg)', lineHeight: 1.5 }}>
              Информация о вашем платеже.
            </p>
          </>
        )}
      </Card>

      {paymentData && (
        <Card padding="large" shadow="default" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
          <CardContent>
            <h2 style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)', margin: 0, fontSize: 'var(--mac-font-size-xl)' }}>
              <Receipt size={20} aria-hidden="true" />
              Детали платежа
            </h2>

            <div style={detailGridStyle}>
              <div style={detailItemStyle}>
                <p style={detailLabelStyle}>{t('misc.ps_nomer_platezha')}</p>
                <p style={detailValueStyle}>#{paymentId}</p>
              </div>

              <div style={detailItemStyle}>
                <p style={detailLabelStyle}>{t('misc.ps_summa')}</p>
                <p style={{ ...detailValueStyle, color: 'var(--mac-accent-blue)' }}>
                  {formatAmount(paymentData.amount, paymentData.currency)}
                </p>
              </div>

              <div style={detailItemStyle}>
                <p style={detailLabelStyle}>{t('misc.ps_sposob_oplaty')}</p>
                <p style={{ ...detailValueStyle, fontWeight: 'var(--mac-font-weight-medium)' }}>
                  {getProviderName(paymentData.provider)}
                </p>
              </div>

              <div style={detailItemStyle}>
                <p style={detailLabelStyle}>{t('misc.ps_status_2')}</p>
                <Badge variant={getStatusColor(paymentData.status)}>
                  {getStatusText(paymentData.status)}
                </Badge>
              </div>

              <div style={{ ...detailItemStyle, gridColumn: '1 / -1' }}>
                <p style={detailLabelStyle}>{t('misc.ps_data_i_vremya')}</p>
                <p style={{ ...detailValueStyle, fontWeight: 'var(--mac-font-weight-medium)' }}>
                  {new Date(paymentData.created_at).toLocaleString('ru-RU')}
                </p>
              </div>

              {paymentData.description && (
                <div style={{ ...detailItemStyle, gridColumn: '1 / -1' }}>
                  <p style={detailLabelStyle}>{t('misc.ps_opisanie')}</p>
                  <p style={{ ...detailValueStyle, fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {paymentData.description}
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card padding="large" shadow="default">
        <CardContent>
          <h2 style={{ margin: 0, fontSize: 'var(--mac-font-size-xl)' }}>
            Действия
          </h2>

          <div style={actionGridStyle}>
            <Button
              variant="primary"
              fullWidth
              onClick={downloadReceipt}
              disabled={!paymentData}
            >
              <Download style={buttonIconStyle} />
              Скачать квитанцию
            </Button>

            <Button
              variant="outline"
              fullWidth
              onClick={printReceipt}
              disabled={!paymentData}
            >
              <Printer style={buttonIconStyle} />
              Печать
            </Button>

            <Button
              variant="outline"
              fullWidth
              onClick={shareReceipt}
              disabled={!paymentData}
            >
              <Share2 style={buttonIconStyle} />
              Поделиться
            </Button>

            <Button
              variant="outline"
              fullWidth
              onClick={() => navigate('/')}
            >
              <Home style={buttonIconStyle} />
              На главную
            </Button>
          </div>
        </CardContent>
      </Card>

      <p style={{ margin: '24px 0 0', textAlign: 'center', color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
        При возникновении вопросов обратитесь в службу поддержки.
      </p>
    </main>
  );
};

export default PaymentSuccess;
