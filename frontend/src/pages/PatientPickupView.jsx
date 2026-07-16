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
import { notify } from '../services/notify.js';
import { useTranslation } from '../i18n/useTranslation';

// Get user role for role-based UI
const getUserRole = () => {
  const st = auth.getState();
  const profile = st.profile || st.user || {};
  return String(profile?.role || profile?.role_name || '').toLowerCase();
};

export default function PatientPickupView() {
  const { t } = useTranslation();
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
    if (specialtyParam === 'cardio') return t('misc.ppu_title_cardio');
    if (specialtyParam === 'derma') return t('misc.ppu_title_derma');
    if (specialtyParam === 'dental') return t('misc.ppu_title_dental');
    if (isDoctor) return t('misc.ppu_title_patient');
    if (isLabView) return t('misc.ppu_title_lab');
    if (isCashierView) return t('misc.ppu_title_cashier');
    return t('misc.ppu_title_default');
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
      setError(t('misc.ppu_load_error'));
    } finally {
      setIsLoading(false);
    }
  }, [patientId, t]);

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
      done: { icon: '🟢', label: t('misc.ppu_status_done'), bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      in_progress: { icon: '🟡', label: t('misc.ppu_status_in_progress'), bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      ordered: { icon: '⚪', label: t('misc.ppu_status_ordered'), bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)' },
      canceled: { icon: '🔴', label: t('misc.ppu_status_canceled'), bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' }
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
      scheduled: { icon: '📅', label: t('misc.ppu_visit_status_scheduled'), bg: 'var(--mac-accent-bg)', color: 'var(--mac-accent)' },
      in_queue: { icon: '⏳', label: t('misc.ppu_visit_status_in_queue'), bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      in_progress: { icon: '🟡', label: t('misc.ppu_visit_status_in_progress'), bg: 'var(--mac-warning-bg)', color: 'var(--mac-warning)' },
      completed: { icon: '🟢', label: t('misc.ppu_visit_status_completed'), bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      paid: { icon: '💳', label: t('misc.ppu_visit_status_paid'), bg: 'var(--mac-success-bg)', color: 'var(--mac-success)' },
      cancelled: { icon: '🔴', label: t('misc.ppu_visit_status_cancelled'), bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' },
      no_show: { icon: '❌', label: t('misc.ppu_visit_status_no_show'), bg: 'var(--mac-error-bg)', color: 'var(--mac-error)' }
    };
    return config[status] || { icon: '⚪', label: status || t('misc.ppu_visit_status_unknown'), bg: 'var(--mac-bg-secondary)', color: 'var(--mac-text-secondary)' };
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
      : `<tr><td colspan="3">${t('misc.ppu_print_no_visits')}</td></tr>`;

    const labHtml = labResults.length
      ? labResults.map((result) => `
        <tr>
          <td>${getLabDisplayName(result)}</td>
          <td>${result.value || '—'}</td>
          <td>${getStatusBadge(result.status).label}</td>
        </tr>
      `).join('')
      : `<tr><td colspan="3">${t('misc.ppu_print_no_lab_results')}</td></tr>`;

    openPrintableWindow({
      features: 'width=900,height=700',
      html: `
      <!doctype html>
      <html lang="ru">
        <head>
          <title>${t('misc.ppu_print_title')}</title>
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
          <div class="muted">${t('misc.ppu_print_muted')}</div>
          <div class="meta">
            <div><strong>${t('misc.ppu_print_patient')}</strong> ${patient?.full_name || patient?.name || '—'}</div>
            <div><strong>${t('misc.ppu_print_id')}</strong> ${patientId || '—'}</div>
            <div><strong>${t('misc.ppu_print_birth_date')}</strong> ${formatDate(patient?.birth_date || patient?.birthDate)}</div>
            <div><strong>${t('misc.ppu_print_phone')}</strong> ${patient?.phone || '—'}</div>
          </div>

          <h2>${t('misc.ppu_print_visits_title')}</h2>
          <table>
            <thead>
              <tr>
                <th>{t('common.date')}</th>
                <th>{t('common.doctor')}</th>
                <th>{t('common.status')}</th>
              </tr>
            </thead>
            <tbody>${visitsHtml}</tbody>
          </table>

          <h2>${t('misc.ppu_print_lab_title')}</h2>
          <table>
            <thead>
              <tr>
                <th>${t('misc.ppu_print_lab_study')}</th>
                <th>${t('misc.ppu_print_lab_result')}</th>
                <th>{t('common.status')}</th>
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
      notify.info(t('misc.ppu_pdf_unavailable'));
    }
  };

  // Styles
  const styles = {
    container: {
      minHeight: '100vh',
      background: 'var(--mac-gradient-window, linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%))',
      padding: 'var(--mac-spacing-6)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
    },
    header: {
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-4)',
      marginBottom: 'var(--mac-spacing-6)'
    },
    backButton: {
      background: 'var(--mac-bg-secondary, white)',
      border: '1px solid var(--mac-border, #e2e8f0)',
      borderRadius: 'var(--mac-radius-md)',
      padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
      cursor: 'pointer',
      fontSize: 'var(--mac-font-size-base)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)'
    },
    title: {
      fontSize: 'var(--mac-font-size-3xl)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      color: 'var(--mac-text-primary, #1e293b)',
      margin: 0
    },
    card: {
      background: 'var(--mac-bg-primary, white)',
      borderRadius: 'var(--mac-radius-xl)',
      boxShadow: 'var(--mac-shadow-md)',
      padding: 'var(--mac-spacing-6)',
      marginBottom: 'var(--mac-spacing-6)'
    },
    patientInfo: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
      gap: 'var(--mac-spacing-4)'
    },
    infoItem: {
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-1)'
    },
    infoLabel: {
      fontSize: 'var(--mac-font-size-xs)',
      color: 'var(--mac-text-tertiary, #64748b)',
      textTransform: 'uppercase',
      letterSpacing: '0.5px'
    },
    infoValue: {
      fontSize: 'var(--mac-font-size-lg)',
      fontWeight: 'var(--mac-font-weight-medium)',
      color: 'var(--mac-text-primary, #1e293b)'
    },
    sectionTitle: {
      fontSize: 'var(--mac-font-size-xl)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      color: 'var(--mac-text-primary, #1e293b)',
      marginBottom: 'var(--mac-spacing-4)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)'
    },
    labList: {
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-3)'
    },
    labItem: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: 'var(--mac-spacing-4)',
      background: 'var(--mac-bg-secondary, #f8fafc)',
      borderRadius: 'var(--mac-radius-lg)',
      border: '1px solid var(--mac-border, #e2e8f0)'
    },
    labInfo: {
      flex: 1
    },
    labName: {
      fontSize: 'var(--mac-font-size-lg)',
      fontWeight: 'var(--mac-font-weight-medium)',
      color: 'var(--mac-text-primary, #1e293b)',
      marginBottom: 'var(--mac-spacing-1)'
    },
    labDate: {
      fontSize: 'var(--mac-font-size-sm)',
      color: 'var(--mac-text-secondary, #64748b)'
    },
    statusBadge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)',
      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
      borderRadius: 'var(--mac-radius-xl)',
      fontSize: 'var(--mac-font-size-sm)',
      fontWeight: 'var(--mac-font-weight-medium)'
    },
    actions: {
      display: 'flex',
      gap: 'var(--mac-spacing-2)',
      marginLeft: 'var(--mac-spacing-4)'
    },
    actionButton: {
      background: 'var(--mac-bg-primary, white)',
      border: '1px solid var(--mac-border, #e2e8f0)',
      borderRadius: 'var(--mac-radius-md)',
      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
      cursor: 'pointer',
      fontSize: 'var(--mac-font-size-sm)',
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)',
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
          title={t('misc.ppu_loading_title')}
          description={t('misc.ppu_loading_desc')}
          ariaLabel={t('misc.ppu_loading_aria')}
          style={styles.loading}
        />
            </div>);

  }

  if (error) {
    return (
      <div style={styles.container}>
        <AppError
          title={t('misc.ppu_load_error')}
          description={error}
          action={
            <Button
              type="button"
              variant="outline"
              size="small"
              onClick={loadData}
              disabled={isLoading}
              loading={isLoading}
              aria-label={t('misc.ppu_retry_aria')}>
              {t('misc.ppu_retry')}
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
                  aria-label={t('misc.ppu_back_aria')}>
                    ← {t('misc.ppu_back')}
                </button>
                <h1 id="patient-pickup-title" style={styles.title}>{getPageTitle()}</h1>
            </div>

            {/* Patient Info Card */}
            <div style={styles.card}>
                <h2 style={styles.sectionTitle}>
                    👤 {t('misc.ppu_patient_info_title')}
                </h2>
                <div style={styles.patientInfo}>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>{t('misc.ppu_field_full_name')}</span>
                        <span style={styles.infoValue}>
                            {patient?.last_name} {patient?.first_name} {patient?.middle_name || ''}
                        </span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>{t('misc.ppu_field_birth_date')}</span>
                        <span style={styles.infoValue}>{formatDate(patient?.birth_date)}</span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>{t('common.phone')}</span>
                        <span style={styles.infoValue}>{patient?.phone || '—'}</span>
                    </div>
                    <div style={styles.infoItem}>
                        <span style={styles.infoLabel}>{t('misc.ppu_field_patient_id')}</span>
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
                        🧪 {t('misc.ppu_lab_results_title')}
                    </h2>

                    {labResults.length === 0 ?
        <AppEmpty
          title={t('misc.ppu_no_lab_results_title')}
          description={t('misc.ppu_no_lab_results_desc')}
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
                                                {t('misc.ppu_lab_code_order', { code: getLabDisplayCode(lab), id: lab.id })}
                                            </div>
                                        </div>

                                        <div
                  aria-label={t('misc.ppu_lab_status_aria', { label: status.label })}
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
                    aria-label={t('misc.ppu_print_lab_aria', { name: getLabDisplayName(lab) })}
                    title={t('misc.ppu_print_action')}>

                                                        🖨️ {t('misc.ppu_print_action')}
                                                    </button>
                  <button
                    type="button"
                    style={styles.actionButton}
                    onClick={() => handleDownloadPDF(lab)}
                    aria-label={t('misc.ppu_download_pdf_aria', { name: getLabDisplayName(lab) })}
                    title={t('misc.ppu_download_pdf_title_attr')}>

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
                        {isCashierView ? `💳 ${t('misc.ppu_title_cashier')}` : `📋 ${t('misc.ppu_print_visits_title')}`}
                    </h2>

                    {visits.length === 0 ?
        <AppEmpty
          title={t('misc.ppu_no_visits_title')}
          description={t('misc.ppu_no_visits_desc')}
          style={styles.emptyState}
        /> :

        <div className="admin-table-wrapper" style={{ overflowX: 'auto' }} aria-label={t('misc.ppu_title_patient')}>
                            <table style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 'var(--mac-font-size-base)'
          }}>
                                <caption style={styles.visuallyHidden}>{t('misc.ppu_title_patient')}</caption>
                                <thead>
                                    <tr style={{
                background: 'var(--mac-bg-tertiary, #f1f5f9)',
                borderBottom: '2px solid var(--mac-separator, #e2e8f0)'
              }}>
                                        <th style={{ padding: 'var(--mac-spacing-3)', textAlign: 'left', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)' }}>{t('common.date')}</th>
                                        <th style={{ padding: 'var(--mac-spacing-3)', textAlign: 'left', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)' }}>{t('misc.ppu_col_visit_num')}</th>
                                        <th style={{ padding: 'var(--mac-spacing-3)', textAlign: 'left', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)' }}>{t('misc.ppu_col_services')}</th>
                                        <th style={{ padding: 'var(--mac-spacing-3)', textAlign: 'right', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)' }}>{t('misc.ppu_col_amount')}</th>
                                        <th style={{ padding: 'var(--mac-spacing-3)', textAlign: 'center', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-secondary)' }}>{t('common.status')}</th>
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
                                                <td style={{ padding: 'var(--mac-spacing-3)', whiteSpace: 'nowrap' }}>
                                                    {formatDate(visit.visit_date || visit.created_at)}
                                                    {visit.visit_time && <span style={{ color: 'var(--mac-text-tertiary)', marginLeft: 'var(--mac-spacing-2)' }}>{visit.visit_time}</span>}
                                                </td>
                                                <td style={{ padding: 'var(--mac-spacing-3)', fontWeight: 'var(--mac-font-weight-medium)' }}>
                                                    #{visit.id}
                                                </td>
                                                <td style={{ padding: 'var(--mac-spacing-3)', maxWidth: '300px' }}>
                                                    {servicesText}
                                                </td>
                                                <td style={{ padding: 'var(--mac-spacing-3)', textAlign: 'right', fontWeight: 'var(--mac-font-weight-semibold)', whiteSpace: 'nowrap' }}>
                                                    {totalAmount > 0 ? t('misc.ppu_amount_with_currency', { amount: totalAmount.toLocaleString('ru-RU') }) : '—'}
                                                </td>
                                                <td style={{ padding: 'var(--mac-spacing-3)', textAlign: 'center' }}>
                                                    <span
                                                      aria-label={t('misc.ppu_visit_status_aria', { label: visitStatus.label })}
                                                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-1)',
                        padding: '4px 10px',
                        borderRadius: 'var(--mac-radius-lg)',
                        fontSize: 'var(--mac-font-size-xs)',
                        fontWeight: 'var(--mac-font-weight-medium)',
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
