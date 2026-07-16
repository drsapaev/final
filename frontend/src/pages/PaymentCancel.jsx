
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Box, Card, CardContent, Typography, Button, Alert,
} from '../components/ui/macos';
import { XCircle as CancelIcon, Home as HomeIcon, Headset as SupportIcon } from 'lucide-react';
import { useTranslation } from '../i18n/useTranslation';

const SUPPORT_TELEGRAM_HANDLE = '@clinic_support';
const SUPPORT_TELEGRAM_URL = 'https://t.me/clinic_support';

const pageStyle = {
  maxWidth: 960,
  margin: '32px auto',
  padding: '0 16px 40px',
};

const statusCardStyle = {
  marginBottom: 16,
  borderColor: 'var(--mac-warning-border, color-mix(in srgb, var(--mac-warning), transparent 64%))',
  background: 'var(--mac-warning-bg)',
};

const statusContentStyle = {
  textAlign: 'center',
  padding: '32px 16px',
};

const cancelIconStyle = {
  width: 80,
  height: 80,
  color: 'var(--mac-warning)',
  marginBottom: 8,
};

const detailGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
  gap: 12,
};

const detailItemStyle = {
  border: '1px solid var(--mac-border)',
  borderRadius: 'var(--mac-radius-md)',
  padding: 12,
};

const actionGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
  gap: 12,
  marginTop: 8,
};

const PaymentCancel = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Получаем параметры из URL
  const paymentId = searchParams.get('payment_id');
  const reason = searchParams.get('reason');
  const error = searchParams.get('error');

  const handleCashierPayment = () => {
    // Возвращаемся в существующий кассовый маршрут без несуществующего retry-route.
    navigate('/cashier');
  };

  const handleContactSupport = () => {
    // Открываем существующий официальный Telegram-канал поддержки из landing/contact copy.
    window.location.assign(SUPPORT_TELEGRAM_URL);
  };

  const getReason = () => {
    const reasons = {
      'user_cancelled': 'Вы отменили платеж',
      'timeout': 'Время ожидания истекло',
      'insufficient_funds': 'Недостаточно средств',
      'card_declined': 'Карта отклонена',
      'technical_error': 'Техническая ошибка',
      'provider_error': 'Ошибка платежной системы'
    };

    return reasons[reason] || 'Платеж был отменен или не подтвержден';
  };

  return (
    <main style={pageStyle} aria-labelledby="payment-cancel-title">
      {/* Заголовок */}
      <Card
        style={statusCardStyle}
        role="alert"
        aria-live="assertive"
        aria-labelledby="payment-cancel-title"
        aria-describedby="payment-cancel-reason">
        <CardContent style={statusContentStyle}>
          <CancelIcon style={cancelIconStyle} aria-hidden="true" />
          <Typography id="payment-cancel-title" variant="h4" color="warning" gutterBottom>
            Платеж не завершен
          </Typography>
          <Typography id="payment-cancel-reason" variant="h6" color="textSecondary">
            {getReason()}
          </Typography>
        </CardContent>
      </Card>

      {/* Информация об ошибке */}
      {error &&
      <Alert severity="error" role="alert" style={{ marginBottom: 12 }}>
          <Typography variant="body1" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
            Детали ошибки:
          </Typography>
          <Typography variant="body2">
            {error}
          </Typography>
        </Alert>
      }

      {/* Информация о платеже */}
      {paymentId &&
      <Card style={{ marginBottom: 16 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Информация о платеже
            </Typography>
            <div style={detailGridStyle}>
              <div style={detailItemStyle}>
                <Typography variant="body2" color="textSecondary">Номер платежа</Typography>
                <Typography variant="h6">#{paymentId}</Typography>
              </div>
              <div style={detailItemStyle}>
                <Typography variant="body2" color="textSecondary">Время отмены</Typography>
                <Typography variant="body1">{new Date().toLocaleString('ru-RU')}</Typography>
              </div>
            </div>
          </CardContent>
        </Card>
      }

      {/* Рекомендации */}
      <Card style={{ marginBottom: 16 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Что делать дальше?
          </Typography>
          <Box style={{ marginTop: 8 }}>
            <Typography variant="body1" paragraph>
              • Проверьте баланс на карте или счете
            </Typography>
            <Typography variant="body1" paragraph>
              • Убедитесь в правильности введенных данных
            </Typography>
            <Typography variant="body1" paragraph>
              • Попробуйте использовать другой способ оплаты
            </Typography>
            <Typography variant="body1" paragraph>
              • Обратитесь в клинику через официальный канал поддержки при повторных ошибках
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* Действия */}
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Доступные действия
          </Typography>
          <div style={actionGridStyle}>
            <Button onClick={handleCashierPayment}>К оплате в кассе</Button>
            <Button variant="outline" onClick={handleContactSupport}><SupportIcon style={{ marginRight: 8 }} />Связаться в Telegram</Button>
            <Button variant="outline" onClick={() => navigate('/')}><HomeIcon style={{ marginRight: 8 }} />На главную</Button>
          </div>
        </CardContent>
      </Card>

      {/* Контактная информация */}
      <Box style={{ marginTop: 16, textAlign: 'center' }}>
        <Typography variant="body2" color="textSecondary" paragraph>
          Официальный канал поддержки: {SUPPORT_TELEGRAM_HANDLE}
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Контакты клиники также доступны на главной странице.
        </Typography>
      </Box>
    </main>);

};

export default PaymentCancel;
