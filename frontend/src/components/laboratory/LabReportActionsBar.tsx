
import { Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import { Download, Eye, GitBranch, Lock, Printer, Send } from 'lucide-react';

interface LabReportActionsBarProps {
  saving?: boolean;
  busyAction?: string;
  canSaveDraft?: boolean;
  canFinalize?: boolean;
  canRevise?: boolean;
  canPrint?: boolean;
  canNotify?: boolean;
  /** PR8: серверный PDF-preview до утверждения (Admin/Lab, без side-effects). */
  canPreview?: boolean;
  onSaveDraft: () => void;
  onFinalize: () => void;
  onRevise: () => void;
  onPrint: () => void;
  onNotify?: () => void;
  onPreview?: () => void;
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
 * PR8 (codex-lab-workflow-hardening-plan): кнопка «Предпросмотр» —
 * серверный A4-рендер того же движка, что пойдёт на печать, ДО
 * утверждения. Разрешение приходит из backend available_actions
 * ('preview', только неутверждённые бланки); preview не вызывает
 * mark-printed и не меняет статус.
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
  canPreview = false,
  onSaveDraft,
  onFinalize,
  onRevise,
  onPrint,
  onNotify,
  onPreview,
}: LabReportActionsBarProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  const showPrimaryGroup = canSaveDraft || canFinalize;
  const showSecondaryGroup = canRevise || canPrint || canNotify || canPreview;

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
          {/* PR8: предпросмотр сохранённых значений до утверждения —
              серверный A4-рендер, watermark «Черновик», без side-effects. */}
          {canPreview && (
            <Button
              variant="outline"
              onClick={onPreview}
              disabled={saving || busyAction === 'preview'}
              title={t('actions.preview_title')}
            >
              <Eye size={16} aria-hidden="true" />
              {busyAction === 'preview' ? t('actions.previewing') : t('actions.preview')}
            </Button>
          )}
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

