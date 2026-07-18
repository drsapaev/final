
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
import ECGViewerRaw from './ECGViewer';
import React from 'react';
const ECGViewer = ECGViewerRaw as unknown as React.ComponentType<Record<string, unknown>>;
import EchoFormRaw from './EchoForm';
const EchoForm = EchoFormRaw as unknown as React.ComponentType<Record<string, unknown>>;
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
        visitId={selectedPatient?.visit_id}
        patientId={selectedPatient?.patient_id || selectedPatient?.patient?.id}
        onDataUpdate={onDataUpdate}
      />
      <EchoForm
        visitId={selectedPatient?.visit_id}
        patientId={selectedPatient?.patient_id || selectedPatient?.patient?.id}
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
