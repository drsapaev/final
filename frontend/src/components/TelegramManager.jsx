import { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,

  Badge,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Select,

  Switch,

  Grid,
  List,
  Table } from
'./ui/macos';
import {
  TableHead,
  TableBody,
  TableRow,
  TableCell } from
'./ui/macos/Table';
import {
  ListItem,
  ListItemIcon,
  ListItemText } from
'./ui/macos/List';
import {
  Plus,
  Edit,
  Trash2,
  Send,
  MessageSquare,
  Settings,
  RefreshCw,
  CheckCircle } from


'lucide-react';
import {
  TableContainer,
  IconButton,
  TextField,
  FormControl,
  InputLabel,
  MenuItem,
  FormControlLabel } from
'@mui/material';
import { api } from '../api/client.js';

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
      const [statusRes, integrationRes, templatesRes] = await Promise.all([
        api.get('/telegram/bot-status'),
        api.get('/admin/telegram/integration-status').catch(() => ({ data: null })),
        api.get('/admin/telegram/templates')
      ]);

      const statusData = statusRes?.data || {};
      const integrationData = integrationRes?.data || {};
      const templatesData = templatesRes?.data || {};

      setBotStatus({
        bot_active: Boolean(integrationData.active ?? statusData.active ?? statusData.configured),
        webhook_configured: Boolean(integrationData.webhook_set || statusData.webhook_configured || statusData.webhook_set),
        subscribers_count: Number(integrationData.linked_users ?? statusData?.stats?.active_users ?? statusData?.stats?.total_users ?? 0),
        total_users: Number(integrationData.total_users ?? statusData?.stats?.total_users ?? 0),
        bot_username: integrationData.bot_username || statusData.bot_username || statusData?.bot_info?.username,
        mode: integrationData.mode || ((statusData.webhook_configured || statusData.webhook_set) ? 'webhook' : 'polling'),
        polling_ready: Boolean(integrationData.polling_ready),
        qr_linking_enabled: Boolean(integrationData.qr_linking_enabled),
        contact_linking_enabled: Boolean(integrationData.contact_linking_enabled),
        pending_update_count: integrationData.pending_update_count,
        transition_path: integrationData.transition_path,
        webhook_error: integrationData.webhook_error,
        configured: Boolean(integrationData.configured ?? statusData.configured),
        raw: { status: statusData, integration: integrationData }
      });

      const normalizedTemplates = Array.isArray(templatesData) ?
      templatesData :
      Object.entries(templatesData).map(([key, value]) => ({
        id: key,
        name: value?.subject || key,
        message_type: key,
        content: value?.message_text || '',
        is_active: true
      }));

      setTemplates(normalizedTemplates);
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Ошибка загрузки данных Telegram');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async () => {
    setError('В этой сборке доступен просмотр Telegram шаблонов. Создание шаблонов через UI пока не опубликовано в backend contract.');
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
      <Box display="flex" justifyContent="center" alignItems="center" sx={{ minHeight: '400px' }}>
        <CircularProgress />
      </Box>);

  }

  return (
    <Box sx={{ p: 3 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Telegram бот
        </Typography>
        <Button
          variant="outlined"
          onClick={loadTelegramData}>
          <RefreshCw size={16} />
          Обновить
        </Button>
      </Box>

      {error &&
      <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      }
      {success &&
      <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      }

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
                    <MessageSquare
                      style={{
                        color: botStatus?.bot_active ? 'var(--mac-success, #28a745)' : 'var(--mac-error, #dc3545)'
                      }} />
                    
                  </ListItemIcon>
                  <ListItemText
                    primary="Бот активен"
                    secondary={botStatus?.bot_active ? 'Да' : 'Нет'} />
                  
                  <Badge
                    variant={botStatus?.bot_active ? 'success' : 'error'}
                    size="small">
                    
                    {botStatus?.bot_active ? 'Активен' : 'Неактивен'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Webhook настроен"
                    secondary={botStatus?.webhook_configured ? 'Да' : 'Нет'} />
                  
                  <Badge
                    variant={botStatus?.webhook_configured ? 'success' : 'warning'}
                    size="small">
                    
                    {botStatus?.webhook_configured ? 'Настроен' : 'Не настроен'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Подписчиков"
                    secondary={`${botStatus?.subscribers_count || 0} привязано / ${botStatus?.total_users || 0} всего`} />
                  
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary="Telegram bot"
                    secondary={botStatus?.bot_username ? `@${botStatus.bot_username}` : 'Не настроен'} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Режим подключения"
                    secondary={botStatus?.mode === 'webhook' ? 'Webhook' : 'Polling'} />

                  <Badge
                    variant={botStatus?.mode === 'webhook' ? 'success' : 'warning'}
                    size="small">

                    {botStatus?.mode === 'webhook' ? 'Webhook' : 'Polling'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Привязка пациентов"
                    secondary={`QR: ${botStatus?.qr_linking_enabled ? 'да' : 'нет'}, телефон: ${botStatus?.contact_linking_enabled ? 'да' : 'нет'}`} />

                </ListItem>
                {botStatus?.webhook_error &&
                <ListItem>
                    <ListItemIcon>
                      <Settings />
                    </ListItemIcon>
                    <ListItemText
                      primary="Telegram API"
                      secondary={botStatus.webhook_error} />

                  </ListItem>
                }
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
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <Button
                  fullWidth
                  variant="contained"
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Settings size={16} />
                  Настроить бота
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Send size={16} />
                  Отправить сообщение
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={() => setShowTemplateDialog(true)}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Plus size={16} />
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
                    {templates.map((template) =>
                    <TableRow key={template.id} hover>
                        <TableCell>{template.name}</TableCell>
                        <TableCell>
                          <Badge
                          variant="primary"
                          size="small">
                          
                            {template.message_type}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                          variant={template.is_active ? 'success' : 'default'}
                          size="small">
                          
                            {template.is_active ? 'Активен' : 'Неактивен'}
                          </Badge>
                        </TableCell>
                        <TableCell align="right">
                          <IconButton>
                            <Edit />
                          </IconButton>
                          <IconButton>
                            <Trash2 />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    )}
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
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                required />
              
            </Grid>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>Тип сообщения</InputLabel>
                <Select
                  value={templateForm.message_type}
                  onChange={(e) => setTemplateForm({ ...templateForm, message_type: e.target.value })}
                  label="Тип сообщения">
                  
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
                onChange={(e) => setTemplateForm({ ...templateForm, content: e.target.value })}
                required
                placeholder="Используйте переменные: {patient_name}, {appointment_date}, {doctor_name}" />
              
            </Grid>
            <Grid item xs={12}>
              <FormControlLabel
                control={
                <Switch
                  checked={templateForm.is_active}
                  onChange={(e) => setTemplateForm({ ...templateForm, is_active: e.target.checked })} />

                }
                label="Активный шаблон" />
              
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
    </Box>);

};

export default TelegramManager;
