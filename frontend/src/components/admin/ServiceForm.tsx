import type { CSSProperties } from 'react';

import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
/**
 * ServiceForm — extracted from ServiceCatalog.jsx (UX Audit Admin #4.1).
 *
 * Form for adding/editing services with 3 tabs: basic, queue, options.
 * Previously inline in ServiceCatalog.jsx (1208 lines total).
 */
import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { AlertCircle, X, Save, Package, Users, Filter } from 'lucide-react';
import { MacOSTab, MacOSCard, Button, Input, Label, Select, Textarea, Checkbox } from '../ui/macos';
import ServiceChangesPreview from './ServiceChangesPreview';
import { isValidServiceCode, normalizeServiceCode, formatServiceCodeInput } from '../../utils/serviceCodeUtils';
import logger from '../../utils/logger';
import { api } from '../../api/client';
import notify from '../../services/notify';
import React from "react";
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

// UX Audit Admin #4.1: shared constants extracted from ServiceCatalog.jsx.
const SERVICE_GROUP_PREFIXES = {
  cardiology: 'K',
  ecg: 'E',
  dermatology: 'D',
  dental: 'S',
  laboratory: 'L',
  procedures: 'P',
};

const SERVICE_GROUP_ALIASES = {
  cardio: 'cardiology',
  derma: 'dermatology',
  stomatology: 'dental',
  lab: 'laboratory',
  physiotherapy: 'procedures',
};

// UX Audit Admin #4.1: service group label keys live under admin2.sf_group_<key>.
// The lookup is performed via t18() at the call site so the dictionary remains
// free of hardcoded Russian strings.

const resolveServiceGroup = ({ queueTag, departmentKey, categorySpecialty }) => {
  // t accessed via closure or t18()
  for (const rawValue of [queueTag, departmentKey, categorySpecialty]) {
    if (!rawValue) continue;
    const normalized = String(rawValue).trim().toLowerCase();
    if (!normalized) continue;
    if (SERVICE_GROUP_PREFIXES[normalized]) return normalized;
    if (SERVICE_GROUP_ALIASES[normalized]) {
      return SERVICE_GROUP_ALIASES[normalized];
    }
  }

  return null;
};

const getAllowedPrefixesForGroup = (groupKey) => SERVICE_GROUP_PREFIXES[groupKey] || [];


const ServiceForm = ({ service, categories, doctors, queueProfiles = [], setMessage, onSave, onCancel }) => {
  // t accessed via closure or t18()
  const [activeTab, setActiveTab] = useState('basic'); // 'basic', 'queue', 'options'
  const [showPreview, setShowPreview] = useState(false); // ✅ PREVIEW: Show changes preview
  const [formData, setFormData] = useState({
    name: service?.name || '',
    code: service?.code || service?.service_code || '', // Unified: use code as primary
    category_id: service?.category_id || '',
    price: service?.price || '',
    currency: service?.currency || 'UZS',
    duration_minutes: service?.duration_minutes || 30,
    doctor_id: service?.doctor_id || '',
    active: service?.active !== undefined ? service.active : true,
    department_key: service?.department_key || '',
    queue_tag: service?.queue_tag || '',
    requires_doctor: service?.requires_doctor || false,
    is_consultation: service?.is_consultation || false,
    allow_doctor_price_override: service?.allow_doctor_price_override || false
  });

  // State для проверки дубликатов
  const [codeWarning, setCodeWarning] = useState('');
  const [checkingDuplicates, setCheckingDuplicates] = useState(false);

  // Async проверка дубликатов для code
  useEffect(() => {
    if (!formData.code || formData.code.length < 2) {
      setCodeWarning('');
      return;
    }

    const normalizedCode = normalizeServiceCode(formData.code);
    if (!isValidServiceCode(normalizedCode)) {
      setCodeWarning('');
      return;
    }

    const timeoutId = setTimeout(async () => {
      try {
        setCheckingDuplicates(true);
        const response = await api.get('/services');
        const services = response.data;
        const duplicate = services.find(
          (s) => (s.code === normalizedCode || s.service_code === normalizedCode) && s.id !== service?.id
        );
        if (duplicate) {
          setCodeWarning(t18('admin2.sf_code_duplicate_warning', { code: normalizedCode, name: duplicate.name }));
        } else {
          setCodeWarning('');
        }
      } catch (error) {
        logger.error('Ошибка проверки дубликатов:', error);
      } finally {
        setCheckingDuplicates(false);
      }
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [formData.code, service?.id]);

  const selectedFormCategory = categories.find(
    (category) => category.id === parseInt(formData.category_id, 10)
  );
  const selectedServiceGroup = resolveServiceGroup({
    queueTag: formData.queue_tag,
    departmentKey: formData.department_key,
    categorySpecialty: selectedFormCategory?.specialty
  });
  const allowedPrefixes = getAllowedPrefixesForGroup(selectedServiceGroup);
  const normalizedCode = formData.code ? normalizeServiceCode(formData.code) : '';
  const codePrefix = normalizedCode ? normalizedCode.charAt(0).toUpperCase() : '';
  const codePrefixMismatch =
    Boolean(
      normalizedCode &&
      isValidServiceCode(normalizedCode) &&
      allowedPrefixes.length &&
      codePrefix &&
      !allowedPrefixes.includes(codePrefix)
    );
  const expectedPrefixLabel = allowedPrefixes.length ? allowedPrefixes.join(' / ') : '';
  const selectedGroupLabel = selectedServiceGroup
    ? t18(`admin2.sf_group_${selectedServiceGroup}`, { defaultValue: selectedServiceGroup })
    : '';

  // Auto-extract category_code from code prefix (guarded by prefix alignment checks)
  const derivedCategoryCode = formData.code ? formData.code.charAt(0).toUpperCase() : '';

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      notify.warning(t18('admin2.service_name_required'));
      return;
    }

    if (codePrefixMismatch) {
      const errorText = selectedGroupLabel
        ? t18('admin2.sf_code_mismatch_group_error', { code: normalizedCode, group: selectedGroupLabel, prefixes: expectedPrefixLabel })
        : t18('admin2.sf_code_mismatch_category_error', { code: normalizedCode, prefixes: expectedPrefixLabel });
      logger.warn('[FIX:ADM-06] Blocking mismatched service code before save:', {
        normalizedCode,
        selectedServiceGroup,
        allowedPrefixes,
        category_id: formData.category_id,
        queue_tag: formData.queue_tag,
        department_key: formData.department_key
      });
      setMessage({ type: 'danger', text: errorText });
      return;
    }

    // ✅ PREVIEW: Show changes preview for editing (not for new services)
    if (service) {
      setShowPreview(true);
    } else {
      // For new services, save directly
      handleConfirmSave();
    }
  };

  const handleConfirmSave = () => {
    // Подготавливаем данные для API
    const canonicalCode = normalizedCode || null;
    const apiData = {
      ...formData,
      price: formData.price ? parseFloat(formData.price) : null,
      category_id: formData.category_id ? parseInt(formData.category_id) : null,
      doctor_id: formData.doctor_id ? parseInt(formData.doctor_id) : null,
      duration_minutes: parseInt(formData.duration_minutes) || 30,
      code: canonicalCode,
      service_code: canonicalCode, // Sync for backwards compatibility
      category_code: derivedCategoryCode || null // Auto-derived from code
    };

    // Убираем пустые строки
    Object.keys(apiData).forEach((key) => {
      if (apiData[key] === '' || apiData[key] === 'null') {
        apiData[key] = null;
      }
    });

    logger.log('📝 Подготовленные данные для API:', apiData);
    setShowPreview(false);
    onSave(apiData);
  };

  const handleChange = (field, value) => {
    let normalizedValue = value;

    if (field === 'code') {
      normalizedValue = formatServiceCodeInput(value) as string;
    }

    // ⭐ SSOT: Sync queue_tag with department_key
    if (field === 'queue_tag' && normalizedValue) {
      const matchingProfile = queueProfiles.find((p) =>
      (p.queue_tags || []).includes(normalizedValue) || p.key === normalizedValue
      );

      if (matchingProfile) {
        setFormData((prev) => ({ ...prev, [field]: normalizedValue, department_key: matchingProfile.key }));
        return;
      }
    }

    setFormData((prev) => ({ ...prev, [field]: normalizedValue }));
  };

  const tabs = [
  { key: 'basic', label: t18('admin2.sf_tab_basic'), icon: Package },
  { key: 'queue', label: t18('admin2.sf_tab_queue'), icon: Users },
  { key: 'options', label: t18('admin2.sf_tab_options'), icon: Filter }];


  return (
    <MacOSCard variant="default" className="p-6">
      <h3 className="admin-h3-18-600-primary-mb-20">
        {service ? t18('admin2.sf_header_edit') : t18('admin2.sf_header_add')}
      </h3>

      {/* Tab Navigation */}
      <div className="admin-tab-bar-catalog">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className="admin-tab-btn-catalog"
              style={{
                '--admin-tab-border': isActive ? '2px solid var(--mac-accent)' : '2px solid transparent',
                '--admin-tab-color': isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                '--admin-tab-weight': isActive ? '600' : '500'
              } as CSSProperties}>

              <TabIcon size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
              {tab.label}
            </button>);

        })}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">

        {/* TAB: Основное */}
        {activeTab === 'basic' &&
        <div className="admin-grid-auto-250-12">
            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_name')}
              </label>
              <Input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              required />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_code')}
              </label>
              <Input
              type="text"
              value={formData.code}
              onChange={(e) => handleChange('code', e.target.value)}
              placeholder="K01"
              maxLength={3} />

              {formData.code && !isValidServiceCode(formData.code) &&
            <div className="admin-hint-12-warning-mt-4">
                  {t18('admin2.sf_hint_code_format')}
                </div>
            }
              {codeWarning &&
            <div className="admin-hint-12-error-mt-4-flex">
                  <AlertCircle size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                  {codeWarning}
                </div>
            }
              {checkingDuplicates && !codeWarning &&
            <div className="admin-hint-12-tertiary-mt-4">
                  {t18('admin2.sf_checking_duplicates')}
                </div>
            }
              {derivedCategoryCode &&
            <div className="admin-hint-12-secondary-mt-4">
                  {t18('admin2.sf_hint_code_prefix', { prefix: derivedCategoryCode })}
                </div>
            }
              {selectedGroupLabel && !codePrefixMismatch &&
            <div className="admin-hint-12-secondary-mt-4">
                  {t18('admin2.sf_hint_expected_prefix', { group: selectedGroupLabel, prefixes: expectedPrefixLabel })}
                </div>
            }
              {codePrefixMismatch &&
            <div className="admin-hint-12-warning-mt-4-flex">
                  <AlertCircle size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                  {selectedGroupLabel
                    ? t18('admin2.sf_warn_code_mismatch_group', { code: normalizedCode, group: selectedGroupLabel })
                    : t18('admin2.sf_warn_code_mismatch_no_group', { code: normalizedCode })}
                </div>
            }
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_category')}
              </label>
              <Select
              value={formData.category_id}
              onChange={(value) => handleChange('category_id', value)}
              options={[
              { value: '', label: t18('admin2.sf_select_category') },
              ...categories.map((category) => ({
                value: category.id,
                label: `${category.name_ru} (${category.specialty})`
              }))]
              } />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_price')}
              </label>
              <div className="admin-form-row-gap-8">
                <Input
                type="number"
                value={formData.price}
                onChange={(e) => handleChange('price', parseFloat(e.target.value) || '')}
                min="0"
                step="0.01"
                className="admin-input-flex-1" />

                <Select
                value={formData.currency}
                onChange={(value) => handleChange('currency', value)}
                options={[
                { value: 'UZS', label: 'UZS' },
                { value: 'USD', label: 'USD' }]
                }
                className="admin-input-min-w-80" />
              </div>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_duration')}
              </label>
              <Input
              type="number"
              value={formData.duration_minutes}
              onChange={(e) => handleChange('duration_minutes', parseInt(e.target.value) || 30)}
              min="5"
              step="5" />
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_doctor')}
              </label>
              <Select
              value={formData.doctor_id}
              onChange={(value) => handleChange('doctor_id', value)}
              options={[
              { value: '', label: t18('admin2.sf_select_all_doctors') },
              ...doctors.map((doctor) => ({
                value: doctor.id,
                label: `${doctor.user?.full_name || t18('admin2.sf_doctor_fallback', { id: doctor.id })} (${doctor.specialty})`
              }))]
              } />
            </div>
          </div>
        }

        {/* TAB: Очередь */}
        {activeTab === 'queue' &&
        <div className="flex flex-col gap-4">
            <div className="admin-info-banner-catalog">
              <p className="admin-p-14-secondary-m0">
                {t18('admin2.sf_queue_tab_desc')}
              </p>
            </div>

            <div>
              <label className="admin-label-14-500-primary-mb-8">
                {t18('admin2.sf_label_queue_tab')}
              </label>
              <Select
              value={formData.queue_tag}
              onChange={(value) => handleChange('queue_tag', value)}
              options={[
              { value: '', label: t18('admin2.sf_no_queue_option') },
              ...queueProfiles.
              filter((profile) => profile.is_active !== false).
              map((profile) => ({
                value: profile.queue_tags?.[0] || profile.key,
                label: profile.title_ru || profile.title
              }))]
              } />
            </div>

            {formData.queue_tag &&
          <div className="admin-success-banner-catalog">
                <p className="admin-p-14-success-m0">
                  {t18('admin2.sf_queue_tag_banner_prefix')} <strong>{formData.queue_tag}</strong>
                </p>
              </div>
          }
          </div>
        }

        {/* TAB: Опции */}
        {activeTab === 'options' &&
        <div className="flex flex-col gap-4">
            <div className="admin-grid-auto-200-12">
              <Checkbox
              id="active"
              checked={formData.active}
              onChange={(checked) => handleChange('active', checked)}
              label={t18('admin2.sf_chk_active')} />

              <Checkbox
              id="requires_doctor"
              checked={formData.requires_doctor}
              onChange={(checked) => handleChange('requires_doctor', checked)}
              label={t18('admin2.sf_chk_requires_doctor')} />

              <Checkbox
              id="is_consultation"
              checked={formData.is_consultation}
              onChange={(checked) => handleChange('is_consultation', checked)}
              label={t18('admin2.sf_chk_is_consultation')} />

              <Checkbox
              id="allow_doctor_price_override"
              checked={formData.allow_doctor_price_override}
              onChange={(checked) => handleChange('allow_doctor_price_override', checked)}
              label={t18('admin2.sf_chk_allow_price_override')} />

            </div>

            <div className="admin-bg-secondary-box-catalog">
              <h5 className="admin-h5-14-600-primary-mb-8">
                {t18('admin2.sf_hints_title')}
              </h5>
              <ul className="admin-ul-13-secondary-pl-20">
                <li><strong>{t18('admin2.sf_hint_requires_doctor_label')}</strong>{t18('admin2.sf_hint_requires_doctor_desc')}</li>
                <li><strong>{t18('admin2.sf_hint_consultation_label')}</strong>{t18('admin2.sf_hint_consultation_desc')}</li>
                <li><strong>{t18('admin2.sf_hint_price_override_label')}</strong>{t18('admin2.sf_hint_price_override_desc')}</li>
              </ul>
            </div>
          </div>
        }

        {/* Кнопки */}
        <div className="admin-form-actions-catalog">
          {/* UX Audit Admin #2.2: fake progress indicator «1/3, 2/3, 3/3» удалён.
              Табы свободные (можно кликнуть любую), индикатор вводил в заблуждение,
              имитируя wizard с последовательным продвижением. */}
          <div className="admin-form-row-gap-12">
            <Button type="button" variant="outline" onClick={onCancel}>
              <X size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
              {t18('admin2.sf_btn_cancel')}
            </Button>
            <Button type="submit">
              <Save size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
              {t18('admin2.sf_btn_save')}
            </Button>
          </div>
        </div>
      </form>

      {/* ✅ PREVIEW: Changes preview modal */}
      {showPreview && (
        <div className="admin-modal-overlay">
          <div className="admin-modal-body-catalog-800">
            <ServiceChangesPreview
              oldService={service}
              newService={formData}
              onConfirm={handleConfirmSave}
              onCancel={() => setShowPreview(false)}
            />
          </div>
        </div>
      )}
    </MacOSCard>);

};

ServiceForm.propTypes = {
  service: PropTypes.object,
  categories: PropTypes.array,
  doctors: PropTypes.array,
  queueProfiles: PropTypes.array,
  setMessage: PropTypes.func,
  onSave: PropTypes.func,
  onCancel: PropTypes.func
};

