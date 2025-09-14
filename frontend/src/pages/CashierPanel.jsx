import React, { useEffect, useState } from 'react';
import { CreditCard, Calendar, Download, Search, Filter, CheckCircle, XCircle, DollarSign } from 'lucide-react';
import { Card, Badge, Button, Skeleton } from '../design-system/components';
import { useBreakpoint } from '../design-system/hooks';
import { APPOINTMENT_STATUS } from '../constants/appointmentStatus';
import PaymentWidget from '../components/payment/PaymentWidget';
import { 
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions,
  Typography,
  Box,
  Alert
} from '@mui/material';

const CashierPanel = () => {
  const { isMobile } = useBreakpoint();
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [payments, setPayments] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showPaymentWidget, setShowPaymentWidget] = useState(false);
  const [paymentSuccess, setPaymentSuccess] = useState(null);
  const [paymentError, setPaymentError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      
      // Загружаем записи ожидающие оплаты
      try {
        const appointmentsResponse = await fetch('/api/v1/appointments/?status=pending&limit=50', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (appointmentsResponse.ok) {
          const appointmentsData = await appointmentsResponse.json();
          setAppointments(appointmentsData);
        }
      } catch (error) {
        console.error('Ошибка загрузки записей:', error);
      }

      // Загружаем историю платежей
      try {
        const paymentsResponse = await fetch('/api/v1/payments/?limit=50', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (paymentsResponse.ok) {
          const paymentsData = await paymentsResponse.json();
          setPayments(paymentsData);
        } else {
          // Fallback данные
          setPayments([
            { id: 1, time: '09:10', patient: 'Ахмедов Алишер', service: 'Консультация', amount: 120000, method: 'Карта', status: 'paid' },
            { id: 2, time: '09:30', patient: 'Каримова Зухра',  service: 'Анализы',     amount: 85000,  method: 'Наличные', status: 'paid' },
            { id: 3, time: '10:05', patient: 'Тошматов Бахтиёр', service: 'ЭхоКГ',       amount: 220000, method: 'Карта', status: 'pending' },
          ]);
        }
      } catch (error) {
        console.error('Ошибка загрузки платежей:', error);
        // Fallback данные
        setPayments([
          { id: 1, time: '09:10', patient: 'Ахмедов Алишер', service: 'Консультация', amount: 120000, method: 'Карта', status: 'paid' },
          { id: 2, time: '09:30', patient: 'Каримова Зухра',  service: 'Анализы',     amount: 85000,  method: 'Наличные', status: 'paid' },
          { id: 3, time: '10:05', patient: 'Тошматов Бахтиёр', service: 'ЭхоКГ',       amount: 220000, method: 'Карта', status: 'pending' },
        ]);
      }
      
      setIsLoading(false);
    };
    load();
  }, []);

  const format = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' сум';

  // Обработчики PaymentWidget
  const handlePaymentSuccess = (paymentData) => {
    setPaymentSuccess(paymentData);
    setShowPaymentWidget(false);
    
    // Обновляем список записей
    setAppointments(prev => prev.map(apt => 
      apt.id === selectedAppointment?.id 
        ? { ...apt, status: 'paid', payment_id: paymentData.payment_id }
        : apt
    ));
    
    // Добавляем платеж в историю
    setPayments(prev => [{
      id: paymentData.payment_id,
      time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
      patient: selectedAppointment?.patient_name || 'Неизвестно',
      service: selectedAppointment?.department || 'Услуга',
      amount: paymentData.amount || selectedAppointment?.cost,
      method: paymentData.provider || 'Онлайн',
      status: 'paid'
    }, ...prev]);
  };

  const handlePaymentError = (error) => {
    setPaymentError(error);
    console.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    setShowPaymentWidget(false);
    setSelectedAppointment(null);
  };

  const openPaymentWidget = (appointment) => {
    setSelectedAppointment(appointment);
    setShowPaymentWidget(true);
    setPaymentError(null);
    setPaymentSuccess(null);
  };

  // Функции для работы с оплатами
  const processPayment = async (appointment, paymentData) => {
    try {
      // Сначала создаем платеж
      const paymentResponse = await fetch('/api/v1/payments/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          appointment_id: appointment.id,
          amount: paymentData.amount,
          method: paymentData.method,
          note: paymentData.note || `Оплата за ${appointment.department || 'услугу'}`
        })
      });

      if (paymentResponse.ok) {
        const payment = await paymentResponse.json();
        
        // Затем отмечаем запись как оплаченную
        const markPaidResponse = await fetch(`/api/v1/appointments/${appointment.id}/mark-paid`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
          }
        });

        if (markPaidResponse.ok) {
          // Обновляем списки
          setAppointments(prev => prev.filter(apt => apt.id !== appointment.id));
          setPayments(prev => [payment, ...prev]);
          setShowPaymentModal(false);
          setSelectedAppointment(null);
          alert('Оплата успешно обработана!');
        } else {
          throw new Error('Ошибка при обновлении статуса записи');
        }
      } else {
        const error = await paymentResponse.json();
        throw new Error(error.detail || 'Ошибка при создании платежа');
      }
    } catch (error) {
      console.error('CashierPanel: Payment error:', error);
      alert('Ошибка при обработке оплаты: ' + error.message);
    }
  };

  const filtered = payments.filter(p => {
    const matchesText = [p.patient, p.service, p.method].join(' ').toLowerCase().includes(query.toLowerCase());
    const matchesStatus = status === 'all' || p.status === status;
    return matchesText && matchesStatus;
  });

  return (
    <div style={{ padding: 16 }}>
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CreditCard className="w-7 h-7 text-blue-600" />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Панель кассира</h1>
              <p className="text-sm text-gray-500">Приём оплат и выдача чеков</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm"><Calendar className="w-4 h-4 mr-2"/>Сегодня</Button>
            <Button variant="outline" size="sm"><Download className="w-4 h-4 mr-2"/>Экспорт</Button>
          </div>
        </div>

        {/* Filters */}
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                value={query}
                onChange={(e)=>setQuery(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Поиск по пациенту, услуге, способу оплаты"
              />
            </div>
            <select
              value={status}
              onChange={(e)=>setStatus(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg"
            >
              <option value="all">Все статусы</option>
              <option value="paid">Оплачено</option>
              <option value="pending">Ожидает</option>
            </select>
            <Button variant="outline"><Filter className="w-4 h-4 mr-2"/>Фильтры</Button>
          </div>
        </Card>

        {/* Записи ожидающие оплаты */}
        {appointments.length > 0 && (
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-orange-500" />
                Записи ожидающие оплаты ({appointments.length})
              </h2>
            </div>
            <div className="space-y-3">
              {appointments.map((appointment) => (
                <div key={appointment.id} className="flex items-center justify-between p-3 bg-orange-50 border border-orange-200 rounded-lg">
                  <div className="flex-1">
                    <div className="font-medium text-gray-900">
                      {appointment.patient_name || `Пациент #${appointment.patient_id}`}
                    </div>
                    <div className="text-sm text-gray-600">
                      {appointment.department} • {appointment.appointment_date} {appointment.appointment_time}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="warning">Ожидает оплаты</Badge>
                    <div className="flex gap-2">
                      <Button 
                        size="sm" 
                        variant="outline"
                        onClick={() => openPaymentWidget(appointment)}
                      >
                        <CreditCard className="w-4 h-4 mr-1" />
                        Онлайн
                      </Button>
                      <Button 
                        size="sm" 
                        onClick={() => {
                          setSelectedAppointment(appointment);
                          setShowPaymentModal(true);
                        }}
                      >
                        <DollarSign className="w-4 h-4 mr-1" />
                        Касса
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Table */}
        <Card className="p-0 overflow-hidden">
          {isLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Время</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Пациент</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Услуга</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Способ</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Сумма</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Статус</th>
                    <th className="text-left px-4 py-3 text-gray-900 font-medium">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="px-4 py-3">{row.time}</td>
                      <td className="px-4 py-3">{row.patient}</td>
                      <td className="px-4 py-3">{row.service}</td>
                      <td className="px-4 py-3">{row.method}</td>
                      <td className="px-4 py-3 font-medium">{format(row.amount)}</td>
                      <td className="px-4 py-3">
                        <Badge variant={row.status === 'paid' ? 'success' : 'warning'}>
                          {row.status === 'paid' ? 'Оплачено' : 'Ожидает'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 flex gap-2">
                        <Button size="sm" variant="success"><CheckCircle className="w-4 h-4 mr-1"/>Принять</Button>
                        <Button size="sm" variant="danger"><XCircle className="w-4 h-4 mr-1"/>Отмена</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Модальное окно оплаты */}
        {showPaymentModal && selectedAppointment && (
          <PaymentModal
            appointment={selectedAppointment}
            onProcessPayment={processPayment}
            onClose={() => {
              setShowPaymentModal(false);
              setSelectedAppointment(null);
            }}
          />
        )}

        {/* Диалог онлайн-оплаты */}
        <Dialog 
          open={showPaymentWidget} 
          onClose={handlePaymentCancel}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            <Typography variant="h6">
              Онлайн-оплата
            </Typography>
            {selectedAppointment && (
              <Typography variant="body2" color="textSecondary">
                Пациент: {selectedAppointment.patient_name} • {selectedAppointment.department}
              </Typography>
            )}
          </DialogTitle>
          
          <DialogContent>
            {paymentError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {paymentError}
              </Alert>
            )}
            
            {selectedAppointment && (
              <PaymentWidget
                visitId={selectedAppointment.id}
                amount={selectedAppointment.cost || 100000}
                currency="UZS"
                description={`Оплата за ${selectedAppointment.department || 'медицинские услуги'}`}
                onSuccess={handlePaymentSuccess}
                onError={handlePaymentError}
                onCancel={handlePaymentCancel}
              />
            )}
          </DialogContent>
          
          <DialogActions>
            <Button onClick={handlePaymentCancel}>
              Закрыть
            </Button>
          </DialogActions>
        </Dialog>

        {/* Диалог успешной оплаты */}
        <Dialog 
          open={!!paymentSuccess} 
          onClose={() => setPaymentSuccess(null)}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box display="flex" alignItems="center">
              <CheckCircle style={{ color: '#4caf50', marginRight: 8 }} />
              Оплата успешна!
            </Box>
          </DialogTitle>
          
          <DialogContent>
            {paymentSuccess && (
              <Box>
                <Typography variant="body1" gutterBottom>
                  Платеж успешно обработан
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  ID платежа: {paymentSuccess.payment_id}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Провайдер: {paymentSuccess.provider}
                </Typography>
              </Box>
            )}
          </DialogContent>
          
          <DialogActions>
            <Button onClick={() => setPaymentSuccess(null)} variant="contained">
              OK
            </Button>
          </DialogActions>
        </Dialog>
      </div>
    </div>
  );
};

// Компонент модального окна оплаты
const PaymentModal = ({ appointment, onProcessPayment, onClose }) => {
  const [paymentData, setPaymentData] = useState({
    amount: '',
    method: 'cash',
    note: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!paymentData.amount || paymentData.amount <= 0) {
      alert('Введите корректную сумму');
      return;
    }
    onProcessPayment(appointment, paymentData);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Обработка оплаты</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <XCircle className="w-6 h-6" />
          </button>
        </div>

        <div className="mb-4 p-3 bg-gray-50 rounded-lg">
          <div className="font-medium text-gray-900">
            {appointment.patient_name || `Пациент #${appointment.patient_id}`}
          </div>
          <div className="text-sm text-gray-600">
            {appointment.department} • {appointment.appointment_date} {appointment.appointment_time}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Сумма (сум)
            </label>
            <input
              type="number"
              value={paymentData.amount}
              onChange={(e) => setPaymentData({ ...paymentData, amount: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Введите сумму"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Способ оплаты
            </label>
            <select
              value={paymentData.method}
              onChange={(e) => setPaymentData({ ...paymentData, method: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="cash">Наличные</option>
              <option value="card">Банковская карта</option>
              <option value="online">Онлайн оплата</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Примечание (необязательно)
            </label>
            <textarea
              value={paymentData.note}
              onChange={(e) => setPaymentData({ ...paymentData, note: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              rows="2"
              placeholder="Дополнительная информация"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <Button type="submit" className="flex-1">
              <CheckCircle className="w-4 h-4 mr-2" />
              Обработать оплату
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>
              Отмена
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CashierPanel;



