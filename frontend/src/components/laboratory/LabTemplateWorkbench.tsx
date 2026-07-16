// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useMemo, useState, useId } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Icon,
} from '../ui/macos';
import { useConfirm } from '../common/ConfirmDialog';
import { labReportingApi } from '../../api/labReporting';
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

export default function LabTemplateWorkbench({
  templates,
  selectedTemplate = null,
  onSelectTemplate,
  onTemplatesChanged,
  notify
}) {
  const { t } = useTranslation();
  // L-H-1 fix: useConfirm() для всех destructive actions (вместо native confirm()).
  // Согласованность с LabReportWorkbench — единый стилизованный portal-dialog
  // с focus-trap, Esc-to-cancel, явным описанием последствий.
  const [confirm, confirmDialog] = useConfirm();

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
  const [catalogUnits, setCatalogUnits] = useState([]);
  const [catalogAnalytes, setCatalogAnalytes] = useState([]);

  // Phase 4+ Phase 2: collapsible sections + field cards + duplicate + reorder.
  const [expandedSections, setExpandedSections] = useState(new Set([0]));
  const [expandedFields, setExpandedFields] = useState(new Set());

  const toggleSection = (sectionIndex) => {
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

  const toggleField = (sectionIndex, fieldIndex) => {
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
    return selectedTemplate.versions.find((version) => version.id === selectedTemplate.draft_version_id)
      || selectedTemplate.versions.find((version) => version.id === selectedTemplate.published_version_id)
      || selectedTemplate.versions[selectedTemplate.versions.length - 1]
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
        ]);
        if (cancelled) {
          return;
        }
        setCatalogUnits(units);
        setCatalogAnalytes(analytes);
      } catch (error) {
        if (!cancelled) {
          notify('error', error.message || t('errors.catalog_load_failed'));
        }
      }
    }

    loadCatalog();
    return () => {
      cancelled = true;
    };
  }, [notify]);

  async function handleCreateTemplate(formData) {
    if (!formData.code || !formData.name) {
      notify('error', t('errors.template_code_name_required'));
      return;
    }
    setSaving(true);
    try {
      await labReportingApi.createTemplate({
        ...formData,
        initial_version: blankVersion
      });
      notify('success', t('success.template_created'));
      setShowNewTemplateDialog(false);
      await onTemplatesChanged();
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function ensureDraftVersion() {
    if (!selectedTemplate) {
      throw new Error(t('misc.ltw_snachala_vyberite_shablon'));
    }
    if (hasTemplateVersionAction(activeVersion, 'update')) {
      return activeVersion.id;
    }
    if (!hasTemplateVersionAction(activeVersion, 'create_draft')) {
      throw new Error(t('misc.ltw_server_ne_razreshil_sozdat_c'));
    }
    const version = await labReportingApi.createTemplateVersion(selectedTemplate.id, activeVersion?.id || null);
    await onTemplatesChanged(selectedTemplate.id);
    return version.id;
  }

  // PR-57: validate reference ranges (low < high) before save/publish
  function validateReferenceRanges() {
    if (!draftVersion?.sections) return [];
    const errors = [];
    draftVersion.sections.forEach((section, sIdx) => {
      (section.fields || []).forEach((field) => {
        const rule = field.reference_rule;
        if (!rule) return;
        const def = rule.default;
        if (def && def.low != null && def.high != null && def.low !== '' && def.high !== '') {
          if (parseFloat(def.low) >= parseFloat(def.high)) {
            errors.push(t('misc.ltw_sektsiya_section_title_sidx_', { sIdx: section.title || sIdx + 1, field_key: field.label || field.field_key, low: def.low, high: def.high }));
          }
        }
        (rule.cases || []).forEach((c, cIdx) => {
          if (c.low != null && c.high != null && c.low !== '' && c.high !== '') {
            if (parseFloat(c.low) >= parseFloat(c.high)) {
              errors.push(t('misc.ltw_sektsiya_section_title_sidx__2', { sIdx: section.title || sIdx + 1, field_key: field.label || field.field_key, cIdx: cIdx + 1, low: c.low, high: c.high }));
            }
          }
        });
      });
    });
    return errors;
  }

  // PR-57: validate field_key uniqueness before save/publish
  function validateFieldKeyUniqueness() {
    if (!draftVersion?.sections) return [];
    const errors = [];
    const seenKeys = new Set();
    draftVersion.sections.forEach((section, sIdx) => {
      (section.fields || []).forEach((field) => {
        const key = field.field_key;
        if (!key) return;
        if (seenKeys.has(key)) {
          errors.push(t('misc.ltw_dublikat_field_key_key_v_sek', { key: key, sIdx: section.title || sIdx + 1 }));
        }
        seenKeys.add(key);
      });
    });
    return errors;
  }

  async function handleSaveTemplate() {
    if (!selectedTemplate) {
      notify('error', t('errors.select_template_first'));
      return;
    }
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify('error', `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      const payload = buildVersionPayload(draftVersion);
      await labReportingApi.updateTemplateVersion(versionId, payload);
      notify('success', t('success.template_draft_saved'));
      await onTemplatesChanged(selectedTemplate.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handlePublishVersion() {
    if (!selectedTemplate) {
      notify('error', t('errors.select_template'));
      return;
    }
    const rangeErrors = validateReferenceRanges();
    const keyErrors = validateFieldKeyUniqueness();
    if (rangeErrors.length > 0 || keyErrors.length > 0) {
      const allErrors = [...rangeErrors, ...keyErrors];
      notify('error', `${t('errors.validation_errors')} (${allErrors.length}):\n${allErrors.slice(0, 5).join('\n')}${allErrors.length > 5 ? '\n...' : ''}`);
      return;
    }
    setSaving(true);
    try {
      const versionId = await ensureDraftVersion();
      await labReportingApi.updateTemplateVersion(versionId, buildVersionPayload(draftVersion));
      await labReportingApi.publishTemplateVersion(versionId);
      notify('success', t('success.template_published'));
      await onTemplatesChanged(selectedTemplate.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  // PR-65 / Medium-19: archive template version (soft-delete)
  // L-H-1 fix: native confirm() заменён на useConfirm() — стилизованный
  // portal-dialog с focus-trap, Esc-to-cancel, явным описанием последствий.
  async function handleArchiveTemplate() {
    if (!selectedTemplate || !activeVersion) {
      notify('error', t('errors.select_version_for_archive'));
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
      await labReportingApi.archiveTemplateVersion(activeVersion.id);
      notify('success', t('success.template_archived'));
      await onTemplatesChanged(selectedTemplate.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleCloneTemplate() {
    if (!selectedTemplate) {
      notify('error', t('errors.select_template_for_copy'));
      return;
    }
    setSaving(true);
    try {
      const cloned = await labReportingApi.cloneTemplate(selectedTemplate.id);
      notify('success', t('success.template_cloned'));
      await onTemplatesChanged(cloned.id);
    } catch (error) {
      notify('error', error.message);
    } finally {
      setSaving(false);
    }
  }

  // ─── Field/Section mutation helpers (used by ContentTab) ───

  function updateBranding(key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      branding_overrides: { ...prev.branding_overrides, [key]: value }
    }));
  }

  function updateSigner(key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      signer_defaults: { ...prev.signer_defaults, [key]: value }
    }));
  }

  function updateSection(sectionIndex, key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex ? { ...section, [key]: value } : section
      ))
    }));
  }

  function updateField(sectionIndex, fieldIndex, key, value) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        return {
          ...section,
          fields: section.fields.map((field, nestedIndex) => (
            nestedIndex === fieldIndex ? { ...field, [key]: value } : field
          ))
        };
      })
    }));
  }

  function updateFieldCatalog(sectionIndex, fieldIndex, key, value) {
    if (key !== 'analyte_code') {
      updateField(sectionIndex, fieldIndex, key, value);
      return;
    }
    const analyte = catalogAnalytes.find((item) => item.code === value);
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        return {
          ...section,
          fields: section.fields.map((field, nestedIndex) => {
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

  async function loadCatalogReferenceRange(sectionIndex, fieldIndex, analyteCode) {
    try {
      const ranges = await labReportingApi.listCatalogReferenceRanges(analyteCode);
      if (ranges && ranges.length > 0) {
        const range = ranges[0];
        updateField(sectionIndex, fieldIndex, 'reference_text',
          range.text || `${range.low || ''}–${range.high || ''}`);
        if (range.low != null) updateField(sectionIndex, fieldIndex, 'reference_low', range.low);
        if (range.high != null) updateField(sectionIndex, fieldIndex, 'reference_high', range.high);
        notify('success', `${t('success.norm_loaded_from_catalog')}: ${range.text || ''}`);
      } else {
        notify('info', t('errors.no_norm_in_catalog'));
      }
    } catch (e) {
      notify('error', `${t('errors.catalog_load_error')}: ${e.message}`);
    }
  }

  function addSection() {
    setDraftVersion((prev) => ({
      ...prev,
      sections: [...prev.sections, blankSection(prev.sections.length + 1)]
    }));
  }

  function addField(sectionIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex
          ? { ...section, fields: [...section.fields, blankField()] }
          : section
      ))
    }));
  }

  function removeField(sectionIndex, fieldIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => (
        index === sectionIndex
          ? { ...section, fields: section.fields.filter((_, nestedIndex) => nestedIndex !== fieldIndex) }
          : section
      ))
    }));
  }

  function removeSection(sectionIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.filter((_, index) => index !== sectionIndex)
    }));
  }

  function duplicateField(sectionIndex, fieldIndex) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        const fieldToClone = section.fields[fieldIndex];
        if (!fieldToClone) return section;
        const cloned = {
          ...fieldToClone,
          field_key: `${fieldToClone.field_key || 'field'}_copy_${Date.now()}`,
          label: t('misc.ltw_fieldtoclone_label_pole_kopi', { label: fieldToClone.label || 'Поле' }),
        };
        const newFields = [...section.fields];
        newFields.splice(fieldIndex + 1, 0, cloned);
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveField(sectionIndex, fieldIndex, direction) {
    setDraftVersion((prev) => ({
      ...prev,
      sections: prev.sections.map((section, index) => {
        if (index !== sectionIndex) return section;
        const newFields = [...section.fields];
        const targetIndex = direction === 'up' ? fieldIndex - 1 : fieldIndex + 1;
        if (targetIndex < 0 || targetIndex >= newFields.length) return section;
        [newFields[fieldIndex], newFields[targetIndex]] = [newFields[targetIndex], newFields[fieldIndex]];
        return { ...section, fields: newFields };
      })
    }));
  }

  function moveSection(sectionIndex, direction) {
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
              <Icon name="rectangle.stack.badge.plus" size={20} />
              {t('template.title')}
            </span>
            <Button variant="primary" size="small" onClick={() => setShowNewTemplateDialog(true)} disabled={saving}>
              <Icon name="plus" size={14} />
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
              onChange={(e) => setTemplateSearch(e.target.value)}
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
            {templates
              .filter((t) => {
                if (!templateSearch.trim()) return true;
                const q = templateSearch.trim().toLowerCase();
                return [t.name, t.code, t.family].some((f) => (f || '').toLowerCase().includes(q));
              })
              .map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => onSelectTemplate(template.id)}
                className={`ltw-template-btn ${selectedTemplate?.id === template.id ? 'ltw-template-btn-selected' : ''}`}
              >
                <div className="ltw-fw-600">{template.name}</div>
                <div className="ltw-text-13 ltw-text-secondary">{template.code} • {template.family}</div>
                <div className="ltw-flex-gap-6">
                  {template.published_version_id && <Badge variant="success">{t('misc.ltw_opublikovan')}</Badge>}
                  {template.draft_version_id && <Badge variant="warning">{t('misc.ltw_chernovik')}</Badge>}
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
              <Icon name="slider.horizontal.3" size={20} />
              Редактор бланка
            </span>
            {selectedTemplate && (
              <div className="ltw-flex-gap-8">
                <Button variant="outline" onClick={handleCloneTemplate} disabled={saving}>
                  <Icon name="doc.on.doc" size={16} />
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
                    notify('success', t('misc.ltw_chernovik_vosstanovlen_iz_se'));
                  }}
                  disabled={saving || !activeVersion}
                  title={t('misc.ltw_otmenit_izmeneniya_i_vosstan')}
                >
                  <Icon name="arrow.counterclockwise" size={16} />
                  Отменить
                </Button>
                <Button variant="outline" onClick={handleSaveTemplate} disabled={saving}>
                  <Icon name="square.and.arrow.down" size={16} />
                  {t('common.save_draft')}
                </Button>
                <Button variant="primary" onClick={handlePublishVersion} disabled={saving}>
                  <Icon name="checkmark.seal" size={16} />
                  {t('template.publish')}
                </Button>
                <Button variant="outline" onClick={handleArchiveTemplate} disabled={saving || !activeVersion} title={t('template.archive')}>
                  <Icon name="archivebox" size={16} />
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
                <Badge variant="info">{selectedTemplate.code}</Badge>
                <Badge variant="primary">{selectedTemplate.family}</Badge>
                {activeVersion?.status && <Badge variant={activeVersion.status === 'PUBLISHED' ? 'success' : 'warning'}>{formatVersionStatus(activeVersion.status)}</Badge>}
              </div>

              {/* L-M-7 fix: заменён aria-pressed на role=tablist + role=tab + aria-selected.
                  Согласованность с LabPanel.jsx (там тоже role=tablist).
                  Keyboard-навигация: стрелки вправо/лево, Home, End. */}
              <div className="ltw-tab-bar ltw-tablist" role="tablist" aria-label={t('misc.ltw_redaktor_shablona')}>
                {EDITOR_TABS.map((tab) => {
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
                      onKeyDown={(e) => {
                        const idx = EDITOR_TABS.findIndex((t) => t.id === tab.id);
                        let nextIdx = null;
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
        existingTemplates={templates}
      />

      {/* UX-AUDIT-FIX14: ID datalist теперь уникальны per-instance (useId) */}
      <datalist id={analyteCatalogId}>
        {catalogAnalytes.map((analyte) => (
          <option key={analyte.code} value={analyte.code}>
            {analyte.name}
          </option>
        ))}
      </datalist>
      <datalist id={unitCatalogId}>
        {catalogUnits.map((unit) => (
          <option key={unit.code} value={unit.code}>
            {unit.symbol}
          </option>
        ))}
      </datalist>

      {/* L-H-1 fix: portal-mounted ConfirmDialog для destructive actions */}
      {confirmDialog}
    </div>
  );
}

LabTemplateWorkbench.propTypes = {
  templates: PropTypes.array.isRequired,
  selectedTemplate: PropTypes.object,
  onSelectTemplate: PropTypes.func.isRequired,
  onTemplatesChanged: PropTypes.func.isRequired,
  notify: PropTypes.func.isRequired
};
