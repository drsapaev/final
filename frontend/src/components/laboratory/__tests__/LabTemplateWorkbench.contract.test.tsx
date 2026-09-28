import fs from 'fs';
import path from 'path';

import { describe, expect, it } from 'vitest';

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, '../../..');

// L-H-6 fix: helper-функции вынесены в templateEditor/utils.js.
// Контракт-тест обновлён, чтобы читать оба файла.
const source = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/LabTemplateWorkbench.tsx'),
  'utf8'
);

const utilsSource = fs.readFileSync(
  path.join(ROOT, 'components/laboratory/templateEditor/utils.ts'),
  'utf8'
);

function blockFromFile(fileContent: string, startMarker: string, endMarker: string) {
  const start = fileContent.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = fileContent.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return fileContent.slice(start, end);
}

describe('LabTemplateWorkbench template version command contract', () => {
  it('pins the archive target before a deferred save-and-continue guard', () => {
    const archiveBlock = blockFromFile(
      source,
      'async function handleArchiveTemplate() {',
      'async function handleCloneTemplate() {',
    );

    expect(archiveBlock).toContain('const archiveVersionId =');
    expect(archiveBlock).toContain('archiveTemplateVersion(archiveVersionId)');
    expect(archiveBlock).not.toContain('archiveTemplateVersion((activeVersion');
  });

  it('uses backend-owned template version actions instead of status for draft creation', () => {
    // helper теперь в utils.js
    const helperBlock = blockFromFile(
      utilsSource,
      'export function hasTemplateVersionAction(version: Record<string, unknown> | null | undefined, action: string) {',
      'export function parseJsonInput(value: string | null | undefined) {'
    );
    const ensureDraftBlock = blockFromFile(
      source,
      'async function ensureDraftVersion(): Promise<string | number> {',
      'async function handleSaveTemplate() {'
    );

    expect(helperBlock).toContain('version?.available_actions');
    expect(helperBlock).toContain('TEMPLATE_VERSION_ACTION_CAN_FIELD');
    expect(helperBlock).toContain('return false;');
    expect(ensureDraftBlock).toContain('hasTemplateVersionAction(activeVersion, \'update\')');
    expect(ensureDraftBlock).toContain('hasTemplateVersionAction(activeVersion, \'create_draft\')');
    expect(ensureDraftBlock).toContain('labReportingApi.createTemplateVersion');
    expect(ensureDraftBlock).not.toContain('activeVersion?.status === \'DRAFT\'');
  });

  it('UX-AUDIT-QW2: Reset button requires confirm dialog before discarding draft', () => {
    // QW2 fix: кнопка «Отменить» (Reset) ранее мгновенно сбрасывала черновик
    // через notify('info', ...). Должна вызывать useConfirm() — как Archive и Publish.
    const resetBlock = source.indexOf('Отменить');
    expect(resetBlock).toBeGreaterThan(-1);
    // Находим блок onClick рядом с кнопкой «Отменить»
    const onClickStart = source.lastIndexOf('onClick={async () => {', resetBlock);
    expect(onClickStart).toBeGreaterThan(-1);
    const onClickEnd = source.indexOf('}}', onClickStart);
    const onClickBody = source.slice(onClickStart, onClickEnd);

    expect(onClickBody).toContain('await confirm(');
    // STRAT#10: строка мигрирована на t('confirm.reset_draft_title')
    expect(onClickBody).toContain("t('confirm.reset_draft_title')");
    expect(onClickBody).toContain("intent: 'warning'");
    expect(onClickBody).toContain('if (!ok) return;');
    // Не должно быть мгновенного setDraftVersion без confirm
    const setDraftIdx = onClickBody.indexOf('setDraftVersion(hydrateVersion(');
    const confirmIdx = onClickBody.indexOf('await confirm(');
    expect(setDraftIdx).toBeGreaterThan(confirmIdx);
  });

  it('STRAT#10: both confirm dialogs (archive + reset) use t() from unified i18n', () => {
    // STRAT#10: archive и reset dialogs мигрированы на t()
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');

    // Archive dialog
    expect(source).toContain("t('confirm.archive_title')");
    expect(source).toContain("t('confirm.archive_message')");
    expect(source).toContain("t('confirm.archive_description')");
    expect(source).toContain("t('confirm.archive_confirm')");

    // Reset dialog
    expect(source).toContain("t('confirm.reset_draft_title')");
    expect(source).toContain("t('confirm.reset_draft_message')");
    expect(source).toContain("t('confirm.reset_draft_description')");
    expect(source).toContain("t('confirm.reset_confirm')");

    // Общий cancel label
    expect(source).toContain("t('confirm.cancel')");

    // Больше нет хардкоженных русских строк в confirm() calls
    expect(source).not.toContain("title: 'Архивирование версии шаблона'");
    expect(source).not.toContain("title: 'Сброс черновика'");
    expect(source).not.toContain("confirmLabel: 'Архивировать'");
    expect(source).not.toContain("confirmLabel: 'Сбросить'");
    expect(source).not.toContain("cancelLabel: 'Отмена'");
  });

  it('STRAT#15: tab labels and action buttons use t() from unified i18n', () => {
    // STRAT#15: tab labels + action buttons мигрированы на t()
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');

    // Title
    expect(source).toContain("t('template.title')");
    // Action buttons
    expect(source).toContain("t('template.new_template')");
    expect(source).toContain("t('template.clone')");
    expect(source).toContain("t('common.save_draft')");
    expect(source).toContain("t('template.publish')");
    expect(source).toContain("t('template.archive')");
    // Tab labels — uses dynamic key pattern t(`template.${tab.id}_tab`)
    expect(source).toContain('t(`template.${tab.id}_tab`)');

    // Больше нет хардкоженных русских строк для tabs/buttons
    expect(source).not.toContain('>Шаблоны<');
    expect(source).not.toContain('>Новый<');
    expect(source).not.toContain('>Клонировать<');
    expect(source).not.toContain('>Опубликовать<');
    expect(source).not.toContain('>Архивировать<');
    expect(source).not.toContain('{tab.label}');
  });

  it('STRAT#17: notify() calls use t() for all hardcoded Russian messages', () => {
    // STRAT#17: все notify() с hardcoded русскими строками мигрированы на t()
    expect(source).toContain("from '../../i18n/useTranslation'");
    expect(source).toContain('import { useTranslation }');

    // Success messages
    expect(source).toContain("t('success.template_created')");
    expect(source).toContain("t('success.template_draft_saved')");
    expect(source).toContain("t('success.template_published')");
    expect(source).toContain("t('success.template_archived')");
    expect(source).toContain("t('success.template_cloned')");
    expect(source).toContain("t('success.norm_loaded_from_catalog')");

    // Error messages
    expect(source).toContain("t('errors.catalog_load_failed')");
    expect(source).toContain("t('errors.template_code_name_required')");
    expect(source).toContain("t('errors.select_template_first')");
    expect(source).toContain("t('errors.select_template')");
    expect(source).toContain("t('errors.select_version_for_archive')");
    expect(source).toContain("t('errors.select_template_for_copy')");
    expect(source).toContain("t('errors.validation_errors')");
    expect(source).toContain("t('errors.no_norm_in_catalog')");
    expect(source).toContain("t('errors.catalog_load_error')");

    // Больше нет хардкоженных русских строк в notify() calls
    expect(source).not.toContain("'Не удалось загрузить лабораторный каталог.'");
    expect(source).not.toContain("'Укажите код и название шаблона.'");
    expect(source).not.toContain("'Шаблон создан.'");
    expect(source).not.toContain("'Черновик шаблона сохранён.'");
    expect(source).not.toContain("'Версия шаблона опубликована.'");
    expect(source).not.toContain("'Версия шаблона архивирована.'");
    expect(source).not.toContain("'Копия шаблона создана.'");
  });
});

// ─── PR4: behavioral tests — валидация текущего draft до любых запросов ───
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach as rtlBeforeEach } from 'vitest';
import LabTemplateWorkbenchRaw from '../LabTemplateWorkbench';
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

const mockedApi = labReportingApi as unknown as Record<string, ReturnType<typeof vi.fn>>;

const ruleTemplateFixture = {
  id: 5,
  code: 'rule_demo',
  name: 'Rule Demo',
  family: 'chemistry',
  description: '',
  is_active: true,
  published_version_id: 51,
  draft_version_id: null,
  latest_version_id: 51,
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
          key: 's1',
          title: 'Раздел 1',
          sort_order: 10,
          section_style: {},
          fields: [
            {
              field_key: 'hgb',
              label: 'Гемоглобин',
              value_type: 'numeric',
              unit: 'г/л',
              reference_mode: 'static_text',
              reference_text: '110-160',
              required: false,
              sort_order: 10,
              reference_rule: {
                cases: [
                  { when: { source: 'patient.sex', op: 'eq', value: 'M' }, text: '1-10', low: 1, high: 10 },
                ],
                default: { text: '1-10', low: 1, high: 10 },
              },
              visibility_rule: null,
              highlight_rule: null,
            },
          ],
        },
      ],
    },
  ],
};

function renderRuleTemplateWorkbench() {
  return render(
    <ThemeProvider>
      <LabTemplateWorkbenchRaw
        templates={[ruleTemplateFixture]}
        selectedTemplate={ruleTemplateFixture}
        onSelectTemplate={vi.fn()}
        onTemplatesChanged={vi.fn(async () => {})}
        notify={vi.fn()}
      />
    </ThemeProvider>
  );
}

function expandFirstFieldEditor() {
  fireEvent.click(screen.getByRole('button', { name: /Поле: Гемоглобин/ }));
}

describe('LabTemplateWorkbench draft rule validation (PR4)', () => {
  rtlBeforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listCatalogUnits.mockResolvedValue([]);
    mockedApi.listCatalogAnalytes.mockResolvedValue([]);
    mockedApi.listCatalogReferenceRanges.mockResolvedValue([]);
    mockedApi.createTemplateVersion.mockResolvedValue({ id: 52 });
    mockedApi.updateTemplateVersion.mockResolvedValue({ id: 52 });
    mockedApi.publishTemplateVersion.mockResolvedValue({ id: 52 });
  });

  it('blocks publish when the edited rule becomes low >= high (validates draft text, not stale object)', async () => {
    renderRuleTemplateWorkbench();
    expandFirstFieldEditor();

    // Пользователь меняет нижнюю границу кейса с 1 на 10 (1..10 -> 10..1).
    fireEvent.change(screen.getByLabelText('Нижняя граница нормы'), {
      target: { value: '10' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Опубликовать' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(mockedApi.createTemplateVersion).not.toHaveBeenCalled();
    expect(mockedApi.updateTemplateVersion).not.toHaveBeenCalled();
    expect(mockedApi.publishTemplateVersion).not.toHaveBeenCalled();
  });

  it('reports invalid rule JSON inline before any request and keeps the typed text', async () => {
    renderRuleTemplateWorkbench();
    expandFirstFieldEditor();

    // Developer path: raw JSON textarea внутри structured editor.
    fireEvent.click(screen.getByText('Raw JSON (для продвинутых)'));
    fireEvent.change(screen.getByLabelText('JSON правил нормы'), {
      target: { value: '{invalid' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить черновик' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByRole('alert').textContent).toContain('Гемоглобин');
    expect(mockedApi.createTemplateVersion).not.toHaveBeenCalled();
    expect(mockedApi.updateTemplateVersion).not.toHaveBeenCalled();
    // Введённый текст не потерян.
    expect((screen.getByLabelText('JSON правил нормы') as HTMLTextAreaElement).value).toBe('{invalid');
  });
});

describe('LabTemplateWorkbench create template flow (PR5)', () => {
  rtlBeforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listCatalogUnits.mockResolvedValue([]);
    mockedApi.listCatalogAnalytes.mockResolvedValue([]);
  });

  it('guards creation before POST and refreshes exactly the returned id without a second guarded selection', async () => {
    const onSelectTemplate = vi.fn();
    const onTemplatesChanged = vi.fn(async (_preferredTemplateId?: string | number | null) => {});
    const guardTransition = vi.fn((transition: () => void | Promise<void>) => {
      void transition();
      return true;
    });
    mockedApi.createTemplate.mockResolvedValue({
      id: 9,
      code: 'new_rule_t',
      name: 'Новый шаблон правил',
      family: 'chemistry',
    });

    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[]}
          selectedTemplate={null}
          onSelectTemplate={onSelectTemplate}
          onTemplatesChanged={onTemplatesChanged}
          guardTransition={guardTransition}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: 'Новый' }));
    fireEvent.change(screen.getByLabelText('Код шаблона'), { target: { value: 'new_rule_t' } });
    fireEvent.change(screen.getByLabelText('Название шаблона'), { target: { value: 'Новый шаблон правил' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    await waitFor(() => expect(mockedApi.createTemplate).toHaveBeenCalled());

    expect(guardTransition).toHaveBeenCalledTimes(1);
    expect(onTemplatesChanged).toHaveBeenCalledWith(9);
    expect(onSelectTemplate).not.toHaveBeenCalled();
  });

  it('Cancel keeps both the dirty template draft and new-template form without sending POST', async () => {
    const guardTransition = vi.fn((_transition: () => void | Promise<void>) => {
      // Models the guard dialog Cancel action: the transition is not run.
      return false;
    });

    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture]}
          selectedTemplate={ruleTemplateFixture}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          guardTransition={guardTransition}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    expandFirstFieldEditor();
    const draftInput = screen.getByLabelText('Название поля');
    fireEvent.change(draftInput, { target: { value: 'Гемоглобин, изменённый' } });

    fireEvent.click(screen.getByRole('button', { name: 'Новый' }));
    const codeInput = screen.getByLabelText('Код шаблона');
    const nameInput = screen.getByLabelText('Название шаблона');
    fireEvent.change(codeInput, { target: { value: 'new_rule_t' } });
    fireEvent.change(nameInput, { target: { value: 'Новый шаблон правил' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    await waitFor(() => expect(guardTransition).toHaveBeenCalledTimes(1));
    expect(mockedApi.createTemplate).not.toHaveBeenCalled();
    expect(draftInput).toHaveValue('Гемоглобин, изменённый');
    expect(codeInput).toHaveValue('new_rule_t');
    expect(nameInput).toHaveValue('Новый шаблон правил');
  });

  it('routes clone and archive refreshes through the dirty transition guard', async () => {
    const guardTransition = vi.fn((_transition: () => void | Promise<void>) => {
      // Models Cancel: neither command may run before the guard resolves.
      return false;
    });

    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture]}
          selectedTemplate={ruleTemplateFixture}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          guardTransition={guardTransition}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    await waitFor(() => expect(mockedApi.listCatalogUnits).toHaveBeenCalled());

    fireEvent.click(screen.getByRole('button', { name: 'Клонировать' }));
    fireEvent.click(screen.getByRole('button', { name: 'Архивировать' }));

    expect(guardTransition).toHaveBeenCalledTimes(2);
    expect(mockedApi.cloneTemplate).not.toHaveBeenCalled();
    expect(mockedApi.archiveTemplateVersion).not.toHaveBeenCalled();
  });
});

describe('LabTemplateWorkbench guard save freshness (PR5 review fix)', () => {
  rtlBeforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listCatalogUnits.mockResolvedValue([]);
    mockedApi.listCatalogAnalytes.mockResolvedValue([]);
    mockedApi.createTemplateVersion.mockResolvedValue({ id: 52 });
    mockedApi.updateTemplateVersion.mockResolvedValue({ id: 52 });
  });

  it('registered save uses the current render state after the template loads later', async () => {
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => () => {}
    );
    const onTemplatesChanged = vi.fn(async (_preferredTemplateId?: string | number | null) => {});
    mockedApi.createTemplateVersion.mockResolvedValue({ id: 52 });
    mockedApi.updateTemplateVersion.mockResolvedValue({ id: 52 });

    const workbench = (template: Record<string, unknown> | null) => (
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={template ? [template] : []}
          selectedTemplate={template}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={onTemplatesChanged}
          registerDirtySource={registerDirtySource}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    // Реальный LabPanel монтирует workbench до загрузки шаблона.
    const { rerender } = render(workbench(null));
    rerender(workbench(ruleTemplateFixture));

    // Ждём hydrate активной версии, раскрываем поле и делаем draft dirty.
    await screen.findByRole('button', { name: /Поле: Гемоглобин/ });
    fireEvent.click(screen.getByRole('button', { name: /Поле: Гемоглобин/ }));
    fireEvent.change(screen.getByLabelText('Нижняя граница нормы'), {
      target: { value: '2' },
    });

    // Guard вызывает зарегистрированный источник: save обязан видеть
    // АКТУАЛЬНЫЙ рендер, а не selectedTemplate=null первого рендера.
    const source = registerDirtySource.mock.calls[0][0] as {
      id: string;
      isDirty: () => boolean;
      save: () => Promise<void>;
    };
    expect(source.id).toBe('template');
    expect(source.isDirty()).toBe(true);
    await act(async () => {
      await source.save();
    });

    // Актуальный version id (51 -> новый draft 52) и актуальные изменения.
    expect(mockedApi.createTemplateVersion).toHaveBeenCalledWith(5, 51);
    expect(mockedApi.updateTemplateVersion).toHaveBeenCalled();
    const [, payload] = mockedApi.updateTemplateVersion.mock.calls[0] as [unknown, { sections: Array<{ fields: Array<Record<string, unknown>> }> }];
    const rule = payload.sections[0].fields[0].reference_rule as {
      cases: Array<{ low: number }>;
    };
    expect(rule.cases[0].low).toBe(2);
    // Сохранение прошло успешно — переход может продолжиться.
    expect(onTemplatesChanged).toHaveBeenCalled();
  });

  it('registered save visibly reports an API failure and rethrows so the guard stays put', async () => {
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void> }) => () => {}
    );
    const notify = vi.fn();
    mockedApi.updateTemplateVersion
      .mockRejectedValueOnce(new Error('save exploded'))
      .mockResolvedValueOnce({ id: 52 });

    const onTemplatesChanged = vi.fn(async () => {});
    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture]}
          selectedTemplate={ruleTemplateFixture}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={onTemplatesChanged}
          registerDirtySource={registerDirtySource}
          notify={notify}
        />
      </ThemeProvider>
    );

    expandFirstFieldEditor();
    fireEvent.change(screen.getByLabelText('Название поля'), {
      target: { value: 'Гемоглобин, изменённый' },
    });

    const source = registerDirtySource.mock.calls[0][0] as {
      isDirty: () => boolean;
      save: () => Promise<void>;
    };
    expect(source.isDirty()).toBe(true);

    let saveError: unknown;
    await act(async () => {
      try {
        await source.save();
      } catch (error) {
        saveError = error;
      }
    });
    expect(saveError).toEqual(new Error('save exploded'));
    expect(notify).toHaveBeenCalledWith('error', 'save exploded');
    expect(onTemplatesChanged).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Название поля')).toHaveValue('Гемоглобин, изменённый');

    await act(async () => {
      await source.save();
    });
    expect(mockedApi.createTemplateVersion).toHaveBeenCalledTimes(1);
    expect(mockedApi.updateTemplateVersion).toHaveBeenCalledTimes(2);
    expect(mockedApi.updateTemplateVersion.mock.calls[0][0]).toBe(52);
    expect(mockedApi.updateTemplateVersion.mock.calls[1][0]).toBe(52);
    expect(onTemplatesChanged).toHaveBeenCalledTimes(1);
  });

  // PR 3351 (review round 6, P1): защита документа (refresh / закрытие
  // вкладки) переехала с per-workbench-хука (только dirty-state) на
  // уровень LabDirtyGuardProvider (dirty ИЛИ pending — см.
  // LabDirtyGuardContext.test.tsx). Workbench больше НЕ регистрирует
  // собственный beforeunload-слушатель: dirty-состояние предоставляется
  // через зарегистрированный источник, а блокировка/разблокировка
  // unload-а — решение провайдера по общему реестру.
  it('does not register a document-level beforeunload listener itself: dirty state is exposed via the registered source (review round 6)', async () => {
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void>; discard?: () => void }) => () => {},
    );
    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture]}
          selectedTemplate={ruleTemplateFixture}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          registerDirtySource={registerDirtySource}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    await waitFor(() => expect(mockedApi.listCatalogUnits).toHaveBeenCalled());

    expandFirstFieldEditor();
    fireEvent.change(screen.getByLabelText('Название поля'), {
      target: { value: 'Гемоглобин, изменённый' },
    });

    // Dirty-состояние видно через зарегистрированный источник (его
    // читает провайдер), но самого слушателя у workbench больше нет —
    // без провайдера событие проходит без блокировки.
    const source = registerDirtySource.mock.calls[0][0] as { isDirty: () => boolean };
    expect(source.isDirty()).toBe(true);
    const event = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });

  // PR #3351 (P1 — Discard): registered discard сбрасывает черновик шаблона
  // к hydrate(activeVersion): не dirty, поле возвращает серверное значение,
  // источник больше не dirty (блокировку beforeunload в этот момент
  // снимает провайдер — review round 6).
  it('registered discard resets the template draft to the hydrated version', async () => {
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void>; discard?: () => void }) => () => {},
    );
    render(
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture]}
          selectedTemplate={ruleTemplateFixture}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          registerDirtySource={registerDirtySource}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    await waitFor(() => expect(mockedApi.listCatalogUnits).toHaveBeenCalled());
    await screen.findByRole('button', { name: /Поле: Гемоглобин/ });
    expandFirstFieldEditor();
    fireEvent.change(screen.getByLabelText('Название поля'), {
      target: { value: 'Гемоглобин, изменённый' },
    });

    const source = registerDirtySource.mock.calls[0][0] as {
      isDirty: () => boolean;
      discard?: () => void;
    };
    expect(source.isDirty()).toBe(true);

    act(() => {
      source.discard?.();
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByLabelText('Название поля')).toHaveValue('Гемоглобин');
    expect(source.isDirty()).toBe(false);
  });

  // PR #3351 (P1 — гидратация и идентичность черновика): смена
  // selectedTemplate ре-гидратирует редактор из новой версии — правки
  // предыдущего шаблона не протекают и не считаются dirty.
  it('re-hydrates the draft when the selected template changes', async () => {
    const otherTemplate = {
      ...ruleTemplateFixture,
      id: 6,
      code: 'rule_demo_b',
      name: 'Rule Demo B',
      published_version_id: 61,
      versions: [
        {
          ...ruleTemplateFixture.versions[0],
          id: 61,
          template_id: 6,
          sections: [
            {
              ...ruleTemplateFixture.versions[0].sections[0],
              fields: [
                {
                  ...ruleTemplateFixture.versions[0].sections[0].fields[0],
                  field_key: 'wbc',
                  label: 'Лейкоциты',
                },
              ],
            },
          ],
        },
      ],
    };
    const registerDirtySource = vi.fn(
      (_source: { id: string; isDirty: () => boolean; save: () => Promise<void>; discard?: () => void }) => () => {},
    );
    const workbench = (template: Record<string, unknown>) => (
      <ThemeProvider>
        <LabTemplateWorkbenchRaw
          templates={[ruleTemplateFixture, otherTemplate]}
          selectedTemplate={template}
          onSelectTemplate={vi.fn()}
          onTemplatesChanged={vi.fn(async () => {})}
          registerDirtySource={registerDirtySource}
          notify={vi.fn()}
        />
      </ThemeProvider>
    );

    const { rerender } = render(workbench(ruleTemplateFixture));
    await screen.findByRole('button', { name: /Поле: Гемоглобин/ });
    expandFirstFieldEditor();
    fireEvent.change(screen.getByLabelText('Название поля'), {
      target: { value: 'Гемоглобин, изменённый' },
    });
    const dirtySource = registerDirtySource.mock.calls[0][0] as { isDirty: () => boolean };
    expect(dirtySource.isDirty()).toBe(true);

    rerender(workbench(otherTemplate));
    await screen.findByRole('button', { name: /Поле: Лейкоциты/ });

    // Редактор показывает поля нового шаблона; правки старого не протекли.
    expect(screen.queryByRole('button', { name: /Поле: Гемоглобин/ })).toBeNull();
    // Раскрытие поля (ключ 0-0) сохраняется — редактор поля уже открыт.
    expect(screen.getByLabelText('Название поля')).toHaveValue('Лейкоциты');
    expect(dirtySource.isDirty()).toBe(false);
  });
});
