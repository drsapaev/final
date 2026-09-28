import { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Card, Input, Select } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import {
  deleteDentalMedia,
  listDentalMedia,
  loadDentalMediaContent,
  updateDentalMedia,
  uploadDentalMedia,
  type DentalMediaCategory,
  type DentalMediaItem,
  type DentalMediaMetadata,
} from '../../api/dentalMedia';

type MetadataDraft = {
  title: string;
  description: string;
  category: DentalMediaCategory;
  tooth: string;
  capture_date: string;
};

interface PhotoArchiveProps {
  patientId?: string | number | null;
  visitId?: string | number | null;
  patientName?: string;
  presentation?: 'page' | 'dialog';
  onClose?: () => void;
  onGoToPatients?: () => void;
  onGoToQueue?: () => void;
}

const toId = (value?: string | number | null) => {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
};

const errorStatus = (error: unknown): number | undefined => {
  if (!error || typeof error !== 'object') return undefined;
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === 'number' ? response.status : undefined;
};

const newMetadataDraft = (item: DentalMediaItem): MetadataDraft => ({
  title: item.title || '',
  description: item.description || '',
  category: item.category,
  tooth: item.tooth || '',
  capture_date: item.capture_date || '',
});

const PhotoArchive = ({
  patientId,
  visitId,
  patientName = '',
  presentation = 'page',
  onClose,
  onGoToPatients,
  onGoToQueue,
}: PhotoArchiveProps) => {
  const { t } = useTranslation();
  const numericPatientId = toId(patientId);
  const numericVisitId = toId(visitId);
  const [items, setItems] = useState<DentalMediaItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [category, setCategory] = useState<DentalMediaCategory>('photo');
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadTooth, setUploadTooth] = useState('');
  const [uploadDate, setUploadDate] = useState('');
  const [uploading, setUploading] = useState(false);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<MetadataDraft | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ item: DentalMediaItem; url: string } | null>(null);
  const [previewingId, setPreviewingId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewCloseRef = useRef<HTMLButtonElement>(null);
  const requestId = useRef(0);

  const reload = useCallback(async () => {
    if (!numericPatientId || !numericVisitId) return;
    const currentRequest = ++requestId.current;
    setLoading(true);
    setLoadingMore(false);
    setLoadError(false);
    try {
      const result = await listDentalMedia(numericPatientId, numericVisitId);
      if (requestId.current !== currentRequest) return;
      setItems(result.items);
      setTotalItems(result.total);
      setCurrentPage(result.page);
    } catch {
      if (requestId.current !== currentRequest) return;
      setItems([]);
      setLoadError(true);
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [numericPatientId, numericVisitId]);

  useEffect(() => {
    void reload();
    return () => { requestId.current += 1; };
  }, [reload, retryKey]);

  useEffect(() => () => {
    if (preview?.url) URL.revokeObjectURL(preview.url);
  }, [preview?.url]);

  useEffect(() => {
    if (!preview) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    previewCloseRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPreview(null);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousFocus?.focus();
    };
  }, [preview]);

  const showActionError = (error: unknown) => {
    setSuccessMessage(null);
    if (errorStatus(error) === 403) {
      setActionError(t('dental.dental_pa_permission_denied'));
      return;
    }
    setActionError(t('dental.dental_pa_action_failed'));
  };

  const loadMore = async () => {
    if (!numericPatientId || !numericVisitId || loadingMore) return;
    const nextPage = currentPage + 1;
    const currentRequest = ++requestId.current;
    setLoadingMore(true);
    setActionError(null);
    try {
      const result = await listDentalMedia(numericPatientId, numericVisitId, nextPage);
      if (requestId.current !== currentRequest) return;
      setItems((current) => {
        const existingIds = new Set(current.map((item) => item.id));
        return [...current, ...result.items.filter((item) => !existingIds.has(item.id))];
      });
      setTotalItems(result.total);
      setCurrentPage(result.page);
    } catch (error: unknown) {
      if (requestId.current === currentRequest) showActionError(error);
    } finally {
      if (requestId.current === currentRequest) setLoadingMore(false);
    }
  };

  const handleFileChange = (file?: File) => {
    setActionError(null);
    setSuccessMessage(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }
    const extension = file.name.split('.').pop()?.toLowerCase();
    const supported = ['jpg', 'jpeg', 'png', 'pdf'].includes(extension || '') &&
      ['image/jpeg', 'image/png', 'application/pdf', 'application/octet-stream'].includes(file.type || 'application/octet-stream');
    if (!supported) {
      setSelectedFile(null);
      setActionError(t('dental.dental_pa_unsupported_file'));
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }
    setSelectedFile(file);
    setCategory(extension === 'pdf' ? 'xray' : 'photo');
  };

  const submitUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!numericPatientId || !numericVisitId || !selectedFile) return;
    const extension = selectedFile.name.split('.').pop()?.toLowerCase();
    if (extension === 'pdf' && category !== 'xray') {
      setActionError(t('dental.dental_pa_pdf_xray_only'));
      return;
    }
    setUploading(true);
    setActionError(null);
    setSuccessMessage(null);
    try {
      await uploadDentalMedia(numericPatientId, numericVisitId, category, selectedFile, {
        title: uploadTitle.trim() || null,
        description: uploadDescription.trim() || null,
        tooth: uploadTooth.trim() || null,
        capture_date: uploadDate || null,
      });
      setSelectedFile(null);
      setUploadTitle('');
      setUploadDescription('');
      setUploadTooth('');
      setUploadDate('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      setSuccessMessage(t('dental.dental_pa_upload_success'));
      await reload();
    } catch (error: unknown) {
      showActionError(error);
    } finally {
      setUploading(false);
    }
  };

  const saveMetadata = async (item: DentalMediaItem) => {
    if (!editDraft) return;
    if (item.mime_type === 'application/pdf' && editDraft.category !== 'xray') {
      setActionError(t('dental.dental_pa_pdf_xray_only'));
      return;
    }
    setSavingId(item.id);
    setActionError(null);
    setSuccessMessage(null);
    const metadata: DentalMediaMetadata = {
      title: editDraft.title.trim() || null,
      description: editDraft.description.trim() || null,
      category: editDraft.category,
      tooth: editDraft.tooth.trim() || null,
      capture_date: editDraft.capture_date || null,
    };
    try {
      await updateDentalMedia(item.id, metadata);
      setEditingId(null);
      setEditDraft(null);
      setSuccessMessage(t('dental.dental_pa_metadata_success'));
      await reload();
    } catch (error: unknown) {
      showActionError(error);
    } finally {
      setSavingId(null);
    }
  };

  const deleteItem = async (item: DentalMediaItem) => {
    setDeletingId(item.id);
    setActionError(null);
    setSuccessMessage(null);
    try {
      await deleteDentalMedia(item.id);
      setConfirmDeleteId(null);
      setSuccessMessage(t('dental.dental_pa_delete_success'));
      await reload();
    } catch (error: unknown) {
      showActionError(error);
    } finally {
      setDeletingId(null);
    }
  };

  const openPreview = async (item: DentalMediaItem) => {
    if (!numericVisitId) return;
    setPreviewingId(item.id);
    setActionError(null);
    try {
      const blob = await loadDentalMediaContent(item.id, numericVisitId);
      const url = URL.createObjectURL(blob);
      setPreview({ item, url });
    } catch (error: unknown) {
      showActionError(error);
    } finally {
      setPreviewingId(null);
    }
  };

  const title = t('dental.dental_pa_title', { name: patientName || t('dental.dental_panel_patient_default') });
  const dialog = presentation === 'dialog';

  const content = (
    <div className="dental-flex-col dental-gap-16">
      <div className="dental-flex-between-16">
        <h2 id={dialog ? 'dental-photo-archive-title' : undefined} className="dental-text-primary">{title}</h2>
        {dialog && onClose && <Button variant="outline" onClick={onClose}>{t('dental.dental_pa_aria_close')}</Button>}
      </div>

      {(!numericPatientId || !numericVisitId) && (
        <Card padding="large">
          <div className="dental-flex-col dental-gap-12">
            <p className="dental-text-primary">{numericPatientId ? t('dental.dental_pa_need_visit') : t('dental.dental_pa_no_patient')}</p>
            <div className="dental-flex dental-gap-8">
              {!numericPatientId && onGoToPatients && <Button variant="outline" onClick={onGoToPatients}>{t('dental.dental_dpt_title')}</Button>}
              {numericPatientId && onGoToQueue && <Button variant="outline" onClick={onGoToQueue}>{t('dental.dental_dpt_go_queue')}</Button>}
            </div>
          </div>
        </Card>
      )}

      {numericPatientId && numericVisitId && (
        <>
          <Card padding="large">
            <form className="dental-flex-col dental-gap-12" onSubmit={submitUpload}>
              <h3 className="dental-text-primary">{t('dental.dental_pa_upload_heading')}</h3>
              <label className="dental-flex-col dental-gap-8">
                <span className="dental-text-secondary">{t('dental.dental_pa_file_label')}</span>
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
                  aria-label={t('dental.dental_pa_file_label')}
                  onChange={(event) => handleFileChange(event.target.files?.[0])}
                />
              </label>
              <div className="dental-flex-col dental-gap-12">
                <label className="dental-flex-col dental-gap-8">
                  <span className="dental-text-secondary">{t('dental.dental_pa_category_label')}</span>
                  <Select
                    aria-label={t('dental.dental_pa_category_label')}
                    value={category}
                    onValueChange={(value) => setCategory(value as DentalMediaCategory)}
                    options={[
                      { value: 'photo', label: t('dental.dental_pa_cat_photo') },
                      { value: 'xray', label: t('dental.dental_pa_cat_radiograph') },
                    ]}
                  />
                </label>
                <Input aria-label={t('dental.dental_pa_title_label')} placeholder={t('dental.dental_pa_title_label')} value={uploadTitle} onChange={(event) => setUploadTitle(event.target.value)} maxLength={255} />
                <Input aria-label={t('dental.dental_pa_description_label')} placeholder={t('dental.dental_pa_description_label')} value={uploadDescription} onChange={(event) => setUploadDescription(event.target.value)} maxLength={2000} />
                <div className="dental-flex dental-gap-12">
                  <Input aria-label={t('dental.dental_pa_tooth_input_label')} placeholder={t('dental.dental_pa_tooth_input_label')} value={uploadTooth} onChange={(event) => setUploadTooth(event.target.value)} maxLength={16} />
                  <Input type="date" aria-label={t('dental.dental_pa_capture_date_label')} value={uploadDate} onChange={(event) => setUploadDate(event.target.value)} />
                </div>
              </div>
              <p className="dental-text-desc dental-text-secondary">{t('dental.dental_pa_supported_formats')}</p>
              <Button type="submit" variant="primary" disabled={!selectedFile || uploading} loading={uploading}>
                {uploading ? t('dental.dental_pa_uploading') : t('dental.dental_pa_btn_upload')}
              </Button>
            </form>
          </Card>

          {actionError && <p role="alert" className="dental-text-danger">{actionError}</p>}
          {successMessage && <p role="status" aria-live="polite" className="dental-text-success">{successMessage}</p>}

          <section aria-labelledby="dental-photo-list-title" className="dental-flex-col dental-gap-12">
            <h3 id="dental-photo-list-title" className="dental-text-primary">{t('dental.dental_pa_saved_heading')}</h3>
            {loading && <p role="status" aria-live="polite" className="dental-text-secondary">{t('dental.dental_pa_loading')}</p>}
            {loadError && (
              <Card padding="large" role="alert">
                <div className="dental-flex-col dental-gap-12">
                  <p className="dental-text-primary">{t('dental.dental_pa_load_failed')}</p>
                  <Button variant="outline" onClick={() => setRetryKey((value) => value + 1)}>{t('dental.dental_dpt_retry')}</Button>
                </div>
              </Card>
            )}
            {!loading && !loadError && items.length === 0 && (
              <Card padding="large"><p className="dental-text-secondary">{t('dental.dental_pa_empty_view_hint')}</p></Card>
            )}
            {!loading && items.map((item) => {
              const isEditing = editingId === item.id && editDraft;
              return (
                <Card key={item.id} padding="default">
                  <div className="dental-flex-col dental-gap-12">
                    {isEditing ? (
                      <div className="dental-flex-col dental-gap-12">
                        <label className="dental-flex-col dental-gap-8">
                          <span className="dental-text-secondary">{t('dental.dental_pa_category_label')}</span>
                          <Select
                            aria-label={t('dental.dental_pa_category_label')}
                            value={editDraft.category}
                            onValueChange={(value) => setEditDraft({ ...editDraft, category: value as DentalMediaCategory })}
                            options={item.mime_type === 'application/pdf'
                              ? [{ value: 'xray', label: t('dental.dental_pa_cat_radiograph') }]
                              : [
                                { value: 'photo', label: t('dental.dental_pa_cat_photo') },
                                { value: 'xray', label: t('dental.dental_pa_cat_radiograph') },
                              ]}
                          />
                        </label>
                        <Input aria-label={t('dental.dental_pa_title_label')} value={editDraft.title} onChange={(event) => setEditDraft({ ...editDraft, title: event.target.value })} maxLength={255} />
                        <Input aria-label={t('dental.dental_pa_description_label')} value={editDraft.description} onChange={(event) => setEditDraft({ ...editDraft, description: event.target.value })} maxLength={2000} />
                        <div className="dental-flex dental-gap-12">
                          <Input aria-label={t('dental.dental_pa_tooth_input_label')} value={editDraft.tooth} onChange={(event) => setEditDraft({ ...editDraft, tooth: event.target.value })} maxLength={16} />
                          <Input type="date" aria-label={t('dental.dental_pa_capture_date_label')} value={editDraft.capture_date} onChange={(event) => setEditDraft({ ...editDraft, capture_date: event.target.value })} />
                        </div>
                        <div className="dental-flex dental-gap-8">
                          <Button variant="primary" onClick={() => void saveMetadata(item)} disabled={savingId === item.id} loading={savingId === item.id}>{t('dental.dental_pa_btn_save')}</Button>
                          <Button variant="outline" onClick={() => { setEditingId(null); setEditDraft(null); }}>{t('dental.dental_pa_btn_cancel')}</Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="dental-flex-between-16">
                          <div>
                            <p className="dental-text-primary dental-font-medium">{item.title || t(item.category === 'xray' ? 'dental.dental_pa_cat_radiograph' : 'dental.dental_pa_cat_photo')}</p>
                            <p className="dental-text-desc dental-text-secondary">
                              {t(item.category === 'xray' ? 'dental.dental_pa_cat_radiograph' : 'dental.dental_pa_cat_photo')} · {item.mime_type.toUpperCase()}
                              {item.capture_date ? ` · ${item.capture_date}` : ''}
                              {item.tooth ? ` · ${t('dental.dental_pa_tooth_input_label')}: ${item.tooth}` : ''}
                            </p>
                            {item.description && <p className="dental-text-secondary">{item.description}</p>}
                          </div>
                          <Button variant="outline" onClick={() => void openPreview(item)} disabled={previewingId === item.id} loading={previewingId === item.id}>
                            {t('dental.dental_pa_title_view')}
                          </Button>
                        </div>
                        <div className="dental-flex dental-gap-8">
                          <Button variant="outline" onClick={() => { setEditingId(item.id); setEditDraft(newMetadataDraft(item)); setActionError(null); }}>{t('dental.dental_pa_btn_edit')}</Button>
                          {confirmDeleteId === item.id ? (
                            <>
                              <span className="dental-text-secondary">{t('dental.dental_pa_confirm_delete')}</span>
                              <Button variant="danger" onClick={() => void deleteItem(item)} disabled={deletingId === item.id} loading={deletingId === item.id}>{t('dental.dental_pa_title_delete')}</Button>
                              <Button variant="outline" onClick={() => setConfirmDeleteId(null)}>{t('dental.dental_pa_btn_cancel')}</Button>
                            </>
                          ) : (
                            <Button variant="outline" onClick={() => { setConfirmDeleteId(item.id); setActionError(null); }}>{t('dental.dental_pa_title_delete')}</Button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </Card>
              );
            })}
            {!loading && !loadError && items.length < totalItems && (
              <Button variant="outline" onClick={() => void loadMore()} disabled={loadingMore} loading={loadingMore}>
                {t('dental.dental_pa_load_more')}
              </Button>
            )}
          </section>
        </>
      )}

      {preview && (
        <div className="dental-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="dental-photo-preview-title">
          <section className="dental-modal-card-xl dental-flex-col dental-gap-12">
            <div className="dental-flex-between-16">
              <h3 id="dental-photo-preview-title" className="dental-text-primary">{preview.item.title || t('dental.dental_pa_title_view')}</h3>
              <Button ref={previewCloseRef} variant="outline" onClick={() => setPreview(null)}>{t('dental.dental_pa_aria_close_viewer')}</Button>
            </div>
            {preview.item.mime_type === 'application/pdf' ? (
              <a href={preview.url} target="_blank" rel="noreferrer">{t('dental.dental_pa_open_pdf')}</a>
            ) : (
              <img src={preview.url} alt={preview.item.title || t('dental.dental_pa_title_view')} className="dental-photo-preview" />
            )}
          </section>
        </div>
      )}
    </div>
  );

  if (!dialog) return content;
  return (
    <div className="dental-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="dental-photo-archive-title">
      <section className="dental-modal-card-xl" aria-label={title}>{content}</section>
    </div>
  );
};

export default PhotoArchive;
