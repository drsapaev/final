import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ChatButton from '../ChatButton';

const chatMock = vi.hoisted(() => ({
  windowLoads: 0,
  loadMessages: vi.fn(),
  setIsChatOpen: vi.fn(),
  releaseWindowImport: undefined as undefined | (() => void),
}));

vi.mock('../../../hooks/useChat', () => ({
  useChat: () => ({
    unreadCount: 0,
    isConnected: true,
    loadMessages: chatMock.loadMessages,
  }),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

vi.mock('../ChatWindow', async () => {
  chatMock.windowLoads += 1;
  await new Promise<void>((resolve) => {
    chatMock.releaseWindowImport = resolve;
  });
  const { useEffect } = await import('react');
  function MockChatWindow({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
    useEffect(() => chatMock.setIsChatOpen(isOpen), [isOpen]);
    return (
      <div data-testid="chat-window" data-open={String(isOpen)}>
        <button onClick={onClose}>Close chat</button>
      </div>
    );
  }
  return {
    default: MockChatWindow,
  };
});

describe('ChatButton lazy window', () => {
  beforeEach(() => {
    chatMock.loadMessages.mockClear();
    chatMock.setIsChatOpen.mockClear();
  });

  it('does not load the window until first opening and keeps it mounted after close', async () => {
    render(<ChatButton />);
    expect(screen.queryByTestId('chat-window')).not.toBeInTheDocument();
    expect(chatMock.windowLoads).toBe(0);

    fireEvent.click(screen.getByRole('button', { name: 'chatOpen' }));
    expect(screen.getByRole('status')).toHaveTextContent('common.loading');
    await waitFor(() => expect(chatMock.releaseWindowImport).toBeTypeOf('function'));
    act(() => chatMock.releaseWindowImport?.());
    expect(await screen.findByTestId('chat-window')).toHaveAttribute('data-open', 'true');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(chatMock.windowLoads).toBe(1);
    expect(chatMock.setIsChatOpen).toHaveBeenLastCalledWith(true);

    fireEvent.click(screen.getByRole('button', { name: 'Close chat' }));
    await waitFor(() => {
      expect(screen.getByTestId('chat-window')).toHaveAttribute('data-open', 'false');
      expect(chatMock.setIsChatOpen).toHaveBeenLastCalledWith(false);
    });

    fireEvent.click(screen.getByRole('button', { name: 'chatOpen' }));
    expect(screen.getByTestId('chat-window')).toHaveAttribute('data-open', 'true');
    expect(chatMock.windowLoads).toBe(1);

    fireEvent.click(screen.getByRole('button', { name: 'Close chat' }));
    await waitFor(() => expect(screen.getByTestId('chat-window')).toHaveAttribute('data-open', 'false'));
    act(() => {
      window.dispatchEvent(new CustomEvent('openChat', { detail: { userId: 42 } }));
    });

    expect(await screen.findByTestId('chat-window')).toHaveAttribute('data-open', 'true');
    expect(chatMock.loadMessages).toHaveBeenCalledExactlyOnceWith(42);
    expect(chatMock.setIsChatOpen).toHaveBeenLastCalledWith(true);
  });
});
