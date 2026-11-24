import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import type { LabWorklistPage } from '@/types/features/labWorkspace';
import LabQueueWorkbench from '../LabQueueWorkbench';
import LabReportHistoryPanel from '../LabReportHistoryPanel';

const emptyWorklist: LabWorklistPage = {
  entries: [],
  total: 0,
  counts: { actionable: 0, today: 0, overdue: 0, awaiting_specimen: 0, in_review: 0, ready: 0 },
  next_cursor: null,
  date: '2026-11-24',
  timezone: 'Asia/Tashkent',
};

const report = {
  id: 71,
  status: 'FINALIZED',
  patient_snapshot: { full_name: 'SYNTHETIC-PATIENT' },
  template: { name: 'SYNTHETIC-CBC' },
  created_at: '2026-11-24T07:00:00Z',
};

it.each([
  {
    language: 'ru', total: 'Всего', empty: 'На сегодня не найдено лабораторных записей.',
    recent: 'Недавние лабораторные отчёты', critical: 'Критические',
    report: 'Отчёт', finalized: 'Утверждён', noVisit: 'Визит: без визита',
  },
  {
    language: 'uz-Cyrl', total: 'Жами', empty: 'Бугунги кун учун лаборатория ёзувлари топилмади.',
    recent: 'Сўнгги лаборатория ҳисоботлари', critical: 'Критик',
    report: 'Ҳисобот', finalized: 'Тасдиқланган', noVisit: 'Ташриф: ташрифсиз',
  },
  {
    language: 'uz-Latn', total: 'Jami', empty: 'Bugun laboratoriya yozuvlari topilmadi.',
    recent: 'So\'nggi laboratoriya hisobotlari', critical: 'Kritik',
    report: 'Hisobot', finalized: 'Tasdiqlangan', noVisit: 'Tashrif: tashrifsiz',
  },
])('localizes the worklist and report history in $language', async (labels) => {
  await i18n.changeLanguage(labels.language);
  const onFilter = vi.fn();
  const onOpen = vi.fn();

  try {
    render(
      <ThemeProvider>
        <LabQueueWorkbench
          appointments={[]} worklist={emptyWorklist}
          onOpenAppointment={vi.fn()} onQueryChange={vi.fn()}
        />
        <LabReportHistoryPanel
          showRecentReportsBrowser recentReports={[report]}
          onSeverityFilterChange={onFilter} onOpenInstance={onOpen}
        />
      </ThemeProvider>,
    );

    expect(screen.getByText(`${labels.total}: 0`)).toBeVisible();
    expect(screen.getByText(labels.empty)).toBeVisible();
    expect(screen.getByText(labels.recent)).toBeVisible();
    expect(screen.getByText(labels.noVisit)).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: labels.critical }));
    expect(onFilter).toHaveBeenCalledWith('critical');
    fireEvent.click(screen.getByRole('button', {
      name: `${labels.report} SYNTHETIC-CBC, SYNTHETIC-PATIENT, ${labels.finalized}`,
    }));
    expect(onOpen).toHaveBeenCalledWith(report.id);
  } finally {
    cleanup();
    await i18n.changeLanguage('ru');
  }
});
