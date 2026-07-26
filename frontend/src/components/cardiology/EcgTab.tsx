
/**
 * EcgTab — R-15 (UX audit): extracted from CardiologistPanelUnified.
 *
 * Renders the "ЭКГ" tab content:
 *   1. "Добавить ЭКГ" button
 *   2. ECGViewer (file upload, parsing, AI analysis)
 *   3. EchoForm (echocardiography results)
 *
 * All state stays in the parent. This is a presentational wrapper.
 */

import PropTypes from 'prop-types';
import { Plus } from 'lucide-react';
import { Button } from '../ui/macos';
import ECGViewer from './ECGViewer';
import React from 'react';
import EchoForm from './EchoForm';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * @param {Object} props
 * @param {Object} props.selectedPatient - Currently selected patient
 * @param {Function} props.onAddEcg - Open the ECG add flow
 * @param {Function} props.onDataUpdate - Reload patient data after ECG/Echo changes
 * @param {Function} props.getSpacing - Theme spacing getter
 */
export function EcgTab({
  selectedPatient,
  onAddEcg,
  onDataUpdate,
  getSpacing,
}: {
  selectedPatient: Record<string, unknown> | null;
  onAddEcg: () => void;
  onDataUpdate: () => void;
  getSpacing: (key: string) => string;
}) {
  if (!selectedPatient) {
    return null;
  }

  return (
    <div style={{
      width: '100%',
      maxWidth: 'none',
      overflow: 'visible',
      display: 'flex',
      flexDirection: 'column',
      gap: getSpacing('xl'),
    }}>
      <div className="flex justify-end">
        <Button onClick={onAddEcg}>
          <Plus size={16} className="cardio-icon-mr" /> Добавить ЭКГ
        </Button>
      </div>
      <ECGViewer
        visitId={selectedPatient?.visit_id as string | number | undefined}
        patientId={(selectedPatient?.patient_id || (selectedPatient?.patient as Record<string, unknown> | undefined)?.id) as string | number | undefined}
        onDataUpdate={onDataUpdate}
      />
      <EchoForm
        visitId={selectedPatient?.visit_id as string | number | undefined}
        patientId={(selectedPatient?.patient_id || (selectedPatient?.patient as Record<string, unknown> | undefined)?.id) as string | number | null | undefined}
        onDataUpdate={onDataUpdate}
      />
    </div>
  );
}

EcgTab.propTypes = {
  selectedPatient: PropTypes.object,
  onAddEcg: PropTypes.func.isRequired,
  onDataUpdate: PropTypes.func.isRequired,
  getSpacing: PropTypes.func.isRequired,
};

export default EcgTab;
