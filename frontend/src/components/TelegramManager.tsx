import { useState, useEffect, useMemo, useCallback } from 'react';
import type { CSSProperties } from 'react';  // PR-41 / High-16: added memoization hooks
import { useTranslation } from 'react-i18next';
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
  Table,
} from './ui/macos';
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
import { api } from '../api/client';

const ONBOARDING_STATUS_FILTER_OPTIONS = [
{ value: 'all', label: 'All statuses' },
{ value: 'pending_review', label: 'Pending review' },
{ value: 'needs_more_info', label: 'Needs more info' },
{ value: 'linked_existing', label: 'Linked existing' },
{ value: 'created_patient', label: 'Created patient' },
{ value: 'rejected', label: 'Rejected' },
{ value: 'expired', label: 'Expired' },
{ value: 'cancelled', label: 'Cancelled' }];

const ONBOARDING_SORT_OPTIONS = [
{ value: 'newest', label: 'Newest first' },
{ value: 'oldest', label: 'Oldest first' },
{ value: 'highest_confidence', label: 'Highest confidence' },
{ value: 'sla_overdue', label: 'SLA overdue' }];

const ONBOARDING_NEEDS_MORE_INFO_REASONS = [
{ value: 'wrong_contact', label: 'Wrong contact' },
{ value: 'patient_unreachable', label: 'Patient unreachable' },
{ value: 'duplicate_suspected', label: 'Duplicate suspected' },
{ value: 'other', label: 'Other' }];

const ONBOARDING_REJECT_REASONS = [
{ value: 'wrong_contact', label: 'Wrong contact' },
{ value: 'patient_unreachable', label: 'Patient unreachable' },
{ value: 'duplicate_suspected', label: 'Duplicate suspected' },
{ value: 'invalid_identity', label: 'Invalid identity' },
{ value: 'not_clinic_patient', label: 'Not a clinic patient' },
{ value: 'other', label: 'Other' }];

const ONBOARDING_OVERRIDE_REASONS = [
{ value: 'duplicate_suspected', label: 'Duplicate reviewed' },
{ value: 'other', label: 'Other' }];

const ONBOARDING_STATUS_LABELS = {
  pending_review: 'Pending review',
  needs_more_info: 'Needs more info',
  linked_existing: 'Linked existing',
  created_patient: 'Created patient',
  rejected: 'Rejected',
  expired: 'Expired',
  cancelled: 'Cancelled'
};

const ONBOARDING_REASON_LABELS = {
  wrong_contact: 'Wrong contact',
  patient_unreachable: 'Patient unreachable',
  duplicate_suspected: 'Duplicate suspected',
  invalid_identity: 'Invalid identity',
  not_clinic_patient: 'Not a clinic patient',
  other: 'Other'
};

const TelegramManager = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [botStatus, setBotStatus] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [onboardingRequests, setOnboardingRequests] = useState([]);
  const [onboardingTotal, setOnboardingTotal] = useState(0);
  const [onboardingReviewForms, setOnboardingReviewForms] = useState({});
  const [onboardingActionId, setOnboardingActionId] = useState('');
  const [onboardingAnalytics, setOnboardingAnalytics] = useState(null);
  const [onboardingStatusFilter, setOnboardingStatusFilter] = useState('all');
  const [onboardingSort, setOnboardingSort] = useState('newest');
  const [onboardingDialog, setOnboardingDialog] = useState({
    open: false,
    action: '',
    requestId: null,
    candidateId: ''
  });
  const [exportingOnboardingCsv, setExportingOnboardingCsv] = useState(false);
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
  } as any);

  useEffect(() => {
    loadTelegramData();
  }, []);

  useEffect(() => {
    loadOnboardingRequests();
  }, [onboardingStatusFilter, onboardingSort]);

  const getOnboardingSearchPayload = (request, form = {}) => {
    const contactName = getOnboardingValue(request, 'contactName', 'contact_name', '');
    const contactPhone = getOnboardingValue(request, 'contactPhone', 'contact_phone', '');
    const desiredBranch = getOnboardingValue(request, 'desiredBranch', 'desired_branch', '');
    const desiredDate = getOnboardingValue(request, 'desiredDate', 'desired_date', '');
    const desiredDoctorId = getOnboardingValue(request, 'desiredDoctorId', 'desired_doctor_id', '');
    const contactNameParts = splitOnboardingContactName(contactName);
    const draftName = [
    form.lastName || contactNameParts.lastName,
    form.firstName || contactNameParts.firstName].
    filter(Boolean).join(' ').trim();

    return {
      ...(form.phone || contactPhone ? { phone: (form.phone || contactPhone).trim() } : {}),
      ...(draftName ? { name: draftName } : {}),
      ...(desiredBranch ? { branch: desiredBranch } : {}),
      ...(desiredDoctorId ? { doctorId: Number(desiredDoctorId) } : {}),
      ...(desiredDate ? { preferredDateFrom: desiredDate, preferredDateTo: desiredDate } : {})
    };
  };

  const hydrateOnboardingRequests = async (items) => {
    const hydrated = await Promise.all((items || []).map(async (request) => {
      if (!['pending_review', 'needs_more_info'].includes(request.status)) {
        return {
          ...request,
          duplicateCandidates: request.duplicateCandidates || [],
          duplicateSearch: request.duplicateSearch || null
        };
      }

      try {
        const response = await api.post(
          `/telegram/onboarding/requests/${request.id}/search-patients`,
          getOnboardingSearchPayload(request, onboardingReviewForms[request.id] || {})
        );
        return {
          ...request,
          duplicateCandidates: Array.isArray(response?.data?.candidates) ? response.data.candidates : [],
          duplicateSearch: response?.data || null
        };
      } catch (_error) {
        return {
          ...request,
          duplicateCandidates: request.duplicateCandidates || [],
          duplicateSearch: request.duplicateSearch || null
        };
      }
    }));

    return hydrated;
  };

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
      await loadOnboardingRequests();
      await loadOnboardingAnalytics();
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || t('misc.tg_err_load'));
    } finally {
      setLoading(false);
    }
  };

  const loadOnboardingRequests = async () => {
    try {
      const statusFilterValue = onboardingStatusFilter === 'all' ? '' : onboardingStatusFilter;
      const response = await api.get('/telegram/onboarding/requests', {
        params: { status_filter: statusFilterValue, limit: 40 }
      }) as any;
      const data = response?.data || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const hydratedItems = await hydrateOnboardingRequests(items);
      setOnboardingRequests(hydratedItems);
      setOnboardingTotal(Number(data.total ?? hydratedItems.length ?? 0));
    } catch (_err) {
      setError('Could not load REQUEST_REVIEW patient requests.');
    }
  };

  const loadOnboardingAnalytics = async () => {
    try {
      const response = await api.get('/telegram/onboarding/analytics/summary') as any;
      setOnboardingAnalytics(response?.data || null);
    } catch (_err) {
      setOnboardingAnalytics(null);
    }
  };

  const handleExportOnboardingCsv = async () => {
    try {
      setExportingOnboardingCsv(true);
      const statusFilterValue = onboardingStatusFilter === 'all' ? '' : onboardingStatusFilter;
      const response = await api.get('/telegram/onboarding/requests/export', {
        params: { status_filter: statusFilterValue },
        responseType: 'blob'
      }) as any;
      const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'telegram_onboarding_requests.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setSuccess('Masked onboarding CSV exported.');
    } catch (_err) {
      setError('Could not export onboarding CSV.');
    } finally {
      setExportingOnboardingCsv(false);
    }
  };

  // PR-41 / High-16: wrap handler in useCallback to avoid re-creating on every render
  const updateOnboardingReviewForm = useCallback((requestId, field, value) => {
    setOnboardingReviewForms((current) => ({
      ...current,
      [requestId]: {
        ...(current[requestId] || {}),
        [field]: value
      }
    }));
  }, []);

  const closeOnboardingDialog = () => {
    setOnboardingDialog({
      open: false,
      action: '',
      requestId: null,
      candidateId: ''
    });
  };

  const openOnboardingActionDialog = (requestId, action, candidateId = '') => {
    setOnboardingDialog({
      open: true,
      action,
      requestId,
      candidateId
    });
  };

  const refreshOnboardingCandidates = async (requestId) => {
    const request = onboardingRequests.find((item) => item.id === requestId);
    if (!request) {
      return;
    }

    try {
      setOnboardingActionId(`search:${requestId}`);
      const response = await api.post(
        `/telegram/onboarding/requests/${requestId}/search-patients`,
        getOnboardingSearchPayload(request, onboardingReviewForms[requestId] || {})
      );
      setOnboardingRequests((current) => current.map((item) => item.id === requestId ? {
        ...item,
        duplicateCandidates: Array.isArray(response?.data?.candidates) ? response.data.candidates : [],
        duplicateSearch: response?.data || null
      } : item));
    } catch (_err) {
      setError('Could not refresh duplicate candidates.');
    } finally {
      setOnboardingActionId('');
    }
  };

  const handleOnboardingReviewAction = async (requestId, action, options = {}) => {
    const request = onboardingRequests.find((item) => item.id === requestId) || {};
    const form = onboardingReviewForms[requestId] || {};
    const safeNote = (form.safeNote || '').trim();
    const reasonCode = form.reasonCode || undefined;
    const actionKey = `${action}:${requestId}`;
    let endpoint = `/telegram/onboarding/requests/${requestId}/${action}`;
    let payload = { reasonCode, safeNote: safeNote || undefined };

    if (action === 'link-existing') {
      const candidateId = options.candidateId || form.selectedCandidateId || onboardingDialog.candidateId;
      if (!candidateId) {
        setError('Select a duplicate candidate before linking.');
        return;
      }
      endpoint = `/telegram/onboarding/requests/${requestId}/link-existing`;
      payload = {
        candidateId,
        ...(reasonCode ? { reasonCode } : {}),
        ...(safeNote ? { safeNote } : {})
      };
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

      const highConfidenceCandidateExists = Boolean(
        request?.duplicateSearch?.highConfidenceCandidateExists ||
        request?.duplicateReviewSnapshot?.highConfidenceCandidateExists
      );
      if (highConfidenceCandidateExists && !form.confirmCreateDespiteDuplicates) {
        setError('High-confidence duplicate found. Confirm create despite duplicates or link the existing patient.');
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
        ...(form.selectedCandidateId ? { reviewCandidateId: form.selectedCandidateId } : {}),
        ...(reasonCode ? { reasonCode } : {}),
        ...(safeNote ? { safeNote } : {}),
        confirmCreateDespiteDuplicates: Boolean(form.confirmCreateDespiteDuplicates)
      };
    } else if (action === 'request-more-info' || action === 'reject') {
      if (!reasonCode) {
        setError('Choose a reason code before continuing.');
        return;
      }
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
      closeOnboardingDialog();
      await loadOnboardingRequests();
      await loadOnboardingAnalytics();
    } catch (_err) {
      setError('Could not update REQUEST_REVIEW request. Check staff role and request status.');
    } finally {
      setOnboardingActionId('');
    }
  };

  const handleCreateTemplate = async () => {
    setError(t('misc.tg_err_template_create'));
  };

  const registerPatientCommands = async () => {
    try {
      setError('');
      setSuccess('');
      setRegisteringCommands(true);
      const response = await api.post('/admin/telegram/register-patient-commands') as any;
      const languages = Array.isArray(response?.data?.registered_languages) ?
      response.data.registered_languages.join(', ') :
      'ru, uz';
      setSuccess(t('misc.tg_success_patient_commands', { languages }));
      await loadTelegramData();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || detail?.error;
      setError(message || e?.message || t('misc.tg_err_register_commands'));
    } finally {
      setRegisteringCommands(false);
    }
  };

  const registerStaffCommands = async () => {
    try {
      setError('');
      setSuccess('');
      setRegisteringStaffCommands(true);
      const response = await api.post('/admin/telegram/register-staff-commands') as any;
      const commands = Array.isArray(response?.data?.registered_commands) ?
      response.data.registered_commands.join(', ') :
      'read-only staff commands';
      setSuccess(t('misc.tg_success_staff_commands', { commands }));
      await loadTelegramData();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const message = typeof detail === 'string' ? detail : detail?.message || detail?.error;
      setError(message || e?.message || t('misc.tg_err_register_staff_commands'));
    } finally {
      setRegisteringStaffCommands(false);
    }
  };

  // PR-41 / High-16: memoize filtered/derived arrays BEFORE any early return
  // (React Hooks must be called in the same order on every render).
  const patientBot = botStatus?.patient_bot || {};
  const patientBotFeatures = Array.isArray(patientBot.features) ? patientBot.features : [];
  const enabledPatientFeatures = useMemo(
    () => patientBotFeatures.filter((feature) => feature?.enabled),
    [patientBotFeatures]
  );
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
  // PR-41 / High-16: memoize filtered array
  const readyStaffControls = useMemo(
    () => staffBotReadiness.filter((item) => item?.ready),
    [staffBotReadiness]
  );
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
  t('misc.tg_lang_russian');
  const patientCapabilities = [
    {
      key: 'book',
      icon: Calendar,
      menu: t('misc.tg_cmd_book_menu'),
      command: '/book',
      label: patientCommandLabel('/book', t('misc.tg_cmd_book_label')),
      detail: t('misc.tg_cmd_book_detail')
    },
    {
      key: 'services',
      icon: Smartphone,
      menu: t('misc.tg_cmd_services_menu'),
      command: '/services',
      label: patientCommandLabel('/services', t('misc.tg_cmd_services_label')),
      detail: patientMiniAppManifestFeature?.enabled
        ? t('misc.tg_cmd_services_detail_manifest', { endpoint: patientMiniAppManifestEndpoint })
        : t('misc.tg_cmd_services_detail')
    },
    {
      key: 'queue',
      icon: Ticket,
      menu: t('misc.tg_cmd_queue_menu'),
      command: '/queue',
      label: patientCommandLabel('/queue', t('misc.tg_cmd_queue_label')),
      detail: t('misc.tg_cmd_queue_detail')
    },
    {
      key: 'visits',
      icon: Calendar,
      menu: t('misc.tg_cmd_visits_menu'),
      command: '/visits',
      label: patientCommandLabel('/visits', t('misc.tg_cmd_visits_label')),
      detail: t('misc.tg_cmd_visits_detail')
    },
    {
      key: 'payments',
      icon: CreditCard,
      menu: t('misc.tg_cmd_payments_menu'),
      command: '/payments',
      label: patientCommandLabel('/payments', t('misc.tg_cmd_payments_label')),
      detail: patientPaymentEntryFeature?.enabled
        ? t('misc.tg_cmd_payments_detail_entry', { route: patientPaymentEntryRoute })
        : t('misc.tg_cmd_payments_detail')
    },
    {
      key: 'results',
      icon: FileText,
      menu: t('misc.tg_cmd_results_menu'),
      command: '/results',
      label: patientCommandLabel('/results', t('misc.tg_cmd_results_label')),
      detail: t('misc.tg_cmd_results_detail', { count: patientBot.max_pdf_reports_per_request || 3 })
    },
    {
      key: 'forms',
      icon: ClipboardList,
      menu: t('misc.tg_cmd_forms_menu'),
      command: '/forms',
      label: patientCommandLabel('/forms', t('misc.tg_cmd_forms_label')),
      detail: patientFormsEntryFeature?.enabled
        ? t('misc.tg_cmd_forms_detail_entry', { route: patientFormsEntryRoute })
        : t('misc.tg_cmd_forms_detail')
    },
    {
      key: 'documents',
      icon: ReceiptText,
      menu: t('misc.tg_cmd_documents_menu'),
      command: '/documents',
      label: patientCommandLabel('/documents', t('misc.tg_cmd_documents_label')),
      detail: t('misc.tg_cmd_documents_detail')
    },
    {
      key: 'doctors',
      icon: Stethoscope,
      menu: t('misc.tg_cmd_doctors_menu'),
      command: '/doctors',
      label: patientCommandLabel('/doctors', t('misc.tg_cmd_doctors_label')),
      detail: t('misc.tg_cmd_doctors_detail')
    },
    {
      key: 'cabinet',
      icon: Smartphone,
      menu: t('misc.tg_cmd_cabinet_menu'),
      command: '/cabinet',
      label: patientCommandLabel('/cabinet', t('misc.tg_cmd_cabinet_label')),
      detail: t('misc.tg_cmd_cabinet_detail')
    },
    {
      key: 'profile',
      icon: UserCheck,
      menu: t('misc.tg_cmd_profile_menu'),
      command: '/profile',
      label: patientCommandLabel('/profile', t('misc.tg_cmd_profile_label')),
      detail: t('misc.tg_cmd_profile_detail')
    },
    {
      key: 'settings',
      icon: Languages,
      menu: t('misc.tg_cmd_settings_menu'),
      command: '/settings',
      label: patientCommandLabel('/settings', t('misc.tg_cmd_settings_label')),
      detail: t('misc.tg_cmd_settings_detail', { languages: patientLanguageSummary })
    },
    {
      key: 'support',
      icon: Phone,
      menu: t('misc.tg_cmd_support_menu'),
      command: '/support',
      label: patientCommandLabel('/support', t('misc.tg_cmd_support_label')),
      detail: t('misc.tg_cmd_support_detail')
    },
    {
      key: 'staff',
      icon: UserCog,
      menu: t('misc.tg_cmd_staff_menu'),
      command: '/staff',
      label: patientCommandLabel('/staff', t('misc.tg_cmd_staff_label')),
      detail: t('misc.tg_cmd_staff_detail')
    }
  ];
  const staffCapabilitySummary = [
    {
      key: 'roles',
      icon: Users,
      label: t('misc.tg_staff_cap_roles_label'),
      detail: t('misc.tg_staff_cap_roles_detail', { roleCount: staffRoleMenuEnablementRoleCount || staffRoles.length || 0, itemCount: staffRoleMenuEnablementItemCount || staffMenuItemCount || 0 })
    },
    {
      key: 'commands',
      icon: MessageSquare,
      label: t('misc.tg_staff_cap_commands_label'),
      detail: staffCommandNames.length ?
      t('misc.tg_staff_cap_commands_detail_list', { commands: staffCommandNames.join(' ') }) :
      t('misc.tg_staff_cap_commands_detail_empty')
    },
    {
      key: 'safety',
      icon: ShieldCheck,
      label: t('misc.tg_staff_cap_safety_label'),
      detail: staffAuditReady ?
      t('misc.tg_staff_cap_safety_detail_ready') :
      t('misc.tg_staff_cap_safety_detail_pending')
    }
  ];
  const templateTypeOptions = [
    { value: 'text', label: t('misc.tg_tpl_type_text') },
    { value: 'photo', label: t('misc.tg_tpl_type_photo') },
    { value: 'document', label: t('misc.tg_tpl_type_document') }
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
  const getOnboardingAgeBadge = (value) => {
    if (!value) return { label: 'New', variant: 'primary' };
    const ageMs = Date.now() - new Date(value).getTime();
    if (Number.isNaN(ageMs) || ageMs < 0) return { label: 'New', variant: 'primary' };
    const ageMinutes = ageMs / (1000 * 60);
    if (ageMinutes >= 240) return { label: 'Overdue', variant: 'danger' };
    if (ageMinutes >= 60) return { label: 'Waiting 1h', variant: 'warning' };
    return { label: 'New', variant: 'primary' };
  };
  const getCandidateValue = (candidate, camelKey, snakeKey, fallback = '') =>
  candidate?.[camelKey] ?? candidate?.[snakeKey] ?? fallback;
  const getCandidateTopScore = (request) => {
    const duplicateCandidates = Array.isArray(request?.duplicateCandidates) ? request.duplicateCandidates : [];
    const snapshotCandidates = Array.isArray(request?.duplicateReviewSnapshot?.topCandidates) ? request.duplicateReviewSnapshot.topCandidates : [];
    const candidates = duplicateCandidates.length ? duplicateCandidates : snapshotCandidates;
    if (!candidates.length) return 0;
    return Number(getCandidateValue(candidates[0], 'matchScore', 'match_score', 0)) || 0;
  };
  const getVisibleDuplicateCandidates = (request) => {
    if (Array.isArray(request?.duplicateCandidates) && request.duplicateCandidates.length) {
      return request.duplicateCandidates;
    }
    return Array.isArray(request?.duplicateReviewSnapshot?.topCandidates) ? request.duplicateReviewSnapshot.topCandidates : [];
  };
  const getReasonOptionsForAction = (action) => {
    if (action === 'request-more-info') return ONBOARDING_NEEDS_MORE_INFO_REASONS;
    if (action === 'reject') return ONBOARDING_REJECT_REASONS;
    if (action === 'create-patient') return ONBOARDING_OVERRIDE_REASONS;
    return ONBOARDING_NEEDS_MORE_INFO_REASONS;
  };
  const getStatusLabel = (status) => ONBOARDING_STATUS_LABELS[status] || status || 'Unknown';
  const getReasonLabel = (reasonCode) => ONBOARDING_REASON_LABELS[reasonCode] || reasonCode || 'Not specified';
  const getRiskVariant = (riskLevel) => {
    if (riskLevel === 'high') return 'danger';
    if (riskLevel === 'medium') return 'warning';
    return 'primary';
  };
  const getRiskLabel = (riskLevel) => {
    if (riskLevel === 'high') return 'High risk';
    if (riskLevel === 'medium') return 'Medium risk';
    return 'Low risk';
  };
  const formatCandidateReasons = (candidate) => {
    const reasons = [];
    const matchReasons = getCandidateValue(candidate, 'matchReasons', 'match_reasons', {});
    if (matchReasons?.phone_match || matchReasons?.phoneMatch) reasons.push('Phone match');
    const similarity = Number(matchReasons?.name_similarity ?? matchReasons?.nameSimilarity ?? 0);
    if (similarity > 0) reasons.push(`Name similarity ${Math.round(similarity * 100)}%`);
    if (matchReasons?.dob_match || matchReasons?.dobMatch) reasons.push('DOB month/year match');
    if (matchReasons?.recent_visit_match || matchReasons?.recentVisitMatch) reasons.push('Recent visit/contact match');
    return reasons.length ? reasons.join(' · ') : 'Manual review only';
  };
  const getOnboardingActionTitle = (action) => {
    if (action === 'link-existing') return 'Link existing patient';
    if (action === 'create-patient') return 'Create new patient';
    if (action === 'request-more-info') return 'Request more info';
    if (action === 'reject') return 'Reject request';
    return 'Review request';
  };
  const getOnboardingActionDescription = (action) => {
    if (action === 'link-existing') {
      return 'You are linking this Telegram user and onboarding request to an existing patient. This action will be audit logged.';
    }
    if (action === 'create-patient') {
      return 'Use this only after duplicate review. Staff-created patients are linked and audit logged immediately.';
    }
    if (action === 'request-more-info') {
      return 'Ask only for safe identity or contact details. Protected medical data stays blocked.';
    }
    if (action === 'reject') {
      return 'Reject only when clinic staff cannot safely continue from this request.';
    }
    return '';
  };
  const getOnboardingActionButtonLabel = (action, busy) => {
    if (busy && action === 'link-existing') return 'Linking...';
    if (busy && action === 'create-patient') return 'Creating...';
    if (busy && action === 'request-more-info') return 'Sending...';
    if (busy && action === 'reject') return 'Rejecting...';
    return getOnboardingActionTitle(action);
  };
  const getDialogCandidateId = (form, dialogState) =>
  form?.selectedCandidateId ||
  dialogState?.candidateId ||
  '';
  const isReviewableStatus = (status) => ['pending_review', 'needs_more_info'].includes(status);
  const visibleOnboardingRequests = [...onboardingRequests].
  filter((request) => onboardingStatusFilter === 'all' ? true : request.status === onboardingStatusFilter).
  sort((left, right) => {
    if (onboardingSort === 'oldest') {
      return new Date(getOnboardingValue(left, 'createdAt', 'created_at', 0)).getTime() -
      new Date(getOnboardingValue(right, 'createdAt', 'created_at', 0)).getTime();
    }
    if (onboardingSort === 'highest_confidence') {
      return getCandidateTopScore(right) - getCandidateTopScore(left);
    }
    if (onboardingSort === 'sla_overdue') {
      return new Date(getOnboardingValue(left, 'createdAt', 'created_at', 0)).getTime() -
      new Date(getOnboardingValue(right, 'createdAt', 'created_at', 0)).getTime();
    }
    return new Date(getOnboardingValue(right, 'createdAt', 'created_at', 0)).getTime() -
    new Date(getOnboardingValue(left, 'createdAt', 'created_at', 0)).getTime();
  });
  const onboardingSummaryCards = [
  {
    label: 'Pending requests',
    value: onboardingAnalytics?.dashboard?.pendingRequests ??
    onboardingRequests.filter((item) => item.status === 'pending_review').length
  },
  {
    label: 'Overdue requests',
    value: onboardingAnalytics?.dashboard?.overdueRequests ??
    onboardingRequests.filter((item) => getOnboardingAgeBadge(getOnboardingValue(item, 'createdAt', 'created_at', '')).label === 'Overdue').length
  },
  {
    label: 'Today\'s submitted',
    value: onboardingAnalytics?.dashboard?.todaySubmitted ?? 0
  },
  {
    label: 'Linked / created today',
    value: onboardingAnalytics?.dashboard?.linkedOrCreatedToday ?? 0
  },
  {
    label: 'Avg review time',
    value: `${onboardingAnalytics?.dashboard?.averageReviewTimeMinutes ?? 0} min`
  },
  {
    label: 'Conversion rate',
    value: `${onboardingAnalytics?.dashboard?.conversionRate ?? 0}%`
  }];
  const iconActionStyle = {
    width: 32,
    minHeight: 32,
    padding: 0
  };
  const capabilityPanelStyle = {
    border: '1px solid var(--mac-card-border, rgba(27, 46, 73, 0.14))',
    borderRadius: 'var(--mac-radius-lg)',
    background: 'var(--mac-bg-secondary, rgba(238, 246, 255, 0.88))',
    boxShadow: 'var(--mac-shadow-sm)',
    padding: 'var(--mac-spacing-4)'
  };
  const capabilityGridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
    gap: '10px'
  };
  const capabilityCardStyle = {
    border: '1px solid var(--mac-card-border, rgba(27, 46, 73, 0.14))',
    borderRadius: 'var(--mac-radius-md)',
    background: 'var(--mac-card-bg, rgba(255, 255, 255, 0.82))',
    boxShadow: 'var(--mac-shadow-sm)',
    padding: 'var(--mac-spacing-3)',
    minHeight: 136,
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--mac-spacing-2)'
  };
  const capabilityIconStyle = {
    width: 28,
    height: 28,
    borderRadius: 'var(--mac-radius-sm)',
    background: 'var(--mac-accent-bg, rgba(0, 122, 255, 0.1))',
    color: 'var(--mac-accent-blue, #007aff)',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: '0 0 auto'
  };
  const dialogRequest = onboardingRequests.find((item) => item.id === onboardingDialog.requestId) || null;
  const dialogForm = onboardingDialog.requestId ? onboardingReviewForms[onboardingDialog.requestId] || {} : {};
  const dialogContactName = dialogRequest ?
  getOnboardingValue(dialogRequest, 'contactName', 'contact_name', '') :
  '';
  const dialogContactPhone = dialogRequest ?
  getOnboardingValue(dialogRequest, 'contactPhone', 'contact_phone', '') :
  '';
  const dialogNameParts = splitOnboardingContactName(dialogContactName);
  const dialogDuplicateCandidates = dialogRequest ? getVisibleDuplicateCandidates(dialogRequest) : [];
  const dialogSelectedCandidateId = getDialogCandidateId(dialogForm, onboardingDialog);
  const dialogSelectedCandidate = dialogDuplicateCandidates.find(
    (candidate) => getCandidateValue(candidate, 'candidateId', 'candidate_id', '') === dialogSelectedCandidateId
  ) || null;
  const dialogHighConfidenceDuplicateExists = Boolean(
    dialogRequest?.duplicateSearch?.highConfidenceCandidateExists ||
    dialogRequest?.duplicateReviewSnapshot?.highConfidenceCandidateExists
  );
  const dialogReasonOptions = getReasonOptionsForAction(onboardingDialog.action);
  const dialogStatus = dialogRequest?.status || '';
  const dialogReviewable = isReviewableStatus(dialogStatus);

  // PR-41 / High-16: moved loading check AFTER all useMemo/useCallback hooks
  // (React Hooks rules-of-hooks requires hooks to be called in the same order
  // on every render — early returns before hooks violate this).
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
          {t('misc.tg_title')}
        </Typography>
        <Button
          variant="outlined"
          onClick={loadTelegramData}>
          <RefreshCw size={16 as never} />
          {t('misc.tg_refresh')}
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
          <Card
            style={{
              backgroundColor: 'var(--mac-bg-secondary)',
              border: '1px solid var(--mac-border)',
              boxShadow: 'var(--mac-shadow-sm)'
            }}>
            <CardContent>
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="flex-start"
                gap={2}
                mb={2}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    {t('misc.tg_bot_intro_title')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t('misc.tg_bot_intro_desc')}
                  </Typography>
                </Box>
                <Badge variant={botStatus?.bot_active ? 'success' : 'warning'} size="small">
                  {botStatus?.mode === 'webhook' ? t('misc.tg_bot_intro_mode_webhook') : t('misc.tg_bot_intro_mode_polling')}
                </Badge>
              </Box>

              <Grid container spacing={2}>
                <Grid item xs={12} md={8}>
                  <Box
                    style={capabilityPanelStyle}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1">
                        {t('misc.tg_patient_bot_title')}
                      </Typography>
                      <Badge variant={enabledPatientFeatures.length ? 'success' : 'warning'} size="small">
                        {patientBot.version || 'v1'}
                      </Badge>
                    </Box>
                    <Box
                      style={capabilityGridStyle}>
                      {patientCapabilities.map((item) => {
                        const Icon = item.icon;
                        return (
                          <Box
                            key={item.key}
                            style={capabilityCardStyle}>
                            <Box display="flex" alignItems="center" gap={1}>
                              <span style={capabilityIconStyle}>
                                <Icon size={15 as never} />
                              </span>
                              <Typography variant="body2" fontWeight={600}>
                                {item.label}
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.secondary" style={{ lineHeight: 1.45 }}>
                              {item.detail}
                            </Typography>
                            <Box display="flex" justifyContent="space-between" alignItems="center" mt="auto" gap={1}>
                              <Typography variant="caption" color="text.secondary">
                                {t('misc.tg_command_label')}
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
                    style={{ ...capabilityPanelStyle, height: '100%' }}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1.5}>
                      <Typography variant="subtitle1">
                        {t('misc.tg_staff_admin_bot_title')}
                      </Typography>
                      <Badge variant={staffRoleMenuRuntimeEnabled ? 'success' : 'warning'} size="small">
                        {t('misc.tg_read_only')}
                      </Badge>
                    </Box>
                    <Box display="flex" sx={{ flexDirection: 'column' }} gap={1.25}>
                      {staffCapabilitySummary.map((item) => {
                        const Icon = item.icon;
                        return (
                          <Box
                            key={item.key}
                            style={capabilityCardStyle}>
                            <Box display="flex" alignItems="center" gap={1} mb={0.5}>
                              <span style={capabilityIconStyle}>
                                <Icon size={15 as never} />
                              </span>
                              <Typography variant="body2" fontWeight={600}>
                                {item.label}
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.secondary" style={{ lineHeight: 1.45 }}>
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
                {t('misc.tg_bot_status_title')}
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
                    primary={t('misc.tg_bot_active')}
                    secondary={botStatus?.bot_active ? t('misc.tg_yes') : t('misc.tg_no')} />
                  
                  <Badge
                    variant={botStatus?.bot_active ? 'success' : 'error'}
                    size="small">
                    
                    {botStatus?.bot_active ? t('misc.tg_active') : t('misc.tg_inactive')}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary={t('misc.tg_webhook_configured')}
                    secondary={botStatus?.webhook_configured ? t('misc.tg_yes') : t('misc.tg_no')} />
                  
                  <Badge
                    variant={botStatus?.webhook_configured ? 'success' : 'warning'}
                    size="small">
                    
                    {botStatus?.webhook_configured ? t('misc.tg_webhook_set') : t('misc.tg_webhook_not_set')}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary={t('misc.tg_subscribers')}
                    secondary={t('misc.tg_subscribers_count', { linked: botStatus?.subscribers_count || 0, total: botStatus?.total_users || 0 })} />
                  
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary="Telegram bot"
                    secondary={botStatus?.bot_username ? `@${botStatus.bot_username}` : t('misc.tg_not_configured')} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary={t('misc.tg_connection_mode')}
                    secondary={botStatus?.mode === 'webhook' ? t('misc.tg_bot_intro_mode_webhook') : t('misc.tg_bot_intro_mode_polling')} />

                  <Badge
                    variant={botStatus?.mode === 'webhook' ? 'success' : 'warning'}
                    size="small">

                    {botStatus?.mode === 'webhook' ? t('misc.tg_bot_intro_mode_webhook') : t('misc.tg_bot_intro_mode_polling')}
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
                    t('misc.tg_staff_token_contract_not_published')} />

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
                    primary={t('misc.tg_patient_linking')}
                    secondary={t('misc.tg_linking_summary', { qr: botStatus?.qr_linking_enabled ? t('misc.tg_yes_short') : t('misc.tg_no_short'), phone: botStatus?.contact_linking_enabled ? t('misc.tg_yes_short') : t('misc.tg_no_short') })} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary={`Patient bot ${patientBot.version || 'v1'}`}
                    secondary={enabledPatientFeatures.length ?
                    enabledPatientFeatures.map((feature) => feature.label).join(', ') :
                    t('misc.tg_patient_features_inactive')} />

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
                    primary={t('misc.tg_patient_languages')}
                    secondary={patientBotLanguages.length ?
                    patientBotLanguages.map((item) => item.label).join(', ') :
                    t('misc.tg_lang_russian')} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Settings />
                  </ListItemIcon>
                  <ListItemText
                    primary={t('misc.tg_patient_commands')}
                    secondary={patientBotCommands.length ?
                    patientBotCommands.map((item) => item.command).join(' ') :
                    t('misc.tg_no_data')} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MessageSquare />
                  </ListItemIcon>
                  <ListItemText
                    primary={`Staff bot ${staffBot.version || 'planning'}`}
                    secondary={staffBot.enabled ?
                    t('misc.tg_staff_bot_ready') :
                    t('misc.tg_staff_bot_plan')} />

                  <Badge
                    variant={staffBot.enabled ? 'success' : 'warning'}
                    size="small">

                    {staffBot.enabled ? t('misc.tg_staff_bot_ready_badge') : t('misc.tg_staff_bot_plan_badge')}
                  </Badge>
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff guardrails"
                    secondary={staffBotReadiness.length ?
                    `${readyStaffControls.length}/${staffBotReadiness.length} ${t('misc.tg_staff_guardrails_ready')}; ${t('misc.tg_staff_guardrails_roles')}: ${staffRoleSummary}` :
                    t('misc.tg_staff_guardrails_not_published')} />

                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckCircle />
                  </ListItemIcon>
                  <ListItemText
                    primary="Staff linking foundation"
                    secondary={staffLinkingMethodNames.length ?
                    t('misc.tg_staff_linking_summary', { methods: staffLinkingMethodNames.join(', '), required: staffLinkingContract.required_before_enablement ? t('misc.tg_staff_linking_required') : t('misc.tg_staff_linking_not_required') }) :
                    t('misc.tg_staff_linking_not_published')} />

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
                    t('misc.tg_auth_contract_not_published')} />

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
                    t('misc.tg_staff_menu_summary', { roleCount: staffMenuContract.length, itemCount: staffMenuItemCount }) :
                    t('misc.tg_staff_menu_not_published')} />

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
                    t('misc.tg_staff_command_not_published')} />

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
                    t('misc.tg_confirmation_not_published')} />

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
                    t('misc.tg_audit_not_published')} />

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
                    primary={t('misc.tg_results_title')}
                    secondary={patientBot.results_delivery === 'telegram_pdf' ?
                    t('misc.tg_results_pdf', { count: patientBot.max_pdf_reports_per_request || 3 }) :
                    t('misc.tg_results_notification')} />

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
                {t('misc.tg_quick_actions')}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <Button
                  fullWidth
                  variant="contained"
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Settings size={16 as never} />
                  {t('misc.tg_configure_bot')}
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  disabled={!botStatus?.configured || registeringCommands}
                  onClick={registerPatientCommands}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <CheckCircle size={16 as never} />
                  {registeringCommands ? t('misc.tg_registering_commands') : t('misc.tg_register_commands')}
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  disabled={!staffCommandRegistrationEnabled || registeringStaffCommands}
                  onClick={registerStaffCommands}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <CheckCircle size={16 as never} />
                  {registeringStaffCommands ? t('misc.tg_registering_staff_commands') : t('misc.tg_register_staff_commands')}
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Send size={16 as never} />
                  {t('misc.tg_send_message')}
                </Button>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={() => setShowTemplateDialog(true)}
                  style={{ paddingTop: 12, paddingBottom: 12 }}>
                  <Plus size={16 as never} />
                  {t('misc.tg_new_template')}
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
                    {onboardingTotal} requests
                  </Badge>
                  <Button
                    type="button"
                    variant="outlined"
                    size="small"
                    disabled={exportingOnboardingCsv}
                    onClick={handleExportOnboardingCsv}>
                    <ReceiptText size={16 as never} />
                    {exportingOnboardingCsv ? 'Exporting...' : 'Export CSV'}
                  </Button>
                </Box>
              </Box>

              <Box
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                  gap: 12,
                  marginBottom: 16
                }}>
                {onboardingSummaryCards.map((card) =>
                <Box
                  key={card.label}
                  style={{
                    border: '1px solid var(--mac-border)',
                    borderRadius: 8,
                    padding: 12,
                    background: 'var(--mac-bg-secondary)'
                  }}>
                    <Typography variant="caption" color="text.secondary">
                      {card.label}
                    </Typography>
                    <Typography variant="h6" style={{ marginTop: 6 }}>
                      {card.value}
                    </Typography>
                  </Box>
                )}
              </Box>

              <Box
                display="flex"
                gap={1.5}
                alignItems="flex-end"
                sx={{ flexWrap: 'wrap' }}
                mb={2}>
                <Select
                  label="Status filter"
                  value={onboardingStatusFilter}
                  options={ONBOARDING_STATUS_FILTER_OPTIONS}
                  onChange={(value) => setOnboardingStatusFilter(value)}
                  style={{ minWidth: 220 }} />
                <Select
                  label="Sort"
                  value={onboardingSort}
                  options={ONBOARDING_SORT_OPTIONS}
                  onChange={(value) => setOnboardingSort(value)}
                  style={{ minWidth: 220 }} />
                <Button
                  type="button"
                  variant="outlined"
                  size="small"
                  onClick={loadOnboardingRequests}
                  aria-label="Refresh REQUEST_REVIEW requests"
                  style={{ minHeight: 32 }}>
                  <RefreshCw size={16 as never} />
                  Refresh
                </Button>
              </Box>

              {!visibleOnboardingRequests.length ? (
                <Alert severity="info">
                  No pending REQUEST_REVIEW requests. Unknown patients still get a safe appointment request CTA instead of confirmed booking.
                </Alert>
              ) : (
                <Box display="flex" sx={{ flexDirection: 'column' }} gap={2}>
                  {visibleOnboardingRequests.map((request) => {
                    const requestId = request.id;
                    const form = onboardingReviewForms[requestId] || {};
                    const contactName = getOnboardingValue(request, 'contactName', 'contact_name', 'No name');
                    const contactPhone = getOnboardingValue(request, 'contactPhone', 'contact_phone', 'No phone');
                    const desiredService = getOnboardingValue(request, 'desiredService', 'desired_service', 'Service not selected');
                    const desiredBranch = getOnboardingValue(request, 'desiredBranch', 'desired_branch', 'Branch not selected');
                    const desiredDate = getOnboardingValue(request, 'desiredDate', 'desired_date', '');
                    const desiredTime = getOnboardingValue(request, 'desiredTime', 'desired_time', '');
                    const note = getOnboardingValue(request, 'note', 'note', '');
                    const createdAt = getOnboardingValue(request, 'createdAt', 'created_at', '');
                    const status = request.status || 'pending_review';
                    const statusLabel = getStatusLabel(status);
                    const ageBadge = getOnboardingAgeBadge(createdAt);
                    const reviewable = isReviewableStatus(status);
                    const duplicateCandidates = getVisibleDuplicateCandidates(request);
                    const topScore = getCandidateTopScore(request);
                    const highConfidenceCandidateExists = Boolean(
                      request?.duplicateSearch?.highConfidenceCandidateExists ||
                      request?.duplicateReviewSnapshot?.highConfidenceCandidateExists
                    );
                    const auditTrail = Array.isArray(request.auditTrail) ? request.auditTrail : [];
                    const notificationPreview = request.notificationPreview || null;
                    const actionBusy = onboardingActionId.endsWith(`:${requestId}`) || onboardingActionId === `search:${requestId}`;

                    return (
                      <Box
                        key={requestId}
                        style={{
                          border: '1px solid var(--mac-border)',
                          borderRadius: 8,
                          padding: 16,
                          background: 'var(--mac-bg-secondary)'
                        }}>
                        <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={2} sx={{ flexWrap: 'wrap' }} mb={2}>
                          <Box>
                            <Typography variant="body1" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
                              Request #{requestId}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Received {formatOnboardingCreatedAt(createdAt)}
                            </Typography>
                          </Box>
                          <Box display="flex" gap={1} alignItems="center" sx={{ flexWrap: 'wrap' }}>
                            <Badge variant={onboardingStatusVariant(status)} size="small">
                              {statusLabel}
                            </Badge>
                            <Badge variant={ageBadge.variant} size="small">
                              {ageBadge.label}
                            </Badge>
                            {topScore > 0 ? (
                              <Badge variant={topScore >= 0.85 ? 'danger' : topScore >= 0.5 ? 'warning' : 'primary'} size="small">
                                Match {Math.round(topScore * 100)}%
                              </Badge>
                            ) : null}
                          </Box>
                        </Box>

                        <Box
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                            gap: 16
                          }}>
                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              Onboarding details
                            </Typography>
                            <Box display="flex" sx={{ flexDirection: 'column' }} gap={0.75} mt={1}>
                              <Typography variant="body2">{contactName}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                {contactPhone}
                              </Typography>
                              <Typography variant="body2">{desiredService}</Typography>
                              <Typography variant="caption" color="text.secondary">
                                {desiredBranch}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {formatOnboardingDate(desiredDate)} {desiredTime || 'Time not selected'}
                              </Typography>
                              {note ? (
                                <Typography variant="caption" color="text.secondary">
                                  Note: {note}
                                </Typography>
                              ) : (
                                <Typography variant="caption" color="text.secondary">
                                  No safe note submitted
                                </Typography>
                              )}
                            </Box>
                          </Box>

                          <Box>
                            <Box display="flex" justifyContent="space-between" alignItems="center" gap={1} sx={{ flexWrap: 'wrap' }} mb={1}>
                              <Typography variant="caption" color="text.secondary">
                                Duplicate review
                              </Typography>
                              {reviewable ? (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="small"
                                  disabled={actionBusy}
                                  onClick={() => refreshOnboardingCandidates(requestId)}
                                  aria-label={`Refresh duplicate candidates for request ${requestId}`}>
                                  <RefreshCw size={14 as never} />
                                  Refresh candidates
                                </Button>
                              ) : null}
                            </Box>
                            {highConfidenceCandidateExists ? (
                              <Alert severity="warning" style={{ marginBottom: 12 }}>
                                High-confidence duplicate found. Review visible evidence before creating a new patient.
                              </Alert>
                            ) : null}
                            {duplicateCandidates.length ? (
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={1}>
                                {duplicateCandidates.map((candidate) => {
                                  const candidateId = getCandidateValue(candidate, 'candidateId', 'candidate_id', '');
                                  const maskedName = getCandidateValue(candidate, 'maskedName', 'masked_name', 'Masked patient');
                                  const maskedPhone = getCandidateValue(candidate, 'maskedPhone', 'masked_phone', 'No phone');
                                  const dobYear = getCandidateValue(candidate, 'dobYear', 'dob_year', '');
                                  const dobMonth = getCandidateValue(candidate, 'dobMonth', 'dob_month', '');
                                  const recentVisitSummary = getCandidateValue(candidate, 'recentVisitSummary', 'recent_visit_summary', '');
                                  const branch = getCandidateValue(candidate, 'branch', 'branch', '');
                                  const riskLevel = getCandidateValue(candidate, 'riskLevel', 'risk_level', 'low');
                                  const matchScore = Number(getCandidateValue(candidate, 'matchScore', 'match_score', 0)) || 0;
                                  return (
                                    <Box
                                      key={candidateId}
                                      style={{
                                        border: '1px solid var(--mac-border)',
                                        borderRadius: 8,
                                        padding: 12,
                                        background: 'var(--mac-bg-primary)'
                                      }}>
                                      <Box display="flex" justifyContent="space-between" alignItems="flex-start" gap={1} sx={{ flexWrap: 'wrap' }}>
                                        <Box>
                                          <Typography variant="body2" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
                                            {maskedName}
                                          </Typography>
                                          <Typography variant="caption" color="text.secondary">
                                            {maskedPhone}
                                            {dobMonth && dobYear ? ` - DOB ${String(dobMonth).padStart(2, '0')}/${dobYear}` : ''}
                                          </Typography>
                                        </Box>
                                        <Box display="flex" gap={1} alignItems="center" sx={{ flexWrap: 'wrap' }}>
                                          <Badge variant={getRiskVariant(riskLevel)} size="small">
                                            {getRiskLabel(riskLevel)}
                                          </Badge>
                                          <Badge variant={matchScore >= 0.85 ? 'danger' : matchScore >= 0.5 ? 'warning' : 'primary'} size="small">
                                            {Math.round(matchScore * 100)}%
                                          </Badge>
                                        </Box>
                                      </Box>
                                      <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 8 }}>
                                        {formatCandidateReasons(candidate)}
                                      </Typography>
                                      {recentVisitSummary ? (
                                        <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                                          {recentVisitSummary}
                                        </Typography>
                                      ) : null}
                                      {branch ? (
                                        <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                                          Branch: {branch}
                                        </Typography>
                                      ) : null}
                                      {reviewable ? (
                                        <Box mt={1.5}>
                                          <Button
                                            type="button"
                                            variant="contained"
                                            size="small"
                                            onClick={() => {
                                              updateOnboardingReviewForm(requestId, 'selectedCandidateId', candidateId);
                                              openOnboardingActionDialog(requestId, 'link-existing', candidateId);
                                            }}>
                                            <UserCheck size={16 as never} />
                                            Link this patient
                                          </Button>
                                        </Box>
                                      ) : null}
                                    </Box>
                                  );
                                })}
                              </Box>
                            ) : (
                              <Alert severity="info">
                                No safe duplicate candidates yet. Staff may still create a patient only after duplicate review is completed.
                              </Alert>
                            )}
                          </Box>

                          <Box>
                            <Typography variant="caption" color="text.secondary">
                              Staff action
                            </Typography>
                            <Box display="flex" sx={{ flexDirection: 'column' }} gap={1} mt={1}>
                              {reviewable ? (
                                <>
                                  <Button
                                    type="button"
                                    variant="contained"
                                    size="small"
                                    disabled={actionBusy || !duplicateCandidates.length}
                                    onClick={() => openOnboardingActionDialog(requestId, 'link-existing', form.selectedCandidateId || '')}>
                                    <UserCheck size={16 as never} />
                                    Link this patient
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outlined"
                                    size="small"
                                    disabled={actionBusy}
                                    onClick={() => openOnboardingActionDialog(requestId, 'create-patient')}>
                                    <Plus size={16 as never} />
                                    Create new patient
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outlined"
                                    size="small"
                                    disabled={actionBusy}
                                    onClick={() => openOnboardingActionDialog(requestId, 'request-more-info')}>
                                    <MessageSquare size={16 as never} />
                                    Request more info
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="outlined"
                                    size="small"
                                    disabled={actionBusy}
                                    onClick={() => openOnboardingActionDialog(requestId, 'reject')}>
                                    <Trash2 size={16 as never} />
                                    Reject
                                  </Button>
                                </>
                              ) : (
                                <Alert severity="success">
                                  Review complete. Protected actions stay closed until the linked patient cabinet is ready.
                                </Alert>
                              )}

                              {notificationPreview ? (
                                <Box
                                  style={{
                                    border: '1px dashed var(--mac-border)',
                                    borderRadius: 8,
                                    padding: 12,
                                    marginTop: 8
                                  }}>
                                  <Typography variant="caption" color="text.secondary">
                                    Patient-facing safe message
                                  </Typography>
                                  <Typography variant="body2" style={{ marginTop: 6, fontWeight: 'var(--mac-font-weight-semibold)' }}>
                                    {notificationPreview.title}
                                  </Typography>
                                  <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                                    {notificationPreview.body}
                                  </Typography>
                                  <Badge variant="primary" size="small" style={{ marginTop: 8 }}>
                                    {notificationPreview.ctaLabel}
                                  </Badge>
                                </Box>
                              ) : null}
                            </Box>
                          </Box>
                        </Box>

                        <Box
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                            gap: 12,
                            marginTop: 16
                          }}>
                          <Box
                            style={{
                              border: '1px solid var(--mac-border)',
                              borderRadius: 8,
                              padding: 12,
                              background: 'var(--mac-bg-primary)'
                            }}>
                            <Typography variant="caption" color="text.secondary">
                              Audit trail
                            </Typography>
                            {auditTrail.length ? (
                              <Box display="flex" sx={{ flexDirection: 'column' }} gap={0.75} mt={1}>
                                {auditTrail.map((item, index) =>
                                <Box key={`${requestId}-${item.action}-${index}`}>
                                    <Typography variant="body2">
                                      {item.action}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                      {(item.reviewer || 'System review')} - {item.timestamp ? formatOnboardingCreatedAt(item.timestamp) : 'No timestamp'}
                                      {item.reasonCode ? ` - ${getReasonLabel(item.reasonCode)}` : ''}
                                    </Typography>
                                  </Box>
                                )}
                              </Box>
                            ) : (
                              <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 8 }}>
                                No audit events yet.
                              </Typography>
                            )}
                          </Box>

                          <Box
                            style={{
                              border: '1px solid var(--mac-border)',
                              borderRadius: 8,
                              padding: 12,
                              background: 'var(--mac-bg-primary)'
                            }}>
                            <Typography variant="caption" color="text.secondary">
                              Safe next step
                            </Typography>
                            <Typography variant="body2" style={{ marginTop: 8 }}>
                              {reviewable ?
                              'Review duplicates, then link the patient or create a staff-approved patient profile.' :
                              'This request already has a staff outcome. The patient sees only a safe next action in Telegram and Mini App.'}
                            </Typography>
                          </Box>
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                {t('misc.tg_templates_title')}
              </Typography>
              <div style={{ width: '100%', overflowX: 'auto' }}>
                <Table style={{ minWidth: 640 }}>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>{t('misc.tg_col_name')}</TableHeaderCell>
                      <TableHeaderCell>{t('misc.tg_col_type')}</TableHeaderCell>
                      <TableHeaderCell>{t('misc.tg_col_status')}</TableHeaderCell>
                      <TableHeaderCell align="right">{t('misc.tg_col_actions')}</TableHeaderCell>
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
                          
                            {template.is_active ? t('misc.tg_active') : t('misc.tg_inactive')}
                          </Badge>
                        </TableCell>
                        <TableCell align="right">
                          <Box display="inline-flex" gap={0.5} justifyContent="flex-end">
                            <Button
                              type="button"
                              variant="ghost"
                              size="small"
                              aria-label={t('misc.tg_action_edit')}
                              title={t('misc.tg_action_edit')}
                              style={iconActionStyle}>
                              <Edit size={16 as never} />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="small"
                              aria-label={t('misc.tg_action_delete')}
                              title={t('misc.tg_action_delete')}
                              style={iconActionStyle}>
                              <Trash2 size={16 as never} />
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

      <Dialog open={onboardingDialog.open} onClose={closeOnboardingDialog} maxWidth="md" fullWidth>
        <DialogTitle>{getOnboardingActionTitle(onboardingDialog.action)}</DialogTitle>
        <DialogContent>
          <Box display="flex" sx={{ flexDirection: 'column' }} gap={2}>
            <Alert severity={onboardingDialog.action === 'reject' ? 'warning' : 'info'}>
              {getOnboardingActionDescription(onboardingDialog.action)}
            </Alert>

            {dialogRequest ? (
              <Box
                style={{
                  border: '1px solid var(--mac-border)',
                  borderRadius: 8,
                  padding: 12,
                  background: 'var(--mac-bg-secondary)'
                }}>
                <Typography variant="body2" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
                  Request #{dialogRequest.id}
                </Typography>
                <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                  {dialogContactName || 'No name'} - {dialogContactPhone || 'No phone'}
                </Typography>
                <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                  Status: {getStatusLabel(dialogStatus)}
                </Typography>
              </Box>
            ) : null}

            {onboardingDialog.action === 'link-existing' ? (
              <>
                {dialogDuplicateCandidates.length ? (
                  <Select
                    label="Duplicate candidate"
                    value={dialogSelectedCandidateId}
                    options={dialogDuplicateCandidates.map((candidate) => ({
                      value: getCandidateValue(candidate, 'candidateId', 'candidate_id', ''),
                      label: `${getCandidateValue(candidate, 'maskedName', 'masked_name', 'Masked patient')} - ${Math.round((Number(getCandidateValue(candidate, 'matchScore', 'match_score', 0)) || 0) * 100)}%`
                    }))}
                    onChange={(value) => updateOnboardingReviewForm(onboardingDialog.requestId, 'selectedCandidateId', value)}
                    style={{ width: '100%' }} />
                ) : (
                  <Alert severity="warning">
                    No duplicate candidate is selected yet. Refresh candidates from the request card first.
                  </Alert>
                )}

                {dialogSelectedCandidate ? (
                  <Box
                    style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: 8,
                      padding: 12,
                      background: 'var(--mac-bg-primary)'
                    }}>
                    <Typography variant="body2" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>
                      {getCandidateValue(dialogSelectedCandidate, 'maskedName', 'masked_name', 'Masked patient')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                      {getCandidateValue(dialogSelectedCandidate, 'maskedPhone', 'masked_phone', 'No phone')}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" style={{ display: 'block', marginTop: 4 }}>
                      {formatCandidateReasons(dialogSelectedCandidate)}
                    </Typography>
                  </Box>
                ) : null}
              </>
            ) : null}

            {onboardingDialog.action === 'create-patient' ? (
              <Box display="flex" sx={{ flexDirection: 'column' }} gap={1.5}>
                {dialogHighConfidenceDuplicateExists ? (
                  <Alert severity="warning">
                    High-confidence duplicate detected. Review duplicates and confirm override before creating a new patient.
                  </Alert>
                ) : null}
                {dialogDuplicateCandidates.length ? (
                  <Select
                    label="Reviewed duplicate candidate"
                    value={dialogSelectedCandidateId}
                    options={[
                      { value: '', label: 'No candidate selected' },
                      ...dialogDuplicateCandidates.map((candidate) => ({
                        value: getCandidateValue(candidate, 'candidateId', 'candidate_id', ''),
                        label: `${getCandidateValue(candidate, 'maskedName', 'masked_name', 'Masked patient')} - ${Math.round((Number(getCandidateValue(candidate, 'matchScore', 'match_score', 0)) || 0) * 100)}%`
                      }))
                    ]}
                    onChange={(value) => updateOnboardingReviewForm(onboardingDialog.requestId, 'selectedCandidateId', value)}
                    style={{ width: '100%' }} />
                ) : null}
                <Box
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: 12
                  }}>
                  <Input
                    label="Last name"
                    value={dialogForm.lastName ?? dialogNameParts.lastName}
                    onChange={(event) => updateOnboardingReviewForm(onboardingDialog.requestId, 'lastName', event.target.value)}
                    placeholder="Last name"
                    required />
                  <Input
                    label="First name"
                    value={dialogForm.firstName ?? dialogNameParts.firstName}
                    onChange={(event) => updateOnboardingReviewForm(onboardingDialog.requestId, 'firstName', event.target.value)}
                    placeholder="First name"
                    required />
                  <Input
                    label="Middle name"
                    value={dialogForm.middleName ?? dialogNameParts.middleName}
                    onChange={(event) => updateOnboardingReviewForm(onboardingDialog.requestId, 'middleName', event.target.value)}
                    placeholder="Middle name" />
                  <Input
                    label="Phone"
                    value={dialogForm.phone ?? dialogContactPhone}
                    onChange={(event) => updateOnboardingReviewForm(onboardingDialog.requestId, 'phone', event.target.value)}
                    placeholder="+998..." />
                </Box>
                {dialogHighConfidenceDuplicateExists ? (
                  <>
                    <Select
                      label="Override reason"
                      value={dialogForm.reasonCode || ''}
                      options={dialogReasonOptions}
                      onChange={(value) => updateOnboardingReviewForm(onboardingDialog.requestId, 'reasonCode', value)}
                      style={{ width: '100%' }} />
                    <Switch
                      checked={Boolean(dialogForm.confirmCreateDespiteDuplicates)}
                      onChange={(checked) => updateOnboardingReviewForm(onboardingDialog.requestId, 'confirmCreateDespiteDuplicates', checked)}
                      label="I reviewed duplicates and still want to create a new patient" />
                  </>
                ) : null}
              </Box>
            ) : null}

            {['request-more-info', 'reject'].includes(onboardingDialog.action) ? (
              <Select
                label="Reason code"
                value={dialogForm.reasonCode || ''}
                options={dialogReasonOptions}
                onChange={(value) => updateOnboardingReviewForm(onboardingDialog.requestId, 'reasonCode', value)}
                style={{ width: '100%' }} />
            ) : null}

            {['create-patient', 'request-more-info', 'reject', 'link-existing'].includes(onboardingDialog.action) ? (
              <Textarea
                label="Safe staff note"
                value={dialogForm.safeNote || ''}
                maxLength={512}
                minRows={3}
                maxRows={5}
                onChange={(event) => updateOnboardingReviewForm(onboardingDialog.requestId, 'safeNote', event.target.value)}
                placeholder="Use safe operational wording only. Do not include diagnosis, lab details, raw IDs, or tokens."
                style={{ width: '100%' }} />
            ) : null}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeOnboardingDialog}>Cancel</Button>
          <Button
            variant={onboardingDialog.action === 'reject' ? 'outlined' : 'contained'}
            disabled={
              !dialogReviewable ||
              (onboardingDialog.action === 'link-existing' && !dialogSelectedCandidateId) ||
              (onboardingDialog.action === 'create-patient' &&
                dialogHighConfidenceDuplicateExists &&
                (!dialogForm.confirmCreateDespiteDuplicates || !dialogForm.reasonCode)) ||
              (['request-more-info', 'reject'].includes(onboardingDialog.action) && !dialogForm.reasonCode)
            }
            onClick={() => handleOnboardingReviewAction(
              onboardingDialog.requestId,
              onboardingDialog.action,
              { candidateId: dialogSelectedCandidateId }
            )}>
            {getOnboardingActionButtonLabel(
              onboardingDialog.action,
              onboardingActionId === `${onboardingDialog.action}:${onboardingDialog.requestId}`
            )}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={showTemplateDialog} onClose={() => setShowTemplateDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>{t('misc.tg_dialog_create_template')}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={6}>
              <Input
                label={t('misc.tg_field_template_name')}
                value={templateForm.name}
                onChange={(e) => setTemplateForm({ ...templateForm, name: e.target.value })}
                style={{ width: '100%' }}
                required />

            </Grid>
            <Grid item xs={12} sm={6}>
              <Select
                label={t('misc.tg_field_message_type')}
                value={templateForm.message_type}
                options={templateTypeOptions}
                onChange={(messageType) => setTemplateForm({ ...templateForm, message_type: messageType })}
                style={{ width: '100%' }} />
            </Grid>
            <Grid item xs={12}>
              <Textarea
                label={t('misc.tg_field_message_content')}
                minRows={6}
                maxRows={8}
                value={templateForm.content}
                onChange={(e) => setTemplateForm({ ...templateForm, content: e.target.value })}
                required
                style={{ width: '100%' }}
                placeholder={t('misc.tg_placeholder_template_vars')} />

            </Grid>
            <Grid item xs={12}>
              <Switch
                label={t('misc.tg_field_active_template')}
                checked={templateForm.is_active}
                onChange={(isActive) => setTemplateForm({ ...templateForm, is_active: isActive })} />

            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowTemplateDialog(false)}>{t('misc.tg_cancel')}</Button>
          <Button onClick={handleCreateTemplate} variant="contained">
            {t('misc.tg_create')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>);

};

export default TelegramManager;
