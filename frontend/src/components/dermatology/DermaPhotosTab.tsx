
import logger from '../../utils/logger';
/**
 * DermaPhotosTab — R-15: extracted from DermatologistPanelUnified.
 * Renders the "Фото" tab: PhotoUploader + SkinAnalysis + PhotoComparison.
 */
import PropTypes from 'prop-types';
import { MacOSCard, MacOSEmptyState, Button } from '../ui/macos';
import React from 'react';
import { Camera } from 'lucide-react';
import PhotoUploader from './PhotoUploader';
import SkinAnalysis from './SkinAnalysis';
import PhotoComparison from './PhotoComparison';
import { useTranslation } from '../../i18n/useTranslation';

type TFunc = (key: string, options?: Record<string, unknown>) => string;

interface PhotoData {
  before?: Array<{ url?: string } | string>;
  after?: Array<{ url?: string } | string>;
}

interface CurrentAppointment {
  visit_id?: number | string;
  patient_id?: number;
  patient?: { id?: number };
}

interface SelectedPatient {
  patient_id?: number;
  patient?: { id?: number };
}

export function DermaPhotosTab({
  hasPatient,
  currentAppointment,
  selectedPatient,
  photoData,
  onPhotoUpdate,
  onGoToAppointments,
}: {
  hasPatient?: boolean;
  currentAppointment?: CurrentAppointment | null;
  selectedPatient?: SelectedPatient | null;
  photoData: PhotoData;
  onPhotoUpdate?: (data: unknown) => void;
  onGoToAppointments?: () => void;
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as TFunc;
  if (!hasPatient) {
    return (
      <MacOSEmptyState
        icon={Camera}
        title={t('derma.derma_photos_select_patient_title')}
        description={t('derma.derma_photos_select_patient_desc')}
        action={<Button variant="outline" onClick={onGoToAppointments} style={{ marginTop: 'var(--mac-spacing-4)' }}>{t('derma.derma_photos_go_to_appointments')}</Button>}
      />
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          {t('derma.derma_photos_upload_title')}
        </h3>
        <PhotoUploader
          visitId={currentAppointment?.visit_id}
          patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
          onDataUpdate={onPhotoUpdate}
        />
      </MacOSCard>

      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          {t('derma.derma_photos_ai_title')}
        </h3>
        <SkinAnalysis
          photos={photoData}
          visitId={currentAppointment?.visit_id}
          patientId={currentAppointment?.patient_id || selectedPatient?.patient_id || selectedPatient?.patient?.id}
          onAnalysisComplete={(result: unknown) => {
            logger.info('AI анализ завершен:', result);
          }}
        />
      </MacOSCard>

      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 'var(--mac-spacing-5)', color: 'var(--mac-text-primary)' }}>
          {t('derma.derma_photos_compare_title')}
        </h3>
        <PhotoComparison
          beforePhoto={typeof photoData.before?.[0] === 'string' ? photoData.before[0] as string : (photoData.before?.[0] as { url?: string } | undefined)?.url ?? null}
          afterPhoto={typeof photoData.after?.[0] === 'string' ? photoData.after[0] as string : (photoData.after?.[0] as { url?: string } | undefined)?.url ?? null}
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
