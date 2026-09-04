import { useEffect, useMemo, useState, useId } from 'react';
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
  notify
}: {
  templates?: unknown[];
  selectedTemplate?: Record<string, unknown> | null;
  onSelectTemplate?: (template: Record<string, unknown>) => void;
  onTemplatesChanged?: () => Promise<void>;
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

  useEffect(() => {
    setDraftVersion(hydrateVersion(activeVersion));
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
    setSaving(true);
    try {
      await labReportingApi.createTemplate({
        ...formData,
        initial_version: blankVersion
      });
      notify?.('success', t('success.template_created'));
      setShowNewTemplateDialog(false);
      await onTemplatesChanged?.();
    } catch (error) {
      notify?.('error', getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function ensureDraftVersion(): Promise<string | number> {
    if (!selectedTemplate) {
      throw new Error(t('misc.ltw_snachala_vyberite_shablon'));
    }
    if (hasTemplateVersionAction(activeVersion, 'update')) {
      return (activeVersion as Record<string, unknown>)?.id as string | number;
    }
    if (!hasTemplateVersionAction(activeVersion, 'create_draft')) {
      throw new Error(t('misc.ltw_server_ne_razreshil_sozdat_c'));
    }
    const version = (await labReportingApi.createTemplateVersion((selectedTemplate as { id?: string | number })?.id as string | number, ((activeVersion as Record<string, unknown>)?.id as string | number) ?? null)) as Record<string, unknown>;
    await onTemplatesChanged?.();
    return (version as Record<string, unknown>)?.id as string | number;
  }

  // PR-57: validate reference ranges (low < high) before save/publish
  function validateReferenceRanges() {
    if (!draftVersion?.sections) return [] as string[];
    const errors: string[] = [];
    draftVersion.sections.forEach((section: Record<string, unknown>, sIdx: number) => {
      ((section.fields as Record<string, unknown>[]) || []).forEach((field: Record<string, unknown>) => {
        const rule = field.reference_rule as Record<string, unknown> | null;
        if (!rule) return;
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

  async function handleSaveTemplate() {
    if (!selectedTemplate) {
      notify?.('error', t('errors.select_template_first'));
      return;
    }
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify?.('error', `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      const payload = buildVersionPayload(draftVersion);
      await labReportingApi.updateTemplateVersion(versionId, payload);
      notify?.('success', t('success.template_draft_saved'));
      await onTemplatesChanged?.();
    } catch (error) {
      notify?.('error', getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handlePublishVersion() {
    if (!selectedTemplate) {
      notify?.('error', t('errors.select_template'));
      return;
    }
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify?.('error', `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      await labReportingApi.updateTemplateVersion(versionId, buildVersionPayload(draftVersion));
      await labReportingApi.publishTemplateVersion(versionId);
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
      await labReportingApi.archiveTemplateVersion((activeVersion as Record<string, unknown>)?.id as string | number);
      notify?.('success', t('success.template_archived'));
      await onTemplatesChanged?.();
    } catch (error) {
      notify?.('error', getErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  async function handleCloneTemplate() {
    if (!selectedTemplate) {
      notify?.('error', t('errors.select_template_for_copy'));
      return;
    }
    setSaving(true);
    try {
      const cloned = (await labReportingApi.cloneTemplate((selectedTemplate as { id?: string | number })?.id as string | number)) as Record<string, unknown>;
      notify?.('success', t('success.template_cloned'));
      await onTemplatesChanged?.();
    } catch (error) {
      const err = error as { message?: string };
      notify?.('error', err?.message || '');
    } finally {
      setSaving(false);
    }
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

  return (
    <div className="ltw-root">
      <Card variant="filled" padding="none">
        <CardHeader className="ltw-card-header">
          <CardTitle className="ltw-card-title">
            <span className="ltw-flex-center">
              <SquareStack size={20} aria-hidden="true" />
              {t('template.title')}
            </span>
            <Button variant="primary" size="small" onClick={() => setShowNewTemplateDialog(true)} disabled={saving}>
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
                onClick={() => onSelectTemplate?.(template as Record<string, unknown>)}
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
        saving={saving}
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
  );
}

