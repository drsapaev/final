import { useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Check, X, ArrowLeft, AlertTriangle } from 'lucide-react';
import {
  Button, MacOSCard,
  Input,
  Checkbox } from '../components/ui/macos';
import { initializeSetup } from '../api/setup';
import { getCanonicalRouteById } from '../routing/routeSelectors';
import logger from '../utils/logger';
import './Setup.css';
import { useTranslation } from '../i18n/useTranslation';

// ============================================================================
// UX Audit Stage 2 — Setup.jsx full rewrite
// ============================================================================
// Применены все правки из UX_AUDIT.md, раздел 2:
//   2.1 (critical): Поле «Повторите пароль» + индикатор силы + «Показать пароль»
//   2.1 (critical): adminUsername пустой по умолчанию (раньше 'admin')
//   2.2: Timezone как <select> с IANA-списком
//   2.2: Чекбокс «Филиал = клиника» (auto-copy полей)
//   2.2: Real-time валидация на blur + hint только после первой попытки submit
//   2.2: Кнопка «Назад» / «Отмена»
//   2.2: Перенос «Ключ активации» в отдельную секцию
//   2.2: Замена placeholder «optional» → «(необязательно)»
//   2.5: CSS media queries для мобильных (отдельный Setup.css файл)
// ============================================================================

const initialForm = {
  clinicName: '',
  clinicAddress: '',
  clinicPhone: '',
  clinicEmail: '',
  clinicTimezone: 'Asia/Tashkent',
  clinicLogoUrl: '',
  branchName: '',
  branchCode: '',
  branchAddress: '',
  branchPhone: '',
  branchEmail: '',
  branchTimezone: 'Asia/Tashkent',
  // UX Audit Stage 2 (Setup issue 2.1): adminUsername пустой по умолчанию.
  // Раньше 'admin' — предсказуемое имя, снижает безопасность.
  adminUsername: '',
  adminPassword: '',
  // UX Audit Stage 2 (Setup issue 2.1): добавлено поле подтверждения пароля.
  adminPasswordConfirm: '',
  adminFullName: '',
  adminEmail: '',
  activationKey: ''
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// UX Audit Stage 2 (Setup issue 2.2): список IANA-таймзон для <select>.
// Ограничен наиболее релевантными для СНГ/Узбекистана, плюс популярные мировые.
// Полный список IANA был бы ~400 пунктов — это перегрузка для администратора клиники.
const TIMEZONES = [
  // Узбекистан и Центральная Азия
  { value: 'Asia/Tashkent', labelKey: 'misc.setup_tz_tashkent' },
  { value: 'Asia/Samarkand', labelKey: 'misc.setup_tz_samarkand' },
  { value: 'Asia/Almaty', labelKey: 'misc.setup_tz_almaty' },
  { value: 'Asia/Bishkek', labelKey: 'misc.setup_tz_bishkek' },
  { value: 'Asia/Ashgabat', labelKey: 'misc.setup_tz_ashgabat' },
  { value: 'Asia/Dushanbe', labelKey: 'misc.setup_tz_dushanbe' },
  // Россия
  { value: 'Europe/Moscow', labelKey: 'misc.setup_tz_moscow' },
  { value: 'Europe/Samara', labelKey: 'misc.setup_tz_samara' },
  { value: 'Asia/Yekaterinburg', labelKey: 'misc.setup_tz_yekaterinburg' },
  { value: 'Asia/Omsk', labelKey: 'misc.setup_tz_omsk' },
  { value: 'Asia/Novosibirsk', labelKey: 'misc.setup_tz_novosibirsk' },
  { value: 'Asia/Krasnoyarsk', labelKey: 'misc.setup_tz_krasnoyarsk' },
  { value: 'Asia/Irkutsk', labelKey: 'misc.setup_tz_irkutsk' },
  { value: 'Asia/Yakutsk', labelKey: 'misc.setup_tz_yakutsk' },
  { value: 'Asia/Vladivostok', labelKey: 'misc.setup_tz_vladivostok' },
  // Другие популярные
  { value: 'Europe/Kiev', labelKey: 'misc.setup_tz_kiev' },
  { value: 'Europe/Minsk', labelKey: 'misc.setup_tz_minsk' },
  { value: 'Europe/Istanbul', labelKey: 'misc.setup_tz_istanbul' },
  { value: 'Europe/Dubai', labelKey: 'misc.setup_tz_dubai' },
  { value: 'Europe/London', labelKey: 'misc.setup_tz_london' },
  { value: 'Europe/Berlin', labelKey: 'misc.setup_tz_berlin' },
  { value: 'America/New_York', labelKey: 'misc.setup_tz_new_york' },
];

// UX Audit Stage 2 (Setup issue 2.1): индикатор силы пароля.
// Возвращает { score: 0-4, label, color, percent }.
function getPasswordStrength(password) {
  if (!password) {
    return { score: 0, labelKey: '', color: 'transparent', percent: 0 };
  }

  let score = 0;
  // Длина
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  // Разнообразие символов
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^a-zA-Z0-9]/.test(password)) score += 1;
  // Ограничиваем до 4
  score = Math.min(score, 4);

  const labels = [
    { labelKey: 'misc.setup_pw_strength_very_weak', color: 'var(--mac-error)', percent: 25 },
    { labelKey: 'misc.setup_pw_strength_weak', color: 'var(--mac-warning)', percent: 50 },
    { labelKey: 'misc.setup_pw_strength_medium', color: 'var(--mac-warning)', percent: 75 },
    { labelKey: 'misc.setup_pw_strength_good', color: 'var(--mac-success)', percent: 100 },
    { labelKey: 'misc.setup_pw_strength_strong', color: 'var(--mac-success)', percent: 100 },
  ];

  return { score, ...labels[score] };
}

// UX Audit Stage 2 (Setup issue 2.2): правила валидации для real-time feedback.
// Каждое правило возвращает true если поле заполнено корректно.
const REQUIRED_FIELDS = [
  {
    key: 'clinicName',
    labelKey: 'misc.setup_label_clinic_name',
    isComplete: (form) => Boolean(form.clinicName.trim())
  },
  {
    key: 'branchName',
    labelKey: 'misc.setup_label_branch_name',
    isComplete: (form) => Boolean(form.branchName.trim())
  },
  {
    key: 'adminUsername',
    labelKey: 'misc.setup_label_admin_username_min3',
    isComplete: (form) => form.adminUsername.trim().length >= 3
  },
  {
    key: 'adminFullName',
    labelKey: 'misc.setup_label_admin_full_name',
    isComplete: (form) => Boolean(form.adminFullName.trim())
  },
  {
    key: 'adminEmail',
    labelKey: 'misc.setup_label_admin_email',
    isComplete: (form) => EMAIL_PATTERN.test(form.adminEmail.trim())
  },
  {
    key: 'adminPassword',
    labelKey: 'misc.setup_label_admin_password_min8',
    isComplete: (form) => form.adminPassword.length >= 8
  },
  // UX Audit Stage 2 (Setup issue 2.1): подтверждение пароля — обязательное поле.
  {
    key: 'adminPasswordConfirm',
    labelKey: 'misc.setup_label_password_confirm',
    isComplete: (form) =>
      Boolean(form.adminPasswordConfirm) &&
      form.adminPasswordConfirm === form.adminPassword
  }
];

function buildPayload(form) {
  return {
    clinic: {
      name: form.clinicName.trim(),
      address: form.clinicAddress.trim() || null,
      phone: form.clinicPhone.trim() || null,
      email: form.clinicEmail.trim() || null,
      timezone: form.clinicTimezone.trim() || 'Asia/Tashkent',
      logo_url: form.clinicLogoUrl.trim() || null
    },
    branch: {
      name: form.branchName.trim(),
      code: form.branchCode.trim() || null,
      address: form.branchAddress.trim() || null,
      phone: form.branchPhone.trim() || null,
      email: form.branchEmail.trim() || null,
      timezone: form.branchTimezone.trim() || form.clinicTimezone.trim() || 'Asia/Tashkent'
    },
    admin: {
      username: form.adminUsername.trim(),
      password: form.adminPassword,
      full_name: form.adminFullName.trim(),
      email: form.adminEmail.trim()
    },
    activation_key: form.activationKey.trim() || null
  };
}

export default function Setup() {
  // UX Audit Stage 1 (Setup issue 2.3): SPA-навигация вместо window.location.assign.
  const navigate = useNavigate();
  const loginRoute = getCanonicalRouteById('login')?.path || '/login';
  const { t } = useTranslation();

  const requiredFieldRefs = useRef({});
  // UX Audit Stage 2 (Setup issue 2.2): track touched fields для real-time валидации.
  // Поле считается "touched" после первого blur. До этого подсветки нет —
  // не обвиняем пользователя в ошибках, которых он ещё не сделал.
  const [touched, setTouched] = useState({});
  // UX Audit Stage 2 (Setup issue 2.2): submitAttempted — был ли хотя бы один submit.
  // Hint об обязательных полях показываем только после первой попытки submit.
  const [submitAttempted, setSubmitAttempted] = useState(false);
  // UX Audit Stage 2 (Setup issue 2.1): show/hide для пароля и подтверждения.
  const [showPassword, setShowPassword] = useState(false);
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false);
  // UX Audit Stage 2 (Setup issue 2.2): чекбокс «Филиал = клиника».
  // При включении поля филиала (адрес/телефон/email/timezone) авто-копируются
  // из клиники и становятся readonly.
  const [branchSameAsClinic, setBranchSameAsClinic] = useState(false);

  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState({
    loading: false,
    error: '',
    success: ''
  });

  // Полный список невалидных обязательных полей (для блокировки submit).
  const missingRequiredFields = useMemo(() => {
    return REQUIRED_FIELDS.filter((field) => !field.isComplete(form));
  }, [form]);

  // UX Audit Stage 2 (Setup issue 2.2): подсвечиваем только touched поля ИЛИ
  // все поля после первой попытки submit. До этого — не пугаем пользователя.
  const visibleInvalidKeys = useMemo(() => {
    const keys = new Set();
    for (const field of missingRequiredFields) {
      if (submitAttempted || touched[field.key]) {
        keys.add(field.key);
      }
    }
    return keys;
  }, [missingRequiredFields, submitAttempted, touched]);

  const missingRequiredLabels = useMemo(() => {
    return missingRequiredFields.map((field) => t(field.labelKey));
  }, [missingRequiredFields, t]);

  const isSubmitDisabled = useMemo(() => {
    return missingRequiredFields.length > 0 || status.loading;
  }, [missingRequiredFields.length, status.loading]);

  const submitTitle = useMemo(() => {
    if (status.loading || missingRequiredFields.length === 0) {
      return undefined;
    }
    return t('misc.setup_submit_title_fill', { fields: missingRequiredLabels.join(', ') });
  }, [missingRequiredFields.length, missingRequiredLabels, status.loading, t]);

  // UX Audit Stage 2 (Setup issue 2.1): индикатор силы пароля — пересчитывается
  // только при изменении adminPassword.
  const passwordStrength = useMemo(() => {
    return getPasswordStrength(form.adminPassword);
  }, [form.adminPassword]);

  // UX Audit Stage 2 (Setup issue 2.1): проверка совпадения паролей.
  const passwordsMatch = useMemo(() => {
    if (!form.adminPasswordConfirm) return null; // поле пустое — не показываем
    return form.adminPassword === form.adminPasswordConfirm;
  }, [form.adminPassword, form.adminPasswordConfirm]);

  const setRequiredFieldRef = (key) => (node) => {
    if (node) {
      requiredFieldRefs.current[key] = node;
    }
  };

  const focusFirstMissingField = () => {
    const firstMissing = missingRequiredFields[0];
    if (!firstMissing) {
      return;
    }

    const node = requiredFieldRefs.current[firstMissing.key];
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      node.focus({ preventScroll: true });
    }
  };

  // UX Audit Stage 2 (Setup issue 2.2): авто-копирование полей клиники в филиал
  // при включённом чекбоксе «Филиал = клиника».
  const updateField = (key) => (event) => {
    const value = event.target.value;
    setForm((prev) => {
      const next = { ...prev, [key]: value };

      // Если включён branchSameAsClinic и меняется одно из клиники-полей,
      // синхронизируем соответствующее branch-поле.
      if (branchSameAsClinic) {
        const syncMap = {
          clinicAddress: 'branchAddress',
          clinicPhone: 'branchPhone',
          clinicEmail: 'branchEmail',
          clinicTimezone: 'branchTimezone',
        };
        const branchKey = syncMap[key];
        if (branchKey) {
          next[branchKey] = value;
        }
      }

      return next;
    });
  };

  // UX Audit Stage 2 (Setup issue 2.2): обработчик blur — помечает поле как touched.
  const handleBlur = (key) => () => {
    setTouched((prev) => ({ ...prev, [key]: true }));
  };

  // UX Audit Stage 2 (Setup issue 2.2): toggle «Филиал = клиника».
  // При включении — копируем текущие значения клиники в филиал.
  // При выключении — оставляем скопированные значения как есть (не очищаем).
  //
  // UX Audit Setup bugfix: macos Checkbox вызывает onChange(boolean) напрямую,
  // а не onChange(event). Раньше здесь было `event.target.checked` —
  // это undefined, и чекбокс вообще не работал.
  const handleBranchSameAsClinicChange = (checked) => {
    setBranchSameAsClinic(checked);
    if (checked) {
      setForm((prev) => ({
        ...prev,
        branchAddress: prev.clinicAddress,
        branchPhone: prev.clinicPhone,
        branchEmail: prev.clinicEmail,
        branchTimezone: prev.clinicTimezone,
      }));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    // UX Audit Stage 2 (Setup issue 2.2): помечаем все поля как "проверенные"
    // после первой попытки submit — теперь все ошибки видимы.
    setSubmitAttempted(true);

    if (missingRequiredFields.length > 0) {
      // Прокручиваем к первому невалидному полю.
      setTimeout(focusFirstMissingField, 0);
      return;
    }

    setStatus({
      loading: true,
      error: '',
      success: ''
    });

    try {
      await initializeSetup(buildPayload(form));
      setStatus({
        loading: false,
        error: '',
        success: t('misc.setup_msg_success')
      });

      // UX Audit Stage 1 (Setup issue 2.3): SPA-navigate с задержкой 800мс.
      setTimeout(() => {
        navigate(loginRoute, { replace: true });
      }, 800);
    } catch (error) {
      logger.error('[setup] initialization failed', error);
      setStatus({
        loading: false,
        error: error?.message || t('misc.setup_msg_error'),
        success: ''
      });
    }
  };

  // UX Audit Stage 2 (Setup issue 2.1): helper для стиля инпута в зависимости от валидности.
  const fieldStyle = (key) => {
    return visibleInvalidKeys.has(key) ? 'setup-field setup-field--invalid' : 'setup-field';
  };

  // Поля филиала, которые авто-копируются — readonly при branchSameAsClinic.
  const branchFieldReadOnly = branchSameAsClinic;

  return (
    <div className="setup-wrap">
      <MacOSCard className="setup-card">
        <div className="setup-hero">
          <span className="setup-badge">First-Run Setup</span>
          <h1 className="setup-heading">{t('misc.setup_heading')}</h1>
          <p className="setup-description">
            {t('misc.setup_description')}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="setup-form">
          {/* ====================================================================
              Секция 1: Клиника
              ==================================================================== */}
          <section className="setup-section">
            <h2 className="setup-section-title">{t('misc.setup_section_clinic')}</h2>
            <div className="setup-grid">
              <label className="setup-label">
                <span>{t('misc.setup_label_clinic_name')} <span className="setup-required-marker">*</span></span>
                <Input
                  ref={setRequiredFieldRef('clinicName')}
                  className={fieldStyle('clinicName')}
                  name="clinicName"
                  required
                  aria-label={t('misc.setup_aria_clinic_name')}
                  aria-invalid={visibleInvalidKeys.has('clinicName')}
                  value={form.clinicName}
                  onChange={updateField('clinicName')}
                  onBlur={handleBlur('clinicName')}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_phone')}
                <Input
                  className="setup-field"
                  aria-label={t('misc.setup_aria_clinic_phone')}
                  value={form.clinicPhone}
                  onChange={updateField('clinicPhone')}
                />
              </label>
              <label className="setup-label">
                Email
                <Input
                  className="setup-field"
                  type="email"
                  aria-label={t('misc.setup_aria_clinic_email')}
                  value={form.clinicEmail}
                  onChange={updateField('clinicEmail')}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_timezone')}
                <select
                  className="setup-field setup-select"
                  aria-label={t('misc.setup_aria_clinic_timezone')}
                  value={form.clinicTimezone}
                  onChange={updateField('clinicTimezone')}
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>{t(tz.labelKey)}</option>
                  ))}
                </select>
              </label>
              <label className="setup-label setup-label--wide">
                {t('misc.setup_label_address')}
                <textarea
                  className="setup-field setup-textarea"
                  aria-label={t('misc.setup_aria_clinic_address')}
                  value={form.clinicAddress}
                  onChange={updateField('clinicAddress')}
                />
              </label>
              <label className="setup-label setup-label--wide">
                {t('misc.setup_label_logo_url')}
                <Input
                  className="setup-field"
                  aria-label={t('misc.setup_aria_clinic_logo_url')}
                  value={form.clinicLogoUrl}
                  onChange={updateField('clinicLogoUrl')}
                  placeholder={t('misc.setup_placeholder_optional')}
                />
              </label>
            </div>
          </section>

          {/* ====================================================================
              Секция 2: Первый филиал
              ==================================================================== */}
          <section className="setup-section">
            <h2 className="setup-section-title">{t('misc.setup_section_branch')}</h2>

            {/* UX Audit Stage 2 (Setup issue 2.2): чекбокс авто-копирования. */}
            <label className="setup-checkbox-row">
              <Checkbox checked={branchSameAsClinic} onChange={handleBranchSameAsClinicChange} aria-label={t('misc.setup_aria_branch_same')} />
              <span>{t('misc.setup_label_branch_same')}</span>
            </label>

            <div className="setup-grid">
              <label className="setup-label">
                <span>{t('misc.setup_label_branch_name')} <span className="setup-required-marker">*</span></span>
                <Input
                  ref={setRequiredFieldRef('branchName')}
                  className={fieldStyle('branchName')}
                  name="branchName"
                  required
                  aria-label={t('misc.setup_aria_branch_name')}
                  aria-invalid={visibleInvalidKeys.has('branchName')}
                  value={form.branchName}
                  onChange={updateField('branchName')}
                  onBlur={handleBlur('branchName')}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_branch_code')}
                <Input
                  className="setup-field"
                  aria-label={t('misc.setup_aria_branch_code')}
                  value={form.branchCode}
                  onChange={updateField('branchCode')}
                  placeholder={t('misc.setup_placeholder_optional')}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_branch_phone')}
                <Input
                  className="setup-field"
                  aria-label={t('misc.setup_aria_branch_phone')}
                  value={form.branchPhone}
                  onChange={updateField('branchPhone')}
                  readOnly={branchFieldReadOnly}
                  disabled={branchFieldReadOnly}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_branch_email')}
                <Input
                  className="setup-field"
                  type="email"
                  aria-label={t('misc.setup_aria_branch_email')}
                  value={form.branchEmail}
                  onChange={updateField('branchEmail')}
                  readOnly={branchFieldReadOnly}
                  disabled={branchFieldReadOnly}
                />
              </label>
              <label className="setup-label">
                {t('misc.setup_label_branch_timezone')}
                <select
                  className="setup-field setup-select"
                  aria-label={t('misc.setup_aria_branch_timezone')}
                  value={form.branchTimezone}
                  onChange={updateField('branchTimezone')}
                  disabled={branchFieldReadOnly}
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>{t(tz.labelKey)}</option>
                  ))}
                </select>
              </label>
              <label className="setup-label setup-label--wide">
                {t('misc.setup_label_branch_address')}
                <textarea
                  className="setup-field setup-textarea"
                  aria-label={t('misc.setup_aria_branch_address')}
                  value={form.branchAddress}
                  onChange={updateField('branchAddress')}
                  readOnly={branchFieldReadOnly}
                  disabled={branchFieldReadOnly}
                />
              </label>
            </div>
          </section>

          {/* ====================================================================
              Секция 3: Главный администратор
              ==================================================================== */}
          <section className="setup-section">
            <h2 className="setup-section-title">{t('misc.setup_section_admin')}</h2>
            <div className="setup-grid">
              <label className="setup-label">
                <span>Username <span className="setup-required-marker">*</span></span>
                <Input
                  ref={setRequiredFieldRef('adminUsername')}
                  className={fieldStyle('adminUsername')}
                  name="adminUsername"
                  required
                  minLength={3}
                  aria-label={t('misc.setup_aria_admin_username')}
                  aria-invalid={visibleInvalidKeys.has('adminUsername')}
                  value={form.adminUsername}
                  onChange={updateField('adminUsername')}
                  onBlur={handleBlur('adminUsername')}
                  placeholder={t('misc.setup_placeholder_admin_username')}
                  autoComplete="username"
                />
              </label>
              <label className="setup-label">
                <span>{t('misc.setup_label_full_name')} <span className="setup-required-marker">*</span></span>
                <Input
                  ref={setRequiredFieldRef('adminFullName')}
                  className={fieldStyle('adminFullName')}
                  name="adminFullName"
                  required
                  aria-label={t('misc.setup_aria_admin_full_name')}
                  aria-invalid={visibleInvalidKeys.has('adminFullName')}
                  value={form.adminFullName}
                  onChange={updateField('adminFullName')}
                  onBlur={handleBlur('adminFullName')}
                />
              </label>
              <label className="setup-label">
                <span>Email <span className="setup-required-marker">*</span></span>
                <Input
                  ref={setRequiredFieldRef('adminEmail')}
                  className={fieldStyle('adminEmail')}
                  type="email"
                  name="adminEmail"
                  required
                  aria-label={t('misc.setup_aria_admin_email')}
                  aria-invalid={visibleInvalidKeys.has('adminEmail')}
                  value={form.adminEmail}
                  onChange={updateField('adminEmail')}
                  onBlur={handleBlur('adminEmail')}
                  autoComplete="email"
                />
              </label>

              {/* ============ Пароль + подтверждение ============ */}
              {/* UX Audit Stage 2 (Setup issue 2.1): блок пароля с show/hide и силой. */}
              <label className="setup-label">
                <span>{t('misc.setup_label_password')} <span className="setup-required-marker">*</span></span>
                <div className="setup-password-field">
                  <Input
                    ref={setRequiredFieldRef('adminPassword')}
                    className={`${fieldStyle('adminPassword')} setup-password-input`}
                    type={showPassword ? 'text' : 'password'}
                    name="adminPassword"
                    required
                    minLength={8}
                    aria-label={t('misc.setup_aria_admin_password')}
                    aria-invalid={visibleInvalidKeys.has('adminPassword')}
                    autoComplete="new-password"
                    value={form.adminPassword}
                    onChange={updateField('adminPassword')}
                    onBlur={handleBlur('adminPassword')}
                  />
                  <button
                    type="button"
                    className="setup-password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? t('misc.setup_aria_hide_password') : t('misc.setup_aria_show_password')}
                    title={showPassword ? t('misc.setup_aria_hide_password') : t('misc.setup_aria_show_password')}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {/* Индикатор силы пароля */}
                {form.adminPassword && (
                  <div className="setup-strength" aria-live="polite">
                    <div className="setup-strength-bar">
                      <div
                        className="setup-strength-fill"
                        style={{
                          width: `${passwordStrength.percent}%`,
                          background: passwordStrength.color,
                        }}
                      />
                    </div>
                    <span
                      className="setup-strength-label"
                      style={{ color: passwordStrength.color }}
                    >
                      {t(passwordStrength.labelKey)}
                    </span>
                  </div>
                )}

                {/* Подсказка по требованиям */}
                <span className="setup-hint">
                  {t('misc.setup_hint_password')}
                </span>
              </label>

              {/* Подтверждение пароля */}
              <label className="setup-label">
                <span>{t('misc.setup_label_password_repeat')} <span className="setup-required-marker">*</span></span>
                <div className="setup-password-field">
                  <Input
                    ref={setRequiredFieldRef('adminPasswordConfirm')}
                    className={`${fieldStyle('adminPasswordConfirm')} setup-password-input`}
                    type={showPasswordConfirm ? 'text' : 'password'}
                    name="adminPasswordConfirm"
                    required
                    aria-label={t('misc.setup_aria_password_confirm')}
                    aria-invalid={visibleInvalidKeys.has('adminPasswordConfirm')}
                    autoComplete="new-password"
                    value={form.adminPasswordConfirm}
                    onChange={updateField('adminPasswordConfirm')}
                    onBlur={handleBlur('adminPasswordConfirm')}
                  />
                  <button
                    type="button"
                    className="setup-password-toggle"
                    onClick={() => setShowPasswordConfirm((v) => !v)}
                    aria-label={showPasswordConfirm ? t('misc.setup_aria_hide_password') : t('misc.setup_aria_show_password')}
                    title={showPasswordConfirm ? t('misc.setup_aria_hide_password') : t('misc.setup_aria_show_password')}
                  >
                    {showPasswordConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>

                {/* Индикатор совпадения паролей */}
                {form.adminPasswordConfirm && (
                  <div className="setup-password-match" aria-live="polite">
                    {passwordsMatch ? (
                      <>
                        <Check size={14} aria-hidden="true" />
                        <span className="setup-password-match--ok">{t('misc.setup_msg_passwords_match')}</span>
                      </>
                    ) : (
                      <>
                        <X size={14} aria-hidden="true" />
                        <span className="setup-password-match--err">{t('misc.setup_msg_passwords_mismatch')}</span>
                      </>
                    )}
                  </div>
                )}
              </label>
            </div>
          </section>

          {/* ====================================================================
              Секция 4: Активация (UX Audit Stage 2: перенесена из секции администратора)
              ==================================================================== */}
          <section className="setup-section">
            <h2 className="setup-section-title">{t('misc.setup_section_activation')}</h2>
            <p className="setup-section-hint">
              {t('misc.setup_activation_hint')}
            </p>
            <div className="setup-grid">
              <label className="setup-label setup-label--wide">
                {t('misc.setup_label_activation_key')}
                <Input
                  className="setup-field"
                  aria-label={t('misc.setup_aria_activation_key')}
                  value={form.activationKey}
                  onChange={updateField('activationKey')}
                  placeholder={t('misc.setup_placeholder_optional')}
                />
              </label>
            </div>
          </section>

          {/* ====================================================================
              Сообщения об ошибке/успехе
              ==================================================================== */}
          {status.error ? (
            <div className="setup-message setup-message--error" role="alert">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{status.error}</span>
            </div>
          ) : null}
          {status.success ? (
            <div className="setup-message setup-message--success" role="status">
              <Check size={16} aria-hidden="true" />
              <span>{status.success}</span>
            </div>
          ) : null}

          {/* ====================================================================
              Кнопки: Назад + Завершить настройку
              ==================================================================== */}
          <div className="setup-actions">
            {/* UX Audit Stage 2 (Setup issue 2.2): hint показываем только после
                первой попытки submit, а не сразу при открытии страницы. */}
            {submitAttempted && missingRequiredFields.length > 0 && !status.loading ? (
              <div className="setup-required-hint" role="status">
                {t('misc.setup_required_hint', { fields: missingRequiredLabels.join(', ') })}
                {' '}
                <button type="button" className="setup-hint-action" onClick={focusFirstMissingField}>
                  {t('misc.setup_action_show_first_field')}
                </button>
              </div>
            ) : null}

            <div className="setup-actions-buttons">
              {/* UX Audit Stage 2 (Setup issue 2.2): кнопка «Назад». */}
              <Button
                type="button"
                variant="outline"
                onClick={() => navigate(loginRoute)}
                disabled={status.loading}
                title={t('misc.setup_title_back')}
              >
                <ArrowLeft size={16} />
                {t('misc.setup_action_back')}
              </Button>
              <Button
                type="submit"
                variant="primary"
                disabled={isSubmitDisabled}
                title={submitTitle}
              >
                {status.loading ? t('misc.setup_action_saving') : t('misc.setup_action_finish')}
              </Button>
            </div>
          </div>
        </form>
      </MacOSCard>
    </div>
  );
}
