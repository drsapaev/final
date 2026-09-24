import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { CalendarCheck, CheckCircle2, RefreshCw, Ticket, XCircle } from 'lucide-react';

import { useTranslation } from '../i18n/useTranslation';
import {
    confirmVisitByPwa,
    getVisitInfoByToken,
    type VisitInfoByTokenDto,
    type VisitQueueNumberDto,
} from '../api/visitConfirmation';
import { Button } from '../components/ui/macos';
import './ConfirmVisitPage.css';

/**
 * Публичная страница подтверждения визита по SMS-приглашению (PWA).
 *
 * Ссылка из напоминания (backend notifications_pkg/_formatting.py) ведёт на
 * /confirm-visit#token=…; страница читает карточку визита
 * (POST /visits/info с токеном в теле) и подтверждает визит
 * (POST /patient/visits/confirm).
 *
 * PR 3390 review round (P1): маршрут отсутствовал — wildcard уводил ссылку
 * пациента на /not-found, при этом напоминание отмечалось доставленным.
 */

type Phase = 'checking' | 'ready' | 'load-error' | 'invalid' | 'done';

const isAxiosLikeError = (
    err: unknown,
): err is { response?: { status?: number; data?: { detail?: string } } } =>
    typeof err === 'object' && err !== null && 'response' in err;

const errorDetail = (err: unknown): string => {
    const detail = isAxiosLikeError(err) ? err.response?.data?.detail : undefined;
    return typeof detail === 'string' ? detail : '';
};

/** Локальный формат даты ISO (YYYY-MM-DD) → DD.MM.YYYY без сдвига таймзоны. */
const formatVisitDate = (iso: string): string => {
    const parts = iso.split('-');
    return parts.length === 3 ? `${parts[2]}.${parts[1]}.${parts[0]}` : iso;
};

const ConfirmVisitPage = () => {
    const { t } = useTranslation();
    const location = useLocation();
    const token = (
        new URLSearchParams(location.hash.slice(1)).get('token') ??
        new URLSearchParams(location.search).get('token') ?? ''
    ).trim();

    useLayoutEffect(() => {
        // Remove both new fragment and legacy query tokens before the first
        // API call. A fragment is also absent from the initial HTTP request.
        const url = new URL(window.location.href);
        const fragment = new URLSearchParams(url.hash.slice(1));
        if (!url.searchParams.has('token') && !fragment.has('token')) return;
        url.searchParams.delete('token');
        fragment.delete('token');
        url.hash = fragment.toString();
        window.history.replaceState(
            window.history.state,
            '',
            `${url.pathname}${url.search}${url.hash}`,
        );
    }, [location.search, location.hash]);

    const [phase, setPhase] = useState<Phase>('checking');
    const [info, setInfo] = useState<VisitInfoByTokenDto | null>(null);
    const [confirming, setConfirming] = useState(false);
    const [actionError, setActionError] = useState('');
    const [loadError, setLoadError] = useState('');
    const [invalidReason, setInvalidReason] = useState('');
    const [queueNumbers, setQueueNumbers] = useState<VisitQueueNumberDto[]>([]);
    const [doneMessage, setDoneMessage] = useState('');
    const [stateToken, setStateToken] = useState(token);
    const aliveRef = useRef(true);
    const activeTokenRef = useRef(token);
    const loadSequenceRef = useRef(0);

    useEffect(() => {
        aliveRef.current = true;
        return () => {
            aliveRef.current = false;
        };
    }, []);

    /** Загрузка карточки; только 400/404 делают ссылку недействительной. */
    const loadInfo = useCallback(async (requestedToken: string) => {
        const sequence = ++loadSequenceRef.current;
        setStateToken(requestedToken);
        setPhase('checking');
        setInfo(null);
        setActionError('');
        setLoadError('');
        setInvalidReason('');
        setDoneMessage('');
        setQueueNumbers([]);
        setConfirming(false);
        try {
            const data = await getVisitInfoByToken(requestedToken);
            if (!aliveRef.current || loadSequenceRef.current !== sequence ||
                activeTokenRef.current !== requestedToken) return;
            setInfo(data);
            setPhase('ready');
        } catch (err) {
            if (!aliveRef.current || loadSequenceRef.current !== sequence ||
                activeTokenRef.current !== requestedToken) return;
            const status = isAxiosLikeError(err) ? err.response?.status : undefined;
            if (status === 400 || status === 404) {
                setInvalidReason(errorDetail(err));
                setPhase('invalid');
            } else {
                setLoadError(errorDetail(err));
                setPhase('load-error');
            }
        }
    }, []);

    useEffect(() => {
        activeTokenRef.current = token;
        if (!token) {
            ++loadSequenceRef.current;
            setStateToken(token);
            setInfo(null);
            setInvalidReason('');
            setActionError('');
            setLoadError('');
            setConfirming(false);
            setPhase('invalid');
        } else {
            void loadInfo(token);
        }
        return () => {
            // Ignore a response from the previous token or StrictMode effect.
            ++loadSequenceRef.current;
        };
    }, [token, loadInfo]);

    const confirm = useCallback(async () => {
        if (!token || confirming) return;
        setConfirming(true);
        setActionError('');
        try {
            const data = await confirmVisitByPwa(token);
            if (!aliveRef.current || activeTokenRef.current !== token) return;
            setDoneMessage(data.message || t('cv_confirmed'));
            // ConfirmationResponse.queue_numbers is {[key: string]: unknown}[]
            // in the generated contract; the backend pins {queue_tag, number,
            // queue_id} (visit_confirmation_service) — bridge-cast at the boundary.
            setQueueNumbers(
                (data.queue_numbers ?? []) as unknown as VisitQueueNumberDto[],
            );
            setPhase('done');
        } catch (err) {
            if (!aliveRef.current || activeTokenRef.current !== token) return;
            if (isAxiosLikeError(err)) {
                const status = err.response?.status ?? 0;
                if (status === 404 || status === 400) {
                    // Токен больше не подтверждаем (неизвестен/уже подтверждён/
                    // истек/канал) — терминальный экран с причиной сервера.
                    setInvalidReason(errorDetail(err) || t('cv_invalid_link'));
                    setPhase('invalid');
                    return;
                }
            }
            setActionError(errorDetail(err) || t('cv_error'));
        } finally {
            if (aliveRef.current && activeTokenRef.current === token) setConfirming(false);
        }
    }, [token, confirming, t]);

    const visiblePhase = stateToken === token ? phase : token ? 'checking' : 'invalid';

    const totalLabel = info
        ? `${new Intl.NumberFormat('ru-RU').format(info.total_amount)} ${info.currency}`
        : '';

    return (
        <div className="cv-page">
            <section className="cv-card" aria-labelledby="cv-title">
                <header>
                    <h1 id="cv-title" className="cv-title">
                        {t('cv_title')}
                    </h1>
                    <p className="cv-subtitle">{t('cv_subtitle')}</p>
                </header>

                {visiblePhase === 'checking' && (
                    <div className="cv-status" role="status" aria-live="polite">
                        <RefreshCw
                            className="cv-status-icon cv-status-icon-muted"
                            aria-hidden="true"
                        />
                        <p className="cv-status-text">{t('cv_loading')}</p>
                    </div>
                )}

                {visiblePhase === 'load-error' && (
                    <div className="cv-status" role="alert">
                        <XCircle
                            className="cv-status-icon cv-status-icon-error"
                            aria-hidden="true"
                        />
                        <p className="cv-status-text">{loadError || t('cv_error')}</p>
                        <Button onClick={() => void loadInfo(token)}>
                            {t('btn_retry')}
                        </Button>
                    </div>
                )}

                {visiblePhase === 'invalid' && (
                    <div className="cv-status" role="alert">
                        <XCircle
                            className="cv-status-icon cv-status-icon-error"
                            aria-hidden="true"
                        />
                        <p className="cv-status-text">
                            {(stateToken === token && invalidReason) || t('cv_invalid_link')}
                        </p>
                        <p className="cv-status-hint">{t('cv_invalid_hint')}</p>
                    </div>
                )}

                {visiblePhase === 'ready' && info && (
                    <>
                        <div className="cv-fields">
                            <div className="cv-field">
                                <span className="cv-label">{t('cv_patient')}</span>
                                <span className="cv-value">{info.patient_name}</span>
                            </div>
                            <div className="cv-field">
                                <span className="cv-label">{t('cv_doctor')}</span>
                                <span className="cv-value">{info.doctor_name}</span>
                            </div>
                            <div className="cv-field">
                                <span className="cv-label">{t('cv_datetime')}</span>
                                <span className="cv-value">
                                    <CalendarCheck
                                        className="cv-inline-icon"
                                        aria-hidden="true"
                                    />
                                    {formatVisitDate(info.visit_date)}
                                    {info.visit_time ? `, ${info.visit_time}` : ''}
                                </span>
                            </div>
                            {info.services.length > 0 && (
                                <div className="cv-field">
                                    <span className="cv-label">{t('cv_services')}</span>
                                    <ul className="cv-services">
                                        {info.services.map((service) => (
                                            <li
                                                key={`${service.code ?? service.name}-${service.name}`}
                                                className="cv-service-row"
                                            >
                                                <span>{service.name}</span>
                                                <span className="cv-service-qty">
                                                    ×{service.quantity}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            <div className="cv-total-row">
                                <span className="cv-label">{t('cv_total')}</span>
                                <span className="cv-total-value">{totalLabel}</span>
                            </div>
                        </div>

                        {actionError && (
                            <div className="cv-error" role="alert">
                                {actionError}
                            </div>
                        )}

                        <div className="cv-actions">
                            <Button onClick={confirm} disabled={confirming}>
                                {confirming ? t('cv_confirming') : t('cv_confirm')}
                            </Button>
                        </div>
                    </>
                )}

                {visiblePhase === 'done' && (
                    <div className="cv-status" role="status">
                        <CheckCircle2
                            className="cv-status-icon cv-status-icon-ok"
                            aria-hidden="true"
                        />
                        <p className="cv-status-text">{doneMessage || t('cv_confirmed')}</p>
                        {queueNumbers.length > 0 && (
                            <>
                                <p className="cv-status-hint">{t('cv_queue_numbers')}</p>
                                <div className="cv-queue-list">
                                    {queueNumbers.map((entry) => (
                                        <div
                                            key={`${entry.queue_id}-${entry.queue_tag}`}
                                            className="cv-queue-item"
                                        >
                                            <span className="cv-queue-tag">
                                                <Ticket aria-hidden="true" />
                                                {entry.queue_tag}
                                            </span>
                                            <span className="cv-queue-number">
                                                №{entry.number}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                )}
            </section>
        </div>
    );
};

export default ConfirmVisitPage;
