import { useEffect, useId, useRef, useState } from 'react';
import {
  approveRegistrarCartBenefit,
  listRegistrarPatientBenefits,
  readRegistrarBenefitBalance,
  type RegistrarBenefitOption,
  type SavedRegistrarBenefitCart,
} from '../../api/registrarBenefits';
import { useTranslation } from '../../i18n/useTranslation';
import { getLocale } from '../../utils/dateUtils';
import ModernDialog from '../dialogs/ModernDialog';

interface RegistrarBenefitReviewProps {
  cart: SavedRegistrarBenefitCart;
  patientId: number;
  onFinish: (verifiedTotal: string | null) => void;
}

type Balance = Awaited<ReturnType<typeof readRegistrarBenefitBalance>>;
type Review =
  | { status: 'unattempted' }
  | { status: 'approved'; total: string; discount: string }
  | { status: 'reconciled'; balance: Balance }
  | { status: 'unverified' };

export default function RegistrarBenefitReview({ cart, patientId, onFinish }: RegistrarBenefitReviewProps) {
  const { t } = useTranslation();
  const selectId = useId();
  const [options, setOptions] = useState<RegistrarBenefitOption[] | null>(null);
  const [listError, setListError] = useState(false);
  const [selectedId, setSelectedId] = useState('');
  const [review, setReview] = useState<Review>({ status: 'unattempted' });
  const [busy, setBusy] = useState(false);
  const requestRunning = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    listRegistrarPatientBenefits(patientId, controller.signal).then((items) => {
      if (!controller.signal.aborted) setOptions(items);
    }).catch(() => {
      if (!controller.signal.aborted) setListError(true);
    });
    return () => controller.abort();
  }, [patientId]);

  const formatter = new Intl.NumberFormat(getLocale(), {
    ...(cart.currency ? { style: 'currency', currency: cart.currency } : {}),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const canApprove = review.status === 'unattempted'
    || (review.status === 'reconciled' && review.balance.canRetry);
  const selected = options?.find((option) => String(option.id) === selectedId);
  const currentTotal = review.status === 'approved' ? review.total
    : review.status === 'reconciled' ? review.balance.total : null;
  const canContinue = review.status === 'unattempted' || review.status === 'approved'
    || (review.status === 'reconciled' && review.balance.canContinue);
  const continuationTotal = review.status === 'unattempted' ? cart.originalTotal : currentTotal;

  const reconcile = async () => {
    try {
      const balance = await readRegistrarBenefitBalance(cart);
      setReview({ status: 'reconciled', balance });
    } catch {
      setReview({ status: 'unverified' });
    }
  };

  const handleApproval = async () => {
    if (!canApprove || !selected || requestRunning.current) return;
    requestRunning.current = true;
    setBusy(true);
    try {
      const result = await approveRegistrarCartBenefit(cart, selected.id);
      setReview({ status: 'approved', ...result });
    } catch {
      await reconcile();
    } finally {
      requestRunning.current = false;
      setBusy(false);
    }
  };

  const refreshBalance = async () => {
    if (requestRunning.current) return;
    requestRunning.current = true;
    setBusy(true);
    try {
      await reconcile();
    } finally {
      requestRunning.current = false;
      setBusy(false);
    }
  };

  const finish = (total: string | null) => {
    if (!requestRunning.current) onFinish(total);
  };

  return (
    <ModernDialog
      isOpen
      title={t('misc.aw_benefit_title', { invoice: cart.invoiceId })}
      maxWidth="34rem"
      onClose={() => finish(null)}
      closeOnBackdrop={false}
      closeOnEscape={!busy}
      showCloseButton={!busy}
      actions={[
        { label: t('misc.aw_benefit_records'), onClick: () => finish(null), disabled: busy },
        ...(canContinue && continuationTotal !== null ? [{
          label: t('misc.aw_benefit_continue'),
          onClick: () => finish(continuationTotal),
          disabled: busy,
          variant: canApprove && options?.length ? 'secondary' : 'primary',
        }] : []),
        ...(canApprove && options?.length ? [{
          label: t('misc.aw_benefit_approve'),
          onClick: () => { void handleApproval(); },
          disabled: busy || !selected,
          variant: 'primary',
        }] : []),
        ...(review.status === 'unverified' ? [{
          label: t('misc.aw_benefit_refresh_total'),
          onClick: () => { void refreshBalance(); },
          disabled: busy,
          variant: 'primary',
        }] : []),
      ]}
    >
      <div className="registrar-benefit-review" aria-busy={busy}>
        <dl className="registrar-benefit-review__totals">
          <dt>{t('misc.aw_benefit_original_total')}</dt>
          <dd>{formatter.format(Number(cart.originalTotal))}</dd>
          {review.status === 'approved' && <>
            <dt>{t('misc.aw_benefit_discount')}</dt>
            <dd>{formatter.format(Number(review.discount))}</dd>
          </>}
          {currentTotal !== null && <>
            <dt>{t('misc.aw_benefit_current_total')}</dt>
            <dd>{formatter.format(Number(currentTotal))}</dd>
          </>}
        </dl>

        {canApprove && (
          listError ? <p role="alert">{t('misc.aw_benefit_list_error')}</p>
            : options === null ? <p role="status">{t('common.loading')}</p>
            : options.length === 0 ? <p>{t('misc.aw_benefit_no_options')}</p>
            : <div className="registrar-benefit-review__choice">
              <label htmlFor={selectId}>{t('misc.aw_benefit_select')}</label>
              <select id={selectId} value={selectedId} disabled={busy} onChange={(event) => setSelectedId(event.target.value)}>
                <option value="">{t('misc.aw_benefit_choose_option')}</option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>{option.name} (#{option.id})</option>
                ))}
              </select>
            </div>
        )}
        {busy && <p role="status">{t('common.loading')}</p>}
        {review.status === 'approved' && <p role="status">{t('misc.aw_benefit_approved')}</p>}
        {review.status === 'reconciled' && <p role="status">{t('misc.aw_benefit_reconciled')}</p>}
        {review.status === 'unverified' && <p role="alert">{t('misc.aw_benefit_unknown_total')}</p>}
      </div>
    </ModernDialog>
  );
}
