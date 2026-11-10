/**
 * EMRAI-FE-003 + EMRSMART-FE-001 (audit 3886, round 27) — fail-first.
 *
 * EMRAI-FE-003: EMRSmartFieldV2's dismiss handler only delegated to an
 * optional parent callback (which the real parent never passes) and never
 * removed the rejected suggestion locally; closing the populated popover
 * (× / Esc) set showPopover=false but the auto-open effect immediately
 * reopened it on the next render while the field stayed focused. A doctor
 * could not reliably reject or finish a wrong clinical suggestion.
 *
 * EMRSMART-FE-001: the `label` and `required` props were declared but never
 * destructured nor forwarded to the textarea/input — no aria-label, no
 * accessible name, no required semantics for the primary diagnosis field.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, type Mock } from 'vitest';
import { EMRSmartFieldV2 } from '../EMRSmartFieldV2';

const TWO = [
    { id: 'a', content: 'S-one', source: 'ai', confidence: 0.9 },
    { id: 'b', content: 'S-two', source: 'ai', confidence: 0.8 },
];

function renderField(overrides: Record<string, unknown> = {}) {
    const onChange = (overrides.onChange as Mock | undefined) ?? vi.fn();
    const props: Record<string, unknown> = { ...overrides, onChange: onChange as never };
    const { rerender, ...rest } = render(
        <EMRSmartFieldV2
            value="жалобы"
            suggestions={TWO as unknown as never[]}
            label="Диагноз"
            required
            id="emr-diagnosis"
            {...(props as Record<string, never>)}
        />,
    );
    return { ...rest, rerender, onChange };
}

/** Native focus (sets document.activeElement) + React focus event. */
function focusField(): HTMLElement {
    const field = document.getElementById('emr-diagnosis') as HTMLElement;
    expect(field).not.toBeNull();
    field.focus();
    fireEvent.focus(field);
    return field;
}

describe('EMRSMART-FE-001: label and required reach the editable field', () => {
    it('R05: the textarea is reachable by role with the supplied label and required semantics', () => {
        renderField();
        const field = screen.getByRole('textbox', { name: /диагноз/i });
        expect(field).toHaveAttribute('aria-required', 'true');
    });

    it('R06: single-line input variant also carries the accessible name', () => {
        renderField({ multiline: false });
        const field = screen.getByRole('textbox', { name: /диагноз/i });
        expect(field.tagName).toBe('INPUT');
    });

    it('C07 (control): without a label the field still renders and keeps its id', () => {
        renderField({ label: undefined, required: undefined, suggestions: [] });
        const field = document.getElementById('emr-diagnosis');
        expect(field).not.toBeNull();
        expect(field).not.toHaveAttribute('aria-required');
    });
});

describe('EMRAI-FE-003: dismissed suggestions disappear and stay dismissed', () => {
    it('R08: dismissing one suggestion removes it from the popover immediately', async () => {
        renderField();
        focusField();

        expect(screen.getByText('S-one')).toBeInTheDocument();
        // [0] is the popover header close; per-item × buttons follow
        fireEvent.click(screen.getAllByText('×')[1]);

        await waitFor(() => {
            expect(screen.queryByText('S-one')).not.toBeInTheDocument();
        });
        expect(screen.getByText('S-two')).toBeInTheDocument();
    });

    it('R09: dismissing every suggestion closes the popover with nothing left', async () => {
        renderField();
        focusField();

        fireEvent.click(screen.getAllByText('×')[1]);
        await waitFor(() => {
            expect(screen.queryByText('S-one')).not.toBeInTheDocument();
        });
        fireEvent.click(screen.getAllByText('×')[1]);
        await waitFor(() => {
            expect(screen.queryByText('S-two')).not.toBeInTheDocument();
        });

        // popover with zero visible suggestions renders nothing at all
        expect(screen.queryByText('AI предлагает')).not.toBeInTheDocument();
    });

    it('R10: user-closed popover stays closed while the same batch is focused (no reopen loop)', async () => {
        renderField();
        focusField();

        expect(screen.getByText('S-one')).toBeInTheDocument();
        // click the popover header close (×) — focus stays in the field
        fireEvent.click(screen.getAllByText('×')[0]);

        // the pre-fix auto-open effect resurrects the same batch on the very
        // next commit; assert it stays closed
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('S-one')).not.toBeInTheDocument();
        expect(screen.queryByText('S-two')).not.toBeInTheDocument();
    });

    it('R11: applying a suggestion closes the popover and it stays closed for that batch', async () => {
        const { onChange } = renderField();
        focusField();

        fireEvent.click(screen.getAllByText('✓')[0]);

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange.mock.calls[0][0]).toContain('S-one');
        await new Promise((r) => setTimeout(r, 50));
        expect(screen.queryByText('S-two')).not.toBeInTheDocument();
    });

    it('R12: a NEW batch of suggestions still auto-opens after the user closed the old one', async () => {
        const { rerender } = renderField();
        focusField();
        fireEvent.click(screen.getAllByText('×')[0]);
        await waitFor(() => {
            expect(screen.queryByText('S-one')).not.toBeInTheDocument();
        });

        // a fresh request result arrives (new array identity)
        rerender(
            <EMRSmartFieldV2
                value="жалобы"
                onChange={vi.fn()}
                suggestions={[{ id: 'c', content: 'S-three', source: 'ai', confidence: 0.7 }] as unknown as never[]}
                label="Диагноз"
                required
                id="emr-diagnosis"
            />,
        );

        await waitFor(() => {
            expect(screen.getByText('S-three')).toBeInTheDocument();
        });
    });

    it('C13 (control): applying a suggestion emits the appended text through onChange', () => {
        const { onChange } = renderField();
        focusField();

        fireEvent.click(screen.getAllByText('✓')[0]);

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange.mock.calls[0][0]).toContain('S-one');
    });

    it('C14 (control): Tab in the focused field still accepts the first visible suggestion', () => {
        const { onChange } = renderField();
        focusField();

        fireEvent.keyDown(document, { key: 'Tab' });

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange.mock.calls[0][0]).toContain('S-one');
    });

    it('C15 (control): Tab accepts the first suggestion after another was dismissed', async () => {
        const { onChange } = renderField();
        focusField();

        fireEvent.click(screen.getAllByText('×')[1]);
        await waitFor(() => {
            expect(screen.queryByText('S-one')).not.toBeInTheDocument();
        });

        fireEvent.keyDown(document, { key: 'Tab' });

        expect(onChange).toHaveBeenCalledTimes(1);
        expect(onChange.mock.calls[0][0]).toContain('S-two');
    });
});
