import React from 'react';

export const ControlCenter = ({ onActivate, onLogin }) => {
  return (
    <div className="control-center spotlight-card">
      <h2>Панель управления</h2>
      <div className="control-actions">
        <button
          className="control-button activation"
          onClick={onActivate}
        >
          <span className="button-icon">🔑</span>
          <div className="button-content">
            <span className="button-title">Активация системы</span>
            <span className="button-description">Активируйте вашу лицензию</span>
          </div>
        </button>

        <button
          className="control-button login"
          onClick={onLogin}
        >
          <span className="button-icon">🚀</span>
          <div className="button-content">
            <span className="button-title">Вход в систему</span>
            <span className="button-description">Для зарегистрированных пользователей</span>
          </div>
        </button>
      </div>

      <div className="features-grid">
        <div className="feature-item">
          <span className="feature-icon">👥</span>
          <span className="feature-name">Управление пациентами</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📋</span>
          <span className="feature-name">Электронные карты</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📊</span>
          <span className="feature-name">Аналитика и отчеты</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">💳</span>
          <span className="feature-name">Прием платежей</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">🔔</span>
          <span className="feature-name">Уведомления</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">🌐</span>
          <span className="feature-name">Телемедицина</span>
        </div>
      </div>
    </div>
  );
};
