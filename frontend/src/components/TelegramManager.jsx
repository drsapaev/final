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
  Input,
  Select,

  Switch,
  Textarea,

  Grid,
  List,
  Table } from
'./ui/macos';
import {
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeaderCell } from
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
  ClipboardList,
  CreditCard,
  FileText,
  Languages,
  Phone,
  ReceiptText,
  ShieldCheck,
  Smartphone,
  Stethoscope,
  Ticket,
  UserCog,
  UserCheck,
  Users } from


'lucide-react';
import { api } from '../api/client.js';

const TelegramManager = () => {
  const [botStatus, setBotStatus] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [onboardingRequests, setOnboardingRequests] = useState([]);
  const [onboardingTotal, setOnboardingTotal] = useState(0);
  const [onboardingReviewForms, setOnboardingReviewForms] = useState({});
  const [onboardingActionId, setOnboardingActionId] = useState('');
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
      const [statusRes, integrationRes, templatesRes, onboardingRes] = await Promise.all([
        api.get('/telegram/bot-status'),
        api.get('/admin/telegram/integration-status').catch(() => ({ data: null })),
        api.get('/admin/telegram/templates'),
        api.get('/telegram/onboarding/requests', {
          params: { status_filter: 'pending_review', limit: 20 }
        }).catch(() => ({ data: { items: [], total: 0 } }))
      ]);

      const statusData = statusRes?.data || {};
      const integrationData = integrationRes?.data || {};
      const templatesData = templatesRes?.data || {};
      const onboardingData = onboardingRes?.data || {};

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
      setOnboardingRequests(Array.isArray(onboardingData.items) ? onboardingData.items : []);
      setOnboardingTotal(Number(onboardingData.total ?? 0));
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Ошибка загрузки данных Telegram');
    } finally {
      setLoading(false);
    }
  };

  const loadOnboardingRequests = async () => {
    try {
      const response = await api.get('/telegram/onboarding/requests', {
        params: { status_filter: 'pending_review', limit: 20 }
      });
      const data = response?.data || {};
      setOnboardingRequests(Array.isArray(data.items) ? data.items : []);
      setOnboardingTotal(Number(data.total ?? 0));
    } catch (_err) {
      setError('Could not load REQUEST_REVIEW patient requests.');
    }
  };

  const updateOnboardingReviewForm = (requestId, field, value) => {
    setOnboardingReviewForms((current) => ({
      ...current,
      [requestId]: {
        ...(current[requestId] || {}),
        [field]: value
      }
    }));
  };

  const handleOnboardingReviewAction = async (requestId, action) => {
    const request = onboardingRequests.find((item) => item.id === requestId) || {};
    const form = onboardingReviewForms[requestId] || {};
    const reviewMessage = (form.reviewMessage || '').trim();
    const actionKey = `${action}:${requestId}`;
    let endpoint = `/telegram/onboarding/requests/${requestId}/${action}`;
    let payload = { reviewMessage: reviewMessage || undefined };

    if (action === 'link-existing') {
      const patientId = Number(form.patientId);
      if (!Number.isInteger(patientId) || patientId <= 0) {
        setError('Enter an existing patient ID before linking.');
        return;
      }
      payload = { patientId, reviewMessage: reviewMessage || undefined };
    } else if (action === 'create-patient') {
      const contactName = getOnboardingValue(request, 'contactName', 'contact_name', '');
      const contactPhone = getOnboardingValue(request, 'contactPhone', 'contact_phone', '');
      const nameParts = splitOnboardingContactName(contactName);
      const lastName = (form.lastName || nameParts.lastName || '').trim();
      const firstName = (form.firstName || nameParts.firstName || '').trim();
      const middleName = (form.middleName || nameParts.middleName || '').trim();
      const phone = (form.phone || contactPhone || '').trim();

      if (!lastName || !firstName) {
        setError('Enter first and last name before creating a Patient.');
        return;
      }

      endpoint = `/telegram/onboarding/requests/${requestId}/create-patient`;
      payload = {
        patient: {
          last_name: lastName,
          first_name: firstName,
          ...(middleName ? { middle_name: middleName } : {}),
          ...(phone ? { phone } : {})
        },
        reviewMessage: reviewMessage || undefined
      };
    }

    try {
      setError('');
      setSuccess('');
      setOnboardingActionId(actionKey);
      await api.post(endpoint, payload);
      setSuccess('REQUEST_REVIEW request updated.');
      setOnboardingReviewForms((current) => {
        const next = { ...current };
        delete next[requestId];
        return next;
      });
      await loadOnboardingRequests();
    } catch (_err) {
      setError('Could not update REQUEST_REVIEW request. Check staff role and request status.');
    } finally {
      setOnboardingActionId('');
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
    (feature) =>
      feature?.key === 'patient_payments_mini_app_entry' ||
      feature?.key === 'patient_payments_protected_entry'
  );
  const patientFormsEntryFeature = patientBotFeatures.find(
    (feature) =>
      feature?.key === 'patient_forms_entrypoint' ||
      feature?.key === 'patient_forms_placeholder'
  );
  const patientPaymentEntryRoute =
    patientPaymentEntryFeature?.contract?.route ||
    '/telegram/mini-app/patient?section=payments';
  const patientFormsEntryRoute =
    patientFormsEntryFeature?.contract?.route ||
    '/telegram/mini-app/patient?section=forms';
  const patientMiniAppManifestFeature = patientBotFeatures.find(
    (feature) => feature?.key === 'patient_mini_app_manifest'
  );
  const patientMiniAppManifestEndpoint =
    patientMiniAppManifestFeature?.contract?.endpoint ||
    '/api/v1/telegram/mini-app/patient/manifest';
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
  const staffConfirmationIdempotencyReady = Boolean(
    staffConfirmationContract.idempotency_request_hash_runtime_enabled ||
    staffConfirmationRuntime.idempotency_request_hash_runtime_enabled
  );
  const staffConfirmationBlockedBy = Array.isArray(staffConfirmationContract.runtime_blocked_by) ?
  staffConfirmationContract.runtime_blocked_by :
  [];
  const staffConfirmationBlockerSummary = staffConfirmationBlockedBy.length ?
  staffConfirmationBlockedBy.join(', ') :
  'none';
  const staffDomainAdapterContract =
  staffBot.domain_adapter_contract || staffConfirmationContract.domain_adapter_contract || {};
  const staffDomainAdapters = Array.isArray(staffDomainAdapterContract.adapters) ?
  staffDomainAdapterContract.adapters :
  [];
  const staffQueueDomainAdapters = staffDomainAdapters.filter((adapter) => adapter?.domain === 'queue');
  const readyStaffDomainAdapters = staffDomainAdapters.filter((adapter) => adapter?.runtime_enabled);
  const staffDomainAdapterBlockedBy = Array.isArray(staffDomainAdapterContract.blocked_by) ?
  staffDomainAdapterContract.blocked_by :
  [];
  const staffQueueAdapterCommands = staffQueueDomainAdapters.flatMap((adapter) =>
  Array.isArray(adapter?.telegram_commands) ? adapter.telegram_commands : []
  );
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
  const staffAuditRequiredStateEvents = Array.isArray(staffAuditContract.required_state_change_event_types) ?
  staffAuditContract.required_state_change_event_types :
  [];
  const staffAuditPendingStateEvents = Array.isArray(staffAuditRuntime.pending_state_change_event_types) ?
  staffAuditRuntime.pending_state_change_event_types :
  staffAuditRequiredStateEvents;
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
      key: 'services',
      icon: Smartphone,
      menu: '📲 Онлайн-сервисы',
      command: '/services',
      label: patientCommandLabel('/services', 'Все функции бота'),
      detail: patientMiniAppManifestFeature?.enabled
        ? `Backend Mini App manifest готов: ${patientMiniAppManifestEndpoint}; требует initData и не раскрывает записи.`
        : 'Открывает видимую карту подключённых и будущих функций, включая безопасные заглушки.'
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
      key: 'visits',
      icon: Calendar,
      menu: '📅 Мои визиты',
      command: '/visits',
      label: patientCommandLabel('/visits', 'Мои визиты'),
      detail: 'Показывает последние и сегодняшние визиты без диагнозов, услуг и медицинских деталей.'
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
      key: 'forms',
      icon: ClipboardList,
      menu: '📋 Анкеты пациента',
      command: '/forms',
      label: patientCommandLabel('/forms', 'Анкеты пациента'),
      detail: patientFormsEntryFeature?.enabled
        ? `Запускает пациентские анкеты в защищенном Mini App: ${patientFormsEntryRoute}.`
        : 'Раздел пока не включен для этого пациента.'
    },
    {
      key: 'documents',
      icon: ReceiptText,
      menu: '🧾 Документы и чеки',
      command: '/documents',
      label: patientCommandLabel('/documents', 'Документы и чеки'),
      detail: 'Будущий защищённый вход к чекам и документам; внутренние номера не отправляются в Telegram.'
    },
    {
      key: 'doctors',
      icon: Stethoscope,
      menu: '🧑‍⚕️ Врачи и расписание',
      command: '/doctors',
      label: patientCommandLabel('/doctors', 'Врачи и расписание'),
      detail: 'Пока показывает безопасную подсказку; запись и расписание остаются через регистратуру.'
    },
    {
      key: 'cabinet',
      icon: Smartphone,
      menu: '📲 Кабинет пациента',
      command: '/cabinet',
      label: patientCommandLabel('/cabinet', 'Кабинет пациента'),
      detail: 'Будущий защищённый вход к Mini App/кабинету, без приёма медицинских данных в чате.'
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
    },
    {
      key: 'staff',
      icon: UserCog,
      menu: '👥 Режим сотрудника',
      command: '/staff',
      label: patientCommandLabel('/staff', 'Режим сотрудника'),
      detail: 'Видимый вход для сотрудников: только персональная ссылка администратора или привязанный staff-профиль.'
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
  const templateTypeOptions = [
    { value: 'text', label: 'Текст' },
    { value: 'photo', label: 'Фото' },
    { value: 'document', label: 'Документ' }
  ];
  const getOnboardingValue = (request, camelKey, snakeKey, fallback = '') =>
    request?.[camelKey] ?? request?.[snakeKey] ?? fallback;
  const splitOnboardingContactName = (value) => {
    const parts = String(value || '').trim().split(/\s+/).filter(Boolean);
    return {
      lastName: parts[0] || '',
      firstName: parts[1] || '',
      middleName: parts.slice(2).join(' ')
    };
  };
  const formatOnboardingDate = (value) => {
    if (!value) return 'not selected';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };
  const formatOnboardingCreatedAt = (value) => {
    if (!value) return 'new';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'new';
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };
  const onboardingStatusVariant = (status) => {
    if (status === 'pending_review') return 'warning';
    if (status === 'linked_existing' || status === 'created_patient') return 'success';
    if (status === 'needs_more_info') return 'primary';
    if (status === 'rejected' || status === 'expired') return 'danger';
    return 'default';
  };
  const iconActionStyle = {
    width: 32,
    minHeight: 32,
    padding: 0
  };

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
                    <Box display="flex" sx={{ flexDirection: 'column' }} gap={1.25}>
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
                    `${staffConfirmationOperations.length} state-changing actions require confirmation; guard: ${staffConfirmationGuardReady ? 'ready' : 'pending'}; replay: ${staffConfirmationIdempotencyReady ? 'ready' : 'pending'}; actions: ${staffConfirmationActionsEnabled ? 'enabled' : 'disabled'}` :
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
                    primary="Staff queue action adapters"
                    secondary={staffQueueDomainAdapters.length ?
                    `${readyStaffDomainAdapters.length}/${staffDomainAdapters.length} adapters enabled; queue commands: ${staffQueueAdapterCommands.join(' ') || 'none'}; blockers: ${staffDomainAdapterBlockedBy.join(', ') || 'none'}` :
                    'Queue action adapter contract not published'} />

                  <Badge
                    variant={staffDomainAdapterContract.runtime_enabled ? 'success' : 'warning'}
                    size="small">

                    {staffDomainAdapterContract.runtime_enabled ? 'Enabled' : 'Blocked'}
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
                    `${staffAuditRecordedEvents.length} recorded, ${staffAuditPendingEvents.length} pending; state-change pending: ${staffAuditPendingStateEvents.join(', ') || 'none'}; writer: ${staffAuditContract.record_writer_enabled ? 'enabled' : 'disabled'}; read-only commands: ${staffAuditReadOnlyReady ? 'audited' : 'pending'}` :
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
              <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={2} mb={2}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    REQUEST_REVIEW patient requests
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Unknown Telegram users can submit only an onboarding request. Staff must link an existing patient or ask for safe extra details before any protected workflow opens.
                  </Typography>
                </Box>
                <Box display="flex" gap={1} alignItems="center">
                  <Badge variant={onboardingTotal > 0 ? 'warning' : 'success'} size="small">
                    {onboardingTotal} pending
                  </Badge>
                  <Button
                    type="button"
                    variant="outlined"
                    size="small"
                    onClick={loadOnboardingRequests}
                    aria-label="Refresh REQUEST_REVIEW requests">
                    <RefreshCw size={16} />
                    Refresh
                  </Button>
                </Box>
              </Box>

              {!onboardingRequests.length ? (
                <Alert severity="info">
                  No pending REQUEST_REVIEW requests. Unknown patients still get a safe appointment request CTA instead of confirmed booking.
                </Alert>
              ) : (
                <div style={{ width: '100%', overflowX: 'auto' }}>
                  <Table style={{ minWidth: 1080 }}>
                    <TableHead>
                      <TableRow>
                        <TableHeaderCell>Request</TableHeaderCell>
                        <TableHeaderCell>Contact</TableHeaderCell>
                        <TableHeaderCell>Desired visit</TableHeaderCell>
                        <TableHeaderCell>Review</TableHeaderCell>
                        <TableHeaderCell align="right">Actions</TableHeaderCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {onboardingRequests.map((request) => {
                        const requestId = request.id;
                        const form = onboardingReviewForms[requestId] || {};
                        const contactName = getOnboardingValue(request, 'contactName', 'contact_name', 'No name');
                        const contactPhone = getOnboardingValue(request, 'contactPhone', 'contact_phone', 'No phone');
                        const contactNameParts = splitOnboardingContactName(contactName);
                        const createLastName = (form.lastName || contactNameParts.lastName || '').trim();
                        const createFirstName = (form.firstName || contactNameParts.firstName || '').trim();
                        const canCreatePatient = Boolean(createLastName && createFirstName);
                        const desiredService = getOnboardingValue(request, 'desiredService', 'desired_service', 'Service not selected');
                        const desiredBranch = getOnboardingValue(request, 'desiredBranch', 'desired_branch', 'Branch not selected');
                        const desiredDate = getOnboardingValue(request, 'desiredDate', 'desired_date', '');
                        const desiredTime = getOnboardingValue(request, 'desiredTime', 'desired_time', '');
                        const desiredDoctorId = getOnboardingValue(request, 'desiredDoctorId', 'desired_doctor_id', '');
                        const note = getOnboardingValue(request, 'note', 'note', '');
                        const createdAt = getOnboardingValue(request, 'createdAt', 'created_at', '');
                        const status = request.status || 'pending_review';
                        const linkActionId = `link-existing:${requestId}`;
                        const createPatientActionId = `create-patient:${requestId}`;
                        const moreInfoActionId = `request-more-info:${requestId}`;
                        const rejectActionId = `reject:${requestId}`;
                        const actionBusy = onboardingActionId.endsWith(`:${requestId}`);

                        return (
                          <TableRow key={requestId} hover>
                            <TableCell>
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={0.5}>
                                <Typography variant="body2" fontWeight={600}>
                                  #{requestId}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {formatOnboardingCreatedAt(createdAt)}
                                </Typography>
                                <Badge variant={onboardingStatusVariant(status)} size="small">
                                  {status}
                                </Badge>
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={0.5}>
                                <Typography variant="body2">{contactName}</Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {contactPhone}
                                </Typography>
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={0.5}>
                                <Typography variant="body2">{desiredService}</Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {desiredBranch}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {formatOnboardingDate(desiredDate)} {desiredTime}
                                  {desiredDoctorId ? `, doctor #${desiredDoctorId}` : ''}
                                </Typography>
                                {note && (
                                  <Typography variant="caption" color="text.secondary">
                                    Note: {note}
                                  </Typography>
                                )}
                              </Box>
                            </TableCell>
                            <TableCell>
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={1}>
                                <Input
                                  label="Existing patient ID"
                                  value={form.patientId || ''}
                                  onChange={(event) => updateOnboardingReviewForm(requestId, 'patientId', event.target.value)}
                                  inputMode="numeric"
                                  placeholder="12345"
                                  style={{ width: 180 }} />
                                <Box display="flex" gap={1} sx={{ flexWrap: 'wrap' }}>
                                  <Input
                                    label="Last name"
                                    value={form.lastName ?? contactNameParts.lastName}
                                    onChange={(event) => updateOnboardingReviewForm(requestId, 'lastName', event.target.value)}
                                    placeholder="Last"
                                    style={{ width: 150 }} />
                                  <Input
                                    label="First name"
                                    value={form.firstName ?? contactNameParts.firstName}
                                    onChange={(event) => updateOnboardingReviewForm(requestId, 'firstName', event.target.value)}
                                    placeholder="First"
                                    style={{ width: 150 }} />
                                  <Input
                                    label="Phone"
                                    value={form.phone ?? contactPhone}
                                    onChange={(event) => updateOnboardingReviewForm(requestId, 'phone', event.target.value)}
                                    placeholder="+998..."
                                    style={{ width: 180 }} />
                                </Box>
                                <Textarea
                                  label="Patient-facing safe message"
                                  value={form.reviewMessage || ''}
                                  maxLength={512}
                                  minRows={2}
                                  maxRows={4}
                                  onChange={(event) => updateOnboardingReviewForm(requestId, 'reviewMessage', event.target.value)}
                                  placeholder="Ask for safe contact details or explain decision"
                                  style={{ minWidth: 280 }} />
                              </Box>
                            </TableCell>
                            <TableCell align="right">
                              <Box display="inline-flex" sx={{ flexDirection: 'column' }} gap={1} alignItems="stretch">
                                <Button
                                  type="button"
                                  variant="contained"
                                  size="small"
                                  disabled={actionBusy || !form.patientId}
                                  onClick={() => handleOnboardingReviewAction(requestId, 'link-existing')}>
                                  <UserCheck size={16} />
                                  {onboardingActionId === linkActionId ? 'Linking...' : 'Link existing'}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outlined"
                                  size="small"
                                  disabled={actionBusy || !canCreatePatient}
                                  onClick={() => handleOnboardingReviewAction(requestId, 'create-patient')}>
                                  <Plus size={16} />
                                  {onboardingActionId === createPatientActionId ? 'Creating...' : 'Create patient'}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outlined"
                                  size="small"
                                  disabled={actionBusy}
                                  onClick={() => handleOnboardingReviewAction(requestId, 'request-more-info')}>
                                  <MessageSquare size={16} />
                                  {onboardingActionId === moreInfoActionId ? 'Sending...' : 'Need info'}
                                </Button>
                                <Button
                                  type="button"
                                  variant="outlined"
                                  size="small"
                                  disabled={actionBusy}
                                  onClick={() => handleOnboardingReviewAction(requestId, 'reject')}>
                                  <Trash2 size={16} />
                                  {onboardingActionId === rejectActionId ? 'Rejecting...' : 'Reject'}
                                </Button>
                              </Box>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Шаблоны сообщений
              </Typography>
              <div style={{ width: '100%', overflowX: 'auto' }}>
                <Table style={{ minWidth: 640 }}>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Название</TableHeaderCell>
                      <TableHeaderCell>Тип</TableHeaderCell>
                      <TableHeaderCell>Статус</TableHeaderCell>
                      <TableHeaderCell align="right">Действия</TableHeaderCell>
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
                          <Box display="inline-flex" gap={0.5} justifyContent="flex-end">
                            <Button
                              type="button"
                              variant="ghost"
                              size="small"
                              aria-label="Редактировать"
                              title="Редактировать"
                              style={iconActionStyle}>
                              <Edit size={16} />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="small"
                              aria-label="Удалить"
                              title="Удалить"
                              style={iconActionStyle}>
                              <Trash2 size={16} />
                            </Button>
                          </Box>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Dialog open={showTemplateDialog} onClose={() => setShowTemplateDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Создать шаблон сообщения</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <Input
                label="Название шаблона"
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                style={{ width: '100%' }}
                required />

            </Grid>
            <Grid item xs={12} sm={6}>
              <Select
                label="Тип сообщения"
                value={templateForm.message_type}
                options={templateTypeOptions}
                onChange={(messageType) => setTemplateForm({ ...templateForm, message_type: messageType })}
                style={{ width: '100%' }} />
            </Grid>
            <Grid item xs={12}>
              <Textarea
                label="Содержание сообщения"
                minRows={6}
                maxRows={8}
                value={templateForm.content}
                onChange={(e) => setTemplateForm({ ...templateForm, content: e.target.value })}
                required
                style={{ width: '100%' }}
                placeholder="Используйте переменные: {patient_name}, {appointment_date}, {doctor_name}" />

            </Grid>
            <Grid item xs={12}>
              <Switch
                label="Активный шаблон"
                checked={templateForm.is_active}
                onChange={(isActive) => setTemplateForm({ ...templateForm, is_active: isActive })} />

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
