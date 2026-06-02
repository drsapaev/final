import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Save, User, Mail, Phone, MapPin } from 'lucide-react';
import {
  Label,
  MacOSAlert,
  MacOSButton,
  MacOSCheckbox,
  MacOSBadge,
  MacOSInput,
  MacOSModal,
  Select,
} from '../ui/macos';
import PropTypes from 'prop-types';

const DoctorModal = ({
  isOpen,
  onClose,
  doctor = null,
  onSave,
  loading = false,
  availableUsers = [],
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
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          marginTop: '4px',
          fontSize: '12px',
          color: 'var(--mac-error)',
        }}
      >
        <AlertCircle size={14} />
        {errors[field]}
      </div>
    ) : null;

  return (
    <MacOSModal
      isOpen={isOpen}
      onClose={onClose}
      title={doctor ? 'Редактировать врача' : 'Добавить врача'}
      size="lg"
    >
      <form
        onSubmit={handleSubmit}
        style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
      >
        {submitError ? (
          <MacOSAlert type="error" style={{ marginBottom: '12px' }}>
            {submitError}
          </MacOSAlert>
        ) : null}

        <div>
          <Label required style={{ display: 'block', marginBottom: '8px' }}>
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
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>ФИО</Label>
            <MacOSInput value={selectedUser?.full_name || ''} readOnly icon={User} />
          </div>
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>Email</Label>
            <MacOSInput value={selectedUser?.email || ''} readOnly icon={Mail} />
          </div>
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>Телефон</Label>
            <MacOSInput value={selectedUser?.phone || ''} readOnly icon={Phone} />
          </div>
          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>Роль</Label>
            <MacOSInput value={selectedUser?.role || ''} readOnly />
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <MacOSBadge variant={selectedUserStatus.variant}>
            {selectedUserStatus.label}
          </MacOSBadge>
          <MacOSBadge variant={formData.cabinet ? 'info' : 'warning'}>
            {formData.cabinet ? `Кабинет ${formData.cabinet}` : 'Кабинет не задан'}
          </MacOSBadge>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '16px',
          }}
        >
          <div>
            <Label required style={{ display: 'block', marginBottom: '8px' }}>
              Специальность
            </Label>
            <MacOSInput
              value={formData.specialty}
              onChange={(event) => handleChange('specialty', event.target.value)}
              placeholder="cardiology, dermatology, dentistry..."
            />
            {renderFieldError('specialty')}
          </div>

          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>Кабинет</Label>
            <MacOSInput
              value={formData.cabinet}
              onChange={(event) => handleChange('cabinet', event.target.value)}
              placeholder="101"
              icon={MapPin}
            />
          </div>

          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Цена по умолчанию
            </Label>
            <MacOSInput
              type="number"
              value={formData.priceDefault}
              onChange={(event) => handleChange('priceDefault', event.target.value)}
              placeholder="0"
            />
            {renderFieldError('priceDefault')}
          </div>

          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Стартовый номер онлайн
            </Label>
            <MacOSInput
              type="number"
              min="1"
              value={formData.startNumberOnline}
              onChange={(event) => handleChange('startNumberOnline', event.target.value)}
            />
            {renderFieldError('startNumberOnline')}
          </div>

          <div>
            <Label style={{ display: 'block', marginBottom: '8px' }}>
              Онлайн записей в день
            </Label>
            <MacOSInput
              type="number"
              min="1"
              value={formData.maxOnlinePerDay}
              onChange={(event) => handleChange('maxOnlinePerDay', event.target.value)}
            />
            {renderFieldError('maxOnlinePerDay')}
          </div>
        </div>

        <div>
          <MacOSCheckbox
            checked={formData.active}
            onChange={(checked) => handleChange('active', checked)}
            label="Врач активен"
            description="Неактивные врачи не участвуют в текущих операционных сценариях."
          />
        </div>

        <div
          style={{
            display: 'flex',
            gap: '12px',
            justifyContent: 'flex-end',
            paddingTop: '16px',
            borderTop: '1px solid var(--mac-separator)',
          }}
        >
          <MacOSButton type="button" variant="outline" onClick={onClose} disabled={loading}>
            Отмена
          </MacOSButton>
          <MacOSButton type="submit" disabled={loading} icon={<Save size={16} />}>
            {doctor ? 'Сохранить изменения' : 'Добавить врача'}
          </MacOSButton>
        </div>
      </form>
    </MacOSModal>
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
