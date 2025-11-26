import React from 'react';

export const LandingHero = ({ onGetStarted }) => {
  return (
    <section className="landing-hero">
      <div className="hero-content">
        <h1 className="hero-title">
          Система управления клиникой
        </h1>
        <p className="hero-subtitle">
          Современное решение для медицинских учреждений
        </p>
        <div className="hero-actions">
          <button
            className="cta-button primary"
            onClick={onGetStarted}
          >
            Начать работу
          </button>
          <button className="cta-button secondary">
            Узнать больше
          </button>
        </div>
      </div>
      <div className="hero-visual">
        <div className="feature-badge">
          <span className="badge-icon">🏥</span>
          <span className="badge-text">Медицинская система</span>
        </div>
      </div>
    </section>
  );
};
