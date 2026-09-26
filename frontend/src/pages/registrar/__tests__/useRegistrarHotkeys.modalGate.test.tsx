/**
 * E-054 leftover #1 (wizard-пятёрка #3079 superseded): hotkey gate.
 *
 * При открытом мастере (showWizard) или slots-модале (showSlotsModal)
 * Ctrl-хоткеи панели не должны переключать вкладки/панели ЗА модальным
 * окном: Ctrl+K не переоткрывает мастер, Ctrl+1..5 не уводят пользователя
 * с открытой формой записи. Escape не гейтится: slots-модал закрывается
 * панелью, мастер — собственной защитой requestClose.
 *
 * RED→GREEN: на main до фикса тесты 1-3 падали (хоткеи срабатывали
 * поверх открытого модала).
 */
import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRegistrarHotkeys } from '../useRegistrarHotkeys';

const press = (key: string, init: KeyboardEventInit = {}) => {
  document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, ...init }));
};

const setup = (overrides: Partial<Parameters<typeof useRegistrarHotkeys>[0]> = {}) => {
  const handlers = {
    setShowWizard: vi.fn(),
    setShowSlotsModal: vi.fn(),
    setActiveTab: vi.fn(),
    navigate: vi.fn(),
    showWizard: false,
    showSlotsModal: false,
    appointments: [],
    ...overrides,
  };
  renderHook(() => useRegistrarHotkeys(handlers));
  return handlers;
};

describe('useRegistrarHotkeys — modal gate (E-054 leftover 1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it('wizard open: Ctrl+2 не переключает вкладку за мастером', () => {
    const h = setup({ showWizard: true });
    press('2', { ctrlKey: true });
    expect(h.setActiveTab).not.toHaveBeenCalled();
  });

  it('slots modal open: Ctrl+5 не уводит навигацию за модал', () => {
    const h = setup({ showSlotsModal: true });
    press('5', { ctrlKey: true });
    expect(h.navigate).not.toHaveBeenCalled();
  });

  it('wizard open: Ctrl+K не переоткрывает мастер', () => {
    const h = setup({ showWizard: true });
    press('k', { ctrlKey: true });
    expect(h.setShowWizard).not.toHaveBeenCalled();
  });

  it('wizard closed: Ctrl+K по-прежнему открывает мастер (регрессия)', () => {
    const h = setup();
    press('k', { ctrlKey: true });
    expect(h.setShowWizard).toHaveBeenCalledWith(true);
  });

  it('wizard closed: Ctrl+2 по-прежнему переключает вкладку (регрессия)', () => {
    const h = setup();
    press('2', { ctrlKey: true });
    expect(h.setActiveTab).toHaveBeenCalledWith('appointments');
  });

  it('wizard open: Escape по-прежнему закрывает slots-модал панелью (не гейтится)', () => {
    const h = setup({ showWizard: true, showSlotsModal: true });
    press('Escape');
    expect(h.setShowSlotsModal).toHaveBeenCalledWith(false);
  });

  it('фокус в input по-прежнему глушит хоткеи (существующий контракт)', () => {
    const h = setup();
    const input = document.createElement('input');
    document.body.appendChild(input);
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '2', ctrlKey: true, bubbles: true }));
    expect(h.setActiveTab).not.toHaveBeenCalled();
    input.remove();
  });
});
