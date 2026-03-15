import React, { startTransition, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useTranslation } from '../hooks/useTranslation';
import { MacOSButton, MacOSCard, MacOSModal } from '../components/ui/macos';
import {
  Activity,
  ArrowRight,
  BarChart3,
  Calendar,
  CheckCircle,
  Clock,
  Key,
  MapPin,
  MessageSquare,
  Moon,
  Phone,
  Shield,
  Sparkles,
  Stethoscope,
  Sun,
  User,
  Users
} from 'lucide-react';
import AppActivation from '../components/activation/AppActivation';
import { LANDING_COPY, buildGlassStyle } from './landingContent';
import './Landing.css';

const FEATURE_VISUALS = [
  { icon: Calendar, accent: '#22c55e' },
  { icon: Users, accent: '#0ea5e9' },
  { icon: BarChart3, accent: '#f59e0b' },
  { icon: Shield, accent: '#a855f7' }
];

const IMPACT_VISUALS = [
  { icon: Sparkles, accent: '#0ea5e9' },
  { icon: CheckCircle, accent: '#22c55e' },
  { icon: ArrowRight, accent: '#f97316' }
];

function SurfaceLabel({ children }) {
  return <span className="landing-surface-label">{children}</span>;
}

function HeroMetric({ value, label, detail }) {
  return (
    <div className="landing-hero-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      <small>{detail}</small>
    </div>
  );
}

function SectionHeading({ eyebrow, title, description }) {
  return (
    <div className="landing-section-heading">
      <SurfaceLabel>{eyebrow}</SurfaceLabel>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}

function FeatureCard({ accent, icon: Icon, title, badge, description }) {
  return (
    <MacOSCard className="landing-feature-card" shadow="large" style={{ borderColor: `${accent}33` }}>
      <div className="landing-feature-icon" style={{ background: `${accent}18`, color: accent }}>
        <Icon size={20} />
      </div>
      <div className="landing-feature-copy">
        <SurfaceLabel>{badge}</SurfaceLabel>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </MacOSCard>
  );
}

function WorkflowStep({ title, description }) {
  return (
    <div className="landing-workflow-step">
      <div className="landing-workflow-marker" aria-hidden="true" />
      <div>
        <h3>{title}</h3>
        <p>{description}</p>
      </div>
    </div>
  );
}

function ImpactCard({ accent, icon: Icon, title, description }) {
  return (
    <MacOSCard className="landing-impact-card" shadow="large">
      <div className="landing-impact-icon" style={{ color: accent, background: `${accent}14` }}>
        <Icon size={20} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </MacOSCard>
  );
}

function ContactRow({ icon: Icon, label, value, href }) {
  const content = href ? (
    <a
      className="landing-contact-link"
      href={href}
      target={href.startsWith('http') ? '_blank' : undefined}
      rel={href.startsWith('http') ? 'noreferrer' : undefined}
    >
      {value}
    </a>
  ) : (
    <span>{value}</span>
  );

  return (
    <div className="landing-contact-row">
      <div className="landing-contact-icon">
        <Icon size={18} />
      </div>
      <div>
        <strong>{label}</strong>
        {content}
      </div>
    </div>
  );
}

function toTelegramUrl(handle) {
  const sanitizedHandle = String(handle || '').trim().replace(/^@/, '');
  return sanitizedHandle ? `https://t.me/${sanitizedHandle}` : undefined;
}

function toTelUrl(phone) {
  const sanitizedPhone = String(phone || '').replace(/[^\d+]/g, '');
  return sanitizedPhone ? `tel:${sanitizedPhone}` : undefined;
}

export default function Landing() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const { availableLanguages, language, setLanguage, t } = useTranslation();
  const [showActivation, setShowActivation] = useState(false);

  const copy = LANDING_COPY[language] || LANDING_COPY.ru;
  const cardStyle = useMemo(() => buildGlassStyle(isDark), [isDark]);
  const heroCardStyle = useMemo(() => buildGlassStyle(isDark, 'hero'), [isDark]);
  const accentCardStyle = useMemo(() => buildGlassStyle(isDark, 'accent'), [isDark]);

  const currentLanguageIndex = availableLanguages.findIndex((item) => item.code === language);
  const currentLanguage = availableLanguages[currentLanguageIndex] || availableLanguages[0];
  const nextLanguage =
    availableLanguages[(currentLanguageIndex + 1) % availableLanguages.length] || availableLanguages[0];

  const handleLanguageCycle = () => {
    if (!nextLanguage?.code) {
      return;
    }

    startTransition(() => {
      setLanguage(nextLanguage.code);
    });
  };

  return (
    <div className={`landing-shell ${isDark ? 'landing-shell--dark' : 'landing-shell--light'}`}>
      <div className="landing-orb landing-orb--one" aria-hidden="true" />
      <div className="landing-orb landing-orb--two" aria-hidden="true" />
      <div className="landing-grid-overlay" aria-hidden="true" />

      <main className="landing-page">
        <header className="landing-topbar">
          <div className="landing-status-pill" role="status" aria-live="polite">
            <Activity size={15} />
            <span>{copy.liveStatus}</span>
          </div>

          <div className="landing-toolbar">
            <MacOSButton
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              className="landing-toolbar-button"
              aria-label={isDark ? t('lightTheme') : t('darkTheme')}
              title={isDark ? t('lightTheme') : t('darkTheme')}
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </MacOSButton>

            <MacOSButton
              variant="ghost"
              size="sm"
              onClick={handleLanguageCycle}
              className="landing-toolbar-button landing-language-button"
              aria-label={`${copy.languageSwitchLabel}: ${currentLanguage?.name || language} -> ${nextLanguage?.name || language}`}
              title={`${copy.languageSwitchLabel}: ${nextLanguage?.name || language}`}
            >
              <span className="landing-language-flag">{currentLanguage?.flag || '🌐'}</span>
              <span>{language.toUpperCase()}</span>
            </MacOSButton>
          </div>
        </header>

        <section className="landing-hero">
          <MacOSCard className="landing-hero-card" shadow="large" style={heroCardStyle}>
            <SurfaceLabel>{copy.heroEyebrow}</SurfaceLabel>
            <h1>{copy.heroTitle}</h1>
            <p className="landing-hero-description">{copy.heroDescription}</p>

            <div className="landing-role-pills" aria-label="Supported roles">
              {copy.rolePills.map((pill) => (
                <span key={pill} className="landing-role-pill">
                  {pill}
                </span>
              ))}
            </div>

            <ul className="landing-hero-points">
              {copy.heroPoints.map((point) => (
                <li key={point}>
                  <CheckCircle size={18} />
                  <span>{point}</span>
                </li>
              ))}
            </ul>

            <div className="landing-cta-row">
              <MacOSButton variant="primary" size="lg" onClick={() => navigate('/login')} className="landing-primary-cta">
                <User size={18} />
                {t('loginButton')}
              </MacOSButton>

              <MacOSButton variant="outline" size="lg" onClick={() => setShowActivation(true)} className="landing-secondary-cta">
                <Key size={18} />
                {t('activateButton')}
              </MacOSButton>
            </div>

            <p className="landing-hero-footnote">{copy.heroFootnote}</p>
          </MacOSCard>

          <div className="landing-side-column">
            <MacOSCard className="landing-console-card" shadow="large" style={cardStyle}>
              <div className="landing-console-header">
                <div>
                  <SurfaceLabel>{copy.consoleTitle}</SurfaceLabel>
                  <h2>{copy.consoleSubtitle}</h2>
                </div>
                <div className="landing-console-badge">
                  <Stethoscope size={18} />
                </div>
              </div>

              <div className="landing-console-metrics">
                {copy.consoleMetrics.map((item) => (
                  <HeroMetric key={item.label} value={item.value} label={item.label} detail={item.detail} />
                ))}
              </div>

              <div className="landing-console-feed">
                {copy.consoleEvents.map((event) => (
                  <div key={event.title} className="landing-console-feed-item">
                    <div className="landing-console-feed-dot" aria-hidden="true" />
                    <div>
                      <strong>{event.title}</strong>
                      <p>{event.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </MacOSCard>

            <MacOSCard className="landing-side-cta-card" shadow="large" style={accentCardStyle}>
              <SurfaceLabel>{copy.closingTitle}</SurfaceLabel>
              <p>{copy.closingDescription}</p>
              <div className="landing-side-cta-actions">
                <MacOSButton variant="primary" onClick={() => navigate('/login')} className="landing-inline-button">
                  {t('loginButton')}
                  <ArrowRight size={16} />
                </MacOSButton>

                <MacOSButton variant="ghost" onClick={() => setShowActivation(true)} className="landing-inline-button">
                  <Key size={16} />
                  {t('activateButton')}
                </MacOSButton>
              </div>
            </MacOSCard>
          </div>
        </section>

        <section className="landing-metric-strip landing-progressive-section" aria-label="Key product metrics">
          {copy.metricStrip.map((item) => (
            <MacOSCard key={item.label} className="landing-metric-card" shadow="large" style={cardStyle}>
              <strong>{item.value}</strong>
              <span>{item.label}</span>
              <small>{item.detail}</small>
            </MacOSCard>
          ))}
        </section>

        <section className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.featureEyebrow} title={copy.featureTitle} description={copy.featureDescription} />

          <div className="landing-feature-grid">
            {copy.features.map((feature, index) => {
              const visual = FEATURE_VISUALS[index % FEATURE_VISUALS.length];
              return (
                <FeatureCard
                  key={feature.title}
                  accent={visual.accent}
                  icon={visual.icon}
                  title={feature.title}
                  badge={feature.badge}
                  description={feature.description}
                />
              );
            })}
          </div>
        </section>

        <section className="landing-section landing-operating-grid landing-progressive-section">
          <MacOSCard className="landing-section-card" shadow="large" style={cardStyle}>
            <SectionHeading eyebrow={copy.workflowEyebrow} title={copy.workflowTitle} description={copy.workflowDescription} />

            <div className="landing-workflow-list">
              {copy.workflowSteps.map((step) => (
                <WorkflowStep key={step.title} title={step.title} description={step.description} />
              ))}
            </div>
          </MacOSCard>

          <MacOSCard className="landing-section-card landing-checklist-card" shadow="large" style={cardStyle}>
            <SectionHeading eyebrow={copy.operationsEyebrow} title={copy.operationsTitle} description={copy.operationsDescription} />

            <ul className="landing-checklist">
              {copy.operationsChecklist.map((item) => (
                <li key={item}>
                  <CheckCircle size={18} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </MacOSCard>
        </section>

        <section className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.impactEyebrow} title={copy.impactTitle} description={copy.impactDescription} />

          <div className="landing-impact-grid">
            {copy.impactCards.map((card, index) => {
              const visual = IMPACT_VISUALS[index % IMPACT_VISUALS.length];
              return (
                <ImpactCard
                  key={card.title}
                  accent={visual.accent}
                  icon={visual.icon}
                  title={card.title}
                  description={card.description}
                />
              );
            })}
          </div>
        </section>

        <section className="landing-section landing-contact-grid landing-progressive-section">
          <MacOSCard className="landing-section-card" shadow="large" style={cardStyle}>
            <SectionHeading eyebrow={t('contacts')} title={copy.supportTitle} description={copy.contactDescription} />

            <div className="landing-contact-list">
              <ContactRow icon={MapPin} label={copy.contactLabels.address} value={t('address')} />
              <ContactRow icon={Phone} label={copy.contactLabels.phone} value={t('phone')} href={toTelUrl(t('phone'))} />
              <ContactRow icon={Clock} label={copy.contactLabels.schedule} value={t('schedule')} />
              <ContactRow icon={MessageSquare} label={copy.contactLabels.support} value={t('telegram')} href={toTelegramUrl(t('telegram'))} />
            </div>
          </MacOSCard>

          <MacOSCard className="landing-section-card landing-support-card" shadow="large" style={accentCardStyle}>
            <SurfaceLabel>{copy.supportTitle}</SurfaceLabel>
            <p className="landing-support-description">{copy.supportDescription}</p>

            <ul className="landing-support-list">
              {copy.supportBullets.map((item) => (
                <li key={item}>
                  <CheckCircle size={18} />
                  <span>{item}</span>
                </li>
              ))}
            </ul>

            <div className="landing-support-actions">
              <MacOSButton variant="primary" size="lg" onClick={() => navigate('/login')}>
                <User size={18} />
                {t('loginButton')}
              </MacOSButton>
              <MacOSButton variant="outline" size="lg" onClick={() => setShowActivation(true)}>
                <Key size={18} />
                {t('activateButton')}
              </MacOSButton>
            </div>
          </MacOSCard>
        </section>

        <footer className="landing-footer">
          <div className="landing-footer-brand">
            <div className="landing-footer-logo" aria-hidden="true">
              <Stethoscope size={18} />
            </div>
            <div>
              <strong>{t('title')}</strong>
              <span>{t('footer')}</span>
            </div>
          </div>

          <div className="landing-footer-note">
            <Sparkles size={16} />
            <span>{copy.closingDescription}</span>
          </div>
        </footer>
      </main>

      <MacOSModal isOpen={showActivation} onClose={() => setShowActivation(false)} title={copy.activationTitle} size="md">
        <AppActivation onClose={() => setShowActivation(false)} />
      </MacOSModal>
    </div>
  );
}
