import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Button, 
  Badge, 
  Input, 
  Select, 
  Label, 
  Textarea 
} from '../ui/native';
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
    <div className="space-y-6">
      {/* Заголовок и кнопки */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Счета</h3>
          <p className="text-gray-600">Управление счетами и выставлением</p>
        </div>
        <Button onClick={() => setShowCreateInvoice(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Создать счет
        </Button>
      </div>

      {/* Список счетов */}
      <div className="grid gap-4">
        {invoices.map(invoice => (
          <Card key={invoice.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="font-medium">Счет № {invoice.invoice_number}</h4>
                  {getStatusBadge(invoice.status)}
                  <Badge variant="outline">{invoice.invoice_type}</Badge>
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-2">
                  <div>Пациент ID: {invoice.patient_id}</div>
                  <div>Дата: {new Date(invoice.issue_date).toLocaleDateString()}</div>
                  <div>Срок оплаты: {invoice.due_date ? new Date(invoice.due_date).toLocaleDateString() : 'Не указан'}</div>
                  <div>Сумма: {invoice.total_amount.toLocaleString()} сум</div>
                </div>

                {invoice.balance > 0 && (
                  <div className="text-sm">
                    <span className="text-red-600">К доплате: {invoice.balance.toLocaleString()} сум</span>
                  </div>
                )}
              </div>
              
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleViewInvoiceHTML(invoice.id)}
                >
                  <Eye className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleSendInvoice(invoice.id)}
                >
                  <Send className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setPaymentForm({ ...paymentForm, invoice_id: invoice.id, amount: invoice.balance });
                    setShowRecordPayment(true);
                  }}
                >
                  <CreditCard className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Форма создания счета */}
      {showCreateInvoice && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-medium">Создать счет</h4>
            <Button variant="outline" onClick={() => setShowCreateInvoice(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <Label>ID пациента</Label>
              <Input
                type="number"
                value={invoiceForm.patient_id}
                onChange={(e) => setInvoiceForm({...invoiceForm, patient_id: e.target.value})}
                placeholder="ID пациента"
              />
            </div>

            <div>
              <Label>Тип счета</Label>
              <Select
                value={invoiceForm.invoice_type}
                onChange={(e) => setInvoiceForm({...invoiceForm, invoice_type: e.target.value})}
              >
                <option value="STANDARD">Обычный</option>
                <option value="RECURRING">Периодический</option>
                <option value="ADVANCE">Авансовый</option>
                <option value="CORRECTION">Корректировочный</option>
              </Select>
            </div>

            <div>
              <Label>Срок оплаты (дней)</Label>
              <Input
                type="number"
                value={invoiceForm.due_days}
                onChange={(e) => setInvoiceForm({...invoiceForm, due_days: parseInt(e.target.value)})}
                placeholder="30"
              />
            </div>

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={invoiceForm.auto_send}
                  onChange={(e) => setInvoiceForm({...invoiceForm, auto_send: e.target.checked})}
                />
                Автоотправка
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={invoiceForm.send_reminders}
                  onChange={(e) => setInvoiceForm({...invoiceForm, send_reminders: e.target.checked})}
                />
                Напоминания
              </label>
            </div>
          </div>

          {/* Позиции счета */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <Label>Позиции счета</Label>
              <Button size="sm" onClick={addInvoiceItem}>
                <Plus className="w-4 h-4 mr-1" />
                Добавить
              </Button>
            </div>

            {invoiceForm.items.map((item, index) => (
              <div key={index} className="grid grid-cols-4 gap-2 mb-2 p-2 border rounded">
                <Input
                  placeholder="Описание"
                  value={item.description}
                  onChange={(e) => updateInvoiceItem(index, 'description', e.target.value)}
                />
                <Input
                  type="number"
                  placeholder="Количество"
                  value={item.quantity}
                  onChange={(e) => updateInvoiceItem(index, 'quantity', parseFloat(e.target.value))}
                />
                <Input
                  type="number"
                  placeholder="Цена"
                  value={item.unit_price}
                  onChange={(e) => updateInvoiceItem(index, 'unit_price', parseFloat(e.target.value))}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => removeInvoiceItem(index)}
                  disabled={invoiceForm.items.length === 1}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 mb-4">
            <div>
              <Label>Описание</Label>
              <Textarea
                value={invoiceForm.description}
                onChange={(e) => setInvoiceForm({...invoiceForm, description: e.target.value})}
                placeholder="Описание счета"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setShowCreateInvoice(false)}>
              Отмена
            </Button>
            <Button onClick={handleCreateInvoice}>
              <Save className="w-4 h-4 mr-2" />
              Создать
            </Button>
          </div>
        </Card>
      )}

      {/* Форма записи платежа */}
      {showRecordPayment && (
        <Card className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h4 className="text-lg font-medium">Записать платеж</h4>
            <Button variant="outline" onClick={() => setShowRecordPayment(false)}>
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>ID счета</Label>
              <Input
                type="number"
                value={paymentForm.invoice_id}
                onChange={(e) => setPaymentForm({...paymentForm, invoice_id: e.target.value})}
                placeholder="ID счета"
              />
            </div>

            <div>
              <Label>Сумма платежа</Label>
              <Input
                type="number"
                value={paymentForm.amount}
                onChange={(e) => setPaymentForm({...paymentForm, amount: parseFloat(e.target.value)})}
                placeholder="0"
              />
            </div>

            <div>
              <Label>Способ оплаты</Label>
              <Select
                value={paymentForm.payment_method}
                onChange={(e) => setPaymentForm({...paymentForm, payment_method: e.target.value})}
              >
                <option value="CASH">Наличные</option>
                <option value="CARD">Банковская карта</option>
                <option value="BANK_TRANSFER">Банковский перевод</option>
                <option value="ONLINE">Онлайн платеж</option>
                <option value="INSURANCE">Страховка</option>
                <option value="INSTALLMENT">Рассрочка</option>
              </Select>
            </div>

            <div>
              <Label>Номер ссылки</Label>
              <Input
                value={paymentForm.reference_number}
                onChange={(e) => setPaymentForm({...paymentForm, reference_number: e.target.value})}
                placeholder="Номер транзакции"
              />
            </div>

            <div className="col-span-2">
              <Label>Описание</Label>
              <Textarea
                value={paymentForm.description}
                onChange={(e) => setPaymentForm({...paymentForm, description: e.target.value})}
                placeholder="Описание платежа"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={() => setShowRecordPayment(false)}>
              Отмена
            </Button>
            <Button onClick={handleRecordPayment}>
              <Save className="w-4 h-4 mr-2" />
              Записать
            </Button>
          </div>
        </Card>
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
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Управление биллингом</h2>
        <p className="text-gray-600">
          Автоматическое выставление счетов, управление платежами и аналитика
        </p>
      </div>

      {/* Табы */}
      <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-md transition-colors ${
                activeTab === tab.id
                  ? 'bg-white shadow-sm text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500">Загрузка...</div>
        </div>
      ) : (
        <>
          {activeTab === 'invoices' && renderInvoicesTab()}
          {activeTab === 'payments' && renderPaymentsTab()}
          {activeTab === 'analytics' && renderAnalyticsTab()}
          {activeTab === 'settings' && (
            <div className="text-center text-gray-500">
              Настройки биллинга будут добавлены в следующей версии
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default BillingManager;

