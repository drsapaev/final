import React, { useState } from 'react';
import '@testing-library/jest-dom';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';

/**
 * EMRPRES-FE-001..004 (audit 3886, round 19) — fail-first.
 *
 * 001: the uncommitted draft form (isAdding/newItem/suggestions) survived an
 *      in-place visit/patient switch of the mounted editor, so visit A's
 *      half-typed drug could be committed into visit B's list.
 * 002: ID-less (imported/legacy) prescriptions rendered a working-looking
 *      Delete button that silently did nothing (`p.id !== undefined && ...`).
 * 003: `id: Date.now()` collides within one millisecond (or a frozen clock):
 *      two Adds share an id and deleting one removes BOTH.
 * 004: alias DTO fields (drug/dosage/freq) are permitted by the contract but
 *      rendered blank (only name/dose/frequency were read).
 * The tests below fail on the pre-fix source.
 */

import PrescriptionEditorRaw from '../PrescriptionEditor';

const PrescriptionEditor = PrescriptionEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;
type RxItem = { id?: string | number; name?: string; drug?: string; dose?: string; dosage?: string; frequency?: string; freq?: string; duration?: string };

const t = (key: string) => i18n.t(key) as string;
const deleteAria = () => t('misc.pe_udalit_naznachenie');

beforeEach(async () => {
  vi.clearAllMocks();
  await act(async () => { await i18n.changeLanguage('ru'); });
});

describe('EMRPRES-FE-001: draft form is discarded on a visit-identity switch', () => {
  it("visit A's half-typed drug cannot stay visible nor be committed into visit B", async () => {
    const onChange = vi.fn();
    const view = render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[]} onChange={onChange} isEditable visitKey="visit-A" />
      </ThemeProvider>,
    );

    // Start a draft under visit A.
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Добавить назначение' })); });
    const nameInput = screen.getByLabelText('Prescription medicine name');
    await act(async () => { fireEvent.change(nameInput, { target: { value: 'Аспирин A' } }); });
    await act(async () => { fireEvent.change(screen.getByLabelText('Prescription dose'), { target: { value: '500 мг' } }); });

    // A temporary read-only phase inside the SAME visit keeps the draft
    // (autosave locks fields; the visit identity did not change).
    view.rerender(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[]} onChange={onChange} isEditable={false} visitKey="visit-A" />
      </ThemeProvider>,
    );
    view.rerender(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[]} onChange={onChange} isEditable visitKey="visit-A" />
      </ThemeProvider>,
    );
    expect((screen.queryByLabelText('Prescription medicine name') as HTMLInputElement | null)?.value).toBe('Аспирин A');

    // Context switch: the SAME mounted editor now serves visit B.
    view.rerender(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[]} onChange={onChange} isEditable visitKey="visit-B" />
      </ThemeProvider>,
    );

    // The A draft must be gone: form closed, no half-typed values left.
    expect(screen.queryByLabelText('Prescription medicine name')).toBeNull();
    expect(screen.queryByDisplayValue('Аспирин A')).toBeNull();

    // Reopening the form under B must not resurrect A's drug, and a plain
    // Add must not commit anything A-related.
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Добавить назначение' })); });
    expect((screen.getByLabelText('Prescription medicine name') as HTMLInputElement).value).toBe('');
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Добавить' })); });
    expect(onChange).not.toHaveBeenCalled();
  });

  it('committed lists stay isolated: switching to B does not touch A\'s committed rows', async () => {
    const onChange = vi.fn();
    const aList: RxItem[] = [{ id: 1, name: 'Варфарин', dose: '5 мг', frequency: '1 р/д' }];
    const view = render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={aList} onChange={onChange} isEditable visitKey="visit-A" />
      </ThemeProvider>,
    );
    expect(screen.getByText('Варфарин')).toBeInTheDocument();

    view.rerender(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[]} onChange={onChange} isEditable visitKey="visit-B" />
      </ThemeProvider>,
    );
    // B starts empty — no A rows leak into B's editor.
    expect(screen.queryByText('Варфарин')).toBeNull();
  });
});

describe('EMRPRES-FE-002: ID-less prescriptions are deletable', () => {
  it('deleting the second ID-less row emits exactly the first', async () => {
    const onChange = vi.fn();
    const first: RxItem = { name: 'Импорт A' };
    const second: RxItem = { name: 'Импорт B' };
    render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[first, second]} onChange={onChange} isEditable />
      </ThemeProvider>,
    );
    const deleteButtons = screen.getAllByRole('button', { name: deleteAria() });
    expect(deleteButtons).toHaveLength(2);

    await act(async () => { fireEvent.click(deleteButtons[1]); });
    expect(onChange).toHaveBeenCalledTimes(1);
    const emitted = onChange.mock.calls[0][0] as RxItem[];
    expect(emitted).toHaveLength(1);
    expect(emitted[0].name).toBe('Импорт A');
  });

  it('duplicate-named ID-less rows do not delete each other', async () => {
    const onChange = vi.fn();
    const rowOne: RxItem = { name: 'Дубликат' };
    const rowTwo: RxItem = { name: 'Дубликат' };
    render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[rowOne, rowTwo]} onChange={onChange} isEditable />
      </ThemeProvider>,
    );
    const deleteButtons = screen.getAllByRole('button', { name: deleteAria() });
    await act(async () => { fireEvent.click(deleteButtons[0]); });
    expect(onChange).toHaveBeenCalledTimes(1);
    const emitted = onChange.mock.calls[0][0] as RxItem[];
    expect(emitted).toHaveLength(1);
    // Exactly one of the two duplicate rows remains (not zero, not two).
    expect(emitted[0]).toBe(rowTwo);
    expect(emitted).not.toContain(rowOne);
  });
});

describe('EMRPRES-FE-003: collision-resistant client ids (frozen clock)', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('two Adds under a frozen Date.now get distinct ids; deleting one preserves the other', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_700_000_000_000);
    // Controlled harness: every onChange emission is logged AND fed back
    // into the rendered list (the editor is a controlled component).
    const log: RxItem[][] = [];
    function RxHarness() {
      const [list, setList] = useState<RxItem[]>([]);
      const handleChange = (next: RxItem[]) => { log.push(next); setList(next); };
      return (
        <ThemeProvider>
          <PrescriptionEditor prescriptions={list} onChange={handleChange} isEditable />
        </ThemeProvider>
      );
    }
    render(<RxHarness />);

    const add = async (drug: string) => {
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Добавить назначение' })); });
      await act(async () => { fireEvent.change(screen.getByLabelText('Prescription medicine name'), { target: { value: drug } }); });
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Добавить' })); });
    };
    await add('Диклофенак');
    await add('Ибупрофен');

    expect(log).toHaveLength(2);
    const afterTwo = log[1];
    expect(afterTwo).toHaveLength(2);
    const [idA, idB] = [afterTwo[0].id, afterTwo[1].id];
    expect(idA).toBeDefined();
    expect(idB).toBeDefined();
    // Pre-fix: both ids === 1_700_000_000_000 — collision.
    expect(idA).not.toBe(idB);

    // Both rows are rendered; deleting the first must preserve the second
    // (pre-fix: the shared id made the filter remove BOTH rows).
    expect(screen.getAllByRole('button', { name: deleteAria() })).toHaveLength(2);
    await act(async () => { fireEvent.click(screen.getAllByRole('button', { name: deleteAria() })[0]); });
    expect(log).toHaveLength(3);
    const afterDelete = log[2];
    expect(afterDelete).toHaveLength(1);
    expect(afterDelete[0].name).toBe('Ибупрофен');
    expect(screen.getByText('Ибупрофен')).toBeInTheDocument();
    expect(screen.queryByText('Диклофенак')).toBeNull();
  });
});

describe('EMRPRES-FE-004: alias DTO fields render, not blank', () => {
  it('drug/dosage/freq alias rows show their real values', async () => {
    const aliasRow: RxItem = { drug: 'Example', dosage: '5 mg', freq: 'ежедневно', duration: '7 дней' };
    const canonicalRow: RxItem = { id: 3, name: 'Канонический', dose: '10 мг', frequency: '2 р/д' };
    render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[canonicalRow, aliasRow]} onChange={vi.fn()} isEditable />
      </ThemeProvider>,
    );
    // Pre-fix: the alias row rendered an empty drug name / no dose / no freq.
    expect(screen.getByText('Example')).toBeInTheDocument();
    expect(screen.getByText(/5 mg/)).toBeInTheDocument();
    expect(screen.getByText(/ежедневно/)).toBeInTheDocument();
    expect(screen.getByText(/7 дней/)).toBeInTheDocument();
    expect(screen.getByText('Канонический')).toBeInTheDocument();
  });

  it('deleting an alias row works without an id (belt with 002)', async () => {
    const onChange = vi.fn();
    const aliasRow: RxItem = { drug: 'AliasOnly', dosage: '5 mg', freq: 'ежедневно' };
    const canonicalRow: RxItem = { id: 3, name: 'Канонический', dose: '10 мг', frequency: '2 р/д' };
    render(
      <ThemeProvider>
        <PrescriptionEditor prescriptions={[canonicalRow, aliasRow]} onChange={onChange} isEditable />
      </ThemeProvider>,
    );
    const deleteButtons = screen.getAllByRole('button', { name: deleteAria() });
    await act(async () => { fireEvent.click(deleteButtons[1]); });
    const emitted = onChange.mock.calls[0][0] as RxItem[];
    expect(emitted).toHaveLength(1);
    expect(emitted[0].name).toBe('Канонический');
  });
});
