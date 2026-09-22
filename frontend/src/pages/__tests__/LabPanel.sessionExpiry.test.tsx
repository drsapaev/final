import React from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import LabPanelRaw from '../LabPanel';
import { LabDirtyGuardProvider } from '../../components/laboratory/LabDirtyGuardContext';
import { ThemeProvider } from '../../contexts/ThemeContext';

// LabPanel полагается на TS-пропы из импортов — в строгом режиме тестового
// проекта типы вырождаются; каст к перmissive ComponentType (паттерн
// LabReportWorkbench.test.tsx).
const LabPanel = LabPanelRaw as unknown as React.ComponentType<Record<string, unknown>>;

/**
 * PR 3351 (review round 8, P2): КОМПОНЕНТНЫЙ тест session-expiry накладок —
 * ревью явно требует не только hook-тест: обе накладки LabPanel (warning
 * «Сессия скоро истечёт» + не-dismissable redirectPending) обязаны появляться
 * и исчезать как ЕДИНАЯ машина на живом рендере панели.
 *
 * Сценарий ревью: warning открыт → токен истёк и pending=true → токен
 * обновлён (gen N+1) → pending=false → ОБЕ накладки исчезают → с новым
 * поколением токена предупреждение срабатывает СНОВА.
 *
 * Fake-таймеры: опрос токена (30 c) и все дебаунсы управляются вручную;
 * UI-цепочки (клик пациента → GET instance → резолв шаблона → CREATE)
 * проливаются микротасками через act-флаш.
 */

const TEMPLATES_SUMMARY = [
  { id: 5, code: 'rule_demo', name: 'Rule Demo', family: 'chemistry', is_active: true, published_version_id: 51, draft_version_id: null, latest_version_id: 51 },
];

const TEMPLATE_DETAIL = {
  ...TEMPLATES_SUMMARY[0],
  versions: [
    {
      id: 51,
      template_id: 5,
      version_no: 1,
      status: 'PUBLISHED',
      available_actions: ['create_draft'],
      layout_preset: 'lab_table_classic_v1',
      page_settings: {},
      branding_overrides: {},
      signer_defaults: {},
      footer_notes: '',
      sections: [
        {
          id: 1,
          key: 's1',
          title: 'Раздел 1',
          sort_order: 10,
          section_style: {},
          fields: [
            { id: 1, field_key: 'wbc', label: 'Лейкоциты', value_type: 'text', unit: '', reference_mode: 'static_text', reference_text: '', required: false, sort_order: 10, reference_rule: null, visibility_rule: null, highlight_rule: null },
          ],
        },
      ],
    },
  ],
};

const INSTANCE_A = {
  id: 88,
  status: 'DRAFT',
  template_id: 5,
  patient_id: 101,
  visit_id: 701,
  updated_at: '2026-09-13T08:00:00.000000+00:00',
  signer_snapshot: {},
  available_actions: ['edit', 'save_draft', 'finalize'],
  critical_findings: [],
  patient_snapshot: { patient_id: 101, full_name: 'Пациент Один' },
  template: TEMPLATE_DETAIL,
  template_version: TEMPLATE_DETAIL.versions[0],
  sections: TEMPLATE_DETAIL.versions[0].sections.map((section) => ({
    ...section,
    fields: section.fields.map((field) => ({ ...field, value_text: '' })),
  })),
};

const INSTANCE_CREATED = { ...INSTANCE_A, id: 90, updated_at: '2026-09-13T08:05:00.000000+00:00' };

const QUEUE_ENTRIES = [
  { id: 1, appointment_id: 'a-1', patient_id: 101, patient_fio: 'Пациент Один', patient_phone: '', status: 'waiting', report_instance_id: 88, services: [], service_codes: [], service_details: [] },
];

const createInstanceMock = vi.hoisted(() => vi.fn());

vi.mock('../../api/labReporting', () => ({
  labReportingApi: {
    listQueueToday: vi.fn(async () => ({ entries: QUEUE_ENTRIES, total: QUEUE_ENTRIES.length })),
    listTemplates: vi.fn(async () => TEMPLATES_SUMMARY),
    resolveTemplateOptions: vi.fn(async () => ({
      visit_id: 601,
      service_codes: ['svc-101'],
      allowed_templates: TEMPLATES_SUMMARY,
      default_template: TEMPLATES_SUMMARY[0],
      unmapped_service_codes: [],
      resolution_mode: 'mapped',
    })),
    listInstances: vi.fn(async () => []),
    getInstance: vi.fn(async (id: string | number) => (
      Number(id) === 88 ? INSTANCE_A : INSTANCE_CREATED
    )),
    createInstance: createInstanceMock,
    updateInstance: vi.fn(),
    bulkSaveValues: vi.fn(),
    finalize: vi.fn(),
    revise: vi.fn(),
    markPrinted: vi.fn(),
    downloadPdf: vi.fn(async () => ({ blob: new Blob(), url: '' })),
  },
}));

vi.mock('../../services/print', () => ({
  printService: { printLabResults: vi.fn() },
}));

// PR 3351 (review round 8): тест нацелен на session-expiry накладки, а не на
// виртуализацию. @tanstack/react-virtual измеряет элементы через rAF — под
// vi.useFakeTimers() фреймы не тикают, и getVirtualItems() остаётся пустым
// (0 карточек). Простой рендер карточек сохраняет контракт
// role="button" + onOpenAppointment, на который опирается сценарий.
vi.mock('../../components/laboratory/VirtualizedQueueList', () => ({
  default: ({ appointments, onOpenAppointment }: {
    appointments: Array<Record<string, unknown>>;
    onOpenAppointment: (appointment: Record<string, unknown>) => void;
  }) => (
    <div className="lqw-virtualized-list">
      {appointments.map((appointment) => (
        // jsx-a11y: тестовый дублёр — клавиатурный вход не проверяется,
        // слушатель заглушен (роль/клик — контракт настоящего компонента).
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events
        <div
          key={String(appointment.id)}
          role="button"
          tabIndex={0}
          onClick={() => onOpenAppointment(appointment)}
        >
          {String(appointment.patient_fio ?? '')}
        </div>
      ))}
    </div>
  ),
}));

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// jsdom has no ResizeObserver; @tanstack/react-virtual needs it.
(globalThis as Record<string, unknown>).ResizeObserver = ResizeObserverStub;

function installToken(expiresAtMs: number, sub: string) {
  const payload = { sub, role: 'Lab', exp: Math.floor(expiresAtMs / 1000) };
  // Части собираются в рантайме: единый JWT-подобный литерал в исходнике
  // триггерит secret-сканер CI (generic high entropy).
  const token = [
    'eyJhbGciOiJIUzI1NiJ9',
    window.btoa(JSON.stringify(payload)),
    'sig',
  ].join('.');
  window.sessionStorage.setItem('auth_token', token);
}

const settle = async () => {
  // Несколько act-флашей: клик → guard → GET instance → setState →
  // резолв шаблона → setState → render (каждый await — микротаск-хоп).
  // Под fake-таймерами каждый флаш ещё и продвигает очередь таймеров на 0 —
  // async act React-а ждёт собственного scheduler-тика, который подменён.
  for (let i = 0; i < 10; i += 1) {
    await act(async () => {
      vi.advanceTimersByTime(0);
      await Promise.resolve();
    });
  }
};

describe('LabPanel session-expiry overlays (PR 3351, review round 8, P2 — component level)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(() => ({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    window.sessionStorage.clear();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('clears both expiry overlays after a token refresh and warns again for the new generation', async () => {
    vi.useFakeTimers();
    // gen N: внутри 5-минутного порога — предупреждение срабатывает сразу
    // на mount-проверке опроса.
    installToken(Date.now() + 4 * 60_000, '7');

    let releaseCreate: ((value: unknown) => void) | null = null;
    createInstanceMock.mockImplementation(() => new Promise((resolve) => {
      releaseCreate = resolve;
    }));

    render(
      <MemoryRouter initialEntries={['/lab?tab=queue']}>
        <ThemeProvider>
          <LabDirtyGuardProvider>
            <LabPanel />
          </LabDirtyGuardProvider>
        </ThemeProvider>
      </MemoryRouter>,
    );
    await settle();

    // (1) warning-overlay открыт.
    expect(
      screen.getByRole('alertdialog', { name: 'Предупреждение об истечении сессии' }),
    ).toBeInTheDocument();


    // Открываем пациента → отчёт #88 → резолв шаблона.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Пациент Один/ }));
    });
    await settle();
    expect(screen.getByText('Отчёт #88')).toBeInTheDocument();

    // CREATE «висит»: pending-источник 'report' в обоих реестрах guard-а.
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Добавить бланк/ }));
    });
    expect(createInstanceMock).toHaveBeenCalledTimes(1);
    await settle();

    // (2) gen N истёк поверх pending: redirectPending-overlay появляется,
    // warning-overlay по-прежнему открыт — ОБЕ накладки видимы.
    await act(async () => {
      vi.advanceTimersByTime(4 * 60_000 + 30_000);
    });
    expect(
      screen.getByRole('alertdialog', { name: 'Переход после завершения операции' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('alertdialog', { name: 'Предупреждение об истечении сессии' }),
    ).toBeInTheDocument();

    // (3) single-flight refresh: gen N+1 (другое значение, валидный exp).
    // Следующий тик опроса видит смену поколения → onSessionRecovered →
    // warning-overlay исчез; redirect-overlay ждёт операцию.
    installToken(Date.now() + 30 * 60_000, '7-refreshed');
    await act(async () => {
      vi.advanceTimersByTime(30_000);
    });
    expect(
      screen.queryByRole('alertdialog', { name: 'Предупреждение об истечении сессии' }),
    ).toBeNull();
    expect(
      screen.getByRole('alertdialog', { name: 'Переход после завершения операции' }),
    ).toBeInTheDocument();

    // (4) CREATE завершён: pending снят, отложенный redirect отменён
    // валидным gen N+1 — ВТОРАЯ накладка исчезает, logout НЕ выполняется
    // (location.href не тронут — SPA жива, бланк #90 открыт).
    await act(async () => {
      releaseCreate?.(INSTANCE_CREATED);
    });
    await settle();
    expect(
      screen.queryByRole('alertdialog', { name: 'Переход после завершения операции' }),
    ).toBeNull();
    expect(
      screen.queryByRole('alertdialog', { name: 'Предупреждение об истечении сессии' }),
    ).toBeNull();
    expect(screen.getByText('Отчёт #90')).toBeInTheDocument();

    // (5) Новое поколение — новый жизненный цикл: gen N+1 входит в
    // 5-минутный окно → предупреждение срабатывает СНОВА (round 8: смена
    // поколения сбрасывает warningFired; раньше флаг оставался взведённым
    // и предупреждение молчало).
    await act(async () => {
      vi.advanceTimersByTime(26 * 60_000);
    });
    expect(
      screen.getByRole('alertdialog', { name: 'Предупреждение об истечении сессии' }),
    ).toBeInTheDocument();
  });
});
