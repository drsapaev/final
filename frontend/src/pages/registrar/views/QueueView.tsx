/**
 * Registrar Panel — Queue View.
 *
 * Decomposition step 6a: extracted from RegistrarPanel.jsx (lines 2447-2503).
 *
 * Wraps ModernQueueManager with a card header. Handles URL search params
 * for date, doctor, and search query.
 *
 * @param {Object} props
 * @param {Object} props.searchParams - URLSearchParams from useSearchParams
 * @param {Function} props.setSearchParams - setter for URL params
 * @param {Function} props.loadAppointments - reload appointments after queue update
 * @param {Function} props.getSpacing - theme spacing helper
 * @param {Function} props.getFontSize - theme font size helper
 * @param {Function} props.getColor - theme color helper
 * @param {string} props.language - UI language code
 * @param {string} props.theme - 'light' or 'dark'
 * @param {Array} props.doctors - doctors list for ModernQueueManager
 */
import React from 'react';
import { Card, CardHeader, CardContent } from '../../../components/ui/macos';
import { AnimatedTransition } from '../../../components/ui';
import ModernQueueManagerRaw from '../../../components/queue/ModernQueueManager';
const ModernQueueManager = ModernQueueManagerRaw as unknown as React.ComponentType<Record<string, unknown>>;
import { getLocalDateString } from '../../../utils/dateUtils';
import logger from '../../../utils/logger';
// i18n-unification: use unified useTranslation instead of getRegistrarTranslator
import { useTranslation } from '../../../i18n/useTranslation';

interface QueueViewProps {
  searchParams: URLSearchParams;
  setSearchParams: (params: URLSearchParams) => void;
  loadAppointments: () => void | Promise<void>;
  getSpacing: (key: string) => string;
  getFontSize: (key: string) => string;
  getColor: (key: string) => string;
  language: string;
  theme: string;
  doctors: unknown[];
}

const QueueView = React.memo(({
  searchParams,
  setSearchParams,
  loadAppointments,
  getSpacing,
  getFontSize,
  getColor,
  language,
  theme,
  doctors,
}: QueueViewProps) => {
  // UX Audit R-3.8: используем t() для локализации заголовка и подзаголовка.
  // i18n-unification: t() now routes flat keys to registrarPanel.* namespace.
  const { t: tI18n } = useTranslation();
  const t = ((key: string) => (tI18n as unknown as (k: string) => string)('registrarPanel.' + key)) as (key: string) => string;
  return (
    <AnimatedTransition type="fade" delay={100}>
      <Card variant="default" style={{ margin: `0 ${getSpacing('xl')} ${getSpacing('xl')} ${getSpacing('xl')}` }}>
        <CardHeader>
          <AnimatedTransition type="slide" direction="up" delay={200}>
            <h1 style={{
              margin: 0,
              fontSize: getFontSize('3xl'),
              fontWeight: 'var(--mac-font-weight-normal)',
              lineHeight: '1.25',
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('sm'),
              color: getColor('textPrimary'),
            }}>
              {t('tabs_queue')}
            </h1>
          </AnimatedTransition>
          <AnimatedTransition type="fade" delay={400}>
            <div style={{
              fontSize: getFontSize('lg'),
              opacity: 0.9,
              lineHeight: '1.5',
              color: getColor('textSecondary'),
            }}>
              {/* UX Audit R-3.8: subtitle локализован через t() */}
              {t('queue_subtitle')}
            </div>
          </AnimatedTransition>
        </CardHeader>

        <CardContent>
          <ModernQueueManager
            selectedDate={searchParams.get('date') || getLocalDateString()}
            selectedDoctor={searchParams.get('doctor') || ''}
            searchQuery={searchParams.get('q') || ''}
            onQueueUpdate={loadAppointments}
            onDateChange={(newDate: string) => {
              logger.info('RegistrarPanel received date change:', newDate);
              const newParams = new URLSearchParams(searchParams);
              newParams.set('date', newDate);
              setSearchParams(newParams);
            }}
            onDoctorChange={(newDoctorId: string) => {
              logger.info('RegistrarPanel received doctor change:', newDoctorId);
              const newParams = new URLSearchParams(searchParams);
              newParams.set('doctor', newDoctorId);
              setSearchParams(newParams);
            }}
            language={language}
            theme={theme}
            doctors={doctors as never}
          />
        </CardContent>
      </Card>
    </AnimatedTransition>
  );
});

QueueView.displayName = 'QueueView';

export default QueueView;
