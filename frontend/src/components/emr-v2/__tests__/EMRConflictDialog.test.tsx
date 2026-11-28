import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import i18n from '@/i18n';
import { EMRConflictDialog } from '../EMRConflictDialog';

const conflict = { yourVersion: 3, serverVersion: 4 };

describe('EMR version conflict recovery', () => {
    afterEach(async () => {
        await act(async () => { await i18n.changeLanguage('ru'); });
    });

    it('announces a failed read and keeps the explicit retry available without queuing another action', async () => {
        let rejectReload!: (reason: Error) => void;
        const onReload = vi.fn<() => Promise<unknown>>()
            .mockImplementationOnce(() => new Promise((_, reject) => { rejectReload = reject; }))
            .mockResolvedValueOnce({ data: { complaints: 'SYNTHETIC current version' } });
        const onCompare = vi.fn();
        const onAmend = vi.fn();
        render(<ThemeProvider><EMRConflictDialog conflict={conflict} isSigned
            onReload={onReload} onCompare={onCompare} onAmend={onAmend} /></ThemeProvider>);
        const dialog = screen.getByRole('dialog', { name: 'Конфликт версий' });
        const compare = screen.getByRole('button', { name: 'Сравнить изменения' });
        const reload = screen.getByRole('button', { name: 'Загрузить новую версию' });
        const amend = screen.getByRole('button', { name: 'Внести поправку' });
        expect(dialog).toHaveAttribute('aria-modal', 'true');
        expect(reload).toHaveAccessibleDescription('При загрузке версии с сервера несохранённые правки будут удалены.');
        await waitFor(() => expect(compare).toHaveFocus());
        expect(fireEvent.keyDown(compare, { key: 'z', ctrlKey: true })).toBe(false);

        fireEvent.click(reload);
        expect(screen.getByRole('status')).toBeVisible();
        expect(reload).toHaveAttribute('aria-disabled', 'true');
        fireEvent.click(reload);
        fireEvent.click(compare);
        fireEvent.click(amend);
        expect(onReload).toHaveBeenCalledTimes(1);
        expect(onCompare).not.toHaveBeenCalled();
        expect(onAmend).not.toHaveBeenCalled();

        await act(async () => rejectReload(new Error('SYNTHETIC HTTP 503')));
        expect(screen.getByRole('alert')).toHaveTextContent('Ваши правки остались в редакторе. Повторите загрузку.');
        expect(reload).toHaveAttribute('aria-disabled', 'false');
        fireEvent.click(compare);
        fireEvent.click(amend);
        expect(onCompare).toHaveBeenCalledOnce();
        expect(onAmend).toHaveBeenCalledOnce();
        fireEvent.click(reload);
        await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
        expect(screen.queryByRole('alert')).toBeNull();
        expect(onReload).toHaveBeenCalledTimes(2);
    });

    it('presents an unsuccessful read marker in Uzbek without closing the conflict', async () => {
        await i18n.changeLanguage('uz-Latn');
        render(<ThemeProvider><EMRConflictDialog conflict={conflict}
            onReload={() => Promise.resolve({ stale: true })} /></ThemeProvider>);
        const dialog = screen.getByRole('dialog', { name: 'Qayd versiyalari ziddiyati' });
        fireEvent.click(screen.getByRole('button', { name: 'Yangi versiyani yuklash' }));

        expect(await screen.findByRole('alert')).toHaveTextContent('Tahrirlaringiz muharrirda qoldi.');
        expect(dialog).toBeVisible();
        expect(screen.getByText('v4')).toBeVisible();
    });
});
