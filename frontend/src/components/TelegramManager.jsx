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
  const [registeringCommands, setRegisteringCommands] = useState(false);
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
        patient_bot: integrationData.patient_bot || null,
        staff_bot: integrationData.staff_bot || null,
        supported_functions: Array.isArray(integrationData.supported_functions) ? integrationData.supported_functions : [],
        planned_functions: Array.isArray(integrationData.planned_functions) ? integrationData.planned_functions : [],
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

  const registerPatientCommands = async () => {
    try {
      setError('');
      setSuccess('');
      setRegisteringCommands(true);
      const response = await api.post('/admin/telegram/register-patient-commands');
      const languages = Array.isArray(response?.data?.registered_languages) ?
      response.data.registered_languages.join(', ') :
      'ru, uz';
      setSuccess(`Команды пациентского бота зарегистрированы: ${languages}`);
      await loadTelegramData();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || detail?.error;
      setError(message || e?.message || 'Не удалось зарегистрировать команды Telegram');
    } finally {
      setRegisteringCommands(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" sx={{ minHeight: '400px' }}>
        <CircularProgress />
      </Box>);

  }

  const patientBot = botStatus?.patient_bot || {};
  const patientBotFeatures = Array.isArray(patientBot.features) ? patientBot.features : [];
  const enabledPatientFeatures = patientBotFeatures.filter((feature) => feature?.enabled);
  const patientBotCommands = Array.isArray(patientBot.commands) ? patientBot.commands : [];
  const patientBotLanguages = Array.isArray(patientBot.supported_languages) ? patientBot.supported_languages : [];
  const staffBot = botStatus?.staff_bot || {};
  const staffBotReadiness = Array.isArray(staffBot.readiness) ? staffBot.readiness : [];
  const readyStaffControls = staffBotReadiness.filter((item) => item?.ready);
  const staffRoles = Array.isArray(staffBot.supported_roles) ? staffBot.supported_roles : [];
  const staffMenuContractSource = Array.isArray(staffBot.read_only_menu_contract) ? staffBot.read_only_menu_contract : [];
  const staffRoleMenus = staffBot.role_menus || {};
  const staffMenuRoleCount = typeof staffRoleMenus.role_count === 'number' ?
  staffRoleMenus.role_count :
  staffMenuContractSource.length;
  const staffMenuContract = staffMenuRoleCount === staffMenuContractSource.length ?
  staffMenuContractSource :
  Array.from({ length: staffMenuRoleCount });
  const staffMenuItemCount = typeof staffRoleMenus.item_count === 'number' ?
  staffRoleMenus.item_count :
  staffMenuContractSource.reduce((count, role) => {
    const items = Array.isArray(role?.items) ? role.items : [];
    return count + items.length;
  }, 0);
  const staffRoleSummary = staffRoles.length ? staffRoles.join(', ') : 'none';
  const staffTokenContract = staffBot.token_contract || {};
  const staffLinkingContract = staffBot.linking_contract || staffBot.role_linking || {};
  const staffLinkingMethods = Array.isArray(staffLinkingContract.accepted_methods) ?
  staffLinkingContract.accepted_methods :
  [];
  const staffLinkingMethodNames = staffLinkingMethods.
  map((method) => method?.label || method?.key || method).
  filter(Boolean);
  const staffLinkingRuntimeContract = staffBot.linking_runtime_contract || {};
  const staffAuthorizationContract = staffBot.authorization_contract || staffBot.authorization || {};
  const staffAuthorizationRoles = Array.isArray(staffAuthorizationContract.role_checks) ?
  staffAuthorizationContract.role_checks :
  [];
  const staffCommandContract = staffBot.command_registration_contract || staffBot.command_contract || {};
  const staffCommandList = Array.isArray(staffCommandContract.commands) ?
  staffCommandContract.commands :
  [];
  const staffCommandNames = staffCommandList.
  map((item) => item?.command).
  filter(Boolean);
  const staffConfirmationContract = staffBot.confirmation_contract || {};
  const staffConfirmationOperations = Array.isArray(staffConfirmationContract.operations) ?
  staffConfirmationContract.operations :
  [];
  const staffAuditContract = staffBot.audit_contract || {};
  const staffAuditEvents = Array.isArray(staffAuditContract.event_types) ?
  staffAuditContract.event_types :
  [];
  const staffRoleMenuEnablementContract = staffBot.role_menu_enablement_contract || {};
  const staffRoleMenuEnablementRoleCount = typeof staffRoleMenuEnablementContract.role_count === 'number' ?
  staffRoleMenuEnablementContract.role_count :
  staffMenuContract.length;
  const staffRoleMenuEnablementItemCount = typeof staffRoleMenuEnablementContract.menu_item_count === 'number' ?
  staffRoleMenuEnablementContract.menu_item_count :
  staffMenuItemCount;

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
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff token separation"
                    secondary={staffTokenContract.contract_version ?
                    `scope: ${staffTokenContract.scope || 'staff'}; runtime read: ${staffTokenContract.runtime_read_enabled ? 'enabled' : 'disabled'}` :
                    'Dedicated staff bot token contract не опубликован'} />

                  <Badge
                    variant={staffTokenContract.runtime_read_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffTokenContract.required_before_enablement ? 'Required' : 'Planned'}
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
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary={`Patient bot ${patientBot.version || 'v1'}`}
                    secondary={enabledPatientFeatures.length ?
                    enabledPatientFeatures.map((feature) => feature.label).join(', ') :
                    'Функции пациента не активны'} />

                  <Badge
                    variant={enabledPatientFeatures.length ? 'success' : 'warning'}
                    size="small">

                    {enabledPatientFeatures.length || 0}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Языки пациента"
                    secondary={patientBotLanguages.length ?
                    patientBotLanguages.map((item) => item.label).join(', ') :
                    'Русский'} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Команды пациента"
                    secondary={patientBotCommands.length ?
                    patientBotCommands.map((item) => item.command).join(' ') :
                    'Нет данных'} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary={`Staff bot ${staffBot.version || 'planning'}`}
                    secondary={staffBot.enabled ?
                    'Готов к ролевым действиям' :
                    'План: роли, audit и подтверждения до включения'} />

                  <Badge
                    variant={staffBot.enabled ? 'success' : 'warning'}
                    size="small">

                    {staffBot.enabled ? 'Готов' : 'План'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff guardrails"
                    secondary={staffBotReadiness.length ?
                    `${readyStaffControls.length}/${staffBotReadiness.length} готово; роли: ${staffRoleSummary}` :
                    'Требуется отдельный staff/admin contract'} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff linking foundation"
                    secondary={staffLinkingMethodNames.length ?
                    `${staffLinkingMethodNames.join(', ')}; до включения: ${staffLinkingContract.required_before_enablement ? 'обязательно' : 'не требуется'}` :
                    'Контракт привязки сотрудников не опубликован'} />

                  <Badge
                    variant={staffLinkingContract.enabled ? 'success' : 'warning'}
                    size="small">

                    {staffLinkingContract.enabled ? 'Enabled' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff linking runtime"
                    secondary={staffLinkingRuntimeContract.contract_version ?
                    `${staffLinkingRuntimeContract.write_helper || 'link helper'}; handler: ${staffLinkingRuntimeContract.runtime_handler_enabled ? 'enabled' : 'disabled'}` :
                    'Staff linking runtime contract not published'} />

                  <Badge
                    variant={staffLinkingRuntimeContract.runtime_handler_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffLinkingRuntimeContract.helper_available ? 'Helper' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff authorization"
                    secondary={staffAuthorizationRoles.length ?
                    `${staffAuthorizationRoles.length} role checks; default: ${staffAuthorizationContract.default_decision || 'deny'}` :
                    'Authorization contract не опубликован'} />

                  <Badge
                    variant={staffAuthorizationContract.enabled ? 'success' : 'warning'}
                    size="small">

                    {staffAuthorizationContract.server_side_required ? 'Required' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff menu contract"
                    secondary={staffMenuContract.length ?
                    `${staffMenuContract.length} ролей, ${staffMenuItemCount} read-only пунктов; действия: выключены` :
                    'Read-only contract не опубликован'} />

                  <Badge
                    variant={staffBot.state_changing_actions_enabled ? 'error' : 'warning'}
                    size="small">

                    {staffBot.state_changing_actions_enabled ? 'Actions' : 'Read-only'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff role menu enablement"
                    secondary={staffRoleMenuEnablementContract.contract_version ?
                    `${staffRoleMenuEnablementRoleCount} roles, ${staffRoleMenuEnablementItemCount} items; runtime menu: ${staffRoleMenuEnablementContract.runtime_menu_enabled ? 'enabled' : 'disabled'}` :
                    'Role menu enablement contract not published'} />

                  <Badge
                    variant={staffRoleMenuEnablementContract.runtime_menu_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffRoleMenuEnablementContract.required_before_enablement ? 'Required' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff command registration"
                    secondary={staffCommandNames.length ?
                    `${staffCommandNames.join(' ')}; registration: ${staffCommandContract.registration_enabled ? 'enabled' : 'disabled until staff gates'}` :
                    'Staff command contract не опубликован'} />

                  <Badge
                    variant={staffCommandContract.registration_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffCommandContract.registration_enabled ? 'Enabled' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff action confirmations"
                    secondary={staffConfirmationOperations.length ?
                    `${staffConfirmationOperations.length} state-changing actions require confirmation; actions: ${staffConfirmationContract.state_changing_actions_enabled ? 'enabled' : 'disabled'}` :
                    'Confirmation contract не опубликован'} />

                  <Badge
                    variant={staffConfirmationContract.state_changing_actions_enabled ? 'error' : 'warning'}
                    size="small">

                    {staffConfirmationContract.required_for_state_changes ? 'Required' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff audit logging"
                    secondary={staffAuditEvents.length ?
                    `${staffAuditEvents.length} required events; writer: ${staffAuditContract.record_writer_enabled ? 'enabled' : 'disabled'}` :
                    'Audit contract не опубликован'} />

                  <Badge
                    variant={staffAuditContract.record_writer_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffAuditContract.required_before_enablement ? 'Required' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Send />
                  </ListItemIcon>
                  <ListItemText
                    primary="Результаты"
                    secondary={patientBot.results_delivery === 'telegram_pdf' ?
                    `PDF в Telegram, до ${patientBot.max_pdf_reports_per_request || 3} файлов` :
                    'Уведомление в Telegram'} />

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
                  disabled={!botStatus?.configured || registeringCommands}
                  onClick={registerPatientCommands}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <CheckCircle size={16} />
                  {registeringCommands ? 'Регистрация команд...' : 'Зарегистрировать команды'}
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
