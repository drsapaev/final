import { useMemo, useRef, useState } from 'react';
import { MacOSButton, MacOSCard } from '../components/ui/macos';
import { initializeSetup } from '../api/setup';
import logger from '../utils/logger';

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
  adminUsername: 'admin',
  adminPassword: '',
  adminFullName: '',
  adminEmail: '',
  activationKey: ''
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const REQUIRED_FIELDS = [
  {
    key: 'clinicName',
    label: 'Название клиники',
    isComplete: (form) => Boolean(form.clinicName.trim())
  },
  {
    key: 'branchName',
    label: 'Название филиала',
    isComplete: (form) => Boolean(form.branchName.trim())
  },
  {
    key: 'adminUsername',
    label: 'Username администратора',
    isComplete: (form) => form.adminUsername.trim().length >= 3
  },
  {
    key: 'adminFullName',
    label: 'Полное имя администратора',
    isComplete: (form) => Boolean(form.adminFullName.trim())
  },
  {
    key: 'adminEmail',
    label: 'Email администратора',
    isComplete: (form) => EMAIL_PATTERN.test(form.adminEmail.trim())
  },
  {
    key: 'adminPassword',
    label: 'Пароль администратора, минимум 8 символов',
    isComplete: (form) => form.adminPassword.length >= 8
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
  const requiredFieldRefs = useRef({});
  const [form, setForm] = useState(initialForm);
  const [status, setStatus] = useState({
    loading: false,
    error: '',
    success: ''
  });

  const missingRequiredFields = useMemo(() => {
    return REQUIRED_FIELDS
      .filter((field) => !field.isComplete(form));
  }, [form]);

  const missingRequiredLabels = useMemo(() => {
    return missingRequiredFields.map((field) => field.label);
  }, [missingRequiredFields]);

  const missingRequiredKeys = useMemo(() => {
    return new Set(missingRequiredFields.map((field) => field.key));
  }, [missingRequiredFields]);

  const isSubmitDisabled = useMemo(() => {
    return missingRequiredFields.length > 0 || status.loading;
  }, [missingRequiredFields.length, status.loading]);

  const submitTitle = useMemo(() => {
    if (status.loading || missingRequiredFields.length === 0) {
      return undefined;
    }
    return `Заполните: ${missingRequiredLabels.join(', ')}`;
  }, [missingRequiredFields.length, missingRequiredLabels, status.loading]);

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

  const updateField = (key) => (event) => {
    const value = event.target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
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
        success: 'Первичная настройка завершена. Переходим к входу...'
      });

      window.location.assign('/login');
    } catch (error) {
      logger.error('[setup] initialization failed', error);
      setStatus({
        loading: false,
        error: error?.message || 'Не удалось завершить первичную настройку',
        success: ''
      });
    }
  };

  return (
    <div style={wrapStyle}>
      <MacOSCard style={cardStyle}>
        <div style={heroStyle}>
          <span style={badgeStyle}>First-Run Setup</span>
          <h1 style={headingStyle}>Настройка инсталляции клиники</h1>
          <p style={descriptionStyle}>
            Этот шаг создаёт данные клиники, первый филиал и главного администратора
            внутри уже развернутой системы. Инфраструктура и база данных не создаются здесь.
          </p>
        </div>

        <form onSubmit={handleSubmit} style={formStyle}>
          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Клиника</h2>
            <div style={gridStyle}>
              <label style={labelStyle}>
                <span>Название клиники <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('clinicName')}
                  style={missingRequiredKeys.has('clinicName') ? requiredInputStyle : inputStyle}
                  name="clinicName"
                  required
                  aria-invalid={missingRequiredKeys.has('clinicName')}
                  value={form.clinicName}
                  onChange={updateField('clinicName')}
                />
              </label>
              <label style={labelStyle}>
                Телефон
                <input style={inputStyle} value={form.clinicPhone} onChange={updateField('clinicPhone')} />
              </label>
              <label style={labelStyle}>
                Email
                <input style={inputStyle} type="email" value={form.clinicEmail} onChange={updateField('clinicEmail')} />
              </label>
              <label style={labelStyle}>
                Timezone
                <input style={inputStyle} value={form.clinicTimezone} onChange={updateField('clinicTimezone')} />
              </label>
              <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                Адрес
                <textarea style={textareaStyle} value={form.clinicAddress} onChange={updateField('clinicAddress')} />
              </label>
              <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                URL логотипа
                <input style={inputStyle} value={form.clinicLogoUrl} onChange={updateField('clinicLogoUrl')} />
              </label>
            </div>
          </section>

          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Первый филиал</h2>
            <div style={gridStyle}>
              <label style={labelStyle}>
                <span>Название филиала <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('branchName')}
                  style={missingRequiredKeys.has('branchName') ? requiredInputStyle : inputStyle}
                  name="branchName"
                  required
                  aria-invalid={missingRequiredKeys.has('branchName')}
                  value={form.branchName}
                  onChange={updateField('branchName')}
                />
              </label>
              <label style={labelStyle}>
                Код филиала
                <input style={inputStyle} value={form.branchCode} onChange={updateField('branchCode')} placeholder="optional" />
              </label>
              <label style={labelStyle}>
                Телефон филиала
                <input style={inputStyle} value={form.branchPhone} onChange={updateField('branchPhone')} />
              </label>
              <label style={labelStyle}>
                Email филиала
                <input style={inputStyle} type="email" value={form.branchEmail} onChange={updateField('branchEmail')} />
              </label>
              <label style={labelStyle}>
                Timezone филиала
                <input style={inputStyle} value={form.branchTimezone} onChange={updateField('branchTimezone')} />
              </label>
              <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                Адрес филиала
                <textarea style={textareaStyle} value={form.branchAddress} onChange={updateField('branchAddress')} />
              </label>
            </div>
          </section>

          <section style={sectionStyle}>
            <h2 style={sectionTitleStyle}>Главный администратор</h2>
            <div style={gridStyle}>
              <label style={labelStyle}>
                <span>Username <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('adminUsername')}
                  style={missingRequiredKeys.has('adminUsername') ? requiredInputStyle : inputStyle}
                  name="adminUsername"
                  required
                  minLength={3}
                  aria-invalid={missingRequiredKeys.has('adminUsername')}
                  value={form.adminUsername}
                  onChange={updateField('adminUsername')}
                />
              </label>
              <label style={labelStyle}>
                <span>Полное имя <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('adminFullName')}
                  style={missingRequiredKeys.has('adminFullName') ? requiredInputStyle : inputStyle}
                  name="adminFullName"
                  required
                  aria-invalid={missingRequiredKeys.has('adminFullName')}
                  value={form.adminFullName}
                  onChange={updateField('adminFullName')}
                />
              </label>
              <label style={labelStyle}>
                <span>Email <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('adminEmail')}
                  style={missingRequiredKeys.has('adminEmail') ? requiredInputStyle : inputStyle}
                  type="email"
                  name="adminEmail"
                  required
                  aria-invalid={missingRequiredKeys.has('adminEmail')}
                  value={form.adminEmail}
                  onChange={updateField('adminEmail')}
                />
              </label>
              <label style={labelStyle}>
                <span>Пароль <span style={requiredMarkerStyle}>*</span></span>
                <input
                  ref={setRequiredFieldRef('adminPassword')}
                  style={missingRequiredKeys.has('adminPassword') ? requiredInputStyle : inputStyle}
                  type="password"
                  name="adminPassword"
                  required
                  minLength={8}
                  aria-invalid={missingRequiredKeys.has('adminPassword')}
                  autoComplete="new-password"
                  value={form.adminPassword}
                  onChange={updateField('adminPassword')}
                />
              </label>
              <label style={{ ...labelStyle, gridColumn: '1 / -1' }}>
                Ключ активации
                <input style={inputStyle} value={form.activationKey} onChange={updateField('activationKey')} placeholder="optional" />
              </label>
            </div>
          </section>

          {status.error ? <div style={errorStyle}>{status.error}</div> : null}
          {status.success ? <div style={successStyle}>{status.success}</div> : null}

          <div style={actionsStyle}>
            {missingRequiredFields.length > 0 && !status.loading ? (
              <div style={requiredHintStyle} role="status">
                Заполните обязательные поля: {missingRequiredLabels.join(', ')}.
                {' '}
                <button type="button" style={hintActionStyle} onClick={focusFirstMissingField}>
                  Показать первое поле
                </button>
              </div>
            ) : null}
            <MacOSButton type="submit" variant="primary" disabled={isSubmitDisabled} title={submitTitle}>
              {status.loading ? 'Сохраняем...' : 'Завершить настройку'}
            </MacOSButton>
          </div>
        </form>
      </MacOSCard>
    </div>
  );
}

const wrapStyle = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'flex-start',
  justifyContent: 'center',
  padding: '32px 16px',
  background: 'linear-gradient(180deg, rgba(12,74,110,0.08), rgba(15,23,42,0.03))'
};

const cardStyle = {
  width: '100%',
  maxWidth: '960px',
  padding: '32px',
  borderRadius: '28px'
};

const heroStyle = {
  marginBottom: '24px'
};

const badgeStyle = {
  display: 'inline-flex',
  padding: '6px 12px',
  borderRadius: '999px',
  background: 'rgba(14,116,144,0.12)',
  color: '#0f766e',
  fontSize: '12px',
  fontWeight: 700,
  letterSpacing: '0.04em',
  textTransform: 'uppercase'
};

const headingStyle = {
  margin: '16px 0 8px',
  fontSize: '32px'
};

const descriptionStyle = {
  margin: 0,
  color: 'var(--mac-text-secondary)',
  lineHeight: 1.6
};

const formStyle = {
  display: 'grid',
  gap: '24px'
};

const sectionStyle = {
  display: 'grid',
  gap: '16px'
};

const sectionTitleStyle = {
  margin: 0,
  fontSize: '20px'
};

const gridStyle = {
  display: 'grid',
  gap: '16px',
  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))'
};

const labelStyle = {
  display: 'grid',
  gap: '8px',
  fontSize: '14px',
  fontWeight: 600
};

const requiredMarkerStyle = {
  color: '#dc2626',
  fontWeight: 700
};

const baseFieldStyle = {
  border: '1px solid rgba(148, 163, 184, 0.35)',
  borderRadius: '14px',
  padding: '12px 14px',
  fontSize: '14px',
  background: 'rgba(255,255,255,0.7)'
};

const inputStyle = {
  ...baseFieldStyle
};

const requiredInputStyle = {
  ...baseFieldStyle,
  border: '1px solid rgba(220, 38, 38, 0.65)',
  boxShadow: '0 0 0 3px rgba(220, 38, 38, 0.10)'
};

const textareaStyle = {
  ...baseFieldStyle,
  minHeight: '88px',
  resize: 'vertical'
};

const actionsStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '16px',
  flexWrap: 'wrap'
};

const requiredHintStyle = {
  flex: '1 1 280px',
  color: '#b45309',
  fontSize: '13px',
  lineHeight: 1.5
};

const hintActionStyle = {
  border: 0,
  background: 'transparent',
  color: '#2563eb',
  cursor: 'pointer',
  font: 'inherit',
  fontWeight: 700,
  marginLeft: '8px',
  padding: 0,
  textDecoration: 'underline'
};

const messageStyle = {
  padding: '12px 14px',
  borderRadius: '14px',
  fontSize: '14px'
};

const errorStyle = {
  ...messageStyle,
  background: 'rgba(239,68,68,0.10)',
  color: '#b91c1c'
};

const successStyle = {
  ...messageStyle,
  background: 'rgba(34,197,94,0.10)',
  color: '#166534'
};
