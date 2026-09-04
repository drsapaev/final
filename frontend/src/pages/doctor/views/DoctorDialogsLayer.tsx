import AIChatWidget from '../../../components/ai/AIChatWidget';
import ScheduleNextModal from '../../../components/common/ScheduleNextModal';
import RoleNotificationCenter from '../../../components/notifications/RoleNotificationCenter';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * PR-UI-15-2: the modal/widget surfaces (ScheduleNextModal + AI chat widget
 * + role notification center) extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent —
 * see cashier views/CashierDialogsLayer).
 */
export default function DoctorDialogsLayer({
  scheduleNextModalOpen,
  scheduleNextModalPatient,
  onScheduleNextClose,
  onScheduleNextSuccess,
  doctorSpecialty,
}: {
  scheduleNextModalOpen: boolean;
  scheduleNextModalPatient: Record<string, unknown> | null;
  onScheduleNextClose: () => void;
  onScheduleNextSuccess: (result?: unknown, formData?: Record<string, unknown>) => void;
  doctorSpecialty: string;
}) {
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

  return (
    <>
      {/* Модальное окно Schedule Next */}
      {scheduleNextModalOpen &&
      <ScheduleNextModal
        isOpen={scheduleNextModalOpen}
        onClose={onScheduleNextClose}
        onSuccess={onScheduleNextSuccess}
        patient={scheduleNextModalPatient ?? undefined}
        theme={{ isDark, getColor, getSpacing, getFontSize }} />

      }

      {/* AI Chat Widget */}
      <AIChatWidget
        contextType="general"
        specialty={doctorSpecialty}
        useWebSocket={false}
        position="bottom-right" />

      <RoleNotificationCenter userRole="doctor" />
    </>
  );
}
