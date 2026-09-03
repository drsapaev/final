
import { Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import { Download, GitBranch, Lock, Printer, Send } from 'lucide-react';

interface LabReportActionsBarProps {
  saving?: boolean;
  busyAction?: string;
  canSaveDraft?: boolean;
  canFinalize?: boolean;
  canRevise?: boolean;
  canPrint?: boolean;
  canNotify?: boolean;
  onSaveDraft: () => void;
  onFinalize: () => void;
  onRevise: () => void;
  onPrint: () => void;
  onNotify?: () => void;
}

/**
 * P-04 fix: LabReportActionsBar выделен из LabReportWorkbench.
 *
 * WF-round5: Mark Ready убран (был функционально пустой операцией —
 * backend разрешал одинаковые действия для DRAFT/IN_PROGRESS/READY).
 * Теперь только: Save Draft → Finalize (primary), затем: Revise → Print → Notify (primary).
 *
 * P1 fix: добавлена кнопка "Отправить пациенту" — вызывает POST /telegram/send-lab-results
 * для push-уведомления результатов через Telegram бот.
 *
 * Терминология (Вариант B): «Финализировать» → «Утвердить»,
 * «Создать ревизию» → «Создать исправленную версию».
 *
 * STRAT#5: все русские строки мигрированы на t() из labTranslations.
 * i18n-unification: t() теперь берётся из useTranslation() (react-i18next),
 * что обеспечивает реактивность при смене языка.
 */
export default function LabReportActionsBar({
  saving = false,
  busyAction = '',
  canSaveDraft = false,
  canFinalize = false,
  canRevise = false,
  canPrint = false,
  canNotify = false,
  onSaveDraft,
  onFinalize,
  onRevise,
  onPrint,
  onNotify,
}: LabReportActionsBarProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  const showPrimaryGroup = canSaveDraft || canFinalize;
  const showSecondaryGroup = canRevise || canPrint || canNotify;

  if (!showPrimaryGroup && !showSecondaryGroup) {
    return null;
  }

  return (
    <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', flexWrap: 'wrap' }}>
      {showPrimaryGroup && (
        <>
          <Button variant="outline" onClick={onSaveDraft} disabled={saving || !canSaveDraft}>
            <Download size={16} aria-hidden="true" />
            {busyAction === 'save' ? t('actions.saving') : t('actions.save_draft')}
          </Button>
          <Button variant="primary" onClick={onFinalize} disabled={saving || !canFinalize}>
            <Lock size={16} aria-hidden="true" />
            {busyAction === 'finalize' ? t('actions.finalizing') : t('actions.finalize')}
          </Button>
        </>
      )}
      {showSecondaryGroup && (
        <>
          <Button variant="outline" onClick={onRevise} disabled={saving || !canRevise} title={t('actions.revise_title')}>
            <GitBranch size={16} aria-hidden="true" />
            {/* L-L-2 fix: сокращён текст кнопки для tablet-friendly layout.
                Полное название доступно в title-атрибуте. */}
            {busyAction === 'revise' ? t('actions.revising') : t('actions.revise')}
          </Button>
          <Button variant="outline" onClick={onPrint} disabled={saving || !canPrint}>
            <Printer size={16} aria-hidden="true" />
            {busyAction === 'print' ? t('actions.printing') : t('actions.print')}
          </Button>
          {/* P1 fix: Notify patient via Telegram — only for finalized/printed reports */}
          {canNotify && (
            <Button variant="secondary" color="success" onClick={onNotify} disabled={saving || busyAction === 'notify'}>
              <Send size={16} aria-hidden="true" />
              {busyAction === 'notify' ? t('actions.notifying') : t('actions.notify_patient')}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

