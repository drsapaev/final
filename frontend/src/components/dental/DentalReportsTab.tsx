
/**
 * DentalReportsTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Отчёты" tab: saved visit protocols + ReportsAndAnalytics.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { BarChart3 } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

type TFunc = (key: string, options?: Record<string, unknown>) => string;

const ReportsAndAnalytics = ({ patients, diagnoses, prosthetics }: {
  patients?: unknown[];
  diagnoses?: unknown[];
  prosthetics?: unknown[];
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as TFunc;
  return (
    <Card padding="large">
      <div className="dental-flex-between-16">
        <div>
          <h3 className="dental-text-primary">{t('dental.dental_drt_analytics_title')}</h3>
          <p className="dental-text-desc dental-text-secondary">{t('dental.dental_drt_analytics_subtitle')}</p>
        </div>
        <BarChart3 size={24} className="dental-text-secondary" />
      </div>
      <div className="dental-grid-3 dental-gap-16 dental-mt-16">
        <Card padding="default">
          <div className="dental-text-desc dental-text-secondary">{t('dental.dental_drt_stat_patients')}</div>
          <div className="dental-text-value dental-text-primary">{patients?.length || 0}</div>
        </Card>
        <Card padding="default">
          <div className="dental-text-desc dental-text-secondary">{t('dental.dental_drt_stat_diagnoses')}</div>
          <div className="dental-text-value dental-text-primary">{diagnoses?.length || 0}</div>
        </Card>
        <Card padding="default">
          <div className="dental-text-desc dental-text-secondary">{t('dental.dental_drt_stat_prosthetics')}</div>
          <div className="dental-text-value dental-text-primary">{prosthetics?.length || 0}</div>
        </Card>
      </div>
    </Card>
  );
};

ReportsAndAnalytics.propTypes = {
  patients: PropTypes.array,
  diagnoses: PropTypes.array,
  prosthetics: PropTypes.array,
};

interface SavedVisitProtocol {
  visit_id: string | number;
  patient_name: string;
  saved_at: string;
  visitData?: { chiefComplaint?: string };
}

export function DentalReportsTab({
  savedVisitProtocols = [],
  onReopenProtocol,
  patients = [],
  diagnoses = [],
  prosthetics = [],
}: {
  savedVisitProtocols?: SavedVisitProtocol[];
  onReopenProtocol?: (protocol: SavedVisitProtocol) => void;
  patients?: unknown[];
  diagnoses?: unknown[];
  prosthetics?: unknown[];
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as TFunc;
  const protocols: SavedVisitProtocol[] = savedVisitProtocols;
  return (
    <div className="dental-flex-col dental-gap-24">
      {savedVisitProtocols.length > 0 && (
        <Card padding="large">
          <div className="dental-flex-between-16">
            <div>
              <h3 className="dental-text-primary">{t('dental.dental_drt_saved_title')}</h3>
              <p className="dental-text-desc dental-text-secondary">
                {t('dental.dental_drt_saved_subtitle')}
              </p>
            </div>
          </div>
          <div className="dental-grid-auto-fill-280">
            {protocols.map((protocol) => (
              <div key={protocol.visit_id} className="dental-protocol-card-flex">
                <div>
                  <div className="dental-text-primary">{protocol.patient_name}</div>
                  <div className="dental-text-desc dental-text-secondary">
                    {t('dental.dental_drt_visit_meta', { visitId: protocol.visit_id, date: new Date(protocol.saved_at).toLocaleString('ru-RU') })}
                  </div>
                </div>
                <div className="dental-text-value dental-text-primary">
                  {protocol.visitData?.chiefComplaint || t('dental.dental_drt_no_complaint')}
                </div>
                <Button
                  onClick={() => onReopenProtocol?.(protocol)}
                  className="dental-align-self-start">
                  {t('dental.dental_drt_btn_open')}
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
      <ReportsAndAnalytics patients={patients} diagnoses={diagnoses} prosthetics={prosthetics} />
    </div>
  );
}

DentalReportsTab.propTypes = {
  savedVisitProtocols: PropTypes.array,
  onReopenProtocol: PropTypes.func,
  patients: PropTypes.array,
  diagnoses: PropTypes.array,
  prosthetics: PropTypes.array,
};

export default DentalReportsTab;
