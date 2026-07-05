/**
 * DentalPatientsTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Пациенты" tab: patient cards with action buttons.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { Scissors, FileText, Eye } from 'lucide-react';
// P0 fix: 'Tooth' is not exported by lucide-react. Use Stethoscope as alias (matches DentistPanelUnified.jsx:42).
import { Stethoscope as Tooth } from 'lucide-react';

export function DentalPatientsTab({
  patients = [],
  onSelectPatient,
  onDentalChart,
  onTreatment,
  onProsthetic,
}) {
  if (patients.length === 0) {
    return (
      <Card padding="lg">
        <div className="dental-text-center dental-p-48 dental-text-secondary">
          Нет пациентов
        </div>
      </Card>
    );
  }

  return (
    <div className="dental-flex-col dental-gap-16">
      {patients.map((patient) => (
        <Card key={patient.id || patient.patient_id} padding="md">
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
                size="sm"
                variant="outline"
                aria-label={`Просмотр пациента ${patient.name || patient.id}`}
                onClick={() => onSelectPatient(patient)}
                title="Просмотр"
                className="dental-p-8px">
                <Eye aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                aria-label={`Схема зубов ${patient.name || patient.id}`}
                onClick={() => onDentalChart(patient)}
                title="Схема зубов"
                className="dental-p-8px">
                <Tooth aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                aria-label={`Лечение ${patient.name || patient.id}`}
                onClick={() => onTreatment(patient)}
                title="Лечение"
                className="dental-p-8px">
                <Scissors aria-hidden="true" className="dental-icon-16" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                aria-label={`Протезирование ${patient.name || patient.id}`}
                onClick={() => onProsthetic(patient)}
                title="Протезирование"
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
