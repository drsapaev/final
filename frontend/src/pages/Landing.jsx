import React, { startTransition, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import {
  Button, MacOSCard,
} from '../components/ui/macos';
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
import { LANDING_COPY, buildGlassStyle } from './landingContent';
import { BRAND } from '../config/brand';
import './Landing.css';
import PropTypes from 'prop-types';
import { useTranslation } from '../hooks/useTranslation';

const FEATURE_VISUALS = [
  { icon: FileText, accent: 'var(--mac-accent-blue)' },
  { icon: Users, accent: 'var(--mac-success)' },
  { icon: Activity, accent: 'var(--mac-warning)' },
  { icon: CreditCard, accent: 'var(--mac-accent-teal, #14b8a6)' },
  { icon: MessageSquare, accent: 'var(--mac-accent-purple)' },
  { icon: BarChart3, accent: 'var(--mac-warning)' }
];

const MODULE_VISUALS = [FileText, Stethoscope, Activity, Users, MessageSquare, CreditCard, BarChart3, Shield];
const SHOWCASE_VISUALS = [BarChart3, Users, Activity, FileText, CreditCard];
const SECURITY_VISUALS = [Shield, Users, Key, Activity];
const INTEGRATION_VISUALS = [MessageSquare, CreditCard, CreditCard, CreditCard, Activity, FileText];

function SurfaceLabel({ children }) {
  const { t } = useTranslation();
  return <span className="landing-surface-label">{children}</span>;
}


SurfaceLabel.propTypes = {
  children: PropTypes.node,
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
  align: PropTypes.oneOf(['left', 'center']),
  description: PropTypes.string,
  eyebrow: PropTypes.string,
  title: PropTypes.string,
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
  detail: PropTypes.string,
  label: PropTypes.string,
  style: PropTypes.object,
  value: PropTypes.node,
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
  accent: PropTypes.string,
  badge: PropTypes.string,
  description: PropTypes.string,
  icon: PropTypes.elementType,
  title: PropTypes.string,
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
  description: PropTypes.string,
  icon: PropTypes.elementType,
  label: PropTypes.string,
  style: PropTypes.object,
  title: PropTypes.string,
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
  description: PropTypes.string,
  title: PropTypes.string,
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


// UX Audit Stage 2 (Landing issue 1.5): почищены propTypes-артефакты.
// Удалён `...(ContactRow.propTypes || {})` (бессмысленный spread из codemod)
// и удалён несуществующий prop `startsWith: PropTypes.any`.
ContactRow.propTypes = {
  href: PropTypes.string,
  icon: PropTypes.elementType,
  label: PropTypes.string,
  value: PropTypes.string,
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
  const copy = LANDING_COPY[language] || LANDING_COPY.ru;
  const cardStyle = useMemo(() => buildGlassStyle(isDark), [isDark]);
  const heroCardStyle = useMemo(() => buildGlassStyle(isDark, 'hero'), [isDark]);
  const accentCardStyle = useMemo(() => buildGlassStyle(isDark, 'accent'), [isDark]);

  const currentLanguageIndex = availableLanguages.findIndex((item) => item.code === language);
  const currentLanguage = availableLanguages[currentLanguageIndex] || availableLanguages[0];
  // UX Audit Stage 2: nextLanguage удалён — был нужен только для cycle-переключателя,
  // сейчас используется dropdown и прямое handleLanguageSelect(code).

  // UX Audit Stage 2 (Landing issue 1.2): свитчер языков → dropdown вместо cycle.
  // Раньше было 4 языка (RU→UZ→EN→KZ→RU) и чтобы попасть в EN из RU нужно 2 клика.
  // Теперь dropdown открывается одним кликом и сразу показывает все варианты.
  const [showLangDropdown, setShowLangDropdown] = useState(false);

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

  // UX Audit Stage 2 (Landing issue 1.2): заменили cycle на dropdown select.
  // handleLanguageCycle удалён, вместо него — handleLanguageSelect(code).
  const handleLanguageSelect = (code) => {
    if (!code) {
      return;
    }

    startTransition(() => {
      setLanguage(code);
    });
    setShowLangDropdown(false);
  };

  // UX Audit Stage 2 (Landing issue 1.2): close dropdown on outside click / Escape.
  useEffect(() => {
    if (!showLangDropdown) {
      return undefined;
    }

    const handleClickOutside = (event) => {
      const trigger = document.getElementById('landing-lang-trigger');
      const dropdown = document.getElementById('landing-lang-dropdown');
      if (
        trigger && !trigger.contains(event.target) &&
        dropdown && !dropdown.contains(event.target)
      ) {
        setShowLangDropdown(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setShowLangDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [showLangDropdown]);

  const scrollToSection = (sectionId) => {
    document.getElementById(sectionId)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  };

  // UX Audit Stage 2 (Landing issue 1.2): smooth-scroll для футер-якорей.
  // Раньше клик на якорь в футере (#product, #workflow и т.д.) делал резкий
  // browser-jump, потому что это были <a href="#..."> без обработчика.
  // Теперь перехватываем клик и используем тот же scrollToSection.
  const handleFooterLinkClick = (event, href) => {
    if (!href || !href.startsWith('#')) {
      return;
    }
    event.preventDefault();
    const sectionId = href.slice(1);
    scrollToSection(sectionId);
  };

  // UX Audit Stage 2 (Landing issue 1.1): унификация CTA.
  // Раньше 7 кнопок с 5 разными текстами вели на /login.
  // Теперь 2 цели: «Войти в систему» (→ /login) и «Связаться с продажами» (→ telegram).
  // Кнопка «Связаться с продажами» открывает Telegram-чат с поддержкой.
  const handleSalesContact = () => {
    const telegramUrl = toTelegramUrl(t('telegram'));
    if (telegramUrl) {
      window.open(telegramUrl, '_blank', 'noopener,noreferrer');
    } else {
      // Fallback: скроллим к секции контактов
      scrollToSection('contact');
    }
  };

  return (
    <div className={`landing-shell ${isDark ? 'landing-shell--dark' : 'landing-shell--light'}`}>
      <div className="landing-orb landing-orb--one" aria-hidden="true" />
      <div className="landing-orb landing-orb--two" aria-hidden="true" />
      <div className="landing-grid-overlay" aria-hidden="true" />

      <main className="landing-page">
        <header className="landing-topbar">
          {/* UX Audit Stage 1: используем единый BRAND config вместо хардкода */}
          <a className="landing-brand" href="#hero" aria-label={BRAND.name}>
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
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleTheme}
              className="landing-toolbar-button"
              aria-label={isDark ? t('lightTheme') : t('darkTheme')}
              title={isDark ? t('lightTheme') : t('darkTheme')}
            >
              {isDark ? <Sun size={16} /> : <Moon size={16} />}
            </Button>

            {/* UX Audit Stage 2 (Landing issue 1.2):
                Свитчер языков теперь dropdown вместо cycle.
                Раньше было 4 клика чтобы вернуться к исходному языку, теперь — 1 клик. */}
            <div className="landing-language-wrap">
              <Button
                id="landing-lang-trigger"
                variant="ghost"
                size="sm"
                onClick={() => setShowLangDropdown((v) => !v)}
                className="landing-toolbar-button landing-language-button"
                aria-label={copy.languageSwitchLabel}
                title={copy.languageSwitchLabel}
                aria-expanded={showLangDropdown}
                aria-haspopup="listbox"
              >
                <span className="landing-language-flag">{currentLanguage?.flag || '🌐'}</span>
                <span>{language.toUpperCase()}</span>
                <ChevronRight
                  size={12}
                  aria-hidden="true"
                  style={{
                    transform: showLangDropdown ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 150ms ease',
                    marginLeft: 2,
                  }}
                />
              </Button>

              {showLangDropdown && (
                <ul
                  id="landing-lang-dropdown"
                  role="listbox"
                  aria-label={copy.languageSwitchLabel}
                  className="landing-language-dropdown"
                >
                  {availableLanguages.map((lang) => {
                    const isActive = lang.code === language;
                    return (
                      <li key={lang.code} role="option" aria-selected={isActive}>
                        <button
                          type="button"
                          className={`landing-language-option ${isActive ? 'landing-language-option--active' : ''}`}
                          onClick={() => handleLanguageSelect(lang.code)}
                        >
                          <span className="landing-language-flag" aria-hidden="true">{lang.flag || '🌐'}</span>
                          <span>{lang.name}</span>
                          <span className="landing-language-code">{lang.code.toUpperCase()}</span>
                          {isActive && <CheckCircle size={14} aria-hidden="true" />}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <Button variant="primary" size="sm" onClick={() => navigate('/login')} className="landing-header-login">
              <User size={16} />
              {copy.headerLogin}
            </Button>
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
              {/* UX Audit Stage 2 (Landing issue 1.1):
                  Унификация CTA. Раньше 7 кнопок с 5 текстами вели на /login.
                  Теперь 2 цели:
                    - «Войти в систему» (primary) → /login
                    - «Связаться с продажами» (outline) → Telegram-чат
                  Hero secondary («Смотреть 2-минутный обзор») оставлен как scroll-to-section,
                  но переименован в «Посмотреть интерфейс» в landingContent.js. */}
              <Button variant="primary" size="lg" onClick={() => navigate('/login')} className="landing-primary-cta">
                <User size={18} />
                {copy.headerLogin}
              </Button>

              <Button variant="outline" size="lg" onClick={() => scrollToSection('screens')} className="landing-secondary-cta">
                <ArrowRight size={18} />
                {copy.hero.secondaryCta}
              </Button>
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

                {/* UX Audit Stage 2 (Landing issue 1.1):
                    Pricing 3 кнопки раньше все вели на /login с разными текстами
                    («Запросить демо», «Выбрать Professional», «Обсудить Enterprise»).
                    Теперь: featured plan → /login (trial start),
                    остальные 2 → sales contact (Telegram) для персональной консультации. */}
                <Button
                  variant={plan.featured ? 'primary' : 'outline'}
                  size="lg"
                  onClick={plan.featured ? () => navigate('/login') : handleSalesContact}
                  className="landing-plan-button"
                  title={plan.featured
                    ? 'Открыть демо-режим системы'
                    : 'Связаться с продажами для персонального предложения'}
                >
                  {plan.cta}
                </Button>
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
              {/* UX Audit Stage 2 (Landing issue 1.1):
                  Final CTA 2 кнопки раньше обе вели на /login.
                  Теперь: primary «Запросить демо» → /login (trial),
                  secondary «Активировать лицензию» → sales contact (Telegram). */}
              <Button variant="primary" size="lg" onClick={() => navigate('/login')}>
                <User size={18} />
                {copy.finalCta.primaryCta}
              </Button>
              <Button variant="outline" size="lg" onClick={handleSalesContact}>
                <Key size={18} />
                {copy.finalCta.secondaryCta}
              </Button>

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
                    // UX Audit Stage 2 (Landing issue 1.2):
                    // Smooth-scroll для футер-якорей через handleFooterLinkClick.
                    // Раньше это был резкий browser-jump.
                    <a
                      key={link.label}
                      href={link.href}
                      className="landing-footer-link"
                      onClick={(e) => handleFooterLinkClick(e, link.href)}
                    >
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
    </div>
  );
}
