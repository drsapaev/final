import PropTypes from 'prop-types';
import { Button, Icon } from '../ui/macos';

/**
 * P-04 fix: LabReportActionsBar выделен из LabReportWorkbench.
 *
 * Панель действий с lifecycle state machine бланка:
 *   - Save Draft (canSaveDraft)
 *   - Mark Ready (canMarkReady)
 *   - Finalize (canFinalize) — primary
 *   - Create Revision (canRevise)
 *   - Print Result (canPrint) — primary
 *
 * Кнопки показываются только если соответствующее действие доступно
 * (server-driven через available_actions). Каждая кнопка отображает
 * busy-state с текстом «Сохраняю...» / «Финализирую...» и т.д.
 */
export default function LabReportActionsBar({
  saving = false,
  busyAction = '',
  canSaveDraft = false,
  canMarkReady = false,
  canFinalize = false,
  canRevise = false,
  canPrint = false,
  onSaveDraft,
  onMarkReady,
  onFinalize,
  onRevise,
  onPrint,
}) {
  const showPrimaryGroup = canSaveDraft || canMarkReady || canFinalize;
  const showSecondaryGroup = canRevise || canPrint;

  if (!showPrimaryGroup && !showSecondaryGroup) {
    return null;
  }

  return (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      {showPrimaryGroup && (
        <>
          <Button variant="outline" onClick={onSaveDraft} disabled={saving || !canSaveDraft}>
            <Icon name="square.and.arrow.down" size={16} />
            {busyAction === 'save' ? 'Сохраняю...' : 'Сохранить черновик'}
          </Button>
          <Button variant="outline" onClick={onMarkReady} disabled={saving || !canMarkReady}>
            <Icon name="checkmark.circle" size={16} />
            {busyAction === 'ready' ? 'Перевожу...' : 'Отметить готовым'}
          </Button>
          <Button variant="primary" onClick={onFinalize} disabled={saving || !canFinalize}>
            <Icon name="lock.circle" size={16} />
            {busyAction === 'finalize' ? 'Финализирую...' : 'Финализировать'}
          </Button>
        </>
      )}
      {showSecondaryGroup && (
        <>
          <Button variant="outline" onClick={onRevise} disabled={saving || !canRevise}>
            <Icon name="arrow.triangle.branch" size={16} />
            {busyAction === 'revise' ? 'Создаю ревизию...' : 'Создать ревизию'}
          </Button>
          <Button variant="primary" onClick={onPrint} disabled={saving || !canPrint}>
            <Icon name="printer" size={16} />
            {busyAction === 'print' ? 'Отправляю...' : 'Печать результата'}
          </Button>
        </>
      )}
    </div>
  );
}

LabReportActionsBar.propTypes = {
  saving: PropTypes.bool,
  busyAction: PropTypes.string,
  canSaveDraft: PropTypes.bool,
  canMarkReady: PropTypes.bool,
  canFinalize: PropTypes.bool,
  canRevise: PropTypes.bool,
  canPrint: PropTypes.bool,
  onSaveDraft: PropTypes.func.isRequired,
  onMarkReady: PropTypes.func.isRequired,
  onFinalize: PropTypes.func.isRequired,
  onRevise: PropTypes.func.isRequired,
  onPrint: PropTypes.func.isRequired,
};
