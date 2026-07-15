import logger from '../../utils/logger';
/**
 * DermaPhotosTab — R-15: extracted from DermatologistPanelUnified.
 * Renders the "Фото" tab: PhotoUploader + SkinAnalysis + PhotoComparison.
 */
import PropTypes from 'prop-types';
import { MacOSCard, MacOSEmptyState, Button } from '../ui/macos';
import { Camera } from 'lucide-react';
import PhotoUploader from './PhotoUploader';
import SkinAnalysis from './SkinAnalysis';
import PhotoComparison from './PhotoComparison';
import { useTranslation } from '../../i18n/adapter';

export function DermaPhotosTab({
  hasPatient,
  currentAppointment,
  selectedPatient,
  photoData,
  onPhotoUpdate,
  onGoToAppointments,
}) {
  if (!hasPatient) {
    return (
      <MacOSEmptyState
        icon={Camera}
        title="Выберите пациента"
        description="Откройте прием из очереди или списка записей для работы с фото"
        action={<Button variant="outline" onClick={onGoToAppointments} style={{ marginTop: 'var(--mac-spacing-4)' }}>Перейти к записям</Button>}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          Загрузка фото
        </h3>
        <PhotoUploader
          visitId={currentAppointment?.visit_id}
          patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
          onDataUpdate={onPhotoUpdate}
        />
      </MacOSCard>

      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          AI анализ кожи
        </h3>
        <SkinAnalysis
          photos={photoData}
          visitId={currentAppointment?.visit_id}
          patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
          onAnalysisComplete={(result) => {
            logger.info('AI анализ завершен:', result);
          }}
        />
      </MacOSCard>

      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          Сравнение «до» и «после»
        </h3>
        <PhotoComparison
          beforePhoto={photoData.before?.[0]}
          afterPhoto={photoData.after?.[0]}
          metadata={{ visitId: currentAppointment?.visit_id, patientId: currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id }}
        />
      </MacOSCard>
    </div>
  );
}

DermaPhotosTab.propTypes = {
  hasPatient: PropTypes.bool,
  currentAppointment: PropTypes.object,
  selectedPatient: PropTypes.object,
  photoData: PropTypes.object,
  onPhotoUpdate: PropTypes.func,
  onGoToAppointments: PropTypes.func,
};

export default DermaPhotosTab;
