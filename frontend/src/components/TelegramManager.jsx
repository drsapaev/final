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
  CheckCircle,
  Calendar,
  CreditCard,
  FileText,
  Languages,
  Phone,
  ShieldCheck,
  Ticket,
  UserCheck,
  Users } from


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
  const [registeringStaffCommands, setRegisteringStaffCommands] = useState(false);
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

  const registerStaffCommands = async () => {
    try {
      setError('');
      setSuccess('');
      setRegisteringStaffCommands(true);
      const response = await api.post('/admin/telegram/register-staff-commands');
      const commands = Array.isArray(response?.data?.registered_commands) ?
      response.data.registered_commands.join(', ') :
      'read-only staff commands';
      setSuccess(`Staff-команды зарегистрированы: ${commands}`);
      await loadTelegramData();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || detail?.error;
      setError(message || e?.message || 'Не удалось зарегистрировать staff-команды Telegram');
    } finally {
      setRegisteringStaffCommands(false);
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
  const patientPaymentEntryFeature = patientBotFeatures.find(
    (feature) => feature?.key === 'patient_payments_protected_entry'
  );
  const patientPaymentEntryRoute = patientPaymentEntryFeature?.contract?.route || '/patient/payments';
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
  const staffTokenReady = Boolean(staffTokenContract.ready || staffTokenContract.enabled);
  const staffTokenBlockedBy = Array.isArray(staffTokenContract.runtime_blocked_by)
    ? staffTokenContract.runtime_blocked_by
    : [];
  const staffTokenSource = staffTokenContract.source_key
    ? `${staffTokenContract.source || 'source'}: ${staffTokenContract.source_key}`
    : staffTokenContract.source || 'not_configured';
  let staffTokenIssue = 'separate token configured';
  if (staffTokenContract.patient_bot_token_reused) {
    staffTokenIssue = 'patient token reused';
  } else if (staffTokenBlockedBy.length) {
    staffTokenIssue = `blocked: ${staffTokenBlockedBy.join(', ')}`;
  }
  const staffTokenSecretVisibility = staffTokenContract.token_returned_to_frontend
    ? 'secret exposed to frontend'
    : 'secret hidden from frontend';
  const staffLinkingContract = staffBot.linking_contract || staffBot.role_linking || {};
  const staffLinkingMethods = Array.isArray(staffLinkingContract.accepted_methods) ?
  staffLinkingContract.accepted_methods :
  [];
  const staffLinkingMethodNames = staffLinkingMethods.
  map((method) => method?.label || method?.key || method).
  filter(Boolean);
  const staffLinkingRuntimeContract = staffBot.linking_runtime_contract || {};
  const staffLinkTokenValidationContract = staffBot.link_token_validation_contract || {};
  const staffLinkTokenStorageContract =
  staffBot.link_token_storage_contract || staffLinkTokenValidationContract.storage_contract || {};
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
  const staffCommandEndpointReady = Boolean(
    staffCommandContract.registration_endpoint_published ||
    staffCommandContract.runtime_registration_enabled
  );
  const staffCommandRegistrationEnabled = Boolean(staffCommandContract.registration_enabled);
  const staffConfirmationContract = staffBot.confirmation_contract || {};
  const staffConfirmationRuntime = staffBot.confirmations || {};
  const staffConfirmationOperations = Array.isArray(staffConfirmationContract.operations) ?
  staffConfirmationContract.operations :
  [];
  const staffConfirmationGuardReady = Boolean(
    staffConfirmationContract.runtime_guard_enabled ||
    staffConfirmationRuntime.runtime_guard_enabled ||
    staffConfirmationRuntime.ready
  );
  const staffConfirmationActionsEnabled = Boolean(
    staffConfirmationContract.state_changing_actions_enabled ||
    staffBot.state_changing_actions_enabled
  );
  const staffConfirmationDenyOnly = Boolean(
    staffConfirmationContract.deny_only_runtime_enabled ||
    staffConfirmationRuntime.deny_only_runtime_enabled
  );
  const staffNextSlice = staffBot.next_slice || 'none';
  const staffConfirmationTokenRuntimeEnabled = Boolean(
    staffConfirmationContract.confirmation_token_runtime_enabled ||
    staffConfirmationRuntime.confirmation_token_runtime_enabled
  );
  const staffConfirmationBlockedBy = Array.isArray(staffConfirmationContract.runtime_blocked_by) ?
  staffConfirmationContract.runtime_blocked_by :
  [];
  const staffConfirmationBlockerSummary = staffConfirmationBlockedBy.length ?
  staffConfirmationBlockedBy.join(', ') :
  'none';
  const staffAuditContract = staffBot.audit_contract || {};
  const staffAuditRuntime = staffBot.audit || {};
  const staffAuditEvents = Array.isArray(staffAuditContract.event_types) ?
  staffAuditContract.event_types :
  [];
  const staffAuditRecordedEvents = Array.isArray(staffAuditContract.recorded_event_types) ?
  staffAuditContract.recorded_event_types :
  [];
  const staffAuditPendingEvents = Array.isArray(staffAuditContract.pending_event_types) ?
  staffAuditContract.pending_event_types :
  [];
  const staffAuditReady = Boolean(
    staffAuditContract.enabled ||
    staffAuditRuntime.ready
  );
  const staffAuditReadOnlyReady = Boolean(
    staffAuditContract.read_only_menu_events_enabled ||
    staffAuditRuntime.read_only_menu_events_ready
  );
  const staffRoleMenuEnablementContract = staffBot.role_menu_enablement_contract || {};
  const staffRoleMenuRuntimeEnabled = Boolean(
    staffRoleMenuEnablementContract.runtime_menu_enabled || staffBot.read_only_runtime_enabled
  );
  const staffRoleMenuDomainDataEnabled = Boolean(
    staffRoleMenuEnablementContract.domain_data_commands_enabled
  );
  const staffRoleMenuDomainDataStatus =
  staffRoleMenuEnablementContract.domain_data_commands_status ||
  (staffRoleMenuDomainDataEnabled ? 'enabled' : 'app only');
  const staffRoleMenuDomainDataKeys = Array.isArray(staffRoleMenuEnablementContract.domain_data_command_keys) ?
  staffRoleMenuEnablementContract.domain_data_command_keys :
  [];
  const staffRoleMenuEnablementRoleCount = typeof staffRoleMenuEnablementContract.role_count === 'number' ?
  staffRoleMenuEnablementContract.role_count :
  staffMenuContract.length;
  const staffRoleMenuEnablementItemCount = typeof staffRoleMenuEnablementContract.menu_item_count === 'number' ?
  staffRoleMenuEnablementContract.menu_item_count :
  staffMenuItemCount;
  const patientCommandLabel = (commandName, fallback) => {
    const command = patientBotCommands.find((item) => item?.command === commandName);
    return command?.label || fallback;
  };
  const patientLanguageSummary = patientBotLanguages.length ?
  patientBotLanguages.map((item) => item.label).join(', ') :
  'Русский';
  const patientCapabilities = [
    {
      key: 'book',
      icon: Calendar,
      menu: '🏥 Записаться на приём',
      command: '/book',
      label: patientCommandLabel('/book', 'Записаться на приём'),
      detail: 'Показывает безопасный путь через регистратуру; визит из свободного текста не создаёт.'
    },
    {
      key: 'queue',
      icon: Ticket,
      menu: '🎫 Моя очередь',
      command: '/queue',
      label: patientCommandLabel('/queue', 'Моя очередь'),
      detail: 'Номер, кабинет, статус и позиция ожидания без изменения очереди.'
    },
    {
      key: 'payments',
      icon: CreditCard,
      menu: '💳 Оплаты и долг',
      command: '/payments',
      label: patientCommandLabel('/payments', 'Оплаты и долг'),
      detail: patientPaymentEntryFeature?.enabled
        ? `Начислено, оплачено, долг; кнопка ведет в защищенный кабинет: ${patientPaymentEntryRoute}.`
        : 'Начислено, оплачено, долг и незавершённые платежи по визиту.'
    },
    {
      key: 'results',
      icon: FileText,
      menu: '📄 Результаты',
      command: '/results',
      label: patientCommandLabel('/results', 'PDF-результаты'),
      detail: `До ${patientBot.max_pdf_reports_per_request || 3} готовых PDF только для привязанного пациента.`
    },
    {
      key: 'profile',
      icon: UserCheck,
      menu: '👤 Мой статус',
      command: '/profile',
      label: patientCommandLabel('/profile', 'Мой статус'),
      detail: 'Показывает привязку Telegram к карте пациента и последний визит.'
    },
    {
      key: 'settings',
      icon: Languages,
      menu: '⚙️ Настройки',
      command: '/settings',
      label: patientCommandLabel('/settings', 'Язык и уведомления'),
      detail: `Языки v1: ${patientLanguageSummary}. После выбора меню сразу обновляется.`
    },
    {
      key: 'support',
      icon: Phone,
      menu: '☎️ Связаться с клиникой',
      command: '/support',
      label: patientCommandLabel('/support', 'Связаться с клиникой'),
      detail: 'Подсказка для записи, кассы и срочных вопросов без медицинских данных в чате.'
    }
  ];
  const staffCapabilitySummary = [
    {
      key: 'roles',
      icon: Users,
      label: 'Ролевые меню',
      detail: `${staffRoleMenuEnablementRoleCount || staffRoles.length || 0} ролей, ${staffRoleMenuEnablementItemCount || staffMenuItemCount || 0} read-only пунктов.`
    },
    {
      key: 'commands',
      icon: MessageSquare,
      label: 'Staff-команды',
      detail: staffCommandNames.length ?
      `${staffCommandNames.join(' ')}; действия изменения состояния выключены.` :
      'Команды появятся после staff token и регистрации.'
    },
    {
      key: 'safety',
      icon: ShieldCheck,
      label: 'Безопасность',
      detail: staffAuditReady ?
      'RBAC, audit и подтверждения включены для read-only режима.' :
      'RBAC, audit и подтверждения обязательны перед действиями.'
    }
  ];

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
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="flex-start"
                gap={2}
                mb={2}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Что умеет Telegram-бот
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Patient bot работает с пациентом, staff/admin bot остаётся безопасным read-only слоем для сотрудников.
                  </Typography>
                </Box>
                <Badge variant={botStatus?.bot_active ? 'success' : 'warning'} size="small">
                  {botStatus?.mode === 'webhook' ? 'Webhook' : 'Polling'}
                </Badge>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={12} md={8}>
                  <Box
                    sx={{
                      border: '1px solid var(--mac-border-color, rgba(0,0,0,0.12))',
                      borderRadius: 8,
                      p: 2
                    }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1">
                        Пациентский бот
                      </Typography>
                      <Badge variant={enabledPatientFeatures.length ? 'success' : 'warning'} size="small">
                        {patientBot.version || 'v1'}
                      </Badge>
                    </Box>
                    <Box
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                        gap: 1.25
                      }}>
                      {patientCapabilities.map((item) => {
                        const Icon = item.icon;
                        return (
                          <Box
                            key={item.key}
                            sx={{
                              border: '1px solid var(--mac-border-color, rgba(0,0,0,0.12))',
                              borderRadius: 6,
                              p: 1.25,
                              minHeight: 128,
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 1
                            }}>
                            <Box display="flex" alignItems="center" gap={1}>
                              <Icon size={16} />
                              <Typography variant="body2" fontWeight={600}>
                                {item.menu}
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.secondary">
                              {item.detail}
                            </Typography>
                            <Box display="flex" justifyContent="space-between" alignItems="center" mt="auto" gap={1}>
                              <Typography variant="caption" color="text.secondary">
                                {item.label}
                              </Typography>
                              <Badge variant="info" size="small">
                                {item.command}
                              </Badge>
                            </Box>
                          </Box>);
                      })}
                    </Box>
                  </Box>
                </Grid>

                <Grid item xs={12} md={4}>
                  <Box
                    sx={{
                      border: '1px solid var(--mac-border-color, rgba(0,0,0,0.12))',
                      borderRadius: 8,
                      p: 2,
                      height: '100%'
                    }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1">
                        Staff/admin bot
                      </Typography>
                      <Badge variant={staffRoleMenuRuntimeEnabled ? 'success' : 'warning'} size="small">
                        Read-only
                      </Badge>
                    </Box>
                    <Box display="flex" flexDirection="column" gap={1.25}>
                      {staffCapabilitySummary.map((item) => {
                        const Icon = item.icon;
                        return (
                          <Box
                            key={item.key}
                            sx={{
                              border: '1px solid var(--mac-border-color, rgba(0,0,0,0.12))',
                              borderRadius: 6,
                              p: 1.25
                            }}>
                            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                              <Icon size={16} />
                              <Typography variant="body2" fontWeight={600}>
                                {item.label}
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.secondary">
                              {item.detail}
                            </Typography>
                          </Box>);
                      })}
                    </Box>
                  </Box>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

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
                    `${staffTokenSource}; ${staffTokenIssue}; ${staffTokenSecretVisibility}` :
                    'Dedicated staff bot token contract не опубликован'} />

                  <Badge
                    variant={staffTokenReady ? 'success' : 'warning'}
                    size="small">

                    {staffTokenReady ? 'Ready' : 'Required'}
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
                    primary="Staff link token validation"
                    secondary={staffLinkTokenValidationContract.contract_version ?
                    `${staffLinkTokenValidationContract.token_properties?.length || 0} token checks; helper: ${staffLinkTokenValidationContract.runtime_helper_available ? 'available' : 'planned'}; storage: ${staffLinkTokenValidationContract.storage_migration_required ? 'migration required' : 'ready'}` :
                    'Staff link token validation contract not published'} />

                  <Badge
                    variant={staffLinkTokenValidationContract.validator_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffLinkTokenValidationContract.runtime_helper_available ? 'Helper' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff link token storage"
                    secondary={staffLinkTokenStorageContract.contract_version ?
                    `${staffLinkTokenStorageContract.table || 'token table'}; indexes: ${staffLinkTokenStorageContract.required_indexes?.length || 0}; migration: ${staffLinkTokenStorageContract.migration_created ? 'created' : 'required'}` :
                    'Staff link token storage contract not published'} />

                  <Badge
                    variant={staffLinkTokenStorageContract.migration_created ? 'success' : 'warning'}
                    size="small">

                    {staffLinkTokenStorageContract.runtime_write_enabled ? 'Writes' : 'Planned'}
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
                    `${staffRoleMenuEnablementRoleCount} roles, ${staffRoleMenuEnablementItemCount} items; runtime menu: ${staffRoleMenuRuntimeEnabled ? 'enabled' : 'disabled'}; live data: ${staffRoleMenuDomainDataStatus}${staffRoleMenuDomainDataKeys.length ? ` (${staffRoleMenuDomainDataKeys.join(', ')})` : ''}` :
                    'Role menu enablement contract not published'} />

                  <Badge
                    variant={staffRoleMenuRuntimeEnabled ? 'success' : 'warning'}
                    size="small">

                    {staffRoleMenuRuntimeEnabled ? 'Enabled' : 'Required'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff command registration"
                    secondary={staffCommandNames.length ?
                    `${staffCommandNames.join(' ')}; registration: ${staffCommandRegistrationEnabled ? 'ready' : 'blocked until staff token'}; endpoint: ${staffCommandEndpointReady ? 'published' : 'planned'}` :
                    'Staff command contract не опубликован'} />

                  <Badge
                    variant={staffCommandRegistrationEnabled ? 'success' : 'warning'}
                    size="small">

                    {staffCommandRegistrationEnabled ? 'Ready' : staffCommandEndpointReady ? 'Endpoint' : 'Planned'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff action confirmations"
                    secondary={staffConfirmationOperations.length ?
                    `${staffConfirmationOperations.length} state-changing actions require confirmation; guard: ${staffConfirmationGuardReady ? 'ready' : 'pending'}; mode: ${staffConfirmationDenyOnly ? 'deny-only' : 'planned'}; actions: ${staffConfirmationActionsEnabled ? 'enabled' : 'disabled'}` :
                    'Confirmation contract не опубликован'} />

                  <Badge
                    variant={staffConfirmationGuardReady ? 'success' : 'warning'}
                    size="small">

                    {staffConfirmationGuardReady ? 'Guard' : 'Required'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff next runtime slice"
                    secondary={`${staffNextSlice}; token runtime: ${staffConfirmationTokenRuntimeEnabled ? 'enabled' : 'blocked'}; blockers: ${staffConfirmationBlockerSummary}`} />

                  <Badge
                    variant={staffConfirmationBlockedBy.length ? 'warning' : 'success'}
                    size="small">

                    {staffConfirmationBlockedBy.length ? 'Blocked' : 'Ready'}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff audit logging"
                    secondary={staffAuditEvents.length ?
                    `${staffAuditRecordedEvents.length} recorded, ${staffAuditPendingEvents.length} pending; writer: ${staffAuditContract.record_writer_enabled ? 'enabled' : 'disabled'}; read-only commands: ${staffAuditReadOnlyReady ? 'audited' : 'pending'}` :
                    'Audit contract не опубликован'} />

                  <Badge
                    variant={staffAuditReady ? 'success' : 'warning'}
                    size="small">

                    {staffAuditReady ? 'Ready' : 'Required'}
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
                  disabled={!staffCommandRegistrationEnabled || registeringStaffCommands}
                  onClick={registerStaffCommands}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <CheckCircle size={16} />
                  {registeringStaffCommands ? 'Регистрация staff-команд...' : 'Зарегистрировать staff-команды'}
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
                          <IconButton aria-label="Редактировать" title="Редактировать">
                            <Edit />
                          </IconButton>
                          <IconButton aria-label="Удалить" title="Удалить">
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
