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
  Paper,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';
import {
  Email,
  Sms,
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
  Template,
  History
} from '@mui/icons-material';

const EmailSMSManager = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [templates, setTemplates] = useState([]);
  const [history, setHistory] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showSendDialog, setShowSendDialog] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [newTemplate, setNewTemplate] = useState({
    name: '',
    subject: '',
    content: '',
    type: 'email',
    variables: []
  });
  const [sendData, setSendData] = useState({
    recipients: [],
    template_id: '',
    variables: {}
  });

  useEffect(() => {
    loadEmailSMSData();
  }, []);

  const loadEmailSMSData = async () => {
    setLoading(true);
    try {
      const [templatesRes, historyRes, statsRes] = await Promise.all([
        fetch('/api/v1/notifications/templates'),
        fetch('/api/v1/notifications/history'),
        fetch('/api/v1/notifications/history/stats')
      ]);

      if (templatesRes.ok) {
        const templatesData = await templatesRes.json();
        setTemplates(templatesData);
      }

      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setHistory(historyData);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
    } catch (error) {
      setError('Ошибка загрузки данных Email/SMS');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/notifications/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTemplate)
      });

      if (response.ok) {
        setSuccess('Шаблон создан');
        setShowTemplateDialog(false);
        setNewTemplate({
          name: '',
          subject: '',
          content: '',
          type: 'email',
          variables: []
        });
        loadEmailSMSData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка создания шаблона');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTemplate = async (templateId, updatedTemplate) => {
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/notifications/templates/${templateId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedTemplate)
      });

      if (response.ok) {
        setSuccess('Шаблон обновлен');
        loadEmailSMSData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка обновления шаблона');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (templateId) => {
    if (!window.confirm('Удалить шаблон?')) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/v1/notifications/templates/${templateId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setSuccess('Шаблон удален');
        loadEmailSMSData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка удаления шаблона');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/notifications/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(sendData)
      });

      if (response.ok) {
        setSuccess('Сообщения отправлены');
        setShowSendDialog(false);
        setSendData({
          recipients: [],
          template_id: '',
          variables: {}
        });
        loadEmailSMSData();
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Ошибка отправки сообщений');
      }
    } catch (error) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'sent': return 'success';
      case 'failed': return 'error';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'sent': return 'Отправлено';
      case 'failed': return 'Ошибка';
      case 'pending': return 'Ожидает';
      default: return status;
    }
  };

  const TabPanel = ({ children, value, index, ...other }) => (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`tabpanel-${index}`}
      aria-labelledby={`tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center">
              <Email color="primary" sx={{ mr: 1 }} />
              <Typography variant="h6" component="h3">
                Email/SMS Менеджер
              </Typography>
            </Box>
            <Button
              variant="outlined"
              startIcon={<Refresh />}
              onClick={loadEmailSMSData}
              disabled={loading}
            >
              Обновить
            </Button>
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

          {stats && (
            <Grid container spacing={2} mb={3}>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="primary">
                    {stats.total_sent || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Отправлено
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="success.main">
                    {stats.success_rate || 0}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Успешность
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="info.main">
                    {stats.templates_count || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Шаблонов
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} sm={6} md={3}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="h4" color="warning.main">
                    {stats.pending_count || 0}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    В очереди
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          )}

          <Box display="flex" gap={2} flexWrap="wrap">
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setShowTemplateDialog(true)}
            >
              Создать шаблон
            </Button>
            <Button
              variant="outlined"
              startIcon={<Send />}
              onClick={() => setShowSendDialog(true)}
            >
              Отправить сообщения
            </Button>
          </Box>
        </CardContent>
      </Card>

      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)}>
            <Tab icon={<Template />} label="Шаблоны" />
            <Tab icon={<History />} label="История" />
          </Tabs>
        </Box>

        <TabPanel value={activeTab} index={0}>
          <List>
            {templates.map((template) => (
              <React.Fragment key={template.id}>
                <ListItem>
                  <ListItemIcon>
                    {template.type === 'email' ? <Email /> : <Sms />}
                  </ListItemIcon>
                  <ListItemText
                    primary={template.name}
                    secondary={
                      <Box>
                        <Typography variant="body2" color="text.secondary">
                          {template.subject}
                        </Typography>
                        <Box display="flex" gap={1} mt={1}>
                          <Chip
                            size="small"
                            label={template.type === 'email' ? 'Email' : 'SMS'}
                            color="primary"
                            variant="outlined"
                          />
                          <Chip
                            size="small"
                            label={template.language || 'RU'}
                            variant="outlined"
                          />
                        </Box>
                      </Box>
                    }
                  />
                  <ListItemSecondaryAction>
                    <Box display="flex" gap={1}>
                      <IconButton
                        size="small"
                        onClick={() => {
                          setSelectedTemplate(template);
                          setShowTemplateDialog(true);
                        }}
                      >
                        <Edit />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteTemplate(template.id)}
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
        </TabPanel>

        <TabPanel value={activeTab} index={1}>
          <List>
            {history.slice(0, 10).map((item) => (
              <ListItem key={item.id}>
                <ListItemIcon>
                  {item.status === 'sent' ? <CheckCircle color="success" /> : <Error color="error" />}
                </ListItemIcon>
                <ListItemText
                  primary={item.subject}
                  secondary={
                    <Box>
                      <Typography variant="body2" color="text.secondary">
                        {item.recipient} • {new Date(item.created_at).toLocaleString()}
                      </Typography>
                      <Box display="flex" gap={1} mt={1}>
                        <Chip
                          size="small"
                          label={getStatusLabel(item.status)}
                          color={getStatusColor(item.status)}
                          variant="outlined"
                        />
                        <Chip
                          size="small"
                          label={item.type}
                          variant="outlined"
                        />
                      </Box>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        </TabPanel>
      </Card>

      {/* Диалог создания/редактирования шаблона */}
      <Dialog
        open={showTemplateDialog}
        onClose={() => setShowTemplateDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {selectedTemplate ? 'Редактировать шаблон' : 'Создать шаблон'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Название"
            value={selectedTemplate?.name || newTemplate.name}
            onChange={(e) => {
              if (selectedTemplate) {
                setSelectedTemplate({ ...selectedTemplate, name: e.target.value });
              } else {
                setNewTemplate({ ...newTemplate, name: e.target.value });
              }
            }}
            margin="normal"
          />
          
          <FormControl fullWidth margin="normal">
            <InputLabel>Тип</InputLabel>
            <Select
              value={selectedTemplate?.type || newTemplate.type}
              onChange={(e) => {
                if (selectedTemplate) {
                  setSelectedTemplate({ ...selectedTemplate, type: e.target.value });
                } else {
                  setNewTemplate({ ...newTemplate, type: e.target.value });
                }
              }}
            >
              <MenuItem value="email">Email</MenuItem>
              <MenuItem value="sms">SMS</MenuItem>
            </Select>
          </FormControl>
          
          <TextField
            fullWidth
            label="Тема"
            value={selectedTemplate?.subject || newTemplate.subject}
            onChange={(e) => {
              if (selectedTemplate) {
                setSelectedTemplate({ ...selectedTemplate, subject: e.target.value });
              } else {
                setNewTemplate({ ...newTemplate, subject: e.target.value });
              }
            }}
            margin="normal"
          />
          
          <TextField
            fullWidth
            multiline
            rows={6}
            label="Содержание"
            value={selectedTemplate?.content || newTemplate.content}
            onChange={(e) => {
              if (selectedTemplate) {
                setSelectedTemplate({ ...selectedTemplate, content: e.target.value });
              } else {
                setNewTemplate({ ...newTemplate, content: e.target.value });
              }
            }}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setShowTemplateDialog(false);
            setSelectedTemplate(null);
          }}>
            Отмена
          </Button>
          <Button
            variant="contained"
            onClick={selectedTemplate ? 
              () => handleUpdateTemplate(selectedTemplate.id, selectedTemplate) : 
              handleCreateTemplate
            }
            disabled={loading}
          >
            {selectedTemplate ? 'Обновить' : 'Создать'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог отправки сообщений */}
      <Dialog
        open={showSendDialog}
        onClose={() => setShowSendDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Отправить сообщения</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            select
            label="Шаблон"
            value={sendData.template_id}
            onChange={(e) => setSendData({ ...sendData, template_id: e.target.value })}
            margin="normal"
          >
            {templates.map((template) => (
              <MenuItem key={template.id} value={template.id}>
                {template.name} ({template.type})
              </MenuItem>
            ))}
          </TextField>
          
          <TextField
            fullWidth
            multiline
            rows={3}
            label="Получатели (по одному на строку)"
            value={sendData.recipients.join('\n')}
            onChange={(e) => setSendData({ 
              ...sendData, 
              recipients: e.target.value.split('\n').filter(r => r.trim()) 
            })}
            margin="normal"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSendDialog(false)}>
            Отмена
          </Button>
          <Button
            variant="contained"
            onClick={handleSendMessage}
            disabled={!sendData.template_id || sendData.recipients.length === 0 || loading}
          >
            Отправить
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EmailSMSManager;
