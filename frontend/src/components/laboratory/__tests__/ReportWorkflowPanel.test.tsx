import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import i18n from '../../../i18n';
import ReportWorkflowPanel, { ReportWorkflowDialog } from '../ReportWorkflowPanel';

function renderWorkflow(report: Record<string, unknown>) {
  const onReview = vi.fn();
  const onPrompt = vi.fn();
  render(<ReportWorkflowPanel
    report={{ managed_release: true, status: 'IN_PROGRESS', ...report }}
    canSubmit
    disabled={false}
    onReview={onReview}
    onPrompt={onPrompt}
  />);
  return { onReview, onPrompt };
}

afterEach(async () => {
  cleanup();
  await i18n.changeLanguage('ru');
});

describe('managed report hold guidance', () => {
  it.each([
    ['ru', 'Не все связанные пробы приняты', 'В разделе «Пробы» проверьте статус каждой связанной пробы и доступные для неё действия.'],
    ['uz-Cyrl', 'Камида битта боғланган намуна ҳали қабул қилинмаган', '«Намуналар» бўлимида ҳар бир боғланган намунанинг ҳолати ва унга оид амалларни текширинг.'],
    ['uz-Latn', 'Kamida bitta bog‘langan namuna hali qabul qilinmagan', '«Namunalar» bo‘limida har bir bog‘langan namunaning holati va unga oid amallarni tekshiring.'],
  ])('shows why specimens prevent release and where to act in %s', async (language, reason, guidance) => {
    await i18n.changeLanguage(language);
    renderWorkflow({ release_holds: ['specimen_not_accepted'], available_actions: ['preview'] });

    const alert = within(screen.getByRole('alert'));
    expect(alert.getByText(reason)).toBeVisible();
    expect(alert.getByText(guidance)).toBeVisible();
  });

  it('directs a permitted QC operator to record the updated disposition without changing submission', () => {
    const { onReview, onPrompt } = renderWorkflow({
      release_holds: ['qc_rejected'],
      available_actions: ['preview', 'edit', 'submit_review', 'record_qc'],
      workflow_events: [{ id: 1, kind: 'qc_recorded', actor_name: 'SYNTHETIC-OPERATOR',
        occurred_at: '2026-09-26T08:00:00Z', evidence: { qc: { status: 'rejected' } } }],
    });

    expect(screen.getByText('Контроль качества неприемлем')).toBeVisible();
    expect(screen.getByText('Разберите причину отклонения, затем запишите актуальный итог через «Записать контроль качества».')).toBeVisible();
    expect(screen.getByText('Итог контроля качества · Неприемлемо')).toBeVisible();
    const recordQc = screen.getByRole('button', { name: 'Записать контроль качества' });
    fireEvent.click(recordQc);
    fireEvent.click(screen.getByRole('button', { name: 'Передать на проверку' }));
    expect(onPrompt).toHaveBeenCalledWith('record_qc', recordQc);
    expect(onReview).toHaveBeenCalledWith('submit_review');
  });

  it('names the record QC action when the authorized operator has no disposition', () => {
    renderWorkflow({ release_holds: ['qc_missing'], available_actions: ['preview', 'edit', 'record_qc'] });

    expect(screen.getByText('Запишите фактический итог через «Записать контроль качества».')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Записать контроль качества' })).toBeEnabled();
  });

  it('points to an authorized QC operator when the current user cannot record QC', () => {
    renderWorkflow({ release_holds: ['qc_missing'], available_actions: ['preview', 'edit', 'submit_review'] });

    expect(screen.getByText('Итог контроля качества ещё не записан')).toBeVisible();
    expect(screen.getByText(/Попросите сотрудника с правом записи контроля качества/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Записать контроль качества' })).not.toBeInTheDocument();
  });

  it.each(['IN_REVIEW', 'REVIEWED'])('offers the actual reviewer action in %s before suggesting edits', (status) => {
    const { onPrompt } = renderWorkflow({
      status,
      release_holds: ['review_evidence_changed', 'qc_missing', 'specimen_result_mismatch'],
      available_actions: ['preview', 'return_to_draft'],
    });

    expect(screen.getAllByText(/Выберите «Вернуть в черновик»/)).toHaveLength(1);
    expect(screen.queryByText(/Попросите сотрудника с правом записи контроля качества/)).not.toBeInTheDocument();
    const returnToDraft = screen.getByRole('button', { name: 'Вернуть в черновик' });
    fireEvent.click(returnToDraft);
    expect(onPrompt).toHaveBeenCalledWith('return_to_draft', returnToDraft);
    expect(screen.queryByRole('button', { name: 'Подтвердить проверку' })).not.toBeInTheDocument();
  });

  it('explains who can return a locked report for repeat review', () => {
    renderWorkflow({ status: 'REVIEWED', release_holds: ['review_evidence_changed'], available_actions: ['preview'] });

    expect(screen.getByText(/Попросите сотрудника с правом проверки вернуть бланк в черновик/)).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Вернуть в черновик' })).not.toBeInTheDocument();
  });

  it('guides editable reports back to the accepted specimen for a mismatched result', () => {
    renderWorkflow({ release_holds: ['specimen_result_mismatch'], available_actions: ['preview', 'edit'] });

    expect(screen.getByText(/Источник измерения не совпадает с принятой пробой/)).toBeVisible();
    expect(screen.getByText(/Сверьте привязку в разделе «Пробы»/)).toBeVisible();
  });

  it.each(['instrument_warning', 'unusual_change'])(
    'offers the reviewer a documented resolution for %s', hold => {
      const { onReview, onPrompt } = renderWorkflow({
        status: 'IN_REVIEW', release_holds: [hold], available_actions: ['review', 'return_to_draft'],
      });
      expect(screen.getByText(/укажите, что проверили и какое решение приняли/)).toBeVisible();
      const review = screen.getByRole('button', { name: 'Подтвердить проверку' });
      expect(review).toBeEnabled();
      fireEvent.click(review);
      expect(onPrompt).toHaveBeenCalledWith('review', review);
      expect(onReview).not.toHaveBeenCalled();
    },
  );

  it('keeps QC prerequisites in force when a reviewer needs to document a finding', () => {
    renderWorkflow({ status: 'IN_REVIEW', release_holds: ['instrument_warning', 'qc_missing'],
      available_actions: ['review', 'return_to_draft'] });
    expect(screen.getByRole('button', { name: 'Подтвердить проверку' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Вернуть в черновик' })).toBeEnabled();
  });

  it('submits a flagged unusual change with the documented return reason', () => {
    const onSubmit = vi.fn();
    render(<ThemeProvider>
      <ReportWorkflowDialog action="return_to_draft" saving={false} onClose={vi.fn()} onSubmit={onSubmit} />
    </ThemeProvider>);

    const submit = screen.getByRole('button', { name: 'Вернуть в черновик' });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Отметить необычную динамику' }));
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Причина' }), { target: { value: '  SYNTHETIC finding  ' } });
    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledWith({ reason: 'SYNTHETIC finding', unusual_change: true });
  });

  it('keeps unknown reasons visible and skips managed controls for legacy reports', () => {
    const { unmount } = render(<ReportWorkflowPanel
      report={{ managed_release: true, release_holds: ['future_hold'] }}
      canSubmit
      disabled={false}
      onReview={vi.fn()}
      onPrompt={vi.fn()}
    />);
    expect(screen.getByText('Проверьте условия выпуска')).toBeVisible();
    expect(screen.queryByText('Следующие шаги')).not.toBeInTheDocument();
    unmount();

    renderWorkflow({ managed_release: false, release_holds: ['qc_missing'], available_actions: ['record_qc'] });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Записать контроль качества' })).not.toBeInTheDocument();
  });
});
