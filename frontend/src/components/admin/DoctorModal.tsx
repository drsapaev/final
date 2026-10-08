
import { useEffect, useMemo, useRef, useState } from 'react';
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
  Textarea,
} from '../ui/macos';
import type { SelectChangeEvent } from '../ui/macos/Select';
import { useTranslation } from '../../i18n/useTranslation';
import React from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import type { WebsiteDoctorContent } from '../../types/domain/clinic';

interface DoctorUser {
  id: string | number;
  full_name?: string;
  username?: string;
  email?: string;
  phone?: string;
  role?: string;
  is_active?: boolean;
  linked_doctor_id?: string | number | null;
}

// Local doctor-record shape for the DoctorModal admin form. Named `DoctorRecord`
// to avoid shadowing the canonical `Doctor` domain type in @/types/domain/clinic.
interface DoctorRecord {
  id?: string | number;
  user_id?: string | number | null;
  specialty?: string;
  cabinet?: string;
  price_default?: number | null;
  start_number_online?: number | null;
  max_online_per_day?: number | null;
  active?: boolean;
  user?: DoctorUser | null;
}

// Local department-list shape (used for <Select> options). Named `DepartmentDto`
// because `Department` is a canonical domain type in @/types/domain/clinic.
interface DepartmentDto {
  value: string;
  label: string;
}

interface DoctorModalProps {
  isOpen: boolean;
  onClose: () => void;
  doctor?: DoctorRecord | null;
  onSave: (data: Record<string, unknown>) => Promise<void> | void;
  loading?: boolean;
  availableUsers?: DoctorUser[];
  departments?: DepartmentDto[];
}

interface DoctorFormState {
  userId: string;
  specialty: string;
  cabinet: string;
  priceDefault: string;
  startNumberOnline: string;
  maxOnlinePerDay: string;
  active: boolean;
}

const DoctorModal = ({
  isOpen,
  onClose,
  doctor = null,
  onSave,
  loading = false,
  availableUsers = [],
  departments = [],
}: DoctorModalProps) => {
  const { t: rawT, language } = useTranslation(); const t = rawT;
  const [formData, setFormData] = useState<DoctorFormState>({
    userId: '',
    specialty: '',
    cabinet: '',
    priceDefault: '',
    startNumberOnline: '1',
    maxOnlinePerDay: '15',
    active: true,
  });
  const [errors, setErrors] = useState<Record<string, string | null>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  // Catalog-backed specialty options (Codex P1): the specialty written to
  // Doctor.specialty must be an ACTIVE medical_specialties code; department
  // keys (cardio/dental/...) are a DIFFERENT domain and now rejected by the
  // backend write guard. Loaded from the vocabulary endpoint; on failure the
  // select stays empty and the backend 400/503 detail surfaces on submit.
  const [specialtyOptions, setSpecialtyOptions] = useState<
    { value: string; label: string }[]
  >([]);
  const [websiteContent, setWebsiteContent] = useState<WebsiteDoctorContent | null>(null);
  const [websiteForm, setWebsiteForm] = useState({ bio_ru: '', bio_uz: '', slug: '' });
  const [websiteLoading, setWebsiteLoading] = useState(false);
  const [websiteSaving, setWebsiteSaving] = useState(false);
  const [websiteError, setWebsiteError] = useState('');
  const [websiteNotice, setWebsiteNotice] = useState('');
  const websiteLoadErrorTranslation = useRef(t);
  const websiteRequestGeneration = useRef(0);

  useEffect(() => {
    websiteLoadErrorTranslation.current = t;
  }, [t]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    // Locale resolution per owner spec: ru→title_ru, en→title_en,
    // uz-Latn→title_uz, everything else (uz-Cyrl, kk, unknown) → title_ru
    // compatibility fallback, then code (Codex P2: translations were
    // unreachable outside the Russian locale).
    const titleFieldForLocale: Record<string, 'title_ru' | 'title_uz' | 'title_en'> = {
      ru: 'title_ru',
      en: 'title_en',
      'uz-Latn': 'title_uz',
    };
    const titleField =
      titleFieldForLocale[language] ?? 'title_ru';
    import('../../api/client')
      .then(({ api }) =>
        api.get('/admin/doctors/specialty-vocabulary').catch(() => null),
      )
      .then(
        (
          response: {
            data?: Array<{
              code: string;
              title_ru?: string | null;
              title_uz?: string | null;
              title_en?: string | null;
            }>;
          } | null,
        ) => {
          if (cancelled) return;
          // Catalog unavailable (network error / 503): clear the previous
          // options instead of leaving a stale, selectable list that only
          // fails on save (Codex P2 round 5).
          if (!response?.data) {
            setSpecialtyOptions([]);
            return;
          }
          setSpecialtyOptions(
            response.data.map((item) => ({
              value: item.code,
              label: item[titleField] || item.title_ru || item.code,
            })),
          );
        },
      )
      .catch(() => {
        if (!cancelled) setSpecialtyOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, language]);

  useEffect(() => {
    const requestGeneration = ++websiteRequestGeneration.current;
    if (!isOpen || !doctor?.id) {
      setWebsiteContent(null);
      setWebsiteForm({ bio_ru: '', bio_uz: '', slug: '' });
      setWebsiteError('');
      setWebsiteNotice('');
      setWebsiteLoading(false);
      setWebsiteSaving(false);
      return;
    }

    let cancelled = false;
    setWebsiteLoading(true);
    setWebsiteSaving(false);
    setWebsiteError('');
    setWebsiteContent(null);
    setWebsiteForm({ bio_ru: '', bio_uz: '', slug: '' });
    api.get(`/admin/doctors/${doctor.id}/website-content`)
      .then((response) => {
        if (cancelled || requestGeneration !== websiteRequestGeneration.current) return;
        const content = response.data as WebsiteDoctorContent;
        setWebsiteContent(content);
        setWebsiteForm({
          bio_ru: content.bio_ru || '',
          bio_uz: content.bio_uz || '',
          slug: content.slug || '',
        });
      })
      .catch((error: unknown) => {
        if (cancelled || requestGeneration !== websiteRequestGeneration.current) return;
        const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
        const detailMessage = typeof detail === 'object' && detail !== null
          ? (detail as { message?: string }).message
          : typeof detail === 'string' ? detail : undefined;
        setWebsiteError(
          detailMessage || websiteLoadErrorTranslation.current('admin2.dmdl_site_load_error'),
        );
      })
      .finally(() => {
        if (!cancelled && requestGeneration === websiteRequestGeneration.current) {
          setWebsiteLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (requestGeneration === websiteRequestGeneration.current) {
        websiteRequestGeneration.current += 1;
      }
    };
  }, [doctor?.id, isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    setFormData({
      userId: doctor?.user_id != null ? String(doctor.user_id) : '',
      specialty: doctor?.specialty || '',
      cabinet: doctor?.cabinet || '',
      priceDefault:
        doctor?.price_default == null
          ? ''
          : String(doctor.price_default),
      startNumberOnline:
        doctor?.start_number_online == null
          ? '1'
          : String(doctor.start_number_online),
      maxOnlinePerDay:
        doctor?.max_online_per_day == null
          ? '15'
          : String(doctor.max_online_per_day),
      active: doctor?.active !== false,
    });
    setErrors({});
    setSubmitError(null);
  }, [doctor, isOpen]);

  const selectedUser = useMemo<DoctorUser | null>(() => {
    const fallbackUser = doctor?.user || null;
    const fromList = availableUsers.find(
      (item) => String(item.id) === String(formData.userId)
    );
    return fromList || fallbackUser || null;
  }, [availableUsers, doctor?.user, formData.userId]);

  const selectedUserStatus = useMemo<{ variant: string; label: string }>(() => {
    if (!selectedUser) return { variant: 'warning', label: t('admin2.dmdl_user_not_selected') };
    if (selectedUser.is_active === false) {
      return { variant: 'warning', label: t('admin2.dmdl_user_account_inactive') };
    }
    if (selectedUser.linked_doctor_id && String(selectedUser.linked_doctor_id) !== String(doctor?.id || '')) {
      return { variant: 'warning', label: t('admin2.dmdl_user_already_linked', { id: selectedUser.linked_doctor_id }) };
    }
    return { variant: 'success', label: t('admin2.dmdl_user_link_active') };
  }, [doctor?.id, selectedUser, t]);

  const userOptions = useMemo(
    () => [
      { value: '', label: t('admin2.dmdl_user_select_placeholder') },
      ...availableUsers.map((user) => ({
        value: String(user.id),
        label: `${user.full_name || user.username || ''} • ${user.role || ''}${user.is_active ? '' : t('admin2.dmdl_user_inactive_suffix')}`,
      })),
    ],
    [availableUsers, t]
  );

  const validateForm = () => {
    const nextErrors: Record<string, string | null> = {};
    if (!formData.userId) {
      nextErrors.userId = t('admin2.dmdl_err_user_required');
    }
    if (!formData.specialty.trim()) {
      nextErrors.specialty = t('admin2.dmdl_err_specialty_required');
    } else if (!/^[a-z][a-z0-9_]*$/.test(formData.specialty.trim())) {
      // PR-19: validate specialty format — must match queue_tag pattern
      nextErrors.specialty = t('admin2.dmdl_err_specialty_format');
    }
    if (formData.priceDefault !== '' && Number.isNaN(Number(formData.priceDefault))) {
      nextErrors.priceDefault = t('admin2.dmdl_err_price_number');
    }
    if (formData.startNumberOnline !== '' && Number.isNaN(Number(formData.startNumberOnline))) {
      nextErrors.startNumberOnline = t('admin2.dmdl_err_start_number');
    }
    if (formData.maxOnlinePerDay !== '' && Number.isNaN(Number(formData.maxOnlinePerDay))) {
      nextErrors.maxOnlinePerDay = t('admin2.dmdl_err_max_online_number');
    }

    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleChange = <K extends keyof DoctorFormState>(field: K, value: DoctorFormState[K]) => {
    setFormData((current) => ({ ...current, [field]: value }));
    if (errors[field]) {
      setErrors((current) => ({ ...current, [field]: null }));
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
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
    } catch (error: unknown) {
      setSubmitError((error instanceof Error ? error.message : String(error)) || t('admin2.dmdl_err_save_fallback'));
    }
  };

  const saveWebsiteContent = async (
    operation: 'save_draft' | 'save_published' | 'publish' | 'unpublish' | 'republish',
  ) => {
    if (!doctor?.id) return;
    setWebsiteSaving(true);
    setWebsiteError('');
    setWebsiteNotice('');
    const requestGeneration = websiteRequestGeneration.current;
    const requestedDoctorId = doctor.id;
    try {
      const response = await api.put(
        `/admin/doctors/${requestedDoctorId}/website-content`,
        { ...websiteForm, operation },
      );
      const content = response.data as WebsiteDoctorContent;
      if (
        requestGeneration !== websiteRequestGeneration.current ||
        String(content.id) !== String(requestedDoctorId)
      ) {
        logger.debug('[FIX] Ignored stale website doctor save response');
        return;
      }
      setWebsiteContent(content);
      setWebsiteForm({
        bio_ru: content.bio_ru || '',
        bio_uz: content.bio_uz || '',
        slug: content.slug || '',
      });
      setWebsiteNotice(t('admin2.dmdl_site_save_success'));
    } catch (error: unknown) {
      if (requestGeneration !== websiteRequestGeneration.current) {
        logger.debug('[FIX] Ignored stale website doctor save error');
        return;
      }
      const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const detailMessage = typeof detail === 'object' && detail !== null
        ? (detail as { message?: string }).message
        : typeof detail === 'string' ? detail : undefined;
      setWebsiteError(detailMessage || t('admin2.dmdl_site_save_error'));
    } finally {
      if (requestGeneration === websiteRequestGeneration.current) {
        setWebsiteSaving(false);
      }
    }
  };

  const websiteMissingFields = websiteContent ? [
    ...(!websiteContent.display_name?.trim() ? ['display_name'] : []),
    ...(!websiteForm.bio_ru.trim() ? ['bio_ru'] : []),
    ...(!websiteForm.bio_uz.trim() ? ['bio_uz'] : []),
    ...(!websiteForm.slug.trim() ? ['slug'] : []),
    ...(!websiteContent.active || !websiteContent.owner_active ? ['active'] : []),
  ] : [];

  const websiteFieldLabel = (field: string) => {
    const keys: Record<string, string> = {
      display_name: 'dmdl_site_display_name',
      bio_ru: 'dmdl_site_bio_ru',
      bio_uz: 'dmdl_site_bio_uz',
      slug: 'dmdl_site_slug',
      active: 'dmdl_active_label',
    };
    return t(`admin2.${keys[field] || field}`);
  };

  const renderFieldError = (field: keyof DoctorFormState) =>
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
      title={doctor ? t('admin2.dmdl_title_edit') : t('admin2.dmdl_title_add')}
      size="large"
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
            {t('admin2.dmdl_label_user')}
          </Label>
          <Select
            value={formData.userId}
            onChange={(e: SelectChangeEvent) => handleChange('userId', e.target.value)}
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
            <Label className="admin-label-block-mb-8">{t('admin2.dmdl_label_full_name')}</Label>
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
            <Label className="admin-label-block-mb-8">{t('admin2.dmdl_label_role')}</Label>
            <Input value={selectedUser?.role || ''} readOnly />
          </div>
        </div>

        <div className="admin-flex-wrap-8">
          <Badge variant={selectedUserStatus.variant}>
            {selectedUserStatus.label}
          </Badge>
          <Badge variant={formData.cabinet ? 'info' : 'warning'}>
            {formData.cabinet ? t('admin2.dmdl_cabinet_set', { cabinet: formData.cabinet }) : t('admin2.dmdl_cabinet_not_set')}
          </Badge>
        </div>

        <div
          className="admin-grid-autofit-220-16"
        >
          <div>
            <Label required className="admin-label-block-mb-8">
              {t('admin2.dmdl_label_specialty')}
            </Label>
            {specialtyOptions.length > 0 ? (
              <Select
                value={formData.specialty}
                onChange={(e: SelectChangeEvent) => handleChange('specialty', e.target.value)}
                options={[
                  { value: '', label: t('admin2.dmdl_select_department_placeholder') },
                  ...specialtyOptions,
                  // Editing a doctor whose stored specialty is inactive/absent
                  // from the active catalog: keep the value visible as a
                  // clearly-marked historical option so unrelated edits do not
                  // look like a blank/reassigned specialty (the backend accepts
                  // the unchanged historical value — no-cascade contract).
                  ...(doctor?.specialty &&
                  doctor.specialty === formData.specialty &&
                  !specialtyOptions.some((o) => o.value === formData.specialty)
                    ? [
                        {
                          value: doctor.specialty,
                          label: `${doctor.specialty} (${t('admin2.dmdl_specialty_historical')})`,
                        },
                      ]
                    : []),
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
              {t('admin2.dmdl_specialty_hint')}
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
              {t('admin2.dmdl_label_price_default')}
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
              {t('admin2.dmdl_label_start_number')}
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
              {t('admin2.dmdl_label_max_online')}
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
            onChange={(checked: boolean) => handleChange('active', checked)}
            label={t('admin2.dmdl_active_label')}
            description={t('admin2.dmdl_active_description')}
          />
        </div>

        {doctor?.id && (
          <section aria-labelledby="doctor-site-content-title" className="admin-flex-col-16">
            <div className="admin-flex items-center justify-between gap-8">
              <div>
                <h3 id="doctor-site-content-title" className="admin-title-20">
                  {t('admin2.dmdl_site_content_title')}
                </h3>
                <p className="admin-hint-text-12-secondary-mt-4">
                  {t('admin2.dmdl_site_content_help')}
                </p>
              </div>
              {websiteContent && (
                <Badge variant={websiteContent.show_on_website ? 'success' : 'outline'}>
                  {websiteContent.show_on_website
                    ? t('admin2.sitepub_status_published')
                    : t('admin2.sitepub_status_draft')}
                </Badge>
              )}
            </div>

            {websiteLoading && <p role="status">{t('admin2.sitepub_loading')}</p>}
            {websiteError && <Alert type="error" className="admin-mb-12">{websiteError}</Alert>}
            {websiteNotice && <Alert type="success" className="admin-mb-12">{websiteNotice}</Alert>}

            {websiteContent && (
              <>
                <div className="admin-grid-autofit-220-16">
                  <div>
                    <Label htmlFor="doctor-site-display-name" className="admin-label-block-mb-8">
                      {t('admin2.dmdl_site_display_name')}
                    </Label>
                    <Input id="doctor-site-display-name" value={websiteContent.display_name || ''} readOnly />
                  </div>
                  <div>
                    <Label htmlFor="doctor-site-slug" required className="admin-label-block-mb-8">
                      {t('admin2.dmdl_site_slug')}
                    </Label>
                    <Input
                      id="doctor-site-slug"
                      value={websiteForm.slug}
                      onChange={(event) => setWebsiteForm((current) => ({ ...current, slug: event.target.value }))}
                      disabled={websiteSaving || websiteLoading || websiteContent.slug_locked}
                      maxLength={160}
                    />
                    {websiteContent.slug_locked && (
                      <p className="admin-hint-text-12-secondary-mt-4">{t('admin2.dmdl_site_slug_locked')}</p>
                    )}
                  </div>
                  <div>
                    <Label htmlFor="doctor-site-bio-ru" required className="admin-label-block-mb-8">
                      {t('admin2.dmdl_site_bio_ru')}
                    </Label>
                    <Textarea
                      id="doctor-site-bio-ru"
                      value={websiteForm.bio_ru}
                      onChange={(event) => setWebsiteForm((current) => ({ ...current, bio_ru: event.target.value }))}
                      disabled={websiteSaving || websiteLoading}
                      minRows={3}
                    />
                  </div>
                  <div>
                    <Label htmlFor="doctor-site-bio-uz" required className="admin-label-block-mb-8">
                      {t('admin2.dmdl_site_bio_uz')}
                    </Label>
                    <Textarea
                      id="doctor-site-bio-uz"
                      value={websiteForm.bio_uz}
                      onChange={(event) => setWebsiteForm((current) => ({ ...current, bio_uz: event.target.value }))}
                      disabled={websiteSaving || websiteLoading}
                      minRows={3}
                    />
                  </div>
                </div>

                {websiteMissingFields.length > 0 && (
                  <p role="status" className="admin-hint-text-12-secondary-mt-4">
                    {t('admin2.dmdl_site_missing_fields')}: {websiteMissingFields.map(websiteFieldLabel).join(', ')}
                  </p>
                )}
                {(!websiteContent.active || !websiteContent.owner_active) && (
                  <p role="status" className="admin-hint-text-12-secondary-mt-4">
                    {t('admin2.dmdl_site_active_required')}
                  </p>
                )}

                <div className="admin-flex-wrap-8">
                  {!websiteContent.show_on_website && (
                    <Button type="button" variant="outline" onClick={() => void saveWebsiteContent('save_draft')} disabled={websiteSaving || websiteLoading}>
                      {websiteSaving ? t('admin2.sitepub_saving') : t('admin2.sitepub_save_draft')}
                    </Button>
                  )}
                  {websiteContent.show_on_website && (
                    <Button type="button" variant="outline" onClick={() => void saveWebsiteContent('save_published')} disabled={websiteSaving || websiteLoading || websiteMissingFields.length > 0}>
                      {websiteSaving ? t('admin2.sitepub_saving') : t('admin2.sitepub_save_published')}
                    </Button>
                  )}
                  {!websiteContent.show_on_website && (
                    <Button type="button" onClick={() => void saveWebsiteContent(websiteContent.website_first_published_at ? 'republish' : 'publish')} disabled={websiteSaving || websiteLoading || websiteMissingFields.length > 0}>
                      {websiteSaving
                        ? t('admin2.sitepub_saving')
                        : websiteContent.website_first_published_at
                          ? t('admin2.sitepub_republish')
                          : t('admin2.sitepub_publish')}
                    </Button>
                  )}
                  {websiteContent.show_on_website && (
                    <Button type="button" variant="outline" onClick={() => void saveWebsiteContent('unpublish')} disabled={websiteSaving || websiteLoading}>
                      {t('admin2.sitepub_unpublish')}
                    </Button>
                  )}
                </div>
              </>
            )}
          </section>
        )}

        <div
          className="admin-modal-actions-footer"
        >
          <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
            {t('admin2.dmdl_btn_cancel')}
          </Button>
          <Button type="submit" disabled={loading} icon={<Save size={16} />}>
            {doctor ? t('admin2.dmdl_btn_save') : t('admin2.dmdl_title_add')}
          </Button>
        </div>
      </form>
    </Modal>
  );
};


export default DoctorModal;
