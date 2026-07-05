import PropTypes from 'prop-types';
import { Button, Icon } from '../ui/macos';

/**
 * P-04 fix: LabReportActionsBar выделен из LabReportWorkbench.
 *
 * WF-round5: Mark Ready убран (был функционально пустой операцией —
 * backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).
 * Теперь только: Save Draft → Finalize (primary), затем: Revise → Print (primary).
 *
 * Терминология (Вариант B): «Финализировать» → «Утвердить»,
 * «Создать ревизию» → «Создать исправленную версию».
 */
export default function LabReportActionsBar({
  saving = false,
  busyAction = '',
  canSaveDraft = false,
  canFinalize = false,
  canRevise = false,
  canPrint = false,
  onSaveDraft,
  onFinalize,
  onRevise,
  onPrint,
}) {
  const showPrimaryGroup = canSaveDraft || canFinalize;
  const showSecondaryGroup = canRevise || canPrint;

  if (!showPrimaryGroup && !showSecondaryGroup) {
    return null;
  }

  return (
    <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
      {showPrimaryGroup && (
        <>
          <Button variant="outline" onClick={onSaveDraft} disabled={saving || !canSaveDraft}>
            <Icon name="square.and.arrow.down" size={16} />
            {busyAction === 'save' ? 'Сохраняю...' : 'Сохранить черновик'}
          </Button>
          <Button variant="primary" onClick={onFinalize} disabled={saving || !canFinalize}>
            <Icon name="lock.circle" size={16} />
            {busyAction === 'finalize' ? 'Утверждаю...' : 'Утвердить'}
          </Button>
        </>
      )}
      {showSecondaryGroup && (
        <>
          <Button variant="outline" onClick={onRevise} disabled={saving || !canRevise}>
            <Icon name="arrow.triangle.branch" size={16} />
            {busyAction === 'revise' ? 'Создаю исправленную версию...' : 'Создать исправленную версию'}
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
  canFinalize: PropTypes.bool,
  canRevise: PropTypes.bool,
  canPrint: PropTypes.bool,
  onSaveDraft: PropTypes.func.isRequired,
  onFinalize: PropTypes.func.isRequired,
  onRevise: PropTypes.func.isRequired,
  onPrint: PropTypes.func.isRequired,
};
