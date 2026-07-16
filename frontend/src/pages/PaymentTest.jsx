/**
 * PaymentTest - Тестовая страница для проверки PaymentWidget
 */

import { useEffect, useState } from 'react';
import { CreditCard, FlaskConical } from 'lucide-react';

import {
  Alert, Button, Card, CardContent, Typography,
  Input } from '../components/ui/macos';
import PaymentWidget from '../components/payment/PaymentWidget';
import { getApiOrigin, setToken, getToken } from '../api/client';

import logger from '../utils/logger';
import { useTranslation } from '../i18n/useTranslation';

const pageStyle = {
  maxWidth: 1180,
  margin: '0 auto',
  padding: '32px 16px 48px',
};

const headerStyle = {
  textAlign: 'center',
  marginBottom: 32,
};

const titleRowStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 12,
  flexWrap: 'wrap',
};

const mainGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))',
  gap: 24,
  alignItems: 'start',
};

const fieldStackStyle = {
  display: 'grid',
  gap: 14,
  marginTop: 16,
};

const fieldLabelStyle = {
  display: 'grid',
  gap: 6,
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-sm)',
  fontWeight: 'var(--mac-font-weight-medium)',
};

const fieldControlStyle = {
  width: '100%',
  minHeight: 40,
  boxSizing: 'border-box',
  border: '1px solid var(--mac-card-border, var(--mac-border))',
  borderRadius: 'var(--mac-radius-md)',
  background: 'var(--mac-card-bg, var(--mac-bg-primary))',
  color: 'var(--mac-text-primary)',
  padding: '9px 12px',
  font: 'inherit',
  outlineOffset: 2,
};

const resultPreStyle = {
  margin: 0,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-md)',
  background: 'var(--mac-bg-tertiary)',
  color: 'var(--mac-text-primary)',
  padding: 12,
  fontSize: 12,
  lineHeight: 1.45,
};

const placeholderStyle = {
  minHeight: 400,
  display: 'grid',
  placeItems: 'center',
  textAlign: 'center',
};

const statsGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
  gap: 12,
};

const statItemStyle = {
  textAlign: 'center',
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-md)',
  padding: 16,
  background: 'var(--mac-bg-secondary)',
};

const fullWidthButtonStyle = {
  width: '100%',
};

const PaymentTest = () => {
  const { t } = useTranslation();
  const [showWidget, setShowWidget] = useState(false);
  const [testData, setTestData] = useState({
    visitId: 1,
    amount: 150000,
    currency: 'UZS',
    description: t('misc.pt_testovaya_oplata_meditsinski')
  });
  const [result, setResult] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Проверяем авторизацию при загрузке
  useEffect(() => {
    const token = getToken();
    setIsAuthenticated(!!token);
  }, []);

  const handleTestAuth = () => {
    setResult({
      type: 'info',
      message: 'Open /login and sign in before using the internal payment test.'
    });
    window.location.assign('/login');
  };

  const handlePaymentSuccess = (paymentData) => {
    logger.log('Payment Success:', paymentData);
    setResult({
      type: 'success',
      data: paymentData,
      message: t('misc.pt_platezh_uspeshno_obrabotan')
    });
    setShowWidget(false);
  };

  const handlePaymentError = (errorMessage) => {
    logger.error('Payment Error:', errorMessage);
    setResult({
      type: 'error',
      message: errorMessage
    });
  };

  const handlePaymentCancel = () => {
    logger.log('Payment Cancelled');
    setShowWidget(false);
    setResult({
      type: 'info',
      message: t('misc.pt_platezh_otmenen_polzovatelem')
    });
  };

  const startTest = () => {
    setResult(null);
    setShowWidget(true);
  };

  return (
    <main style={pageStyle} aria-labelledby="payment-test-title">
      <header style={headerStyle}>
        <div style={titleRowStyle}>
          <FlaskConical size={40} aria-hidden="true" />
          <Typography id="payment-test-title" variant="h1">
            Тестирование PaymentWidget
          </Typography>
        </div>
        <Typography variant="body1" color="textSecondary" style={{ marginTop: 8 }}>
          Страница для тестирования компонента онлайн-платежей
        </Typography>
      </header>

      <section style={mainGridStyle}>
        <div>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Настройки теста
              </Typography>

              <div style={fieldStackStyle}>
                <label style={fieldLabelStyle} htmlFor="payment-test-visit-id">
                  ID визита
                  <Input
                    id="payment-test-visit-id"
                    type="number"
                    aria-label="Payment test visit id"
                    value={testData.visitId}
                    onChange={(e) => setTestData({ ...testData, visitId: parseInt(e.target.value, 10) })}
                    style={fieldControlStyle}
                  />
                </label>

                <label style={fieldLabelStyle} htmlFor="payment-test-amount">
                  Сумма
                  <Input
                    id="payment-test-amount"
                    type="number"
                    aria-label="Payment test amount"
                    value={testData.amount}
                    onChange={(e) => setTestData({ ...testData, amount: parseFloat(e.target.value) })}
                    style={fieldControlStyle}
                  />
                </label>

                <label style={fieldLabelStyle} htmlFor="payment-test-currency">
                  Валюта
                  <select
                    id="payment-test-currency"
                    value={testData.currency}
                    onChange={(e) => setTestData({ ...testData, currency: e.target.value })}
                    style={fieldControlStyle}
                  >
                    <option value="UZS">UZS (Узбекский сум)</option>
                    <option value="KZT">KZT (Казахский тенге)</option>
                    <option value="USD">USD (Доллар США)</option>
                  </select>
                </label>

                <label style={fieldLabelStyle} htmlFor="payment-test-description">
                  Описание
                  <textarea
                    id="payment-test-description"
                    aria-label="Payment test description"
                    rows={2}
                    value={testData.description}
                    onChange={(e) => setTestData({ ...testData, description: e.target.value })}
                    style={{ ...fieldControlStyle, resize: 'vertical', minHeight: 72 }}
                  />
                </label>

                {!isAuthenticated ? (
                  <Button
                    variant="outline"
                    size="large"
                    onClick={handleTestAuth}
                    style={{
                      ...fullWidthButtonStyle,
                      borderColor: 'var(--mac-warning)',
                      color: 'var(--mac-warning)',
                    }}
                  >
                    🔐 Открыть вход
                  </Button>
                ) : (
                  <div style={{ display: 'grid', gap: 8 }}>
                    <Alert severity="success" role="status">
                      ✅ Авторизован для тестирования
                    </Alert>
                    <Button
                      variant="outline"
                      size="small"
                      onClick={() => {
                        // P2 warning: setToken(null) globally resets auth — only use in test context
  // This is a test page, so it's acceptable, but add a confirm dialog
  if (window.confirm(t('misc.pt_eto_sbrosit_avtorizatsiyu_pr'))) {
    setToken(null);
  }
                        setIsAuthenticated(false);
                        setResult({ type: 'info', message: t('misc.pt_avtorizatsiya_sbroshena') });
                      }}
                      style={fullWidthButtonStyle}
                    >
                      🚪 Выйти
                    </Button>
                  </div>
                )}

                <Button
                  variant="primary"
                  size="large"
                  onClick={startTest}
                  disabled={showWidget || !isAuthenticated}
                  style={fullWidthButtonStyle}
                >
                  <CreditCard size={18} aria-hidden="true" />
                  {showWidget ? t('misc.pt_test_zapuschen') : isAuthenticated ? t('misc.pt_zapustit_test') : t('misc.pt_trebuetsya_avtorizatsiya')}
                </Button>
              </div>
            </CardContent>
          </Card>

          {result && (
            <Card style={{ marginTop: 16 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Результат теста
                </Typography>

                <Alert
                  severity={result.type === 'success' ? 'success' : result.type === 'error' ? 'error' : 'info'}
                  role={result.type === 'error' ? 'alert' : 'status'}
                  style={{ marginBottom: 12 }}
                >
                  {result.message}
                </Alert>

                {result.data && (
                  <pre style={resultPreStyle}>
                    {JSON.stringify(result.data, null, 2)}
                  </pre>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <div>
          {showWidget ? (
            <PaymentWidget
              visitId={testData.visitId}
              amount={testData.amount}
              currency={testData.currency}
              description={testData.description}
              onSuccess={handlePaymentSuccess}
              onError={handlePaymentError}
              onCancel={handlePaymentCancel}
            />
          ) : (
            <Card>
              <CardContent style={placeholderStyle}>
                <div>
                  <CreditCard
                    size={80}
                    aria-hidden="true"
                    style={{ color: 'var(--mac-text-tertiary)', marginBottom: 12 }}
                  />
                  <Typography variant="h6" color="textSecondary">
                    Нажмите &quot;Запустить тест&quot; для отображения виджета
                  </Typography>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>

      <Card style={{ marginTop: 24 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Информация о тестируемой системе
          </Typography>

          <div style={statsGridStyle}>
            <div style={statItemStyle}>
              <Typography variant="h4" color="primary">3</Typography>
              <Typography variant="body2" color="textSecondary">{t('misc.pt_provaydera')}</Typography>
            </div>

            <div style={statItemStyle}>
              <Typography variant="h4" color="success">2</Typography>
              <Typography variant="body2" color="textSecondary">{t('misc.pt_valyuty')}</Typography>
            </div>

            <div style={statItemStyle}>
              <Typography variant="h4" color="warning">100%</Typography>
              <Typography variant="body2" color="textSecondary">{t('misc.pt_gotovnost')}</Typography>
            </div>

            <div style={statItemStyle}>
              <Typography variant="h4" color="primary">✓</Typography>
              <Typography variant="body2" color="textSecondary">Webhook</Typography>
            </div>
          </div>

          <Alert severity="info" style={{ marginTop: 16 }}>
            <Typography variant="body2">
              <strong>{t('misc.pt_podderzhivaemye_provaydery')}</strong> Click (UZS), Payme (UZS), Kaspi (KZT)
              <br />
              <strong>Backend:</strong> {getApiOrigin()}
              <br />
              <strong>Frontend:</strong> http://localhost:5173
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    </main>
  );
};

export default PaymentTest;
