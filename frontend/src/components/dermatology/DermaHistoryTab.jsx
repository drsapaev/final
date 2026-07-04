/**
 * DermaHistoryTab — R-15: extracted from DermatologistPanelUnified.
 * Renders the "История" tab: skin examinations + cosmetic procedures history.
 */
import PropTypes from 'prop-types';
import { Calendar } from 'lucide-react';
import { MacOSCard, Badge } from '../ui/macos';

export function DermaHistoryTab({
  skinExaminations = [],
  cosmeticProcedures = [],
  getSpacing,
}) {
  return (
    <div className="derma-flex-col-24">
      <MacOSCard className="derma-p-8">
        <h3 className="derma-flex-center">
          <Calendar size={20} className="derma-icon-mr derma-text-secondary" />
          История приемов и процедур
        </h3>

        <div className="derma-grid-auto-350-24">
          {/* Skin examinations history */}
          <div>
            <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: 'var(--mac-text-primary)' }}>
              Осмотры кожи ({skinExaminations.length})
            </h4>
            {skinExaminations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {skinExaminations.map((exam) => (
                  <div key={exam.id} style={{ padding: '12px', border: '1px solid var(--mac-border)', borderRadius: '8px', background: 'var(--mac-surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <Badge variant="info">{exam.exam_date}</Badge>
                      <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                        {exam.skin_type} - {exam.skin_condition}
                      </span>
                    </div>
                    {exam.diagnosis && <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>{exam.diagnosis}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
                Нет осмотров
              </div>
            )}
          </div>

          {/* Cosmetic procedures history */}
          <div>
            <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: 'var(--mac-text-primary)' }}>
              Косметологические процедуры ({cosmeticProcedures.length})
            </h4>
            {cosmeticProcedures.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {cosmeticProcedures.map((proc) => (
                  <div key={proc.id} style={{ padding: '12px', border: '1px solid var(--mac-border)', borderRadius: '8px', background: 'var(--mac-surface)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <Badge variant="info">{proc.procedure_date}</Badge>
                      <span style={{ fontSize: '13px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>
                        {Number(proc.total_cost || 0).toLocaleString()} UZS
                      </span>
                    </div>
                    {proc.procedure_type && <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>{proc.procedure_type} - {proc.area_treated}</div>}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--mac-text-secondary)' }}>
                Нет процедур
              </div>
            )}
          </div>
        </div>
      </MacOSCard>
    </div>
  );
}

DermaHistoryTab.propTypes = {
  skinExaminations: PropTypes.array,
  cosmeticProcedures: PropTypes.array,
  getSpacing: PropTypes.func,
};

export default DermaHistoryTab;
