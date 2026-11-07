/**
 * TEMPL-FE-001..004 (audit 3886, ledger group «laboratory template editor
 * async target identity» + «template designer persisted order») — fail-first
 * regressions:
 *
 * TEMPL-FE-001: a deferred catalog reference-range response applied to
 * whatever field OCCUPIED the old indexes — after the operator changed the
 * analyte, moved the field or switched templates, analyte A's range was
 * written into field B / the moved field / another template's draft.
 *
 * TEMPL-FE-002: the deferred delete confirmation captured bare indexes —
 * after a draft context switch while the dialog was pending, confirming
 * deleted whatever section occupied the old index in the NEW draft.
 *
 * TEMPL-FE-003: Move Up/Down swapped only the arrays; buildVersionPayload
 * kept the stale persisted sort_order, so a reloaded/printed template
 * reverted to the pre-move ordering.
 *
 * TEMPL-FE-004: addSection regenerated `section_${length + 1}`, duplicating
 * an existing key after a middle removal (backend UniqueConstraint rejects
 * the whole save); no frontend section-key uniqueness validation existed.
 *
 * Red-first: on the pre-fix source the stale-range writes, the displaced
 * delete, the stale sort_order payload and the duplicate section key all
 * reproduce for the documented reasons.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';

vi.mock('../../../api/labReporting', () => ({
  labReportingApi: {
    listCatalogUnits: vi.fn(),
    listCatalogAnalytes: vi.fn(),
    listCatalogReferenceRanges: vi.fn(),
    createTemplate: vi.fn(),
    createTemplateVersion: vi.fn(),
    updateTemplateVersion: vi.fn(),
    publishTemplateVersion: vi.fn(),
    archiveTemplateVersion: vi.fn(),
    cloneTemplate: vi.fn(),
  },
}));

import { labReportingApi } from '@/api/labReporting';
import LabTemplateWorkbenchRaw from '../LabTemplateWorkbench';
import { buildVersionPayload, nextSectionKey } from '../templateEditor/utils';

const LabTemplateWorkbench = LabTemplateWorkbenchRaw as unknown as React.ComponentType<
  Record<string, unknown>
>;

const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;

function field(key: string, label: string, analyteCode = '', referenceMode = 'static_text') {
  return {
    field_key: key,
    label,
    value_type: 'numeric',
    unit: 'г/л',
    analyte_code: analyteCode,
    reference_mode: referenceMode,
    reference_text: '',
    reference_low: null,
    reference_high: null,
    reference_rule: null,
    visibility_rule: null,
    highlight_rule: null,
    required: false,
    sort_order: 10,
  };
}

function section(key: string, title: string, fields: unknown[], sort_order: number) {
  return { key, title, sort_order, section_style: {}, fields };
}

const TEMPLATE_A = {
  id: 5,
  code: 'tpl_a',
  name: 'Template A',
  family: 'chemistry',
  is_active: true,
  published_version_id: 51,
  draft_version_id: null,
  latest_version_id: 51,
  versions: [
    {
      id: 51,
      template_id: 5,
      version_no: 1,
      status: 'DRAFT',
      available_actions: ['update'],
      layout_preset: 'lab_table_classic_v1',
      page_settings: {},
      branding_overrides: {},
      signer_defaults: {},
      footer_notes: '',
      sections: [
        section('s1', 'Секция 1', [field('f1', 'Гемоглобин', 'HGB', 'catalog'), field('f2', 'Лейкоциты')], 10),
        section('s2', 'Секция 2', [field('f3', 'Глюкоза'), field('f4', 'Холестерин')], 20),
      ],
    },
  ],
};

const TEMPLATE_B = {
  ...TEMPLATE_A,
  id: 6,
  code: 'tpl_b',
  name: 'Template B',
  published_version_id: 61,
  latest_version_id: 61,
  versions: [
    {
      ...TEMPLATE_A.versions[0],
      id: 61,
      template_id: 6,
      sections: [
        section('x1', 'Другая секция 1', [field('g1', 'Другой анализ')], 10),
        section('x2', 'Другая секция 2', [field('g2', 'Ещё анализ')], 20),
      ],
    },
  ],
};

function workbench(template: unknown) {
  return (
    <ThemeProvider>
      <LabTemplateWorkbench
        templates={[template]}
        selectedTemplate={template}
        onSelectTemplate={vi.fn()}
        onTemplatesChanged={vi.fn(async () => {})}
        notify={vi.fn()}
      />
    </ThemeProvider>
  );
}

// Section 0 is expanded by default (useState(new Set([0]))); expanding it
// again would COLLAPSE it. Only non-first sections need an explicit click.
function expandSection(title: string) {
  const header = screen.getByRole('button', { name: new RegExp(`Секция: ${title}`) });
  if (!header.getAttribute('aria-expanded')?.match(/true/i)) {
    fireEvent.click(header);
  }
}

function expandField(label: string) {
  fireEvent.click(screen.getByRole('button', { name: new RegExp(`Поле: ${label}`) }));
}

function referenceTextInput(label: string): HTMLInputElement {
  void label;
  // The field card's own reference_text input is the FIRST «Текст нормы»
  // in the DOM; the structured ReferenceRuleEditor renders another one.
  return screen.getAllByLabelText('Текст нормы')[0] as HTMLInputElement;
}

function sectionActionButton(title: string, action: string): HTMLElement {
  // Action buttons carry plain aria-labels («Удалить секцию», «Переместить
  // секцию вверх», ...); disambiguate by the owning section header's DOM
  // position — each section card follows its header in document order.
  const header = screen.getByRole('button', { name: new RegExp(`Секция: ${title}`) }) as HTMLButtonElement;
  const card = header.closest('div');
  const buttons = (card ? [card, ...Array.from(card.querySelectorAll('button'))] : []) as HTMLElement[];
  const all = screen.getAllByRole('button', { name: action });
  const headerOrder = Array.from(document.querySelectorAll('button'))
    .filter((b) => /Секция:/.test(b.getAttribute('aria-label') || ''));
  const sectionIndex = headerOrder.indexOf(header);
  void buttons;
  // Sections are numbered by document order; each section owns exactly one
  // button with this action label.
  return all[sectionIndex];
}

function fieldActionButton(sectionTitle: string, fieldLabel: string, action: string): HTMLElement {
  const header = screen.getByRole('button', { name: new RegExp(`Поле: ${fieldLabel}`) });
  void header; void sectionTitle;
  // Field action buttons are plain-labeled too; within the expanded section
  // the fields are in document order — use the Nth match of the action.
  return screen.getAllByRole('button', { name: action })[
    Array.from(document.querySelectorAll('button'))
      .filter((b) => /Поле:/.test(b.getAttribute('aria-label') || ''))
      .findIndex((b) => b === header)
  ];
}

async function confirmDialogButton(name: string): Promise<HTMLElement> {
  // The ConfirmDialog is portal-rendered AFTER the main content, so its
  // button is the LAST match for the label.
  const all = await screen.findAllByRole('button', { name });
  return all[all.length - 1];
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.listCatalogUnits.mockResolvedValue([]);
  mockedApi.listCatalogAnalytes.mockResolvedValue([]);
  mockedApi.createTemplateVersion.mockResolvedValue({ id: 99 });
  mockedApi.updateTemplateVersion.mockResolvedValue({ id: 99 });
  mockedApi.publishTemplateVersion.mockResolvedValue({ id: 99 });
});

describe('TEMPL-FE-001 — a deferred catalog range applies only to its initiating field', () => {
  it('drops the stale range after the analyte changed while the request was pending (pre-fix: written into the field)', async () => {
    let releaseRanges: (ranges: unknown[]) => void = () => {};
    mockedApi.listCatalogReferenceRanges.mockImplementation(
      () => new Promise((resolve) => { releaseRanges = resolve; })
    );

    render(workbench(TEMPLATE_A));
    expandSection('Секция 1');
    expandField('Гемоглобин');

    // The catalog load for analyte HGB starts and hangs.
    fireEvent.click(screen.getByRole('button', { name: /Загрузить из каталога/ }));
    await waitFor(() => expect(mockedApi.listCatalogReferenceRanges).toHaveBeenCalled());

    // The operator changes the analyte to LBC while the read is pending.
    fireEvent.change(screen.getByLabelText('Код анализируемого показателя'), { target: { value: 'LBC' } });

    // HGB's ranges resolve late.
    releaseRanges([{ text: 'HGB 130-170', low: 130, high: 170 }]);
    await new Promise((resolve) => { setTimeout(resolve, 100); });

    // The stale HGB range must NOT be written into the LBC field.
    expect(referenceTextInput('Гемоглобин').value).toBe('');
  });

  it('control: the unchanged target still receives its own range', async () => {
    mockedApi.listCatalogReferenceRanges.mockResolvedValue([{ text: 'HGB 130-170', low: 130, high: 170 }]);

    render(workbench(TEMPLATE_A));
    expandSection('Секция 1');
    expandField('Гемоглобин');

    fireEvent.click(screen.getByRole('button', { name: /Загрузить из каталога/ }));

    await waitFor(() => {
      expect(referenceTextInput('Гемоглобин').value).toBe('HGB 130-170');
    });
  });

  it('drops the stale range after the field moved while the request was pending (pre-fix: written into the displaced field)', async () => {
    let releaseRanges: (ranges: unknown[]) => void = () => {};
    mockedApi.listCatalogReferenceRanges.mockImplementation(
      () => new Promise((resolve) => { releaseRanges = resolve; })
    );

    render(workbench(TEMPLATE_A));
    expandSection('Секция 1');
    expandField('Гемоглобин');

    // The catalog load for the HGB field starts and hangs.
    fireEvent.click(screen.getByRole('button', { name: /Загрузить из каталога/ }));
    await waitFor(() => expect(mockedApi.listCatalogReferenceRanges).toHaveBeenCalled());

    // The operator moves Лейкоциты up: it now occupies index 0.
    fireEvent.click(fieldActionButton('Секция 1', 'Лейкоциты', 'Переместить поле вверх'));

    // HGB's ranges resolve late — they must not land in Лейкоциты.
    releaseRanges([{ text: 'HGB 130-170', low: 130, high: 170 }]);
    await new Promise((resolve) => { setTimeout(resolve, 100); });

    // Лейкоциты (the displaced occupant of the old index) keeps its state.
    // Лейкоциты (the displaced occupant of the old index) keeps its state:
    // NO «Текст нормы» input in the document carries the stale HGB range.
    const allReferenceInputs = screen.getAllByLabelText('Текст нормы') as HTMLInputElement[];
    expect(allReferenceInputs.every((el) => el.value !== 'HGB 130-170')).toBe(true);
  });
});

describe('TEMPL-FE-002 — a confirmed delete targets the captured identity, never a displaced index', () => {
  it('drops the section removal after the draft switched to another template while the dialog was pending (pre-fix: deleted the displaced section of the NEW draft)', async () => {
    // The real ConfirmDialog renders its own confirm button; we drive the
    // flow by clicking that button after the rerender.

    const { rerender } = render(workbench(TEMPLATE_A));

    // Click the trash on Секция 2 — the confirm dialog opens and hangs.
    fireEvent.click(sectionActionButton('Секция 2', 'Удалить секцию'));
    const confirmButton = await confirmDialogButton('Удалить секцию');

    // A parent-driven template switch rehydrates the draft while the
    // dialog is pending (the modal does not block programmatic transitions).
    rerender(workbench(TEMPLATE_B));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Секция: Другая секция 2/ })).toBeInTheDocument();
    });

    // The operator confirms the OLD dialog.
    fireEvent.click(confirmButton);
    await new Promise((resolve) => { setTimeout(resolve, 100); });

    // The new draft keeps BOTH its sections: the stale confirmation must
    // not remove «Другая секция 2» (the displaced index occupant).
    expect(screen.getByRole('button', { name: /Секция: Другая секция 1/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Секция: Другая секция 2/ })).toBeInTheDocument();
  });
});

describe('TEMPL-FE-003 — persisted sort_order matches the visual order', () => {
  it('buildVersionPayload renumbers section and field sort_order from array positions (pre-fix: stale persisted values)', () => {
    const draft = {
      layout_preset: 'lab_table_classic_v1',
      page_settings: {},
      branding_overrides: {},
      signer_defaults: {},
      footer_notes: '',
      sections: [
        // Visual order after a Move Up: s2 first, s1 second — but the
        // sections still carry their ORIGINAL persisted sort_order values.
        section('s2', 'Секция 2', [
          { ...field('f4', 'Холестерин'), sort_order: 20 },
          { ...field('f3', 'Глюкоза'), sort_order: 10 },
        ], 20),
        section('s1', 'Секция 1', [
          { ...field('f2', 'Лейкоциты'), sort_order: 20 },
          { ...field('f1', 'Гемоглобин'), sort_order: 10 },
        ], 10),
      ],
    };

    const payload = buildVersionPayload(draft as never);

    expect(payload.sections[0].key).toBe('s2');
    expect(payload.sections[0].sort_order).toBe(10);
    expect(payload.sections[1].key).toBe('s1');
    expect(payload.sections[1].sort_order).toBe(20);
    expect(payload.sections[0].fields[0].field_key).toBe('f4');
    expect(payload.sections[0].fields[0].sort_order).toBe(10);
    expect(payload.sections[0].fields[1].field_key).toBe('f3');
    expect(payload.sections[0].fields[1].sort_order).toBe(20);
  });

  it('component: moving a section up and saving persists the new visual order', async () => {
    render(workbench(TEMPLATE_A));

    // Move Секция 2 up.
    fireEvent.click(sectionActionButton('Секция 2', 'Переместить секцию вверх'));

    // Save the draft.
    fireEvent.click(screen.getByRole('button', { name: /Сохранить черновик/ }));

    await waitFor(() => expect(mockedApi.updateTemplateVersion).toHaveBeenCalled());
    const payload = mockedApi.updateTemplateVersion.mock.calls[0][1];
    expect(payload.sections[0].key).toBe('s2');
    expect(payload.sections[0].sort_order).toBe(10);
    expect(payload.sections[1].key).toBe('s1');
    expect(payload.sections[1].sort_order).toBe(20);
  });
});

describe('TEMPL-FE-004 — section keys never collide', () => {
  it('addSection after a middle removal picks the smallest unused key (pre-fix: duplicates section_3)', () => {
    expect(nextSectionKey(['section_1', 'section_3'])).toBe('section_2');
    expect(nextSectionKey(['section_2', 'section_3'])).toBe('section_1');
    expect(nextSectionKey([])).toBe('section_1');
    expect(nextSectionKey(['section_1', 'section_2', 'section_3'])).toBe('section_4');
  });

  it('component: remove-then-add yields a unique section key', async () => {
    render(workbench({
      ...TEMPLATE_A,
      versions: [{
        ...TEMPLATE_A.versions[0],
        sections: [
          section('section_1', 'Раздел 1', [field('f1', 'Анализ 1')], 10),
          section('section_2', 'Раздел 2', [field('f2', 'Анализ 2')], 20),
          section('section_3', 'Раздел 3', [field('f3', 'Анализ 3')], 30),
        ],
      }],
    }));

    // Remove the middle section (confirm the dialog).
    fireEvent.click(sectionActionButton('Раздел 2', 'Удалить секцию'));
    fireEvent.click(await confirmDialogButton('Удалить секцию'));
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Секция: Раздел 2/ })).not.toBeInTheDocument();
    });

    // Add a new section: its key must be the unused section_2, NOT a
    // duplicate of the existing section_3.
    fireEvent.click(screen.getByRole('button', { name: 'Добавить секцию' }));

    // Expand every collapsed section so all key inputs are visible.
    document
      .querySelectorAll('button[aria-expanded="false"]')
      .forEach((b) => {
        if (/^Секция:/.test(b.getAttribute('aria-label') || '')) fireEvent.click(b);
      });

    await waitFor(() => {
      const keyInputs = screen.getAllByLabelText('Ключ секции').map((el) => (el as HTMLInputElement).value);
      expect(keyInputs).toEqual(expect.arrayContaining(['section_1', 'section_3', 'section_2']));
      const unique = new Set(keyInputs);
      expect(unique.size).toBe(keyInputs.length);
    });
  });

  it('blocks save when a manual key edit duplicates another section key (pre-fix: reached the backend UniqueConstraint)', async () => {
    const notify = vi.fn();
    render(
      <ThemeProvider>
        <LabTemplateWorkbench
          templates={[TEMPLATE_A]}
          selectedTemplate={TEMPLATE_A}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          notify={notify}
        />
      </ThemeProvider>
    );

    expandSection('Секция 2');
    // Manually collide the section key with Секция 1 (the SECOND «Ключ
    // секции» input belongs to Секция 2 — section 1 is expanded by default).
    const keyInputs = screen.getAllByLabelText('Ключ секции') as HTMLInputElement[];
    fireEvent.change(keyInputs[keyInputs.length - 1], { target: { value: 's1' } });

    fireEvent.click(screen.getByRole('button', { name: /Сохранить черновик/ }));

    await waitFor(() => expect(notify).toHaveBeenCalledWith('error', expect.stringContaining('s1')));
    expect(mockedApi.updateTemplateVersion).not.toHaveBeenCalled();
  });
});
