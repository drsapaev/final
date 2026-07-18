
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
export const ControlCenter = ({ onActivate, onLogin }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  return (
    <div className="control-center spotlight-card">
      <h2>{t('misc.cc_panel_upravleniya')}</h2>
      <div className="control-actions">
        <button
          className="control-button activation"
          onClick={onActivate}
        >
          <span className="button-icon">🔑</span>
          <div className="button-content">
            <span className="button-title">{t('misc.cc_aktivatsiya_sistemy')}</span>
            <span className="button-description">{t('misc.cc_aktiviruyte_vashu_litsenziyu')}</span>
          </div>
        </button>

        <button
          className="control-button login"
          onClick={onLogin}
        >
          <span className="button-icon">🚀</span>
          <div className="button-content">
            <span className="button-title">{t('misc.cc_vhod_v_sistemu')}</span>
            <span className="button-description">{t('misc.cc_dlya_zaregistrirovannyh_polz')}</span>
          </div>
        </button>
      </div>

      <div className="features-grid">
        <div className="feature-item">
          <span className="feature-icon">👥</span>
          <span className="feature-name">{t('misc.cc_upravlenie_patsientami')}</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📋</span>
          <span className="feature-name">{t('misc.cc_elektronnye_karty')}</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📊</span>
          <span className="feature-name">{t('misc.cc_analitika_i_otchety')}</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">💳</span>
          <span className="feature-name">{t('misc.cc_priem_platezhey')}</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">🔔</span>
          <span className="feature-name">{t('misc.cc_uvedomleniya')}</span>
        </div>
        <div className="feature-item">
          <span className="feature-icon">🌐</span>
          <span className="feature-name">{t('misc.cc_telemeditsina')}</span>
        </div>
      </div>
    </div>
  );
};


ControlCenter.propTypes = {
  ...(ControlCenter.propTypes || {}),
  onActivate: PropTypes.any,
  onLogin: PropTypes.any,
};
