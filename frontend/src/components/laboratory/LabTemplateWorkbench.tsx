import { useEffect, useLayoutEffect, useMemo, useState, useId, useRef } from 'react';
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle } from '../ui/macos';
import { useConfirm } from '../common/ConfirmDialog';
// ADR-0015: use useLabReporting hook instead of importing api/labReporting directly.
import { useLabReporting } from '../../hooks/useLabReporting';
import './LabTemplateWorkbench.css';

// L-H-6 fix: декомпозиция монолита (1598 → ~600 строк).
// Helper-функции и подкомпоненты вынесены в отдельные модули:
import {
  blankField,
  blankSection,
  blankVersion,
  hydrateVersion,
  buildVersionPayload,
  hasTemplateVersionAction,
  parseJsonInput,
} from './templateEditor/utils';
import {
  EDITOR_TABS,
  formatVersionStatus,
} from './templateEditor/config';
import NewTemplateDialog from './templateEditor/NewTemplateDialog';
import ContentTab from './templateEditor/ContentTab';
// STRAT#10: t() для i18n — confirm dialogs мигрированы на translation keys.
import DesignTab from './templateEditor/DesignTab';
import SignersTab from './templateEditor/SignersTab';
import PreviewTab from './templateEditor/PreviewTab';
import { useTranslation } from '../../i18n/useTranslation';
import { getErrorMessage } from '../../utils/type-guards';
import { Archive, BadgeCheck, Download, Files, Plus, RotateCcw, SlidersHorizontal, SquareStack } from 'lucide-react';

export default function LabTemplateWorkbench({
  templates,
  selectedTemplate = null,
  onSelectTemplate,
  onTemplatesChanged,
  registerDirtySource,
  onDirtyStateChange,
  guardTransition,
  templateTransitionPending = false,
  onOperationPendingChange = undefined,
  notify
}: {
  templates?: unknown[];
  selectedTemplate?: Record<string, unknown> | null;
  onSelectTemplate?: (template: Record<string, unknown>) => void;
  onTemplatesChanged?: (preferredTemplateId?: string | number | null) => Promise<void>;
  registerDirtySource?: (source: {
    id: string;
    isDirty: () => boolean;
    save: () => Promise<void>;
    discard?: () => void;
  }) => () => void;
  /** PR 3351: вызывается при каждом изменении dirty-состояния (sentinel route-guard). */
  onDirtyStateChange?: () => void;
  guardTransition?: (
    transition: () => void | Promise<void>,
    options?: { onCancel?: () => void | Promise<void>; sourceIds?: string[] },
  ) => boolean;
  templateTransitionPending?: boolean;
  onOperationPendingChange?: (pending: boolean) => void;
  notify?: (type: string, message: string) => void;
  [k: string]: unknown;
}) {
  const { t: rawT } = useTranslation();
  const t = rawT;
  // L-H-1 fix: useConfirm() для всех destructive actions (вместо native confirm()).
  // Согласованность с LabReportWorkbench — единый стилизованный portal-dialog
  // с focus-trap, Esc-to-cancel, явным описанием последствий.
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // ADR-0015: lab reporting API accessed via hook.
  const labReportingApi = useLabReporting();

  // UX-AUDIT-FIX14: useId() для уникальных ID <datalist>. Ранее ID были
  // захардкожены как 'lab-analyte-catalog' / 'lab-unit-catalog' —
  // глобальные, что вызывало бы коллизию при множественном монтировании
  // LabTemplateWorkbench (например, в тестах или будущих admin-панелях).
  // Теперь React генерирует уникальные ID на каждый instance компонента.
  const analyteCatalogId = useId();
  const unitCatalogId = useId();

  // Phase 4+: New Template dialog state (was always-visible form).
  const [showNewTemplateDialog, setShowNewTemplateDialog] = useState(false);

  // Phase 4+: editor tabs — Content / Design / Signers / Preview.
  const [editorTab, setEditorTab] = useState('content');

  // WF-21 fix: search в списке шаблонов.
  const [templateSearch, setTemplateSearch] = useState('');
  const [draftVersion, setDraftVersion] = useState(hydrateVersion(null));
  const [saving, setSaving] = useState(false);
  const [draftSourceVersion, setDraftSourceVersion] = useState<Record<string, unknown> | null>(null);
  const pendingCreatedDraftRef = useRef<{
    templateId: string | number;
    sourceVersionId: string | number | null;
    draftVersionId: string | number;
  } | null>(null);
  const [catalogUnits, setCatalogUnits] = useState<Array<Record<string, unknown>>>([]);
  const [catalogAnalytes, setCatalogAnalytes] = useState<Array<Record<string, unknown>>>([]);

  // Phase 4+ Phase 2: collapsible sections + field cards + duplicate + reorder.
  const [expandedSections, setExpandedSections] = useState<Set<number>>(new Set([0]));
  const [expandedFields, setExpandedFields] = useState<Set<string>>(new Set());

  const toggleSection = (sectionIndex: number) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(sectionIndex)) {
        next.delete(sectionIndex);
      } else {
        next.add(sectionIndex);
      }
      return next;
    });
  };

  const toggleField = (sectionIndex: number, fieldIndex: number) => {
    const key = `${sectionIndex}-${fieldIndex}`;
    setExpandedFields((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const activeVersion = useMemo(() => {
    if (!selectedTemplate) {
      return null;
    }
    const versions = ((selectedTemplate as { versions?: unknown[] })?.versions || []) as Record<string, unknown>[];
    const draftId = (selectedTemplate as { draft_version_id?: string | number })?.draft_version_id;
    const publishedId = (selectedTemplate as { published_version_id?: string | number })?.published_version_id;
    return versions.find((version) => version?.id === draftId)
      || versions.find((version) => version?.id === publishedId)
      || versions[versions.length - 1]
      || null;
  }, [selectedTemplate]);
  const draftHydrated = draftSourceVersion === activeVersion;
  const interactionPending = saving || templateTransitionPending || !draftHydrated;

  useLayoutEffect(() => {
    onOperationPendingChange?.(saving);
    return () => {
      if (saving) onOperationPendingChange?.(false);
    };
  }, [onOperationPendingChange, saving]);

  useEffect(() => {
    const pendingDraft = pendingCreatedDraftRef.current;
    if (!pendingDraft) return;
    const templateId = (selectedTemplate as { id?: string | number } | null)?.id;
    const activeVersionId = (activeVersion as Record<string, unknown> | null)?.id as string | number | undefined;
    if (
      String(templateId ?? '') !== String(pendingDraft.templateId)
      || (
        String(activeVersionId ?? '') !== String(pendingDraft.sourceVersionId ?? '')
        && String(activeVersionId ?? '') !== String(pendingDraft.draftVersionId)
      )
      || String(activeVersionId ?? '') === String(pendingDraft.draftVersionId)
    ) {
      pendingCreatedDraftRef.current = null;
    }
  }, [activeVersion, selectedTemplate]);

  useLayoutEffect(() => {
    setDraftVersion(hydrateVersion(activeVersion));
    setDraftSourceVersion(activeVersion);
  }, [activeVersion]);

  useEffect(() => {
    let cancelled = false;

    async function loadCatalog() {
      try {
        const [units, analytes] = await Promise.all([
          labReportingApi.listCatalogUnits(),
          labReportingApi.listCatalogAnalytes()
        ]) as [Record<string, unknown>[], Record<string, unknown>[]];
        if (cancelled) {
          return;
        }
        setCatalogUnits(units);
        setCatalogAnalytes(analytes);
      } catch (error) {
        if (!cancelled && notify) {
          notify('error', getErrorMessage(error) || t('errors.catalog_load_failed'));
        }
      }
    }

    loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [notify]);

  async function handleCreateTemplate(formData: Record<string, unknown>) {
    if (!formData.code || !formData.name) {
      notify?.('error', t('errors.template_code_name_required'));
      return;
    }

    const createAndSelect = async () => {
      setSaving(true);
      try {
        const created = await labReportingApi.createTemplate({
          ...formData,
          initial_version: blankVersion
        }) as Record<string, unknown> | undefined;
        notify?.('success', t('success.template_created'));
        setShowNewTemplateDialog(false);
        // PR5: единственный post-create переход. Родитель обновляет список и
        // выбирает ровно id из ответа; повторный onSelectTemplate запустил бы
        // второй dirty-guard уже после успешного POST.
        const createdId = (created as { id?: string | number })?.id ?? null;
        await onTemplatesChanged?.(createdId);
      } catch (error) {
        notify?.('error', getErrorMessage(error));
      } finally {
        setSaving(false);
      }
    };

    // PR5: подтверждение охватывает весь переход, включая POST. При Cancel
    // callback не выполняется, поэтому старый draft и заполненная форма
    // создания остаются на месте.
    if (guardTransition) {
      guardTransition(createAndSelect, { sourceIds: ['template'] });
      return;
    }
    await createAndSelect();
  }

  async function ensureDraftVersion(): Promise<string | number> {
    if (!selectedTemplate) {
      throw new Error(t('misc.ltw_snachala_vyberite_shablon'));
    }
    const templateId = (selectedTemplate as { id?: string | number })?.id as string | number;
    const sourceVersionId = ((activeVersion as Record<string, unknown>)?.id as string | number) ?? null;
    const pendingDraft = pendingCreatedDraftRef.current;
    if (
      pendingDraft
      && String(pendingDraft.templateId) === String(templateId)
      && String(pendingDraft.sourceVersionId ?? '') === String(sourceVersionId ?? '')
    ) {
      return pendingDraft.draftVersionId;
    }
    if (hasTemplateVersionAction(activeVersion, 'update')) {
      return (activeVersion as Record<string, unknown>)?.id as string | number;
    }
    if (!hasTemplateVersionAction(activeVersion, 'create_draft')) {
      throw new Error(t('misc.ltw_server_ne_razreshil_sozdat_c'));
    }
    const version = (await labReportingApi.createTemplateVersion(templateId, sourceVersionId)) as Record<string, unknown>;
    const draftVersionId = (version as Record<string, unknown>)?.id as string | number;
    pendingCreatedDraftRef.current = { templateId, sourceVersionId, draftVersionId };
    return draftVersionId;
  }

  // PR-57: validate reference ranges (low < high) before save/publish
  // PR4: читаем ТЕКУЩИЙ draft из reference_rule_text (structured editor
  // пишет именно туда), а не устаревший field.reference_rule с бэкенда —
  // иначе правка 1..10 -> 10..1 невидима для валидатора.
  function validateReferenceRanges() {
    if (!draftVersion?.sections) return [] as string[];
    const errors: string[] = [];
    draftVersion.sections.forEach((section: Record<string, unknown>, sIdx: number) => {
      ((section.fields as Record<string, unknown>[]) || []).forEach((field: Record<string, unknown>) => {
        const parsed = parseJsonInput(field.reference_rule_text as string | null | undefined);
        if (!parsed || parsed === Symbol.for('invalid-json') || typeof parsed !== 'object') return;
        const rule = parsed as Record<string, unknown>;
        const def = rule.default as Record<string, unknown> | undefined;
        if (def && def.low != null && def.high != null && def.low !== '' && def.high !== '') {
          if (parseFloat(String(def.low)) >= parseFloat(String(def.high))) {
            errors.push(t('misc.ltw_sektsiya_section_title_sidx_', { sIdx: (section.title as string) || sIdx + 1, field_key: (field.label as string) || (field.field_key as string), low: def.low, high: def.high }));
          }
        }
        ((rule.cases as Record<string, unknown>[]) || []).forEach((c: Record<string, unknown>, cIdx: number) => {
          if (c.low != null && c.high != null && c.low !== '' && c.high !== '') {
            if (parseFloat(String(c.low)) >= parseFloat(String(c.high))) {
              errors.push(t('misc.ltw_sektsiya_section_title_sidx__2', { sIdx: (section.title as string) || sIdx + 1, field_key: (field.label as string) || (field.field_key as string), cIdx: cIdx + 1, low: c.low, high: c.high }));
            }
          }
        });
      });
    });
    return errors;
  }

  // PR4: JSON-валидация правил текущего draft ДО любых запросов —
  // buildVersionPayload бросает позже, когда ensureDraftVersion уже успел
  // создать draft-версию запросом.
  function validateRuleJsonErrors() {
    if (!draftVersion?.sections) return [] as string[];
    const errors: string[] = [];
    const invalidMarker = Symbol.for('invalid-json');
    const ruleKeys: Array<[string, string]> = [
      ['reference_rule_text', 'правил нормы'],
      ['visibility_rule_text', 'правил видимости'],
      ['highlight_rule_text', 'правил подсветки'],
    ];
    draftVersion.sections.forEach((section: Record<string, unknown>, sIdx: number) => {
      ((section.fields as Record<string, unknown>[]) || []).forEach((field: Record<string, unknown>) => {
        const fieldTitle = (field.label as string) || (field.field_key as string) || `#${sIdx + 1}`;
        ruleKeys.forEach(([key, ruleTitle]) => {
          if (parseJsonInput(field[key] as string | null | undefined) === invalidMarker) {
            errors.push(`${fieldTitle}: JSON ${ruleTitle} заполнен некорректно`);
          }
        });
      });
    });
    return errors;
  }

  // PR-57: validate field_key uniqueness before save/publish
  function validateFieldKeyUniqueness() {
    if (!draftVersion?.sections) return [] as string[];
    const errors: string[] = [];
    const seenKeys = new Set<string>();
    draftVersion.sections.forEach((section: Record<string, unknown>, sIdx: number) => {
      ((section.fields as Record<string, unknown>[]) || []).forEach((field: Record<string, unknown>) => {
        const key = field.field_key as string;
        if (!key) return;
        if (seenKeys.has(key)) {
          errors.push(t('misc.ltw_dublikat_field_key_key_v_sek', { key: key, sIdx: (section.title as string) || sIdx + 1 }));
        }
        seenKeys.add(key);
      });
    });
    return errors;
  }

  // PR5: ядро сохранения draft шаблона — бросает исключение при неудаче,
  // чтобы dirty-guard не продолжал переход после неуспешного сохранения.
  async function attemptSaveTemplate() {
    if (!selectedTemplate) {
      const message = t('errors.select_template_first');
      throw new Error(message);
    }
    const rangeErrors = validateReferenceRanges();
    const jsonErrors = validateRuleJsonErrors();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || jsonErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...jsonErrors, ...keyErrors];
      const message = `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`;
      throw new Error(message);
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      const payload = buildVersionPayload(draftVersion);
      await labReportingApi.updateTemplateVersion(versionId, payload);
      notify?.('success', t('success.template_draft_saved'));
      await onTemplatesChanged?.();
    } finally {
      setSaving(false);
    }
  }

  // Единая оболочка для кнопки Save и dirty-guard: любая ошибка видима
  // пользователю и пробрасывается дальше, чтобы guard не выполнил переход.
  async function saveTemplateWithFeedback() {
    try {
      await attemptSaveTemplate();
    } catch (error) {
      notify?.('error', getErrorMessage(error, t('errors.save_failed')));
      throw error;
    }
  }

  async function handleSaveTemplate() {
    try {
      await saveTemplateWithFeedback();
    } catch {
      // saveTemplateWithFeedback уже показал ошибку; кнопка остаётся на месте.
    }
  }

  async function handlePublishVersion() {
    if (!selectedTemplate) {
      notify?.('error', t('errors.select_template'));
      return;
    }
    const rangeErrors = validateReferenceRanges();
    const jsonErrors = validateRuleJsonErrors();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || jsonErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...jsonErrors, ...keyErrors];
      notify?.('error', `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      await labReportingApi.updateTemplateVersion(versionId, buildVersionPayload(draftVersion));
      await labReportingApi.publishTemplateVersion(versionId);
      pendingCreatedDraftRef.current = null;
      notify?.('success', t('success.template_published'));
      await onTemplatesChanged?.();
    } catch (error) {
      notify?.('error', getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  // PR-65 / Medium-19: archive template version (soft-delete)
  // L-H-1 fix: native confirm() заменён на useConfirm() — стилизованный
  // portal-dialog с focus-trap, Esc-to-cancel, явным описанием последствий.
  async function handleArchiveTemplate() {
    if (!selectedTemplate || !activeVersion) {
      notify?.('error', t('errors.select_version_for_archive'));
      return;
    }
    // Archive exactly the version the operator selected when pressing the
    // button. Save-and-continue may create/refresh a different draft version;
    // letting the deferred callback read activeVersion again would make the
    // destructive target depend on response timing.
    const archiveVersionId = (activeVersion as Record<string, unknown>)?.id as string | number;
    const archiveAndRefresh = async () => {
      const ok = await confirm({
        title: t('confirm.archive_title'),
        message: t('confirm.archive_message'),
        description: t('confirm.archive_description'),
        confirmLabel: t('confirm.archive_confirm'),
        cancelLabel: t('confirm.cancel'),
        intent: 'warning',
      });
      if (!ok) return;
      setSaving(true);
      try {
        await labReportingApi.archiveTemplateVersion(archiveVersionId);
        notify?.('success', t('success.template_archived'));
        await onTemplatesChanged?.();
      } catch (error) {
        notify?.('error', getErrorMessage(error));
      } finally {
        setSaving(false);
      }
    };
    if (guardTransition) {
      // PR 3351 (review round 2, P1): archive меняет только шаблон — скоуп
      // ['template']. Dirty report-draft не должен ни спрашиваться, ни
      // сбрасываться: Queue/Templates/Reports смонтированы одновременно
      // (hidden-секции), операция над шаблоном не уничтожает report-черновик.
      guardTransition(archiveAndRefresh, { sourceIds: ['template'] });
      return;
    }
    await archiveAndRefresh();
  }

  async function handleCloneTemplate() {
    if (!selectedTemplate) {
      notify?.('error', t('errors.select_template_for_copy'));
      return;
    }
    const cloneAndRefresh = async () => {
      setSaving(true);
      try {
        await labReportingApi.cloneTemplate((selectedTemplate as { id?: string | number })?.id as string | number);
        notify?.('success', t('success.template_cloned'));
        await onTemplatesChanged?.();
      } catch (error) {
        const err = error as { message?: string };
        notify?.('error', err?.message || '');
      } finally {
        setSaving(false);
      }
    };
    if (guardTransition) {
      // PR 3351 (review round 2, P1): clone меняет только шаблон — скоуп
      // ['template'] (см. комментарий у archive).
      guardTransition(cloneAndRefresh, { sourceIds: ['template'] });
      return;
    }
    await cloneAndRefresh();
  }

  // ─── Field/Section mutation helpers (used by ContentTab) ───

  function updateBranding(key: string, value: unknown) {
    setDraftVersion((prev) => ({
      ...prev,
      branding_overrides: { ...prev.branding_overrides, [key]: value }
    }));
  }

  function updateSigner(key: string, value: unknown) {
    setDraftVersion((prev) => ({
      ...prev,
      signer_defaults: { ...prev.signer_defaults, [key]: value }
    }));
  }

  function updateSection(sectionIndex: number, key: string, value: unknown) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => (
        index === sectionIndex ? { ...section, [key]: value } : section
      ))
    }));
  }

  function updateField(sectionIndex: number, fieldIndex: number, key: string, value: unknown) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => {
        if (index !== sectionIndex) return section;
        return {
          ...section,
          fields: (section.fields as Record<string, unknown>[]).map((field: Record<string, unknown>, nestedIndex: number) => (
            nestedIndex === fieldIndex ? { ...field, [key]: value } : field
          ))
        };
      })
    }));
  }

  function updateFieldCatalog(sectionIndex: number, fieldIndex: number, key: string, value: unknown) {
    if (key !== 'analyte_code') {
      updateField(sectionIndex, fieldIndex, key, value);
      return;
    }
    const analyte = catalogAnalytes.find((item: Record<string, unknown>) => item.code === value);
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => {
        if (index !== sectionIndex) return section;
        return {
          ...section,
          fields: (section.fields as Record<string, unknown>[]).map((field: Record<string, unknown>, nestedIndex: number) => {
            if (nestedIndex !== fieldIndex) return field;
            return {
              ...field,
              analyte_code: value,
              unit_code: analyte?.default_unit_code || field.unit_code || ''
            };
          })
        };
      })
    }));
  }

  async function loadCatalogReferenceRange(sectionIndex: number, fieldIndex: number, analyteCode: string) {
    try {
      const ranges = await labReportingApi.listCatalogReferenceRanges(analyteCode as unknown as null) as unknown as Array<{ text?: string; low?: number; high?: number }>;
      if (ranges && ranges.length > 0) {
        const range = ranges[0];
        updateField(sectionIndex, fieldIndex, 'reference_text',
          range.text || `${range.low || ''}–${range.high || ''}`);
        if (range.low != null) updateField(sectionIndex, fieldIndex, 'reference_low', range.low as number);
        if (range.high != null) updateField(sectionIndex, fieldIndex, 'reference_high', range.high as number);
        notify?.('success', `${t('success.norm_loaded_from_catalog')}: ${range.text || ''}`);
      } else {
        notify?.('info', t('errors.no_norm_in_catalog'));
      }
    } catch (e) {
      notify?.('error', `${t('errors.catalog_load_error')}: ${(e as Error).message}`);
    }
  }

  function addSection() {
    setDraftVersion((prev) => ({
      ...prev,
      sections: [...prev.sections, blankSection(prev.sections.length + 1)]
    }));
  }

  function addField(sectionIndex: number) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => (
        index === sectionIndex
          ? { ...section, fields: [...((section.fields as Record<string, unknown>[]) || []), blankField()] }
          : section
      ))
    }));
  }

  function removeField(sectionIndex: number, fieldIndex: number) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => (
        index === sectionIndex
          ? { ...section, fields: (section.fields as Record<string, unknown>[]).filter((_, nestedIndex: number) => nestedIndex !== fieldIndex) }
          : section
      ))
    }));
  }

  function removeSection(sectionIndex: number) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.filter((_: Record<string, unknown>, index: number) => index !== sectionIndex)
    }));
  }

  function duplicateField(sectionIndex: number, fieldIndex: number) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => {
        if (index !== sectionIndex) return section;
        const fields = section.fields as Record<string, unknown>[];
        const fieldToClone = fields[fieldIndex];
        if (!fieldToClone) return section;
        const cloned = {
          ...fieldToClone,
          field_key: `${fieldToClone.field_key || 'field'}_copy_${Date.now()}`,
          label: t('misc.ltw_fieldtoclone_label_pole_kopi', { label: (fieldToClone.label as string) || 'Поле' }),
        };
        const newFields = [...fields];
        newFields.splice(fieldIndex + 1, 0, cloned);
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveField(sectionIndex: number, fieldIndex: number, direction: 'up' | 'down') {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section: Record<string, unknown>, index: number) => {
        if (index !== sectionIndex) return section;
        const newFields = [...(section.fields as Record<string, unknown>[])];
        const targetIndex = direction === 'up' ? fieldIndex - 1 : fieldIndex + 1;
        if (targetIndex < 0 || targetIndex >= newFields.length) return section;
        [newFields[fieldIndex], newFields[targetIndex]] = [newFields[targetIndex], newFields[fieldIndex]];
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveSection(sectionIndex: number, direction: 'up' | 'down') {
    setDraftVersion((prev) => {
      const newSections = [...prev.sections];
      const targetIndex = direction === 'up' ? sectionIndex - 1 : sectionIndex + 1;
      if (targetIndex < 0 || targetIndex >= newSections.length) return prev;
      [newSections[sectionIndex], newSections[targetIndex]] = [newSections[targetIndex], newSections[sectionIndex]];
      return { ...prev, sections: newSections };
    });
  }

  // L-H-6 fix: render-tab функции заменены на подкомпоненты ContentTab /
  // DesignTab / SignersTab / PreviewTab. Это убирает ~700 строк из этого файла
  // и позволяет независимо тестировать каждый tab.

  // PR5: dirty-state draft шаблона — черновик отличается от hydrate(activeVersion).
  const templateDirty = useMemo(() => {
    if (!selectedTemplate || !draftHydrated) return false;
    return JSON.stringify(draftVersion) !== JSON.stringify(hydrateVersion(activeVersion));
  }, [draftHydrated, draftVersion, selectedTemplate, activeVersion]);

  const isTemplateDirtyRef = useRef(templateDirty);
  // PR 3351 (route-level leave guard): обновляемый ref + notify на каждом
  // рендере — route-guard перевзвешивает sentinel при флипе dirty.
  const onDirtyStateChangeRef = useRef(onDirtyStateChange);
  useEffect(() => {
    onDirtyStateChangeRef.current = onDirtyStateChange;
  });
  useEffect(() => {
    isTemplateDirtyRef.current = templateDirty;
    onDirtyStateChangeRef.current?.();
  });
  const activeVersionRef = useRef(activeVersion);
  useEffect(() => {
    activeVersionRef.current = activeVersion;
  });
  const registerDirtySourceRef = useRef(registerDirtySource);
  // PR5-review: saveTemplateWithFeedback захватывает state конкретного рендера —
  // регистрация монтируется один раз, но вызывает АКТУАЛЬНУЮ функцию через
  // обновляемый ref (паттерн handleSaveDraftRef в LabReportWorkbench),
  // иначе после загрузки шаблона save продолжает видеть первый рендер.
  const attemptSaveTemplateRef = useRef<() => Promise<void>>(async () => {});
  useEffect(() => {
    attemptSaveTemplateRef.current = saveTemplateWithFeedback;
  });
  useEffect(() => {
    if (!registerDirtySourceRef.current) return;
    return registerDirtySourceRef.current({
      id: 'template',
      isDirty: () => isTemplateDirtyRef.current,
      save: () => attemptSaveTemplateRef.current(),
      // PR 3351: Discard сбрасывает черновик шаблона к hydrate(activeVersion).
      // Если переход (загрузка другого шаблона) упадёт и вернёт прежний
      // selectedTemplate, сброшенный draft не останется dirty и не будет
      // перезаписан поздним сохранением.
      discard: () => {
        setDraftVersion(hydrateVersion(activeVersionRef.current));
      },
    });
  }, []);

  // PR 3351 (review round 6, P1): beforeunload для полного документа
  // (refresh/закрытие вкладки) больше не ставится здесь. Единственный
  // владелец — LabDirtyGuardProvider: он видит ОБЩЕЕ состояние
  // (dirty-источники ИЛИ незавершённые операции), поэтому pending-only
  // мутация (clone чистого шаблона) тоже блокирует unload. Workbench-хук
  // на одном dirty-state этот сценарий пропускал.

  // PR4: единый список ошибок валидации текущего draft для inline-блока;
  // хендлеры Save/Publish используют те же проверки перед любым запросом.
  const draftValidationErrors = [
    ...validateReferenceRanges(),
    ...validateRuleJsonErrors(),
    ...validateFieldKeyUniqueness(),
  ];

  return (
    <fieldset
      disabled={interactionPending}
      aria-busy={interactionPending}
      className="ltw-fieldset-reset"
    >
      <div className="ltw-root">
      <Card variant="filled" padding="none">
        <CardHeader className="ltw-card-header">
          <CardTitle className="ltw-card-title">
            <span className="ltw-flex-center">
              <SquareStack size={20} aria-hidden="true" />
              {t('template.title')}
            </span>
            <Button variant="primary" size="small" onClick={() => setShowNewTemplateDialog(true)} disabled={interactionPending}>
              <Plus size={14} aria-hidden="true" />
              {t('template.new_template')}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="ltw-card-content">
          {/* WF-21 fix: search для консистентности с LabQueueWorkbench */}
          <div className="ltw-search-wrapper">
            <input
              type="search"
              value={templateSearch}
              onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setTemplateSearch(e.target.value)}
              placeholder={t('misc.ltw_poisk_po_nazvaniyu_kodu_seme')}
              aria-label={t('misc.ltw_poisk_shablonov')}
              className="ltw-search-input"
            />
            {templateSearch && (
              <button
                type="button"
                onClick={() => setTemplateSearch('')}
                aria-label={t('misc.ltw_ochistit_poisk')}
                className="ltw-search-clear"
              >
                ×
              </button>
            )}
          </div>

          <div className="ltw-grid-8">
            {((templates as Record<string, unknown>[]) || [])
              .filter((t: Record<string, unknown>) => {
                if (!templateSearch.trim()) return true;
                const q = templateSearch.trim().toLowerCase();
                return [String(t.name ?? ''), String(t.code ?? ''), String(t.family ?? '')].some((f) => (f || '').toLowerCase().includes(q));
              })
              .map((template: Record<string, unknown>) => (
              <button
                key={String(template.id ?? "")}
                type="button"
                onClick={() => {
                  if (!interactionPending) onSelectTemplate?.(template as Record<string, unknown>);
                }}
                disabled={interactionPending}
                className={`ltw-template-btn ${String(selectedTemplate?.id ?? "") === String(template.id ?? "") ? 'ltw-template-btn-selected' : ''}`}
              >
                <div className="ltw-fw-600">{String(template.name ?? "")}</div>
                <div className="ltw-text-13 ltw-text-secondary">{String(template.code ?? "")} • {String(template.family ?? "")}</div>
                <div className="ltw-flex-gap-6">
                  {Boolean(template.published_version_id) && <Badge variant="success">{t('misc.ltw_opublikovan')}</Badge>}
                  {Boolean(template.draft_version_id) && <Badge variant="warning">{t('misc.ltw_chernovik')}</Badge>}
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card variant="filled" padding="none">
        <CardHeader className="ltw-card-header">
          <CardTitle className="ltw-card-title-gap-12">
            <span className="ltw-flex-center">
              <SlidersHorizontal size={20} aria-hidden="true" />
              Редактор бланка
            </span>
            {selectedTemplate && (
              <div className="ltw-flex-gap-8">
                <Button variant="outline" onClick={handleCloneTemplate} disabled={saving}>
                  <Files size={16} aria-hidden="true" />
                  {t('template.clone')}
                </Button>
                <Button
                  variant="outline"
                  onClick={async () => {
                    if (!activeVersion) return;
                    // UX-AUDIT-QW2: Reset — необратимая потеря черновика.
                    // Ранее выполнялся мгновенно через notify('info', ...),
                    // что диссонировало с ConfirmDialog на Archive/Publish.
                    // Теперь обёрнут в useConfirm() — соответствует
                    // Nielsen Heuristic #5 (Error Prevention) и эвристике #4
                    // (Consistency & Standards).
                    const ok = await confirm({
                      title: t('confirm.reset_draft_title'),
                      message: t('confirm.reset_draft_message'),
                      description: t('confirm.reset_draft_description'),
                      confirmLabel: t('confirm.reset_confirm'),
                      cancelLabel: t('confirm.cancel'),
                      intent: 'warning',
                    });
                    if (!ok) return;
                    setDraftVersion(hydrateVersion(activeVersion));
                    notify?.('success', t('misc.ltw_chernovik_vosstanovlen_iz_se'));
                  }}
                  disabled={saving || !activeVersion}
                  title={t('misc.ltw_otmenit_izmeneniya_i_vosstan')}
                >
                  <RotateCcw size={16} aria-hidden="true" />
                  Отменить
                </Button>
                <Button variant="outline" onClick={handleSaveTemplate} disabled={saving}>
                  <Download size={16} aria-hidden="true" />
                  {t('common.save_draft')}
                </Button>
                <Button variant="primary" onClick={handlePublishVersion} disabled={saving}>
                  <BadgeCheck size={16} aria-hidden="true" />
                  {t('template.publish')}
                </Button>
                <Button variant="outline" onClick={handleArchiveTemplate} disabled={saving || !activeVersion} title={t('template.archive')}>
                  <Archive size={16} aria-hidden="true" />
                  {t('template.archive')}
                </Button>
              </div>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="ltw-card-content-flat">
          {!selectedTemplate ? (
            <Alert severity="info">{t('misc.ltw_vyberite_shablon_sleva_chtob')}</Alert>
          ) : (
            <div className="ltw-grid-16">
              {/* PR4: inline-ошибки валидации текущего draft — видны до
                  нажатия Save/Publish, без ожидания toast-уведомления. */}
              {draftValidationErrors.length > 0 && (
                <Alert severity="error" role="alert">
                  {draftValidationErrors.slice(0, 5).map((errorText: string) => (
                    <div key={errorText}>{errorText}</div>
                  ))}
                  {draftValidationErrors.length > 5 && <div>… +{draftValidationErrors.length - 5}</div>}
                </Alert>
              )}
              <div className="ltw-badges-row">
                <Badge variant="info">{String(selectedTemplate.code ?? "")}</Badge>
                <Badge variant="primary">{String(selectedTemplate.family ?? "")}</Badge>
                {Boolean((activeVersion as Record<string, unknown>)?.status) && <Badge variant={(activeVersion as Record<string, unknown>)?.status === 'PUBLISHED' ? 'success' : 'warning'}>{formatVersionStatus(String((activeVersion as Record<string, unknown>)?.status))}</Badge>}
              </div>

              {/* L-M-7 fix: заменён aria-pressed на role=tablist + role=tab + aria-selected.
                  Согласованность с LabPanel.jsx (там тоже role=tablist).
                  Keyboard-навигация: стрелки вправо/лево, Home, End. */}
              <div className="ltw-tab-bar ltw-tablist" role="tablist" aria-label={t('misc.ltw_redaktor_shablona')}>
                {EDITOR_TABS.map((tab: { id: string; label: string }) => {
                  const isActive = editorTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      id={`ltw-tab-${tab.id}`}
                      aria-selected={isActive}
                      aria-controls={`ltw-tabpanel-${tab.id}`}
                      tabIndex={isActive ? 0 : -1}
                      onClick={() => setEditorTab(tab.id)}
                      onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => {
                        const idx = EDITOR_TABS.findIndex((tt) => tt.id === tab.id);
                        let nextIdx: number | null = null;
                        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextIdx = (idx + 1) % EDITOR_TABS.length;
                        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') nextIdx = (idx - 1 + EDITOR_TABS.length) % EDITOR_TABS.length;
                        else if (e.key === 'Home') nextIdx = 0;
                        else if (e.key === 'End') nextIdx = EDITOR_TABS.length - 1;
                        if (nextIdx !== null) {
                          e.preventDefault();
                          setEditorTab(EDITOR_TABS[nextIdx].id);
                          window.requestAnimationFrame(() => {
                            document.getElementById(`ltw-tab-${EDITOR_TABS[nextIdx].id}`)?.focus();
                          });
                        }
                      }}
                      className={`ltw-tablist-tab ${isActive ? 'ltw-tablist-tab-active' : ''}`}
                    >
                      {t(`template.${tab.id}_tab`)}
                    </button>
                  );
                })}
              </div>

              {/* L-M-7 fix: добавлены role=tabpanel для согласованности с tablist-pattern. */}
              <div
                id={`ltw-tabpanel-${editorTab}`}
                role="tabpanel"
                aria-labelledby={`ltw-tab-${editorTab}`}
                tabIndex={0}
              >
                {editorTab === 'content' && (
                <ContentTab
                  draftVersion={draftVersion}
                  expandedSections={expandedSections}
                  expandedFields={expandedFields}
                  onToggleSection={toggleSection}
                  onToggleField={toggleField}
                  onAddSection={addSection}
                  onAddField={addField}
                  onRemoveSection={removeSection}
                  onRemoveField={removeField}
                  onDuplicateField={duplicateField}
                  onMoveField={moveField}
                  onMoveSection={moveSection}
                  onUpdateSection={updateSection}
                  onUpdateField={updateField}
                  onUpdateFieldCatalog={updateFieldCatalog}
                  onLoadCatalogReferenceRange={loadCatalogReferenceRange}
                  // UX-AUDIT-FIX14: передаём уникальные ID для <datalist>
                  analyteCatalogId={analyteCatalogId}
                  unitCatalogId={unitCatalogId}
                />
              )}
              {editorTab === 'design' && (
                <DesignTab
                  draftVersion={draftVersion}
                  onUpdateLayout={(value) => setDraftVersion((prev) => ({ ...prev, layout_preset: value }))}
                  onUpdateFooter={(value) => setDraftVersion((prev) => ({ ...prev, footer_notes: value }))}
                  onUpdateBranding={updateBranding}
                />
              )}
              {editorTab === 'signers' && (
                <SignersTab
                  draftVersion={draftVersion}
                  onUpdateSigner={updateSigner}
                />
              )}
              {editorTab === 'preview' && (
                <PreviewTab draftVersion={draftVersion} />
              )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <NewTemplateDialog
        open={showNewTemplateDialog}
        onClose={() => setShowNewTemplateDialog(false)}
        onCreate={handleCreateTemplate}
        saving={interactionPending}
        existingTemplates={templates as unknown as Parameters<typeof NewTemplateDialog>[0]['existingTemplates']}
      />

      {/* UX-AUDIT-FIX14: ID datalist теперь уникальны per-instance (useId) */}
      <datalist id={analyteCatalogId}>
        {catalogAnalytes.map((analyte: Record<string, unknown>) => (
          <option key={String(analyte.code ?? '')} value={String(analyte.code ?? '')}>
            {String(analyte.name ?? '')}
          </option>
        ))}
      </datalist>
      <datalist id={unitCatalogId}>
        {catalogUnits.map((unit: Record<string, unknown>) => (
          <option key={String(unit.code ?? '')} value={String(unit.code ?? '')}>
            {String(unit.symbol ?? '')}
          </option>
        ))}
      </datalist>

      {/* L-H-1 fix: portal-mounted ConfirmDialog для destructive actions */}
      {confirmDialog}
      </div>
    </fieldset>
  );
}

