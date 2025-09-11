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
  ListItemIcon
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Send,
  Telegram,
  Settings,
  Refresh,
  CheckCircle,
  Error,
  Warning
} from '@mui/icons-material';

const TelegramManager = () => {
  const [botStatus, setBotStatus] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [templateForm, setTemplateForm] = useState({
    name: '',
    message_type: 'text',
    content: '',
    is_active: true
  });

  useEffect(() => {
    loadTelegramData();
  }, []);

  const loadTelegramData = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      
      const [statusRes, templatesRes] = await Promise.all([
        fetch('/api/v1/telegram/bot-status', {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
        fetch('/api/v1/telegram/templates', {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setBotStatus(statusData);
      }

      if (templatesRes.ok) {
        const templatesData = await templatesRes.json();
        setTemplates(templatesData.templates || templatesData || []);
      }
    } catch (err) {
      setError('Ошибка загрузки данных Telegram');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/telegram/templates', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(templateForm)
      });

      if (response.ok) {
        setSuccess('Шаблон успешно создан');
        loadTelegramData();
        setShowTemplateDialog(false);
        resetForm();
      } else {
        setError('Ошибка создания шаблона');
      }
    } catch (err) {
      setError('Ошибка создания шаблона');
    }
  };

  const resetForm = () => {
    setTemplateForm({
      name: '',
      message_type: 'text',
      content: '',
      is_active: true
    });
  };

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
          Telegram бот
        </Typography>
        <Button
          variant="outlined"
          startIcon={<Refresh />}
          onClick={loadTelegramData}
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
                Статус бота
              </Typography>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <Telegram color={botStatus?.bot_active ? "success" : "error"} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Бот активен"
                    secondary={botStatus?.bot_active ? "Да" : "Нет"}
                  />
                  <Chip
                    label={botStatus?.bot_active ? "Активен" : "Неактивен"}
                    color={botStatus?.bot_active ? "success" : "error"}
                    size="small"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Webhook настроен"
                    secondary={botStatus?.webhook_configured ? "Да" : "Нет"}
                  />
                  <Chip
                    label={botStatus?.webhook_configured ? "Настроен" : "Не настроен"}
                    color={botStatus?.webhook_configured ? "success" : "warning"}
                    size="small"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Подписчиков"
                    secondary={botStatus?.subscribers_count || 0}
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
              <Box display="flex" flexDirection="column" gap={2}>
                <Button
                  fullWidth
                  variant="contained"
                  startIcon={<Settings />}
                  sx={{ py: 1.5 }}
                >
                  Настроить бота
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<Send />}
                  sx={{ py: 1.5 }}
                >
                  Отправить сообщение
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  startIcon={<Add />}
                  onClick={() => setShowTemplateDialog(true)}
                  sx={{ py: 1.5 }}
                >
                  Новый шаблон
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Шаблоны сообщений
              </Typography>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Название</TableCell>
                      <TableCell>Тип</TableCell>
                      <TableCell>Статус</TableCell>
                      <TableCell align="right">Действия</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {templates.map((template) => (
                      <TableRow key={template.id} hover>
                        <TableCell>{template.name}</TableCell>
                        <TableCell>
                          <Chip
                            label={template.message_type}
                            color="primary"
                            size="small"
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={template.is_active ? 'Активен' : 'Неактивен'}
                            color={template.is_active ? 'success' : 'default'}
                            size="small"
                          />
                        </TableCell>
                        <TableCell align="right">
                          <IconButton>
                            <Edit />
                          </IconButton>
                          <IconButton>
                            <Delete />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={showTemplateDialog} onClose={() => setShowTemplateDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Создать шаблон сообщения</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Название шаблона"
                value={templateForm.name}
                onChange={(e) => setTemplateForm({...templateForm, name: e.target.value})}
                required
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Тип сообщения</InputLabel>
                <Select
                  value={templateForm.message_type}
                  onChange={(e) => setTemplateForm({...templateForm, message_type: e.target.value})}
                  label="Тип сообщения"
                >
                  <MenuItem value="text">Текст</MenuItem>
                  <MenuItem value="photo">Фото</MenuItem>
                  <MenuItem value="document">Документ</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Содержание сообщения"
                multiline
                rows={6}
                value={templateForm.content}
                onChange={(e) => setTemplateForm({...templateForm, content: e.target.value})}
                required
                placeholder="Используйте переменные: {patient_name}, {appointment_date}, {doctor_name}"
              />
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                  <Switch
                    checked={templateForm.is_active}
                    onChange={(e) => setTemplateForm({...templateForm, is_active: e.target.checked})}
                  />
                }
                label="Активный шаблон"
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowTemplateDialog(false)}>Отмена</Button>
          <Button onClick={handleCreateTemplate} variant="contained">
            Создать
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TelegramManager;