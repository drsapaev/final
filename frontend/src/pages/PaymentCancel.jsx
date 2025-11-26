import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Box, Card, CardContent, Typography, Button, Alert } from '../components/ui/macos';
import { XCircle as CancelIcon, Home as HomeIcon, RefreshCw as RetryIcon, Headset as SupportIcon } from 'lucide-react';

const PaymentCancel = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  
  // Получаем параметры из URL
  const paymentId = searchParams.get('payment_id');
  const reason = searchParams.get('reason');
  const error = searchParams.get('error');

  const handleRetryPayment = () => {
    // Возвращаемся к оплате или на страницу с услугами
    if (paymentId) {
      navigate(`/payment/retry?payment_id=${paymentId}`);
    } else {
      navigate('/cashier');
    }
  };

  const handleContactSupport = () => {
    // Переход к контактам или открытие чата поддержки
    navigate('/support');
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
    
    return reasons[reason] || 'Платеж был отменен';
  };

  return (
    <Box style={{ maxWidth: 960, margin: '32px auto', padding: '0 16px' }}>
      {/* Заголовок */}
      <Card style={{ marginBottom: 16 }}>
        <CardContent style={{ textAlign: 'center', padding: '32px 16px' }}>
          <CancelIcon style={{ fontSize: 80, color: 'var(--mac-warning)', marginBottom: 8 }} />
          <Typography variant="h4" color="warning" gutterBottom>
            Платеж отменен
          </Typography>
          <Typography variant="h6" color="textSecondary">
            {getReason()}
          </Typography>
        </CardContent>
      </Card>

      {/* Информация об ошибке */}
      {error && (
        <Alert severity="error" style={{ marginBottom: 12 }}>
          <Typography variant="body1" style={{ fontWeight: 600 }}>
            Детали ошибки:
          </Typography>
          <Typography variant="body2">
            {error}
          </Typography>
        </Alert>
      )}

      {/* Информация о платеже */}
      {paymentId && (
        <Card style={{ marginBottom: 16 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Информация о платеже
            </Typography>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
              <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12 }}>
                <Typography variant="body2" color="textSecondary">Номер платежа</Typography>
                <Typography variant="h6">#{paymentId}</Typography>
              </div>
              <div style={{ border: '1px solid var(--mac-border)', borderRadius: 8, padding: 12 }}>
                <Typography variant="body2" color="textSecondary">Время отмены</Typography>
                <Typography variant="body1">{new Date().toLocaleString('ru-RU')}</Typography>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

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
              • Обратитесь в службу поддержки при повторных ошибках
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
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12, marginTop: 8 }}>
            <Button onClick={handleRetryPayment}><RetryIcon style={{ marginRight: 8 }} />Повторить оплату</Button>
            <Button variant="outline" onClick={handleContactSupport}><SupportIcon style={{ marginRight: 8 }} />Связаться с поддержкой</Button>
            <Button variant="outline" onClick={() => navigate('/')}><HomeIcon style={{ marginRight: 8 }} />На главную</Button>
            <Button variant="outline" onClick={() => navigate('/cashier')}>К оплате в кассе</Button>
          </div>
        </CardContent>
      </Card>

      {/* Контактная информация */}
      <Box style={{ marginTop: 16, textAlign: 'center' }}>
        <Typography variant="body2" color="textSecondary" paragraph>
          Служба поддержки: +998 (71) 123-45-67
        </Typography>
        <Typography variant="body2" color="textSecondary">
          Email: support@clinic.uz
        </Typography>
      </Box>
    </Box>
  );
};

export default PaymentCancel;
