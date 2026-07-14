import PropTypes from 'prop-types';
import { Badge, Button, Icon } from '../../ui/macos';
import { fieldTypeOptions, referenceModeOptions } from './config';
import ReferenceRuleEditor from './ReferenceRuleEditor';

/**
 * L-H-6 fix: ContentTab выделен в отдельный файл (~250 строк).
 *
 * Вкладка «Содержимое» — секции и поля шаблона. Поддерживает:
 *   - collapsible секции и поля
 *   - drag-reorder (вверх/вниз)
 *   - duplicate field
 *   - structured ReferenceRuleEditor (вместо raw JSON)
 *   - расширенные правила (видимость/подсветка) — raw JSON, collapsed
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
}) {
  return (
    <div className="ltw-grid">
      <div className="ltw-flex-between">
        <div className="ltw-fw-600">
          Секции и показатели ({draftVersion?.sections?.reduce((acc, s) => acc + (s.fields?.length || 0), 0) || 0} показателей в {draftVersion?.sections?.length || 0} секц.)
        </div>
        <Button variant="outline" onClick={onAddSection}>
          <Icon name="plus" size={16} />
          Добавить секцию
        </Button>
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
              aria-label={`Секция: ${section.title || section.key}`}
            >
              <div className="ltw-flex-center">
                <Icon name={isSectionExpanded ? 'chevron.down' : 'chevron.right'} size={16} />
                <span className="ltw-section-title">{section.title || section.key}</span>
                <Badge variant="default">{section.fields.length} полей</Badge>
              </div>
              <span className="ltw-flex-gap-4">
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveSection(sectionIndex, 'up'); }} disabled={sectionIndex === 0} aria-label="Переместить секцию вверх">
                  <Icon name="arrow.up" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveSection(sectionIndex, 'down'); }} disabled={sectionIndex === draftVersion.sections.length - 1} aria-label="Переместить секцию вниз">
                  <Icon name="arrow.down" size={14} />
                </Button>
                <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onRemoveSection(sectionIndex); }} aria-label="Удалить секцию">
                  <Icon name="trash" size={14} />
                </Button>
              </span>
            </button>

            {isSectionExpanded && (
              <div className="ltw-section-content">
                <div className="ltw-grid-2">
                  <label className="ltw-grid-6">
                    <span>Ключ секции</span>
                    <input className="macos-input" aria-label="Ключ секции" value={section.key} onChange={(event) => onUpdateSection(sectionIndex, 'key', event.target.value)} />
                  </label>
                  <label className="ltw-grid-6">
                    <span>Заголовок секции</span>
                    <input className="macos-input" aria-label="Заголовок секции" value={section.title || ''} onChange={(event) => onUpdateSection(sectionIndex, 'title', event.target.value)} />
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
                          aria-label={`Поле: ${field.label || field.field_key}`}
                        >
                          <div className="ltw-flex-center">
                            <Icon name={isFieldExpanded ? 'chevron.down' : 'chevron.right'} size={14} />
                            <span className="ltw-field-title">{field.label || field.field_key || '(без названия)'}</span>
                            <Badge variant="info">{fieldTypeOptions.find((o) => o.value === field.value_type)?.label || field.value_type}</Badge>
                            {field.required && <Badge variant="warning">обязательное</Badge>}
                          </div>
                          <span className="ltw-flex-gap-4">
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveField(sectionIndex, fieldIndex, 'up'); }} disabled={fieldIndex === 0} aria-label="Переместить поле вверх">
                              <Icon name="arrow.up" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onMoveField(sectionIndex, fieldIndex, 'down'); }} disabled={fieldIndex === section.fields.length - 1} aria-label="Переместить поле вниз">
                              <Icon name="arrow.down" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onDuplicateField(sectionIndex, fieldIndex); }} aria-label="Дублировать поле">
                              <Icon name="doc.on.doc" size={12} />
                            </Button>
                            <Button variant="ghost" size="small" onClick={(e) => { e.stopPropagation(); onRemoveField(sectionIndex, fieldIndex); }} aria-label="Удалить поле">
                              <Icon name="trash" size={12} />
                            </Button>
                          </span>
                        </button>

                        {isFieldExpanded && (
                          <div className="ltw-field-content">
                            <div className="ltw-grid-4">
                              <label className="ltw-grid-6">
                                <span>Ключ поля</span>
                                <input className="macos-input" aria-label="Ключ поля" value={field.field_key} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'field_key', event.target.value)} />
                              </label>
                              <label className="ltw-grid-6">
                                <span>Название поля</span>
                                <input className="macos-input" aria-label="Название поля" value={field.label} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'label', event.target.value)} />
                              </label>
                              <label className="ltw-grid-6">
                                <span>Тип значения</span>
                                <select className="macos-input" aria-label="Тип значения" value={field.value_type} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'value_type', event.target.value)}>
                                  {fieldTypeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                  ))}
                                </select>
                              </label>
                              <label className="ltw-grid-6">
                                <span>Единица измерения</span>
                                <input className="macos-input" aria-label="Единица измерения" value={field.unit || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'unit', event.target.value)} />
                              </label>
                            </div>

                            <div className="ltw-grid-5">
                              <label className="ltw-grid-6">
                                <span>Код анализируемого показателя</span>
                                <input
                                  className="macos-input"
                                  aria-label="Код анализируемого показателя"
                                  list="lab-analyte-catalog"
                                  value={field.analyte_code || ''}
                                  onChange={(event) => onUpdateFieldCatalog(sectionIndex, fieldIndex, 'analyte_code', event.target.value)}
                                />
                              </label>
                              <label className="ltw-grid-6">
                                <span>Код единицы измерения</span>
                                <input
                                  className="macos-input"
                                  aria-label="Код единицы измерения"
                                  list="lab-unit-catalog"
                                  value={field.unit_code || ''}
                                  onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'unit_code', event.target.value)}
                                />
                              </label>
                              <label className="ltw-grid-6">
                                <span>Источник нормы</span>
                                <select className="macos-input" aria-label="Источник нормы" value={field.reference_mode} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'reference_mode', event.target.value)}>
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
                                    Загрузить из каталога
                                  </Button>
                                </div>
                              )}
                              {field.reference_mode === 'catalog' && !field.analyte_code && (
                                <span className="ltw-catalog-hint">
                                  Укажите код аналита для загрузки нормы из каталога
                                </span>
                              )}
                              <label className="ltw-grid-6">
                                <span>Текст нормы</span>
                                <input className="macos-input" aria-label="Текст нормы" value={field.reference_text || ''} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'reference_text', event.target.value)} />
                              </label>
                              <label className="ltw-checkbox-label">
                                <input type="checkbox" aria-label="Обязательное поле" checked={Boolean(field.required)} onChange={(event) => onUpdateField(sectionIndex, fieldIndex, 'required', event.target.checked)} />
                                Обязательное
                              </label>
                            </div>

                            <ReferenceRuleEditor
                              sectionIndex={sectionIndex}
                              fieldIndex={fieldIndex}
                              field={field}
                              updateField={onUpdateField}
                            />

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
                          </div>
                        )}
                      </div>
                    );
                  })}
                  <Button variant="outline" onClick={() => onAddField(sectionIndex)}>
                    <Icon name="plus" size={16} />
                    Добавить показатель
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
};

export default ContentTab;
