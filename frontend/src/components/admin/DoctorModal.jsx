import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Save, User, Mail, Phone, MapPin } from 'lucide-react';
import {
  Label,
  Alert,
  Button,
  Checkbox,
  Badge,
  Input,
  Modal,
  Select,
} from '../ui/macos';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const DoctorModal = ({
  isOpen,
  onClose,
  doctor = null,
  onSave,
  loading = false,
  availableUsers = [],
  departments = [],
}) => {
  const [formData, setFormData] = useState({
    userId: '',
    specialty: '',
    cabinet: '',
    priceDefault: '',
    startNumberOnline: '1',
    maxOnlinePerDay: '15',
    active: true,
  });
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setFormData({
      userId: doctor?.user_id ? String(doctor.user_id) : '',
      specialty: doctor?.specialty || '',
      cabinet: doctor?.cabinet || '',
      priceDefault:
        doctor?.price_default === null || doctor?.price_default === undefined
          ? ''
          : String(doctor.price_default),
      startNumberOnline:
        doctor?.start_number_online === null || doctor?.start_number_online === undefined
          ? '1'
          : String(doctor.start_number_online),
      maxOnlinePerDay:
        doctor?.max_online_per_day === null || doctor?.max_online_per_day === undefined
          ? '15'
          : String(doctor.max_online_per_day),
      active: doctor?.active !== false,
    });
    setErrors({});
    setSubmitError(null);
  }, [doctor, isOpen]);

  const selectedUser = useMemo(() => {
    const fallbackUser = doctor?.user || null;
    const fromList = availableUsers.find(
      (item) => String(item.id) === String(formData.userId)
    );
    return fromList || fallbackUser;
  }, [availableUsers, doctor?.user, formData.userId]);

  const selectedUserStatus = useMemo(() => {
    if (!selectedUser) return { variant: 'warning', label: 'Пользователь не выбран' };
    if (selectedUser.is_active === false) {
      return { variant: 'warning', label: 'Аккаунт пользователя неактивен' };
    }
    if (selectedUser.linked_doctor_id && String(selectedUser.linked_doctor_id) !== String(doctor?.id || '')) {
      return { variant: 'warning', label: `Уже связан с врачом #${selectedUser.linked_doctor_id}` };
    }
    return { variant: 'success', label: 'Связь активна' };
  }, [doctor?.id, selectedUser]);

  const userOptions = useMemo(
    () => [
      { value: '', label: 'Выберите пользователя' },
      ...availableUsers.map((user) => ({
        value: String(user.id),
        label: `${user.full_name || user.username} • ${user.role}${user.is_active ? '' : ' • неактивен'}`,
      })),
    ],
    [availableUsers]
  );

  const validateForm = () => {
    const nextErrors = {};
    if (!formData.userId) {
      nextErrors.userId = 'Нужно выбрать существующий аккаунт пользователя';
    }
    if (!formData.specialty.trim()) {
      nextErrors.specialty = 'Специальность обязательна';
    } else if (!/^[a-z][a-z0-9_]*$/.test(formData.specialty.trim())) {
      // PR-19: validate specialty format — must match queue_tag pattern
      nextErrors.specialty = 'Только латинские буквы в нижнем регистре, цифры и _ (например: cardiology)';
    }
    if (formData.priceDefault !== '' && Number.isNaN(Number(formData.priceDefault))) {
      nextErrors.priceDefault = 'Цена должна быть числом';
    }
    if (formData.startNumberOnline !== '' && Number.isNaN(Number(formData.startNumberOnline))) {
      nextErrors.startNumberOnline = 'Стартовый номер должен быть числом';
    }
    if (formData.maxOnlinePerDay !== '' && Number.isNaN(Number(formData.maxOnlinePerDay))) {
      nextErrors.maxOnlinePerDay = 'Лимит онлайн-записей должен быть числом';
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleChange = (field, value) => {
    setFormData((current) => ({ ...current, [field]: value }));
    if (errors[field]) {
      setErrors((current) => ({ ...current, [field]: null }));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!validateForm()) {
      return;
    }

    try {
      await onSave({
        userId: formData.userId,
        specialty: formData.specialty.trim(),
        cabinet: formData.cabinet.trim(),
        priceDefault: formData.priceDefault,
        startNumberOnline: formData.startNumberOnline,
        maxOnlinePerDay: formData.maxOnlinePerDay,
        active: formData.active,
      });
      onClose();
    } catch (error) {
      setSubmitError(error.message || 'Ошибка сохранения врача');
    }
  };

  const renderFieldError = (field) =>
    errors[field] ? (
      <div
        className="admin-field-error"
      >
        <AlertCircle size={14} />
        {errors[field]}
      </div>
    ) : null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={doctor ? 'Редактировать врача' : 'Добавить врача'}
      size="lg"
    >
      <form
        onSubmit={handleSubmit}
        className="admin-flex-col-20"
      >
        {submitError ? (
          <Alert type="error" className="admin-mb-12">
            {submitError}
          </Alert>
        ) : null}

        <div>
          <Label required className="admin-label-block-mb-8">
            Пользователь
          </Label>
          <Select
            value={formData.userId}
            onChange={(value) => handleChange('userId', value)}
            options={userOptions}
            disabled={loading}
            size="large"
          />
          {renderFieldError('userId')}
        </div>

        <div
          className="admin-grid-autofit-220-16"
        >
          <div>
            <Label className="admin-label-block-mb-8">ФИО</Label>
            <Input value={selectedUser?.full_name || ''} readOnly icon={User} />
          </div>
          <div>
            <Label className="admin-label-block-mb-8">Email</Label>
            <Input value={selectedUser?.email || ''} readOnly icon={Mail} />
          </div>
          <div>
            <Label className="admin-label-block-mb-8">{t('common.phone')}</Label>
            <Input value={selectedUser?.phone || ''} readOnly icon={Phone} />
          </div>
          <div>
            <Label className="admin-label-block-mb-8">Роль</Label>
            <Input value={selectedUser?.role || ''} readOnly />
          </div>
        </div>

        <div className="admin-flex-wrap-8">
          <Badge variant={selectedUserStatus.variant}>
            {selectedUserStatus.label}
          </Badge>
          <Badge variant={formData.cabinet ? 'info' : 'warning'}>
            {formData.cabinet ? `Кабинет ${formData.cabinet}` : 'Кабинет не задан'}
          </Badge>
        </div>

        <div
          className="admin-grid-autofit-220-16"
        >
          <div>
            <Label required className="admin-label-block-mb-8">
              Специальность
            </Label>
            {departments.length > 0 ? (
              <Select
                value={formData.specialty}
                onChange={(value) => handleChange('specialty', value)}
                options={[
                  { value: '', label: '— Выберите отделение —' },
                  ...departments.map((d) => ({ value: d.value, label: d.label })),
                ]}
                size="large"
              />
            ) : (
              <Input
                value={formData.specialty}
                onChange={(event) => handleChange('specialty', event.target.value)}
                placeholder="cardiology, dermatology, dentistry..."
              />
            )}
            {renderFieldError('specialty')}
            <div className="admin-hint-text-12-secondary-mt-4">
              Должно совпадать с key отделения (например: cardiology, derma, dental)
            </div>
          </div>

          <div>
            <Label className="admin-label-block-mb-8">{t('common.cabinet')}</Label>
            <Input
              value={formData.cabinet}
              onChange={(event) => handleChange('cabinet', event.target.value)}
              placeholder="101"
              icon={MapPin}
            />
          </div>

          <div>
            <Label className="admin-label-block-mb-8">
              Цена по умолчанию
            </Label>
            <Input
              type="number"
              value={formData.priceDefault}
              onChange={(event) => handleChange('priceDefault', event.target.value)}
              placeholder="0"
            />
            {renderFieldError('priceDefault')}
          </div>

          <div>
            <Label className="admin-label-block-mb-8">
              Стартовый номер онлайн
            </Label>
            <Input
              type="number"
              min="1"
              value={formData.startNumberOnline}
              onChange={(event) => handleChange('startNumberOnline', event.target.value)}
            />
            {renderFieldError('startNumberOnline')}
          </div>

          <div>
            <Label className="admin-label-block-mb-8">
              Онлайн записей в день
            </Label>
            <Input
              type="number"
              min="1"
              value={formData.maxOnlinePerDay}
              onChange={(event) => handleChange('maxOnlinePerDay', event.target.value)}
            />
            {renderFieldError('maxOnlinePerDay')}
          </div>
        </div>

        <div>
          <Checkbox
            checked={formData.active}
            onChange={(checked) => handleChange('active', checked)}
            label="Врач активен"
            description="Неактивные врачи не участвуют в текущих операционных сценариях."
          />
        </div>

        <div
          className="admin-modal-actions-footer"
        >
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            Отмена
          </Button>
          <Button type="submit" disabled={loading} icon={<Save size={16} />}>
            {doctor ? 'Сохранить изменения' : 'Добавить врача'}
          </Button>
        </div>
      </form>
    </Modal>
  );
};

DoctorModal.propTypes = {
  availableUsers: PropTypes.array,
  doctor: PropTypes.any,
  isOpen: PropTypes.any,
  loading: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
};

export default DoctorModal;
