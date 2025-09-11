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
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  IconButton,
  Chip,
  Switch,
  FormControlLabel,
  Divider,
  Grid,
  Paper
} from '@mui/material';
import {
  Telegram,
  Add,
  Edit,
  Delete,
  Send,
  Settings,
  Notifications,
  NotificationsOff,
  CheckCircle,
  Error,
  Refresh,
  QrCode
} from '@mui/icons-material';

const TelegramManager = () => {
  const [botStatus, setBotStatus] = useState(null);
  const [botConfig, setBotConfig] = useState(null);
  const [users, setUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showConfigDialog, setShowConfigDialog] = useState(false);
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [showMessageDialog, setShowMessageDialog] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [messageText, setMessageText] = useState('');
  const [messageType, setMessageType] = useState('text');

  useEffect(() => {
    loadTelegramData();
  }, []);

  const loadTelegramData = async () => {
    setLoading(true);
    try {
      const [statusRes, configRes, usersRes, messagesRes] = await Promise.all([
        fetch('/api/v1/telegram/bot-status'),
        fetch('/api/v1/telegram/config'),
        fetch('/api/v1/telegram/users'),
        fetch('/api/v1/telegram/messages')
      ]);

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setBotStatus(statusData);
      }

      if (configRes.ok) {
        const configData = await configRes.json();
        setBotConfig(configData);
      }

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        setUsers(usersData);
      }

      if (messagesRes.ok) {
        const messagesData = await messagesRes.json();
        setMessages(messagesData);
      }
    } catch (error) {
      setError('Ошибка загрузки данных Telegram');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedUser || !messageText.trim()) return;

    setLoading(true);
    try {
      const response = await fetch('/api/v1/telegram/send-message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: selectedUser.id,
          message: messageText,
          message_type: messageType
        })
      });

      if (response.ok) {
        setSuccess('Сообщение отправлено');
        setMessageText('');
        setShowMessageDialog(false);
        loadTelegramData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка отправки сообщения');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleNotifications = async (userId, enabled) => {
    try {
      const response = await fetch(`/api/v1/telegram/users/${userId}/notifications`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });

      if (response.ok) {
        setSuccess('Настройки уведомлений обновлены');
        loadTelegramData();
      }
    } catch (error) {
      setError('Ошибка обновления настроек');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Удалить пользователя из Telegram?')) return;

    try {
      const response = await fetch(`/api/v1/telegram/users/${userId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setSuccess('Пользователь удален');
        loadTelegramData();
      }
    } catch (error) {
      setError('Ошибка удаления пользователя');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'success';
      case 'inactive': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'active': return 'Активен';
      case 'inactive': return 'Неактивен';
      case 'pending': return 'Ожидает';
      default: return status;
    }
  };

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center">
              <Telegram color="primary" sx={{ mr: 1 }} />
              <Typography variant="h6" component="h3">
                Telegram Bot
              </Typography>
            </Box>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={loadTelegramData}
              disabled={loading}
            >
              Обновить
            </Button>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

          {botStatus && (
            <Grid container spacing={2} mb={3}>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {botStatus.total_users || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Пользователей
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="success.main">
                    {botStatus.active_users || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Активных
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="info.main">
                    {botStatus.messages_sent || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Сообщений
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Chip
                    icon={botStatus.bot_active ? <CheckCircle /> : <Error />}
                    label={botStatus.bot_active ? 'Активен' : 'Неактивен'}
                    color={botStatus.bot_active ? 'success' : 'error'}
                  />
                </Paper>
              </Grid>
            </Grid>
          )}

          <Box display="flex" gap={2} flexWrap="wrap">
            <Button
              variant="contained"
              startIcon={<Settings />}
              onClick={() => setShowConfigDialog(true)}
            >
              Настройки
            </Button>
            <Button
              variant="outlined"
              startIcon={<Send />}
              onClick={() => setShowMessageDialog(true)}
            >
              Отправить сообщение
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                <Typography variant="h6">Пользователи</Typography>
                <Button
                  size="small"
                  startIcon={<Add />}
                  onClick={() => setShowUserDialog(true)}
                >
                  Добавить
                </Button>
              </Box>
              
              <List>
                {users.map((user) => (
                  <React.Fragment key={user.id}>
                    <ListItem>
                      <ListItemIcon>
                        <Telegram />
                      </ListItemIcon>
                      <ListItemText
                        primary={user.first_name + ' ' + user.last_name}
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              @{user.username} • {user.telegram_id}
                            </Typography>
                            <Box display="flex" gap={1} mt={1}>
                              <Chip
                                size="small"
                                label={getStatusLabel(user.status)}
                                color={getStatusColor(user.status)}
                                variant="outlined"
                              />
                              <Chip
                                size="small"
                                label={user.language_code?.toUpperCase() || 'RU'}
                                variant="outlined"
                              />
                            </Box>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Box display="flex" alignItems="center" gap={1}>
                          <FormControlLabel
                            control={
                              <Switch
                                checked={user.notifications_enabled}
                                onChange={(e) => handleToggleNotifications(user.id, e.target.checked)}
                                size="small"
                              />
                            }
                            label="Уведомления"
                          />
                          <IconButton
                            size="small"
                            onClick={() => handleDeleteUser(user.id)}
                            color="error"
                          >
                            <Delete />
                          </IconButton>
                        </Box>
                      </ListItemSecondaryAction>
                    </ListItem>
                    <Divider />
                  </React.Fragment>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Последние сообщения
              </Typography>
              
              <List>
                {messages.slice(0, 5).map((message) => (
                  <ListItem key={message.id}>
                    <ListItemIcon>
                      {message.status === 'sent' ? <CheckCircle color="success" /> : <Error color="error" />}
                    </ListItemIcon>
                    <ListItemText
                      primary={message.message_text}
                      secondary={
                        <Box>
                          <Typography variant="body2" color="text.secondary">
                            {message.user_name} • {new Date(message.sent_at).toLocaleString()}
                          </Typography>
                          <Chip
                            size="small"
                            label={message.message_type}
                            variant="outlined"
                          />
                        </Box>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Диалог отправки сообщения */}
      <Dialog
        open={showMessageDialog}
        onClose={() => setShowMessageDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Отправить сообщение</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label="Пользователь"
            value={selectedUser?.id || ''}
            onChange={(e) => {
              const user = users.find(u => u.id === e.target.value);
              setSelectedUser(user);
            }}
            margin="normal"
          >
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.first_name} {user.last_name} (@{user.username})
              </option>
            ))}
          </TextField>
          
          <TextField
            fullWidth
            select
            label="Тип сообщения"
            value={messageType}
            onChange={(e) => setMessageType(e.target.value)}
            margin="normal"
          >
            <option value="text">Текст</option>
            <option value="notification">Уведомление</option>
            <option value="reminder">Напоминание</option>
          </TextField>
          
          <TextField
            fullWidth
            multiline
            rows={4}
            label="Текст сообщения"
            value={messageText}
            onChange={(e) => setMessageText(e.target.value)}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowMessageDialog(false)}>
            Отмена
          </Button>
          <Button
            variant="contained"
            onClick={handleSendMessage}
            disabled={!selectedUser || !messageText.trim() || loading}
          >
            Отправить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TelegramManager;
