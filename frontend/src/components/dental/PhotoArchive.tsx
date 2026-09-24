import { useTranslation } from '../../i18n/useTranslation';
import { Alert, Button } from '../ui/macos';

interface PhotoArchiveProps {
  patientId: string | number;
  patientName: string;
  initialData?: unknown;
  onSave?: (data: unknown) => Promise<void> | void;
  onClose?: () => void;
}

/**
 * The previous archive kept uploads as browser-local data URLs and presented
 * them as if they had been saved. Keep the entry point explicit and read-only
 * until the protected dental media API is connected.
 */
const PhotoArchive = ({ patientName, onClose }: PhotoArchiveProps) => {
  const { t } = useTranslation();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dental-photo-archive-title">
      <section className="w-full max-w-xl rounded-lg bg-white p-6 shadow-xl">
        <h2 id="dental-photo-archive-title" className="mb-4 text-xl font-semibold">
          {t('dental.dental_pa_title', { name: patientName })}
        </h2>
        <Alert
          type="warning"
          title={t('dental.dental_panel_photo_archive_unavailable_title')}
          description={t('dental.dental_pa_unavailable')} />
        <div className="mt-5 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            {t('dental.dental_pa_aria_close')}
          </Button>
        </div>
      </section>
    </div>
  );
};

export default PhotoArchive;
