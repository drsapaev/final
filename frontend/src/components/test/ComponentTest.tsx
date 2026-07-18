
import { useTranslation } from '../../i18n/useTranslation';
// Тестовый компонент для проверки работоспособности всех созданных компонентов
import React, { useState } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import {
  ErrorBoundary,
  ToastProvider,
  useToast,
  Loading,
  ModalProvider,
  useModal,
  FormProvider,
  useForm,
  Table as TableRaw,
  RoleGuard,
  useRoleAccess
} from '../common';
const Table = TableRaw as unknown as React.ComponentType<Record<string, unknown>>;

/**
 * Тестовый компонент для проверки всех созданных компонентов
 */
function ComponentTestInner() {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;
  const { addToast } = useToast() as { addToast: (...args: unknown[]) => void };
  const { openModal } = useModal() as { openModal: (...args: unknown[]) => void };
  const { form, setValue, setError, validateForm } = useForm('test-form', { name: '', email: '' });
  const { profile, hasRole, isAdmin } = useRoleAccess();
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const [loading, setLoading] = useState(false);
  const [tableData, setTableData] = useState([
    { id: 1, name: t('misc.ct_user_1'), email: 'ivan@example.com', role: 'admin' },
    { id: 2, name: t('misc.ct_user_2'), email: 'petr@example.com', role: 'doctor' },
    { id: 3, name: t('misc.ct_user_3'), email: 'anna@example.com', role: 'patient' }
  ]);

  const tableColumns = [
    { key: 'name', title: t('final.col_name'), sortable: true },
    { key: 'email', title: 'Email', sortable: true },
    { key: 'role', title: t('final.col_role'), sortable: true }
  ];

  const containerStyle = {
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'primary'),
    minHeight: '100vh'
  };

  const sectionStyle = {
    marginBottom: getSpacing('xl'),
    padding: getSpacing('lg'),
    backgroundColor: getColor('background', 'secondary'),
    borderRadius: '8px',
    border: `1px solid ${getColor('border', 'light')}`
  };

  const titleStyle = {
    fontSize: getFontSize('lg'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    marginBottom: getSpacing('md')
  };

  const buttonStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    margin: getSpacing('xs'),
    backgroundColor: getColor('primary', 'main'),
    color: getColor('primary', 'contrast'),
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: getFontSize('sm')
  };

  const inputStyle = {
    padding: getSpacing('sm'),
    margin: getSpacing('xs'),
    border: `1px solid ${getColor('border', 'main')}`,
    borderRadius: '4px',
    fontSize: getFontSize('sm')
  };

  const handleTestToast = (type) => {
    addToast({
      type,
      title: t('misc.ct_toast_title', { type }),
      message: t('misc.ct_toast_message', { type }),
      duration: 3000
    });
  };

  const handleTestModal = () => {
    openModal({
      title: t('final.test_modal_title'),
      content: (
        <div>
          <p>{t('misc.ct_modal_content')}</p>
          <p>{t('misc.ct_theme_label')}: {theme.isLight ? t('misc.ct_theme_light') : t('misc.ct_theme_dark')}</p>
        </div>
      ),
      footer: (
        <button style={buttonStyle} onClick={() => { }}>
          {t('misc.ct_close')}
        </button>
      )
    });
  };

  const handleTestLoading = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 2000);
  };

  const handleFormSubmit = (values) => {
    logger.log('Form submitted:', values);
    addToast({
      type: 'success',
      title: t('final.form_submitted'),
      message: t('misc.ct_form_data', { data: JSON.stringify(values) })
    });
  };

  const handleFormValidation = () => {
    const isValid = validateForm({
      name: { required: t('misc.ct_validation_name_required') },
      email: {
        required: t('misc.ct_validation_email_required'),
        email: t('misc.ct_validation_email_invalid')
      }
    });

    if (isValid) {
      addToast({
        type: 'success',
        title: t('final.validation_passed'),
        message: t('misc.ct_validation_passed_msg')
      });
    } else {
      addToast({
        type: 'error',
        title: t('final.validation_error'),
        message: t('misc.ct_validation_error_msg')
      });
    }
  };

  return (
    <div style={containerStyle}>
      <h1 style={{ ...titleStyle, fontSize: getFontSize('xl') }}>
        {t('misc.ct_h1_title')}
      </h1>

      {/* Тест темы */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_theme_styles')}</h2>
        <p>{t('misc.ct_current_theme_label')}: {theme.isLight ? t('misc.ct_theme_light') : t('misc.ct_theme_dark')}</p>
        <p>{t('misc.ct_colors_label')}: primary={getColor('primary', 'main')}, secondary={getColor('secondary', 'main')}</p>
        <p>{t('misc.ct_spacing_label')}: sm={getSpacing('sm')}, md={getSpacing('md')}, lg={getSpacing('lg')}</p>
        <p>{t('misc.ct_font_sizes_label')}: sm={getFontSize('sm')}, md={getFontSize('md')}, lg={getFontSize('lg')}</p>
      </div>

      {/* Тест уведомлений */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_toast')}</h2>
        <button style={buttonStyle} onClick={() => handleTestToast('success')}>
          {t('misc.ct_btn_success')}
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('error')}>
          {t('misc.ct_btn_error')}
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('warning')}>
          {t('misc.ct_btn_warning')}
        </button>
        <button style={buttonStyle} onClick={() => handleTestToast('info')}>
          {t('misc.ct_btn_info')}
        </button>
      </div>

      {/* Тест модальных окон */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_modals')}</h2>
        <button style={buttonStyle} onClick={handleTestModal}>
          {t('misc.ct_open_modal')}
        </button>
      </div>

      {/* Тест загрузки */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_loading')}</h2>
        <button style={buttonStyle} onClick={handleTestLoading}>
          {t('misc.ct_test_loading_btn')}
        </button>
        {loading && <Loading text={t('misc.ct_loading_text')} />}
      </div>

      {/* Тест форм */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_forms')}</h2>
        <form onSubmit={(e) => { e.preventDefault(); handleFormSubmit(form?.values); }}>
          <input
            type="text"
            aria-label="Test form name"
            placeholder={t('misc.ct_input_name')}
            value={form?.values?.name || ''}
            onChange={(e) => setValue('name', e.target.value)}
            style={inputStyle}
          />
          <input
            type="email"
            aria-label="Test form email"
            placeholder="Email"
            value={form?.values?.email || ''}
            onChange={(e) => setValue('email', e.target.value)}
            style={inputStyle}
          />
          <button type="button" style={buttonStyle} onClick={handleFormValidation}>
            {t('misc.ct_validate_btn')}
          </button>
          <button type="submit" style={buttonStyle}>
            {t('misc.ct_submit_btn')}
          </button>
        </form>
      </div>

      {/* Тест таблиц */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_tables')}</h2>
        <Table
          data={tableData}
          columns={tableColumns}
          sortable={true}
          filterable={true}
          pagination={true}
          pageSize={2}
        />
      </div>

      {/* Тест ролевой системы */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_roles')}</h2>
        <p>{t('misc.ct_profile_label')}: {profile ? JSON.stringify(profile) : t('misc.ct_not_authorized')}</p>
        <p>{t('misc.ct_role_admin_label')}: {hasRole(['admin']) ? t('misc.ct_yes') : t('misc.ct_no')}</p>
        <p>{t('misc.ct_admin_label')}: {isAdmin() ? t('misc.ct_yes') : t('misc.ct_no')}</p>

        <RoleGuard allowedRoles={['admin']} fallback={<p>{t('misc.ct_access_denied')}</p>}>
          <p>{t('misc.ct_admin_only_content')}</p>
        </RoleGuard>
      </div>

      {/* Тест API */}
      <div style={sectionStyle}>
        <h2 style={titleStyle}>{t('misc.ct_section_api')}</h2>
        <p>{t('misc.ct_api_client_label')}: {typeof window !== 'undefined' ? t('misc.ct_available') : t('misc.ct_unavailable')}</p>
        <p>{t('misc.ct_token_label')}: {tokenManager.getAccessToken() ? t('misc.ct_present') : t('misc.ct_no')}</p>
        <p>{t('misc.ct_profile_label')}: {sessionStorage.getItem('auth_profile') ? t('misc.ct_present') : t('misc.ct_no')}</p>
      </div>
    </div>
  );
}

/**
 * Обертка с провайдерами для тестирования
 */
export default function ComponentTest() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <ModalProvider>
          <FormProvider>
            <ComponentTestInner />
          </FormProvider>
        </ModalProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}

