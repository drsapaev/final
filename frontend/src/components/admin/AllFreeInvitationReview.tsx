import { useRef, useState } from 'react';

import { api } from '../../api/client';
import { useTranslation } from '../../i18n/useTranslation';
import type { components } from '../../types/api';
import { Button, Modal } from '../ui/macos';

export type InvitationReview = components['schemas']['InvitationReissueReview'];
type ReissueRequest = components['schemas']['InvitationReissueRequest'];
type ReissueResult = components['schemas']['InvitationReissueResponse'];

const deliveryLabels: Record<ReissueResult['state'], string> = {
  pending: 'admin2.af_invitation_queued',
  sent: 'admin2.af_invitation_delivered',
  unknown: 'admin2.af_invitation_unverified',
  cancelled: 'admin2.af_invitation_cancelled',
};

interface Props {
  review: InvitationReview;
  onClose: () => void;
}

export default function AllFreeInvitationReview({ review, onClose }: Props) {
  const { t, language } = useTranslation();
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState(false);
  const [deliveryState, setDeliveryState] = useState<ReissueResult['state'] | null>(null);
  const requestKey = useRef<string | null>(null);
  const submitting = useRef(false);
  const formatAmount = (amount: number) => `${amount.toLocaleString(language, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${review.currency ?? ''}`.trim();

  const submit = async () => {
    if (submitting.current || deliveryState) return;
    submitting.current = true;
    setSending(true);
    setFailed(false);
    try {
      requestKey.current ??= crypto.randomUUID();
      const payload: ReissueRequest = {
        expected_patient_id: review.patient_id,
        expected_owner_generation: review.owner_generation,
        expected_context_epoch: review.context_epoch,
        channel: 'phone',
        token: review.token,
      };
      const { data } = await api.post<ReissueResult>(`/visits/${review.visit_id}/confirmation-reissue`, payload, {
        headers: { 'Idempotency-Key': requestKey.current },
      });
      if (!data || !Object.hasOwn(deliveryLabels, data.state)) {
        setFailed(true);
        return;
      }
      setDeliveryState(data.state);
    } catch {
      setFailed(true);
    } finally {
      submitting.current = false;
      setSending(false);
    }
  };

  return (
    <Modal
      isOpen
      title={t('admin2.af_invitation_review')}
      onClose={sending ? undefined : onClose}
      closeOnEscape={!sending}
      closeOnBackdrop={!sending}
      actions={(
        <>
          <Button variant="outline" disabled={sending} onClick={onClose}>{t('common.close')}</Button>
          {!deliveryState && (
            <Button disabled={sending} onClick={() => void submit()}>
              {t(sending ? 'admin2.af_invitation_saving' : 'admin2.af_invitation_submit')}
            </Button>
          )}
        </>
      )}
    >
      <dl className="grid gap-2">
        <div>
          <dt>{t('admin2.af_label_patient')}</dt>
          <dd>{review.patient_name}</dd>
        </div>
        <div>
          <dt>{t('admin2.af_label_datetime')}</dt>
          <dd>{review.visit_date} {review.visit_time}</dd>
        </div>
        <div>
          <dt>{t('admin2.af_label_services')}</dt>
          <dd><ul className="list-disc pl-5">
            {review.services.map((service, index) => (
              <li key={index}>{service.name} × {service.quantity} · {formatAmount(service.total)}</li>
            ))}
          </ul></dd>
        </div>
        <div>
          <dt>{t('admin2.af_invitation_total')}</dt>
          <dd className="font-semibold">{formatAmount(review.total_amount)}</dd>
        </div>
      </dl>
      {failed && <p role="alert">{t('admin2.af_invitation_error')}</p>}
      {deliveryState && <p role="status">{t(deliveryLabels[deliveryState])}</p>}
    </Modal>
  );
}
