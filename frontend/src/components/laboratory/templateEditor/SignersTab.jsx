import PropTypes from 'prop-types';
import { signerFieldLabels } from './config';

/**
 * L-H-6 fix: SignersTab выделен в отдельный файл (~25 строк).
 * Вкладка «Подписи» — подписи по умолчанию (lab_technician + approver).
 */
function SignersTab({ draftVersion, onUpdateSigner }) {
  return (
    <div>
      <div className="ltw-branding-title">Подписи по умолчанию</div>
      <div className="ltw-grid-4-minmax">
        {['lab_technician_label', 'lab_technician_name', 'approver_label', 'approver_name'].map((key) => (
          <label key={key} className="ltw-grid-6">
            <span>{signerFieldLabels[key] || key}</span>
            <input
              className="macos-input"
              aria-label={signerFieldLabels[key] || key}
              value={draftVersion.signer_defaults?.[key] || ''}
              onChange={(event) => onUpdateSigner(key, event.target.value)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

SignersTab.propTypes = {
  draftVersion: PropTypes.object.isRequired,
  onUpdateSigner: PropTypes.func.isRequired,
};

export default SignersTab;
