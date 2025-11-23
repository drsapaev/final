import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Input,
  Select,
  Option,
  Alert,
  Badge,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
} from '../ui/macos';
import {
  QrCode,
  RefreshCw,
  Play,
  Square,
  Eye,
  Printer,
  Download,
  User,
  Phone,
  Clock,
  CheckCircle,
  BarChart3,
  X,
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { useQueueManager } from '../../hooks/useQueueManager';

const OnlineQueueManager = () => {
  // Используем кастомный хук вместо прямых API вызовов
  const {
    loading,
    error,
    success,
    statistics,
    specialists,
    queueData,
    qrData,
    generateQRCode,
    loadTodayQueue,
    loadStatistics,
    openQueue,
    callPatient,
    clearMessages,
    setError,
    setSuccess,
    setQueueData,
    setStatistics
  } = useQueueManager();
  
  // Локальные состояния для UI
  const [qrDialog, setQrDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedSpecialist, setSelectedSpecialist] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);
  
  // Автообновление очереди
  useEffect(() => {
    let interval;
    if (autoRefresh && selectedSpecialist) {
      interval = setInterval(() => {
        loadTodayQueue(selectedSpecialist);
        loadStatistics(selectedSpecialist, selectedDate);
      }, 10000); // Обновляем каждые 10 секунд
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, selectedSpecialist, selectedDate, loadTodayQueue, loadStatistics]);

  // Обработчики для UI - используют методы из хука
  const handleGenerateQR = async () => {
    await generateQRCode(selectedDate, selectedSpecialist);
  };

  const handleOpenQueue = async () => {
    const success = await openQueue(selectedSpecialist);
    if (success) {
      loadTodayQueue(selectedSpecialist);
    }
  };

  const handleCallPatient = async (entryId) => {
    const success = await callPatient(entryId);
    if (success) {
      loadTodayQueue(selectedSpecialist);
    }
  };

  const downloadQR = () => {
    if (!qrData) return;
    
    const svg = document.querySelector('#qr-code-svg');
    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();
    
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.drawImage(img, 0, 0);
      
      const link = document.createElement('a');
      link.download = `qr-queue-${selectedDate}-${qrData.specialist_name}.png`;
      link.href = canvas.toDataURL();
      link.click();
    };
    
    img.src = 'data:image/svg+xml;base64,' + btoa(svgData);
  };

  const formatTime = (dateString) => {
    return new Date(dateString).toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'waiting': return 'primary';
      case 'called': return 'warning';
      case 'completed': return 'success';
      case 'cancelled': return 'error';
      default: return 'default';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'waiting': return 'Ожидает';
      case 'called': return 'Вызван';
      case 'completed': return 'Завершен';
      case 'cancelled': return 'Отменен';
      default: return status;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Управление онлайн-очередью
      </Typography>

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
        {/* Статистика */}
        {statistics && (
          <Grid item xs={12}>
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <BarChartIcon sx={{ mr: 1 }} />
                  Статистика очереди
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
                      <Typography variant="h4" color="primary.contrastText">
                        {statistics.total_entries}
                      </Typography>
                      <Typography variant="body2" color="primary.contrastText">
                        Всего записей
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'warning.light', borderRadius: 1 }}>
                      <Typography variant="h4" color="warning.contrastText">
                        {statistics.waiting}
                      </Typography>
                      <Typography variant="body2" color="warning.contrastText">
                        Ожидают
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'success.light', borderRadius: 1 }}>
                      <Typography variant="h4" color="success.contrastText">
                        {statistics.completed}
                      </Typography>
                      <Typography variant="body2" color="success.contrastText">
                        Завершено
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
                      <Typography variant="h4" color="info.contrastText">
                        {statistics.available_slots}
                      </Typography>
                      <Typography variant="body2" color="info.contrastText">
                        Свободных мест
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Панель управления */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Панель управления
              </Typography>

              <FormControl fullWidth margin="normal">
                <InputLabel>Специалист</InputLabel>
                <Select
                  value={selectedSpecialist}
                  onChange={(e) => {
                    setSelectedSpecialist(e.target.value);
                    setQueueData(null);
                    setStatistics(null);
                    // Загружаем статистику для нового специалиста
                    if (e.target.value) {
                      setTimeout(() => loadStatistics(), 100);
                    }
                  }}
                  label="Специалист"
                >
                  {specialists.map((specialist) => (
                    <MenuItem key={specialist.id} value={specialist.id}>
                      {specialist.full_name || specialist.username}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <TextField
                fullWidth
                type="date"
                label="Дата"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                margin="normal"
                InputLabelProps={{ shrink: true }}
              />

              <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Button
                  variant="contained"
                  startIcon={<QrIcon />}
                  onClick={() => setQrDialog(true)}
                  disabled={!selectedSpecialist || loading}
                  fullWidth
                >
                  Генерировать QR код
                </Button>

                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={loadTodayQueue}
                  disabled={!selectedSpecialist || loading}
                  fullWidth
                >
                  Обновить очередь
                </Button>

                <Button
                  variant="contained"
                  color="success"
                  startIcon={<StartIcon />}
                  onClick={handleOpenQueue}
                  disabled={!selectedSpecialist || loading || queueData?.is_open}
                  fullWidth
                >
                  {queueData?.is_open ? 'Прием открыт' : 'Открыть прием'}
                </Button>
              </Box>

              <Box sx={{ mt: 2 }}>
                <FormControl component="fieldset">
                  <Button
                    variant={autoRefresh ? "contained" : "outlined"}
                    size="small"
                    onClick={() => setAutoRefresh(!autoRefresh)}
                    startIcon={autoRefresh ? <StopIcon /> : <StartIcon />}
                  >
                    {autoRefresh ? 'Остановить' : 'Автообновление'}
                  </Button>
                </FormControl>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Текущая очередь */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">
                  Текущая очередь
                  {queueData && (
                    <Chip
                      label={queueData.is_open ? 'Прием открыт' : 'Онлайн-запись'}
                      color={queueData.is_open ? 'success' : 'primary'}
                      size="small"
                      sx={{ ml: 1 }}
                    />
                  )}
                </Typography>
                
                {queueData && (
                  <Box>
                    <Chip
                      label={`Всего: ${queueData.total_entries}`}
                      variant="outlined"
                      size="small"
                      sx={{ mr: 1 }}
                    />
                    <Chip
                      label={`Ожидают: ${queueData.waiting_entries}`}
                      color="primary"
                      size="small"
                    />
                  </Box>
                )}
              </Box>

              {!selectedSpecialist ? (
                <Alert severity="info">
                  Выберите специалиста для просмотра очереди
                </Alert>
              ) : !queueData ? (
                <Alert severity="warning">
                  Очередь не найдена. Создайте QR код для начала записи.
                </Alert>
              ) : queueData.entries.length === 0 ? (
                <Alert severity="info">
                  Очередь пуста
                </Alert>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow sx={{ bgcolor: 'primary.main' }}>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>№</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Пациент</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Телефон</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Время записи</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Статус</TableCell>
                        <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Действия</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {queueData.entries.map((entry, index) => (
                        <TableRow 
                          key={entry.id}
                          sx={{ 
                            '&:hover': { bgcolor: 'action.hover' },
                            '&:nth-of-type(odd)': { bgcolor: 'action.selected' },
                            transition: 'all 0.3s ease',
                            animation: `slideIn 0.5s ease ${index * 0.1}s both`,
                            '@keyframes slideIn': {
                              from: {
                                opacity: 0,
                                transform: 'translateX(-20px)'
                              },
                              to: {
                                opacity: 1,
                                transform: 'translateX(0)'
                              }
                            }
                          }}
                        >
                          <TableCell>
                            <Box sx={{ 
                              display: 'flex', 
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: 40,
                              height: 40,
                              borderRadius: '50%',
                              bgcolor: entry.status === 'called' ? 'warning.main' : 'primary.main',
                              color: 'white',
                              fontWeight: 'bold',
                              fontSize: '1.1rem',
                              animation: entry.status === 'called' ? 'pulse 2s infinite' : 'none',
                              '@keyframes pulse': {
                                '0%': { transform: 'scale(1)' },
                                '50%': { transform: 'scale(1.1)' },
                                '100%': { transform: 'scale(1)' }
                              }
                            }}>
                              {entry.number}
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <PersonIcon sx={{ mr: 1, color: 'text.secondary' }} />
                              <Typography variant="body2" fontWeight="medium">
                                {entry.patient_name || 'Не указано'}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <PhoneIcon sx={{ mr: 1, color: 'text.secondary' }} />
                              <Typography variant="body2" color="text.secondary">
                                {entry.phone || 'Не указан'}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                              <TimeIcon sx={{ mr: 1, color: 'text.secondary' }} />
                              <Typography variant="body2" color="text.secondary">
                                {formatTime(entry.created_at)}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={getStatusText(entry.status)}
                              color={getStatusColor(entry.status)}
                              size="small"
                              sx={{ 
                                fontWeight: 'medium',
                                animation: entry.status === 'called' ? 'glow 2s infinite' : 'none',
                                '@keyframes glow': {
                                  '0%, 100%': { boxShadow: '0 0 5px rgba(255, 152, 0, 0.5)' },
                                  '50%': { boxShadow: '0 0 20px rgba(255, 152, 0, 0.8)' }
                                }
                              }}
                            />
                          </TableCell>
                          <TableCell>
                            {entry.status === 'waiting' && (
                              <Tooltip title="Вызвать пациента">
                                <IconButton
                                  size="small"
                                  onClick={() => handleCallPatient(entry.id)}
                                  disabled={loading}
                                  sx={{ 
                                    bgcolor: 'success.main',
                                    color: 'white',
                                    '&:hover': { bgcolor: 'success.dark' },
                                    '&:disabled': { bgcolor: 'action.disabled' }
                                  }}
                                >
                                  <StartIcon />
                                </IconButton>
                              </Tooltip>
                            )}
                            {entry.status === 'called' && (
                              <Chip 
                                label="Вызван" 
                                color="warning" 
                                size="small"
                                icon={<StartIcon />}
                              />
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Диалог генерации QR кода */}
      <Dialog open={qrDialog} onClose={() => setQrDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Генерация QR кода для онлайн-очереди</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <TextField
              fullWidth
              type="date"
              label="Дата"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              margin="normal"
              InputLabelProps={{ shrink: true }}
            />

            <FormControl fullWidth margin="normal">
              <InputLabel>Специалист</InputLabel>
              <Select
                value={selectedSpecialist}
                onChange={(e) => setSelectedSpecialist(e.target.value)}
                label="Специалист"
              >
                {specialists.map((specialist) => (
                  <MenuItem key={specialist.id} value={specialist.id}>
                    {specialist.full_name || specialist.username}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {qrData && (
              <Box sx={{ mt: 3, textAlign: 'center' }}>
                <Typography variant="h6" gutterBottom>
                  QR код для записи в очередь
                </Typography>
                
                <Box sx={{ p: 2, border: '1px solid #ddd', borderRadius: 1, display: 'inline-block' }}>
                  <QRCodeSVG
                    id="qr-code-svg"
                    value={`${window.location.origin}/queue/join?token=${qrData.token}`}
                    size={200}
                    level="M"
                    includeMargin={true}
                  />
                </Box>

                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Специалист: {qrData.specialist_name}
                  <br />
                  Дата: {new Date(qrData.day).toLocaleDateString('ru-RU')}
                  <br />
                  Действует до: {formatTime(qrData.expires_at)}
                </Typography>

                <Box sx={{ mt: 2, display: 'flex', gap: 1, justifyContent: 'center' }}>
                  <Button
                    variant="outlined"
                    startIcon={<DownloadIcon />}
                    onClick={downloadQR}
                  >
                    Скачать
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<PrintIcon />}
                    onClick={() => window.print()}
                  >
                    Печать
                  </Button>
                </Box>
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setQrDialog(false)}>
            Отмена
          </Button>
          <Button
            onClick={handleGenerateQR}
            variant="contained"
            disabled={!selectedDate || !selectedSpecialist || loading}
          >
            {loading ? <CircularProgress size={20} /> : 'Генерировать'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default OnlineQueueManager;

