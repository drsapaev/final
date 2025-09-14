import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { 
  Container, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  Box, 
  Alert, 
  CircularProgress,
  Card,
  CardContent,
  Divider
} from '@mui/material';
import { 
  QueueMusic as QueueIcon,
  Phone as PhoneIcon,
  Telegram as TelegramIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon
} from '@mui/icons-material';
import { api as apiClient } from '../api/client';

const QueueJoin = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token');
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    phone: '',
    telegram_id: '',
    patient_name: ''
  });

  // Проверка токена при загрузке
  useEffect(() => {
    if (!token) {
      setError('Недействительная ссылка. Токен не найден.');
    }
  }, [token]);

  const handleInputChange = (field) => (event) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
  };

  const formatPhone = (phone) => {
    // Убираем все нецифровые символы
    const cleaned = phone.replace(/\D/g, '');
    
    // Форматируем для Узбекистана (+998)
    if (cleaned.startsWith('998')) {
      return `+${cleaned}`;
    } else if (cleaned.startsWith('8') && cleaned.length === 9) {
      return `+998${cleaned}`;
    } else if (cleaned.length === 9) {
      return `+998${cleaned}`;
    }
    
    return `+998${cleaned}`;
  };

  const validateForm = () => {
    if (!formData.phone && !formData.telegram_id) {
      setError('Укажите телефон или Telegram ID');
      return false;
    }
    
    if (formData.phone && formData.phone.length < 13) {
      setError('Неверный формат телефона');
      return false;
    }
    
    if (!formData.patient_name.trim()) {
      setError('Укажите ваше ФИО');
      return false;
    }
    
    return true;
  };

  const handleJoinQueue = async () => {
    setError('');
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    
    try {
      const requestData = {
        token,
        patient_name: formData.patient_name.trim(),
      };
      
      if (formData.phone) {
        requestData.phone = formatPhone(formData.phone);
      }
      
      if (formData.telegram_id) {
        requestData.telegram_id = formData.telegram_id.trim();
      }
      
      const response = await apiClient.post('/queue/join', requestData);
      
      if (response.data.success) {
        setResult(response.data);
      } else {
        setError(response.data.message || 'Ошибка при записи в очередь');
      }
    } catch (err) {
      console.error('Queue join error:', err);
      setError(
        err.response?.data?.detail || 
        err.response?.data?.message || 
        'Произошла ошибка при записи в очередь'
      );
    } finally {
      setLoading(false);
    }
  };

  const handlePhoneChange = (event) => {
    const value = event.target.value;
    const formatted = formatPhone(value);
    setFormData(prev => ({
      ...prev,
      phone: formatted
    }));
  };

  if (!token) {
    return (
      <Container maxWidth="sm" sx={{ mt: 4 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          <ErrorIcon color="error" sx={{ fontSize: 60, mb: 2 }} />
          <Typography variant="h5" color="error" gutterBottom>
            Недействительная ссылка
          </Typography>
          <Typography variant="body1" color="text.secondary">
            QR код поврежден или устарел. Обратитесь в регистратуру.
          </Typography>
          <Button 
            variant="contained" 
            onClick={() => navigate('/')}
            sx={{ mt: 3 }}
          >
            На главную
          </Button>
        </Paper>
      </Container>
    );
  }

  if (result) {
    return (
      <Container maxWidth="sm" sx={{ mt: 4 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          <SuccessIcon color="success" sx={{ fontSize: 60, mb: 2 }} />
          
          <Typography variant="h4" color="success.main" gutterBottom>
            {result.duplicate ? 'Вы уже записаны!' : 'Успешно записаны!'}
          </Typography>
          
          <Card sx={{ mt: 3, mb: 3 }}>
            <CardContent>
              <Typography variant="h2" color="primary" gutterBottom>
                №{result.number}
              </Typography>
              <Typography variant="h6" gutterBottom>
                Ваш номер в очереди
              </Typography>
              
              {result.queue_info && (
                <>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="body1" gutterBottom>
                    <strong>Врач:</strong> {result.queue_info.specialist}
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    <strong>Дата:</strong> {new Date(result.queue_info.day).toLocaleDateString('ru-RU')}
                  </Typography>
                  {result.queue_info.estimated_time && (
                    <Typography variant="body2" color="text.secondary">
                      {result.queue_info.estimated_time}
                    </Typography>
                  )}
                </>
              )}
            </CardContent>
          </Card>
          
          <Alert severity="info" sx={{ mb: 3, textAlign: 'left' }}>
            <Typography variant="body2">
              <strong>Важно:</strong>
              <br />• Придите к открытию приема
              <br />• Возьмите с собой документы
              <br />• При опоздании номер может быть аннулирован
            </Typography>
          </Alert>
          
          <Button 
            variant="contained" 
            onClick={() => navigate('/')}
            size="large"
          >
            Готово
          </Button>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 4 }}>
      <Paper elevation={3} sx={{ p: 4 }}>
        <Box textAlign="center" mb={3}>
          <QueueIcon color="primary" sx={{ fontSize: 60, mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Онлайн-очередь
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Заполните форму для записи в очередь
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
        )}

        <Box component="form" noValidate>
          <TextField
            fullWidth
            label="Ваше ФИО"
            value={formData.patient_name}
            onChange={handleInputChange('patient_name')}
            margin="normal"
            required
            placeholder="Иванов Иван Иванович"
          />

          <TextField
            fullWidth
            label="Номер телефона"
            value={formData.phone}
            onChange={handlePhoneChange}
            margin="normal"
            placeholder="+998 90 123 45 67"
            InputProps={{
              startAdornment: <PhoneIcon color="action" sx={{ mr: 1 }} />
            }}
            helperText="Формат: +998 XX XXX XX XX"
          />

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, mb: 1, textAlign: 'center' }}>
            или
          </Typography>

          <TextField
            fullWidth
            label="Telegram ID (опционально)"
            value={formData.telegram_id}
            onChange={handleInputChange('telegram_id')}
            margin="normal"
            placeholder="@username или ID"
            InputProps={{
              startAdornment: <TelegramIcon color="action" sx={{ mr: 1 }} />
            }}
            helperText="Если у вас есть Telegram"
          />

          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={handleJoinQueue}
            disabled={loading}
            sx={{ mt: 3, py: 1.5 }}
          >
            {loading ? (
              <>
                <CircularProgress size={20} sx={{ mr: 1 }} />
                Записываемся...
              </>
            ) : (
              'Записаться в очередь'
            )}
          </Button>
        </Box>

        <Alert severity="info" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Время работы онлайн-записи:</strong>
            <br />с 07:00 до открытия приема
            <br />Один номер на телефон/Telegram
          </Typography>
        </Alert>
      </Paper>
    </Container>
  );
};

export default QueueJoin;
