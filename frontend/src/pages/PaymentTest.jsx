/**
 * PaymentTest - Тестовая страница для проверки PaymentWidget
 */

import { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material';
import CreditCardIcon from '@mui/icons-material/CreditCard';
import ScienceIcon from '@mui/icons-material/Science';

import PaymentWidget from '../components/payment/PaymentWidget';
import { getApiOrigin, setToken, getToken } from '../api/client';

import logger from '../utils/logger';
const PaymentTest = () => {
  const [showWidget, setShowWidget] = useState(false);
  const [testData, setTestData] = useState({
    visitId: 1,
    amount: 150000,
    currency: 'UZS',
    description: 'Тестовая оплата медицинских услуг'
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
      message: 'Платеж успешно обработан!'
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
      message: 'Платеж отменен пользователем'
    });
  };

  const startTest = () => {
    setResult(null);
    setShowWidget(true);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Заголовок */}
      <Box textAlign="center" mb={4}>
        <Typography variant="h3" gutterBottom sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <ScienceIcon sx={{ mr: 2, fontSize: 40 }} />
          Тестирование PaymentWidget
        </Typography>
        <Typography variant="body1" color="textSecondary">
          Страница для тестирования компонента онлайн-платежей
        </Typography>
      </Box>

      <Grid container spacing={4}>
        {/* Настройки теста */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Настройки теста
              </Typography>
              
              <Box sx={{ mt: 2 }}>
                <TextField
                  fullWidth
                  label="ID визита"
                  type="number"
                  value={testData.visitId}
                  onChange={(e) => setTestData({ ...testData, visitId: parseInt(e.target.value) })}
                  sx={{ mb: 2 }}
                />
                
                <TextField
                  fullWidth
                  label="Сумма"
                  type="number"
                  value={testData.amount}
                  onChange={(e) => setTestData({ ...testData, amount: parseFloat(e.target.value) })}
                  sx={{ mb: 2 }}
                />
                
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Валюта</InputLabel>
                  <Select
                    value={testData.currency}
                    onChange={(e) => setTestData({ ...testData, currency: e.target.value })}
                    label="Валюта"
                  >
                    <MenuItem value="UZS">UZS (Узбекский сум)</MenuItem>
                    <MenuItem value="KZT">KZT (Казахский тенге)</MenuItem>
                    <MenuItem value="USD">USD (Доллар США)</MenuItem>
                  </Select>
                </FormControl>
                
                <TextField
                  fullWidth
                  label="Описание"
                  multiline
                  rows={2}
                  value={testData.description}
                  onChange={(e) => setTestData({ ...testData, description: e.target.value })}
                  sx={{ mb: 3 }}
                />
                
                {!isAuthenticated ? (
                  <Button
                    variant="outlined"
                    color="warning"
                    size="large"
                    fullWidth
                    onClick={handleTestAuth}
                    sx={{ mb: 2 }}
                  >
                    🔐 Открыть вход
                  </Button>
                ) : (
                  <Box sx={{ mb: 2 }}>
                    <Alert severity="success" sx={{ mb: 1 }}>
                      ✅ Авторизован для тестирования
                    </Alert>
                    <Button
                      variant="outlined"
                      color="secondary"
                      size="small"
                      fullWidth
                      onClick={() => {
                        setToken(null);
                        setIsAuthenticated(false);
                        setResult({ type: 'info', message: 'Авторизация сброшена' });
                      }}
                    >
                      🚪 Выйти
                    </Button>
                  </Box>
                )}
                
                <Button
                  variant="contained"
                  color="primary"
                  size="large"
                  fullWidth
                  onClick={startTest}
                  startIcon={<CreditCardIcon />}
                  disabled={showWidget || !isAuthenticated}
                >
                  {showWidget ? 'Тест запущен...' : isAuthenticated ? 'Запустить тест' : 'Требуется авторизация'}
                </Button>
              </Box>
            </CardContent>
          </Card>

          {/* Результаты */}
          {result && (
            <Card sx={{ mt: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Результат теста
                </Typography>
                
                <Alert 
                  severity={result.type === 'success' ? 'success' : result.type === 'error' ? 'error' : 'info'}
                  sx={{ mb: 2 }}
                >
                  {result.message}
                </Alert>
                
                {result.data && (
                  <Box sx={{ p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                    <Typography variant="body2" component="pre" sx={{ fontSize: '0.75rem' }}>
                      {JSON.stringify(result.data, null, 2)}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          )}
        </Grid>

        {/* Виджет платежа */}
        <Grid item xs={12} md={8}>
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
            <Card sx={{ height: '400px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CardContent>
                <Box textAlign="center">
                  <CreditCardIcon sx={{ fontSize: 80, color: 'grey.400', mb: 2 }} />
                  <Typography variant="h6" color="textSecondary">
                    Нажмите &quot;Запустить тест&quot; для отображения виджета
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* Информация о системе */}
      <Card sx={{ mt: 4 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Информация о тестируемой системе
          </Typography>
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center" p={2}>
                <Typography variant="h4" color="primary">3</Typography>
                <Typography variant="body2" color="textSecondary">Провайдера</Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center" p={2}>
                <Typography variant="h4" color="success.main">2</Typography>
                <Typography variant="body2" color="textSecondary">Валюты</Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center" p={2}>
                <Typography variant="h4" color="warning.main">100%</Typography>
                <Typography variant="body2" color="textSecondary">Готовность</Typography>
              </Box>
            </Grid>
            
            <Grid item xs={12} sm={6} md={3}>
              <Box textAlign="center" p={2}>
                <Typography variant="h4" color="info.main">✓</Typography>
                <Typography variant="body2" color="textSecondary">Webhook</Typography>
              </Box>
            </Grid>
          </Grid>
          
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Поддерживаемые провайдеры:</strong> Click (UZS), Payme (UZS), Kaspi (KZT)
              <br />
              <strong>Backend:</strong> {getApiOrigin()}
              <br />
              <strong>Frontend:</strong> http://localhost:5173
            </Typography>
          </Alert>
        </CardContent>
      </Card>
    </Container>
  );
};

export default PaymentTest;
