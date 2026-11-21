import { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AppointmentWizardV2 from '../AppointmentWizardV2';
import { useRegistrarWizard } from '../../../pages/registrar/useRegistrarWizard';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  createCart: vi.fn(),
  getPatient: vi.fn(),
  confirm: vi.fn(),
  openPayment: vi.fn(),
  openPrint: vi.fn(),
  reload: vi.fn(),
  reloadIntegrated: vi.fn(),
  role: 'Admin',
}));

vi.mock('../../../api/client', () => ({ api: { get: mocks.get, post: mocks.post } }));
vi.mock('../../../api/registrar', () => ({
  fetchRegistrarDoctors: async () => ({ doctors: [] }),
  fetchRegistrarServices: async () => ({ services_by_group: {
    lab: [{ id: 4, name: 'Synthetic laboratory test', price: 120, service_code: 'L04', queue_tag: 'lab' }],
  } }),
}));
vi.mock('../../../hooks/usePatientsApi', () => ({
  usePatientsApi: () => ({
    checkAuthProbe: async () => true,
    createRegistrarCart: mocks.createCart,
    getPatient: mocks.getPatient,
  }),
}));
vi.mock('../../../hooks/useQueueApi', () => ({ useQueueApi: () => ({}) }));
vi.mock('../../../utils/tokenManager', () => ({ default: { getAccessToken: () => 'synthetic-session' } }));
vi.mock('../../common/RoleGuard', () => ({
  useRoleAccess: () => ({ hasRole: (roles: string[]) => roles.includes(mocks.role) }),
}));
vi.mock('../../common/ConfirmDialog', () => ({ useConfirm: () => [mocks.confirm, null] }));
vi.mock('../../../i18n/useTranslation', () => {
  const t = (key: string, options?: Record<string, unknown>) => options?.invoice ? `${key} ${options.invoice}` : key;
  return { useTranslation: () => ({ t }) };
});
vi.mock('../PatientStepV2', () => ({
  default: ({ onSelectPatient }: { onSelectPatient: (patient: unknown) => void }) => (
    <button onClick={() => onSelectPatient({ id: 18, fio: 'Synthetic Patient', gender: 'male' })}>Select test patient</button>
  ),
}));
vi.mock('../CartStepV2', () => ({
  default: ({ onUpdateCart }: { onUpdateCart: (field: string, value: unknown) => void }) => (
    <button onClick={() => onUpdateCart('items', [{ service_id: 4, quantity: 1, service_price: 120 }])}>
      Add test service
    </button>
  ),
}));

const createAction = 'misc.aw_benefit_create_action';
const approvalAction = 'misc.aw_benefit_approve';
const continueAction = 'misc.aw_benefit_continue';
const decisionPath = '/discount-benefits/benefits/encounter/apply';
const summaryPath = '/registrar/records/payment-summary';
const quotePath = '/registrar/cart/quote';
const savedCart = { success: true, invoice_id: 41, total_amount: '120.00', visit_ids: [71, 72] };
const approval = { application_id: 15, invoice_id: 41, gross_total: '120.00', benefit_total: '30.25', total_amount: '89.75' };
const groupedRecords = [
  { record_kind: 'visit', record_id: 71 },
  { record_kind: 'visit', record_id: 72 },
];
const key = (value: string) => value;

function WizardHarness() {
  const [open, setOpen] = useState(true);
  const flow = useRegistrarWizard({
    setPaymentDialog: mocks.openPayment,
    setPrintDialog: mocks.openPrint,
    loadAppointmentsRef: { current: mocks.reload },
    loadIntegratedData: mocks.reloadIntegrated,
    tI18n: key,
  });
  return (
    <AppointmentWizardV2
      isOpen={open}
      onClose={() => setOpen(false)}
      onComplete={flow.handleWizardComplete}
      isProcessing={flow.isProcessing}
      setIsProcessing={flow.setIsProcessing}
    />
  );
}

function postWithoutDecision(url: string) {
  if (url === quotePath) return Promise.resolve({ data: {
    items: [{ service_id: 4, service_name: 'Synthetic laboratory test', quantity: 1, final_price: 120 }],
    total_amount: '120.00', currency: 'UZS', approval_status: 'approved', quote_token: 'synthetic-quote',
  } });
  return Promise.reject(new Error(`Unexpected test request to ${url}`));
}

function balance(total: string, visitIds = [71, 72]) {
  return { data: {
    total_amount: total, paid_amount: '0.00', remaining_amount: total, can_pay: Number(total) > 0,
    visits: visitIds.map((visitId) => ({ visit_id: visitId })),
  } };
}

async function prepareCart() {
  render(<WizardHarness />);
  fireEvent.click(screen.getByRole('button', { name: 'Select test patient' }));
  fireEvent.click(screen.getByRole('button', { name: 'misc.aw_next' }));
  fireEvent.click(screen.getByRole('button', { name: 'Add test service' }));
  await waitFor(() => expect(mocks.post).toHaveBeenCalledWith(quotePath, expect.any(Object)));
}

async function openReview() {
  await prepareCart();
  fireEvent.click(await screen.findByRole('button', { name: createAction }));
  expect(await screen.findByRole('dialog', { name: 'misc.aw_benefit_title 41' })).toBeVisible();
  const benefitSelect = await screen.findByRole('combobox', { name: 'misc.aw_benefit_select' });
  expect(screen.getByRole('button', { name: approvalAction })).toBeDisabled();
  fireEvent.change(benefitSelect, { target: { value: '23' } });
  return benefitSelect;
}

describe('registrar benefit review and payment handoff', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.role = 'Admin';
    mocks.confirm.mockResolvedValue(true);
    mocks.getPatient.mockResolvedValue({ id: 18, sex: 'M' });
    mocks.createCart.mockResolvedValue(savedCart);
    mocks.get.mockResolvedValue({ data: { patient_benefits: [
      { id: 23, benefit: { name: 'Synthetic benefit' }, is_active: true, verified: true, document_number: 'SYNTHETIC_PRIVATE' },
      { id: 24, benefit: { name: 'Unverified benefit' }, is_active: true, verified: false },
    ] } });
    mocks.post.mockImplementation(postWithoutDecision);
  });

  it('persists the ordinary cart, then approves one selected assignment and opens payment at the server total', async () => {
    let resolveApproval: (response: { data: typeof approval }) => void = () => {};
    mocks.post.mockImplementation((url: string) => url === decisionPath
      ? new Promise((resolve) => { resolveApproval = resolve; })
      : postWithoutDecision(url));

    const selector = await openReview();
    expect(within(selector).getAllByRole('option')).toHaveLength(2);
    expect(screen.queryByText('SYNTHETIC_PRIVATE')).toBeNull();
    expect(mocks.confirm).toHaveBeenCalledWith(expect.objectContaining({
      description: expect.stringContaining('misc.aw_benefit_save_first'),
    }));
    expect(mocks.createCart).toHaveBeenCalledWith(
      expect.objectContaining({ patient_id: 18, all_free: false, discount_mode: 'none', quote_token: 'synthetic-quote' }),
      expect.objectContaining({ idempotencyKey: expect.any(String) }),
    );
    expect(mocks.get).toHaveBeenCalledWith('/discount-benefits/benefits/patient/18', expect.objectContaining({
      params: { active_only: true },
    }));
    expect(mocks.openPayment).not.toHaveBeenCalled();

    const approveButton = screen.getByRole('button', { name: approvalAction });
    fireEvent.click(approveButton);
    fireEvent.click(approveButton);
    fireEvent.keyDown(document.body, { key: 'Enter', ctrlKey: true });
    expect(mocks.createCart).toHaveBeenCalledTimes(1);
    expect(mocks.post.mock.calls.filter(([path]) => path === decisionPath)).toEqual([
      [decisionPath, { invoice_id: 41, patient_benefit_id: 23 }],
    ]);
    resolveApproval({ data: approval });
    expect(await screen.findByText('misc.aw_benefit_approved')).toBeVisible();
    expect(screen.queryByRole('button', { name: approvalAction })).toBeNull();
    expect(mocks.openPayment).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: continueAction }));

    expect(mocks.openPayment).toHaveBeenCalledWith(expect.objectContaining({
      row: expect.objectContaining({ invoice_id: 41, cost: 89.75, grouped_record_refs: groupedRecords }),
    }));
  });

  it('reconciles a lost response from the exact saved visit group without repeating the approval', async () => {
    mocks.post.mockImplementation((url: string) => {
      if (url === decisionPath) return Promise.reject(new Error('Synthetic response loss'));
      if (url === summaryPath) return Promise.resolve(balance('89.75', [72, 71]));
      return postWithoutDecision(url);
    });

    await openReview();
    fireEvent.click(screen.getByRole('button', { name: approvalAction }));
    expect(await screen.findByText('misc.aw_benefit_reconciled')).toBeVisible();
    expect(mocks.post).toHaveBeenCalledWith(summaryPath, { records: groupedRecords });
    expect(screen.queryByRole('button', { name: approvalAction })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: continueAction }));
    expect(mocks.openPayment).toHaveBeenCalledWith(expect.objectContaining({
      row: expect.objectContaining({ cost: 89.75 }),
    }));
  });

  it('returns to the refreshed worklist when the receipt and its recovery reference a different group', async () => {
    mocks.post.mockImplementation((url: string) => {
      if (url === decisionPath) return Promise.resolve({ data: { ...approval, invoice_id: 42 } });
      if (url === summaryPath) return Promise.resolve(balance('89.75', [71, 73]));
      return postWithoutDecision(url);
    });

    await openReview();
    fireEvent.click(screen.getByRole('button', { name: approvalAction }));
    expect(await screen.findByText('misc.aw_benefit_unknown_total')).toBeVisible();
    expect(screen.queryByRole('button', { name: continueAction })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'misc.aw_benefit_records' }));
    expect(mocks.reload).toHaveBeenCalledTimes(1);
    expect(mocks.openPayment).not.toHaveBeenCalled();
    expect(mocks.openPrint).not.toHaveBeenCalled();
  });

  it('can refresh an unverifiable balance and offers a ticket for a verified zero total', async () => {
    const readBalance = vi.fn()
      .mockResolvedValueOnce(balance('0.00', [71, 71]))
      .mockResolvedValueOnce(balance('0.00'));
    mocks.post.mockImplementation((url: string) => {
      if (url === decisionPath) return Promise.reject(new Error('Synthetic response loss'));
      if (url === summaryPath) return readBalance();
      return postWithoutDecision(url);
    });

    await openReview();
    fireEvent.click(screen.getByRole('button', { name: approvalAction }));
    expect(await screen.findByText('misc.aw_benefit_unknown_total')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'misc.aw_benefit_refresh_total' }));
    expect(await screen.findByText('misc.aw_benefit_reconciled')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: continueAction }));

    expect(readBalance).toHaveBeenCalledTimes(2);
    expect(mocks.openPayment).not.toHaveBeenCalled();
    expect(mocks.openPrint).toHaveBeenCalledWith(expect.objectContaining({
      type: 'ticket',
      data: expect.objectContaining({ invoice_id: 41, cost: 0, grouped_record_refs: groupedRecords }),
    }));
  });

  it('refreshes the worklist without opening payment when a saved cart response is unusable', async () => {
    mocks.createCart.mockResolvedValue(null);
    await prepareCart();
    fireEvent.click(await screen.findByRole('button', { name: createAction }));
    await waitFor(() => expect(mocks.reload).toHaveBeenCalledTimes(1));
    expect(mocks.createCart).toHaveBeenCalledTimes(1);
    expect(mocks.get).not.toHaveBeenCalled();
    expect(mocks.openPayment).not.toHaveBeenCalled();
    expect(mocks.openPrint).not.toHaveBeenCalled();
  });

  it('preserves the direct ordinary payment flow for a registrar', async () => {
    mocks.role = 'Registrar';
    await prepareCart();
    expect(screen.queryByRole('button', { name: createAction })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'misc.aw_finish' }));
    await waitFor(() => expect(mocks.openPayment).toHaveBeenCalledWith(expect.objectContaining({
      row: expect.objectContaining({ cost: 120 }),
    })));
    expect(mocks.get).not.toHaveBeenCalled();
    expect(mocks.post).not.toHaveBeenCalledWith(decisionPath, expect.anything());
  });
});
