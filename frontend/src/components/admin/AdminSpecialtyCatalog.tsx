/**
 * Admin — Medical Specialty Catalog management.
 *
 * Owns the medical_specialties runtime SSOT: create (canonical code +
 * titles), edit titles/active/sort_order, deactivate. Deletion is offered
 * only when no doctor references the code (backend enforces 409).
 *
 * Consumption contract: codes created here immediately become available in
 * the Users → Add User onboarding specialty select (via
 * /admin/doctors/specialty-vocabulary) — no frontend deploy needed.
 */
import { useTranslation } from '../../i18n/useTranslation';
import { useCallback, useEffect, useState } from 'react';
import { Plus, RefreshCw, Save, Stethoscope, Trash2 } from 'lucide-react';
import { api } from '../../api/client';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import { Badge, Button, Card, Input, AppEmpty } from '../ui/macos';

interface CatalogRow {
  code: string;
  title_ru: string;
  title_uz: string | null;
  title_en: string | null;
  active: boolean;
  sort_order: number;
}

const AdminSpecialtyCatalog = () => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingCode, setSavingCode] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Partial<CatalogRow>>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/admin/doctors-catalog');
      setRows(response.data);
    } catch (loadError) {
      logger.error('Failed to load specialty catalog:', loadError);
      setError(String(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setDraft = (code: string, patch: Partial<CatalogRow>) =>
    setDrafts((prev) => ({ ...prev, [code]: { ...prev[code], ...patch } }));

  const saveRow = async (row: CatalogRow) => {
    const patch = drafts[row.code];
    if (!patch) return;
    setSavingCode(row.code);
    try {
      const response = await api.put(`/admin/doctors-catalog/${row.code}`, patch);
      setRows((prev) => prev.map((r) => (r.code === row.code ? response.data : r)));
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[row.code];
        return next;
      });
      notify.success(t('admin2.spec_saved'));
    } catch (saveError) {
      logger.error('Failed to save specialty:', saveError);
      notify.error(t('admin2.spec_save_failed'));
    } finally {
      setSavingCode(null);
    }
  };

  const toggleActive = async (row: CatalogRow) => {
    setSavingCode(row.code);
    try {
      const response = await api.put(`/admin/doctors-catalog/${row.code}`, {
        active: !row.active,
      });
      setRows((prev) => prev.map((r) => (r.code === row.code ? response.data : r)));
      notify.success(t('admin2.spec_updated'));
    } catch (toggleError) {
      logger.error('Failed to toggle specialty:', toggleError);
      notify.error(t('admin2.spec_save_failed'));
    } finally {
      setSavingCode(null);
    }
  };

  const removeRow = async (row: CatalogRow) => {
    if (!window.confirm(t('admin2.spec_delete_confirm', { code: row.code }))) return;
    setSavingCode(row.code);
    try {
      await api.delete(`/admin/doctors-catalog/${row.code}`);
      setRows((prev) => prev.filter((r) => r.code !== row.code));
      notify.success(t('admin2.spec_deleted'));
    } catch (removeError) {
      logger.error('Failed to delete specialty:', removeError);
      notify.error(t('admin2.spec_delete_failed'));
    } finally {
      setSavingCode(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card variant="default" shadow="none" className="admin-patients-header-card">
        <div className="admin-patients-header-row">
          <div>
            <h2 className="admin-title-20">{t('admin2.spec_catalog_title')}</h2>
            <p className="admin-patients-subtitle">{t('admin2.spec_catalog_subtitle')}</p>
          </div>
          <Button
            variant="secondary"
            startIcon={<RefreshCw size={16} />}
            onClick={load}
            disabled={loading}
          >
            {t('admin2.ad_refresh')}
          </Button>
        </div>
      </Card>

      {loading ? (
        <div className="admin-p-24" aria-busy="true">{t('admin2.spec_loading')}</div>
      ) : error ? (
        <div className="admin-field-error" role="alert">{error}</div>
      ) : rows.length === 0 ? (
        <AppEmpty icon={Stethoscope} title={t('admin2.spec_empty_title')} description={t('admin2.spec_empty_desc')} />
      ) : (
        <Card variant="default" shadow="none">
          <div className="admin-table-wrapper">
            <table className="admin-w-100pct-bc-collapse" aria-label={t('admin2.spec_table_aria')}>
              <thead>
                <tr className="admin-patients-thead-row">
                  <th className="admin-patients-th">{t('admin2.spec_col_code')}</th>
                  <th className="admin-patients-th">{t('admin2.spec_col_title_ru')}</th>
                  <th className="admin-patients-th">{t('admin2.spec_col_title_en')}</th>
                  <th className="admin-patients-th">{t('admin2.spec_col_status')}</th>
                  <th className="admin-patients-th">{t('admin2.ad_th_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const draft = drafts[row.code] ?? {};
                  const dirty = Boolean(draft.title_ru || draft.title_en);
                  return (
                    <tr key={row.code} className="admin-patients-tbody-row">
                      <td className="admin-p-12-16">
                        <Badge variant={row.active ? 'success' : 'warning'}>{row.code}</Badge>
                      </td>
                      <td className="admin-p-12-16">
                        <Input
                          value={draft.title_ru ?? row.title_ru}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setDraft(row.code, { title_ru: e.target.value })
                          }
                        />
                      </td>
                      <td className="admin-p-12-16">
                        <Input
                          value={draft.title_en ?? row.title_en ?? ''}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setDraft(row.code, { title_en: e.target.value })
                          }
                        />
                      </td>
                      <td className="admin-p-12-16">
                        <Badge variant={row.active ? 'success' : 'warning'}>
                          {row.active ? t('admin2.ad_status_active') : t('admin2.ad_status_inactive')}
                        </Badge>
                      </td>
                      <td className="admin-p-12-16">
                        <div className="flex items-center justify-center gap-2">
                          <Button
                            size="small"
                            variant={dirty ? 'primary' : 'secondary'}
                            startIcon={<Save size={14} />}
                            onClick={() => saveRow(row)}
                            disabled={!dirty || savingCode === row.code}
                          >
                            {t('admin2.umdl_btn_save_changes')}
                          </Button>
                          <Button
                            size="small"
                            variant={row.active ? 'secondary' : 'primary'}
                            onClick={() => toggleActive(row)}
                            disabled={savingCode === row.code}
                          >
                            {row.active ? t('admin2.spec_deactivate') : t('admin2.spec_activate')}
                          </Button>
                          <Button
                            size="small"
                            variant="danger"
                            startIcon={<Trash2 size={14} />}
                            onClick={() => removeRow(row)}
                            disabled={savingCode === row.code}
                            aria-label={t('admin2.ad_delete_aria', { code: row.code })}
                          >
                            <Trash2 size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};

export default AdminSpecialtyCatalog;
