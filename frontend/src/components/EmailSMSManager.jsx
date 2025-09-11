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
  FormControlLabel
} from '@mui/material';
import {
  Add,
  Edit,
  Delete,
  Send,
  Email,
  Sms,
  Refresh,
  Settings,
  History
} from '@mui/icons-material';

const EmailSMSManager = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [templateForm, setTemplateForm] = useState({
    name: '',
    type: 'email',
    subject: '',
    content: '',
    is_active: true
  });

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/notifications/templates', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || data || []);
      } else {
        setError('Ошибка загрузки шаблонов');
      }
    } catch (err) {
      setError('Ошибка подключения к серверу');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/notifications/templates', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(templateForm)
      });

      if (response.ok) {
        setSuccess('Шаблон успешно создан');
        loadTemplates();
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
      type: 'email',
      subject: '',
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
          Управление уведомлениями
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setShowTemplateDialog(true)}
        >
          Новый шаблон
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
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Шаблоны уведомлений
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
                            icon={template.type === 'email' ? <Email /> : <Sms />}
                            label={template.type === 'email' ? 'Email' : 'SMS'}
                            color={template.type === 'email' ? 'primary' : 'secondary'}
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

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Статистика
              </Typography>
              <Box display="flex" flexDirection="column" gap={2}>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Email отправлено:</Typography>
                  <Typography variant="h6">1,234</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>SMS отправлено:</Typography>
                  <Typography variant="h6">567</Typography>
                </Box>
                <Box display="flex" justifyContent="space-between">
                  <Typography>Активных шаблонов:</Typography>
                  <Typography variant="h6">{templates.filter(t => t.is_active).length}</Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={showTemplateDialog} onClose={() => setShowTemplateDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Создать шаблон уведомления</DialogTitle>
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
                <InputLabel>Тип</InputLabel>
                <Select
                  value={templateForm.type}
                  onChange={(e) => setTemplateForm({...templateForm, type: e.target.value})}
                  label="Тип"
                >
                  <MenuItem value="email">Email</MenuItem>
                  <MenuItem value="sms">SMS</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Тема"
                value={templateForm.subject}
                onChange={(e) => setTemplateForm({...templateForm, subject: e.target.value})}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Содержание"
                multiline
                rows={6}
                value={templateForm.content}
                onChange={(e) => setTemplateForm({...templateForm, content: e.target.value})}
                required
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

export default EmailSMSManager;