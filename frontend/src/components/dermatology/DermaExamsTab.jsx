/**
 * DermaExamsTab — R-15: extracted from DermatologistPanelUnified.
 *
 * Renders the "Осмотр кожи" (skin) and "Косметология" (cosmetic) tabs.
 * Each tab shows a form + history list.
 */
import PropTypes from 'prop-types';
import { MacOSCard, Button, Input, Select, Textarea, Badge } from '../ui/macos';
import { useTranslation } from '../../i18n/adapter';

export function DermaExamsTab({
  activeTab,
  // Skin examination
  skinExamination,
  setSkinExamination,
  showSkinForm,
  skinExaminations = [],
  onSkinSubmit,
  onOpenSkinForm,
  onCancelSkinForm,
  // Cosmetic procedures
  cosmeticProcedure,
  setCosmeticProcedure,
  showCosmeticForm,
  cosmeticProcedures = [],
  onCosmeticSubmit,
  onOpenCosmeticForm,
  onCancelCosmeticForm,
  // Theme
  getColor,
  getFontSize,
  getSpacing,
}) {
  if (activeTab === 'skin') {
    return (
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: getSpacing('xl') }}>
        <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--mac-spacing-5)' }}>
            <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
              Осмотры кожи
            </h3>
            <Button onClick={onOpenSkinForm}>Новый осмотр</Button>
          </div>

          {showSkinForm && (
            <form onSubmit={onSkinSubmit} style={{ marginBottom: 'var(--mac-spacing-6)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
                <div>
                  <label className="derma-form-label">Дата осмотра</label>
                  <Input type="date" aria-label="Дата осмотра" value={skinExamination.exam_date || ''} onChange={(e) => setSkinExamination({ ...skinExamination, exam_date: e.target.value })} required />
                </div>
                <div>
                  <label className="derma-form-label">Тип кожи</label>
                  <Select aria-label="Тип кожи" value={skinExamination.skin_type || ''} onChange={(e) => setSkinExamination({ ...skinExamination, skin_type: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="normal">Нормальный</option>
                    <option value="dry">Сухой</option>
                    <option value="oily">Жирный</option>
                    <option value="combination">Комбинированный</option>
                    <option value="sensitive">Чувствительный</option>
                  </Select>
                </div>
                <div>
                  <label className="derma-form-label">Состояние кожи</label>
                  <Input aria-label="Состояние кожи" value={skinExamination.skin_condition || ''} onChange={(e) => setSkinExamination({ ...skinExamination, skin_condition: e.target.value })} placeholder="Напр. акне, экзема" />
                </div>
                <div>
                  <label className="derma-form-label">Поражения</label>
                  <Input aria-label="Поражения" value={skinExamination.lesions || ''} onChange={(e) => setSkinExamination({ ...skinExamination, lesions: e.target.value })} placeholder="Напр. папулы, везикулы" />
                </div>
                <div>
                  <label className="derma-form-label">Распространение</label>
                  <Input aria-label="Распространение" value={skinExamination.distribution || ''} onChange={(e) => setSkinExamination({ ...skinExamination, distribution: e.target.value })} placeholder="Напр. лицо, шея" />
                </div>
                <div>
                  <label className="derma-form-label">Симптомы</label>
                  <Input aria-label="Симптомы" value={skinExamination.symptoms || ''} onChange={(e) => setSkinExamination({ ...skinExamination, symptoms: e.target.value })} placeholder="Напр. зуд, жжение" />
                </div>
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">Диагноз</label>
                <Textarea aria-label="Диагноз" value={skinExamination.diagnosis || ''} onChange={(e) => setSkinExamination({ ...skinExamination, diagnosis: e.target.value })} rows={2} />
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">План лечения</label>
                <Textarea aria-label="План лечения" value={skinExamination.treatment_plan || ''} onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })} rows={3} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--mac-spacing-4)' }}>
                <Button type="button" variant="outline" onClick={onCancelSkinForm}>{t('common.cancel')}</Button>
                <Button type="submit">Сохранить осмотр</Button>
              </div>
            </form>
          )}

          {skinExaminations.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
              {skinExaminations.map((exam) => (
                <div key={exam.id} style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-2)' }}>
                    <Badge variant="info">{exam.exam_date}</Badge>
                    {exam.skin_type && <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>Тип кожи: {exam.skin_type}</span>}
                  </div>
                  {exam.skin_condition && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Состояние: {exam.skin_condition}</div>}
                  {exam.lesions && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Поражения: {exam.lesions}</div>}
                  {exam.diagnosis && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Диагноз: {exam.diagnosis}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--mac-text-secondary)' }}>
              Нет данных осмотров
            </div>
          )}
        </MacOSCard>
      </div>
    );
  }

  if (activeTab === 'cosmetic') {
    return (
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: getSpacing('xl') }}>
        <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--mac-spacing-5)' }}>
            <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
              Косметологические процедуры
            </h3>
            <Button onClick={onOpenCosmeticForm}>Новая процедура</Button>
          </div>

          {showCosmeticForm && (
            <form onSubmit={onCosmeticSubmit} style={{ marginBottom: 'var(--mac-spacing-6)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
                <div>
                  <label className="derma-form-label">Дата процедуры</label>
                  <Input type="date" aria-label="Дата процедуры" value={cosmeticProcedure.procedure_date || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_date: e.target.value })} required />
                </div>
                <div>
                  <label className="derma-form-label">Тип процедуры</label>
                  <Input aria-label="Тип процедуры" value={cosmeticProcedure.procedure_type || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_type: e.target.value })} placeholder="Напр. мезотерапия" />
                </div>
                <div>
                  <label className="derma-form-label">Область</label>
                  <Input aria-label="Область процедуры" value={cosmeticProcedure.area_treated || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, area_treated: e.target.value })} placeholder="Напр. лицо, шея" />
                </div>
                <div>
                  <label className="derma-form-label">Продукты</label>
                  <Input aria-label="Продукты" value={cosmeticProcedure.products_used || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, products_used: e.target.value })} placeholder="Напр. гиалуроновая кислота" />
                </div>
                <div>
                  <label className="derma-form-label">Стоимость (UZS)</label>
                  <Input type="number" aria-label="Стоимость" value={cosmeticProcedure.total_cost || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, total_cost: e.target.value })} placeholder="0" />
                </div>
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">Результаты</label>
                <Textarea aria-label="Результаты" value={cosmeticProcedure.results || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, results: e.target.value })} rows={2} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--mac-spacing-4)' }}>
                <Button type="button" variant="outline" onClick={onCancelCosmeticForm}>{t('common.cancel')}</Button>
                <Button type="submit">Сохранить процедуру</Button>
              </div>
            </form>
          )}

          {cosmeticProcedures.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
              {cosmeticProcedures.map((proc) => (
                <div key={proc.id} style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-2)' }}>
                    <Badge variant="info">{proc.procedure_date}</Badge>
                    <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                      {Number(proc.total_cost || 0).toLocaleString()} UZS
                    </span>
                  </div>
                  {proc.procedure_type && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Тип: {proc.procedure_type}</div>}
                  {proc.area_treated && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Область: {proc.area_treated}</div>}
                  {proc.products_used && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>Продукты: {proc.products_used}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--mac-text-secondary)' }}>
              Нет данных процедур
            </div>
          )}
        </MacOSCard>
      </div>
    );
  }

  return null;
}

DermaExamsTab.propTypes = {
  activeTab: PropTypes.string.isRequired,
  skinExamination: PropTypes.object,
  setSkinExamination: PropTypes.func,
  showSkinForm: PropTypes.bool,
  skinExaminations: PropTypes.array,
  onSkinSubmit: PropTypes.func,
  onOpenSkinForm: PropTypes.func,
  onCancelSkinForm: PropTypes.func,
  cosmeticProcedure: PropTypes.object,
  setCosmeticProcedure: PropTypes.func,
  showCosmeticForm: PropTypes.bool,
  cosmeticProcedures: PropTypes.array,
  onCosmeticSubmit: PropTypes.func,
  onOpenCosmeticForm: PropTypes.func,
  onCancelCosmeticForm: PropTypes.func,
  getColor: PropTypes.func,
  getFontSize: PropTypes.func,
  getSpacing: PropTypes.func,
};

export default DermaExamsTab;
