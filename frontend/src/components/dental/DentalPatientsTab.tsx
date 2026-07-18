
/**
 * DentalPatientsTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Пациенты" tab: patient cards with action buttons.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { Scissors, FileText, Eye } from 'lucide-react';
// P0 fix: 'Tooth' is not exported by lucide-react. Use Stethoscope as alias (matches DentistPanelUnified.jsx:42).
import { Stethoscope as Tooth } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

export function DentalPatientsTab({
  patients = [],
  onSelectPatient,
  onDentalChart,
  onTreatment,
  onProsthetic,
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  if (patients.length === 0) {
    return (
      <Card padding="large">
        <div className="dental-text-center dental-p-48 dental-text-secondary">
          {t('dental.dental_dpt_empty')}
        </div>
      </Card>
    );
  }

  return (
    <div className="dental-flex-col dental-gap-16">
      {patients.map((patient) => (
        <Card key={patient.id || patient.patient_id} padding="default">
          <div className="dental-flex-between-16">
            <div className="dental-flex dental-gap-12 dental-items-center">
              <div>
                <div className="dental-text-primary dental-font-medium">
                  {patient.name || patient.patient_name || '—'}
                </div>
                {patient.phone && (
                  <div className="dental-text-desc dental-text-secondary">
                    {patient.phone}
                  </div>
                )}
              </div>
            </div>
            <div className="dental-flex dental-gap-8">
              <Button
                size="small"
                variant="outline"
                aria-label={t('dental.dental_dpt_aria_view', { name: patient.name || patient.id })}
                onClick={() => onSelectPatient(patient)}
                title={t('dental.dental_dpt_title_view')}
                className="dental-p-8px">
                <Eye aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="small"
                variant="outline"
                aria-label={t('dental.dental_dpt_aria_chart', { name: patient.name || patient.id })}
                onClick={() => onDentalChart(patient)}
                title={t('dental.dental_dpt_title_chart')}
                className="dental-p-8px">
                <Tooth aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="small"
                variant="outline"
                aria-label={t('dental.dental_dpt_aria_treatment', { name: patient.name || patient.id })}
                onClick={() => onTreatment(patient)}
                title={t('dental.dental_dpt_title_treatment')}
                className="dental-p-8px">
                <Scissors aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="small"
                variant="outline"
                aria-label={t('dental.dental_dpt_aria_prosthetic', { name: patient.name || patient.id })}
                onClick={() => onProsthetic(patient)}
                title={t('dental.dental_dpt_title_prosthetic')}
                className="dental-p-8px">
                <FileText aria-hidden="true" className="dental-icon-16" />
              </Button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

DentalPatientsTab.propTypes = {
  patients: PropTypes.array,
  onSelectPatient: PropTypes.func,
  onDentalChart: PropTypes.func,
  onTreatment: PropTypes.func,
  onProsthetic: PropTypes.func,
};

export default DentalPatientsTab;
