export const ContactCard = () => {
  return (
    <div className="contact-card spotlight-card">
      <h2>Контакты</h2>
      <div className="contact-info">
        <div className="contact-item">
          <span className="contact-icon">📞</span>
          <div className="contact-details">
            <span className="contact-label">Телефон</span>
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
            <span className="contact-label">Адрес</span>
            <span className="contact-value">г. Ташкент, ул. Примерная 123</span>
          </div>
        </div>
        <div className="contact-item">
          <span className="contact-icon">🕐</span>
          <div className="contact-details">
            <span className="contact-label">Режим работы</span>
            <span className="contact-value">Пн-Пт: 8:00 - 20:00</span>
          </div>
        </div>
      </div>
    </div>
  );
};
