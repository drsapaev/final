import { useEffect, useMemo, useRef, useState } from 'react';
import { hasLabReportAction } from '../utils/labReportActions';
import { extractFieldValue, getServiceContextItems } from '../utils/labReportNormalize';

/**
 * STRAT#1: useLabReportState — вынесенная state-логика LabReportWorkbench.
 *
 * Раньше LabReportWorkbench.jsx был god-компонентом 1108+ строк: state
 * declarations, derived memos, init effects, handlers и JSX — всё в одном.
 * Это затрудняло тестирование и review. Теперь state-часть изолирована
 * в этом хуке.
 *
 * Что здесь:
 *   - All useState declarations (draftValues, signerSnapshot, saving, ...)
 *   - Derived memos (isDirty, publishedTemplates, missingRequiredFields, ...)
 *   - Action availability flags (canEdit, canFinalize, canRevise, ...)
 *   - Init effect: загрузка значений из activeInstance при смене instance
 *
 * Что осталось в компоненте:
 *   - handleCreateInstance / handleSaveDraft / handleFinalize / handleRevise
 *     / handlePrint / handleNotifyPatient (требуют notify + onInstanceChange)
 *   - JSX rendering
 *
 * Возврат: объект со всем state и setters, чтобы компонент мог их деструктурировать.
 */

interface LabReportTemplate {
  id: string | number;
  published_version_id?: string | number | null;
  draft_version_id?: string | number | null;
  [key: string]: unknown;
}

interface LabReportField {
  field_key: string;
  label?: string;
  required?: boolean;
  value_numeric?: number | null;
  value_text?: string;
  [key: string]: unknown;
}

interface LabReportSection {
  fields: LabReportField[];
  key?: string;
  section_key?: string;
  id?: string | number;
  [key: string]: unknown;
}

interface LabReportInstance {
  sections: LabReportSection[];
  signer_snapshot?: Record<string, unknown>;
  template_id?: string | number;
  [key: string]: unknown;
}

interface LabReportAppointment {
  service_details?: Array<{ id?: string; code?: string; name?: string }>;
  service_codes?: string[];
  [key: string]: unknown;
}

interface LabReportTemplateResolution {
  allowed_templates?: LabReportTemplate[];
  service_codes?: string[];
  default_template?: { id?: string | number };
  [key: string]: unknown;
}

interface UseLabReportStateParams {
  selectedAppointment?: LabReportAppointment | null;
  templates?: LabReportTemplate[];
  templateResolution?: LabReportTemplateResolution | null;
  activeInstance?: LabReportInstance | null;
}

interface PrintFeedback {
  severity: string;
  text: string;
}

export function useLabReportState({
  selectedAppointment = null,
  templates = [],
  templateResolution = null,
  activeInstance = null,
}: UseLabReportStateParams) {
  // ─── State ────────────────────────────────────────────────────────────────
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('');
  const [draftValues, setDraftValues] = useState<Record<string, unknown>>({});
  const [signerSnapshot, setSignerSnapshot] = useState<Record<string, unknown>>({});
  // PR-64 / Medium-16: collapsible sections in report editor
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState<boolean>(false);
  const [busyAction, setBusyAction] = useState<string | null>('');
  const [printFeedback, setPrintFeedback] = useState<PrintFeedback | null>(null);
  const [historySeverityFilter, setHistorySeverityFilter] = useState<string>('all');
  // WF-11 fix: escape hatch для template resolution blocking gap.
  const [escapeHatchActive, setEscapeHatchActive] = useState<boolean>(false);
  // PR-58: autosave state
  const [lastAutoSave, setLastAutoSave] = useState<Date | null>(null);
  const [autoSaving, setAutoSaving] = useState<boolean>(false);

  // Dirty state tracking: snapshot значений при загрузке instance.
  const initialValuesRef = useRef<{ values: Record<string, unknown>; signer: Record<string, unknown> }>({ values: {}, signer: {} });
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // L-L-4 fix: ref для handleSaveDraft, чтобы autosave/keydown могли
  // вызывать последнюю версию без пересоздания listener-ов.
  const handleSaveDraftRef = useRef<(() => void | Promise<void>) | null>(null);

  // ─── Derived: isDirty ────────────────────────────────────────────────────
  const isDirty = useMemo(() => {
    if (!activeInstance) return false;
    const initial = initialValuesRef.current.values;
    const draftKeys = new Set([...Object.keys(draftValues), ...Object.keys(initial)]);
    for (const key of draftKeys) {
      if ((draftValues[key] || '') !== (initial[key] || '')) return true;
    }
    const initialSigner = initialValuesRef.current.signer;
    const signerKeys = ['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'];
    for (const key of signerKeys) {
      if ((signerSnapshot?.[key] || '') !== (initialSigner?.[key] || '')) return true;
    }
    return false;
  }, [activeInstance, draftValues, signerSnapshot]);

  // ─── Derived: template collections ───────────────────────────────────────
  const publishedTemplates = useMemo(
    () => templates.filter((template) => template.published_version_id || template.draft_version_id),
    [templates]
  );
  const serviceContextItems = useMemo(
    () => getServiceContextItems(selectedAppointment),
    [selectedAppointment]
  );
  const resolvedTemplates = templateResolution?.allowed_templates || [];
  const serviceContextPresent = (templateResolution?.service_codes || []).length > 0;
  // WF-11 fix: при escape hatch показываем все published templates.
  const templateOptions = serviceContextPresent ? resolvedTemplates : publishedTemplates;
  const effectiveTemplateOptions = escapeHatchActive
    ? publishedTemplates
    : templateOptions;
  const resolutionHasBlockingGap = serviceContextPresent && resolvedTemplates.length === 0 && !escapeHatchActive;
  const singleAllowedTemplate =
    serviceContextPresent && effectiveTemplateOptions.length === 1 ? effectiveTemplateOptions[0] : null;

  // ─── Derived: action availability (SSOT via hasLabReportAction) ──────────
  const showRecentReportsBrowser = !selectedAppointment && !activeInstance;
  const canEditActiveInstance = hasLabReportAction(activeInstance, 'edit');
  const canSaveDraft = hasLabReportAction(activeInstance, 'save_draft');
  // WF-round5: Mark Ready убран — был функционально пустой операцией.
  const canFinalize = hasLabReportAction(activeInstance, 'finalize');
  const canRevise = hasLabReportAction(activeInstance, 'revise');
  const canPrint = hasLabReportAction(activeInstance, 'print');

  // ─── Derived: WF-10 missing required fields (inline-валидация) ───────────
  const missingRequiredFields = useMemo(() => {
    if (!activeInstance?.sections) return [];
    const missing: string[] = [];
    activeInstance.sections.forEach((section) => {
      (section.fields || []).forEach((field) => {
        if (field.required) {
          const value = draftValues[field.field_key];
          if (value === undefined || value === '' || value === null) {
            missing.push(field.label || field.field_key);
          }
        }
      });
    });
    return missing;
  }, [activeInstance, draftValues]);
  const hasMissingRequired = missingRequiredFields.length > 0;
  const canFinalizeWithValidation = canFinalize && !hasMissingRequired;

  // ─── Init effect: load values from activeInstance on instance change ─────
  useEffect(() => {
    if (!activeInstance) {
      setDraftValues({});
      setSignerSnapshot({});
      setPrintFeedback(null);
      initialValuesRef.current = { values: {}, signer: {} };
      setEscapeHatchActive(false);
      return;
    }
    // WF-12 fix: сбрасываем printFeedback при смене activeInstance.
    setPrintFeedback(null);
    const values: Record<string, unknown> = {};
    activeInstance.sections.forEach((section) => {
      section.fields.forEach((field) => {
        values[field.field_key] = extractFieldValue(field);
      });
    });
    setDraftValues(values);
    setSignerSnapshot(activeInstance.signer_snapshot || {});
    setSelectedTemplateId(String(activeInstance.template_id));
    initialValuesRef.current = {
      values: { ...values },
      signer: { ...(activeInstance.signer_snapshot || {}) },
    };
  }, [activeInstance]);

  // ─── Init effect: default template selection ─────────────────────────────
  useEffect(() => {
    if (activeInstance || !selectedAppointment) {
      return;
    }
    const defaultTemplateId =
      templateResolution?.default_template?.id
      || (!serviceContextPresent ? effectiveTemplateOptions[0]?.id : '')
      || '';
    setSelectedTemplateId((current) => {
      if (current && effectiveTemplateOptions.some((template) => String(template.id) === String(current))) {
        return current;
      }
      return defaultTemplateId ? String(defaultTemplateId) : '';
    });
  }, [
    activeInstance,
    selectedAppointment,
    serviceContextPresent,
    effectiveTemplateOptions,
    templateResolution?.default_template?.id
  ]);

  return {
    // State
    selectedTemplateId,
    setSelectedTemplateId,
    draftValues,
    setDraftValues,
    signerSnapshot,
    setSignerSnapshot,
    collapsedSections,
    setCollapsedSections,
    saving,
    setSaving,
    busyAction,
    setBusyAction,
    printFeedback,
    setPrintFeedback,
    historySeverityFilter,
    setHistorySeverityFilter,
    escapeHatchActive,
    setEscapeHatchActive,
    lastAutoSave,
    setLastAutoSave,
    autoSaving,
    setAutoSaving,
    // Refs (для handlers и effects в компоненте)
    initialValuesRef,
    autoSaveTimerRef,
    handleSaveDraftRef,
    // Derived
    isDirty,
    publishedTemplates,
    serviceContextItems,
    resolvedTemplates,
    serviceContextPresent,
    templateOptions,
    effectiveTemplateOptions,
    resolutionHasBlockingGap,
    singleAllowedTemplate,
    showRecentReportsBrowser,
    canEditActiveInstance,
    canSaveDraft,
    canFinalize,
    canRevise,
    canPrint,
    missingRequiredFields,
    hasMissingRequired,
    canFinalizeWithValidation,
  };
}
