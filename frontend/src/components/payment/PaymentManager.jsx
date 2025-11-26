import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { CreditCard, DollarSign, Receipt, Clock, CheckCircle, XCircle } from 'lucide-react';
import PaymentClick from './PaymentClick';
import PaymentPayMe from './PaymentPayMe';
import './PaymentManager.css';

const API_BASE = '/api/v1';

const PaymentManager = ({ 
  isOpen, 
  onClose, 
  invoiceId = null,
  initialAmount = null,
  patientInfo = null 
}) => {
  // Состояние компонента
  const [selectedProvider, setSelectedProvider] = useState('click');
  const [paymentAmount, setPaymentAmount] = useState(initialAmount || 0);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [createdInvoiceId, setCreatedInvoiceId] = useState(invoiceId);
  
  // Состояние диалогов оплаты
  const [showClickPayment, setShowClickPayment] = useState(false);
  const [showPayMePayment, setShowPayMePayment] = useState(false);

  // Загрузка списка неоплаченных счетов
  useEffect(() => {
    if (isOpen) {
      loadPendingInvoices();
    }
  }, [isOpen]);

  const loadPendingInvoices = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/payments/invoices/pending`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setInvoices(data);
      } else {
        toast.error('Ошибка загрузки счетов');
      }
    } catch (error) {
      console.error('Ошибка загрузки счетов:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  // Создание нового счета для оплаты
  const createPaymentInvoice = async () => {
    if (!paymentAmount || paymentAmount <= 0) {
      toast.error('Введите корректную сумму оплаты');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/payments/invoice/create`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          amount: paymentAmount,
          currency: 'UZS',
          provider: selectedProvider,
          description: `Оплата медицинских услуг${patientInfo ? ` - ${patientInfo.fio}` : ''}`,
          patient_info: patientInfo
        })
      });

      if (response.ok) {
        const result = await response.json();
        setCreatedInvoiceId(result.invoice_id);
        
        // Открываем соответствующий диалог оплаты
        if (selectedProvider === 'click') {
          setShowClickPayment(true);
        } else if (selectedProvider === 'payme') {
          setShowPayMePayment(true);
        }
        
        toast.success('Счет создан, переходим к оплате');
      } else {
        const errorData = await response.json();
        toast.error(`Ошибка создания счета: ${errorData.detail || 'Неизвестная ошибка'}`);
      }
    } catch (error) {
      console.error('Ошибка создания счета:', error);
      toast.error('Ошибка создания счета');
    } finally {
      setLoading(false);
    }
  };

  // Инициация оплаты существующего счета
  const payExistingInvoice = (invoice) => {
    setCreatedInvoiceId(invoice.id);
    setPaymentAmount(invoice.amount);
    
    if (invoice.provider === 'click') {
      setShowClickPayment(true);
    } else if (invoice.provider === 'payme') {
      setShowPayMePayment(true);
    }
  };

  // Обработчики успешной оплаты
  const handlePaymentSuccess = (paymentData) => {
    toast.success('Оплата завершена успешно!');
    setShowClickPayment(false);
    setShowPayMePayment(false);
    loadPendingInvoices(); // Обновляем список счетов
    
    // Уведомляем родительский компонент
    if (onClose) {
      onClose({ success: true, paymentData });
    }
  };

  const handlePaymentError = (error) => {
    toast.error(`Ошибка оплаты: ${error.message}`);
    setShowClickPayment(false);
    setShowPayMePayment(false);
  };

  const handlePaymentClose = () => {
    setShowClickPayment(false);
    setShowPayMePayment(false);
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="payment-manager-overlay">
        <div className="payment-manager-modal">
          <div className="payment-manager-header">
            <h2>
              <CreditCard size={24} />
              Модуль онлайн оплаты
            </h2>
            <button 
              className="close-btn"
              onClick={() => onClose && onClose({ success: false })}
            >
              ✕
            </button>
          </div>

          <div className="payment-manager-content">
            {/* Создание новой оплаты */}
            <div className="payment-section">
              <h3>
                <DollarSign size={20} />
                Новая оплата
              </h3>
              
              <div className="payment-form">
                <div className="form-row">
                  <label>Сумма оплаты (сум)</label>
                  <input
                    type="number"
                    value={paymentAmount}
                    onChange={(e) => setPaymentAmount(Number(e.target.value))}
                    placeholder="Введите сумму"
                    min="1"
                  />
                </div>

                <div className="form-row">
                  <label>Платежный провайдер</label>
                  <div className="provider-options">
                    <label className="radio-option">
                      <input
                        type="radio"
                        name="provider"
                        value="click"
                        checked={selectedProvider === 'click'}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                      />
                      <span>Click</span>
                    </label>
                    
                    <label className="radio-option">
                      <input
                        type="radio"
                        name="provider"
                        value="payme"
                        checked={selectedProvider === 'payme'}
                        onChange={(e) => setSelectedProvider(e.target.value)}
                      />
                      <span>PayMe</span>
                    </label>
                  </div>
                </div>

                {patientInfo && (
                  <div className="patient-info">
                    <p><strong>Пациент:</strong> {patientInfo.fio}</p>
                    <p><strong>Телефон:</strong> {patientInfo.phone}</p>
                  </div>
                )}

                <button 
                  className="create-payment-btn"
                  onClick={createPaymentInvoice}
                  disabled={loading || !paymentAmount}
                >
                  {loading ? 'Создание...' : 'Создать оплату'}
                </button>
              </div>
            </div>

            {/* Список неоплаченных счетов */}
            <div className="invoices-section">
              <h3>
                <Receipt size={20} />
                Неоплаченные счета
              </h3>
              
              {loading ? (
                <div className="loading-state">
                  <Clock size={20} />
                  Загрузка...
                </div>
              ) : invoices.length === 0 ? (
                <div className="empty-state">
                  <CheckCircle size={24} />
                  Нет неоплаченных счетов
                </div>
              ) : (
                <div className="invoices-list">
                  {invoices.map(invoice => (
                    <div key={invoice.id} className="invoice-item">
                      <div className="invoice-info">
                        <div className="invoice-amount">
                          {invoice.amount.toLocaleString()} сум
                        </div>
                        <div className="invoice-details">
                          <span className="invoice-id">№{invoice.id}</span>
                          <span className="invoice-provider">{invoice.provider}</span>
                          <span className="invoice-status">{invoice.status}</span>
                        </div>
                        {invoice.description && (
                          <div className="invoice-description">
                            {invoice.description}
                          </div>
                        )}
                      </div>
                      
                      <button 
                        className="pay-invoice-btn"
                        onClick={() => payExistingInvoice(invoice)}
                        disabled={loading}
                      >
                        Оплатить
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Диалоги оплаты */}
      <PaymentClick
        isOpen={showClickPayment}
        onClose={handlePaymentClose}
        invoiceId={createdInvoiceId}
        totalAmount={paymentAmount}
        currency="UZS"
        onSuccess={handlePaymentSuccess}
        onError={handlePaymentError}
      />
      
      <PaymentPayMe
        isOpen={showPayMePayment}
        onClose={handlePaymentClose}
        invoiceId={createdInvoiceId}
        totalAmount={paymentAmount}
        currency="UZS"
        onSuccess={handlePaymentSuccess}
        onError={handlePaymentError}
      />
    </>
  );
};

export default PaymentManager;

