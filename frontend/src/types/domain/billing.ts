/**
 * Domain types for billing, payments, and discounts.
 * Used by CashierPanel, useFinance, DiscountBenefitsManager,
 * PaymentWidget, and billing-related components.
 */

import type { PatientId, AppointmentId, DoctorId, ServiceId, InvoiceId, PaymentId } from './branded';

export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'click' | 'payme';
export type PaymentStatus = 'pending' | 'paid' | 'refunded' | 'failed' | 'partial';
export type DiscountMode = 'none' | 'repeat' | 'benefit' | 'all_free';

export interface Invoice {
  id: InvoiceId;
  invoice_number?: string;
  appointment_id?: AppointmentId;
  patient_id?: PatientId;
  patient_name?: string;
  invoice_type?: string;
  amount?: number;
  total_amount?: number;
  paid_amount?: number;
  balance?: number;
  discount_amount?: number;
  status?: PaymentStatus;
  method?: PaymentMethod;
  issue_date?: string;
  due_date?: string;
  created_at?: string;
  paid_at?: string;
  items?: InvoiceItem[];
  invoice_id?: InvoiceId;
  provider?: string;
  description?: string;
}

export interface InvoiceItem {
  id?: InvoiceId;
  service_id?: ServiceId;
  service_name?: string;
  quantity?: number;
  price?: number;
  total?: number;
  doctor_id?: DoctorId;
  doctor_name?: string;
}

export interface Payment {
  id: PaymentId;
  payment_number?: string;
  is_confirmed?: boolean;
  invoice_id?: InvoiceId;
  patient_id?: PatientId;
  amount?: number;
  method?: PaymentMethod;
  payment_method?: string;
  status?: PaymentStatus;
  transaction_id?: string;
  reference_number?: string;
  payment_date?: string;
  created_at?: string;
}

export interface Discount {
  id: InvoiceId;
  name?: string;
  description?: string;
  discount_type?: 'percentage' | 'fixed';
  value?: number;
  active?: boolean;
}

export interface DiscountApplication {
  discount_id?: string | number;
  discount_name?: string;
  amount?: number;
  percentage?: number;
}

export interface BillingSummary {
  total_revenue?: number;
  total_paid?: number;
  total_pending?: number;
  total_refunded?: number;
  transaction_count?: number;
  by_method?: Record<string, number>;
  by_status?: Record<string, number>;
}

export type RefundStatus = 'requested' | 'approved' | 'rejected' | 'processed';

export interface Refund {
  id: InvoiceId;
  payment_id?: PaymentId;
  invoice_id?: InvoiceId;
  amount?: number;
  reason?: string;
  status?: RefundStatus;
  requested_at?: string;
  processed_at?: string;
}

export interface PaymentProvider {
  id?: string | number;
  name?: string;
  code?: string;
  is_active?: boolean;
  config?: Record<string, unknown>;
}

export interface PaymentWebhook {
  id?: string | number;
  provider?: string;
  event_type?: string;
  transaction_id?: string;
  status?: string;
  payload?: Record<string, unknown>;
  created_at?: string;
}

export interface CartItemBilling {
  service_id?: ServiceId;
  service_name?: string;
  quantity?: number;
  price?: number;
  total?: number;
  doctor_id?: DoctorId;
  doctor_name?: string;
  discount_amount?: number;
  is_free?: boolean;
}

export interface PaymentResult {
  success: boolean;
  transaction_id?: string;
  error?: string;
  redirect_url?: string;
}
