import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Alert,
  Paper
} from '@mui/material';
import {
  Cancel as CancelIcon,
  Home as HomeIcon,
  Refresh as RetryIcon,
  ContactSupport as SupportIcon
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';

const PaymentCancel = () => {
  const theme = useTheme();
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
    <Box maxWidth="md" mx="auto" mt={4} px={2}>
      {/* Заголовок */}
      <Card elevation={3} sx={{ mb: 3 }}>
        <CardContent sx={{ textAlign: 'center', py: 4 }}>
          <CancelIcon 
            sx={{ 
              fontSize: 80, 
              color: 'warning.main', 
              mb: 2 
            }} 
          />
          <Typography variant="h4" color="warning.main" gutterBottom>
            Платеж отменен
          </Typography>
          <Typography variant="h6" color="textSecondary">
            {getReason()}
          </Typography>
        </CardContent>
      </Card>

      {/* Информация об ошибке */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="body1" fontWeight="bold">
            Детали ошибки:
          </Typography>
          <Typography variant="body2">
            {error}
          </Typography>
        </Alert>
      )}

      {/* Информация о платеже */}
      {paymentId && (
        <Card elevation={2} sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Информация о платеже
            </Typography>
            
            <Grid container spacing={2}>
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
                    Время отмены
                  </Typography>
                  <Typography variant="body1">
                    {new Date().toLocaleString('ru-RU')}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Рекомендации */}
      <Card elevation={2} sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Что делать дальше?
          </Typography>
          
          <Box sx={{ mt: 2 }}>
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
      <Card elevation={2}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Доступные действия
          </Typography>
          
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="contained"
                fullWidth
                startIcon={<RetryIcon />}
                onClick={handleRetryPayment}
                color="primary"
              >
                Повторить оплату
              </Button>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="outlined"
                fullWidth
                startIcon={<SupportIcon />}
                onClick={handleContactSupport}
              >
                Связаться с поддержкой
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
            
            <Grid item xs={12} sm={6} md={3}>
              <Button
                variant="outlined"
                fullWidth
                onClick={() => navigate('/cashier')}
              >
                К оплате в кассе
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Контактная информация */}
      <Box mt={4} textAlign="center">
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
