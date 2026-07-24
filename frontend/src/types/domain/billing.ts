/**
 * Domain types for billing, payments, and discounts.
 * Used by CashierPanel, useFinance, DiscountBenefitsManager,
 * PaymentWidget, and billing-related components.
 */

export type PaymentMethod = 'cash' | 'card' | 'transfer' | 'click' | 'payme' | string;
export type PaymentStatus = 'pending' | 'paid' | 'refunded' | 'failed' | 'partial' | string;
export type DiscountMode = 'none' | 'repeat' | 'benefit' | 'all_free' | string;

export interface Invoice {
  id: string | number;
  appointment_id?: string | number;
  patient_id?: string | number;
  patient_name?: string;
  amount?: number;
  paid_amount?: number;
  discount_amount?: number;
  status?: PaymentStatus;
  method?: PaymentMethod;
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
  invoice_id?: string | number;
  amount?: number;
  method?: PaymentMethod;
  status?: PaymentStatus;
  transaction_id?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface Discount {
  id: string | number;
  name?: string;
  description?: string;
  discount_type?: 'percentage' | 'fixed' | string;
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
