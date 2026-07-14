import PropTypes from 'prop-types';
import { layoutOptions, brandingFieldLabels } from './config';

/**
 * L-H-6 fix: DesignTab выделен в отдельный файл (~50 строк).
 * Вкладка «Оформление» — макет печати, подвал, брендирование.
 */
function DesignTab({ draftVersion, onUpdateLayout, onUpdateFooter, onUpdateBranding }) {
  return (
    <div className="ltw-grid-18">
      <div className="ltw-grid-2-minmax">
        <label className="ltw-grid-6">
          <span>Макет печати</span>
          <select
            className="macos-input"
            aria-label="Макет печати"
            value={draftVersion.layout_preset}
            onChange={(event) => onUpdateLayout(event.target.value)}
          >
            {layoutOptions.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="ltw-grid-6">
          <span>Подвал</span>
          <textarea
            className="macos-input"
            aria-label="Подвал шаблона"
            rows={3}
            value={draftVersion.footer_notes}
            onChange={(event) => onUpdateFooter(event.target.value)}
          />
        </label>
      </div>

      <div>
        <div className="ltw-branding-title">Брендирование документа</div>
        <div className="ltw-grid-3-minmax">
          {['document_title', 'document_subtitle', 'clinic_name', 'address', 'phone', 'logo_url'].map((key) => (
            <label key={key} className="ltw-grid-6">
              <span>{brandingFieldLabels[key] || key}</span>
              <input
                className="macos-input"
                aria-label={brandingFieldLabels[key] || key}
                value={draftVersion.branding_overrides?.[key] || ''}
                onChange={(event) => onUpdateBranding(key, event.target.value)}
              />
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

DesignTab.propTypes = {
  draftVersion: PropTypes.object.isRequired,
  onUpdateLayout: PropTypes.func.isRequired,
  onUpdateFooter: PropTypes.func.isRequired,
  onUpdateBranding: PropTypes.func.isRequired,
};

export default DesignTab;
