/**
 * DentalReportsTab — R-15: extracted from DentistPanelUnified.
 * Renders the "Отчёты" tab: saved visit protocols + ReportsAndAnalytics.
 */
import PropTypes from 'prop-types';
import { Card, Button } from '../ui/macos';
import { BarChart3 } from 'lucide-react';
import { useTranslation } from '../../i18n/adapter';

const ReportsAndAnalytics = ({ patients, diagnoses, prosthetics }) => (
  <Card padding="lg">
    <div className="dental-flex-between-16">
      <div>
        <h3 className="dental-text-primary">Отчёты и аналитика</h3>
        <p className="dental-text-desc dental-text-secondary">Статистика по приемам, диагнозам и процедурам</p>
      </div>
      <BarChart3 size={24} className="dental-text-secondary" />
    </div>
    <div className="dental-grid-3 dental-gap-16 dental-mt-16">
      <Card padding="md">
        <div className="dental-text-desc dental-text-secondary">Всего пациентов</div>
        <div className="dental-text-value dental-text-primary">{patients?.length || 0}</div>
      </Card>
      <Card padding="md">
        <div className="dental-text-desc dental-text-secondary">Диагнозов</div>
        <div className="dental-text-value dental-text-primary">{diagnoses?.length || 0}</div>
      </Card>
      <Card padding="md">
        <div className="dental-text-desc dental-text-secondary">Протезов</div>
        <div className="dental-text-value dental-text-primary">{prosthetics?.length || 0}</div>
      </Card>
    </div>
  </Card>
);

ReportsAndAnalytics.propTypes = {
  patients: PropTypes.array,
  diagnoses: PropTypes.array,
  prosthetics: PropTypes.array,
};

export function DentalReportsTab({
  savedVisitProtocols = [],
  onReopenProtocol,
  patients = [],
  diagnoses = [],
  prosthetics = [],
}) {
  return (
    <div className="dental-flex-col dental-gap-24">
      {savedVisitProtocols.length > 0 && (
        <Card padding="lg">
          <div className="dental-flex-between-16">
            <div>
              <h3 className="dental-text-primary">Сохранённые протоколы визитов</h3>
              <p className="dental-text-desc dental-text-secondary">
                Последние протоколы доступны для повторного открытия без ручной пересборки
              </p>
            </div>
          </div>
          <div className="dental-grid-auto-fill-280">
            {savedVisitProtocols.map((protocol) => (
              <div key={protocol.visit_id} className="dental-protocol-card-flex">
                <div>
                  <div className="dental-text-primary">{protocol.patient_name}</div>
                  <div className="dental-text-desc dental-text-secondary">
                    Визит #{protocol.visit_id} - {new Date(protocol.saved_at).toLocaleString('ru-RU')}
                  </div>
                </div>
                <div className="dental-text-value dental-text-primary">
                  {protocol.visitData?.chiefComplaint || 'Жалоба не указана'}
                </div>
                <Button
                  onClick={() => onReopenProtocol(protocol)}
                  className="dental-align-self-start">
                  Открыть протокол
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
