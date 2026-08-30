/**
 * Registrar Panel — record preview dialog (view component).
 *
 * PR-UI-13-3: extracted verbatim from RegistrarPanel.tsx JSX — the
 * ModernDialog composition for the 10-field record preview grid. Pure
 * presentation view: state lives in useRegistrarDialogs (recordPreviewDialog
 * slice); this component renders it and delegates actions.
 *
 * Naming: *View composition (not *Dialog.tsx) — the modal IMPLEMENTATION is
 * ModernDialog (already counted by the modalFilesOutsideKit ratchet); this
 * file composes it. Inline styles from the original JSX moved to
 * registrar.css classes (same values — zero visual delta).
 */
import ModernDialog from '../../../components/dialogs/ModernDialog';
import { normalizePatientGender, formatPreviewList } from '../registrarHelpers';
import type { Appointment } from '../../../types/domain/clinic';

interface RecordPreviewDialogProps {
  isOpen: boolean;
  row: Appointment | null;
  onClose: () => void;
  onEdit: (row: Appointment) => void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const RecordPreviewDialog = ({ isOpen, row, onClose, onEdit, tI18n }: RecordPreviewDialogProps) => (
  <ModernDialog
    isOpen={isOpen}
    onClose={onClose}
    title={tI18n('registrarPanel.rp_preview_title')}
    maxWidth="36rem"
    dialogStyle={{
      backgroundColor: 'var(--mac-bg-primary)'
    }}
    actions={[
      {
        label: tI18n('registrarPanel.rp_preview_close'),
        variant: 'secondary',
        onClick: onClose
      },
      {
        label: tI18n('registrarPanel.rp_preview_edit'),
        variant: 'primary',
        onClick: () => {
          if (row) onEdit(row);
        }
      }
    ]}>
    {row && (
      <div className="registrar-grid-gap-md registrar-preview-grid">
        {[
          [tI18n('registrarPanel.rp_field_patient'), row.patient_fio || row.patient_name],
          [tI18n('registrarPanel.rp_field_phone'), row.patient_phone || row.phone],
          [tI18n('registrarPanel.rp_field_birth_year'), row.patient_birth_year || row.birth_year],
          [tI18n('registrarPanel.rp_field_gender'), normalizePatientGender(row as unknown as Parameters<typeof normalizePatientGender>[0] as Record<string, unknown>)],
          [tI18n('registrarPanel.rp_field_department'), (row as Record<string, unknown>).queue_name || row.department || row.specialty],
          [tI18n('registrarPanel.rp_field_services'), formatPreviewList(row.services || row.service_details)],
          [tI18n('registrarPanel.rp_field_queue'), formatPreviewList(row.queue_numbers)],
          [tI18n('registrarPanel.rp_field_status'), row.status || row.canonical_status],
          [tI18n('registrarPanel.rp_field_payment'), row.payment_status || row.payment_type],
          [tI18n('registrarPanel.rp_field_amount'), row.cost]
        ].filter(([, value]) => value !== null && value !== undefined && value !== '').map(([label, value]) => (
          <div
            key={String(label)}
            className="registrar-surface registrar-preview-row">
            <span className="registrar-preview-label">{String(label)}</span>
            <span className="registrar-preview-value">
              {String(value)}
            </span>
          </div>
        ))}
      </div>
    )}
  </ModernDialog>
);

export default RecordPreviewDialog;
