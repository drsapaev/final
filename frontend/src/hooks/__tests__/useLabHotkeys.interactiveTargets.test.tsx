import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { useLabHotkeys } from '../useLabHotkeys';

/**
 * LABUX-FE-001 (audit 3886, round 13) — fail-first.
 *
 * Глобальные лабораторные хоткеи (document, capture) фильтровали только
 * INPUT/TEXTAREA. Нативный <select> выбора клинического результата
 * (ReportEditor choice-поля) и contenteditable-регионы получали Escape
 * (clearSelection срабатывал ЗА открытым списком) и Ctrl/⌘+1–3 (сменa
 * вкладки панели посреди выбора). Тесты падают на до-фиксном коде.
 */

function HotkeysHost({
  onClearSelection,
  onSwitchTab,
}: {
  onClearSelection: () => void;
  onSwitchTab: (tab: string) => void;
}) {
  useLabHotkeys({
    clearSelection: onClearSelection,
    switchTab: onSwitchTab,
    refreshData: () => {},
  });
  return (
    <div>
      <select data-testid="native-select">
        <option value="normal">Норма</option>
        <option value="deviation">Отклонение</option>
      </select>
      <div data-testid="contenteditable" contentEditable suppressContentEditableWarning>
       Clinical note
      </div>
      <div data-testid="plain">plain text</div>
    </div>
  );
}

describe('LABUX-FE-001: global lab shortcuts respect native interactive targets', () => {
  it('does NOT fire Escape clearSelection while a native <select> owns the key', () => {
    const clearSelection = vi.fn();
    render(<HotkeysHost onClearSelection={clearSelection} onSwitchTab={() => {}} />);
    fireEvent.keyDown(screen.getByTestId('native-select'), { key: 'Escape' });
    expect(clearSelection).not.toHaveBeenCalled();
  });

  it('does NOT fire Ctrl+1 tab switch while a native <select> owns the key', () => {
    const switchTab = vi.fn();
    render(<HotkeysHost onClearSelection={() => {}} onSwitchTab={switchTab} />);
    fireEvent.keyDown(screen.getByTestId('native-select'), { key: '1', ctrlKey: true });
    expect(switchTab).not.toHaveBeenCalled();
  });

  it('does NOT fire Escape inside a contenteditable region', () => {
    const clearSelection = vi.fn();
    render(<HotkeysHost onClearSelection={clearSelection} onSwitchTab={() => {}} />);
    fireEvent.keyDown(screen.getByTestId('contenteditable'), { key: 'Escape' });
    expect(clearSelection).not.toHaveBeenCalled();
  });

  it('keeps the shortcuts working on a non-interactive target (body-level focus)', () => {
    const clearSelection = vi.fn();
    const switchTab = vi.fn();
    render(<HotkeysHost onClearSelection={clearSelection} onSwitchTab={switchTab} />);
    fireEvent.keyDown(screen.getByTestId('plain'), { key: 'Escape' });
    expect(clearSelection).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByTestId('plain'), { key: '1', ctrlKey: true });
    expect(switchTab).toHaveBeenCalledWith('queue');
  });
});
