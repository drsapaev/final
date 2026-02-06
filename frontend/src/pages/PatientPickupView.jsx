/**
 * PatientPickupView - Read-only view for registrar/cashier to issue lab results
 * Shows patient info and lab results without clinical data
 */
import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import auth from '../stores/auth';
import logger from '../utils/logger';
import FamilyRelationsCard from '../components/patient/FamilyRelationsCard';

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

    const canPrint = ['registrar', 'receptionist', 'admin'].includes(userRole);
    const canDownloadPDF = ['registrar', 'receptionist', 'cashier', 'admin'].includes(userRole);

    const [patient, setPatient] = useState(null);
    const [labResults, setLabResults] = useState([]);
    const [visits, setVisits] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    // Load patient, lab data, and visit history
    useEffect(() => {
        const loadData = async () => {
            if (!patientId) return;

            setIsLoading(true);
            setError(null);

            try {
                // Load patient info
                const patientRes = await api.get(`/patients/${patientId}`);
                setPatient(patientRes.data);

                // Load lab results
                try {
                    const labRes = await api.get('/lab', { params: { patient_id: patientId } });
                    setLabResults(labRes.data || []);
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
        };

        loadData();
    }, [patientId]);

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
            done: { icon: '🟢', label: 'Готов', bg: '#dcfce7', color: '#166534' },
            in_progress: { icon: '🟡', label: 'В процессе', bg: '#fef9c3', color: '#854d0e' },
            ordered: { icon: '⚪', label: 'Заказан', bg: '#f1f5f9', color: '#475569' },
            canceled: { icon: '🔴', label: 'Отменён', bg: '#fee2e2', color: '#991b1b' },
        };
        return config[status] || config.ordered;
    };

    // Get status badge for visits
    const getVisitStatusBadge = (status) => {
        const config = {
            scheduled: { icon: '📅', label: 'Запланирован', bg: '#e0f2fe', color: '#0369a1' },
            in_queue: { icon: '⏳', label: 'В очереди', bg: '#fef9c3', color: '#854d0e' },
            in_progress: { icon: '🟡', label: 'На приёме', bg: '#fef3c7', color: '#92400e' },
            completed: { icon: '🟢', label: 'Завершён', bg: '#dcfce7', color: '#166534' },
            paid: { icon: '💳', label: 'Оплачено', bg: '#d1fae5', color: '#047857' },
            cancelled: { icon: '🔴', label: 'Отменён', bg: '#fee2e2', color: '#991b1b' },
            no_show: { icon: '❌', label: 'Неявка', bg: '#fecaca', color: '#dc2626' },
        };
        return config[status] || { icon: '⚪', label: status || 'Неизвестно', bg: '#f1f5f9', color: '#475569' };
    };

    // Handle print
    const handlePrint = (labResult) => {
        window.print(); // Simple print for now
    };

    // Handle download PDF
    const handleDownloadPDF = async (labResult) => {
        try {
            const response = await api.get(`/lab/${labResult.id}/pdf`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.download = `lab_result_${labResult.id}.pdf`;
            link.click();
        } catch (err) {
            alert('PDF пока недоступен');
        }
    };

    // Styles
    const styles = {
        container: {
            minHeight: '100vh',
            background: 'var(--mac-gradient-window, linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%))',
            padding: '24px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
        },
        header: {
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            marginBottom: '24px',
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
            gap: '8px',
        },
        title: {
            fontSize: '24px',
            fontWeight: '600',
            color: 'var(--mac-text-primary, #1e293b)',
            margin: 0,
        },
        card: {
            background: 'var(--mac-bg-primary, white)',
            borderRadius: '16px',
            boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
            padding: '24px',
            marginBottom: '24px',
        },
        patientInfo: {
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
        },
        infoItem: {
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
        },
        infoLabel: {
            fontSize: '12px',
            color: 'var(--mac-text-tertiary, #64748b)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
        },
        infoValue: {
            fontSize: '16px',
            fontWeight: '500',
            color: 'var(--mac-text-primary, #1e293b)',
        },
        sectionTitle: {
            fontSize: '18px',
            fontWeight: '600',
            color: 'var(--mac-text-primary, #1e293b)',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
        },
        labList: {
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
        },
        labItem: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px',
            background: 'var(--mac-bg-secondary, #f8fafc)',
            borderRadius: '12px',
            border: '1px solid var(--mac-border, #e2e8f0)',
        },
        labInfo: {
            flex: 1,
        },
        labName: {
            fontSize: '15px',
            fontWeight: '500',
            color: 'var(--mac-text-primary, #1e293b)',
            marginBottom: '4px',
        },
        labDate: {
            fontSize: '13px',
            color: 'var(--mac-text-secondary, #64748b)',
        },
        statusBadge: {
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 12px',
            borderRadius: '20px',
            fontSize: '13px',
            fontWeight: '500',
        },
        actions: {
            display: 'flex',
            gap: '8px',
            marginLeft: '16px',
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
            transition: 'all 0.2s ease',
        },
        loading: {
            textAlign: 'center',
            padding: '60px',
            color: 'var(--mac-text-tertiary, #64748b)',
        },
        error: {
            textAlign: 'center',
            padding: '60px',
            color: '#dc2626',
        },
        emptyState: {
            textAlign: 'center',
            padding: '40px',
            color: 'var(--mac-text-tertiary, #64748b)',
        },
    };

    if (isLoading) {
        return (
            <div style={styles.container}>
                <div style={styles.loading}>
                    <div style={{ fontSize: '32px', marginBottom: '16px' }}>⏳</div>
                    Загрузка данных пациента...
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div style={styles.container}>
                <div style={styles.error}>
                    <div style={{ fontSize: '32px', marginBottom: '16px' }}>❌</div>
                    {error}
                </div>
            </div>
        );
    }

    return (
        <div style={styles.container}>
            {/* Header */}
            <div style={styles.header}>
                <button style={styles.backButton} onClick={() => navigate(-1)}>
                    ← Назад
                </button>
                <h1 style={styles.title}>{getPageTitle()}</h1>
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
            {patient && !isLabView && !isCashierView && (
                <FamilyRelationsCard
                    patientId={patient.id}
                    patientName={`${patient.last_name} ${patient.first_name}`}
                    canEdit={['admin', 'registrar', 'receptionist'].includes(userRole)}
                />
            )}

            {/* Lab Results Card - Show for lab view and registrar/admin, hide for cashier-only and doctor-only views */}
            {(isLabView || (!isCashierView && !isDoctor)) && (
                <div style={styles.card}>
                    <h2 style={styles.sectionTitle}>
                        🧪 Результаты анализов
                    </h2>

                    {labResults.length === 0 ? (
                        <div style={styles.emptyState}>
                            <div style={{ fontSize: '32px', marginBottom: '12px' }}>📋</div>
                            Нет результатов анализов для этого пациента
                        </div>
                    ) : (
                        <div style={styles.labList}>
                            {labResults.map((lab) => {
                                const status = getStatusBadge(lab.status);
                                return (
                                    <div key={lab.id} style={styles.labItem}>
                                        <div style={styles.labInfo}>
                                            <div style={styles.labName}>
                                                {lab.service_name || `Анализ #${lab.id}`}
                                            </div>
                                            <div style={styles.labDate}>
                                                Код: {lab.service_code || '—'} • Заказ #{lab.id}
                                            </div>
                                        </div>

                                        <div
                                            style={{
                                                ...styles.statusBadge,
                                                background: status.bg,
                                                color: status.color,
                                            }}
                                        >
                                            {status.icon} {status.label}
                                        </div>

                                        {lab.status === 'done' && (canPrint || canDownloadPDF) && (
                                            <div style={styles.actions}>
                                                {canPrint && (
                                                    <button
                                                        style={styles.actionButton}
                                                        onClick={() => handlePrint(lab)}
                                                        title="Печать"
                                                    >
                                                        🖨️ Печать
                                                    </button>
                                                )}
                                                {canDownloadPDF && (
                                                    <button
                                                        style={styles.actionButton}
                                                        onClick={() => handleDownloadPDF(lab)}
                                                        title="Скачать PDF"
                                                    >
                                                        📄 PDF
                                                    </button>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* Visit History Card - Show for doctor, cashier, and registrar views, hide for lab-only */}
            {!isLabView && (
                <div style={styles.card}>
                    <h2 style={styles.sectionTitle}>
                        {isCashierView ? '💳 История визитов и оплат' : '📋 История визитов'}
                    </h2>

                    {visits.length === 0 ? (
                        <div style={styles.emptyState}>
                            <div style={{ fontSize: '32px', marginBottom: '12px' }}>📆</div>
                            Нет истории визитов для этого пациента
                        </div>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{
                                width: '100%',
                                borderCollapse: 'collapse',
                                fontSize: '14px',
                            }}>
                                <thead>
                                    <tr style={{
                                        background: 'var(--mac-bg-tertiary, #f1f5f9)',
                                        borderBottom: '2px solid var(--mac-separator, #e2e8f0)',
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
                                        const servicesText = services.length > 0
                                            ? (typeof services[0] === 'string'
                                                ? services.join(', ')
                                                : services.map(s => s.name || s).join(', '))
                                            : '—';
                                        // Считаем сумму из visit или из services
                                        const totalAmount = visit.total_amount || services.reduce((sum, s) =>
                                            sum + (parseFloat(typeof s === 'object' ? s.price : 0) || 0) * ((typeof s === 'object' ? s.qty : 1) || 1), 0);

                                        return (
                                            <tr key={visit.id} style={{
                                                borderBottom: '1px solid var(--mac-separator, #e2e8f0)',
                                                background: idx % 2 === 0 ? 'transparent' : 'var(--mac-bg-secondary, #fafafa)',
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
                                                    <span style={{
                                                        display: 'inline-flex',
                                                        alignItems: 'center',
                                                        gap: '4px',
                                                        padding: '4px 10px',
                                                        borderRadius: '12px',
                                                        fontSize: '12px',
                                                        fontWeight: '500',
                                                        background: visitStatus.bg,
                                                        color: visitStatus.color,
                                                    }}>
                                                        {visitStatus.icon} {visitStatus.label}
                                                    </span>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
