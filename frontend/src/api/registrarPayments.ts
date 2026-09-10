import { api } from './client';
import { getRegistrarRecordRefs } from '../pages/registrar/registrarHelpers';

export interface RegistrarPaymentSummary {
  total_amount: number | string;
  paid_amount: number | string;
  remaining_amount: number | string;
  payment_status: string;
  can_pay: boolean;
  snapshot: string;
  visits: { visit_id: number; remaining_amount: number | string }[];
}

export interface RegistrarPaymentInput {
  amount: number;
  method: string;
  payment_snapshot: string;
}

export async function getRegistrarPaymentSummary(record: Record<string, unknown>) {
  const response = await api.post<RegistrarPaymentSummary>('/registrar/records/payment-summary', {
    records: getRegistrarRecordRefs(record),
  });
  return response.data;
}
