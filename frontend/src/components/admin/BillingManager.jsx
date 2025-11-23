import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect, 
  MacOSTextarea,
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSAlert
} from '../ui/macos';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Send, 
  Eye, 
  Download, 
  DollarSign,
  CreditCard,
  FileText,
  Calendar,
  Clock,
  Users,
  TrendingUp,
  Settings,
  Save,
  X,
  CheckCircle,
  AlertCircle,
  XCircle
} from 'lucide-react';
import { toast } from 'react-toastify';

const BillingManager = () => {
  const [activeTab, setActiveTab] = useState('invoices');
  const [invoices, setInvoices] = useState([]);
  const [payments, setPayments] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCreateInvoice, setShowCreateInvoice] = useState(false);
  const [showRecordPayment, setShowRecordPayment] = useState(false);
  const [selectedInvoice, setSelectedInvoice] = useState(null);

  // Форма для создания счета
  const [invoiceForm, setInvoiceForm] = useState({
    patient_id: '',
    visit_id: '',
    appointment_id: '',
    invoice_type: 'STANDARD',
    items: [{ description: '', quantity: 1, unit_price: 0 }],
    description: '',
    notes: '',
    due_days: 30,
    auto_send: false,
    send_reminders: true,
    is_recurring: false,
    recurrence_type: 'MONTHLY',
    recurrence_interval: 1
  });

  // Форма для записи платежа
  const [paymentForm, setPaymentForm] = useState({
    invoice_id: '',
    amount: 0,
    payment_method: 'CASH',
    reference_number: '',
    description: '',
    notes: ''
  });

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };

      if (activeTab === 'invoices') {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/invoices`, {
          headers
        });
        if (response.ok) {
          const data = await response.json();
          setInvoices(data);
        }
      } else if (activeTab === 'payments') {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/payments`, {
          headers
        });
        if (response.ok) {
          const data = await response.json();
          setPayments(data);
        }
      } else if (activeTab === 'analytics') {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/analytics`, {
          headers
        });
        if (response.ok) {
          const data = await response.json();
          setAnalytics(data);
        }
      } else if (activeTab === 'settings') {
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/settings`, {
          headers
        });
        if (response.ok) {
          const data = await response.json();
          setSettings(data);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateInvoice = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/invoices`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(invoiceForm)
      });

      if (response.ok) {
        toast.success('Счет создан успешно');
        setShowCreateInvoice(false);
        setInvoiceForm({
          patient_id: '',
          visit_id: '',
          appointment_id: '',
          invoice_type: 'STANDARD',
          items: [{ description: '', quantity: 1, unit_price: 0 }],
          description: '',
          notes: '',
          due_days: 30,
          auto_send: false,
          send_reminders: true,
          is_recurring: false,
          recurrence_type: 'MONTHLY',
          recurrence_interval: 1
        });
        loadData();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка создания счета');
      }
    } catch (error) {
      console.error('Ошибка создания счета:', error);
      toast.error('Ошибка создания счета');
    }
  };

  const handleRecordPayment = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/payments`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(paymentForm)
      });

      if (response.ok) {
        toast.success('Платеж записан успешно');
        setShowRecordPayment(false);
        setPaymentForm({
          invoice_id: '',
          amount: 0,
          payment_method: 'CASH',
          reference_number: '',
          description: '',
          notes: ''
        });
        loadData();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка записи платежа');
      }
    } catch (error) {
      console.error('Ошибка записи платежа:', error);
      toast.error('Ошибка записи платежа');
    }
  };

  const handleSendInvoice = async (invoiceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/invoices/${invoiceId}/send`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        toast.success('Счет отправлен');
      } else {
        toast.error('Ошибка отправки счета');
      }
    } catch (error) {
      console.error('Ошибка отправки счета:', error);
      toast.error('Ошибка отправки счета');
    }
  };

  const handleViewInvoiceHTML = async (invoiceId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/billing/invoices/${invoiceId}/html`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        // Открываем HTML в новом окне
        const newWindow = window.open('', '_blank');
        newWindow.document.write(data.html);
        newWindow.document.close();
      } else {
        toast.error('Ошибка получения HTML счета');
      }
    } catch (error) {
      console.error('Ошибка получения HTML счета:', error);
      toast.error('Ошибка получения HTML счета');
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
      </Badge>
    );
  };

  const renderInvoicesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок и кнопки */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center' 
      }}>
        <div>
          <h3 style={{ 
            margin: '0 0 4px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)'
          }}>
            Счета
          </h3>
          <p style={{ 
            margin: 0,
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Управление счетами и выставлением
          </p>
        </div>
        <MacOSButton 
          onClick={() => setShowCreateInvoice(true)}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          <Plus size={16} />
          Создать счет
        </MacOSButton>
      </div>

      {/* Список счетов */}
      <div style={{ display: 'grid', gap: '16px' }}>
        {invoices.length === 0 ? (
          <MacOSEmptyState
            type="invoice"
            title="Счета не найдены"
            description="В системе пока нет созданных счетов"
            action={
              <MacOSButton onClick={() => setShowCreateInvoice(true)}>
                <Plus size={16} style={{ marginRight: '8px' }} />
                Создать первый счет
              </MacOSButton>
            }
          />
        ) : (
          invoices.map(invoice => (
            <MacOSCard key={invoice.id} style={{ padding: 0 }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start' 
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px',
                    marginBottom: '12px'
                  }}>
                    <h4 style={{ 
                      margin: 0,
                      color: 'var(--mac-text-primary)',
                      fontSize: 'var(--mac-font-size-md)',
                      fontWeight: 'var(--mac-font-weight-semibold)'
                    }}>
                      Счет № {invoice.invoice_number}
                    </h4>
                    {getStatusBadge(invoice.status)}
                    <MacOSBadge variant="outline">{invoice.invoice_type}</MacOSBadge>
                  </div>
                  
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                    gap: '8px',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '8px'
                  }}>
                    <div>Пациент ID: {invoice.patient_id}</div>
                    <div>Дата: {new Date(invoice.issue_date).toLocaleDateString()}</div>
                    <div>Срок оплаты: {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'Не указан'}</div>
                    <div>Сумма: {invoice.total_amount.toLocaleString()} сум</div>
                  </div>

                  {invoice.balance > 0 && (
                    <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-error)'
                    }}>
                      К доплате: {invoice.balance.toLocaleString()} сум
                    </div>
                  )}
                </div>
                
                <div style={{ display: 'flex', gap: '8px' }}>
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleViewInvoiceHTML(invoice.id)}
                    style={{ 
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Просмотр"
                  >
                    <Eye size={16} />
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => handleSendInvoice(invoice.id)}
                    style={{ 
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Отправить"
                  >
                    <Send size={16} />
                  </MacOSButton>
                  <MacOSButton
                    variant="outline"
                    onClick={() => {
                      setPaymentForm({ ...paymentForm, invoice_id: invoice.id, amount: invoice.balance });
                      setShowRecordPayment(true);
                    }}
                    style={{ 
                      padding: '6px',
                      minWidth: 'auto',
                      width: '32px',
                      height: '32px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center'
                    }}
                    title="Записать платеж"
                  >
                    <CreditCard size={16} />
                  </MacOSButton>
                </div>
              </div>
            </MacOSCard>
          ))
        )}
      </div>

      {/* Форма создания счета */}
      {showCreateInvoice && (
        <MacOSCard style={{ padding: 0 }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h4 style={{ 
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Создать счет
            </h4>
            <MacOSButton 
              variant="outline" 
              onClick={() => setShowCreateInvoice(false)}
              style={{ 
                padding: '6px',
                minWidth: 'auto',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <X size={16} />
            </MacOSButton>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                ID пациента
              </label>
              <MacOSInput
                type="number"
                value={invoiceForm.patient_id}
                onChange={(e) => setInvoiceForm({...invoiceForm, patient_id: e.target.value})}
                placeholder="ID пациента"
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Тип счета
              </label>
              <MacOSSelect
                value={invoiceForm.invoice_type}
                onChange={(e) => setInvoiceForm({...invoiceForm, invoice_type: e.target.value})}
                options={[
                  { value: 'STANDARD', label: 'Обычный' },
                  { value: 'RECURRING', label: 'Периодический' },
                  { value: 'ADVANCE', label: 'Авансовый' },
                  { value: 'CORRECTION', label: 'Корректировочный' }
                ]}
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Срок оплаты (дней)
              </label>
              <MacOSInput
                type="number"
                value={invoiceForm.due_days}
                onChange={(e) => setInvoiceForm({...invoiceForm, due_days: parseInt(e.target.value)})}
                placeholder="30"
              />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>
                <input
                  type="checkbox"
                  checked={invoiceForm.auto_send}
                  onChange={(e) => setInvoiceForm({...invoiceForm, auto_send: e.target.checked})}
                  style={{ margin: 0 }}
                />
                Автоотправка
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>
                <input
                  type="checkbox"
                  checked={invoiceForm.send_reminders}
                  onChange={(e) => setInvoiceForm({...invoiceForm, send_reminders: e.target.checked})}
                  style={{ margin: 0 }}
                />
                Напоминания
              </label>
            </div>
          </div>

          {/* Позиции счета */}
          <div style={{ marginBottom: '16px' }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '8px'
            }}>
              <label style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)'
              }}>
                Позиции счета
              </label>
              <MacOSButton 
                onClick={addInvoiceItem}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '4px',
                  padding: '4px 8px',
                  fontSize: 'var(--mac-font-size-xs)'
                }}
              >
                <Plus size={14} />
                Добавить
              </MacOSButton>
            </div>

            {invoiceForm.items.map((item, index) => (
              <div key={index} style={{ 
                display: 'grid', 
                gridTemplateColumns: '2fr 1fr 1fr auto', 
                gap: '8px',
                marginBottom: '8px',
                padding: '12px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <MacOSInput
                  placeholder="Описание"
                  value={item.description}
                  onChange={(e) => updateInvoiceItem(index, 'description', e.target.value)}
                />
                <MacOSInput
                  type="number"
                  placeholder="Количество"
                  value={item.quantity}
                  onChange={(e) => updateInvoiceItem(index, 'quantity', parseFloat(e.target.value))}
                />
                <MacOSInput
                  type="number"
                  placeholder="Цена"
                  value={item.unit_price}
                  onChange={(e) => updateInvoiceItem(index, 'unit_price', parseFloat(e.target.value))}
                />
                <MacOSButton
                  variant="outline"
                  onClick={() => removeInvoiceItem(index)}
                  disabled={invoiceForm.items.length === 1}
                  style={{ 
                    padding: '6px',
                    minWidth: 'auto',
                    width: '32px',
                    height: '32px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                >
                  <Trash2 size={16} />
                </MacOSButton>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={invoiceForm.description}
                onChange={(e) => setInvoiceForm({...invoiceForm, description: e.target.value})}
                placeholder="Описание счета"
                rows={3}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <MacOSButton 
              variant="outline" 
              onClick={() => setShowCreateInvoice(false)}
            >
              Отмена
            </MacOSButton>
            <MacOSButton 
              onClick={handleCreateInvoice}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px' 
              }}
            >
              <Save size={16} />
              Создать
            </MacOSButton>
          </div>
        </MacOSCard>
      )}

      {/* Форма записи платежа */}
      {showRecordPayment && (
        <MacOSCard style={{ padding: 0 }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h4 style={{ 
              margin: 0,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Записать платеж
            </h4>
            <MacOSButton 
              variant="outline" 
              onClick={() => setShowRecordPayment(false)}
              style={{ 
                padding: '6px',
                minWidth: 'auto',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <X size={16} />
            </MacOSButton>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                ID счета
              </label>
              <MacOSInput
                type="number"
                value={paymentForm.invoice_id}
                onChange={(e) => setPaymentForm({...paymentForm, invoice_id: e.target.value})}
                placeholder="ID счета"
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Сумма платежа
              </label>
              <MacOSInput
                type="number"
                value={paymentForm.amount}
                onChange={(e) => setPaymentForm({...paymentForm, amount: parseFloat(e.target.value)})}
                placeholder="0"
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Способ оплаты
              </label>
              <MacOSSelect
                value={paymentForm.payment_method}
                onChange={(e) => setPaymentForm({...paymentForm, payment_method: e.target.value})}
                options={[
                  { value: 'CASH', label: 'Наличные' },
                  { value: 'CARD', label: 'Банковская карта' },
                  { value: 'BANK_TRANSFER', label: 'Банковский перевод' },
                  { value: 'ONLINE', label: 'Онлайн платеж' },
                  { value: 'INSURANCE', label: 'Страховка' },
                  { value: 'INSTALLMENT', label: 'Рассрочка' }
                ]}
              />
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Номер ссылки
              </label>
              <MacOSInput
                value={paymentForm.reference_number}
                onChange={(e) => setPaymentForm({...paymentForm, reference_number: e.target.value})}
                placeholder="Номер транзакции"
              />
            </div>

            <div style={{ gridColumn: '1 / -1' }}>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                Описание
              </label>
              <MacOSTextarea
                value={paymentForm.description}
                onChange={(e) => setPaymentForm({...paymentForm, description: e.target.value})}
                placeholder="Описание платежа"
                rows={3}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
            <MacOSButton 
              variant="outline" 
              onClick={() => setShowRecordPayment(false)}
            >
              Отмена
            </MacOSButton>
            <MacOSButton 
              onClick={handleRecordPayment}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px' 
              }}
            >
              <Save size={16} />
              Записать
            </MacOSButton>
          </div>
        </MacOSCard>
      )}
    </div>
  );

  const renderPaymentsTab = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Платежи</h3>
        <p className="text-gray-600">История платежей и транзакций</p>
      </div>

      <div className="grid gap-4">
        {payments.map(payment => (
          <Card key={payment.id} className="p-4">
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
                  <div>Способ: {payment.payment_method}</div>
                  <div>Дата: {new Date(payment.payment_date).toLocaleDateString()}</div>
                  {payment.reference_number && (
                    <div>Ссылка: {payment.reference_number}</div>
                  )}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderAnalyticsTab = () => (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Аналитика биллинга</h3>
        <p className="text-gray-600">Статистика по счетам и платежам</p>
      </div>

      {analytics && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-5 h-5 text-blue-500" />
                <h4 className="font-medium">Всего счетов</h4>
              </div>
              <div className="text-2xl font-bold">{analytics.summary?.total_invoices || 0}</div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">Общая сумма</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.total_amount?.toLocaleString() || 0} сум
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-green-500" />
                <h4 className="font-medium">Оплачено</h4>
              </div>
              <div className="text-2xl font-bold text-green-600">
                {analytics.summary?.paid_amount?.toLocaleString() || 0} сум
              </div>
            </Card>

            <Card className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-5 h-5 text-red-500" />
                <h4 className="font-medium">Просрочено</h4>
              </div>
              <div className="text-2xl font-bold text-red-600">
                {analytics.summary?.overdue_amount?.toLocaleString() || 0} сум
              </div>
            </Card>
          </div>

          {analytics.status_breakdown && (
            <Card className="p-4">
              <h4 className="font-medium mb-4">Разбивка по статусам</h4>
              <div className="space-y-2">
                {analytics.status_breakdown.map((stat, index) => (
                  <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                    <span className="font-medium">{stat.status}</span>
                    <div className="flex gap-4 text-sm">
                      <span>Количество: {stat.count}</span>
                      <span>Сумма: {stat.amount?.toLocaleString() || 0} сум</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );

  const tabs = [
    { id: 'invoices', label: 'Счета', icon: FileText },
    { id: 'payments', label: 'Платежи', icon: CreditCard },
    { id: 'analytics', label: 'Аналитика', icon: TrendingUp },
    { id: 'settings', label: 'Настройки', icon: Settings }
  ];

  return (
    <div style={{ padding: 0, maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <DollarSign size={24} color="var(--mac-accent)" />
        <div>
          <h2 style={{ 
            margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Управление биллингом
          </h2>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Автоматическое выставление счетов, управление платежами и аналитика
          </p>
        </div>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }}>
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '16px 24px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderBottom: activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent',
                color: activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                fontWeight: activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент */}
      {loading ? (
        <MacOSLoadingSkeleton type="card" count={3} />
      ) : (
        <>
          {activeTab === 'invoices' && renderInvoicesTab()}
          {activeTab === 'payments' && renderPaymentsTab()}
          {activeTab === 'analytics' && renderAnalyticsTab()}
          {activeTab === 'settings' && (
            <MacOSEmptyState
              type="settings"
              title="Настройки биллинга"
              description="Настройки биллинга будут добавлены в следующей версии"
            />
          )}
        </>
      )}
    </div>
  );
};

export default BillingManager;

