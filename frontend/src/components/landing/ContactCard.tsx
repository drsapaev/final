// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
export const ContactCard = () => {
  const { t } = useTranslation();
  return (
    <div className="contact-card spotlight-card">
      <h2>{t('misc.cc_kontakty')}</h2>
      <div className="contact-info">
        <div className="contact-item">
          <span className="contact-icon">📞</span>
          <div className="contact-details">
            <span className="contact-label">{t('misc.cc_telefon')}</span>
            <span className="contact-value">+998 (90) 123-45-67</span>
          </div>
        </div>
        <div className="contact-item">
          <span className="contact-icon">📧</span>
          <div className="contact-details">
            <span className="contact-label">Email</span>
            <span className="contact-value">info@clinic.uz</span>
          </div>
        </div>
        <div className="contact-item">
          <span className="contact-icon">📍</span>
          <div className="contact-details">
            <span className="contact-label">{t('misc.cc_adres')}</span>
            <span className="contact-value">{t('misc.cc_g_tashkent_ul_primernaya_123')}</span>
          </div>
        </div>
        <div className="contact-item">
          <span className="contact-icon">🕐</span>
          <div className="contact-details">
            <span className="contact-label">{t('misc.cc_rezhim_raboty')}</span>
            <span className="contact-value">Пн-Пт: 8:00 - 20:00</span>
          </div>
        </div>
      </div>
    </div>
  );
};
