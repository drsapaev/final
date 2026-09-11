import React, { type CSSProperties } from 'react';

import { useState, useRef, useEffect, useCallback, useId } from 'react';
import {
  Heart,
  Activity,
  UserCheck,
  Smile,
  FlaskConical,
  Syringe,
  Calendar,
  Clock,
  AlertCircle,
  TrendingUp,
  Package,
  Stethoscope,
  TestTube,
  Scissors,
  FolderTree,
  Sparkles,
  Users } from
'lucide-react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import './Tabs.css';
import { useTranslation } from '../../i18n/useTranslation';

// Маппинг иконок из lucide-react
// ⭐ SSOT: icon names from QueueProfile.icon field
const iconMap = {
  Heart,
  Activity,
  UserCheck,
  Smile,
  FlaskConical,
  Syringe,
  Calendar,
  Package,
  Stethoscope,
  TestTube,
  Scissors,
  FolderTree,
  Sparkles,
  Sparkle: Sparkles, // Alias for backend compatibility
  Users
};

const defaultTabColor = 'var(--mac-accent)';

const toGradient = (color: string) =>
  `linear-gradient(135deg, ${color}, color-mix(in srgb, ${color}, white 14%))`;

// RQ-19: shared tab-id contract. The department tab buttons and the
// registrar worklist tabpanel (WorklistView #main-content aria-labelledby)
// MUST derive the same id, so both sides call this helper. Tab keys are
// backend-defined (queue profile key) and may contain whitespace or other
// characters illegal in an HTML id (see statusIdFor below) — the key is
// percent-encoded (injective + deterministic, no cross-key collisions);
// for clean keys ('cardiology') the output equals the pre-existing
// `${key}-tab` format the panel already referenced (now resolvable).
export const tabButtonIdFor = (tabKey: string): string =>
  `${encodeURIComponent(tabKey)}-tab`;

type IconComponent = React.ComponentType<{ size?: number | string; className?: string }>;

interface TabItem {
  key: string;
  label: string;
  queue_tags: string[];
  icon: IconComponent;
  color: string;
  gradient: string;
}

interface TabsProps {
  activeTab?: string | null;
  onTabChange?: (tab: string | null) => void;
  onProfilesLoaded?: (profiles: unknown[]) => void;
  departmentStats?: Record<string, unknown>;
  language?: string;
  theme?: string;
  dynamicDepartments?: unknown[];
}

const Tabs = ({
  activeTab,
  onTabChange,
  onProfilesLoaded,
  departmentStats = {},
  language = 'ru',
  theme,
  dynamicDepartments
}: TabsProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [indicatorStyle, setIndicatorStyle] = useState<Record<string, any>>({});
  const [tabs, setTabs] = useState<TabItem[]>([]);
  const [loading, setLoading] = useState(true);
  const tabsRef = useRef<HTMLDivElement | null>(null);
  // AXE-MOB-1 (Codex P2 round 1, thread 3944915764): instance-scoped id
  // prefix for the aria-describedby targets — document-unique even with
  // multiple Tabs mounts (e.g. CSSTestPage).
  const uid = useId();

  // ⭐ SSOT: Загрузка профилей очередей (вкладок) из БД через API
  // Tabs определяются в backend, frontend только отображает
  const loadQueueProfiles = useCallback(async () => {
    try {
      setLoading(true);

      // ⭐ NEW API: /queues/profiles возвращает динамические вкладки
      // Формат: { profiles: [{key, title, title_ru, queue_tags, icon, color}] }
      const response = await api.get('/queues/profiles?active_only=true');

      // Backend returns {success: true, profiles: [...], source: 'database'|'fallback'}
      const profiles = (response.data?.profiles as Record<string, any>[]) || [];

      if (profiles.length === 0) {
        throw new Error('No profiles returned from API');
      }

      // Преобразуем данные из API в формат для вкладок
      const profilesData: TabItem[] = profiles.map((profile) => ({
        key: String(profile.key),
        label: language === 'uz' ? profile.title || profile.title_ru : profile.title_ru || profile.title,
        // ⭐ SSOT: queue_tags используются для фильтрации записей на вкладке
        queue_tags: profile.queue_tags || [profile.key],
        icon: (iconMap[profile.icon as keyof typeof iconMap] as IconComponent) || Package, // Fallback на Package если иконка не найдена
        color: profile.color || defaultTabColor,
        gradient: profile.gradient || toGradient(profile.color || defaultTabColor)
      }));

      logger.info(`✅ SSOT: Loaded ${profilesData.length} queue profiles from API (source: ${response.data.source})`);
      setTabs(profilesData);

      // ⭐ SSOT: Notify parent component about loaded profiles for filtering
      if (onProfilesLoaded) {
        onProfilesLoaded(profilesData);
      }
    } catch (error) {
      logger.error('Ошибка загрузки профилей очередей:', error);

      // Fallback на hardcoded вкладки если API не работает
      // ⚠️ TEMPORARY ADAPTER: Remove when API is stable
      setTabs([
      {
        key: 'cardiology',
        label: language === 'uz' ? 'Kardiolog' : t('misc.mt_kardiolog'),
        queue_tags: ['cardio', 'cardiology', 'cardiology_common'],
        icon: Heart,
        color: 'var(--mac-error)',
        gradient: toGradient('var(--mac-error)')
      },
      {
        key: 'ecg',
        label: language === 'uz' ? 'EKG' : t('misc.mt_ekg'),
        queue_tags: ['ecg', 'echokg'],
        icon: Activity,
        color: 'var(--mac-accent-purple)',
        gradient: toGradient('var(--mac-accent-purple)')
      },
      {
        key: 'dermatology',
        label: language === 'uz' ? 'Dermatolog' : t('misc.mt_dermatolog'),
        queue_tags: ['derma', 'dermatology'],
        icon: UserCheck,
        color: 'var(--mac-warning)',
        gradient: toGradient('var(--mac-warning)')
      },
      {
        key: 'stomatology',
        label: language === 'uz' ? 'Stomatolog' : t('misc.mt_stomatolog'),
        queue_tags: ['dental', 'stomatology', 'dentist'],
        icon: Smile,
        color: 'var(--mac-accent)',
        gradient: toGradient('var(--mac-accent)')
      },
      {
        key: 'lab',
        label: language === 'uz' ? 'Laboratoriya' : t('misc.mt_laboratoriya'),
        queue_tags: ['lab', 'laboratory'],
        icon: FlaskConical,
        color: 'var(--mac-success)',
        gradient: toGradient('var(--mac-success)')
      },
      {
        key: 'procedures',
        label: language === 'uz' ? 'Muolajalar' : t('misc.mt_protsedury'),
        queue_tags: ['procedures', 'physio', 'therapy'],
        icon: Syringe,
        color: 'var(--mac-accent-purple)',
        gradient: toGradient('var(--mac-accent-purple)')
      }]
      );
    } finally {
      setLoading(false);
    }
  }, [language, onProfilesLoaded]);

  useEffect(() => {
    loadQueueProfiles();
  }, [loadQueueProfiles]);

  // Слушаем обновления профилей очередей
  useEffect(() => {
    const handleProfilesUpdate = (event: Event) => {
      logger.log('Tabs: Получено обновление профилей очередей', (event as CustomEvent).detail);
      loadQueueProfiles();
    };

    window.addEventListener('queue-profiles:updated', handleProfilesUpdate);
    // Также слушаем старое событие для обратной совместимости
    window.addEventListener('departments:updated', handleProfilesUpdate);

    return () => {
      window.removeEventListener('queue-profiles:updated', handleProfilesUpdate);
      window.removeEventListener('departments:updated', handleProfilesUpdate);
    };
  }, [loadQueueProfiles]);

  const colors = {
    bg: 'color-mix(in srgb, var(--mac-bg-primary), transparent 2%)',
    border: 'var(--mac-border)',
    text: 'var(--mac-text-primary)',
    textSecondary: 'var(--mac-text-secondary)'
  };

  // Обновление позиции индикатора
  useEffect(() => {
    if (activeTab && tabsRef.current) {
      const activeButton = tabsRef.current.querySelector(`[data-tab="${activeTab}"]`);
      if (activeButton) {
        const rect = activeButton.getBoundingClientRect();
        const containerRect = tabsRef.current.getBoundingClientRect();

        setIndicatorStyle({
          left: rect.left - containerRect.left,
          width: rect.width,
          opacity: 1
        });
      }
    } else {
      setIndicatorStyle({ opacity: 0 });
    }
  }, [activeTab, tabs]);

  // Получение статистики для отдела
  const getStats = (tabKey: string) => {
    const stats = (departmentStats[tabKey] || {}) as Record<string, unknown>;
    return {
      todayCount: Number(stats.todayCount ?? 0),
      hasActiveQueue: Boolean(stats.hasActiveQueue),
      hasPendingPayments: Boolean(stats.hasPendingPayments)
    };
  };

  // Рендер индикаторов статуса
  const renderStatusIndicators = (tabKey: string) => {
    const stats = getStats(tabKey);
    const indicators: React.ReactNode[] = [];
    if (stats.hasActiveQueue) {
      indicators.push(
        <div
          key="queue"
          className="status-indicator queue"
          // AXE-MOB-1 (Codex P2 round 4, thread 3945043227): an active-queue
          // phrase WITHOUT the unrelated count — todayCount is every
          // appointment dated today (computeDepartmentStats) while
          // hasActiveQueue is derived independently from active
          // queue_numbers entries, so "Queue: {todayCount}" misannounced
          // both directions ("Queue: 5" for 5 appointments + 1 queued;
          // "Queue: 0" for an other-day active queue). The tooltip agrees
          // with the description below.
          title={t('final.tgs_active_queue')}>

          <Clock size={10} />
        </div>
      );
    }

    if (stats.hasPendingPayments) {
      indicators.push(
        <div
          key="pending"
          className="status-indicator pending"
          // AXE-MOB-1 (Codex P2 round 4, thread 3945043230): the
          // payment-specific label — queue_status.pending is a generic
          // queue-state word (and untranslated in en). registrarPanel
          // .pending_payments resolves to "Pending payments" in en.
          title={t('registrarPanel.pending_payments')}>

          <AlertCircle size={10} />
        </div>
      );
    }

    if (Number(stats.todayCount ?? 0) > 0) {
      indicators.push(
        <div
          key="count"
          className="status-indicator count"
          title={`${t('registrarPanel.today')}: ${String(stats.todayCount ?? '')}`}>

          {String(stats.todayCount ?? '')}
        </div>
      );
    }

    return indicators;
  };

  // AXE-MOB-1 (Codex P2 round 1, thread 3944915764): the department
  // buttons carry aria-label={tab.label}, which overrides name-from-content
  // — without the wiring below the status indicators (active queue, pending
  // payment, today count) would stay visible but DISAPPEAR from screen-
  // reader output. The status text is associated as the button accessible
  // DESCRIPTION via aria-describedby -> the in-button .status-indicators
  // container. The container is rendered visible at EVERY width (only
  // .tab-label collapses at <=768px), so the reference stays resolvable on
  // mobile too; the name keeps the stable department label (WCAG 2.5.3
  // Label-in-Name) and the description announces the operational status.
  // AXE-MOB-1 (Codex P2 round 6, thread 3945096766): the tab key is
  // backend-defined (queue profile key) and may contain whitespace or other
  // characters illegal in an HTML id (e.g. "general medicine").
  // aria-describedby is an ID-reference list — the id MUST be
  // whitespace-free, so the key is percent-encoded (injective +
  // deterministic, no cross-key collisions).
  const statusIdFor = (tabKey: string) => `${uid}-status-${encodeURIComponent(tabKey)}`;
  const hasStatusFor = (tabKey: string) => {
    const s = getStats(tabKey);
    return s.hasActiveQueue || s.hasPendingPayments || s.todayCount > 0;
  };
  // AXE-MOB-1 (Codex P2 round 2, thread 3944985044): the description target
  // must carry REAL text. Icon-only indicators store their meaning in
  // `title` attributes, which are not reliably concatenated into the
  // accessible description, and boolean-only states would compute an EMPTY
  // description (or an unexplained bare count). statusTextFor composes the
  // localized status sentence from the same stats the visible indicators
  // render; it is rendered as a dedicated .sr-only description target —
  // visually invisible, announced by AT.
  // AXE-MOB-1 (Codex P2 rounds 3-4, threads 3945016484 / 3945043227 /
  // 3945043230): every key must be DEFINED in all five locales AND carry
  // the right semantics:
  //   - active queue: final.tgs_active_queue ("Активная очередь") — a
  //     boolean phrase; todayCount is ALL appointments dated today, NOT the
  //     queue size, so it must never ride the queue announcement;
  //   - pending payments: registrarPanel.pending_payments ("Pending
  //     payments") — payment-specific, not the generic queue state word;
  //   - today count: registrarPanel.today + the count — this pairing IS
  //     semantically correct ("Сегодня: N" = appointments dated today).
  const statusTextFor = (tabKey: string): string => {
    const s = getStats(tabKey);
    const parts: string[] = [];
    if (s.hasActiveQueue) parts.push(t('final.tgs_active_queue'));
    if (s.hasPendingPayments) parts.push(t('registrarPanel.pending_payments'));
    if (s.todayCount > 0) parts.push(`${t('registrarPanel.today')}: ${s.todayCount}`);
    return parts.join(', ');
  };

  // RQ-19: ARIA tabs keyboard support — MANUAL ACTIVATION. Switching the
  // active tab refetches the registrar worklist (per-tab data load), so
  // arrow keys move focus WITHOUT activating (APG manual-activation tabs);
  // Enter/Space (native button activation) or click performs the
  // selection. ArrowLeft/ArrowRight wrap around; Home/End jump.
  // preventDefault keeps the horizontally scrollable strip from scrolling
  // while arrowing. Enter/Space deliberately keep the native click
  // behavior (including the toggle-off of the active tab), so keyboard
  // and pointer users get the same selection semantics as before.
  const onTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    const tabButtons = tabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]');
    if (!tabButtons || tabButtons.length === 0) return;
    const count = tabButtons.length;
    let target = -1;
    switch (event.key) {
      case 'ArrowRight': target = (index + 1) % count; break;
      case 'ArrowLeft': target = (index - 1 + count) % count; break;
      case 'Home': target = 0; break;
      case 'End': target = count - 1; break;
      default: return;
    }
    event.preventDefault();
    tabButtons[target]?.focus();
  };

  // Показываем заглушку пока загружаются вкладки
  if (loading) {
    return (
      <div className="modern-tabs">
        <div
          className="tabs-container"
          style={{
            background: colors.bg,
            borderTop: `1px solid ${colors.border}`,
            borderLeft: `1px solid ${colors.border}`,
            borderRight: `1px solid ${colors.border}`,
            borderBottom: `1px solid ${colors.border}`,
            borderRadius: '12px 12px 0 0',
            padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
            boxShadow: 'none'
          }}>

          <div style={{ padding: 'var(--mac-spacing-3)', textAlign: 'center', color: colors.textSecondary }}>
            Загрузка отделений...
          </div>
        </div>
      </div>);

  }

  return (
    <div className="modern-tabs">
      <div
        className="tabs-container"
        style={{
          background: colors.bg,
          borderTop: `1px solid ${colors.border}`,
          borderLeft: `1px solid ${colors.border}`,
          borderRight: `1px solid ${colors.border}`,
          borderBottom: `1px solid ${colors.border}`,
          borderRadius: '12px 12px 0 0',
          padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
          boxShadow: 'none'
        }}>

        {/* Кнопка t('misc.mt_vse_otdeleniya') */}
        <button
          className={`tab-button all-departments ${!activeTab ? 'active' : ''}`}
          onClick={() => onTabChange?.(null)}
          // AXE-MOB-1 (Mobile Chrome registrar:light/dark, axe button-name):
          // Tabs.css hides .tab-label at <=768px, collapsing this control to
          // an icon-only button with NO accessible name. Pin the name to the
          // same source as the visible label (identical text at desktop
          // widths keeps WCAG 2.5.3 Label-in-Name satisfied).
          aria-label={t('queue.all_departments')}
          style={{
            color: !activeTab ? 'var(--mac-accent)' : colors.text
          }}>

          <div className="tab-icon">
            <TrendingUp size={16} />
          </div>
          {/* REG-NS-1 follow-up (Codex P2): queue.all does not exist in any
              locale — the exposed tab rendered the literal key. Use the
              locale-complete all_departments key (all five locales define
              it with real translations). */}
          <span className="tab-label">{t('queue.all_departments')}</span>
        </button>

        {/* Разделитель */}
        <div
          className="tabs-divider"
          style={{ backgroundColor: colors.border }} />


        {/* Контейнер для вкладок отделений */}
        {/* RQ-19: the strip is a real ARIA tablist — the department controls
            are tabs, the selected one is announced via aria-selected (no
            color/icon dependency). The decorative animated indicator below
            is aria-hidden so the tablist exposes only its tabs. */}
        <div className="department-tabs" role="tablist" ref={tabsRef}>
          {/* Анимированный индикатор */}
          <div
            className="tab-indicator"
            aria-hidden="true"
            style={{
              ...indicatorStyle,
              background: activeTab ? tabs.find((tb) => tb.key === activeTab)?.gradient : 'transparent'
            }} />


          {/* Вкладки отделений */}
          {tabs.map((tab, index) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;

            return (
              <button
                key={tab.key}
                data-tab={tab.key}
                id={tabButtonIdFor(tab.key)}
                role="tab"
                aria-selected={isActive}
                aria-controls="main-content"
                // RQ-19: APG roving tabindex — with a selected tab only it
                // stays in the Tab sequence; with NO selection (the
                // all-departments view) every tab remains tabbable,
                // preserving today's keyboard order in the default view.
                tabIndex={isActive || activeTab == null ? 0 : -1}
                onKeyDown={(event) => onTabKeyDown(event, index)}
                className={`tab-button department ${isActive ? 'active' : ''}`}
                onClick={() => onTabChange?.(isActive ? null : tab.key)}
                // AXE-MOB-1: same button-name contract as the
                // all-departments control above — the visible .tab-label is
                // display:none at <=768px (Tabs.css), so the name must come
                // from an attribute. Status text is NOT folded into the
                // label: it rides the accessible description instead (see
                // statusIdFor above) so SR users still hear the operational
                // status this button renders visually.
                aria-label={tab.label}
                aria-describedby={hasStatusFor(tab.key) ? statusIdFor(tab.key) : undefined}
                style={{
                  color: isActive ? 'var(--mac-text-primary)' : colors.text,
                  backgroundColor: isActive ? 'color-mix(in srgb, var(--mac-nav-item-active), transparent 70%)' : 'transparent',
                  '--tab-color': tab.color,
                  '--tab-gradient': tab.gradient
                } as CSSProperties}>

                <div className="tab-content">
                  <div className="tab-icon">
                    <Icon size={16} />
                  </div>
                  <span className="tab-label">{tab.label}</span>

                  {/* Индикаторы статуса */}
                  <div className="status-indicators">
                    {renderStatusIndicators(tab.key)}
                  </div>
                  {/* AXE-MOB-1 round 2 (thread 3944985044): dedicated sr-only
                      description TARGET — the visible container would
                      concatenate the bare count digits into the description
                      ("4 queue.queue: 4 …"); this node carries ONLY the
                      localized sentence, so the description is exact. */}
                  {hasStatusFor(tab.key) && (
                    <span id={statusIdFor(tab.key)} className="sr-only">
                      {statusTextFor(tab.key)}
                    </span>
                  )}
                </div>

                {/* Эффект ripple */}
                <div className="ripple-effect" />
              </button>);

          })}
        </div>
      </div>

      {/* Информационная панель убрана для стиля Edge */}
    </div>);

};


// audit/strict: removed self-referencing propTypes spread

export default Tabs;
