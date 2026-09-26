/** Clinical cosmetic-procedure form shown from the active visit only. */
import React from 'react';
import { Card, Button, Input, Textarea } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

interface CosmeticProcedureForm {
  patient_id: string;
  visit_id: string;
  procedure_date: string;
  procedure_type: string;
  area_treated: string;
  products_used: string;
  results: string;
  follow_up: string;
}

interface DermaExamsTabProps {
  cosmeticProcedure: CosmeticProcedureForm;
  setCosmeticProcedure: (next: CosmeticProcedureForm) => void;
  showCosmeticForm: boolean;
  onCosmeticSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
  onOpenCosmeticForm: () => void;
  onCancelCosmeticForm: () => void;
}

export function DermaExamsTab({
  cosmeticProcedure,
  setCosmeticProcedure,
  showCosmeticForm,
  onCosmeticSubmit,
  onOpenCosmeticForm,
  onCancelCosmeticForm,
}: DermaExamsTabProps) {
  const { t } = useTranslation();

  return (
    <Card className="derma-p-8">
      <div className="derma-flex-between-top">
        <h3>{t('derma.derma_exams_cosmetic_title')}</h3>
        {!showCosmeticForm && (
          <Button type="button" onClick={onOpenCosmeticForm}>
            {t('derma.derma_exams_cosmetic_new')}
          </Button>
        )}
      </div>

      {showCosmeticForm && (
        <form onSubmit={onCosmeticSubmit} className="derma-mt-24">
          <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
            <div>
              <label className="derma-form-label" htmlFor="derma-procedure-date">
                {t('derma.derma_exams_cosmetic_date')}
              </label>
              <Input
                id="derma-procedure-date"
                type="date"
                value={cosmeticProcedure.procedure_date}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCosmeticProcedure({
                  ...cosmeticProcedure,
                  procedure_date: e.target.value,
                })}
                required
              />
            </div>
            <div>
              <label className="derma-form-label" htmlFor="derma-procedure-type">
                {t('derma.derma_exams_cosmetic_type')}
              </label>
              <Input
                id="derma-procedure-type"
                value={cosmeticProcedure.procedure_type}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCosmeticProcedure({
                  ...cosmeticProcedure,
                  procedure_type: e.target.value,
                })}
                placeholder={t('derma.derma_exams_ph_meso')}
                required
              />
            </div>
            <div>
              <label className="derma-form-label" htmlFor="derma-procedure-area">
                {t('derma.derma_exams_cosmetic_area')}
              </label>
              <Input
                id="derma-procedure-area"
                value={cosmeticProcedure.area_treated}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCosmeticProcedure({
                  ...cosmeticProcedure,
                  area_treated: e.target.value,
                })}
                placeholder={t('derma.derma_exams_ph_face_neck')}
              />
            </div>
            <div>
              <label className="derma-form-label" htmlFor="derma-procedure-products">
                {t('derma.derma_exams_cosmetic_products')}
              </label>
              <Input
                id="derma-procedure-products"
                value={cosmeticProcedure.products_used}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCosmeticProcedure({
                  ...cosmeticProcedure,
                  products_used: e.target.value,
                })}
                placeholder={t('derma.derma_exams_ph_hyaluronic')}
              />
            </div>
          </div>

          <div className="derma-mt-16">
            <label className="derma-form-label" htmlFor="derma-procedure-results">
              {t('derma.derma_exams_cosmetic_results')}
            </label>
            <Textarea
              id="derma-procedure-results"
              value={cosmeticProcedure.results}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setCosmeticProcedure({
                ...cosmeticProcedure,
                results: e.target.value,
              })}
              rows={2}
            />
          </div>

          <div className="derma-flex-gap-8 derma-mt-16" style={{ justifyContent: 'flex-end' }}>
            <Button type="button" variant="outline" onClick={onCancelCosmeticForm}>
              {t('common.cancel')}
            </Button>
            <Button type="submit">{t('derma.derma_exams_cosmetic_save')}</Button>
          </div>
        </form>
      )}
    </Card>
  );
}

export default DermaExamsTab;
