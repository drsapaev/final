import { useCallback, useEffect, useRef, useState } from 'react';
import { CalendarClock, RotateCw } from 'lucide-react';
import { useConfirm } from '../common/ConfirmDialog';
import { Badge, Button, Card } from '../ui/macos';
import {
  listPatientPublicBookingRequests,
  withdrawPatientPublicBookingRequest,
  type PatientPublicBookingRequest,
  type PatientPublicBookingRequestStatus,
} from '../../api/publicBooking';
import { useTranslation } from '../../i18n/useTranslation';
import PanelEmptyState from './PanelEmptyState';

const PAGE_SIZE = 50;

const STATUS_KEYS: Record<PatientPublicBookingRequestStatus, string> = {
  pending: 'publicBookingRequests.status.pending',
  needs_new_time: 'publicBookingRequests.status.needsNewTime',
  confirmed: 'publicBookingRequests.status.confirmed',
  rejected: 'publicBookingRequests.status.rejected',
  withdrawn: 'publicBookingRequests.status.withdrawn',
};

const STATUS_HELP_KEYS: Record<PatientPublicBookingRequestStatus, string> = {
  pending: 'publicBookingRequests.help.pending',
  needs_new_time: 'publicBookingRequests.help.needsNewTime',
  confirmed: 'publicBookingRequests.help.confirmed',
  rejected: 'publicBookingRequests.help.rejected',
  withdrawn: 'publicBookingRequests.help.withdrawn',
};

function badgeVariant(status: PatientPublicBookingRequestStatus): string {
  if (status === 'confirmed') return 'success';
  if (status === 'needs_new_time') return 'warning';
  if (status === 'pending') return 'info';
  return 'secondary';
}

function localeFor(language: string): string {
  if (language === 'uz-Latn') return 'uz-Latn-UZ';
  if (language === 'uz-Cyrl') return 'uz-Cyrl-UZ';
  if (language === 'kk') return 'kk-KZ';
  if (language === 'en') return 'en-GB';
  return 'ru-RU';
}

function formatRequestedSlot(request: PatientPublicBookingRequest, locale: string): string {
  const time = request.appointment_time.slice(0, 8);
  const date = new Date(`${request.appointment_date}T${time}+05:00`);
  if (Number.isNaN(date.getTime())) {
    return `${request.appointment_date} · ${request.appointment_time.slice(0, 5)}`;
  }
  const dateText = new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Tashkent',
    dateStyle: 'medium',
  }).format(date);
  const timeText = new Intl.DateTimeFormat(locale, {
    timeZone: 'Asia/Tashkent',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
  return `${dateText} · ${timeText}`;
}

export default function PublicBookingRequestsPanel() {
  const { t, language } = useTranslation();
  const [confirm, confirmDialog] = useConfirm();
  const requestGeneration = useRef(0);
  const [items, setItems] = useState<PatientPublicBookingRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState(false);
  const [busyRequestId, setBusyRequestId] = useState<string | null>(null);
  const locale = localeFor(language || 'ru');

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setLoadingMore(false);
    setError(false);
    try {
      const requests = await listPatientPublicBookingRequests({ limit: PAGE_SIZE, offset: 0 });
      if (generation === requestGeneration.current) {
        setItems(requests);
        setHasMore(requests.length === PAGE_SIZE);
      }
    } catch {
      if (generation === requestGeneration.current) setError(true);
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || !hasMore) return;
    const generation = requestGeneration.current;
    setLoadingMore(true);
    try {
      const requests = await listPatientPublicBookingRequests({
        limit: PAGE_SIZE,
        offset: items.length,
      });
      if (generation !== requestGeneration.current) return;
      setItems((current) => {
        const knownIds = new Set(current.map((item) => item.id));
        return [...current, ...requests.filter((item) => !knownIds.has(item.id))];
      });
      setHasMore(requests.length === PAGE_SIZE);
    } catch {
      if (generation === requestGeneration.current) setError(true);
    } finally {
      if (generation === requestGeneration.current) setLoadingMore(false);
    }
  }, [hasMore, items.length, loading, loadingMore]);

  useEffect(() => {
    void load();
    return () => {
      requestGeneration.current += 1;
    };
  }, [load]);

  const withdraw = useCallback(async (item: PatientPublicBookingRequest) => {
    const confirmed = await confirm({
      title: t('publicBookingRequests.withdrawConfirmTitle'),
      message: t('publicBookingRequests.withdrawConfirmMessage'),
      confirmLabel: t('publicBookingRequests.withdraw'),
      cancelLabel: t('publicBookingRequests.cancel'),
      intent: 'warning',
    });
    if (!confirmed || busyRequestId) return;

    setBusyRequestId(item.id);
    setNotice(false);
    setError(false);
    try {
      await withdrawPatientPublicBookingRequest(item.id, item.version);
      setNotice(true);
      await load();
    } catch {
      setError(true);
    } finally {
      setBusyRequestId(null);
    }
  }, [busyRequestId, confirm, load, t]);

  return (
    <Card className="pp-card" padding="none" data-testid="patient-public-booking-requests">
      <div className="pp-home-card-header">
        <CalendarClock size={16} aria-hidden="true" />
        <h3 className="pp-home-card-title">{t('publicBookingRequests.title')}</h3>
        <Button
          variant="outline"
          size="small"
          className="ml-auto"
          onClick={() => { setNotice(false); void load(); }}
          disabled={loading}
          aria-label={t('publicBookingRequests.refresh')}
        >
          <RotateCw size={14} aria-hidden="true" />
          {t('publicBookingRequests.refresh')}
        </Button>
      </div>
      <p className="px-4 py-3 text-sm text-[var(--mac-text-secondary, rgb(69 85 104))]">
        {t('publicBookingRequests.description')}
      </p>
      {notice && <p className="px-4 text-sm" role="status">{t('publicBookingRequests.withdrawnNotice')}</p>}
      {error && (
        <div className="px-4 pb-3" role="alert">
          <p>{t('publicBookingRequests.loadError')}</p>
          <Button variant="outline" size="small" onClick={() => void load()} disabled={loading}>
            {t('publicBookingRequests.retry')}
          </Button>
        </div>
      )}
      {loading && items.length === 0 ? (
        <div className="pp-home-list">
          <PanelEmptyState
            icon={RotateCw}
            title={t('publicBookingRequests.loading')}
            variant="loading"
          />
        </div>
      ) : !loading && !error && items.length === 0 ? (
        <div className="pp-home-list">
          <PanelEmptyState title={t('publicBookingRequests.empty')} />
        </div>
      ) : (
        <div className="pp-home-list" aria-busy={loading}>
          {items.map((item) => {
            const canWithdraw = item.status === 'pending' || item.status === 'needs_new_time';
            return (
              <div key={item.id} className="pp-home-list-item" data-testid="patient-booking-request">
                <div className="min-w-0">
                  <div className="pp-list-item-primary">
                    {t('publicBookingRequests.requestedTime')}: {formatRequestedSlot(item, locale)}
                  </div>
                  <div className="pp-list-item-secondary">
                    {t(STATUS_HELP_KEYS[item.status])}
                  </div>
                  {item.status === 'needs_new_time' && (
                    <a
                      className="mt-2 inline-block text-sm text-[var(--mac-accent-blue-active, #004bb5)] underline"
                      href={language === 'uz-Latn' ? '/booking' : '/ru/booking'}
                    >
                      {t('publicBookingRequests.chooseAnotherTime')}
                    </a>
                  )}
                  {canWithdraw && (
                    <Button
                      variant="outline"
                      size="small"
                      className="mt-3"
                      disabled={Boolean(busyRequestId)}
                      onClick={() => { void withdraw(item); }}
                    >
                      {busyRequestId === item.id
                        ? t('publicBookingRequests.working')
                        : t('publicBookingRequests.withdraw')}
                    </Button>
                  )}
                </div>
                <Badge variant={badgeVariant(item.status)}>
                  {t(STATUS_KEYS[item.status])}
                </Badge>
              </div>
            );
          })}
        </div>
      )}
      {hasMore && (
        <div className="px-4 pb-4">
          <Button
            variant="outline"
            size="small"
            onClick={() => { void loadMore(); }}
            disabled={loading || loadingMore}
          >
            {loadingMore
              ? t('publicBookingRequests.loading')
              : t('publicBookingRequests.loadMore')}
          </Button>
        </div>
      )}
      {confirmDialog}
    </Card>
  );
}
