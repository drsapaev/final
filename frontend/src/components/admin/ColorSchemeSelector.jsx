import PropTypes from 'prop-types';
import { useMemo } from 'react';
import { Layers, Monitor, Moon, Palette, Rainbow, Sparkles, Sun, SwatchBook } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useMacOSTheme } from '../../theme/macosTheme.jsx';
import { COLOR_SCHEMES } from '../../theme/colorScheme.js';
import {
  MacOSCard, Select,
} from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

const ICONS = {
  light: Sun,
  dark: Moon,
  auto: Monitor,
  vibrant: Rainbow,
  glass: Layers,
  gradient: Sparkles,
};

const getMetrics = (t) => [
  { key: 'mood', label: t('admin2.css_metric_mood') },
  { key: 'surfaces', label: t('admin2.css_metric_surfaces') },
  { key: 'contrast', label: t('admin2.css_metric_contrast') },
  { key: 'bestFor', label: t('admin2.css_metric_best_for') },
];

const ACCENT_LABELS = {
  blue: 'Blue',
  purple: 'Purple',
  pink: 'Pink',
  red: 'Red',
  orange: 'Orange',
  yellow: 'Yellow',
  green: 'Green',
  graphite: 'Graphite',
};

function ThemePreviewCard({ scheme, isActive, onSelect }) {
  const { t } = useTranslation();
  const Icon = ICONS[scheme.id] || Sun;
  const preview = scheme.preview;
  const buttonLabel = isActive
    ? t('admin2.css_aria_current_scheme', { name: scheme.name, mood: scheme.mood, contrast: scheme.contrast })
    : t('admin2.css_aria_select_scheme', { name: scheme.name, mood: scheme.mood, contrast: scheme.contrast });

  return (
    <button
      type="button"
      data-preview-card="true"
      onClick={() => onSelect(scheme.id)}
      aria-pressed={isActive}
      aria-label={buttonLabel}
      className="admin-cursor-pointer-radius-18-p-16-ta-left-grid-gap-14-minh-196" style={{ '--admin-border': isActive ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)', '--admin-background': preview.background, '--admin-color': preview.text, '--admin-boxShadow': isActive ? '0 10px 28px rgba(15, 23, 42, 0.26)' : '0 8px 20px rgba(15, 23, 42, 0.12)' }}
    >
      <div className="admin-flex-ai-start-jc-between-gap-12">
        <div className="admin-grid-gap-6">
          <div className="admin-flex-center-8">
            <Icon aria-hidden="true" focusable="false" className="admin-icon-18" />
            <span className="admin-fontsize-3dd9b4-bold">
              {scheme.name}
            </span>
          </div>
          <span className="admin-fontsize-6b9c17-opacity-0p84">
            {t('admin2.css_mood_atmosphere', { mood: scheme.mood })}
          </span>
        </div>
        {isActive ?
          <span className="admin-fontsize-6b9c17-p-4px8-radius-999-background-c1d2e5">
            {t('admin2.css_active')}
          </span> :
          null}
      </div>

      <div className="admin-radius-14-p-12-grid-gap-10-bd-filter-blur12px-wbd-filter-blur12px" style={{ '--admin-border': `1px solid ${preview.border}`, '--admin-background': preview.surface }}>
        <div className="admin-grid-gtc-56px1fr-gap-10-ai-stretch">
          <div className="admin-radius-10" style={{ '--admin-background': preview.surfaceAlt, '--admin-border': `1px solid ${preview.border}` }} />
          <div className="admin-grid-gap-8">
            <div className="admin-h-12-w-72pct-radius-999-opacity-0p22" style={{ '--admin-background': preview.text }} />
            <div className="admin-h-10-w-48pct-radius-999-opacity-0p12" style={{ '--admin-background': preview.text }} />
            <div className="admin-h-24-w-42pct-radius-10" style={{ '--admin-background': preview.accent }} />
          </div>
        </div>
      </div>

      <div className="admin-flex-wrap-gap-8">
        <span className="admin-fontsize-8b6852-p-4px8-radius-999-background-5d083b" style={{ '--admin-border': `1px solid ${preview.border}` }}>
          {scheme.surfaces}
        </span>
        <span className="admin-fontsize-8b6852-p-4px8-radius-999-background-5d083b" style={{ '--admin-border': `1px solid ${preview.border}` }}>
          {scheme.contrast}
        </span>
      </div>
    </button>
  );
}

ThemePreviewCard.propTypes = {
  scheme: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    mood: PropTypes.string.isRequired,
    surfaces: PropTypes.string.isRequired,
    contrast: PropTypes.string.isRequired,
    preview: PropTypes.shape({
      background: PropTypes.string.isRequired,
      surface: PropTypes.string.isRequired,
      surfaceAlt: PropTypes.string.isRequired,
      accent: PropTypes.string.isRequired,
      text: PropTypes.string.isRequired,
      border: PropTypes.string.isRequired,
    }).isRequired,
  }).isRequired,
  isActive: PropTypes.bool.isRequired,
  onSelect: PropTypes.func.isRequired,
};

export default function ColorSchemeSelector() {
  const { t } = useTranslation();
  const { colorScheme, setColorScheme } = useTheme();
  const { accent } = useMacOSTheme();

  const colorSchemes = useMemo(() =>
    COLOR_SCHEMES.map((scheme) => ({
      ...scheme,
      icon: ICONS[scheme.id] || Sun,
    })), []);

  const currentScheme = colorSchemes.find((scheme) => scheme.id === colorScheme) || colorSchemes[0];
  const currentAccentLabel = ACCENT_LABELS[accent] || accent;
  const ActiveIcon = currentScheme.icon;
  const selectorTitleId = 'color-scheme-selector-title';
  const selectorDescriptionId = 'color-scheme-selector-description';
  const quickSelectId = 'color-scheme-selector-quick-select';
  const helpTextId = 'color-scheme-selector-help';
  const currentPreviewLabel = t('admin2.css_current_preview_label', { name: currentScheme.name, accent: currentAccentLabel });
  const metrics = getMetrics(t);

  return (
    <MacOSCard
      role="region"
      aria-labelledby={selectorTitleId}
      aria-describedby={selectorDescriptionId}
      className="admin-p-24-grid-gap-20"
    >
      <div className="admin-flex-ai-center-gap-10-jc-between-wrap">
        <div className="admin-flex-ai-center-gap-10">
          <Palette aria-hidden="true" focusable="false" className="admin-w-20-h-20-blue" />
          <div className="admin-grid-gap-4">
            <h3 id={selectorTitleId} className="admin-lg-semi-primary-m-0">
              {t('admin2.css_title')}
            </h3>
            <p id={selectorDescriptionId} className="admin-m-0-sm-secondary">
              {t('admin2.css_description')}
            </p>
          </div>
        </div>

        <div
          role="status"
          aria-label={t('admin2.css_accent_noway_aria', { accent: currentAccentLabel })}
          className="admin-inline-flex-ai-center-gap-8-p-10px12-radius-14-bg-bg-secondary-bd-1solidva-9204ee03"
        >
          <SwatchBook aria-hidden="true" focusable="false" className="admin-w-14-h-14-blue" />
          {t('admin2.css_accent_noway_prefix')} <strong className="admin-text-primary">{currentAccentLabel}</strong>
        </div>
      </div>

      <div
        id={helpTextId}
        className="admin-p-14px16-radius-16-background-41d8fc-bd-1solidvar-mac-border-grid-gap-8"
      >
        <div className="admin-fontsize-3044b6-bold-primary">
          {t('admin2.css_what_changes')}
        </div>
        <div className="admin-grid-gap-6-fontsize-6b9c17-secondary">
          <div>{t('admin2.css_scheme_saved_profile')}</div>
          <div>{t('admin2.css_accent_local_browser')}</div>
        </div>
      </div>

      <div className="admin-grid-gap-10">
        <label htmlFor={quickSelectId} className="admin-block-sm-med-primary">
          {t('admin2.css_quick_select')}
        </label>
        <Select
          id={quickSelectId}
          value={colorScheme}
          onChange={setColorScheme}
          aria-describedby={helpTextId}
          options={colorSchemes.map((scheme) => ({
            value: scheme.id,
            label: scheme.name,
          }))}
          placeholder={t('admin2.css_select_scheme_placeholder')}
          size="large"
        />
      </div>

      <div
        role="group"
        aria-label={t('admin2.css_cards_aria')}
        className="admin-grid-gtc-rauto-fitcminmax220pxc1fr-gap-16"
      >
        {colorSchemes.map((scheme) => (
          <ThemePreviewCard
            key={scheme.id}
            scheme={scheme}
            isActive={scheme.id === colorScheme}
            onSelect={setColorScheme}
          />
        ))}
      </div>

      <div className="admin-grid-gtc-minmax240pxc115frminmax260pxc1fr-gap-18">
        <div
          role="img"
          aria-label={currentPreviewLabel}
          className="admin-p-18-radius-18-bd-1solidvar-mac-border-grid-gap-16-minh-220" style={{ '--admin-background': currentScheme.preview.background, '--admin-color': currentScheme.preview.text }}
        >
          <div className="admin-flex-ai-center-gap-10-jc-between">
            <div className="admin-flex-ai-center-gap-10">
              <ActiveIcon aria-hidden="true" focusable="false" className="admin-icon-18" />
              <div className="admin-grid-gap-2">
                <strong>{currentScheme.name}</strong>
                <span className="admin-fontsize-6b9c17-opacity-0p84">{currentScheme.description}</span>
              </div>
            </div>
          </div>

          <div className="admin-grid-gtc-72px1fr-gap-14-flex-1">
            <div className="admin-radius-14-grid-gap-8-p-10" style={{ '--admin-background': currentScheme.preview.surfaceAlt, '--admin-border': `1px solid ${currentScheme.preview.border}` }}>
              <div className="admin-h-10-radius-999-background-022358" />
              <div className="admin-h-10-radius-999-background-4443b0" />
              <div className="admin-mt-auto-h-28-radius-10" style={{ '--admin-background': currentScheme.preview.accent }} />
            </div>

            <div className="admin-radius-16-p-14-grid-gap-12-bd-filter-blur14px-wbd-filter-blur14px" style={{ '--admin-border': `1px solid ${currentScheme.preview.border}`, '--admin-background': currentScheme.preview.surface }}>
              <div className="admin-h-36-radius-12-background-4443b0" style={{ '--admin-border': `1px solid ${currentScheme.preview.border}` }} />
              <div className="admin-grid-gap-8">
                <div className="admin-h-12-w-76pct-radius-999-opacity-0p22" style={{ '--admin-background': currentScheme.preview.text }} />
                <div className="admin-h-10-w-58pct-radius-999-opacity-0p12" style={{ '--admin-background': currentScheme.preview.text }} />
              </div>
              <div className="admin-flex-gap-10">
                <div className="admin-flex-1-h-36-radius-12-bg-blue" />
                <div className="admin-w-38pct-h-36-radius-12-background-4443b0" style={{ '--admin-border': `1px solid ${currentScheme.preview.border}` }} />
              </div>
            </div>
          </div>
        </div>

        <div className="admin-p-18-radius-18-bd-1solidvar-mac-border-background-9a770f-grid-gap-14-align-28f14aec">
          <div className="admin-grid-gap-6">
            <div className="admin-fontsize-6b9c17-secondary-texttransform-5f7abe-ls-008em">
              {t('admin2.css_active_scheme')}
            </div>
            <div className="admin-fontsize-e5e6f8-bold-primary">
              {currentScheme.name}
            </div>
          </div>

          <div className="admin-grid-gap-10">
            {metrics.map((metric) => (
              <div
                key={metric.key}
                className="admin-grid-gap-6-p-12px14-radius-14-bg-bg-tertiary-bd-1solidvar-mac-border"
              >
                <span className="admin-fontsize-8b6852-secondary-texttransform-5f7abe-ls-008em">
                  {metric.label}
                </span>
                <span className="admin-fontsize-0cf08e-primary-semi">
                  {currentScheme[metric.key]}
                </span>
              </div>
            ))}
          </div>

          <div className="admin-p-12px14-radius-14-background-13d6cf-bd-1solidvar-mac-accent-border-primar-b92dd425">
            {t('admin2.css_full_change_hint')}
          </div>
        </div>
      </div>
    </MacOSCard>
  );
}
