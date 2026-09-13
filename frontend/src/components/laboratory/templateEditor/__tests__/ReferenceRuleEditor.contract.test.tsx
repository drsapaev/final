import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ReferenceRuleEditorRaw from '../ReferenceRuleEditor';
import { ThemeProvider } from '@/contexts/ThemeContext';

// Компонент под тестом типизирован через пропсы-интерфейсы; приводим к
// пермиссивному ComponentType, чтобы тест не зависел от strictNullChecks.
const ReferenceRuleEditor = ReferenceRuleEditorRaw as unknown as React.ComponentType<Record<string, unknown>>;

describe('ReferenceRuleEditor numeric bounds (PR4)', () => {
  it('keeps a zero lower bound as 0 instead of null when entered', () => {
    const updateField = vi.fn();
    const field = {
      // Fixture с low: 1: controlled input уже показывает '0' в дефектном
      // сценарии, поэтому вводим 0 поверх 1 — иначе React не отличит change.
      reference_rule_text: JSON.stringify({
        cases: [],
        default: { text: '1-10', low: 1, high: 10 },
      }),
    };

    render(
      <ThemeProvider>
        <ReferenceRuleEditor
          sectionIndex={0}
          fieldIndex={0}
          field={field}
          updateField={updateField}
        />
      </ThemeProvider>
    );

    fireEvent.change(screen.getByLabelText('Нижняя граница по умолчанию'), {
      target: { value: '0' },
    });

    expect(updateField).toHaveBeenCalledTimes(1);
    const serialized = updateField.mock.calls[0][3] as string;
    const rule = JSON.parse(serialized) as { default: { low: number | null; high: number | null } };
    expect(rule.default.low).toBe(0);
    expect(rule.default.high).toBe(10);
  });

  it('writes null only when the bound input is emptied', () => {
    const updateField = vi.fn();
    const field = {
      reference_rule_text: JSON.stringify({
        cases: [],
        default: { text: '0-10', low: 0, high: 10 },
      }),
    };

    render(
      <ThemeProvider>
        <ReferenceRuleEditor
          sectionIndex={0}
          fieldIndex={0}
          field={field}
          updateField={updateField}
        />
      </ThemeProvider>
    );

    fireEvent.change(screen.getByLabelText('Нижняя граница по умолчанию'), {
      target: { value: '' },
    });

    const serialized = updateField.mock.calls[0][3] as string;
    const rule = JSON.parse(serialized) as { default: { low: number | null } };
    expect(rule.default.low).toBeNull();
  });
});
