import { useState, useEffect, useCallback } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Textarea,
  Skeleton,
  MacOSEmptyState,
  Select,
} from '../ui/macos';
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

const INVOICE_TYPE_OPTIONS = [
  { value: 'standard', label: 'Обычный' },
  { value: 'recurring', label: 'Периодический' },
  { value: 'advance', label: 'Авансовый' },
  { value: 'correction', label: 'Корректировочный' }
];

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'Наличные' },
  { value: 'card', label: 'Банковская карта' },
  { value: 'bank_transfer', label: 'Банковский перевод' },
  { value: 'online', label: 'Онлайн платеж' },
  { value: 'insurance', label: 'Страховка' },
  { value: 'installment', label: 'Рассрочка' }
];

const INVOICE_TYPE_LABELS = Object.fromEntries(
  INVOICE_TYPE_OPTIONS.map((option) => [option.value, option.label])
);

const PAYMENT_METHOD_LABELS = Object.fromEntries(
  PAYMENT_METHOD_OPTIONS.map((option) => [option.value, option.label])
);

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
  const [invoices, setInvoices] = useState([]);
  const [payments, setPayments] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [showRecordPayment, setShowRecordPayment] = useState(false);

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
  const [paymentForm, setPaymentForm] = useState({
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
        const response = await api.get('/billing/invoices');
        setInvoices(response.data);
      } else if (activeTab === 'payments') {
        const response = await api.get('/billing/payments');
        setPayments(response.data);
      } else if (activeTab === 'analytics') {
        const response = await api.get('/billing/analytics');
        setAnalytics(response.data);
      } else if (activeTab === 'settings') {
        const response = await api.get('/billing/settings');
        setSettings(response.data);
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
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
      toast.success('Счет создан успешно');
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
      toast.error(error.response?.data?.detail || 'Ошибка создания счета');
    }
  };

  const handleRecordPayment = async () => {
    try {
      await api.post('/billing/payments', buildPaymentPayload(paymentForm));
      toast.success('Платеж записан успешно');
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
      toast.error(error.response?.data?.detail || 'Ошибка записи платежа');
    }
  };

  const handleSendInvoice = async (invoiceId) => {
    try {
      await api.post(`/billing/invoices/${invoiceId}/send`);
      toast.success('Счет отправлен');
    } catch (error) {
      logger.error('Ошибка отправки счета:', error);
      toast.error(error.response?.data?.detail || 'Ошибка отправки счета');
    }
  };

  const handleViewInvoiceHTML = async (invoiceId) => {
    try {
      const response = await api.get(`/billing/invoices/${invoiceId}/html`);
      // Открываем HTML в новом окне
      const newWindow = window.open('', '_blank');
      newWindow.document.write(response.data.html);
      newWindow.document.close();
    } catch (error) {
      logger.error('Ошибка получения HTML счета:', error);
      toast.error(error.response?.data?.detail || 'Ошибка получения HTML счета');
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
      'draft': { variant: 'secondary', label: 'Черновик', icon: FileText },
      'pending': { variant: 'warning', label: 'Ожидает оплаты', icon: Clock },
      'paid': { variant: 'success', label: 'Оплачен', icon: CheckCircle },
      'partially_paid': { variant: 'info', label: 'Частично оплачен', icon: AlertCircle },
      'overdue': { variant: 'danger', label: 'Просрочен', icon: XCircle },
      'cancelled': { variant: 'secondary', label: 'Отменен', icon: X },
      'refunded': { variant: 'warning', label: 'Возвращен', icon: AlertCircle }
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
            Счета
          </h3>
          <p className="admin-m-0-secondary-fs-sm">
            Управление счетами и выставлением
          </p>
        </div>
        <Button
        onClick={() => setShowCreateInvoice(true)}
        className="flex items-center justify-center gap-2">
        
          <Plus size={16} />
          Создать счет
        </Button>
      </div>

      {/* Список счетов */}
      <div className="admin-d-grid-gap-16">
        {invoices.length === 0 ?
      <MacOSEmptyState
        type="invoice"
        title="Счета не найдены"
        description="В системе пока нет созданных счетов"
        action={
        <Button onClick={() => setShowCreateInvoice(true)}>
                <Plus size={16} className="mr-2" />
                Создать первый счет
              </Button>
        } /> :


      invoices.map((invoice) =>
      <MacOSCard key={invoice.id} className="p-0">
              <div className="admin-d-flex-jc-between-ai-start">
                <div className="admin-flex-1">
                  <div className="admin-d-flex-ai-center-gap-8-mb-12">
                    <h4 className="admin-m-0-primary-fs-var-mac-font-size-md-fw-semi">
                      Счет № {invoice.invoice_number}
                    </h4>
                    {getStatusBadge(invoice.status)}
                    <Badge variant="outline">
                      {INVOICE_TYPE_LABELS[invoice.invoice_type] || invoice.invoice_type}
                    </Badge>
                  </div>

                  <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-8-fs-sm-secondary-mb-8">
                    <div>Пациент ID: {invoice.patient_id}</div>
                    <div>Дата: {new Date(invoice.issue_date).toLocaleDateString()}</div>
                    <div>Срок оплаты: {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'Не указан'}</div>
                    <div>Сумма: {invoice.total_amount.toLocaleString()} сум</div>
                  </div>

                  {invoice.balance > 0 &&
            <div className="admin-fs-sm-error">
                      К доплате: {invoice.balance.toLocaleString()} сум
                    </div>
            }
                </div>

                <div className="admin-d-flex-gap-8">
                  <Button
              variant="outline"
              onClick={() => handleViewInvoiceHTML(invoice.id)}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-5"
              title="Просмотреть счет"
              type="button"
              aria-label={`Просмотреть счет ${invoice.invoice_number || invoice.id}`}>

                    <Eye aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => handleSendInvoice(invoice.id)}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-4"
              title="Отправить счет"
              type="button"
              aria-label={`Отправить счет ${invoice.invoice_number || invoice.id}`}>

                    <Send aria-hidden="true" size={16} />
                  </Button>
                  <Button
              variant="outline"
              onClick={() => {
                setPaymentForm({ ...paymentForm, invoice_id: invoice.id, amount: invoice.balance });
                setShowRecordPayment(true);
              }}
              className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-3"
              title="Записать платеж"
              type="button"
              aria-label={`Записать платеж по счету ${invoice.invoice_number || invoice.id}`}>

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
              Создать счет
            </h4>
            <Button
          variant="outline"
          onClick={() => setShowCreateInvoice(false)}
          type="button"
          title="Закрыть форму создания счета"
          aria-label="Закрыть форму создания счета"
          className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center-2">
          
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-16-1">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-9">
                ID пациента
              </label>
              <Input
            type="number"
            value={invoiceForm.patient_id}
            onChange={(e) => setInvoiceForm({ ...invoiceForm, patient_id: e.target.value })}
            placeholder="ID пациента" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-8">
                Тип счета
              </label>
              <Select
            value={invoiceForm.invoice_type}
            onChange={(value) => setInvoiceForm({ ...invoiceForm, invoice_type: value })}
            options={INVOICE_TYPE_OPTIONS}
            size="large" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-7">
                Срок оплаты (дней)
              </label>
              <Input
            type="number"
            value={invoiceForm.due_days}
            onChange={(e) => setInvoiceForm({ ...invoiceForm, due_days: parseInt(e.target.value) })}
            placeholder="30" />
          
            </div>

            <div className="admin-d-flex-ai-center-gap-16">
              <label className="admin-d-flex-ai-center-gap-8-fs-sm-primary-2">
                <input
              type="checkbox"
              aria-label="Auto send invoice"
              checked={invoiceForm.auto_send}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, auto_send: e.target.checked })}
              className="admin-m-0" />
            
                Автоотправка
              </label>
              <label className="admin-d-flex-ai-center-gap-8-fs-sm-primary-1">
                <input
              type="checkbox"
              aria-label="Send payment reminders"
              checked={invoiceForm.send_reminders}
              onChange={(e) => setInvoiceForm({ ...invoiceForm, send_reminders: e.target.checked })}
              className="admin-m-0" />
            
                Напоминания
              </label>
            </div>
          </div>

          {/* Позиции счета */}
          <div className="mb-4">
            <div className="admin-d-flex-jc-between-ai-center-mb-8">
              <label className="admin-fs-sm-fw-med-primary">
                Позиции счета
              </label>
              <Button
            onClick={addInvoiceItem}
            className="admin-d-flex-ai-center-gap-4-p-4px-8px-fs-xs">
            
                <Plus size={14} />
                Добавить
              </Button>
            </div>

            {invoiceForm.items.map((item, index) =>
        <div key={index} className="admin-d-grid-gtc-2fr-1fr-1fr-auto-gap-8-mb-8-p-12-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-bgc-bg-secondary">
                <Input
            placeholder="Описание"
            value={item.description}
            onChange={(e) => updateInvoiceItem(index, 'description', e.target.value)} />
          
                <Input
            type="number"
            placeholder="Количество"
            value={item.quantity}
            onChange={(e) => updateInvoiceItem(index, 'quantity', parseFloat(e.target.value))} />
          
                <Input
            type="number"
            placeholder="Цена"
            value={item.unit_price}
            onChange={(e) => updateInvoiceItem(index, 'unit_price', parseFloat(e.target.value))} />
          
                <Button
            variant="outline"
            onClick={() => removeInvoiceItem(index)}
            type="button"
            title={`Удалить позицию счета ${index + 1}`}
            aria-label={`Удалить позицию счета ${index + 1}`}
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
                Описание
              </label>
              <Textarea
            value={invoiceForm.description}
            onChange={(e) => setInvoiceForm({ ...invoiceForm, description: e.target.value })}
            placeholder="Описание счета"
            rows={3} />
          
            </div>
          </div>

          <div className="admin-d-flex-jc-end-gap-8-3">
            <Button
          variant="outline"
          onClick={() => setShowCreateInvoice(false)}>
          
              Отмена
            </Button>
            <Button
          onClick={handleCreateInvoice}
          className="flex items-center justify-center gap-2">
          
              <Save size={16} />
              Создать
            </Button>
          </div>
        </MacOSCard>
    }

      {/* Форма записи платежа */}
      {showRecordPayment &&
    <MacOSCard className="p-0">
          <div className="admin-d-flex-jc-between-ai-center-mb-16-2">
            <h4 className="admin-m-0-primary-fs-lg-fw-semi">
              Записать платеж
            </h4>
            <Button
          variant="outline"
          onClick={() => setShowRecordPayment(false)}
          type="button"
          title="Закрыть форму записи платежа"
          aria-label="Закрыть форму записи платежа"
          className="admin-p-6-minw-auto-w-32-h-32-d-flex-ai-center-jc-center">
          
              <X aria-hidden="true" size={16} />
            </Button>
          </div>

          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-mb-16">
            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-5">
                ID счета
              </label>
              <Input
            type="number"
            value={paymentForm.invoice_id}
            onChange={(e) => setPaymentForm({ ...paymentForm, invoice_id: e.target.value })}
            placeholder="ID счета" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-4">
                Сумма платежа
              </label>
              <Input
            type="number"
            value={paymentForm.amount}
            onChange={(e) => setPaymentForm({ ...paymentForm, amount: parseFloat(e.target.value) })}
            placeholder="0" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-3">
                Способ оплаты
              </label>
              <Select
            value={paymentForm.payment_method}
            onChange={(value) => setPaymentForm({ ...paymentForm, payment_method: value })}
            options={PAYMENT_METHOD_OPTIONS}
            size="large" />
          
            </div>

            <div>
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-2">
                Номер ссылки
              </label>
              <Input
            value={paymentForm.reference_number}
            onChange={(e) => setPaymentForm({ ...paymentForm, reference_number: e.target.value })}
            placeholder="Номер транзакции" />
          
            </div>

            <div className="admin-gc-1-1">
              <label className="admin-d-block-fs-sm-fw-med-primary-mb-8-1">
                Описание
              </label>
              <Textarea
            value={paymentForm.description}
            onChange={(e) => setPaymentForm({ ...paymentForm, description: e.target.value })}
            placeholder="Описание платежа"
            rows={3} />
          
            </div>
          </div>

          <div className="admin-d-flex-jc-end-gap-8-2">
            <Button
          variant="outline"
          onClick={() => setShowRecordPayment(false)}>
          
              Отмена
            </Button>
            <Button
          onClick={handleRecordPayment}
          className="flex items-center justify-center gap-2">
          
              <Save size={16} />
              Записать
            </Button>
          </div>
        </MacOSCard>
    }
    </div>;


  const renderPaymentsTab = () =>
  <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Платежи</h3>
        <p className="text-gray-600">История платежей и транзакций</p>
      </div>

      <div className="grid gap-4">
        {payments.map((payment) =>
      <MacOSCard key={payment.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-medium">Платеж № {payment.payment_number}</h4>
                  <Badge variant={payment.is_confirmed ? 'success' : 'warning'}>
                    {payment.is_confirmed ? 'Подтвержден' : 'Ожидает подтверждения'}
                  </Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
                  <div>Счет ID: {payment.invoice_id}</div>
                  <div>Пациент ID: {payment.patient_id}</div>
                  <div>Сумма: {payment.amount.toLocaleString()} сум</div>
                  <div>Способ: {PAYMENT_METHOD_LABELS[payment.payment_method] || payment.payment_method}</div>
                  <div>Дата: {new Date(payment.payment_date).toLocaleDateString()}</div>
                  {payment.reference_number &&
              <div>Ссылка: {payment.reference_number}</div>
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
        <h3 className="text-lg font-semibold">Аналитика биллинга</h3>
        <p className="text-gray-600">Статистика по счетам и платежам</p>
      </div>

      {analytics &&
    <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-5 h-5 text-blue-500" />
                <h4 className="font-medium">Всего счетов</h4>
              </div>
              <div className="text-2xl font-bold">{analytics.summary?.total_invoices || 0}</div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">Общая сумма</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.total_amount?.toLocaleString() || 0} сум
              </div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">Оплачено</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.paid_amount?.toLocaleString() || 0} сум
              </div>
            </MacOSCard>

            <MacOSCard className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-5 h-5 text-red-500" />
                <h4 className="font-medium">Просрочено</h4>
              </div>
              <div className="text-2xl font-bold text-red-600">
                {analytics.summary?.overdue_amount?.toLocaleString() || 0} сум
              </div>
            </MacOSCard>
          </div>

          {analytics.status_breakdown &&
      <MacOSCard className="p-4">
              <h4 className="font-medium mb-4">Разбивка по статусам</h4>
              <div className="space-y-2">
                {analytics.status_breakdown.map((stat, index) =>
          <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="font-medium">{stat.status}</span>
                    <div className="flex gap-4 text-sm">
                      <span>Количество: {stat.count}</span>
                      <span>Сумма: {stat.amount?.toLocaleString() || 0} сум</span>
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
  { id: 'invoices', label: 'Счета', icon: FileText },
  { id: 'payments', label: 'Платежи', icon: CreditCard },
  { id: 'analytics', label: 'Аналитика', icon: TrendingUp },
  { id: 'settings', label: 'Настройки', icon: Settings }];


  return (
    <div className="admin-p-0-maxw-1400-m-0-auto">
      <div className="admin-d-flex-ai-center-gap-16-mb-24">
        <DollarSign size={24} color="var(--mac-accent)" />
        <div>
          <h2 className="admin-m-0-primary-fs-xl-fw-bold">
            Управление биллингом
          </h2>
          <p className="admin-m-4px-0-0-0-secondary-fs-sm">
            Автоматическое выставление счетов, управление платежами и аналитика
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
              className="admin-p-16px-24px-bd-none-bg-none-cur-pointer-d-flex-ai-center-gap-8-fs-sm-tr-all-var-mac-duration-bd-b-dyn-col-dyn-fw-dyn" style={{ '--admin-bd-b0': activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent', '--admin-col1': activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)', '--admin-fw2': activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)' }}>
              
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
          title="Настройки биллинга"
          description="Настройки биллинга будут добавлены в следующей версии" />

        }
        </>
      }
    </div>);

};

export default BillingManager;
