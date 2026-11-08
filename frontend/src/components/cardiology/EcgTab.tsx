
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

  const patientIdentity = (selectedPatient?.patient_id || (selectedPatient?.patient as Record<string, unknown> | undefined)?.id) as string | number | undefined;
  const visitIdentity = selectedPatient?.visit_id as string | number | undefined;
  // ECGVIEW-FE-002 / ECHO-FE-001 (audit 3886 round 20): remount the viewer
  // and the echo form when the patient/visit context changes, so no local
  // file list, preview or form state from patient A can survive into
  // patient B's tab. Both components additionally carry internal
  // owner-epoch guards for async work that is already in flight.
  const ownerKey = `${String(patientIdentity ?? 'none')}|${String(visitIdentity ?? 'none')}`;

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
        key={`ecg-viewer-${ownerKey}`}
        visitId={visitIdentity}
        patientId={patientIdentity}
        onDataUpdate={onDataUpdate}
      />
      <EchoForm
        key={`echo-form-${ownerKey}`}
        visitId={visitIdentity}
        patientId={patientIdentity}
        onDataUpdate={onDataUpdate}
      />
    </div>
  );
}


export default EcgTab;
