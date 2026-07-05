/**
 * PatientPickupView - Read-only view for registrar/cashier to issue lab results
 * Shows patient info and lab results without clinical data
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { labReportingApi } from '../api/labReporting';
import auth from '../stores/auth';
import logger from '../utils/logger';
import { openPrintableWindow } from '../utils/printWindow';
import FamilyRelationsCard from '../components/patient/FamilyRelationsCard';
import {
  AppEmpty, AppError, AppLoading, Button,
} from '../components/ui/macos';

// Get user role for role-based UI
const getUserRole = () => {
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  return String(profile?.role || profile?.role_name || '').toLowerCase();
};

export default function PatientPickupView() {
  const { patientId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const userRole = getUserRole();

  // Get view mode and specialty from URL params or derive from role
  const viewParam = searchParams.get('view') || '';
  const specialtyParam = searchParams.get('specialty') || '';

  // Determine what sections to show based on role and params
  const isDoctor = ['doctor', 'cardio', 'derma', 'dentist'].includes(userRole) || viewParam === 'doctor' || specialtyParam;
  const isLabView = userRole === 'lab' || viewParam === 'lab';
  const isCashierView = userRole === 'cashier' || viewParam === 'payments';

  // Get page title based on role/view
  const getPageTitle = () => {
    if (specialtyParam === 'cardio') return 'История визитов — Кардиология';
    if (specialtyParam === 'derma') return 'История визитов — Дерматология';
    if (specialtyParam === 'dental') return 'История визитов — Стоматология';
    if (isDoctor) return 'История визитов пациента';
    if (isLabView) return 'Лабораторные анализы';
    if (isCashierView) return 'История визитов и оплат';
    return 'Выдача результатов';
  };

  const [patient, setPatient] = useState(null);
  const [labResults, setLabResults] = useState([]);
  const [visits, setVisits] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load patient, lab data, and visit history
  const loadData = useCallback(async () => {
    if (!patientId) return;

    setIsLoading(true);
    setError(null);

    try {
      // Load patient info
      const patientRes = await api.get(`/patients/${patientId}`);
      setPatient(patientRes.data);

      // Load lab results
      try {
        const labReportInstances = await labReportingApi.listInstances({ patient_id: patientId, limit: 100 });
        setLabResults(labReportInstances || []);
      } catch {
        setLabResults([]);
      }

      // Load visit history
      try {
        const visitsRes = await api.get('/registrar/visits', { params: { patient_id: patientId } });
        setVisits(visitsRes.data || []);
      } catch {
        setVisits([]);
      }
    } catch (err) {
      logger.error('Error loading patient:', err);
      setError('Не удалось загрузить данные пациента');
    } finally {
      setIsLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleDateString('ru-RU');
    } catch {
      return dateStr;
    }
  };

  // Get status badge for lab results
  const getStatusBadge = (status) => {
    const config = {
      done: { icon: '🟢', label: 'Готов', bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      in_progress: { icon: '🟡', label: 'В процессе', bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      ordered: { icon: '⚪', label: 'Заказан', bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)' },
      canceled: { icon: '🔴', label: 'Отменён', bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' }
    };
    const normalizedStatus = String(status || '').toUpperCase();
    if (['FINALIZED', 'PRINTED'].includes(normalizedStatus)) return config.done;
    if (['IN_PROGRESS', 'READY'].includes(normalizedStatus)) return config.in_progress;
    if (normalizedStatus === 'DRAFT') return config.ordered;
    return config[status] || config.ordered;
  };

  const hasLabReportAction = (labResult, action) => {
    const actions = Array.isArray(labResult?.available_actions) ? labResult.available_actions : [];
    if (actions.includes(action)) return true;
    if (action === 'print') return labResult?.can_print === true;
    return false;
  };

  const getLabDisplayName = (labResult) =>
    labResult?.template?.name || labResult?.service_name || labResult?.name || labResult?.test_name || `Lab #${labResult?.id}`;

  const getLabDisplayCode = (labResult) =>
    labResult?.template?.code || labResult?.service_code || labResult?.test_code || '-';

  // Get status badge for visits
  const getVisitStatusBadge = (status) => {
    const config = {
      scheduled: { icon: '📅', label: 'Запланирован', bg: 'var(--mac-accent-bg)', color: 'var(--mac-accent)' },
      in_queue: { icon: '⏳', label: 'В очереди', bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      in_progress: { icon: '🟡', label: 'На приёме', bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      completed: { icon: '🟢', label: 'Завершён', bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      paid: { icon: '💳', label: 'Оплачено', bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      cancelled: { icon: '🔴', label: 'Отменён', bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' },
      no_show: { icon: '❌', label: 'Неявка', bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' }
    };
    return config[status] || { icon: '⚪', label: status || 'Неизвестно', bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)' };
  };

  // Handle print
  const handlePrint = () => {
    const visitsHtml = visits.length
      ? visits.map((visit) => `
        <tr>
          <td>${formatDate(visit.visit_date || visit.date)}</td>
          <td>${visit.doctor_name || visit.doctor || '—'}</td>
          <td>${getVisitStatusBadge(visit.status).label}</td>
        </tr>
      `).join('')
      : '<tr><td colspan="3">Записи не найдены</td></tr>';

    const labHtml = labResults.length
      ? labResults.map((result) => `
        <tr>
          <td>${getLabDisplayName(result)}</td>
          <td>${result.value || '—'}</td>
          <td>${getStatusBadge(result.status).label}</td>
        </tr>
      `).join('')
      : '<tr><td colspan="3">Результаты не найдены</td></tr>';

    openPrintableWindow({
      features: 'width=900,height=700',
      html: `
      <!doctype html>
      <html lang="ru">
        <head>
          <title>Выдача результатов пациента</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 24px; color: #111827; }
            h1 { margin: 0 0 12px; font-size: 24px; }
            h2 { margin: 24px 0 12px; font-size: 18px; }
            .muted { color: #6b7280; margin-bottom: 16px; }
            .meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 20px; }
            .meta div { border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; }
            th { background: #f3f4f6; }
          </style>
        </head>
        <body>
          <h1>${getPageTitle()}</h1>
          <div class="muted">Печатная форма для выдачи данных пациенту</div>
          <div class="meta">
            <div><strong>Пациент:</strong> ${patient?.full_name || patient?.name || '—'}</div>
            <div><strong>ID:</strong> ${patientId || '—'}</div>
            <div><strong>Дата рождения:</strong> ${formatDate(patient?.birth_date || patient?.birthDate)}</div>
            <div><strong>Телефон:</strong> ${patient?.phone || '—'}</div>
          </div>

          <h2>История визитов</h2>
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Врач</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>${visitsHtml}</tbody>
          </table>

          <h2>Лабораторные результаты</h2>
          <table>
            <thead>
              <tr>
                <th>Исследование</th>
                <th>Результат</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>${labHtml}</tbody>
          </table>
        </body>
      </html>
    `
    });
  };

  // Handle download PDF
  const handleDownloadPDF = async (labResult) => {
    try {
      const blob = await labReportingApi.downloadPdf(labResult.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `lab_result_${labResult.id}.pdf`;
      link.click();
    } catch {
      alert('PDF пока недоступен');
    }
  };

  // Styles
  const styles = {
    container: {
      minHeight: '100vh',
      background: 'var(--mac-gradient-window, linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%))',
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      marginBottom: '24px'
    },
    backButton: {
      background: 'var(--mac-bg-secondary, white)',
      border: '1px solid var(--mac-border, #e2e8f0)',
      borderRadius: '8px',
      padding: '8px 16px',
      cursor: 'pointer',
      fontSize: '14px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    title: {
      fontSize: '24px',
      fontWeight: '600',
      color: 'var(--mac-text-primary, #1e293b)',
      margin: 0
    },
    card: {
      background: 'var(--mac-bg-primary, white)',
      borderRadius: '16px',
      boxShadow: 'var(--mac-shadow-md)',
      padding: '24px',
      marginBottom: '24px'
    },
    patientInfo: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: '16px'
    },
    infoItem: {
      display: 'flex',
      flexDirection: 'column',
      gap: '4px'
    },
    infoLabel: {
      fontSize: '12px',
      color: 'var(--mac-text-tertiary, #64748b)',
      textTransform: 'uppercase',
      letterSpacing: '0.5px'
    },
    infoValue: {
      fontSize: '16px',
      fontWeight: '500',
      color: 'var(--mac-text-primary, #1e293b)'
    },
    sectionTitle: {
      fontSize: '18px',
      fontWeight: '600',
      color: 'var(--mac-text-primary, #1e293b)',
      marginBottom: '16px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    },
    labList: {
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    },
    labItem: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '16px',
      background: 'var(--mac-bg-secondary, #f8fafc)',
      borderRadius: '12px',
      border: '1px solid var(--mac-border, #e2e8f0)'
    },
    labInfo: {
      flex: 1
    },
    labName: {
      fontSize: '15px',
      fontWeight: '500',
      color: 'var(--mac-text-primary, #1e293b)',
      marginBottom: '4px'
    },
    labDate: {
      fontSize: '13px',
      color: 'var(--mac-text-secondary, #64748b)'
    },
    statusBadge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '6px 12px',
      borderRadius: '20px',
      fontSize: '13px',
      fontWeight: '500'
    },
    actions: {
      display: 'flex',
      gap: '8px',
      marginLeft: '16px'
    },
    actionButton: {
      background: 'var(--mac-bg-primary, white)',
      border: '1px solid var(--mac-border, #e2e8f0)',
      borderRadius: '8px',
      padding: '8px 12px',
      cursor: 'pointer',
      fontSize: '13px',
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      transition: 'all 0.2s ease'
    },
    loading: {
      textAlign: 'center',
      padding: '60px',
      color: 'var(--mac-text-tertiary, #64748b)'
    },
    error: {
      textAlign: 'center',
      padding: '60px',
      color: 'var(--mac-error)'
    },
    emptyState: {
      textAlign: 'center',
      padding: '40px',
      color: 'var(--mac-text-tertiary, #64748b)'
    },
    visuallyHidden: {
      position: 'absolute',
      width: '1px',
      height: '1px',
      padding: 0,
      margin: '-1px',
      overflow: 'hidden',
      clip: 'rect(0, 0, 0, 0)',
      whiteSpace: 'nowrap',
      border: 0
    }
  };

  if (isLoading) {
    return (
      <div style={styles.container}>
        <AppLoading
          title="Загрузка данных пациента..."
          description="Получаем карточку, анализы и историю визитов."
          ariaLabel="Загружаем данные пациента"
          style={styles.loading}
        />
            </div>);

  }

  if (error) {
    return (
      <div style={styles.container}>
        <AppError
          title="Не удалось загрузить данные пациента"
          description={error}
          action={
            <Button
              type="button"
              variant="outline"
              size="small"
              onClick={loadData}
              disabled={isLoading}
              loading={isLoading}
              aria-label="Повторить загрузку данных пациента">
              Повторить
            </Button>
          }
          style={styles.error}
        />
            </div>);

  }

  return (
    <section style={styles.container} aria-labelledby="patient-pickup-title">
            {/* Header */}
            <div style={styles.header}>
                <button
                  type="button"
                  style={styles.backButton}
                  onClick={() => navigate(-1)}
                  aria-label="Вернуться на предыдущую страницу">
                    ← Назад
                </button>
                <h1 id="patient-pickup-title" style={styles.title}>{getPageTitle()}</h1>
            </div>

            {/* Patient Info Card */}
            <div style={styles.card}>
                <h2 style={styles.sectionTitle}>
                    👤 Информация о пациенте
                </h2>
                <div style={styles.patientInfo}>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>ФИО</span>
                        <span style={styles.infoValue}>
                            {patient?.last_name} {patient?.first_name} {patient?.middle_name || ''}
                        </span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>Дата рождения</span>
                        <span style={styles.infoValue}>{formatDate(patient?.birth_date)}</span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>Телефон</span>
                        <span style={styles.infoValue}>{patient?.phone || '—'}</span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>ID пациента</span>
                        <span style={styles.infoValue}>#{patient?.id}</span>
                    </div>
                </div>
            </div>

            {/* Family Relations Card - hide for lab and cashier views */}
            {patient && !isLabView && !isCashierView &&
      <FamilyRelationsCard
        patientId={patient.id}
        patientName={`${patient.last_name} ${patient.first_name}`}
        canEdit={['admin', 'registrar', 'receptionist'].includes(userRole)} />

      }

            {/* Lab Results Card - Show for lab view and registrar/admin, hide for cashier-only and doctor-only views */}
            {(isLabView || !isCashierView && !isDoctor) &&
      <div style={styles.card}>
                    <h2 style={styles.sectionTitle}>
                        🧪 Результаты анализов
                    </h2>

                    {labResults.length === 0 ?
        <AppEmpty
          title="Нет результатов анализов"
          description="Для этого пациента пока нет лабораторных результатов для выдачи."
          style={styles.emptyState}
        /> :

        <div style={styles.labList}>
                            {labResults.map((lab) => {
            const status = getStatusBadge(lab.status);
            const canPrintLabReport = hasLabReportAction(lab, 'print');
            return (
              <div key={lab.id} style={styles.labItem}>
                                        <div style={styles.labInfo}>
                                            <div style={styles.labName}>
                                                {getLabDisplayName(lab)}
                                            </div>
                                            <div style={styles.labDate}>
                                                Код: {getLabDisplayCode(lab)} • Заказ #{lab.id}
                                            </div>
                                        </div>

                                        <div
                  aria-label={`Статус анализа: ${status.label}`}
                  style={{
                    ...styles.statusBadge,
                    background: status.bg,
                    color: status.color
                  }}>
                  
                                            {status.icon} {status.label}
                                        </div>

                                        {canPrintLabReport &&
                <div style={styles.actions}>
                  <button
                    type="button"
                    style={styles.actionButton}
                    onClick={() => handlePrint(lab)}
                    aria-label={`Печать анализа ${getLabDisplayName(lab)}`}
                    title="Печать">
                    
                                                        🖨️ Печать
                                                    </button>
                  <button
                    type="button"
                    style={styles.actionButton}
                    onClick={() => handleDownloadPDF(lab)}
                    aria-label={`Скачать PDF анализа ${getLabDisplayName(lab)}`}
                    title="Скачать PDF">
                    
                                                        📄 PDF
                                                    </button>
                                            </div>
                }
                                    </div>);

          })}
                        </div>
        }
                </div>
      }

            {/* Visit History Card - Show for doctor, cashier, and registrar views, hide for lab-only */}
            {!isLabView &&
      <div style={styles.card}>
                    <h2 style={styles.sectionTitle}>
                        {isCashierView ? '💳 История визитов и оплат' : '📋 История визитов'}
                    </h2>

                    {visits.length === 0 ?
        <AppEmpty
          title="Нет истории визитов"
          description="Для этого пациента пока нет визитов, доступных в этом представлении."
          style={styles.emptyState}
        /> :

        <div className="admin-table-wrapper" style={{ overflowX: 'auto' }} aria-label="История визитов пациента">
                            <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: '14px'
          }}>
                                <caption style={styles.visuallyHidden}>История визитов пациента</caption>
                                <thead>
                                    <tr style={{
                background: 'var(--mac-bg-tertiary, #f1f5f9)',
                borderBottom: '2px solid var(--mac-separator, #e2e8f0)'
              }}>
                                        <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', color: 'var(--mac-text-secondary)' }}>Дата</th>
                                        <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', color: 'var(--mac-text-secondary)' }}>№ Визита</th>
                                        <th style={{ padding: '12px', textAlign: 'left', fontWeight: '600', color: 'var(--mac-text-secondary)' }}>Услуги</th>
                                        <th style={{ padding: '12px', textAlign: 'right', fontWeight: '600', color: 'var(--mac-text-secondary)' }}>Сумма</th>
                                        <th style={{ padding: '12px', textAlign: 'center', fontWeight: '600', color: 'var(--mac-text-secondary)' }}>Статус</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {visits.map((visit, idx) => {
                const visitStatus = getVisitStatusBadge(visit.status);
                const services = visit.services || [];
                // Если services — массив строк, просто объединяем
                const servicesText = services.length > 0 ?
                typeof services[0] === 'string' ?
                services.join(', ') :
                services.map((s) => s.name || s).join(', ') :
                '—';
                // Считаем сумму из visit или из services
                const totalAmount = visit.total_amount || services.reduce((sum, s) =>
                sum + (parseFloat(typeof s === 'object' ? s.price : 0) || 0) * ((typeof s === 'object' ? s.qty : 1) || 1), 0);

                return (
                  <tr key={visit.id} style={{
                    borderBottom: '1px solid var(--mac-separator, #e2e8f0)',
                    background: idx % 2 === 0 ? 'transparent' : 'var(--mac-bg-secondary, #fafafa)'
                  }}>
                                                <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                                                    {formatDate(visit.visit_date || visit.created_at)}
                                                    {visit.visit_time && <span style={{ color: 'var(--mac-text-tertiary)', marginLeft: '8px' }}>{visit.visit_time}</span>}
                                                </td>
                                                <td style={{ padding: '12px', fontWeight: '500' }}>
                                                    #{visit.id}
                                                </td>
                                                <td style={{ padding: '12px', maxWidth: '300px' }}>
                                                    {servicesText}
                                                </td>
                                                <td style={{ padding: '12px', textAlign: 'right', fontWeight: '600', whiteSpace: 'nowrap' }}>
                                                    {totalAmount > 0 ? `${totalAmount.toLocaleString('ru-RU')} сум` : '—'}
                                                </td>
                                                <td style={{ padding: '12px', textAlign: 'center' }}>
                                                    <span
                                                      aria-label={`Статус визита: ${visitStatus.label}`}
                                                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '4px 10px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: '500',
                        background: visitStatus.bg,
                        color: visitStatus.color
                      }}>
                                                        {visitStatus.icon} {visitStatus.label}
                                                    </span>
                                                </td>
                                            </tr>);

              })}
                                </tbody>
                            </table>
                        </div>
        }
                </div>
      }
        </section>);

}
