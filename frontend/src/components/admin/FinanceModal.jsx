import React, { useState, useEffect } from 'react';
import { X, Save, CreditCard, DollarSign, Calendar, User, AlertCircle, Receipt, Building } from 'lucide-react';
import { Card, Button } from '../../design-system/components';

const FinanceModal = ({ 
  isOpen, 
  onClose, 
  transaction = null, 
  onSave, 
  loading = false,
  patients = [],
  doctors = []
}) => {
  const [formData, setFormData] = useState({
    type: 'income',
    category: '',
    amount: '',
    description: '',
    patientId: '',
    doctorId: '',
    paymentMethod: 'cash',
    status: 'completed',
    transactionDate: '',
    notes: '',
    reference: ''
  });
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Инициализация формы при открытии
  useEffect(() => {
    if (isOpen) {
      if (transaction) {
        setFormData({
          type: transaction.type || 'income',
          category: transaction.category || '',
          amount: transaction.amount || '',
          description: transaction.description || '',
          patientId: transaction.patientId || '',
          doctorId: transaction.doctorId || '',
          paymentMethod: transaction.paymentMethod || 'cash',
          status: transaction.status || 'completed',
          transactionDate: transaction.transactionDate || '',
          notes: transaction.notes || '',
          reference: transaction.reference || ''
        });
      } else {
        // Устанавливаем сегодняшний день по умолчанию
        const today = new Date().toISOString().split('T')[0];
        
        setFormData({
          type: 'income',
          category: '',
          amount: '',
          description: '',
          patientId: '',
          doctorId: '',
          paymentMethod: 'cash',
          status: 'completed',
          transactionDate: today,
          notes: '',
          reference: ''
        });
      }
      setErrors({});
    }
  }, [isOpen, transaction]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.type) {
      newErrors.type = 'Тип операции обязателен';
    }

    if (!formData.category) {
      newErrors.category = 'Категория обязательна';
    }

    if (!formData.amount || isNaN(formData.amount) || parseFloat(formData.amount) <= 0) {
      newErrors.amount = 'Сумма должна быть положительным числом';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Описание обязательно';
    }

    if (!formData.transactionDate) {
      newErrors.transactionDate = 'Дата операции обязательна';
    }

    if (formData.paymentMethod === 'card' && !formData.reference.trim()) {
      newErrors.reference = 'Номер карты обязателен для карточных платежей';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setIsSubmitting(true);
    try {
      const transactionData = {
        type: formData.type,
        category: formData.category,
        amount: parseFloat(formData.amount),
        description: formData.description.trim(),
        patientId: formData.patientId ? parseInt(formData.patientId) : null,
        doctorId: formData.doctorId ? parseInt(formData.doctorId) : null,
        paymentMethod: formData.paymentMethod,
        status: formData.status,
        transactionDate: formData.transactionDate,
        notes: formData.notes.trim() || null,
        reference: formData.reference.trim() || null
      };

      await onSave(transactionData);
      onClose();
    } catch (error) {
      console.error('Ошибка сохранения транзакции:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  const getPatientName = (patientId) => {
    const patient = patients.find(p => p.id === parseInt(patientId));
    return patient ? `${patient.lastName} ${patient.firstName} ${patient.middleName}` : '';
  };

  const getDoctorName = (doctorId) => {
    const doctor = doctors.find(d => d.id === parseInt(doctorId));
    return doctor ? `${doctor.name} (${doctor.specialization})` : '';
  };

  const getIncomeCategories = () => [
    'Консультация врача',
    'Диагностика',
    'Лечение',
    'Анализы',
    'Процедуры',
    'Медикаменты',
    'Госпитализация',
    'Другие услуги'
  ];

  const getExpenseCategories = () => [
    'Зарплата персонала',
    'Аренда помещения',
    'Коммунальные услуги',
    'Медикаменты',
    'Оборудование',
    'Маркетинг',
    'Административные расходы',
    'Другие расходы'
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
              {transaction ? 'Редактировать транзакцию' : 'Добавить транзакцию'}
            </h2>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              style={{ color: 'var(--text-secondary)' }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Основная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Тип операции */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Тип операции *
                  </label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                                style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.type}
                      onChange={(e) => handleChange('type', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.type ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.type ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    >
                      <option value="income">Доход</option>
                      <option value="expense">Расход</option>
                    </select>
                  </div>
                  {errors.type && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.type}
                    </p>
                  )}
                </div>

                {/* Категория */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Категория *
                  </label>
                  <div className="relative">
                    <Building className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                              style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.category}
                      onChange={(e) => handleChange('category', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.category ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.category ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    >
                      <option value="">Выберите категорию</option>
                      {(formData.type === 'income' ? getIncomeCategories() : getExpenseCategories()).map(category => (
                        <option key={category} value={category}>{category}</option>
                      ))}
                    </select>
                  </div>
                  {errors.category && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.category}
                    </p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Сумма */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Сумма (UZS) *
                  </label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                                style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="number"
                      value={formData.amount}
                      onChange={(e) => handleChange('amount', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.amount ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.amount ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="100000"
                      min="0"
                      step="1000"
                    />
                  </div>
                  {errors.amount && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.amount}
                    </p>
                  )}
                </div>

                {/* Дата операции */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Дата операции *
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                              style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="date"
                      value={formData.transactionDate}
                      onChange={(e) => handleChange('transactionDate', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.transactionDate ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.transactionDate ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                    />
                  </div>
                  {errors.transactionDate && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.transactionDate}
                    </p>
                  )}
                </div>
              </div>

              {/* Описание */}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Описание *
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    errors.description ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: errors.description ? 'var(--danger-color)' : 'var(--border-color)'
                  }}
                  rows="2"
                  placeholder="Опишите суть операции..."
                />
                {errors.description && (
                  <p className="text-sm text-red-500 mt-1 flex items-center">
                    <AlertCircle className="w-4 h-4 mr-1" />
                    {errors.description}
                  </p>
                )}
              </div>
            </div>

            {/* Связанные данные */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Связанные данные
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Пациент */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Пациент
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.patientId}
                      onChange={(e) => handleChange('patientId', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                    >
                      <option value="">Выберите пациента</option>
                      {patients.map(patient => (
                        <option key={patient.id} value={patient.id}>
                          {patient.lastName} {patient.firstName} {patient.middleName}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Врач */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Врач
                  </label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.doctorId}
                      onChange={(e) => handleChange('doctorId', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                    >
                      <option value="">Выберите врача</option>
                      {doctors.map(doctor => (
                        <option key={doctor.id} value={doctor.id}>
                          {doctor.name} - {doctor.specialization}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </div>

            {/* Платежная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Платежная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Способ оплаты */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Способ оплаты
                  </label>
                  <div className="relative">
                    <CreditCard className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                                style={{ color: 'var(--text-tertiary)' }} />
                    <select
                      value={formData.paymentMethod}
                      onChange={(e) => handleChange('paymentMethod', e.target.value)}
                      className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                    >
                      <option value="cash">Наличные</option>
                      <option value="card">Банковская карта</option>
                      <option value="transfer">Банковский перевод</option>
                      <option value="mobile">Мобильный платеж</option>
                    </select>
                  </div>
                </div>

                {/* Статус */}
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Статус
                  </label>
                  <select
                    value={formData.status}
                    onChange={(e) => handleChange('status', e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                  >
                    <option value="pending">Ожидает</option>
                    <option value="completed">Завершена</option>
                    <option value="cancelled">Отменена</option>
                    <option value="refunded">Возврат</option>
                  </select>
                </div>
              </div>

              {/* Номер карты/ссылка */}
              {formData.paymentMethod === 'card' && (
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                    Номер карты/Транзакции *
                  </label>
                  <div className="relative">
                    <Receipt className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                              style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type="text"
                      value={formData.reference}
                      onChange={(e) => handleChange('reference', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.reference ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.reference ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="**** **** **** 1234"
                    />
                  </div>
                  {errors.reference && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.reference}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Дополнительная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                Дополнительная информация
              </h3>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>
                  Заметки
                </label>
                <textarea
                  value={formData.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  style={{ 
                    background: 'var(--bg-primary)', 
                    color: 'var(--text-primary)',
                    borderColor: 'var(--border-color)'
                  }}
                  rows="3"
                  placeholder="Дополнительная информация о транзакции..."
                />
              </div>
            </div>

            {/* Предварительный просмотр */}
            {(formData.amount && formData.description) && (
              <div className="space-y-4">
                <h3 className="text-lg font-medium" style={{ color: 'var(--text-primary)' }}>
                  Предварительный просмотр
                </h3>
                <div className="p-4 rounded-lg" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                  <div className="space-y-2">
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Тип:</strong> {formData.type === 'income' ? 'Доход' : 'Расход'}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Категория:</strong> {formData.category}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Сумма:</strong> {formData.amount ? `${parseInt(formData.amount).toLocaleString('ru-RU')} UZS` : ''}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Описание:</strong> {formData.description}
                    </p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      <strong>Дата:</strong> {formData.transactionDate}
                    </p>
                    {formData.patientId && (
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <strong>Пациент:</strong> {getPatientName(formData.patientId)}
                      </p>
                    )}
                    {formData.doctorId && (
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                        <strong>Врач:</strong> {getDoctorName(formData.doctorId)}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Кнопки */}
            <div className="flex gap-3 pt-4">
              <Button
                type="submit"
                disabled={isSubmitting || loading}
                className="flex-1"
                style={{ 
                  background: 'var(--accent-color)',
                  color: 'white'
                }}
              >
                {isSubmitting ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                    Сохранение...
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    {transaction ? 'Сохранить изменения' : 'Добавить транзакцию'}
                  </>
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                Отмена
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
};

export default FinanceModal;
