import type { CSSProperties } from 'react';
import { Calendar, CheckCircle, Clock, User } from 'lucide-react';

import { Card, AnimatedTransition } from '../../../components/ui/macos';
import type { DoctorStyles } from '../useDoctorStyles';

/**
 * PR-UI-15-2: the dashboard stats grid extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 */
export default function DoctorDashboardTab({
  patientsCount,
  appointmentStats,
  styles,
}: {
  patientsCount: number;
  appointmentStats: { scheduled: number; inProgress: number; completed: number };
  styles: DoctorStyles;
}) {
  const {
    dashboardGridStyle, statCardStyle, statCardHoverStyle,
    primaryColor, successColor, warningColor, accentColor, getColor, getShadow,
  } = styles;

  return (
    <AnimatedTransition type="fade" delay={100}>
      <div>
        {/* Статистика */}
        <div style={dashboardGridStyle}>
          <AnimatedTransition type="scale" delay={200}>
            <Card
              style={statCardStyle}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                Object.assign(e.currentTarget.style, statCardHoverStyle);
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = getShadow('lg');
              }}>

              <div className="doctor-stat-row">
                <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) } as CSSProperties}>
                  <User size={24} />
                </div>
                <div>
                  <div className="doctor-stat-num">
                    {patientsCount}
                  </div>
                  <div className="doctor-stat-label">
                    Активных пациентов
                  </div>
                </div>
              </div>
            </Card>
          </AnimatedTransition>

          <AnimatedTransition type="scale" delay={300}>
            <Card
              style={statCardStyle}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                Object.assign(e.currentTarget.style, statCardHoverStyle);
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = getShadow('lg');
              }}>

              <div className="doctor-stat-row">
                <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': successColor, '--doctor-gradient-to': getColor('success', 600) } as CSSProperties}>
                  <Calendar size={24} />
                </div>
                <div>
                  <div className="doctor-stat-num">
                    {appointmentStats.scheduled}
                  </div>
                  <div className="doctor-stat-label">
                    Записей на сегодня
                  </div>
                </div>
              </div>
            </Card>
          </AnimatedTransition>

          <AnimatedTransition type="scale" delay={400}>
            <Card
              style={statCardStyle}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                Object.assign(e.currentTarget.style, statCardHoverStyle);
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = getShadow('lg');
              }}>

              <div className="doctor-stat-row">
                <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': warningColor, '--doctor-gradient-to': getColor('warning', 600) } as CSSProperties}>
                  <Clock size={24} />
                </div>
                <div>
                  <div className="doctor-stat-num">
                    {appointmentStats.inProgress}
                  </div>
                  <div className="doctor-stat-label">
                    В процессе
                  </div>
                </div>
              </div>
            </Card>
          </AnimatedTransition>

          <AnimatedTransition type="scale" delay={500}>
            <Card
              style={statCardStyle}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                Object.assign(e.currentTarget.style, statCardHoverStyle);
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.transform = 'translateY(0) scale(1)';
                e.currentTarget.style.boxShadow = getShadow('lg');
              }}>

              <div className="doctor-stat-row">
                <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': accentColor, '--doctor-gradient-to': getColor('info', 600) } as CSSProperties}>
                  <CheckCircle size={24} />
                </div>
                <div>
                  <div className="doctor-stat-num">
                    {appointmentStats.completed}
                  </div>
                  <div className="doctor-stat-label">
                    Завершено сегодня
                  </div>
                </div>
              </div>
            </Card>
          </AnimatedTransition>
        </div>
      </div>
    </AnimatedTransition>
  );
}
