import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Divider
} from '@mui/material';
import {
  Security,
  QrCode,
  Phone,
  Email,
  CheckCircle,
  Error,
  Refresh,
  Delete,
  Add
} from '@mui/icons-material';

const TwoFactorManager = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [twoFactorMethod, setTwoFactorMethod] = useState('sms');
  const [qrCode, setQrCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [verificationCode, setVerificationCode] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showSetupDialog, setShowSetupDialog] = useState(false);

  const methods = [
    { value: 'sms', label: 'SMS', icon: <Phone />, description: 'Код отправляется на номер телефона' },
    { value: 'email', label: 'Email', icon: <Email />, description: 'Код отправляется на email' },
    { value: 'app', label: 'Приложение', icon: <QrCode />, description: 'Использование приложения-аутентификатора' }
  ];

  const steps = [
    'Выбор метода',
    'Настройка',
    'Подтверждение',
    'Завершение'
  ];

  useEffect(() => {
    // Загружаем текущее состояние 2FA
    loadTwoFactorStatus();
  }, []);

  const loadTwoFactorStatus = async () => {
    try {
      // Здесь должен быть API запрос для получения статуса 2FA
      const response = await fetch('/api/v1/two-factor/status');
      const data = await response.json();
      setTwoFactorEnabled(data.enabled);
      setTwoFactorMethod(data.method);
    } catch (error) {
      console.error('Ошибка загрузки статуса 2FA:', error);
    }
  };

  const handleSetupTwoFactor = () => {
    setShowSetupDialog(true);
    setActiveStep(0);
    setError('');
    setSuccess('');
  };

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleMethodChange = (method) => {
    setTwoFactorMethod(method);
  };

  const handleSetupMethod = async () => {
    setLoading(true);
    setError('');
    
    try {
      let response;
      
      switch (twoFactorMethod) {
        case 'sms':
          response = await fetch('/api/v1/two-factor/setup-sms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone_number: phoneNumber })
          });
          break;
        case 'email':
          response = await fetch('/api/v1/two-factor/setup-email', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
          });
          break;
        case 'app':
          response = await fetch('/api/v1/two-factor/setup-app', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          const data = await response.json();
          setQrCode(data.qr_code);
          setBackupCodes(data.backup_codes);
          break;
      }
      
      if (response.ok) {
        setSuccess('Метод 2FA настроен. Проверьте код подтверждения.');
        handleNext();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка настройки 2FA');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/v1/two-factor/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          code: verificationCode,
          method: twoFactorMethod 
        })
      });
      
      if (response.ok) {
        setSuccess('2FA успешно активирован!');
        setTwoFactorEnabled(true);
        handleNext();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Неверный код подтверждения');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleDisableTwoFactor = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await fetch('/api/v1/two-factor/disable', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        setSuccess('2FA отключен');
        setTwoFactorEnabled(false);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка отключения 2FA');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const renderStepContent = (step) => {
    switch (step) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Выберите метод двухфакторной аутентификации
            </Typography>
            <List>
              {methods.map((method) => (
                <ListItem
                  key={method.value}
                  button
                  onClick={() => handleMethodChange(method.value)}
                  selected={twoFactorMethod === method.value}
                >
                  <ListItemIcon>{method.icon}</ListItemIcon>
                  <ListItemText
                    primary={method.label}
                    secondary={method.description}
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        );
      
      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Настройка {methods.find(m => m.value === twoFactorMethod)?.label}
            </Typography>
            
            {twoFactorMethod === 'sms' && (
              <TextField
                fullWidth
                label="Номер телефона"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+7 (999) 123-45-67"
                margin="normal"
              />
            )}
            
            {twoFactorMethod === 'email' && (
              <TextField
                fullWidth
                label="Email адрес"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                margin="normal"
              />
            )}
            
            {twoFactorMethod === 'app' && qrCode && (
              <Box textAlign="center" mt={2}>
                <Typography variant="body2" gutterBottom>
                  Отсканируйте QR-код в приложении-аутентификаторе:
                </Typography>
                <Box 
                  component="img" 
                  src={qrCode} 
                  alt="QR Code" 
                  sx={{ maxWidth: 200, border: 1, borderColor: 'divider' }}
                />
                <Typography variant="caption" display="block" mt={1}>
                  Или введите код вручную: {backupCodes[0]}
                </Typography>
              </Box>
            )}
          </Box>
        );
      
      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Подтверждение кода
            </Typography>
            <TextField
              fullWidth
              label="Код подтверждения"
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="Введите 6-значный код"
              margin="normal"
            />
          </Box>
        );
      
      case 3:
        return (
          <Box textAlign="center">
            <CheckCircle color="success" sx={{ fontSize: 64, mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              Двухфакторная аутентификация активирована!
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Теперь для входа в систему потребуется дополнительный код подтверждения
            </Typography>
            
            {backupCodes.length > 0 && (
              <Box mt={3}>
                <Typography variant="subtitle2" gutterBottom>
                  Резервные коды (сохраните их в безопасном месте):
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1} justifyContent="center">
                  {backupCodes.map((code, index) => (
                    <Chip key={index} label={code} variant="outlined" />
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        );
      
      default:
        return null;
    }
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          <Security color="primary" sx={{ mr: 1 }} />
          <Typography variant="h6" component="h3">
            Двухфакторная аутентификация
          </Typography>
        </Box>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

        <Box mb={3}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            Двухфакторная аутентификация добавляет дополнительный уровень безопасности к вашему аккаунту
          </Typography>
          
          <Box display="flex" alignItems="center" gap={2} mt={2}>
            <Chip
              icon={twoFactorEnabled ? <CheckCircle /> : <Error />}
              label={twoFactorEnabled ? 'Активирована' : 'Не активирована'}
              color={twoFactorEnabled ? 'success' : 'error'}
              variant="outlined"
            />
            {twoFactorEnabled && (
              <Chip
                label={`Метод: ${methods.find(m => m.value === twoFactorMethod)?.label}`}
                variant="outlined"
              />
            )}
          </Box>
        </Box>

        <Box display="flex" gap={2}>
          {!twoFactorEnabled ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={handleSetupTwoFactor}
            >
              Настроить 2FA
            </Button>
          ) : (
            <Button
              variant="outlined"
              color="error"
              startIcon={<Delete />}
              onClick={handleDisableTwoFactor}
              disabled={loading}
            >
              Отключить 2FA
            </Button>
          )}
          
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={loadTwoFactorStatus}
            disabled={loading}
          >
            Обновить
          </Button>
        </Box>

        <Dialog
          open={showSetupDialog}
          onClose={() => setShowSetupDialog(false)}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>Настройка двухфакторной аутентификации</DialogTitle>
          <DialogContent>
            <Stepper activeStep={activeStep} orientation="vertical">
              {steps.map((label, index) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                  <StepContent>
                    {renderStepContent(index)}
                    <Box mt={2}>
                      <Button
                        variant="contained"
                        onClick={index === 1 ? handleSetupMethod : index === 2 ? handleVerifyCode : handleNext}
                        disabled={loading}
                        sx={{ mr: 1 }}
                      >
                        {index === steps.length - 1 ? 'Завершить' : 'Далее'}
                      </Button>
                      {index > 0 && (
                        <Button onClick={handleBack} disabled={loading}>
                          Назад
                        </Button>
                      )}
                    </Box>
                  </StepContent>
                </Step>
              ))}
            </Stepper>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowSetupDialog(false)}>
              Отмена
            </Button>
          </DialogActions>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default TwoFactorManager;
