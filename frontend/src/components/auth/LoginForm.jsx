import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider,
  Link,
  IconButton,
  InputAdornment,
  Paper,
  Grid
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  Login,
  Person,
  Lock,
  Email,
  Phone,
  Security,
  Error,
  CheckCircle
} from '@mui/icons-material';

const LoginForm = ({ onLogin, onRegister, onForgotPassword }) => {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    loginType: 'username' // username, phone, email
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const loginTypes = [
    { value: 'username', label: 'Имя пользователя', icon: <Person /> },
    { value: 'email', label: 'Email', icon: <Email /> },
    { value: 'phone', label: 'Телефон', icon: <Phone /> }
  ];

  const handleInputChange = (field) => (event) => {
    setFormData(prev => ({
      ...prev,
      [field]: event.target.value
    }));
    // Очищаем ошибки при изменении
    if (error) setError('');
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: formData.username,
          password: formData.password
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Сохраняем токен
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('token_type', data.token_type);
        
        if (rememberMe) {
          localStorage.setItem('remembered_user', formData.username);
        }

        setSuccess('Успешный вход в систему!');
        
        // Вызываем callback с данными пользователя
        if (onLogin) {
          onLogin(data);
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка входа в систему');
      }
    } catch (err) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = () => {
    if (onRegister) {
      onRegister();
    }
  };

  const handleForgotPassword = () => {
    if (onForgotPassword) {
      onForgotPassword();
    }
  };

  const handleTwoFactor = () => {
    // Переход к двухфакторной аутентификации
    window.location.href = '/two-factor';
  };

  useEffect(() => {
    // Загружаем сохраненного пользователя
    const rememberedUser = localStorage.getItem('remembered_user');
    if (rememberedUser) {
      setFormData(prev => ({ ...prev, username: rememberedUser }));
      setRememberMe(true);
    }
  }, []);

  const getInputLabel = () => {
    switch (formData.loginType) {
      case 'email': return 'Email адрес';
      case 'phone': return 'Номер телефона';
      default: return 'Имя пользователя';
    }
  };

  const getInputType = () => {
    switch (formData.loginType) {
      case 'email': return 'email';
      case 'phone': return 'tel';
      default: return 'text';
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: 2
      }}
    >
      <Card sx={{ maxWidth: 450, width: '100%', boxShadow: 3 }}>
        <CardContent sx={{ p: 4 }}>
          {/* Заголовок */}
          <Box textAlign="center" mb={3}>
            <Box
              sx={{
                width: 60,
                height: 60,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mx: 'auto',
                mb: 2
              }}
            >
              <Login color="white" fontSize="large" />
            </Box>
            <Typography variant="h4" component="h1" gutterBottom>
              Вход в систему
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Система управления клиникой
            </Typography>
          </Box>

          {/* Алерты */}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} icon={<Error />}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mb: 2 }} icon={<CheckCircle />}>
              {success}
            </Alert>
          )}

          {/* Форма входа */}
          <Box component="form" onSubmit={handleLogin}>
            {/* Тип входа */}
            <FormControl fullWidth sx={{ mb: 3 }}>
              <InputLabel>Тип входа</InputLabel>
              <Select
                value={formData.loginType}
                onChange={handleInputChange('loginType')}
                label="Тип входа"
              >
                {loginTypes.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    <Box display="flex" alignItems="center">
                      {type.icon}
                      <Typography sx={{ ml: 1 }}>{type.label}</Typography>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Поле ввода */}
            <TextField
              fullWidth
              label={getInputLabel()}
              type={getInputType()}
              value={formData.username}
              onChange={handleInputChange('username')}
              required
              sx={{ mb: 3 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    {loginTypes.find(t => t.value === formData.loginType)?.icon}
                  </InputAdornment>
                )
              }}
            />

            {/* Пароль */}
            <TextField
              fullWidth
              label="Пароль"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={handleInputChange('password')}
              required
              sx={{ mb: 3 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Lock />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                )
              }}
            />

            {/* Дополнительные опции */}
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
              <Box display="flex" alignItems="center">
                <input
                  type="checkbox"
                  id="rememberMe"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{ marginRight: 8 }}
                />
                <label htmlFor="rememberMe">
                  <Typography variant="body2">Запомнить меня</Typography>
                </label>
              </Box>
              <Link
                component="button"
                variant="body2"
                onClick={handleForgotPassword}
                sx={{ textDecoration: 'none' }}
              >
                Забыли пароль?
              </Link>
            </Box>

            {/* Кнопка входа */}
            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading}
              sx={{ mb: 2, py: 1.5 }}
            >
              {loading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                <>
                  <Login sx={{ mr: 1 }} />
                  Войти
                </>
              )}
            </Button>

            <Divider sx={{ my: 2 }}>
              <Typography variant="body2" color="text.secondary">
                или
              </Typography>
            </Divider>

            {/* Дополнительные кнопки */}
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={handleRegister}
                  startIcon={<Person />}
                >
                  Регистрация
                </Button>
              </Grid>
              <Grid item xs={6}>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={handleTwoFactor}
                  startIcon={<Security />}
                >
                  2FA
                </Button>
              </Grid>
            </Grid>
          </Box>

          {/* Информация о системе */}
          <Box mt={4} textAlign="center">
            <Typography variant="caption" color="text.secondary">
              Система управления клиникой v1.0
            </Typography>
            <br />
            <Typography variant="caption" color="text.secondary">
              © 2025 Все права защищены
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default LoginForm;

