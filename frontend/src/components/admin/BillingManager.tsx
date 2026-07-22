import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Textarea,
  Skeleton,
  MacOSEmptyState,
  Select,
  Checkbox } from '../ui/macos';
import {
  Plus,

  Trash2,
  Send,
  Eye,

  DollarSign,
  CreditCard,
  FileText,

  Clock,

  TrendingUp,
  Settings,
  Save,
  X,
  CheckCircle,
  AlertCircle,
  XCircle } from
'lucide-react';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import { sanitizePrintableHtml } from '../../utils/printWindow';  // PR-35 / P0-7
import { useTranslation } from '../../i18n/useTranslation';

const getInvoiceTypeOptions = (t) => [
  { value: 'standard', label: t('admin2.bill_inv_type_standard') },
  { value: 'recurring', label: t('admin2.bill_inv_type_recurring') },
  { value: 'advance', label: t('admin2.bill_inv_type_advance') },
  { value: 'correction', label: t('admin2.bill_inv_type_correction') }
];

const getPaymentMethodOptions = (t) => [
  { value: 'cash', label: t('admin2.bill_pay_method_cash') },
  { value: 'card', label: t('admin2.bill_pay_method_card') },
  { value: 'bank_transfer', label: t('admin2.bill_pay_method_bank_transfer') },
  { value: 'online', label: t('admin2.bill_pay_method_online') },
  { value: 'insurance', label: t('admin2.bill_pay_method_insurance') },
  { value: 'installment', label: t('admin2.bill_pay_method_installment') }
];

const toNullableInteger = (value) => {
  if (value === '' || value === null || value === undefined) {
    return null;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
};

const buildInvoicePayload = (form) => ({
  ...form,
  patient_id: toNullableInteger(form.patient_id),
  visit_id: toNullableInteger(form.visit_id),
  appointment_id: toNullableInteger(form.appointment_id),
  due_days: toNullableInteger(form.due_days) ?? 30,
  recurrence_interval: toNullableInteger(form.recurrence_interval) ?? 1,
  items: form.items.map((item) => ({
    ...item,
    quantity: toNullableInteger(item.quantity) ?? 1,
    unit_price: Number(item.unit_price) || 0
  }))
});

const buildPaymentPayload = (form) => ({
  ...form,
  invoice_id: toNullableInteger(form.invoice_id),
  amount: Number(form.amount) || 0
});

const BillingManager = () => {
  const [activeTab, setActiveTab] = useState('invoices');
  interface Invoice {
    id: string | number;
    invoice_number?: string;
    status?: string;
    invoice_type?: string;
    patient_id?: string | number;
    issue_date?: string;
    due_date?: string;
    total_amount?: number;
    balance?: number;
    [k: string]: unknown;
  }
  interface Payment {
    id: string | number;
    payment_number?: string;
    is_confirmed?: boolean;
    invoice_id?: string | number;
    patient_id?: string | number;
    amount?: number;
    payment_method?: string;
    payment_date?: string;
    [k: string]: unknown;
  }
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [analytics, setAnalytics] = useState<{ summary?: { total_invoices?: number; total_amount?: number; paid_amount?: number; overdue_amount?: number; recent_invoices?: unknown[]; [k: string]: unknown }; status_breakdown?: Array<{ status?: string; count?: number; [k: string]: unknown }>; [k: string]: unknown } | null>(null);
  const [, setSettings] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [showRecordPayment, setShowRecordPayment] = useState(false);

  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const invoiceTypeOptions = getInvoiceTypeOptions(t);
  const paymentMethodOptions = getPaymentMethodOptions(t);
  const invoiceTypeLabels = Object.fromEntries(
    invoiceTypeOptions.map((option) => [option.value, option.label])
  );
  const paymentMethodLabels = Object.fromEntries(
    paymentMethodOptions.map((option) => [option.value, option.label])
  );

  // Форма для создания счета
  const [invoiceForm, setInvoiceForm] = useState({
    patient_id: '',
    visit_id: '',
    appointment_id: '',
    invoice_type: 'standard',
    items: [{ description: '', quantity: 1, unit_price: 0 }],
    description: '',
    notes: '',
    due_days: 30,
    auto_send: false,
    send_reminders: true,
    is_recurring: false,
    recurrence_type: 'monthly',
    recurrence_interval: 1
  });

  // Форма для записи платежа
  const [paymentForm, setPaymentForm] = useState<{
    invoice_id: string | number;
    amount: number;
    payment_method: string;
    reference_number: string;
    description: string;
    notes: string;
  }>({
    invoice_id: '',
    amount: 0,
    payment_method: 'cash',
    reference_number: '',
    description: '',
    notes: ''
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      if (activeTab === 'invoices') {
        const response = (await api.get('/billing/invoices')) as import('axios').AxiosResponse<unknown[]>;
        setInvoices(response.data as Invoice[]);
      } else if (activeTab === 'payments') {
        const response = (await api.get('/billing/payments')) as import('axios').AxiosResponse<unknown[]>;
        setPayments(response.data as Payment[]);
      } else if (activeTab === 'analytics') {
        const response = (await api.get('/billing/analytics')) as import('axios').AxiosResponse<Record<string, unknown>>;
        setAnalytics(response.data);
      } else if (activeTab === 'settings') {
        const response = (await api.get('/billing/settings')) as import('axios').AxiosResponse<Record<string, unknown>>;
        setSettings(response.data);
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error(t('admin2.bill_load_error'));
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreateInvoice = async () => {
    try {
      await api.post('/billing/invoices', buildInvoicePayload(invoiceForm));
      toast.success(t('admin2.bill_inv_created'));
      setShowCreateInvoice(false);
      setInvoiceForm({
        patient_id: '',
        visit_id: '',
        appointment_id: '',
        invoice_type: 'standard',
        items: [{ description: '', quantity: 1, unit_price: 0 }],
        description: '',
        notes: '',
        due_days: 30,
        auto_send: false,
        send_reminders: true,
        is_recurring: false,
        recurrence_type: 'monthly',
        recurrence_interval: 1
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка создания счета:', error);
      toast.error(error.response?.data?.detail || t('admin2.bill_inv_create_error'));
    }
  };

  const handleRecordPayment = async () => {
    try {
      await api.post('/billing/payments', buildPaymentPayload(paymentForm));
      toast.success(t('admin2.bill_pay_recorded'));
      setShowRecordPayment(false);
      setPaymentForm({
        invoice_id: '',
        amount: 0,
        payment_method: 'cash',
        reference_number: '',
        description: '',
        notes: ''
      });
      loadData();
    } catch (error) {
      logger.error('Ошибка записи платежа:', error);
      toast.error(error.response?.data?.detail || t('admin2.bill_pay_record_error'));
    }
  };

  const handleSendInvoice = async (invoiceId) => {
    try {
      await api.post(`/billing/invoices/${invoiceId}/send`);
      toast.success(t('admin2.bill_inv_sent'));
    } catch (error) {
      logger.error('Ошибка отправки счета:', error);
      toast.error(error.response?.data?.detail || t('admin2.bill_inv_send_error'));
    }
  };

  const handleViewInvoiceHTML = async (invoiceId) => {
    try {
      const response = (await api.get(`/billing/invoices/${invoiceId}/html`)) as import('axios').AxiosResponse<Record<string, unknown>>;
      // PR-35 / P0-7: Sanitize backend HTML before writing to a new window.
      // Previously: document.write(response.data.html) wrote raw backend
      // output to a new window — XSS if backend was compromised or if a
      // patient name contained <script>. Now: DOMPurify strips scripts,
      // event handlers, and dangerous tags via sanitizePrintableHtml().
      const newWindow = window.open('', '_blank');
      if (!newWindow) {
        toast.error('Popup blocked. Allow popups for this site to view invoices.');
        return;
      }
      newWindow.document.write(sanitizePrintableHtml(response.data.html));
      newWindow.document.close();
    } catch (error) {
      logger.error('Ошибка получения HTML счета:', error);
      toast.error(error.response?.data?.detail || t('admin2.bill_inv_html_error'));
    }
  };

  const addInvoiceItem = () => {
    setInvoiceForm({
      ...invoiceForm,
      items: [...invoiceForm.items, { description: '', quantity: 1, unit_price: 0 }]
    });
  };

  const removeInvoiceItem = (index) => {
    const newItems = invoiceForm.items.filter((_, i) => i !== index);
    setInvoiceForm({ ...invoiceForm, items: newItems });
  };

  const updateInvoiceItem = (index, field, value) => {
    const newItems = [...invoiceForm.items];
    newItems[index][field] = value;
    setInvoiceForm({ ...invoiceForm, items: newItems });
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'draft': { variant: 'secondary', label: t('admin2.bill_status_draft'), icon: FileText },
      'pending': { variant: 'warning', label: t('admin2.bill_status_pending'), icon: Clock },
      'paid': { variant: 'success', label: t('admin2.bill_status_paid'), icon: CheckCircle },
      'partially_paid': { variant: 'info', label: t('admin2.bill_status_partially_paid'), icon: AlertCircle },
      'overdue': { variant: 'danger', label: t('admin2.bill_status_overdue'), icon: XCircle },
      'cancelled': { variant: 'secondary', label: t('admin2.bill_status_cancelled'), icon: X },
      'refunded': { variant: 'warning', label: t('admin2.bill_status_refunded'), icon: AlertCircle }
    };

    const config = statusConfig[status] || statusConfig['draft'];
    const Icon = config.icon;

    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="w-3 h-3" />
        {config.label}
      </Badge>);

  };

  const renderInvoicesTab = () =>
  <div className="flex flex-col gap-6">
      {/* Заголовок и кнопки */}
      <div className="admin-d-flex-jc-between-ai-center">
        <div>
          <h3 className="admin-m-0-0-4px-0-primary-fs-lg-fw-semi">
            {t('admin2.bill_invoices_title')}
          </h3>
          <p className="admin-m-0-secondary-fs-sm">
            {t('admin2.bill_invoices_subtitle')}
          </p>
        </div>
        <Button
        onClick={() => setShowCreateInvoice(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          {t('admin2.bill_create_inv_btn')}
        </Button>
      </div>

      {/* Список счетов */}
      <div className="admin-d-grid-gap-16">
        {invoices.length === 0 ?
      <MacOSEmptyState
        type="invoice"
        title={t('admin2.bill_empty_invoices_title')}
        description={t('admin2.bill_empty_invoices_desc')}
        action={
        <Button onClick={() => setShowCreateInvoice(true)}>
                <Plus size={16} className="mr-2" />
                {t('admin2.bill_create_first_inv_btn')}
              </Button>
        } /> :


      invoices.map((invoice) =>
      <MacOSCard key={invoice.id} className="p-0">
              <div className="admin-d-flex-jc-between-ai-start">
                <div className="admin-flex-1">
                  <div className="admin-d-flex-ai-center-gap-8-mb-12">
                    <h4 className="admin-m-0-primary-fs-var-mac-font-size-md-fw-semi">
                      {t('admin2.bill_inv_number', { number: invoice.invoice_number })}
                    </h4>
                    {getStatusBadge(invoice.status)}
                    <Badge variant="outline">
                      {invoiceTypeLabels[invoice.invoice_type] || invoice.invoice_type}
                    </Badge>
                  </div>

                  <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-8-fs-sm-secondary-mb-8">
                    <div>{t('admin2.bill_patient_id')} {invoice.patient_id}</div>
                    <div>{t('admin2.bill_date')} {new Date(invoice.issue_date).toLocaleDateString()}</div>
                    <div>{t('admin2.bill_due_date')} {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : t('admin2.bill_not_specified')}</div>
                    <div>{t('admin2.bill_amount')} {invoice.total_amount.toLocaleString()} {t('admin2.bill_currency')}</div>
                  </div>

                  {invoice.balance > 0 &&
            <div className="admin-fs-sm-error">
                      {t('admin2.bill_balance_due')} {invoice.balance.toLocaleString()} {t('admin2.bill_currency')}
                    </div>
            }
                </div>

                <div className="admin-d-flex-gap-8">
                  <Button
              variant="outline"
              onClick={() => handleViewInvoiceHTML(invoice.id)}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-5"
              title={t('admin2.bill_view_inv_title')}
              type="button"
              aria-label={t('admin2.bill_view_inv_aria', { number: invoice.invoice_number || invoice.id })}>

                    <Eye aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => handleSendInvoice(invoice.id)}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-4"
              title={t('admin2.bill_send_inv_title')}
              type="button"
              aria-label={t('admin2.bill_send_inv_aria', { number: invoice.invoice_number || invoice.id })}>

                    <Send aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => {
                setPaymentForm({ ...paymentForm, invoice_id: invoice.id, amount: invoice.balance });
                setShowRecordPayment(true);
              }}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-3"
              title={t('admin2.bill_record_pay_title')}
              type="button"
              aria-label={t('admin2.bill_record_pay_aria', { number: invoice.invoice_number || invoice.id })}>

                    <CreditCard aria-hidden="true" size={16} />
                  </Button>
                </div>
              </div>
            </MacOSCard>
      )
      }
      </div>

      {/* Форма создания счета */}
      {showCreateInvoice &&
    <MacOSCard className="p-0">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-3">
            <h4 className="admin-m-0-primary-fs-lg-fw-semi-1">
              {t('admin2.bill_create_inv_btn')}
            </h4>
            <Button
          variant="outline"
          onClick={() => setShowCreateInvoice(false)}
          type="button"
          title={t('admin2.bill_close_create_inv_form_aria')}
          aria-label={t('admin2.bill_close_create_inv_form_aria')}
          className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-2">
          
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-16-1">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-9">
                {t('admin2.bill_patient_id_label')}
              </label>
              <Input
            type="number"
            value={invoiceForm.patient_id}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInvoiceForm({ ...invoiceForm, patient_id: e.target.value })}
            placeholder={t('admin2.bill_patient_id_ph')} />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-8">
                {t('admin2.bill_inv_type_label')}
              </label>
              <Select
            value={invoiceForm.invoice_type}
            onChange={(value: unknown) => setInvoiceForm({ ...invoiceForm, invoice_type: String(value) })}
            options={invoiceTypeOptions}
            size="large" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-7">
                {t('admin2.bill_due_days_label')}
              </label>
              <Input
            type="number"
            value={invoiceForm.due_days}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInvoiceForm({ ...invoiceForm, due_days: parseInt(e.target.value) })}
            placeholder="30" />
          
            </div>

            <div className="admin-d-flex-ai-center-gap-16">
              <label className="admin-d-flex-ai-center-gap-8-fs-sm-primary-2">
                <Checkbox aria-label="Auto send invoice" checked={invoiceForm.auto_send} onChange={(checked: boolean) => setInvoiceForm({ ...invoiceForm, auto_send: checked })}
              className="admin-m-0" />
            
                {t('admin2.bill_auto_send_label')}
              </label>
              <label className="admin-d-flex-ai-center-gap-8-fs-sm-primary-1">
                <Checkbox aria-label="Send payment reminders" checked={invoiceForm.send_reminders} onChange={(checked: boolean) => setInvoiceForm({ ...invoiceForm, send_reminders: checked })}
              className="admin-m-0" />
            
                {t('admin2.bill_reminders_label')}
              </label>
            </div>
          </div>

          {/* Позиции счета */}
          <div className="mb-4">
            <div className="admin-d-flex-jc-between-ai-center-mb-8">
              <label className="admin-fs-sm-fw-med-primary">
                {t('admin2.bill_inv_items_label')}
              </label>
              <Button
            onClick={addInvoiceItem}
            className="admin-d-flex-ai-center-gap-4-p-4px-8px-fs-xs">
            
                <Plus size={14} />
                {t('admin2.bill_add_item_btn')}
              </Button>
            </div>

            {invoiceForm.items.map((item, index) =>
        <div key={index} className="admin-d-grid-gtc-2fr-1fr-1fr-auto-gap-8-mb-8-p-12-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary">
                <Input
            placeholder={t('admin2.bill_item_desc_ph')}
            value={item.description}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateInvoiceItem(index, 'description', e.target.value)} />
          
                <Input
            type="number"
            placeholder={t('admin2.bill_item_qty_ph')}
            value={item.quantity}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateInvoiceItem(index, 'quantity', parseFloat(e.target.value))} />
          
                <Input
            type="number"
            placeholder={t('admin2.bill_item_price_ph')}
            value={item.unit_price}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateInvoiceItem(index, 'unit_price', parseFloat(e.target.value))} />
          
                <Button
            variant="outline"
            onClick={() => removeInvoiceItem(index)}
            type="button"
            title={t('admin2.bill_remove_item_aria', { index: index + 1 })}
            aria-label={t('admin2.bill_remove_item_aria', { index: index + 1 })}
            disabled={invoiceForm.items.length === 1}
            className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-1">
            
                  <Trash2 aria-hidden="true" size={16} />
                </Button>
              </div>
        )}
          </div>

          <div className="admin-d-grid-gtc-1fr-gap-16-mb-16">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-6">
                {t('admin2.bill_desc_label')}
              </label>
              <Textarea
            value={invoiceForm.description}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setInvoiceForm({ ...invoiceForm, description: e.target.value })}
            placeholder={t('admin2.bill_inv_desc_ph')}
            rows={3} />
          
            </div>
          </div>

          <div className="admin-d-flex-jc-end-gap-8-3">
            <Button
          variant="outline"
          onClick={() => setShowCreateInvoice(false)}>
          
              {t('admin2.bill_cancel_btn')}
            </Button>
            <Button
          onClick={handleCreateInvoice}
          className="flex items-center justify-center gap-2">
          
              <Save size={16} />
              {t('admin2.bill_create_btn')}
            </Button>
          </div>
        </MacOSCard>
    }

      {/* Форма записи платежа */}
      {showRecordPayment &&
    <MacOSCard className="p-0">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-2">
            <h4 className="admin-m-0-primary-fs-lg-fw-semi">
              {t('admin2.bill_record_pay_modal_title')}
            </h4>
            <Button
          variant="outline"
          onClick={() => setShowRecordPayment(false)}
          type="button"
          title={t('admin2.bill_close_pay_form_aria')}
          aria-label={t('admin2.bill_close_pay_form_aria')}
          className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center">
          
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-16">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-5">
                {t('admin2.bill_inv_id_label')}
              </label>
              <Input
            type="number"
            value={paymentForm.invoice_id}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPaymentForm({ ...paymentForm, invoice_id: e.target.value })}
            placeholder={t('admin2.bill_inv_id_ph')} />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-4">
                {t('admin2.bill_pay_amount_label')}
              </label>
              <Input
            type="number"
            value={paymentForm.amount}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPaymentForm({ ...paymentForm, amount: parseFloat(e.target.value) })}
            placeholder="0" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-3">
                {t('admin2.bill_pay_method_label')}
              </label>
              <Select
            value={paymentForm.payment_method}
            onChange={(value: unknown) => setPaymentForm({ ...paymentForm, payment_method: String(value) })}
            options={paymentMethodOptions}
            size="large" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-2">
                {t('admin2.bill_ref_num_label')}
              </label>
              <Input
            value={paymentForm.reference_number}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPaymentForm({ ...paymentForm, reference_number: e.target.value })}
            placeholder={t('admin2.bill_ref_num_ph')} />
          
            </div>

            <div className="admin-gc-1-1">
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-1">
                {t('admin2.bill_desc_label')}
              </label>
              <Textarea
            value={paymentForm.description}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setPaymentForm({ ...paymentForm, description: e.target.value })}
            placeholder={t('admin2.bill_pay_desc_ph')}
            rows={3} />
          
            </div>
          </div>

          <div className="admin-d-flex-jc-end-gap-8-2">
            <Button
          variant="outline"
          onClick={() => setShowRecordPayment(false)}>
          
              {t('admin2.bill_cancel_btn')}
            </Button>
            <Button
          onClick={handleRecordPayment}
          className="flex items-center justify-center gap-2">
          
              <Save size={16} />
              {t('admin2.bill_record_btn')}
            </Button>
          </div>
        </MacOSCard>
    }
    </div>;


  const renderPaymentsTab = () =>
  <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">{t('admin2.bill_payments_title')}</h3>
        <p className="text-gray-600">{t('admin2.bill_payments_subtitle')}</p>
      </div>

      <div className="grid gap-4">
        {payments.map((payment) =>
      <MacOSCard key={payment.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-medium">{t('admin2.bill_pay_number', { number: payment.payment_number })}</h4>
                  <Badge variant={payment.is_confirmed ? 'success' : 'warning'}>
                    {payment.is_confirmed ? t('admin2.bill_pay_confirmed') : t('admin2.bill_pay_pending_confirm')}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
                  <div>{t('admin2.bill_inv_id_short')} {payment.invoice_id}</div>
                  <div>{t('admin2.bill_patient_id')} {payment.patient_id}</div>
                  <div>{t('admin2.bill_amount')} {payment.amount.toLocaleString()} {t('admin2.bill_currency')}</div>
                  <div>{t('admin2.bill_method_short')} {paymentMethodLabels[payment.payment_method] || payment.payment_method}</div>
                  <div>{t('admin2.bill_date')} {new Date(payment.payment_date).toLocaleDateString()}</div>
                  {payment.reference_number &&
              <div>{t('admin2.bill_ref_short')} {String(payment.reference_number ?? '')}</div>
              }
                </div>
              </div>
            </div>
          </MacOSCard>
      )}
      </div>
    </div>;


  const renderAnalyticsTab = () =>
  <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">{t('admin2.bill_analytics_title')}</h3>
        <p className="text-gray-600">{t('admin2.bill_analytics_subtitle')}</p>
      </div>

      {analytics &&
    <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-5 h-5 text-blue-500" />
                <h4 className="font-medium">{t('admin2.bill_stat_total_inv')}</h4>
              </div>
              <div className="text-2xl font-bold">{analytics.summary?.total_invoices || 0}</div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">{t('admin2.bill_stat_total_amount')}</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.total_amount?.toLocaleString() || 0} {t('admin2.bill_currency')}
              </div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">{t('admin2.bill_stat_paid')}</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.paid_amount?.toLocaleString() || 0} {t('admin2.bill_currency')}
              </div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-5 h-5 text-red-500" />
                <h4 className="font-medium">{t('admin2.bill_stat_overdue')}</h4>
              </div>
              <div className="text-2xl font-bold text-red-600">
                {analytics.summary?.overdue_amount?.toLocaleString() || 0} {t('admin2.bill_currency')}
              </div>
            </MacOSCard>
          </div>

          {analytics.status_breakdown &&
      <MacOSCard className="p-4">
              <h4 className="font-medium mb-4">{t('admin2.bill_status_breakdown')}</h4>
              <div className="space-y-2">
                {analytics.status_breakdown.map((stat, index) =>
          <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="font-medium">{stat.status}</span>
                    <div className="flex gap-4 text-sm">
                      <span>{t('admin2.bill_count')} {stat.count}</span>
                      <span>{t('admin2.bill_amount')} {stat.amount?.toLocaleString() || 0} {t('admin2.bill_currency')}</span>
                    </div>
                  </div>
          )}
              </div>
            </MacOSCard>
      }
        </>
    }
    </div>;


  const tabs = [
  { id: 'invoices', label: t('admin2.bill_tab_invoices'), icon: FileText },
  { id: 'payments', label: t('admin2.bill_tab_payments'), icon: CreditCard },
  { id: 'analytics', label: t('admin2.bill_tab_analytics'), icon: TrendingUp },
  { id: 'settings', label: t('admin2.bill_tab_settings'), icon: Settings }];


  return (
    <div className="admin-p-0-maxw-1400-m-0-auto">
      <div className="admin-d-flex-ai-center-gap-16-mb-24">
        <DollarSign size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-m-0-primary-fs-xl-fw-bold">
            {t('admin2.bill_page_title')}
          </h2>
          <p className="admin-m-4px-0-0-0-secondary-fs-sm">
            {t('admin2.bill_page_subtitle')}
          </p>
        </div>
      </div>

      {/* Табы */}
      <div className="admin-d-flex-bd-b-1px-solid-var-mac-bo-mb-24">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-p-16px-24px-bd-none-bg-none-cur-pointer-d-flex-ai-center-gap-8-fs-sm-tr-all-var-mac-duration-bd-b-dyn-col-dyn-fw-dyn" style={{ '--admin-bd-b0': activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent', '--admin-col1': activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)', '--admin-fw2': activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)' } as CSSProperties}>
              
              <Icon size={16} />
              {tab.label}
            </button>);

        })}
      </div>

      {/* Контент */}
      {loading ?
      <Skeleton type="card" count={3} /> :

      <>
          {activeTab === 'invoices' && renderInvoicesTab()}
          {activeTab === 'payments' && renderPaymentsTab()}
          {activeTab === 'analytics' && renderAnalyticsTab()}
          {activeTab === 'settings' &&
        <MacOSEmptyState
          type="settings"
          title={t('admin2.bill_settings_title')}
          description={t('admin2.bill_settings_desc')} />

        }
        </>
      }
    </div>);

};

export default BillingManager;
