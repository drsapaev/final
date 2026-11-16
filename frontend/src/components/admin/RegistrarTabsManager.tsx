import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowUp, Trash2 } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';
import {
  getAdminRegistrarTabs,
  registrarTabIdentity,
  saveRegistrarTabs,
  type AdminRegistrarTabsResponse,
  type RegistrarTabInput,
  type ResolvedRegistrarTab,
} from '../../api/registrarTabs';
import { Button, Checkbox, Input, Select, Skeleton } from '../ui/macos';
import { useBeforeUnload } from '../../hooks/useNavigationGuard';

const QueueProfilesManager = React.lazy(() => import('./QueueProfilesManager'));

interface DraftTab extends RegistrarTabInput {
  target: ResolvedRegistrarTab;
}

const toDraft = (tab: ResolvedRegistrarTab): DraftTab => ({
  target_kind: tab.target_kind,
  target_id: tab.target_id,
  title: tab.custom_title,
  visible: tab.visible,
  target: tab,
});

const toInput = ({ target_kind, target_id, title, visible }: DraftTab): RegistrarTabInput => ({
  target_kind,
  target_id,
  title: title?.trim() || null,
  visible,
});

interface RegistrarTabsManagerProps {
  theme?: 'light' | 'dark';
  defaultOpenProfiles?: boolean;
  onDirtyChange?: (dirty: boolean) => void;
  onSavingChange?: (saving: boolean) => void;
}

export default function RegistrarTabsManager({ theme = 'light', defaultOpenProfiles = false, onDirtyChange, onSavingChange }: RegistrarTabsManagerProps) {
  const { t, language } = useTranslation();
  const [config, setConfig] = useState<AdminRegistrarTabsResponse | null>(null);
  const [draft, setDraft] = useState<DraftTab[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<'conflict' | 'error' | null>(null);
  const [saved, setSaved] = useState(false);
  const [selectedTarget, setSelectedTarget] = useState('');
  const [profilesOpen, setProfilesOpen] = useState(defaultOpenProfiles);
  const requestGeneration = useRef(0);
  const savingRef = useRef(false);

  const load = useCallback(async () => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    setLoadError(false);
    try {
      const response = await getAdminRegistrarTabs();
      if (requestGeneration.current !== generation) return;
      setConfig(response);
      setDraft(response.tabs.map(toDraft));
      setSelectedTarget('');
      setSaveError(null);
      setSaved(false);
    } catch {
      if (requestGeneration.current === generation) setLoadError(true);
    } finally {
      if (requestGeneration.current === generation) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    return () => { requestGeneration.current += 1; };
  }, [load]);

  useEffect(() => {
    if (defaultOpenProfiles) setProfilesOpen(true);
  }, [defaultOpenProfiles]);

  const labelFor = (target: ResolvedRegistrarTab): string =>
    language === 'ru' ? target.title_ru || target.title : target.title || target.title_ru || '';
  const inputs = draft.map(toInput);
  const dirty = config !== null
    && JSON.stringify(inputs) !== JSON.stringify(config.tabs.map(toDraft).map(toInput));
  useBeforeUnload(dirty || saving, t('registrarPanel.rt_unsaved_warning'));
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => { onSavingChange?.(saving); }, [saving, onSavingChange]);
  useEffect(() => () => { onDirtyChange?.(false); onSavingChange?.(false); }, [onDirtyChange, onSavingChange]);
  const usedTargets = new Set(draft.map(registrarTabIdentity));
  const availableOptions = config?.options.filter((target) => target.available && !usedTargets.has(registrarTabIdentity(target))) || [];

  const updateDraft = (next: DraftTab[]) => {
    setDraft(next);
    setSaved(false);
  };

  const move = (index: number, offset: number) => {
    const next = [...draft];
    const destination = index + offset;
    if (destination < 0 || destination >= next.length) return;
    [next[index], next[destination]] = [next[destination], next[index]];
    updateDraft(next);
  };

  const add = () => {
    const target = availableOptions.find((option) => registrarTabIdentity(option) === selectedTarget);
    if (!target) return;
    updateDraft([...draft, { ...toDraft(target), title: null, visible: true }]);
    setSelectedTarget('');
  };

  const save = async () => {
    if (!config || savingRef.current || loading) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    const generation = ++requestGeneration.current;
    try {
      const response = await saveRegistrarTabs({
        expected_version: config.version,
        tabs: draft.map(toInput),
        reason: 'configure_registrar_tabs',
      });
      if (requestGeneration.current !== generation) return;
      setConfig(response);
      setDraft(response.tabs.map(toDraft));
      setLoadError(false);
      setSaved(true);
      window.dispatchEvent(new CustomEvent('registrar-tabs:updated'));
    } catch (error) {
      if (requestGeneration.current !== generation) return;
      const status = (error as { response?: { status?: number } })?.response?.status;
      setSaveError(status === 409 ? 'conflict' : 'error');
    } finally {
      savingRef.current = false;
      if (requestGeneration.current === generation) setSaving(false);
    }
  };

  return <div>
    <section className="admin-qp-main-card" aria-labelledby="registrar-tabs-title" aria-busy={loading || saving}>
      <div className="admin-qp-header">
        <h2 id="registrar-tabs-title" className="admin-qp-title">{t('registrarPanel.rt_title')}</h2>
        <div className="admin-qp-toolbar">
          <Button variant="secondary" disabled={saving || loading} onClick={() => { void load(); }}>
            {t(dirty ? 'registrarPanel.rt_discard_reload' : 'registrarPanel.rt_reload')}
          </Button>
          <Button disabled={!config || saving || loading || (config.mode === 'configured' && !dirty)} loading={saving} onClick={() => { void save(); }}>
            {t('registrarPanel.rt_save')}
          </Button>
        </div>
      </div>
      <p>{t('registrarPanel.rt_description')}</p>
      <p>{t('registrarPanel.rt_all_departments')}</p>
      {loading && <p role="status">{t('common.loading')}</p>}
      {loadError && <div role="alert">
        <p>{t('registrarPanel.rt_load_error')}</p>
        <Button variant="secondary" disabled={saving || loading} onClick={() => { void load(); }}>{t('registrarPanel.rt_retry')}</Button>
      </div>}
      {saveError && <p role="alert">{t(saveError === 'conflict' ? 'registrarPanel.rt_conflict' : 'registrarPanel.rt_save_error')}</p>}
      {saved && <p role="status">{t('registrarPanel.rt_saved')}</p>}
      {config && <>
        <p>{t(config.mode === 'legacy' ? 'registrarPanel.rt_legacy_notice' : 'registrarPanel.rt_configured_notice')}</p>
        {draft.length === 0 ? <p>{t('registrarPanel.rt_empty')}</p> : <div className="admin-overflow-x-auto">
          <table className="admin-qp-table" aria-label={t('registrarPanel.rt_title')}>
            <thead><tr>
              <th scope="col" className="admin-qp-th">{t('registrarPanel.rt_name')}</th>
              <th scope="col" className="admin-qp-th">{t('registrarPanel.rt_target')}</th>
              <th scope="col" className="admin-qp-th">{t('registrarPanel.rt_visible')}</th>
              <th scope="col" className="admin-qp-th">{t('registrarPanel.rt_actions')}</th>
            </tr></thead>
            <tbody>{draft.map((row, index) => {
              const identity = registrarTabIdentity(row);
              const sourceTarget = config.options.find((target) => registrarTabIdentity(target) === identity) || row.target;
              const name = labelFor(sourceTarget);
              const targetType = t(row.target_kind === 'doctor' ? 'registrarPanel.rt_doctor' : 'registrarPanel.rt_profile');
              const controlName = `${name} — ${targetType} · #${row.target_id}`;
              return <tr key={identity}>
                <td className="admin-qp-td">
                  <Input value={row.title ?? name} maxLength={100} aria-label={t('registrarPanel.rt_name_label', { name: controlName })}
                    disabled={saving || loading} onChange={(event) => updateDraft(draft.map((item, itemIndex) => itemIndex === index ? { ...item, title: event.target.value } : item))} />
                </td>
                <td className="admin-qp-td">
                  {controlName}
                  {!row.target.available && <p>{t('registrarPanel.rt_unavailable')}</p>}
                </td>
                <td className="admin-qp-td">
                  <Checkbox checked={row.visible} disabled={saving || loading}
                    aria-label={t('registrarPanel.rt_visible_label', { name: controlName })}
                    onChange={(visible) => updateDraft(draft.map((item, itemIndex) => itemIndex === index ? { ...item, visible } : item))} />
                </td>
                <td className="admin-qp-td"><div className="admin-qp-toolbar">
                  <Button variant="ghost" disabled={saving || loading || index === 0} aria-label={t('registrarPanel.rt_move_up_label', { name: controlName })} onClick={() => move(index, -1)}><ArrowUp size={16} /></Button>
                  <Button variant="ghost" disabled={saving || loading || index === draft.length - 1} aria-label={t('registrarPanel.rt_move_down_label', { name: controlName })} onClick={() => move(index, 1)}><ArrowDown size={16} /></Button>
                  <Button variant="ghost" disabled={saving || loading} aria-label={t('registrarPanel.rt_remove_label', { name: controlName })} onClick={() => updateDraft(draft.filter((_, itemIndex) => itemIndex !== index))}><Trash2 size={16} /></Button>
                </div></td>
              </tr>;
            })}</tbody>
          </table>
        </div>}
        <div className="admin-qp-toolbar">
          <Select value={selectedTarget} aria-label={t('registrarPanel.rt_add_target')} placeholder={t('registrarPanel.rt_add_target')}
            options={availableOptions.map((target) => ({ value: registrarTabIdentity(target), label: `${labelFor(target)} · #${target.target_id} — ${t(target.target_kind === 'doctor' ? 'registrarPanel.rt_doctor' : 'registrarPanel.rt_profile')}` }))}
            disabled={saving || loading || availableOptions.length === 0} onValueChange={(value) => setSelectedTarget(String(value))} />
          <Button variant="secondary" disabled={!selectedTarget || saving || loading} onClick={add}>{t('registrarPanel.rt_add')}</Button>
        </div>
      </>}
    </section>
    <details open={profilesOpen} onToggle={(event) => setProfilesOpen(event.currentTarget.open)}>
      <summary>{t('registrarPanel.rt_profiles_details')}</summary>
      <p>{t('registrarPanel.rt_profiles_help')}</p>
      {profilesOpen && <React.Suspense fallback={<Skeleton className="admin-skeleton-h-384" />}>
        <QueueProfilesManager theme={theme} />
      </React.Suspense>}
    </details>
  </div>;
}
