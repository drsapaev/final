import React, { startTransition, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useTranslation } from '../hooks/useTranslation';
import { MacOSButton, MacOSCard, MacOSModal } from '../components/ui/macos';
import {
  Activity,
  ArrowRight,
  BarChart3,
  CheckCircle,
  ChevronRight,
  Clock,
  CreditCard,
  FileText,
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
import PropTypes from 'prop-types';

const FEATURE_VISUALS = [
  { icon: FileText, accent: '#0ea5e9' },
  { icon: Users, accent: '#22c55e' },
  { icon: Activity, accent: '#f97316' },
  { icon: CreditCard, accent: '#14b8a6' },
  { icon: MessageSquare, accent: '#8b5cf6' },
  { icon: BarChart3, accent: '#f59e0b' }
];

const MODULE_VISUALS = [FileText, Stethoscope, Activity, Users, MessageSquare, CreditCard, BarChart3, Shield];
const SHOWCASE_VISUALS = [BarChart3, Users, Activity, FileText, CreditCard];
const SECURITY_VISUALS = [Shield, Users, Key, Activity];
const INTEGRATION_VISUALS = [MessageSquare, CreditCard, CreditCard, CreditCard, Activity, FileText];

function SurfaceLabel({ children }) {
  return <span className="landing-surface-label">{children}</span>;
}


SurfaceLabel.propTypes = {
  ...(SurfaceLabel.propTypes || {}),
  children: PropTypes.any,
};

function SectionHeading({ eyebrow, title, description, align = 'left' }) {
  return (
    <div className={`landing-section-heading landing-section-heading--${align}`}>
      <SurfaceLabel>{eyebrow}</SurfaceLabel>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}


SectionHeading.propTypes = {
  ...(SectionHeading.propTypes || {}),
  align: PropTypes.any,
  description: PropTypes.any,
  eyebrow: PropTypes.any,
  title: PropTypes.any,
};

function MetricCard({ value, label, detail, style }) {
  return (
    <MacOSCard className="landing-metric-card" shadow="large" style={style}>
      <strong>{value}</strong>
      <span>{label}</span>
      <small>{detail}</small>
    </MacOSCard>
  );
}


MetricCard.propTypes = {
  ...(MetricCard.propTypes || {}),
  detail: PropTypes.any,
  label: PropTypes.any,
  style: PropTypes.any,
  value: PropTypes.any,
};

function FeatureCard({ accent, icon: Icon, badge, title, description }) {
  return (
    <MacOSCard className="landing-feature-card" shadow="large" style={{ borderColor: `${accent}2f` }}>
      <div className="landing-feature-icon" style={{ background: `${accent}18`, color: accent }}>
        <Icon size={20} />
      </div>
      <SurfaceLabel>{badge}</SurfaceLabel>
      <h3>{title}</h3>
      <p>{description}</p>
    </MacOSCard>
  );
}


FeatureCard.propTypes = {
  ...(FeatureCard.propTypes || {}),
  accent: PropTypes.any,
  badge: PropTypes.any,
  description: PropTypes.any,
  icon: PropTypes.any,
  title: PropTypes.any,
};

function ShowcaseCard({ icon: Icon, label, title, description, style }) {
  return (
    <MacOSCard className="landing-showcase-card" shadow="large" style={style}>
      <div className="landing-showcase-head">
        <div className="landing-showcase-icon">
          <Icon size={20} />
        </div>
        <SurfaceLabel>{label}</SurfaceLabel>
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      <div className="landing-showcase-bars" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </MacOSCard>
  );
}


ShowcaseCard.propTypes = {
  ...(ShowcaseCard.propTypes || {}),
  description: PropTypes.any,
  icon: PropTypes.any,
  label: PropTypes.any,
  style: PropTypes.any,
  title: PropTypes.any,
};

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


WorkflowStep.propTypes = {
  ...(WorkflowStep.propTypes || {}),
  description: PropTypes.any,
  title: PropTypes.any,
};

function ContactRow({ icon: Icon, label, value, href }) {
  const isExternal = href?.startsWith('http');
  const content = href ? (
    <a className="landing-contact-link" href={href} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noreferrer' : undefined}>
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


ContactRow.propTypes = {
  ...(ContactRow.propTypes || {}),
  href: PropTypes.any,
  icon: PropTypes.any,
  label: PropTypes.any,
  startsWith: PropTypes.any,
  value: PropTypes.any,
};

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

  useEffect(() => {
    const root = document.getElementById('root');
    if (!root) {
      return undefined;
    }

    root.classList.add('landing-root');
    document.body.classList.add('landing-body');

    return () => {
      root.classList.remove('landing-root');
      document.body.classList.remove('landing-body');
    };
  }, []);

  const handleLanguageCycle = () => {
    if (!nextLanguage?.code) {
      return;
    }

    startTransition(() => {
      setLanguage(nextLanguage.code);
    });
  };

  const scrollToSection = (sectionId) => {
    document.getElementById(sectionId)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  };

  return (
    <div className={`landing-shell ${isDark ? 'landing-shell--dark' : 'landing-shell--light'}`}>
      <div className="landing-orb landing-orb--one" aria-hidden="true" />
      <div className="landing-orb landing-orb--two" aria-hidden="true" />
      <div className="landing-grid-overlay" aria-hidden="true" />

      <main className="landing-page">
        <header className="landing-topbar">
          <a className="landing-brand" href="#hero" aria-label="MediClinic Pro">
            <div className="landing-brand-mark" aria-hidden="true">
              <Stethoscope size={18} />
            </div>
            <div>
              <strong>{t('title')}</strong>
              <span>{copy.liveStatus}</span>
            </div>
          </a>

          <nav className="landing-nav" aria-label={copy.navigationLabel}>
            {copy.navigation.map((item) => (
              <button key={item.id} type="button" className="landing-nav-link" onClick={() => scrollToSection(item.id)}>
                {item.label}
              </button>
            ))}
          </nav>

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

            <MacOSButton variant="primary" size="sm" onClick={() => navigate('/login')} className="landing-header-login">
              <User size={16} />
              {copy.headerLogin}
            </MacOSButton>
          </div>
        </header>

        <section id="hero" className="landing-hero">
          <MacOSCard className="landing-hero-card" shadow="large" style={heroCardStyle}>
            <div className="landing-live-badge" role="status" aria-live="polite">
              <Activity size={15} />
              <span>{copy.liveStatus}</span>
            </div>

            <SurfaceLabel>{copy.hero.eyebrow}</SurfaceLabel>
            <h1>{copy.hero.title}</h1>
            <p className="landing-hero-description">{copy.hero.description}</p>

            <div className="landing-cta-row">
              <MacOSButton variant="primary" size="lg" onClick={() => navigate('/login')} className="landing-primary-cta">
                <User size={18} />
                {copy.hero.primaryCta}
              </MacOSButton>

              <MacOSButton variant="outline" size="lg" onClick={() => scrollToSection('screens')} className="landing-secondary-cta">
                <ArrowRight size={18} />
                {copy.hero.secondaryCta}
              </MacOSButton>
            </div>

            <div className="landing-role-pills" aria-label="Product highlights">
              {copy.hero.proofChips.map((pill) => (
                <span key={pill} className="landing-role-pill">
                  {pill}
                </span>
              ))}
            </div>

            <div className="landing-console-metrics">
              {copy.hero.quickStats.map((item) => (
                <MetricCard key={item.label} value={item.value} label={item.label} detail={item.detail} style={cardStyle} />
              ))}
            </div>
          </MacOSCard>

          <div className="landing-hero-visuals">
            {copy.hero.visualPanels.map((panel, index) => (
              <MacOSCard
                key={panel.title}
                className={`landing-console-card landing-console-card--${index + 1}`}
                shadow="large"
                style={index === 1 ? accentCardStyle : cardStyle}
              >
                <SurfaceLabel>{panel.label}</SurfaceLabel>
                <h2>{panel.title}</h2>
                <p>{panel.description}</p>

                <ul className="landing-console-feed">
                  {panel.bullets.map((bullet) => (
                    <li key={bullet} className="landing-console-feed-item">
                      <CheckCircle size={16} />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </MacOSCard>
            ))}
          </div>
        </section>

        <section className="landing-section landing-progressive-section" aria-label="Operational proof">
          <SectionHeading eyebrow={copy.trust.eyebrow} title={copy.trust.title} description={copy.trust.description} />

          <div className="landing-metric-strip">
            {copy.trust.items.map((item) => (
              <MetricCard key={item.label} value={item.value} label={item.label} detail={item.detail} style={cardStyle} />
            ))}
          </div>
        </section>

        <section id="product" className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.features.eyebrow} title={copy.features.title} description={copy.features.description} />

          <div className="landing-feature-grid">
            {copy.features.items.map((feature, index) => {
              const visual = FEATURE_VISUALS[index % FEATURE_VISUALS.length];
              return (
                <FeatureCard
                  key={feature.title}
                  accent={visual.accent}
                  icon={visual.icon}
                  badge={feature.badge}
                  title={feature.title}
                  description={feature.description}
                />
              );
            })}
          </div>
        </section>

        <section id="workflow" className="landing-section landing-progressive-section">
          <MacOSCard className="landing-section-card" shadow="large" style={cardStyle}>
            <SectionHeading eyebrow={copy.workflow.eyebrow} title={copy.workflow.title} description={copy.workflow.description} />

            <div className="landing-workflow-grid">
              <div className="landing-workflow-list">
                {copy.workflow.steps.map((step) => (
                  <WorkflowStep key={step.title} title={step.title} description={step.description} />
                ))}
              </div>

              <div className="landing-flow-card">
                <SurfaceLabel>{copy.workflow.flowLabel}</SurfaceLabel>
                <div className="landing-flow-track" aria-label={copy.workflow.flowLabel}>
                  {copy.workflow.flowNodes.map((item, index) => (
                    <React.Fragment key={item}>
                      <span className="landing-flow-chip">{item}</span>
                      {index < copy.workflow.flowNodes.length - 1 ? <ChevronRight size={16} className="landing-flow-arrow" /> : null}
                    </React.Fragment>
                  ))}
                </div>
                <p>{copy.workflow.flowSummary}</p>
              </div>
            </div>
          </MacOSCard>
        </section>

        <section id="modules" className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.modules.eyebrow} title={copy.modules.title} description={copy.modules.description} />

          <div className="landing-module-grid">
            {copy.modules.items.map((module, index) => {
              const Icon = MODULE_VISUALS[index % MODULE_VISUALS.length];
              return (
                <MacOSCard key={module.title} className="landing-module-card" shadow="large" style={cardStyle}>
                  <div className="landing-module-icon">
                    <Icon size={18} />
                  </div>
                  <h3>{module.title}</h3>
                  <p>{module.description}</p>
                </MacOSCard>
              );
            })}
          </div>
        </section>

        <section id="screens" className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.screens.eyebrow} title={copy.screens.title} description={copy.screens.description} />

          <div className="landing-showcase-grid">
            {copy.screens.items.map((item, index) => (
              <ShowcaseCard
                key={item.title}
                icon={SHOWCASE_VISUALS[index % SHOWCASE_VISUALS.length]}
                label={item.label}
                title={item.title}
                description={item.description}
                style={index === 0 ? accentCardStyle : cardStyle}
              />
            ))}
          </div>
        </section>

        <section className="landing-section landing-dual-grid landing-progressive-section">
          <MacOSCard id="integrations" className="landing-section-card" shadow="large" style={cardStyle}>
            <SectionHeading
              eyebrow={copy.integrations.eyebrow}
              title={copy.integrations.title}
              description={copy.integrations.description}
            />

            <div className="landing-integration-grid">
              {copy.integrations.items.map((item, index) => {
                const Icon = INTEGRATION_VISUALS[index % INTEGRATION_VISUALS.length];
                return (
                  <div key={item.title} className="landing-integration-card">
                    <div className="landing-integration-icon">
                      <Icon size={18} />
                    </div>
                    <div>
                      <strong>{item.title}</strong>
                      <span>{item.detail}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </MacOSCard>

          <MacOSCard id="security" className="landing-section-card" shadow="large" style={cardStyle}>
            <SectionHeading eyebrow={copy.security.eyebrow} title={copy.security.title} description={copy.security.description} />

            <div className="landing-security-grid">
              {copy.security.items.map((item, index) => {
                const Icon = SECURITY_VISUALS[index % SECURITY_VISUALS.length];
                return (
                  <div key={item.title} className="landing-security-card">
                    <div className="landing-security-icon">
                      <Icon size={18} />
                    </div>
                    <h3>{item.title}</h3>
                    <p>{item.description}</p>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </section>

        <section className="landing-section landing-progressive-section">
          <SectionHeading
            eyebrow={copy.advantages.eyebrow}
            title={copy.advantages.title}
            description={copy.advantages.description}
            align="center"
          />

          <div className="landing-advantage-grid">
            <MacOSCard className="landing-advantage-card landing-advantage-card--before" shadow="large" style={cardStyle}>
              <h3>{copy.advantages.beforeTitle}</h3>
              <ul className="landing-checklist landing-checklist--negative">
                {copy.advantages.beforeItems.map((item) => (
                  <li key={item}>
                    <span className="landing-checklist-marker landing-checklist-marker--negative" aria-hidden="true" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </MacOSCard>

            <MacOSCard className="landing-advantage-card landing-advantage-card--after" shadow="large" style={accentCardStyle}>
              <h3>{copy.advantages.afterTitle}</h3>
              <ul className="landing-checklist">
                {copy.advantages.afterItems.map((item) => (
                  <li key={item}>
                    <CheckCircle size={18} />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </MacOSCard>
          </div>
        </section>

        <section id="pricing" className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.pricing.eyebrow} title={copy.pricing.title} description={copy.pricing.description} align="center" />

          <div className="landing-pricing-grid">
            {copy.pricing.plans.map((plan) => (
              <MacOSCard
                key={plan.name}
                className={`landing-pricing-card ${plan.featured ? 'landing-pricing-card--featured' : ''}`}
                shadow="large"
                style={plan.featured ? accentCardStyle : cardStyle}
              >
                <SurfaceLabel>{plan.audience}</SurfaceLabel>
                <h3>{plan.name}</h3>
                <div className="landing-plan-price">{plan.price}</div>
                <p className="landing-plan-note">{plan.note}</p>

                <ul className="landing-checklist">
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <CheckCircle size={18} />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <MacOSButton
                  variant={plan.featured ? 'primary' : 'outline'}
                  size="lg"
                  onClick={() => setShowActivation(true)}
                  className="landing-plan-button"
                >
                  {plan.cta}
                </MacOSButton>
              </MacOSCard>
            ))}
          </div>

          <p className="landing-pricing-footnote">{copy.pricing.footnote}</p>
        </section>

        <section id="faq" className="landing-section landing-progressive-section">
          <SectionHeading eyebrow={copy.faq.eyebrow} title={copy.faq.title} description={copy.faq.description} />

          <div className="landing-faq-list">
            {copy.faq.items.map((item) => (
              <details key={item.question} className="landing-faq-item">
                <summary>
                  <span>{item.question}</span>
                  <ChevronRight size={18} />
                </summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section id="contact" className="landing-section landing-progressive-section">
          <MacOSCard className="landing-final-card" shadow="large" style={heroCardStyle}>
            <div className="landing-final-copy">
              <SurfaceLabel>{copy.finalCta.eyebrow}</SurfaceLabel>
              <h2>{copy.finalCta.title}</h2>
              <p>{copy.finalCta.description}</p>

              <ul className="landing-support-list">
                {copy.finalCta.bullets.map((item) => (
                  <li key={item}>
                    <CheckCircle size={18} />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="landing-final-actions">
              <MacOSButton variant="primary" size="lg" onClick={() => navigate('/login')}>
                <User size={18} />
                {copy.finalCta.primaryCta}
              </MacOSButton>
              <MacOSButton variant="outline" size="lg" onClick={() => setShowActivation(true)}>
                <Key size={18} />
                {copy.finalCta.secondaryCta}
              </MacOSButton>

              <div className="landing-contact-list">
                <ContactRow icon={MapPin} label={copy.contactLabels.address} value={t('address')} />
                <ContactRow icon={Phone} label={copy.contactLabels.phone} value={t('phone')} href={toTelUrl(t('phone'))} />
                <ContactRow icon={Clock} label={copy.contactLabels.schedule} value={t('schedule')} />
                <ContactRow
                  icon={MessageSquare}
                  label={copy.contactLabels.support}
                  value={t('telegram')}
                  href={toTelegramUrl(t('telegram'))}
                />
              </div>
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
              <span>{copy.footer.tagline}</span>
            </div>
          </div>

          <div className="landing-footer-columns">
            {copy.footer.groups.map((group) => (
              <div key={group.title} className="landing-footer-column">
                <strong>{group.title}</strong>
                <div className="landing-footer-links">
                  {group.links.map((link) => (
                    <a key={link.label} href={link.href} className="landing-footer-link">
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="landing-footer-note">
            <Sparkles size={16} />
            <span>{copy.footer.footnote}</span>
          </div>
        </footer>
      </main>

      <MacOSModal isOpen={showActivation} onClose={() => setShowActivation(false)} title={copy.activationTitle} size="md">
        <AppActivation onClose={() => setShowActivation(false)} />
      </MacOSModal>
    </div>
  );
}
