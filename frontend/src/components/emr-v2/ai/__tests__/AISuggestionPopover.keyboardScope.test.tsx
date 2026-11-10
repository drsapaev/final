/**
 * EMRAI-FE-002 (audit 3886, round 27) — fail-first.
 *
 * The AI suggestion popover attached a document-level keydown listener that
 * unconditionally preventDefault()-ed ArrowUp/ArrowDown and applied the
 * selected suggestion on EVERY Enter, regardless of where the event
 * originated. While the doctor was typing in the clinical textarea the
 * popover is anchored to, Enter silently appended AI/history text instead
 * of inserting a newline and arrows stopped moving the caret. When focus
 * was on a suggestion item, the item's own Enter handler AND the document
 * handler both fired → double apply.
 *
 * Contract after the fix:
 * - keydown events originating from a text-editing element that is NOT part
 *   of the popover (textarea/input/contenteditable — i.e. the anchor field)
 *   never navigate/apply: Enter/arrows keep their native editing behavior.
 * - when focus is inside the popover, the item's own keyboard handler owns
 *   activation: Enter applies exactly once; arrows still move the selection.
 * - when focus is elsewhere (body), arrows/Enter/Escape keep working.
 */
import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { AISuggestionPopover } from '../AISuggestionPopover';

const SUGGESTIONS = [
    { id: 1, content: 'S-one' },
    { id: 2, content: 'S-two' },
];

function Harness({ onApply, onClose }: { onApply: Mock; onClose: Mock }) {
    const anchorRef = React.useRef<HTMLDivElement>(null);
    return (
        <div>
            <div ref={anchorRef}>
                <textarea aria-label="clinical-notes" />
            </div>
            <AISuggestionPopover
                suggestions={SUGGESTIONS as unknown as never[]}
                onApply={onApply as never}
                isOpen
                anchorRef={anchorRef}
                onClose={onClose as never}
            />
        </div>
    );
}

function dispatchKey(target: HTMLElement | Element, key: string): KeyboardEvent {
    const event = new KeyboardEvent('keydown', {
        key,
        bubbles: true,
        cancelable: true,
    });
    act(() => {
        target.dispatchEvent(event);
    });
    return event;
}

describe('EMRAI-FE-002: popover keyboard handling is scoped, not document-global', () => {
    let onApply: Mock;
    let onClose: Mock;

    beforeEach(() => {
        onApply = vi.fn();
        onClose = vi.fn();
    });

    it('R01: Enter in the anchor textarea inserts a newline — no apply, no preventDefault', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const textarea = screen.getByLabelText('clinical-notes');
        textarea.focus();

        const event = dispatchKey(textarea, 'Enter');

        expect(event.defaultPrevented).toBe(false);
        expect(onApply).not.toHaveBeenCalled();
    });

    it('R02: ArrowDown in the anchor textarea moves the caret, not the popover selection', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const textarea = screen.getByLabelText('clinical-notes');
        textarea.focus();

        const down = dispatchKey(textarea, 'ArrowDown');
        expect(down.defaultPrevented).toBe(false);

        const up = dispatchKey(textarea, 'ArrowUp');
        expect(up.defaultPrevented).toBe(false);
        expect(onApply).not.toHaveBeenCalled();
    });

    it('R03: Enter on a focused suggestion item applies exactly once (no document-level double apply)', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const firstItem = screen.getByText('S-one').closest('[role="button"]') as HTMLElement;
        expect(firstItem).not.toBeNull();
        firstItem.focus();

        dispatchKey(firstItem, 'Enter');

        expect(onApply).toHaveBeenCalledTimes(1);
        expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
    });

    it('R04: Enter on the focused apply button (✓) applies once via the button itself', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const applyButton = screen.getAllByText('✓')[0].closest('button') as HTMLButtonElement;
        applyButton.focus();

        dispatchKey(applyButton, 'Enter');

        // the native button activation handles the apply; the document
        // listener must not add a second call
        expect(onApply).toHaveBeenCalledTimes(1);
    });

    it('C01 (control): Enter with focus on document.body still applies the selected row', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        document.body.focus();

        dispatchKey(document.body, 'Enter');

        expect(onApply).toHaveBeenCalledTimes(1);
        expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }));
    });

    it('C02 (control): arrows still move the selection and Enter applies the moved row (body focus)', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        document.body.focus();

        dispatchKey(document.body, 'ArrowDown');
        dispatchKey(document.body, 'Enter');

        expect(onApply).toHaveBeenCalledTimes(1);
        expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
    });

    it('C03 (control): Escape closes the popover from the anchor textarea', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const textarea = screen.getByLabelText('clinical-notes');
        textarea.focus();

        dispatchKey(textarea, 'Escape');

        expect(onClose).toHaveBeenCalledTimes(1);
        expect(onApply).not.toHaveBeenCalled();
    });

    it('C04 (control): arrows still navigate while focus is inside the popover list', () => {
        render(<Harness onApply={onApply} onClose={onClose} />);
        const firstItem = screen.getByText('S-one').closest('[role="button"]') as HTMLElement;
        firstItem.focus();

        dispatchKey(firstItem, 'ArrowDown');
        // selection moved to the second row; body-focus Enter applies it
        document.body.focus();
        dispatchKey(document.body, 'Enter');

        expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
    });
});
