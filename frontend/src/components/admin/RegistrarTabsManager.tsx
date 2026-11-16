import React, { useCallback, useEffect, useImperativeHandle, useRef, useState, useSyncExternalStore } from 'react';
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
import { getProfileFromStorage, subscribeAuth } from '../../stores/auth';

const QueueProfilesManager = React.lazy(() => import('./QueueProfilesManager'));

interface DraftTab extends RegistrarTabInput {
  target: ResolvedRegistrarTab;
}

interface CachedDraft {
  ownerId: string;
  baseConfig: AdminRegistrarTabsResponse;
  draft: DraftTab[];
}

// One owner-scoped draft per SPA lifetime. Staff labels never enter browser
// storage, and a different/unknown owner clears the prior owner's draft.
let cachedDraft: CachedDraft | null = null;

const draftOwnerId = (): string | null => {
  const profile = getProfileFromStorage();
  if (typeof profile?.id !== 'number' || !Number.isSafeInteger(profile.id) || profile.id <= 0) return null;
  const clinicId = profile.clinic_id;
  const clinicKey = typeof clinicId === 'string' || typeof clinicId === 'number' ? String(clinicId) : 'global';
  return `${clinicKey}:${profile.id}`;
};

const subscribeOwner = (listener: () => void) => subscribeAuth(() => listener());

export interface RegistrarTabsManagerHandle {
  discardDraft: () => void;
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

const RegistrarTabsManager = React.forwardRef<RegistrarTabsManagerHandle, RegistrarTabsManagerProps>(function RegistrarTabsManager(
  { theme = 'light', defaultOpenProfiles = false, onDirtyChange, onSavingChange },
  ref,
) {
  const { t, language } = useTranslation();
  const ownerId = useSyncExternalStore(subscribeOwner, draftOwnerId, () => null);
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
  const loadedOwner = useRef<string | null | undefined>(undefined);

  const load = useCallback(async (discard = false) => {
    const requestOwner = draftOwnerId();
    if (!requestOwner || cachedDraft?.ownerId !== requestOwner) cachedDraft = null;
    if (discard && cachedDraft?.ownerId === requestOwner) cachedDraft = null;
    const restore = !discard && requestOwner ? cachedDraft : null;
    const generation = ++requestGeneration.current;
    setLoading(true);
    setLoadError(false);
    try {
      const response = await getAdminRegistrarTabs();
      if (requestGeneration.current !== generation || draftOwnerId() !== requestOwner) return;
      loadedOwner.current = requestOwner;
      if (restore && restore.ownerId === requestOwner) {
        // Resolve display metadata from this authorized read, but keep the
        // original base/version so a concurrent save remains a real conflict.
        const targets = new Map([...response.options, ...response.tabs].map((tab) => [registrarTabIdentity(tab), tab]));
        setConfig({ ...restore.baseConfig, options: response.options, profile_filters: response.profile_filters });
        setDraft(restore.draft.map((row) => ({
          ...row,
          target: targets.get(registrarTabIdentity(row)) || { ...row.target, available: false },
        })));
        setSaveError(response.version === restore.baseConfig.version ? null : 'conflict');
      } else {
        setConfig(response);
        setDraft(response.tabs.map(toDraft));
        setSaveError(null);
      }
      setSelectedTarget('');
      setSaved(false);
    } catch {
      if (requestGeneration.current === generation) setLoadError(true);
    } finally {
      if (requestGeneration.current === generation) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadedOwner.current = undefined;
    setConfig(null);
    setDraft([]);
    setSaving(false);
    savingRef.current = false;
    void load();
    return () => { requestGeneration.current += 1; };
  }, [load, ownerId]);

  useEffect(() => {
    if (defaultOpenProfiles) setProfilesOpen(true);
  }, [defaultOpenProfiles]);

  const labelFor = (target: ResolvedRegistrarTab): string =>
    language === 'ru' ? target.title_ru || target.title : target.title || target.title_ru || '';
  const currentConfig = loadedOwner.current === ownerId ? config : null;
  const inputs = draft.map(toInput);
  const dirty = currentConfig !== null
    && JSON.stringify(inputs) !== JSON.stringify(currentConfig.tabs.map(toDraft).map(toInput));
  useEffect(() => {
    if (!ownerId) { cachedDraft = null; return; }
    if (!currentConfig || loading) return;
    if (dirty) cachedDraft = { ownerId, baseConfig: currentConfig, draft };
    else if (cachedDraft?.ownerId === ownerId) cachedDraft = null;
  }, [currentConfig, dirty, draft, loading, ownerId]);
  const discardDraft = useCallback(() => {
    if (cachedDraft?.ownerId === ownerId) cachedDraft = null;
    if (currentConfig) setDraft(currentConfig.tabs.map(toDraft));
    setSaveError(null);
    setSaved(false);
  }, [currentConfig, ownerId]);
  useImperativeHandle(ref, () => ({ discardDraft }), [discardDraft]);
  useBeforeUnload(dirty || saving, t('registrarPanel.rt_unsaved_warning'));
  useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => { onSavingChange?.(saving); }, [saving, onSavingChange]);
  useEffect(() => () => { onDirtyChange?.(false); onSavingChange?.(false); }, [onDirtyChange, onSavingChange]);
  const usedTargets = new Set(draft.map(registrarTabIdentity));
  const availableOptions = currentConfig?.options.filter((target) => target.available && !usedTargets.has(registrarTabIdentity(target))) || [];

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
    if (!currentConfig || savingRef.current || loading || draftOwnerId() !== ownerId) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    const generation = ++requestGeneration.current;
    try {
      const response = await saveRegistrarTabs({
        expected_version: currentConfig.version,
        tabs: draft.map(toInput),
        reason: 'configure_registrar_tabs',
      });
      if (requestGeneration.current !== generation || draftOwnerId() !== ownerId) return;
      if (cachedDraft?.ownerId === ownerId) cachedDraft = null;
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
      if (requestGeneration.current === generation) {
        savingRef.current = false;
        setSaving(false);
      }
    }
  };

  return <div>
    <section className="admin-qp-main-card" aria-labelledby="registrar-tabs-title" aria-busy={loading || saving}>
      <div className="admin-qp-header">
        <h2 id="registrar-tabs-title" className="admin-qp-title">{t('registrarPanel.rt_title')}</h2>
        <div className="admin-qp-toolbar">
          <Button variant="secondary" disabled={saving || loading} onClick={() => { discardDraft(); void load(true); }}>
            {t(dirty ? 'registrarPanel.rt_discard_reload' : 'registrarPanel.rt_reload')}
          </Button>
          <Button disabled={!currentConfig || saving || loading || (currentConfig.mode === 'configured' && !dirty)} loading={saving} onClick={() => { void save(); }}>
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
      {currentConfig && <>
        <p>{t(currentConfig.mode === 'legacy' ? 'registrarPanel.rt_legacy_notice' : 'registrarPanel.rt_configured_notice')}</p>
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
              const sourceTarget = currentConfig.options.find((target) => registrarTabIdentity(target) === identity) || row.target;
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
});

export default RegistrarTabsManager;
