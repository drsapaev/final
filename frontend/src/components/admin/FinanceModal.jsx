import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { X, Save, DollarSign, Calendar, AlertCircle, Receipt } from 'lucide-react';
import { MacOSCard, Button,
  Input} from '../ui/macos';
import {
  Select,
} from '../ui/macos';

import logger from '../../utils/logger';

const TRANSACTION_TYPE_OPTIONS = [
  { value: 'income', label: '\u0414\u043e\u0445\u043e\u0434' },
  { value: 'expense', label: '\u0420\u0430\u0441\u0445\u043e\u0434' }
];

const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: '\u041d\u0430\u043b\u0438\u0447\u043d\u044b\u0435' },
  { value: 'card', label: '\u0411\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0430\u044f \u043a\u0430\u0440\u0442\u0430' },
  { value: 'transfer', label: '\u0411\u0430\u043d\u043a\u043e\u0432\u0441\u043a\u0438\u0439 \u043f\u0435\u0440\u0435\u0432\u043e\u0434' },
  { value: 'mobile', label: '\u041c\u043e\u0431\u0438\u043b\u044c\u043d\u044b\u0439 \u043f\u043b\u0430\u0442\u0435\u0436' }
];

const STATUS_OPTIONS = [
  { value: '', label: '\u0421\u0442\u0430\u0442\u0443\u0441 \u043d\u0435 \u043f\u0435\u0440\u0435\u0434\u0430\u043d' },
  { value: 'pending', label: '\u041e\u0436\u0438\u0434\u0430\u0435\u0442' },
  { value: 'completed', label: '\u0417\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430' },
  { value: 'cancelled', label: '\u041e\u0442\u043c\u0435\u043d\u0435\u043d\u0430' },
  { value: 'refunded', label: '\u0412\u043e\u0437\u0432\u0440\u0430\u0442' }
];
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
          status: transaction.status ?? '',
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

    if (!validateForm()) {
      logger.warn('[FIX:FINANCE-AMOUNT-STEP] Blocked invalid finance submission', {
        amount: formData.amount,
        paymentMethod: formData.paymentMethod,
        status: formData.status
      });
      return;
    }

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

      logger.info('[FIX:FINANCE-AMOUNT-STEP] Submitting finance transaction', {
        amount: transactionData.amount,
        type: transactionData.type,
        category: transactionData.category,
        paymentMethod: transactionData.paymentMethod
      });

      await onSave(transactionData);
      onClose();
    } catch (error) {
      logger.error('Ошибка сохранения транзакции:', error);
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
    const patient = patients.find((p) => p.id === parseInt(patientId, 10));
    if (!patient) return '';

    const fullName = [patient.lastName, patient.firstName, patient.middleName]
      .filter(Boolean)
      .join(' ');
    return fullName || patient.fullName || patient.name || '';
  };

  const getDoctorName = (doctorId) => {
    const doctor = doctors.find((d) => d.id === parseInt(doctorId, 10));
    if (!doctor) return '';

    const doctorName =
      doctor.user?.full_name ||
      doctor.fullName ||
      doctor.name ||
      doctor.user?.username ||
      '';
    const specialization = doctor.specialty || doctor.specialization || '';

    if (doctorName && specialization) {
      return `${doctorName} (${specialization})`;
    }

    return doctorName || specialization || '';
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
      <MacOSCard className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold admin-text-primary">
              {transaction ? 'Редактировать транзакцию' : 'Добавить транзакцию'}
            </h2>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors admin-text-secondary"
              aria-label="Close finance transaction modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Форма */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Основная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium admin-text-primary">
                Основная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Тип операции */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Тип операции *
                  </label>
                  <Select
                    value={formData.type}
                    onChange={(value) => handleChange('type', value)}
                    options={TRANSACTION_TYPE_OPTIONS}
                    size="large"
                    className="admin-w-full" />
                  {errors.type && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.type}
                    </p>
                  )}
                </div>

                {/* Категория */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Категория *
                  </label>
                  <Select
                    value={formData.category}
                    onChange={(value) => handleChange('category', value)}
                    options={[
                      { value: '', label: '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044e' },
                      ...(formData.type === 'income' ? getIncomeCategories() : getExpenseCategories()).map((category) => ({
                        value: category,
                        label: category
                      }))
                    ]}
                    size="large"
                    className="admin-w-full" />
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
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Сумма (UZS) *
                  </label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 admin-text-tertiary" />
                    <Input
                      type="number"
                      aria-label="Finance transaction amount"
                      value={formData.amount}
                      onChange={(e) => handleChange('amount', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-modal-input-bd-dyn ${
                        errors.amount ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ '--admin-bd': errors.amount ? 'var(--mac-danger)' : 'var(--mac-border)' }}
                      placeholder="100000"
                      min="1"
                      step="1"
                      inputMode="numeric"
                      aria-describedby="finance-amount-help"
                    />
                  </div>
                  <p id="finance-amount-help" className="text-xs mt-1 admin-text-tertiary">
                    Введите сумму целым числом в UZS. Например: 12500.
                  </p>
                  {errors.amount && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.amount}
                    </p>
                  )}
                </div>

                {/* Дата операции */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Дата операции *
                  </label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 admin-text-tertiary" />
                    <Input
                      type="date"
                      aria-label="Finance transaction date"
                      value={formData.transactionDate}
                      onChange={(e) => handleChange('transactionDate', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-modal-input-bd-dyn ${
                        errors.transactionDate ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ '--admin-bd': errors.transactionDate ? 'var(--mac-danger)' : 'var(--mac-border)' }}
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
                <label className="block text-sm font-medium mb-1 admin-text-primary">
                  Описание *
                </label>
                <textarea
                  aria-label="Finance transaction description"
                  value={formData.description}
                  onChange={(e) => handleChange('description', e.target.value)}
                  className={`w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-modal-input-bd-dyn ${
                    errors.description ? 'border-red-500' : 'border-gray-300'
                  }`}
                  style={{ '--admin-bd': errors.description ? 'var(--mac-danger)' : 'var(--mac-border)' }}
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
              <h3 className="text-lg font-medium admin-text-primary">
                Связанные данные
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Пациент */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Пациент
                  </label>
                  <Select
                    value={formData.patientId === '' ? '' : String(formData.patientId)}
                    onChange={(value) => handleChange('patientId', value)}
                    options={[
                      { value: '', label: '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u0446\u0438\u0435\u043d\u0442\u0430' },
                      ...patients.map((patient) => ({
                        value: String(patient.id),
                        label: [patient.lastName, patient.firstName, patient.middleName]
                          .filter(Boolean)
                          .join(' ') || patient.fullName || patient.name || `\u041f\u0430\u0446\u0438\u0435\u043d\u0442 #${patient.id}`
                      }))
                    ]}
                    size="large"
                    className="admin-w-full" />
                </div>

                {/* Врач */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Врач
                  </label>
                  <Select
                    value={formData.doctorId === '' ? '' : String(formData.doctorId)}
                    onChange={(value) => handleChange('doctorId', value)}
                    options={[
                      { value: '', label: '\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0432\u0440\u0430\u0447\u0430' },
                      ...doctors.map((doctor) => ({
                        value: String(doctor.id),
                        label: getDoctorName(doctor.id) || doctor.user?.full_name || doctor.name || `\u0412\u0440\u0430\u0447 #${doctor.id}`
                      }))
                    ]}
                    size="large"
                    className="admin-w-full" />
                </div>
              </div>
            </div>

            {/* Платежная информация */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium admin-text-primary">
                Платежная информация
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Способ оплаты */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Способ оплаты
                  </label>
                  <Select
                    value={formData.paymentMethod}
                    onChange={(value) => handleChange('paymentMethod', value)}
                    options={PAYMENT_METHOD_OPTIONS}
                    size="large"
                    className="admin-w-full" />
                </div>

                {/* Статус */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Статус
                  </label>
                  <Select
                    value={formData.status}
                    onChange={(value) => handleChange('status', value)}
                    options={STATUS_OPTIONS}
                    size="large"
                    className="admin-w-full" />
                </div>
              </div>

              {/* Номер карты/ссылка */}
              {formData.paymentMethod === 'card' && (
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    Номер карты/Транзакции *
                  </label>
                  <div className="relative">
                    <Receipt className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 admin-text-tertiary" />
                    <Input
                      type="text"
                      aria-label="Finance card or transaction reference"
                      value={formData.reference}
                      onChange={(e) => handleChange('reference', e.target.value)}
                      className={`w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-modal-input-bd-dyn ${
                        errors.reference ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ '--admin-bd': errors.reference ? 'var(--mac-danger)' : 'var(--mac-border)' }}
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
              <h3 className="text-lg font-medium admin-text-primary">
                Дополнительная информация
              </h3>
              <div>
                <label className="block text-sm font-medium mb-1 admin-text-primary">
                  Заметки
                </label>
                <textarea
                  aria-label="Finance transaction notes"
                  value={formData.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-form-control"
                  rows="3"
                  placeholder="Дополнительная информация о транзакции..."
                />
              </div>
            </div>

            {/* Предварительный просмотр */}
            {(formData.amount && formData.description) && (
              <div className="space-y-4">
                <h3 className="text-lg font-medium admin-text-primary">
                  Предварительный просмотр
                </h3>
                <div className="p-4 rounded-lg admin-modal-preview-box">
                  <div className="space-y-2">
                    <p className="text-sm admin-text-secondary">
                      <strong>Тип:</strong> {formData.type === 'income' ? 'Доход' : 'Расход'}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>Категория:</strong> {formData.category}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>Сумма:</strong> {formData.amount ? `${parseInt(formData.amount).toLocaleString('ru-RU')} UZS` : ''}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>Описание:</strong> {formData.description}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>Дата:</strong> {formData.transactionDate}
                    </p>
                    {formData.patientId && (
                      <p className="text-sm admin-text-secondary">
                        <strong>Пациент:</strong> {getPatientName(formData.patientId)}
                      </p>
                    )}
                    {formData.doctorId && (
                      <p className="text-sm admin-text-secondary">
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
                aria-label={transaction ? 'Save transaction changes' : 'Add transaction'}
                className="flex-1 admin-modal-submit-btn"
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
      </MacOSCard>
    </div>
  );
};

export default FinanceModal;

FinanceModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  transaction: PropTypes.shape({
    type: PropTypes.string,
    category: PropTypes.string,
    amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    description: PropTypes.string,
    patientId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    doctorId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    paymentMethod: PropTypes.string,
    status: PropTypes.string,
    transactionDate: PropTypes.string,
    notes: PropTypes.string,
    reference: PropTypes.string
  }),
  onSave: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  patients: PropTypes.arrayOf(PropTypes.object),
  doctors: PropTypes.arrayOf(PropTypes.object)
};

