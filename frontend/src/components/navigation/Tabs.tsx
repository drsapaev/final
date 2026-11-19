import React, { type CSSProperties, useCallback, useEffect, useId, useRef, useState } from 'react';
import { Heart, Activity, UserCheck, Smile, FlaskConical, Syringe, Calendar, Clock, AlertCircle,
  TrendingUp, Package, Stethoscope, TestTube, Scissors, FolderTree, Sparkles, Users } from 'lucide-react';
import { getRegistrarTabs } from '../../api/registrarTabs';
import logger from '../../utils/logger';
import './Tabs.css';
import { useTranslation } from '../../i18n/useTranslation';
import type { Doctor } from '../../types/domain/clinic';

const iconMap = { Heart, Activity, UserCheck, Smile, FlaskConical, Syringe, Calendar, Package,
  Stethoscope, TestTube, Scissors, FolderTree, Sparkles, Sparkle: Sparkles, Users };
const defaultTabColor = 'var(--mac-accent, currentColor)';
const toGradient = (color: string) =>
  `linear-gradient(135deg, ${color}, color-mix(in srgb, ${color}, white 14%))`;

// Shared identity contract with the worklist tabpanel and legacy deep links.
export const tabButtonIdFor = (tabKey: string): string => `${encodeURIComponent(tabKey)}-tab`;
export const doctorTabButtonIdFor = (doctorId: number): string => `registrar-doctor-id-${doctorId}-tab`;
type IconComponent = React.ComponentType<{ size?: number | string; className?: string }>;
interface TabItem {
  target_kind: 'profile' | 'doctor'; target_id: number; key: string; label: string;
  queue_tags: string[]; icon: IconComponent; color: string; gradient: string;
}
interface TabsProps {
  activeTab?: string | null; activeDoctorId?: number | null;
  onTabChange?: (tab: string | null) => void;
  onDoctorChange?: (doctorId: number | null) => void;
  onProfilesLoaded?: (profiles: unknown[]) => void;
  departmentStats?: Record<string, unknown>; doctorStats?: Record<string, unknown>;
  doctorCountLabel?: string;
  // Compatibility catalogs never append tabs to the configured strip.
  doctors?: Doctor[]; language?: string; theme?: string; dynamicDepartments?: unknown[];
}

const Tabs = ({ activeTab, activeDoctorId = null, onTabChange, onDoctorChange, onProfilesLoaded,
  departmentStats = {}, doctorStats = {}, doctorCountLabel, language = 'ru' }: TabsProps) => {
  const { t } = useTranslation();
  const [tabs, setTabs] = useState<TabItem[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [indicatorStyle, setIndicatorStyle] = useState<CSSProperties>({ opacity: 0 });
  const tabsRef = useRef<HTMLDivElement | null>(null);
  const generation = useRef(0);
  const mounted = useRef(false);
  const uid = useId();

  const loadTabs = useCallback(async () => {
    const request = ++generation.current;
    setLoading(true);
    try {
      const response = await getRegistrarTabs();
      if (!mounted.current || request !== generation.current) return;
      const configured = response.tabs.filter((tab) => tab.visible && tab.available);
      const labels = configured.map((tab) =>
        language === 'uz' ? tab.title || tab.title_ru || '' : tab.title_ru || tab.title);
      const counts = new Map<string, number>();
      labels.forEach((label) => {
        const key = label.trim().toLocaleLowerCase();
        counts.set(key, (counts.get(key) || 0) + 1);
      });
      const resolved: TabItem[] = configured.map((tab, index) => {
        const color = tab.color || defaultTabColor;
        const label = labels[index];
        return {
          target_kind: tab.target_kind, target_id: tab.target_id,
          key: tab.target_kind === 'profile' ? tab.profile_key! : `doctor:${tab.target_id}`,
          label: (counts.get(label.trim().toLocaleLowerCase()) || 0) > 1
            ? `${label} · ${tab.target_kind === 'doctor' ? `#${tab.target_id}` : tab.profile_key}` : label,
          queue_tags: tab.queue_tags,
          icon: iconMap[tab.icon as keyof typeof iconMap] || (tab.target_kind === 'doctor' ? UserCheck : Package),
          color, gradient: toGradient(color),
        };
      });
      setTabs(resolved);
      setHasLoaded(true);
      setLoadError(false);
      // Metadata includes hidden profiles for compatible historical deep links.
      // It does not create additional visible tabs.
      onProfilesLoaded?.(response.profile_filters.map((profile) => ({
        ...profile,
        label: language === 'uz' ? profile.title || profile.title_ru || '' : profile.title_ru || profile.title,
      })));
    } catch {
      if (mounted.current && request === generation.current) {
        setLoadError(true);
        logger.warn('Registrar tabs could not be refreshed');
      }
    } finally {
      if (mounted.current && request === generation.current) setLoading(false);
    }
  }, [language, onProfilesLoaded]);

  useEffect(() => {
    mounted.current = true;
    void loadTabs();
    return () => { mounted.current = false; generation.current += 1; };
  }, [loadTabs]);

  useEffect(() => {
    const refresh = () => { void loadTabs(); };
    let lastFocusRefreshAt = 0;
    const refreshIfDue = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastFocusRefreshAt < 5000) return;
      lastFocusRefreshAt = now;
      refresh();
    };
    const visibilityChange = () => {
      if (document.visibilityState === 'visible') refreshIfDue();
    };
    const updates = ['registrar-tabs:updated', 'queue-profiles:updated', 'departments:updated'];
    updates.forEach((event) => window.addEventListener(event, refresh));
    document.addEventListener('visibilitychange', visibilityChange);
    const returns = ['focus', 'online', 'registrar:session-refresh'];
    returns.forEach((event) => window.addEventListener(event, refreshIfDue));
    return () => {
      updates.forEach((event) => window.removeEventListener(event, refresh));
      document.removeEventListener('visibilitychange', visibilityChange);
      returns.forEach((event) => window.removeEventListener(event, refreshIfDue));
    };
  }, [loadTabs]);

  const isSelected = (tab: TabItem) => tab.target_kind === 'doctor'
    ? activeDoctorId === tab.target_id : activeDoctorId == null && activeTab === tab.key;
  const selected = tabs.find(isSelected);
  const isOverview = !activeTab && activeDoctorId == null;
  const hiddenFilter = hasLoaded && !selected && !isOverview;
  useEffect(() => {
    const button = tabsRef.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]');
    if (!button || !tabsRef.current) { setIndicatorStyle({ opacity: 0 }); return; }
    const rect = button.getBoundingClientRect();
    const container = tabsRef.current.getBoundingClientRect();
    setIndicatorStyle({ left: rect.left - container.left, width: rect.width, opacity: 1 });
  }, [activeTab, activeDoctorId, tabs]);

  const statsFor = (tab: TabItem) => {
    const doctor = tab.target_kind === 'doctor';
    const stats = ((doctor ? doctorStats : departmentStats)[doctor ? String(tab.target_id) : tab.key] || {}) as Record<string, unknown>;
    return { todayCount: Number(stats.todayCount ?? 0), hasActiveQueue: Boolean(stats.hasActiveQueue),
      hasPendingPayments: Boolean(stats.hasPendingPayments) };
  };
  const countLabel = (tab: TabItem) => tab.target_kind === 'doctor' && doctorCountLabel
    ? doctorCountLabel : t('registrarPanel.today');
  const statusIdFor = (tab: TabItem) => `${uid}-status-${encodeURIComponent(tab.key)}`;
  const hasStatusFor = (tab: TabItem) => {
    const stats = statsFor(tab);
    return stats.hasActiveQueue || stats.hasPendingPayments || stats.todayCount > 0;
  };
  const statusTextFor = (tab: TabItem) => {
    const stats = statsFor(tab);
    const parts: string[] = [];
    if (stats.hasActiveQueue) parts.push(t('final.tgs_active_queue'));
    if (stats.hasPendingPayments) parts.push(t('registrarPanel.pending_payments'));
    if (stats.todayCount > 0) parts.push(`${countLabel(tab)}: ${stats.todayCount}`);
    return parts.join(', ');
  };
  const renderStatusIndicators = (tab: TabItem) => {
    const stats = statsFor(tab);
    return <>
      {stats.hasActiveQueue && <div className="status-indicator queue" title={t('final.tgs_active_queue')}><Clock size={10} /></div>}
      {stats.hasPendingPayments && <div className="status-indicator pending" title={t('registrarPanel.pending_payments')}><AlertCircle size={10} /></div>}
      {stats.todayCount > 0 && <div className="status-indicator count" title={`${countLabel(tab)}: ${stats.todayCount}`}>{stats.todayCount}</div>}
    </>;
  };
  const onTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const buttons = tabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    if (!buttons?.length) return;
    let target = -1;
    switch (event.key) {
      case 'ArrowRight': target = (index + 1) % buttons.length; break;
      case 'ArrowLeft': target = (index - 1 + buttons.length) % buttons.length; break;
      case 'Home': target = 0; break;
      case 'End': target = buttons.length - 1; break;
      default: return;
    }
    event.preventDefault();
    buttons[target]?.focus();
  };
  const clearFilter = () => {
    if (activeDoctorId != null) onDoctorChange?.(null); else onTabChange?.(null);
  };

  return <div className="modern-tabs">
    {loading && !hasLoaded && <p role="status">{t('registrarPanel.rt_loading')}</p>}
    {loadError && <div className="registrar-stale-banner" role="alert">
      <span>{t('registrarPanel.rt_load_error')}</span>
      <button type="button" onClick={() => { void loadTabs(); }}>{t('registrarPanel.rt_retry')}</button>
    </div>}
    <div className="tabs-container">
      <button type="button" className={`tab-button all-departments ${isOverview ? 'active' : ''}`}
        onClick={() => onTabChange?.(null)} aria-label={t('queue.all_departments')}>
        <div className="tab-icon"><TrendingUp size={16} /></div>
        <span className="tab-label">{t('queue.all_departments')}</span>
      </button>
      {tabs.length > 0 && <div className="tabs-divider" aria-hidden="true" />}
      <div className="department-tabs" role="tablist" ref={tabsRef}>
        <div className="tab-indicator" aria-hidden="true"
          style={{ ...indicatorStyle, background: selected?.gradient || 'transparent' }} />
        {tabs.map((tab, index) => {
          const doctor = tab.target_kind === 'doctor';
          const Icon = tab.icon;
          const active = isSelected(tab);
          return <button key={`${tab.target_kind}:${tab.target_id}`} type="button"
            data-tab={doctor ? undefined : tab.key} data-doctor-id={doctor ? tab.target_id : undefined}
            id={doctor ? doctorTabButtonIdFor(tab.target_id) : tabButtonIdFor(tab.key)}
            role="tab" aria-selected={active} aria-controls="main-content" aria-label={tab.label}
            aria-describedby={hasStatusFor(tab) ? statusIdFor(tab) : undefined} title={tab.label}
            tabIndex={active || isOverview || (hiddenFilter && index === 0) ? 0 : -1}
            onKeyDown={(event) => onTabKeyDown(event, index)}
            onClick={() => doctor ? onDoctorChange?.(active ? null : tab.target_id) : onTabChange?.(active ? null : tab.key)}
            className={`tab-button department ${doctor ? 'doctor' : ''} ${active ? 'active' : ''}`}
            style={{ '--tab-color': tab.color, '--tab-gradient': tab.gradient } as CSSProperties}>
            <div className="tab-content">
              <div className="tab-icon"><Icon size={16} /></div>
              <span className="tab-label">{tab.label}</span>
              <div className="status-indicators">{renderStatusIndicators(tab)}</div>
              {hasStatusFor(tab) && <span id={statusIdFor(tab)} className="sr-only">{statusTextFor(tab)}</span>}
            </div>
            <div className="ripple-effect" />
          </button>;
        })}
      </div>
    </div>
    {hiddenFilter && <div className="registrar-stale-banner" role="status">
      {/* WorklistView keeps this selected-filter IDREF for historical links.
          Supply its label without adding a selectable tab to the strip. */}
      <span id={activeDoctorId != null ? doctorTabButtonIdFor(activeDoctorId) : activeTab ? tabButtonIdFor(activeTab) : undefined}>
        {t('registrarPanel.rt_hidden_filter')}
      </span>
      <button type="button" onClick={clearFilter}>{t('registrarPanel.rt_clear_filter')}</button>
    </div>}
  </div>;
};
export default Tabs;
