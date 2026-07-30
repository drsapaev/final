/**
 * Domain types for billing, payments, and discounts.
 * Used by CashierPanel, useFinance, DiscountBenefitsManager,
 * PaymentWidget, and billing-related components.
 */

export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'click' | 'payme';
export type PaymentStatus = 'pending' | 'paid' | 'refunded' | 'failed' | 'partial';
export type DiscountMode = 'none' | 'repeat' | 'benefit' | 'all_free';

export interface Invoice {
  id: string | number;
  invoice_number?: string;
  appointment_id?: string | number;
  patient_id?: string | number;
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
  [key: string]: unknown;
}

export interface InvoiceItem {
  id?: string | number;
  service_id?: string | number;
  service_name?: string;
  quantity?: number;
  price?: number;
  total?: number;
  doctor_id?: string | number;
  doctor_name?: string;
  [key: string]: unknown;
}

export interface Payment {
  id: string | number;
  payment_number?: string;
  is_confirmed?: boolean;
  invoice_id?: string | number;
  patient_id?: string | number;
  amount?: number;
  method?: PaymentMethod;
  payment_method?: string;
  status?: PaymentStatus;
  transaction_id?: string;
  payment_date?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface Discount {
  id: string | number;
  name?: string;
  description?: string;
  discount_type?: 'percentage' | 'fixed';
  value?: number;
  active?: boolean;
  [key: string]: unknown;
}

export interface DiscountApplication {
  discount_id?: string | number;
  discount_name?: string;
  amount?: number;
  percentage?: number;
  [key: string]: unknown;
}

export interface BillingSummary {
  total_revenue?: number;
  total_paid?: number;
  total_pending?: number;
  total_refunded?: number;
  transaction_count?: number;
  by_method?: Record<string, number>;
  by_status?: Record<string, number>;
  [key: string]: unknown;
}

export type RefundStatus = 'requested' | 'approved' | 'rejected' | 'processed';

export interface Refund {
  id: string | number;
  payment_id?: string | number;
  invoice_id?: string | number;
  amount?: number;
  reason?: string;
  status?: RefundStatus;
  requested_at?: string;
  processed_at?: string;
  [key: string]: unknown;
}

export interface PaymentProvider {
  id?: string | number;
  name?: string;
  code?: string;
  is_active?: boolean;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PaymentWebhook {
  id?: string | number;
  provider?: string;
  event_type?: string;
  transaction_id?: string;
  status?: string;
  payload?: Record<string, unknown>;
  created_at?: string;
  [key: string]: unknown;
}

export interface CartItemBilling {
  service_id?: string | number;
  service_name?: string;
  quantity?: number;
  price?: number;
  total?: number;
  doctor_id?: string | number;
  doctor_name?: string;
  discount_amount?: number;
  is_free?: boolean;
  [key: string]: unknown;
}

export interface PaymentResult {
  success: boolean;
  transaction_id?: string;
  error?: string;
  redirect_url?: string;
  [key: string]: unknown;
}
