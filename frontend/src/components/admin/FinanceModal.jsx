import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { X, Save, DollarSign, Calendar, AlertCircle, Receipt } from 'lucide-react';
import { MacOSCard, Button,
  Input } from '../ui/macos';
import {
  Select,
} from '../ui/macos';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const getTransactionTypeOptions = (t) => [
  { value: 'income', label: t('admin2.fm_type_income') },
  { value: 'expense', label: t('admin2.fm_type_expense') }
];

const getPaymentMethodOptions = (t) => [
  { value: 'cash', label: t('admin2.fm_payment_cash') },
  { value: 'card', label: t('admin2.fm_payment_card') },
  { value: 'transfer', label: t('admin2.fm_payment_transfer') },
  { value: 'mobile', label: t('admin2.fm_payment_mobile') }
];

const getStatusOptions = (t) => [
  { value: '', label: t('admin2.fm_status_not_set') },
  { value: 'pending', label: t('admin2.fm_status_pending') },
  { value: 'completed', label: t('admin2.fm_status_completed') },
  { value: 'cancelled', label: t('admin2.fm_status_cancelled') },
  { value: 'refunded', label: t('admin2.fm_status_refunded') }
];

const getIncomeCategories = (t) => [
  t('admin2.fm_cat_income_consultation'),
  t('admin2.fm_cat_income_diagnostics'),
  t('admin2.fm_cat_income_treatment'),
  t('admin2.fm_cat_income_analyses'),
  t('admin2.fm_cat_income_procedures'),
  t('admin2.fm_cat_income_medications'),
  t('admin2.fm_cat_income_hospitalization'),
  t('admin2.fm_cat_income_other')
];

const getExpenseCategories = (t) => [
  t('admin2.fm_cat_expense_salary'),
  t('admin2.fm_cat_expense_rent'),
  t('admin2.fm_cat_expense_utilities'),
  t('admin2.fm_cat_expense_medications'),
  t('admin2.fm_cat_expense_equipment'),
  t('admin2.fm_cat_expense_marketing'),
  t('admin2.fm_cat_expense_admin'),
  t('admin2.fm_cat_expense_other')
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
  const { t } = useTranslation();

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
      newErrors.type = t('admin2.fm_err_type_required');
    }

    if (!formData.category) {
      newErrors.category = t('admin2.fm_err_category_required');
    }

    if (!formData.amount || isNaN(formData.amount) || parseFloat(formData.amount) <= 0) {
      newErrors.amount = t('admin2.fm_err_amount_positive');
    }

    if (!formData.description.trim()) {
      newErrors.description = t('admin2.fm_err_description_required');
    }

    if (!formData.transactionDate) {
      newErrors.transactionDate = t('admin2.fm_err_date_required');
    }

    if (formData.paymentMethod === 'card' && !formData.reference.trim()) {
      newErrors.reference = t('admin2.fm_err_reference_required');
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <MacOSCard className="w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Заголовок */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold admin-text-primary">
              {transaction ? t('admin2.fm_title_edit') : t('admin2.fm_title_add')}
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
                {t('admin2.fm_section_basic')}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Тип операции */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_type')}
                  </label>
                  <Select
                    value={formData.type}
                    onChange={(value) => handleChange('type', value)}
                    options={getTransactionTypeOptions(t)}
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
                    {t('admin2.fm_label_category')}
                  </label>
                  <Select
                    value={formData.category}
                    onChange={(value) => handleChange('category', value)}
                    options={[
                      { value: '', label: t('admin2.fm_placeholder_category') },
                      ...(formData.type === 'income' ? getIncomeCategories(t) : getExpenseCategories(t)).map((category) => ({
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
                    {t('admin2.fm_label_amount')}
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
                    {t('admin2.fm_amount_hint')}
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
                    {t('admin2.fm_label_date')}
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
                  {t('admin2.fm_label_description')}
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
                  placeholder={t('admin2.fm_placeholder_description')}
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
                {t('admin2.fm_section_related')}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Пациент */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_patient')}
                  </label>
                  <Select
                    value={formData.patientId === '' ? '' : String(formData.patientId)}
                    onChange={(value) => handleChange('patientId', value)}
                    options={[
                      { value: '', label: t('admin2.fm_placeholder_patient') },
                      ...patients.map((patient) => ({
                        value: String(patient.id),
                        label: [patient.lastName, patient.firstName, patient.middleName]
                          .filter(Boolean)
                          .join(' ') || patient.fullName || patient.name || t('admin2.fm_patient_fallback', { id: patient.id })
                      }))
                    ]}
                    size="large"
                    className="admin-w-full" />
                </div>

                {/* Врач */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_doctor')}
                  </label>
                  <Select
                    value={formData.doctorId === '' ? '' : String(formData.doctorId)}
                    onChange={(value) => handleChange('doctorId', value)}
                    options={[
                      { value: '', label: t('admin2.fm_placeholder_doctor') },
                      ...doctors.map((doctor) => ({
                        value: String(doctor.id),
                        label: getDoctorName(doctor.id) || doctor.user?.full_name || doctor.name || t('admin2.fm_doctor_fallback', { id: doctor.id })
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
                {t('admin2.fm_section_payment')}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Способ оплаты */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_payment_method')}
                  </label>
                  <Select
                    value={formData.paymentMethod}
                    onChange={(value) => handleChange('paymentMethod', value)}
                    options={getPaymentMethodOptions(t)}
                    size="large"
                    className="admin-w-full" />
                </div>

                {/* Статус */}
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_status')}
                  </label>
                  <Select
                    value={formData.status}
                    onChange={(value) => handleChange('status', value)}
                    options={getStatusOptions(t)}
                    size="large"
                    className="admin-w-full" />
                </div>
              </div>

              {/* Номер карты/ссылка */}
              {formData.paymentMethod === 'card' && (
                <div>
                  <label className="block text-sm font-medium mb-1 admin-text-primary">
                    {t('admin2.fm_label_reference')}
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
                {t('admin2.fm_section_extra')}
              </h3>
              <div>
                <label className="block text-sm font-medium mb-1 admin-text-primary">
                  {t('admin2.fm_label_notes')}
                </label>
                <textarea
                  aria-label="Finance transaction notes"
                  value={formData.notes}
                  onChange={(e) => handleChange('notes', e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent admin-form-control"
                  rows="3"
                  placeholder={t('admin2.fm_placeholder_notes')}
                />
              </div>
            </div>

            {/* Предварительный просмотр */}
            {(formData.amount && formData.description) && (
              <div className="space-y-4">
                <h3 className="text-lg font-medium admin-text-primary">
                  {t('admin2.fm_section_preview')}
                </h3>
                <div className="p-4 rounded-lg admin-modal-preview-box">
                  <div className="space-y-2">
                    <p className="text-sm admin-text-secondary">
                      <strong>{t('admin2.fm_preview_type')}</strong> {formData.type === 'income' ? t('admin2.fm_type_income') : t('admin2.fm_type_expense')}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>{t('admin2.fm_preview_category')}</strong> {formData.category}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>{t('admin2.fm_preview_amount')}</strong> {formData.amount ? `${parseInt(formData.amount).toLocaleString('ru-RU')} UZS` : ''}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>{t('admin2.fm_preview_description')}</strong> {formData.description}
                    </p>
                    <p className="text-sm admin-text-secondary">
                      <strong>{t('admin2.fm_preview_date')}</strong> {formData.transactionDate}
                    </p>
                    {formData.patientId && (
                      <p className="text-sm admin-text-secondary">
                        <strong>{t('admin2.fm_preview_patient')}</strong> {getPatientName(formData.patientId)}
                      </p>
                    )}
                    {formData.doctorId && (
                      <p className="text-sm admin-text-secondary">
                        <strong>{t('admin2.fm_preview_doctor')}</strong> {getDoctorName(formData.doctorId)}
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
                    {t('admin2.fm_saving')}
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    {transaction ? t('admin2.fm_save_changes') : t('admin2.fm_title_add')}
                  </>
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isSubmitting}
              >
                {t('admin2.fm_cancel')}
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
