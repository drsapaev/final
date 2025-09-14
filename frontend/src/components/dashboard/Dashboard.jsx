import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Paper,
  Divider,
  LinearProgress,
  Alert,
  CircularProgress
} from '@mui/material';
import {
  People,
  Event,
  AttachMoney,
  TrendingUp,
  Notifications,
  Security,
  FileUpload,
  Telegram,
  Email,
  Phone,
  Dashboard as DashboardIcon,
  Refresh,
  MoreVert,
  CheckCircle,
  Warning,
  Error
} from '@mui/icons-material';
// import AdvancedCharts from './AdvancedCharts';

const Dashboard = ({ user }) => {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    loadDashboardData();
    // Обновляем данные каждые 5 минут
    const interval = setInterval(loadDashboardData, 300000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      const [analyticsRes, notificationsRes, filesRes, telegramRes] = await Promise.all([
        fetch('/api/v1/analytics/dashboard', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/notifications/history/stats', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/files/stats', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/telegram/bot-status', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      const analyticsData = analyticsRes.ok ? await analyticsRes.json() : null;
      const notificationsData = notificationsRes.ok ? await notificationsRes.json() : null;
      const filesData = filesRes.ok ? await filesRes.json() : null;
      const telegramData = telegramRes.ok ? await telegramRes.json() : null;

      setDashboardData({
        analytics: analyticsData,
        notifications: notificationsData,
        files: filesData,
        telegram: telegramData
      });
      setLastUpdate(new Date());
    } catch (err) {
      setError('Ошибка загрузки данных дашборда');
    } finally {
      setLoading(false);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Доброе утро';
    if (hour < 18) return 'Добрый день';
    return 'Добрый вечер';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'success';
      case 'warning': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active': return <CheckCircle />;
      case 'warning': return <Warning />;
      case 'error': return <Error />;
      default: return <Notifications />;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" onClick={loadDashboardData}>
          Повторить
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Заголовок */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {getGreeting()}, {user?.full_name || user?.username || 'Пользователь'}!
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Последнее обновление: {lastUpdate.toLocaleTimeString()}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadDashboardData}
          disabled={loading}
        >
          Обновить
        </Button>
      </Box>

      {/* Основные метрики */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Avatar sx={{ bgcolor: 'primary.main', mr: 2 }}>
                  <People />
                </Avatar>
                <Box>
                  <Typography variant="h4">
                    {dashboardData?.analytics?.overview?.total_patients || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Пациентов
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Avatar sx={{ bgcolor: 'success.main', mr: 2 }}>
                  <Event />
                </Avatar>
                <Box>
                  <Typography variant="h4">
                    {dashboardData?.analytics?.today?.appointments || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Записей сегодня
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Avatar sx={{ bgcolor: 'warning.main', mr: 2 }}>
                  <AttachMoney />
                </Avatar>
                <Box>
                  <Typography variant="h4">
                    {dashboardData?.analytics?.overview?.total_payments || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Платежей
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center">
                <Avatar sx={{ bgcolor: 'info.main', mr: 2 }}>
                  <TrendingUp />
                </Avatar>
                <Box>
                  <Typography variant="h4">
                    {dashboardData?.files?.total_files || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Файлов
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Графики и статистика */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Статистика записей
              </Typography>
              <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Typography variant="body1" color="text.secondary">
                  График статистики записей (компонент AdvancedCharts в разработке)
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Статус системы
              </Typography>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <DashboardIcon color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Основная система"
                    secondary="Работает нормально"
                  />
                  <Chip label="Активна" color="success" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Telegram color={dashboardData?.telegram?.bot_active ? "success" : "warning"} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Telegram бот"
                    secondary={dashboardData?.telegram?.bot_active ? "Активен" : "Неактивен"}
                  />
                  <Chip 
                    label={dashboardData?.telegram?.bot_active ? "Активен" : "Неактивен"} 
                    color={dashboardData?.telegram?.bot_active ? "success" : "warning"} 
                    size="small" 
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Email color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Email уведомления"
                    secondary="Работают"
                  />
                  <Chip label="Активны" color="success" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <FileUpload color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Файловая система"
                    secondary="Доступна"
                  />
                  <Chip label="Активна" color="success" size="small" />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Последние уведомления */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">
                  Последние уведомления
                </Typography>
                <IconButton>
                  <MoreVert />
                </IconButton>
              </Box>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <Notifications color="info" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Система обновлена"
                    secondary="2 минуты назад"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Security color="warning" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Новый пользователь зарегистрирован"
                    secondary="15 минут назад"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Event color="success" />
                  </ListItemIcon>
                  <ListItemText
                    primary="Запись на прием создана"
                    secondary="1 час назад"
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Быстрые действия
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<People />}
                    sx={{ py: 1.5 }}
                  >
                    Пациенты
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<Event />}
                    sx={{ py: 1.5 }}
                  >
                    Записи
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<FileUpload />}
                    sx={{ py: 1.5 }}
                  >
                    Файлы
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    fullWidth
                    variant="outlined"
                    startIcon={<Telegram />}
                    sx={{ py: 1.5 }}
                  >
                    Telegram
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
