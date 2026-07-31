/**
 * Tests for billing mappers — InvoiceDto + PaymentDto.
 */

import { describe, it, expect } from 'vitest';
import { mapInvoiceDto, mapInvoiceDtos, mapPaymentDto } from '../billing';

describe('mapInvoiceDto', () => {
  const validDto = {
    id: 123,
    appointment_id: 456,
    patient_id: 789,
    patient_name: 'Test Patient',
    amount: 150000,
    paid_amount: 150000,
    status: 'paid',
    method: 'cash',
    created_at: '2024-01-01T00:00:00Z',
    paid_at: '2024-01-02T00:00:00Z',
  };

  it('transforms a valid DTO to domain Invoice', () => {
    const invoice = mapInvoiceDto(validDto);
    expect(invoice.id).toBe(123);
    expect(invoice.appointment_id).toBe(456);
    expect(invoice.patient_id).toBe(789);
    expect(invoice.amount).toBe(150000);
    expect(invoice.status).toBe('paid');
  });

  it('accepts invoice_id as alternative to id', () => {
    const dto: Record<string, unknown> = { ...validDto };
    delete dto.id;
    dto.invoice_id = 999;
    const invoice = mapInvoiceDto(dto);
    // toInvoiceId converts to string (branded type)
    expect(String(invoice.id)).toBe('999');
  });

  it('throws ZodError when both id and invoice_id are missing', () => {
    const { id: _, ...dtoWithoutId } = validDto;
    expect(() => mapInvoiceDto(dtoWithoutId)).toThrow();
  });

  it('throws ZodError when dto is null', () => {
    expect(() => mapInvoiceDto(null)).toThrow();
  });

  it('passes through extra fields via index signature', () => {
    const dto: Record<string, unknown> = { ...validDto, extra_field: 'value' };
    const invoice = mapInvoiceDto(dto);
    expect((invoice as unknown as Record<string, unknown>).extra_field).toBe('value');
  });
});

describe('mapPaymentDto', () => {
  const validDto = {
    id: 1,
    invoice_id: 100,
    patient_id: 200,
    amount: 50000,
    method: 'click',
    status: 'completed',
    transaction_id: 'tx-123',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('transforms a valid DTO to domain Payment', () => {
    const payment = mapPaymentDto(validDto);
    expect(payment.id).toBe(1);
    expect(payment.invoice_id).toBe(100);
    expect(payment.amount).toBe(50000);
    expect(payment.status).toBe('completed');
  });

  it('throws ZodError when both id and payment_id are missing', () => {
    const { id: _, ...dtoWithoutId } = validDto;
    expect(() => mapPaymentDto(dtoWithoutId)).toThrow();
  });
});

describe('mapInvoiceDtos', () => {
  it('skips invalid entries', () => {
    const dtos = [
      { id: 1, status: 'paid' },
      { no_id: true }, // invalid
      { id: 2, status: 'pending' },
    ];
    const invoices = mapInvoiceDtos(dtos);
    expect(invoices).toHaveLength(2);
    expect(invoices[0].id).toBe(1);
    expect(invoices[1].id).toBe(2);
  });
});
