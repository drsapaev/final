import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  Stepper,
  Step,
  StepLabel,
  StepContent
} from '@mui/material';
import {
  Security,
  Phone,
  Email,
  QrCode,
  CheckCircle,
  Error,
  Warning,
  Refresh,
  Settings,
  Add,
  Edit,
  Delete
} from '@mui/icons-material';

const TwoFactorManager = () => {
  const [twoFactorStatus, setTwoFactorStatus] = useState(null);
  const [trustedDevices, setTrustedDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showSetupDialog, setShowSetupDialog] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [qrCode, setQrCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);

  useEffect(() => {
    loadTwoFactorData();
  }, []);

  const loadTwoFactorData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      const [statusRes, devicesRes] = await Promise.all([
        fetch('/api/v1/auth/2fa/status', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/auth/2fa/trusted-devices', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setTwoFactorStatus(statusData);
      }

      if (devicesRes.ok) {
        const devicesData = await devicesRes.json();
        setTrustedDevices(devicesData.devices || devicesData || []);
      }
    } catch (err) {
      setError('Ошибка загрузки данных 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleSetup2FA = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/auth/2fa/setup', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setQrCode(data.qr_code);
        setBackupCodes(data.backup_codes);
        setShowSetupDialog(true);
      } else {
        setError('Ошибка настройки 2FA');
      }
    } catch (err) {
      setError('Ошибка настройки 2FA');
    }
  };

  const handleVerify2FA = async (code) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/auth/2fa/verify', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ code })
      });

      if (response.ok) {
        setSuccess('2FA успешно настроен');
        setShowSetupDialog(false);
        loadTwoFactorData();
      } else {
        setError('Неверный код');
      }
    } catch (err) {
      setError('Ошибка верификации');
    }
  };

  const handleRemoveDevice = async (deviceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/auth/2fa/trusted-devices/${deviceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setSuccess('Устройство удалено');
        loadTwoFactorData();
      } else {
        setError('Ошибка удаления устройства');
      }
    } catch (err) {
      setError('Ошибка удаления устройства');
    }
  };

  const steps = [
    'Сканируйте QR-код',
    'Введите код из приложения',
    'Сохраните резервные коды'
  ];

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Двухфакторная аутентификация
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadTwoFactorData}
        >
          Обновить
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Статус 2FA
              </Typography>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <Security color={twoFactorStatus?.enabled ? "success" : "error"} />
                  </ListItemIcon>
                  <ListItemText
                    primary="2FA включен"
                    secondary={twoFactorStatus?.enabled ? "Да" : "Нет"}
                  />
                  <Chip
                    label={twoFactorStatus?.enabled ? "Включен" : "Отключен"}
                    color={twoFactorStatus?.enabled ? "success" : "error"}
                    size="small"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Phone />
                  </ListItemIcon>
                  <ListItemText
                    primary="SMS уведомления"
                    secondary={twoFactorStatus?.sms_enabled ? "Включены" : "Отключены"}
                  />
                  <Chip
                    label={twoFactorStatus?.sms_enabled ? "Включены" : "Отключены"}
                    color={twoFactorStatus?.sms_enabled ? "success" : "default"}
                    size="small"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Email />
                  </ListItemIcon>
                  <ListItemText
                    primary="Email уведомления"
                    secondary={twoFactorStatus?.email_enabled ? "Включены" : "Отключены"}
                  />
                  <Chip
                    label={twoFactorStatus?.email_enabled ? "Включены" : "Отключены"}
                    color={twoFactorStatus?.email_enabled ? "success" : "default"}
                    size="small"
                  />
                </ListItem>
              </List>
              <Box mt={2}>
                <Button
                  fullWidth
                  variant="contained"
                  startIcon={<Security />}
                  onClick={handleSetup2FA}
                  disabled={twoFactorStatus?.enabled}
                >
                  {twoFactorStatus?.enabled ? '2FA уже настроен' : 'Настроить 2FA'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Доверенные устройства
              </Typography>
              <List>
                {trustedDevices.map((device) => (
                  <ListItem key={device.id}>
                    <ListItemIcon>
                      <Settings />
                    </ListItemIcon>
                    <ListItemText
                      primary={device.device_name}
                      secondary={`${device.browser} • ${device.last_used}`}
                    />
                    <IconButton
                      onClick={() => handleRemoveDevice(device.id)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </ListItem>
                ))}
                {trustedDevices.length === 0 && (
                  <ListItem>
                    <ListItemText
                      primary="Нет доверенных устройств"
                      secondary="Добавьте устройство для упрощения входа"
                    />
                  </ListItem>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Резервные коды
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Сохраните эти коды в безопасном месте. Они помогут вам войти в систему,
                если вы потеряете доступ к устройству с приложением аутентификатора.
              </Typography>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={() => setSuccess('Новые резервные коды сгенерированы')}
              >
                Сгенерировать новые коды
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={showSetupDialog} onClose={() => setShowSetupDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Настройка двухфакторной аутентификации</DialogTitle>
        <DialogContent>
          <Stepper activeStep={activeStep} orientation="vertical">
            <Step>
              <StepLabel>Сканируйте QR-код</StepLabel>
              <StepContent>
                <Box textAlign="center" py={2}>
                  {qrCode && (
                    <Box
                      component="img"
                      src={qrCode}
                      alt="QR Code"
                      sx={{ maxWidth: 200, height: 'auto' }}
                    />
                  )}
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                    Отсканируйте QR-код в приложении аутентификатора
                  </Typography>
                  <Button
                    variant="contained"
                    onClick={() => setActiveStep(1)}
                    sx={{ mt: 2 }}
                  >
                    Далее
                  </Button>
                </Box>
              </StepContent>
            </Step>
            <Step>
              <StepLabel>Введите код из приложения</StepLabel>
              <StepContent>
                <TextField
                  fullWidth
                  label="Код из приложения"
                  placeholder="000000"
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  onClick={() => setActiveStep(2)}
                  sx={{ mr: 1 }}
                >
                  Далее
                </Button>
                <Button onClick={() => setActiveStep(0)}>
                  Назад
                </Button>
              </StepContent>
            </Step>
            <Step>
              <StepLabel>Сохраните резервные коды</StepLabel>
              <StepContent>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Сохраните эти коды в безопасном месте:
                </Typography>
                <Box sx={{ fontFamily: 'monospace', bgcolor: 'grey.100', p: 2, borderRadius: 1 }}>
                  {backupCodes.map((code, index) => (
                    <Typography key={index} variant="body2">
                      {code}
                    </Typography>
                  ))}
                </Box>
                <Button
                  variant="contained"
                  onClick={() => setShowSetupDialog(false)}
                  sx={{ mt: 2 }}
                >
                  Завершить
                </Button>
              </StepContent>
            </Step>
          </Stepper>
        </DialogContent>
      </Dialog>
    </Box>
  );
};

export default TwoFactorManager;