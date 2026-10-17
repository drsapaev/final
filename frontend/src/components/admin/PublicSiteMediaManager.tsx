import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import { ImagePlus, RefreshCw, Upload } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import { buildApiUrl } from '../../api/runtime';
import {
  getPublicSiteMediaErrorKey,
  listPublicSiteDoctors,
  listPublicSiteMedia,
  publishPublicSiteMedia,
  unpublishPublicSiteMedia,
  uploadPublicSiteMedia,
  type PublicSiteDoctorOption,
  type PublicSiteMedia,
  type PublicSiteMediaKind,
} from '../../api/publicSiteMedia';
import { useConfirm } from '../common/ConfirmDialog';
import { Button, Card } from '../ui/macos';
import './PublicSiteMediaManager.css';

const ACCEPTED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const ACCEPTED_FILE_NAME = /\.(jpe?g|png|webp)$/i;
const FILE_ACCEPT = 'image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp';
const STORAGE_UNAVAILABLE_KEY = 'publicSiteMedia.storageUnavailable';

function upsertMedia(current: PublicSiteMedia[], updated: PublicSiteMedia): PublicSiteMedia[] {
  const sameOwner = (item: PublicSiteMedia) =>
    item.asset_kind === updated.asset_kind && item.doctor_id === updated.doctor_id;

  const next = current.map((item) => {
    if (item.id === updated.id) return updated;
    if (updated.is_published && sameOwner(item) && item.is_published) {
      return { ...item, is_published: false, published_at: null };
    }
    return item;
  });

  if (next.some((item) => item.id === updated.id)) return next;
  return [updated, ...next];
}

export default function PublicSiteMediaManager() {
  const { t } = useTranslation();
  const [confirm, confirmDialog] = useConfirm();
  const [media, setMedia] = useState<PublicSiteMedia[]>([]);
  const [doctors, setDoctors] = useState<PublicSiteDoctorOption[]>([]);
  const [doctorLoadFailed, setDoctorLoadFailed] = useState(false);
  const [assetKind, setAssetKind] = useState<PublicSiteMediaKind>('clinic_logo');
  const [doctorId, setDoctorId] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [loadErrorKey, setLoadErrorKey] = useState<string | null>(null);
  const [actionErrorKey, setActionErrorKey] = useState<string | null>(null);
  const [noticeKey, setNoticeKey] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    const [mediaResult, doctorsResult] = await Promise.allSettled([
      listPublicSiteMedia(),
      listPublicSiteDoctors(),
    ]);

    if (mediaResult.status === 'fulfilled') {
      setMedia(mediaResult.value);
      setLoadErrorKey(null);
      setActionErrorKey((current) => current === STORAGE_UNAVAILABLE_KEY ? null : current);
    } else {
      setLoadErrorKey(getPublicSiteMediaErrorKey(mediaResult.reason));
    }

    if (doctorsResult.status === 'fulfilled') {
      setDoctors(doctorsResult.value);
      setDoctorLoadFailed(false);
    } else {
      setDoctors([]);
      setDoctorLoadFailed(true);
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }

    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  const selectedDoctorId = doctorId ? Number(doctorId) : null;
  const selectedDoctor = doctors.find((doctor) => doctor.id === selectedDoctorId);
  const storageUnavailable = loadErrorKey === STORAGE_UNAVAILABLE_KEY
    || actionErrorKey === STORAGE_UNAVAILABLE_KEY;
  const mutationsDisabled = isLoading || Boolean(loadErrorKey) || storageUnavailable;
  const scopedMedia = media
    .filter((item) => {
      if (item.asset_kind !== assetKind) return false;
      if (assetKind === 'clinic_logo') return item.doctor_id === null;
      return selectedDoctorId !== null && item.doctor_id === selectedDoctorId;
    })
    .sort((left, right) => right.created_at.localeCompare(left.created_at));

  const clearFeedback = () => {
    setActionErrorKey(null);
    setNoticeKey(null);
  };

  const handleAssetKindChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setAssetKind(event.target.value as PublicSiteMediaKind);
    setFile(null);
    clearFeedback();
  };

  const handleDoctorChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setDoctorId(event.target.value);
    setFile(null);
    clearFeedback();
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    clearFeedback();
    if (nextFile && !ACCEPTED_MIME_TYPES.has(nextFile.type) && !ACCEPTED_FILE_NAME.test(nextFile.name)) {
      setFile(null);
      setActionErrorKey('publicSiteMedia.invalidFileType');
      event.target.value = '';
      return;
    }
    setFile(nextFile);
  };

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearFeedback();
    if (!file) {
      setActionErrorKey('publicSiteMedia.selectFile');
      return;
    }
    if (assetKind === 'doctor_portrait' && selectedDoctorId === null) {
      setActionErrorKey('publicSiteMedia.selectDoctorError');
      return;
    }
    if (assetKind === 'doctor_portrait' && doctorLoadFailed) {
      setActionErrorKey('publicSiteMedia.doctorsLoadError');
      return;
    }
    if (assetKind === 'doctor_portrait') {
      if (!selectedDoctor) {
        setActionErrorKey('publicSiteMedia.doctorUnavailable');
        return;
      }
      if (!selectedDoctor.active) {
        setActionErrorKey('publicSiteMedia.inactiveDoctorUpload');
        return;
      }
    }

    setIsBusy(true);
    try {
      const uploaded = await uploadPublicSiteMedia(
        file,
        assetKind,
        assetKind === 'doctor_portrait' ? selectedDoctorId ?? undefined : undefined,
      );
      setMedia((current) => upsertMedia(current, uploaded));
      setNoticeKey('publicSiteMedia.uploadSuccess');
    } catch (error) {
      setActionErrorKey(getPublicSiteMediaErrorKey(error));
    } finally {
      setIsBusy(false);
    }
  };

  const handlePublish = async (item: PublicSiteMedia) => {
    clearFeedback();
    if (assetKind === 'doctor_portrait') {
      if (doctorLoadFailed) {
        setActionErrorKey('publicSiteMedia.doctorsLoadError');
        return;
      }
      if (!selectedDoctor) {
        setActionErrorKey('publicSiteMedia.doctorUnavailable');
        return;
      }
      if (!selectedDoctor.active) {
        setActionErrorKey('publicSiteMedia.inactiveDoctorUpload');
        return;
      }
    }
    const approved = await confirm({
      title: t('publicSiteMedia.confirmPublishTitle'),
      message: t('publicSiteMedia.confirmPublishMessage'),
      confirmLabel: t('publicSiteMedia.confirmPublish'),
      cancelLabel: t('publicSiteMedia.cancel'),
      intent: 'primary',
    });
    if (!approved) return;

    setIsBusy(true);
    try {
      const published = await publishPublicSiteMedia(item.id);
      setMedia((current) => upsertMedia(current, published));
      setNoticeKey('publicSiteMedia.publishSuccess');
    } catch (error) {
      setActionErrorKey(getPublicSiteMediaErrorKey(error));
    } finally {
      setIsBusy(false);
    }
  };

  const handleUnpublish = async (item: PublicSiteMedia) => {
    clearFeedback();
    const approved = await confirm({
      title: t('publicSiteMedia.confirmUnpublishTitle'),
      message: t('publicSiteMedia.confirmUnpublishMessage'),
      confirmLabel: t('publicSiteMedia.confirmUnpublish'),
      cancelLabel: t('publicSiteMedia.cancel'),
      intent: 'warning',
    });
    if (!approved) return;

    setIsBusy(true);
    try {
      const unpublished = await unpublishPublicSiteMedia(item.id);
      setMedia((current) => upsertMedia(current, unpublished));
      setNoticeKey('publicSiteMedia.unpublishSuccess');
    } catch (error) {
      setActionErrorKey(getPublicSiteMediaErrorKey(error));
    } finally {
      setIsBusy(false);
    }
  };

  const formatSize = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024))} KB`;

  return (
    <main className="public-site-media" aria-labelledby="public-site-media-title">
      {confirmDialog}
      <header className="public-site-media__header">
        <div>
          <h1 id="public-site-media-title">{t('publicSiteMedia.title')}</h1>
          <p>{t('publicSiteMedia.description')}</p>
        </div>
        <Button
          type="button"
          variant="outline"
          startIcon={<RefreshCw aria-hidden="true" size={16} />}
          onClick={() => void refresh()}
          disabled={isLoading || isBusy}
        >
          {t('common.refresh')}
        </Button>
      </header>

      <p className="public-site-media__rights" role="note">{t('publicSiteMedia.rightsNotice')}</p>

      {loadErrorKey && (
        <div className="public-site-media__message public-site-media__message--error" role="alert">
          <span>{t(loadErrorKey)}</span>
          <Button type="button" variant="outline" onClick={() => void refresh()} disabled={isLoading}>
            {t('publicSiteMedia.retry')}
          </Button>
        </div>
      )}
      {actionErrorKey && (
        <div className="public-site-media__message public-site-media__message--error" role="alert">
          {t(actionErrorKey)}
        </div>
      )}
      {noticeKey && (
        <div className="public-site-media__message public-site-media__message--success" role="status">
          {t(noticeKey)}
        </div>
      )}

      <div className="public-site-media__grid">
        <Card className="public-site-media__panel" variant="outlined" padding="default">
          <h2>{t('publicSiteMedia.chooseFile')}</h2>
          <form className="public-site-media__form" onSubmit={(event) => void handleUpload(event)}>
            <label className="public-site-media__field">
              <span>{t('publicSiteMedia.assetKind')}</span>
              <select value={assetKind} onChange={handleAssetKindChange} disabled={isBusy}>
                <option value="clinic_logo">{t('publicSiteMedia.clinicLogo')}</option>
                <option value="doctor_portrait">{t('publicSiteMedia.doctorPortrait')}</option>
              </select>
            </label>

            {assetKind === 'doctor_portrait' && (
              <label className="public-site-media__field">
                <span>{t('publicSiteMedia.doctor')}</span>
                <select
                  value={doctorId}
                  onChange={handleDoctorChange}
                  disabled={isBusy || doctorLoadFailed || doctors.length === 0}
                >
                  <option value="">{t('publicSiteMedia.selectDoctor')}</option>
                  {doctors.map((doctor) => (
                    <option key={doctor.id} value={doctor.id}>
                      {doctor.active ? doctor.displayName : `${doctor.displayName} · ${t('publicSiteMedia.inactiveDoctor')}`}
                    </option>
                  ))}
                </select>
                {doctorLoadFailed && <span className="public-site-media__inline-error">{t('publicSiteMedia.doctorsLoadError')}</span>}
                {!doctorLoadFailed && doctors.length === 0 && <span className="public-site-media__hint">{t('publicSiteMedia.noDoctors')}</span>}
                {doctorId && !doctorLoadFailed && !selectedDoctor && <span className="public-site-media__inline-error">{t('publicSiteMedia.doctorUnavailable')}</span>}
                {selectedDoctor?.active === false && <span className="public-site-media__inline-error">{t('publicSiteMedia.inactiveDoctorUpload')}</span>}
              </label>
            )}

            <label className="public-site-media__field">
              <span>{t('publicSiteMedia.chooseFile')}</span>
              <input
                type="file"
                accept={FILE_ACCEPT}
                onChange={handleFileChange}
                aria-label={t('publicSiteMedia.chooseFile')}
                disabled={isBusy || storageUnavailable || (assetKind === 'doctor_portrait' && (!selectedDoctor || !selectedDoctor.active || doctorLoadFailed))}
              />
              <span className="public-site-media__hint">{t('publicSiteMedia.supportedFormats')}</span>
            </label>

            {previewUrl && (
              <div className="public-site-media__preview">
                <p>{t('publicSiteMedia.localPreview')}</p>
                <img src={previewUrl} alt={t('publicSiteMedia.previewAlt')} />
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              startIcon={<Upload aria-hidden="true" size={16} />}
              loading={isBusy}
              disabled={isBusy || mutationsDisabled || !file || (assetKind === 'doctor_portrait' && (!selectedDoctor || !selectedDoctor.active || doctorLoadFailed))}
            >
              {isBusy ? t('publicSiteMedia.uploading') : t('publicSiteMedia.uploadDraft')}
            </Button>
          </form>
        </Card>

        <Card className="public-site-media__panel" variant="outlined" padding="default">
          <div className="public-site-media__list-heading">
            <h2>{assetKind === 'clinic_logo' ? t('publicSiteMedia.clinicLogo') : selectedDoctor?.displayName || t('publicSiteMedia.doctorPortrait')}</h2>
            {assetKind === 'doctor_portrait' && selectedDoctor && (
              <span className="public-site-media__doctor-label">{t('publicSiteMedia.doctor')}</span>
            )}
          </div>

          {isLoading ? (
            <p className="public-site-media__hint" role="status">{t('publicSiteMedia.loading')}</p>
          ) : scopedMedia.length === 0 ? (
            <div className="public-site-media__empty">
              <ImagePlus aria-hidden="true" size={24} />
              <p>{t('publicSiteMedia.noMedia')}</p>
            </div>
          ) : (
            <ul className="public-site-media__list">
              {scopedMedia.map((item) => (
                <li key={item.id}>
                  <article className="public-site-media__item">
                    {item.is_published && (
                      <img
                        className="public-site-media__published-image"
                        src={buildApiUrl(item.media_url)}
                        alt={assetKind === 'clinic_logo' ? t('publicSiteMedia.clinicLogo') : selectedDoctor?.displayName || t('publicSiteMedia.doctorPortrait')}
                        loading="lazy"
                      />
                    )}
                    <div className="public-site-media__item-body">
                      <span className={`public-site-media__status${item.is_published ? ' public-site-media__status--published' : ''}`}>
                        {t(item.is_published ? 'publicSiteMedia.published' : 'publicSiteMedia.draft')}
                      </span>
                      <p>{item.mime_type} · {t('publicSiteMedia.size')}: {formatSize(item.byte_size)}</p>
                      <div className="public-site-media__actions">
                        {item.is_published ? (
                          <Button type="button" variant="outline" color="warning" onClick={() => void handleUnpublish(item)} disabled={mutationsDisabled || isBusy}>
                            {t('publicSiteMedia.unpublish')}
                          </Button>
                        ) : (
                          <Button type="button" variant="primary" onClick={() => void handlePublish(item)} disabled={mutationsDisabled || isBusy || (assetKind === 'doctor_portrait' && (!selectedDoctor || !selectedDoctor.active || doctorLoadFailed))}>
                            {t('publicSiteMedia.publish')}
                          </Button>
                        )}
                      </div>
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </main>
  );
}
