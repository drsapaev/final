/**
 * Contract tests — verify the full pipeline end-to-end:
 *
 *   OpenAPI type (types/api.ts)
 *     ↕  type-level contract
 *   Zod schema (api/mappers/schemas/)
 *     ↕  runtime contract
 *   Mapper (api/mappers/)
 *     ↕  type-level contract
 *   Domain type (types/domain/)
 *
 * These tests catch:
 * 1. Schema drift: zod schema doesn't match OpenAPI type (field added/removed/renamed)
 * 2. Mapper drift: mapper output doesn't satisfy domain type
 * 3. Pipeline integrity: fixture DTO → zod.parse() → mapper → domain type
 *
 * If the backend OpenAPI schema changes (e.g. field renamed), the type-level
 * tests fail at compile time. If the zod schema drifts from the OpenAPI type,
 * the runtime fixture tests fail.
 */

// ============================================================================
// Patient pipeline contract
// ============================================================================

import { describe, it, expect } from 'vitest';
import { PatientDtoSchema } from '../../schemas/patientSchema';
import { mapPatientDto } from '../../patient';
import type { PatientDto } from '../../../../types/api';
import type { Patient } from '../../../../types/domain/clinic';

// --- Type-level contracts (compile-time) ---

// 1. Zod schema output must be assignable to OpenAPI DTO type.
//    If OpenAPI adds a required field that zod doesn't have, this fails.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _patientSchemaToDto: PatientDto = null as unknown as z.infer<typeof PatientDtoSchema>;

// 2. Mapper output must be assignable to domain type.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _patientMapperToDomain: Patient = null as unknown as ReturnType<typeof mapPatientDto>;

// Need z.infer — import locally
import type { z } from 'zod';

// --- Runtime contract tests ---

describe('Patient contract: OpenAPI → zod → mapper → domain', () => {
  // Fixture that matches the OpenAPI Patient schema exactly.
  // If the backend adds/removes/renames a required field, this fixture
  // and the zod schema must be updated together.
  const patientFixture: PatientDto = {
    id: 1,
    last_name: 'Synth',
    first_name: 'Test',
    full_name: 'Synth Test Synthич',
    middle_name: 'Synthич',
    birth_date: '1990-01-15',
    sex: 'male',
    phone: '+0000000000',
    email: 'ivan@example.com',
    doc_type: 'passport',
    doc_number: 'AB1234567',
    address: 'Tashkent',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('fixture passes zod schema validation', () => {
    const parsed = PatientDtoSchema.parse(patientFixture);
    expect(parsed.id).toBe(1);
    expect(parsed.last_name).toBe('Synth');
  });

  it('mapper transforms fixture to domain Patient', () => {
    const patient = mapPatientDto(patientFixture);
    expect(patient.id).toBe(1);
    expect(patient.last_name).toBe('Synth');
    expect(patient.name).toBe('Synth Test Synthич');
  });

  it('mapper output satisfies domain Patient type', () => {
    const patient: Patient = mapPatientDto(patientFixture);
    // Type assertion passes at compile time + runtime check
    expect(patient).toBeDefined();
    expect(typeof patient.id).toBe('number');
  });

  it('zod schema requires all OpenAPI-required fields', () => {
    // Required fields per OpenAPI: id, last_name, first_name, created_at
    const requiredFields: (keyof PatientDto)[] = ['id', 'last_name', 'first_name', 'created_at'];
    for (const field of requiredFields) {
      const partial = { ...patientFixture };
      delete partial[field];
      expect(() => PatientDtoSchema.parse(partial)).toThrow();
    }
  });

  it('zod schema accepts null for optional fields', () => {
    const withNulls = {
      ...patientFixture,
      full_name: null,
      middle_name: null,
      birth_date: null,
      sex: null,
      phone: null,
      email: null,
      doc_type: null,
      doc_number: null,
      address: null,
    };
    expect(() => PatientDtoSchema.parse(withNulls)).not.toThrow();
  });
});

// ============================================================================
// Appointment pipeline contract
// ============================================================================

import { AppointmentDtoSchema } from '../../schemas/appointmentSchema';
import { mapAppointmentDto } from '../../appointment';
import type { AppointmentDto } from '../../../../types/api';
import type { Appointment } from '../../../../types/domain/clinic';

// Type-level contracts
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _appointmentSchemaToDto: AppointmentDto = null as unknown as z.infer<typeof AppointmentDtoSchema>;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _appointmentMapperToDomain: Appointment = null as unknown as ReturnType<typeof mapAppointmentDto>;

describe('Appointment contract: OpenAPI → zod → mapper → domain', () => {
  const appointmentFixture: AppointmentDto = {
    id: 1,
    patient_id: 100,
    doctor_id: 50,
    department: 'cardiology',
    appointment_date: '2024-01-15',
    appointment_time: '10:00',
    notes: 'Regular checkup',
    status: 'scheduled',
    visit_type: 'paid',
    payment_type: 'cash',
    services: ['consultation', 'ecg'],
    payment_amount: 150000,
    payment_currency: 'UZS',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('fixture passes zod schema validation', () => {
    const parsed = AppointmentDtoSchema.parse(appointmentFixture);
    expect(parsed.id).toBe(1);
    expect(parsed.patient_id).toBe(100);
  });

  it('mapper transforms fixture to domain Appointment', () => {
    const appt = mapAppointmentDto(appointmentFixture);
    expect(appt.id).toBe(1);
    expect(appt.patient_id).toBe(100);
    expect(appt.services).toEqual([
      { code: 'consultation', name: 'consultation' },
      { code: 'ecg', name: 'ecg' },
    ]);
  });

  it('mapper output satisfies domain Appointment type', () => {
    const appt: Appointment = mapAppointmentDto(appointmentFixture);
    expect(appt).toBeDefined();
  });

  it('zod schema requires all OpenAPI-required fields', () => {
    const requiredFields: (keyof AppointmentDto)[] = [
      'id', 'patient_id', 'appointment_date', 'status', 'created_at',
    ];
    for (const field of requiredFields) {
      const partial = { ...appointmentFixture };
      delete partial[field];
      expect(() => AppointmentDtoSchema.parse(partial)).toThrow();
    }
  });
});

// ============================================================================
// Billing pipeline contract (Invoice + Payment)
// ============================================================================

import { InvoiceDtoSchema, PaymentDtoSchema } from '../../schemas/billingSchema';
import { mapInvoiceDto, mapPaymentDto } from '../../billing';
import type { Invoice, Payment } from '../../../../types/domain/billing';

// Type-level contracts
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _invoiceMapperToDomain: Invoice = null as unknown as ReturnType<typeof mapInvoiceDto>;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _paymentMapperToDomain: Payment = null as unknown as ReturnType<typeof mapPaymentDto>;

describe('Billing contract: zod → mapper → domain', () => {
  const invoiceFixture = {
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

  const paymentFixture = {
    id: 1,
    invoice_id: 100,
    patient_id: 200,
    amount: 50000,
    method: 'click',
    status: 'completed',
    transaction_id: 'tx-123',
    created_at: '2024-01-01T00:00:00Z',
  };

  it('invoice fixture passes zod schema validation', () => {
    const parsed = InvoiceDtoSchema.parse(invoiceFixture);
    expect(parsed.id).toBe(123);
  });

  it('invoice mapper transforms fixture to domain Invoice', () => {
    const invoice: Invoice = mapInvoiceDto(invoiceFixture);
    expect(invoice).toBeDefined();
    expect(String(invoice.id)).toBe('123');
  });

  it('payment fixture passes zod schema validation', () => {
    const parsed = PaymentDtoSchema.parse(paymentFixture);
    expect(parsed.id).toBe(1);
  });

  it('payment mapper transforms fixture to domain Payment', () => {
    const payment: Payment = mapPaymentDto(paymentFixture);
    expect(payment).toBeDefined();
    expect(String(payment.id)).toBe('1');
  });

  it('invoice schema accepts invoice_id as alternative to id', () => {
    const { id: _, ...withoutId } = invoiceFixture;
    const withInvoiceId = { ...withoutId, invoice_id: 999 };
    const parsed = InvoiceDtoSchema.parse(withInvoiceId);
    expect(parsed.invoice_id).toBe(999);
  });

  it('payment schema accepts payment_id as alternative to id', () => {
    const { id: _, ...withoutId } = paymentFixture;
    const withPaymentId = { ...withoutId, payment_id: 888 };
    const parsed = PaymentDtoSchema.parse(withPaymentId);
    expect(parsed.payment_id).toBe(888);
  });
});

// ============================================================================
// Drift detection: zod schema keys vs OpenAPI type keys
// ============================================================================

describe('Drift detection: schema ↔ OpenAPI field coverage', () => {
  it('Patient zod schema covers all OpenAPI-required fields', () => {
    // These are the required fields in the OpenAPI Patient schema.
    // If the backend adds a new required field, this test must be updated.
    const openApiRequiredFields = ['id', 'last_name', 'first_name', 'created_at'];

    // Get the zod schema shape
    const shape = PatientDtoSchema.shape;
    for (const field of openApiRequiredFields) {
      expect(shape, `zod schema missing field '${field}'`).toHaveProperty(field);
    }
  });

  it('Appointment zod schema covers all OpenAPI-required fields', () => {
    const openApiRequiredFields = [
      'id', 'patient_id', 'appointment_date', 'status', 'created_at',
    ];

    const shape = AppointmentDtoSchema.shape;
    for (const field of openApiRequiredFields) {
      expect(shape, `zod schema missing field '${field}'`).toHaveProperty(field);
    }
  });

  it('Patient zod schema covers all OpenAPI-optional fields', () => {
    // Optional fields in OpenAPI Patient schema
    const openApiOptionalFields = [
      'full_name', 'middle_name', 'birth_date', 'sex',
      'phone', 'email', 'doc_type', 'doc_number', 'address',
    ];

    const shape = PatientDtoSchema.shape;
    for (const field of openApiOptionalFields) {
      expect(shape, `zod schema missing field '${field}'`).toHaveProperty(field);
    }
  });

  it('Appointment zod schema covers all OpenAPI-optional fields', () => {
    const openApiOptionalFields = [
      'doctor_id', 'department', 'appointment_time', 'notes',
      'visit_type', 'payment_type', 'services', 'payment_amount',
      'payment_currency', 'payment_provider', 'payment_transaction_id',
      'payment_webhook_id', 'payment_processed_at', 'updated_at', 'patient_name',
    ];

    const shape = AppointmentDtoSchema.shape;
    for (const field of openApiOptionalFields) {
      expect(shape, `zod schema missing field '${field}'`).toHaveProperty(field);
    }
  });
});
