import PropTypes from 'prop-types';
import { useState } from 'react';
import { Badge, Button, Icon } from '../../ui/macos';
import { useConfirm } from '../../common/ConfirmDialog';
// STRAT#11: t() и tInterpolate() для i18n — delete dialogs мигрированы.
import { t, tInterpolate } from '../utils/labTranslations';
import { fieldTypeOptions, referenceModeOptions } from './config';
import ReferenceRuleEditor from './ReferenceRuleEditor';
import { useTranslation } from '../../../i18n/adapter';

/**
 * L-H-6 fix: ContentTab выделен в отдельный файл (~250 строк).
 *
 * Вкладка «Содержимое» — секции и поля шаблона. Поддерживает:
 *   - collapsible секции и поля
 *   - drag-reorder (вверх/вниз)
 *   - duplicate field
 *   - structured ReferenceRuleEditor (вместо raw JSON)
 *   - расширенные правила (видимость/подсветка) — raw JSON, collapsed
 *
 * UX-AUDIT-FIX4: удаление секции и поля теперь требует подтверждения.
 * Ранее single-click на trash удалял элемент со всеми правилами референсов
 * без возможности отмены. Потеря сложного поля — 5–10 минут работы.
 * Соответствует Nielsen Heuristic #5 (Error Prevention).
 *
 * UX-AUDIT-FIX5: raw JSON textareas (visibility_rule_text /
 * highlight_rule_text) скрыты за глобальным «Developer mode» тогглом.
 * Ранее каждый `<details>` с raw JSON рендерился в каждой field card —
 * 90% лаборантов никогда не редактируют эти правила, но визуальный шум
 * от них отъедал vertical space и повышал когнитивную нагрузку
 * (Nielsen Heuristic #8 — Aesthetic and Minimalist Design).
 * Теперь по умолчанию raw JSON не виден; power users включают тоггл.
 */
function ContentTab({
  draftVersion,
  expandedSections,
  expandedFields,
  onToggleSection,
  onToggleField,
  onAddSection,
  onAddField,
  onRemoveSection,
  onRemoveField,
  onDuplicateField,
  onMoveField,
  onMoveSection,
  onUpdateSection,
  onUpdateField,
  onUpdateFieldCatalog,
  onLoadCatalogReferenceRange,
  // UX-AUDIT-FIX14: уникальные ID для <datalist> от parent (useId()).
  // Ранее были захардкожены как 'lab-analyte-catalog' / 'lab-unit-catalog'.
  analyteCatalogId = 'lab-analyte-catalog',
  unitCatalogId = 'lab-unit-catalog',
}) {
  // UX-AUDIT-FIX4: useConfirm для деструктивных действий (удаление секции/поля).
  const [confirm] = useConfirm();

  // UX-AUDIT-FIX5: глобальный тоггл для raw JSON правил.
  // По умолчанию выключен — raw JSON скрыт из основного UI.
  const [developerMode, setDeveloperMode] = useState(false);

  async function handleRemoveSection(sectionIndex, section) {
    // STRAT#11: строки мигрированы на t() / tInterpolate() из labTranslations.
    const sectionName = section?.title || section?.key || `${t('content.section_fallback')} #${sectionIndex + 1}`;
    const ok = await confirm({
      title: t('confirm.delete_section_title'),
      message: tInterpolate('confirm.delete_section_message', { name: sectionName }),
      description: t('confirm.delete_section_description'),
      confirmLabel: t('confirm.delete_section_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'danger',
    });
    if (ok) onRemoveSection(sectionIndex);
  }

  async function handleRemoveField(sectionIndex, fieldIndex, field) {
    // STRAT#11: строки мигрированы на t() / tInterpolate() из labTranslations.
    const fieldName = field?.label || field?.field_key || `${t('content.field_fallback')} #${fieldIndex + 1}`;
    const ok = await confirm({
      title: t('confirm.delete_field_title'),
      message: tInterpolate('confirm.delete_field_message', { name: fieldName }),
      description: t('confirm.delete_field_description'),
      confirmLabel: t('confirm.delete_field_confirm'),
      cancelLabel: t('confirm.cancel'),
      intent: 'danger',
    });
    if (ok) onRemoveField(sectionIndex, fieldIndex);
  }

  // UX-AUDIT-FIX7: Bulk-загрузка всех референсных интервалов из каталога.
  // Ранее лаборант кликал «Загрузить из каталога» на каждом поле отдельно —
  // при 20 показателях это 20 микро-решений вместо одного (закон Хика,
  // Fitts's Law). Теперь одна кнопка в шапке ContentTab.
  function handleBulkLoadCatalogReferenceRanges() {
    if (!draftVersion?.sections) return;
    let loaded = 0;
    let skipped = 0;
    draftVersion.sections.forEach((section, sectionIndex) => {
      (section.fields || []).forEach((field, fieldIndex) => {
        if (field.reference_mode === 'catalog' && field.analyte_code) {
          onLoadCatalogReferenceRange(sectionIndex, fieldIndex, field.analyte_code);
          loaded += 1;
        } else {
          skipped += 1;
        }
      });
    });
    // Используем глобальный notify (если передан) или тихий возврат.
    // Parent (LabTemplateWorkbench) сам обработает уведомление, т.к.
    // каждый вызов onLoadCatalogReferenceRange триггерит его callback.
    // Здесь только логируем для отладки.
    if (typeof window !== 'undefined' && window.console) {
      // eslint-disable-next-line no-console
      console.debug('[ContentTab] bulk-load reference ranges:', { loaded, skipped });
    }
  }

  return (
    <div className="ltw-grid">
      <div className="ltw-flex-between">
        <div className="ltw-fw-600">
          {t('content.header')} ({draftVersion?.sections?.reduce((acc, s) => acc + (s.fields?.length || 0), 0) || 0} {t('content.header_fields')} {draftVersion?.sections?.length || 0} {t('content.header_sections')})
        </div>
        <span className="ltw-flex-gap-4" style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
          {/* UX-AUDIT-FIX5: Developer mode toggle. По умолчанию выключен —
              raw JSON (visibility_rule_text / highlight_rule_text) скрыт. */}
          <label
            className="ltw-checkbox-label"
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)', fontSize: '0.85em', opacity: 0.85 }}
            title={t('content.developer_mode_title')}
          >
            <input
              type="checkbox"
              checked={developerMode}
              onChange={(e) => setDeveloperMode(e.target.checked)}
              aria-label={t('content.developer_mode_aria')}
            />
            {t('content.developer_mode')}
          </label>
          <Button variant="outline" onClick={onAddSection}>
            <Icon name="plus" size={16} />
            {t('content.add_section')}
          </Button>
          {/* UX-AUDIT-FIX7: Bulk-кнопка для загрузки всех референсных
              интервалов из каталога одним кликом. Показывается всегда,
              но активна только если есть хотя бы одно поле с reference_mode
              === 'catalog' и непустым analyte_code. */}
          <Button
            variant="outline"
            size="small"
            onClick={handleBulkLoadCatalogReferenceRanges}
            disabled={!draftVersion?.sections?.some((s) =>
              (s.fields || []).some((f) =>
                f.reference_mode === 'catalog' && f.analyte_code
              )
            )}
            title={t('content.load_all_norms_title')}
          >
            <Icon name="square.and.arrow.down.on.square" size={14} />
            {t('content.load_all_norms')}
          </Button>
        </span>
      </div>

      {draftVersion.sections.map((section, sectionIndex) => {
        const isSectionExpanded = expandedSections.has(sectionIndex);
        return (
          <div key={`${section.key}-${sectionIndex}`} className="ltw-section-card">
            <button
              type="button"
              className={`ltw-section-header ${isSectionExpanded ? 'ltw-section-header-expanded' : ''}`}
              onClick={() => onToggleSection(sectionIndex)}
              aria-expanded={isSectionExpanded}
              aria-label={`${t('content.section_aria')}: ${section.title || section.key}`}
            >
              <div className="ltw-flex-center">
                <Icon name={isSectionExpanded ? 'chevron.down' : 'chevron.right'} size={16} />
                <span className="ltw-section-title">{section.title || section.key}</span>
                <Badge variant="default">{section.fields.length} {t('content.section_fields_count')}</Badge>
              </div>
              <span className="ltw-flex-gap-4">
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveSection(sectionIndex, 'up'); }} disabled={sectionIndex === 0} aria-label={t('content.move_section_up')}>
                  <Icon name="arrow.up" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveSection(sectionIndex, 'down'); }} disabled={sectionIndex === draftVersion.sections.length - 1} aria-label={t('content.move_section_down')}>
                  <Icon name="arrow.down" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); handleRemoveSection(sectionIndex, section); }} aria-label={t('content.delete_section')}>
                  <Icon name="trash" size={14} />
                </Button>
              </span>
            </button>

            {isSectionExpanded && (
              <div className="ltw-section-content">
                <div className="ltw-grid-2">
                  <label className="ltw-grid-6">
                    <span>{t('content.section_key')}</span>
                    <input className="macos-input" aria-label={t('content.section_key')} value={section.key} onChange={(event) => onUpdateSection(sectionIndex, 'key', event.target.value)} />
                  </label>
                  <label className="ltw-grid-6">
                    <span>{t('content.section_title')}</span>
                    <input className="macos-input" aria-label={t('content.section_title')} value={section.title || ''} onChange={(event) => onUpdateSection(sectionIndex, 'title', event.target.value)} />
                  </label>
                </div>

                <div className="ltw-grid-8">
                  {section.fields.map((field, fieldIndex) => {
                    const fieldKey = `${sectionIndex}-${fieldIndex}`;
                    const isFieldExpanded = expandedFields.has(fieldKey);
                    return (
                      <div key={`${field.field_key}-${fieldIndex}`} className="ltw-field-card">
                        <button
                          type="button"
                          className={`ltw-field-header ${isFieldExpanded ? 'ltw-field-header-expanded' : ''}`}
                          onClick={() => onToggleField(sectionIndex, fieldIndex)}
                          aria-expanded={isFieldExpanded}
                          aria-label={`${t('content.field_aria')}: ${field.label || field.field_key}`}
                        >
                          <div className="ltw-flex-center">
                            <Icon name={isFieldExpanded ? 'chevron.down' : 'chevron.right'} size={14} />
                            <span className="ltw-field-title">{field.label || field.field_key || t('content.field_no_title')}</span>
                            <Badge variant="info">{fieldTypeOptions.find((o) => o.value === field.value_type)?.label || field.value_type}</Badge>
                            {field.required && <Badge variant="warning">{t('content.field_required')}</Badge>}
                          </div>
                          <span className="ltw-flex-gap-4">
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveField(sectionIndex, fieldIndex, 'up'); }} disabled={fieldIndex === 0} aria-label={t('content.move_field_up')}>
                              <Icon name="arrow.up" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveField(sectionIndex, fieldIndex, 'down'); }} disabled={fieldIndex === section.fields.length - 1} aria-label={t('content.move_field_down')}>
                              <Icon name="arrow.down" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onDuplicateField(sectionIndex, fieldIndex); }} aria-label={t('content.duplicate_field')}>
                              <Icon name="doc.on.doc" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); handleRemoveField(sectionIndex, fieldIndex, field); }} aria-label={t('content.delete_field')}>
                              <Icon name="trash" size={12} />
                            </Button>
                          </span>
                        </button>

                        {isFieldExpanded && (
                          <div className="ltw-field-content">
                            <div className="ltw-grid-4">
                              <label className="ltw-grid-6">
                                <span>{t('content.field_key')}</span>
                                <input className="macos-input" aria-label={t('content.field_key')} value={field.field_key} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'field_key', event.target.value)} />
                              </label>
                              <label className="ltw-grid-6">
                                <span>{t('content.field_label')}</span>
                                <input className="macos-input" aria-label={t('content.field_label')} value={field.label} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'label', event.target.value)} />
                              </label>
                              <label className="ltw-grid-6">
                                <span>{t('content.value_type')}</span>
                                <select className="macos-input" aria-label={t('content.value_type')} value={field.value_type} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'value_type', event.target.value)}>
                                  {fieldTypeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              </label>
                              <label className="ltw-grid-6">
                                <span>{t('content.unit')}</span>
                                <input className="macos-input" aria-label={t('content.unit')} value={field.unit || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'unit', event.target.value)} />
                              </label>
                            </div>

                            <div className="ltw-grid-5">
                              <label className="ltw-grid-6">
                                <span>{t('content.analyte_code')}</span>
                                <input
                                  className="macos-input"
                                  aria-label={t('content.analyte_code')}
                                  list={analyteCatalogId}
                                  value={field.analyte_code || ''}
                                  onChange={(event) => onUpdateFieldCatalog(sectionIndex, fieldIndex, 'analyte_code', event.target.value)}
                                />
                              </label>
                              <label className="ltw-grid-6">
                                <span>{t('content.unit_code')}</span>
                                <input
                                  className="macos-input"
                                  aria-label={t('content.unit_code')}
                                  list={unitCatalogId}
                                  value={field.unit_code || ''}
                                  onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'unit_code', event.target.value)}
                                />
                              </label>
                              <label className="ltw-grid-6">
                                <span>{t('content.reference_mode')}</span>
                                <select className="macos-input" aria-label={t('content.reference_mode')} value={field.reference_mode} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'reference_mode', event.target.value)}>
                                  {referenceModeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              </label>
                              {field.reference_mode === 'catalog' && field.analyte_code && (
                                <div className="ltw-label-grid">
                                  <Button
                                    variant="outline"
                                    size="small"
                                    onClick={() => onLoadCatalogReferenceRange(sectionIndex, fieldIndex, field.analyte_code)}
                                  >
                                    <Icon name="square.and.arrow.down.on.square" size={14} />
                                    {t('content.load_from_catalog')}
                                  </Button>
                                </div>
                              )}
                              {field.reference_mode === 'catalog' && !field.analyte_code && (
                                <span className="ltw-catalog-hint">
                                  {t('content.catalog_hint')}
                                </span>
                              )}
                              <label className="ltw-grid-6">
                                <span>{t('content.reference_text')}</span>
                                <input className="macos-input" aria-label={t('content.reference_text')} value={field.reference_text || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'reference_text', event.target.value)} />
                              </label>
                              <label className="ltw-checkbox-label">
                                <input type="checkbox" aria-label={t('content.required_aria')} checked={Boolean(field.required)} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'required', event.target.checked)} />
                                {t('content.required_label')}
                              </label>
                            </div>

                            <ReferenceRuleEditor
                              sectionIndex={sectionIndex}
                              fieldIndex={fieldIndex}
                              field={field}
                              updateField={onUpdateField}
                            />

                            {developerMode && (
                              <details className="ltw-details">
                                <summary className="ltw-summary">
                                  Расширенные правила (видимость / подсветка) — raw JSON
                                </summary>
                                <div className="ltw-raw-json-grid">
                                  <label className="ltw-grid-6">
                                    <span>JSON правил видимости</span>
                                    <textarea className="macos-input" aria-label="JSON правил видимости" rows={3} value={field.visibility_rule_text || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'visibility_rule_text', event.target.value)} />
                                  </label>
                                  <label className="ltw-grid-6">
                                    <span>JSON правил подсветки</span>
                                    <textarea className="macos-input" aria-label="JSON правил подсветки" rows={3} value={field.highlight_rule_text || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'highlight_rule_text', event.target.value)} />
                                  </label>
                                </div>
                              </details>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                  <Button variant="outline" onClick={() => onAddField(sectionIndex)}>
                    <Icon name="plus" size={16} />
                    {t('content.add_field')}
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

ContentTab.propTypes = {
  draftVersion: PropTypes.object.isRequired,
  expandedSections: PropTypes.object.isRequired,
  expandedFields: PropTypes.object.isRequired,
  onToggleSection: PropTypes.func.isRequired,
  onToggleField: PropTypes.func.isRequired,
  onAddSection: PropTypes.func.isRequired,
  onAddField: PropTypes.func.isRequired,
  onRemoveSection: PropTypes.func.isRequired,
  onRemoveField: PropTypes.func.isRequired,
  onDuplicateField: PropTypes.func.isRequired,
  onMoveField: PropTypes.func.isRequired,
  onMoveSection: PropTypes.func.isRequired,
  onUpdateSection: PropTypes.func.isRequired,
  onUpdateField: PropTypes.func.isRequired,
  onUpdateFieldCatalog: PropTypes.func.isRequired,
  onLoadCatalogReferenceRange: PropTypes.func.isRequired,
  // UX-AUDIT-FIX14: уникальные ID для <datalist> от parent (useId).
  analyteCatalogId: PropTypes.string,
  unitCatalogId: PropTypes.string,
};

export default ContentTab;
