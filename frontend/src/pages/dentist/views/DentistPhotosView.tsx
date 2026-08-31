import { Card } from '../../../components/ui/macos';
import type { SelectedPatient } from '../dentistContracts';
import { dentalCardKeyDown } from '../dentistCardA11y';

/**
 * PR-UI-15-6: the photos tab view — verbatim JSX of the former
 * DentistPanelUnified.renderPhotos.
 */
export default function DentistPhotosView({
  patients,
  onPhotoArchive,
  tI18n,
}: {
  patients: SelectedPatient[];
  onPhotoArchive: (patient: SelectedPatient | Record<string, unknown> | null) => void;
  tI18n: (key: string, params?: Record<string, unknown>) => string;
}) {
  return (
    <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_photos_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_photos_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_photos')}
          className="dental-card-btn"
          onClick={() => onPhotoArchive(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => dentalCardKeyDown(event, () => onPhotoArchive(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-warning dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_photos_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>);
}
