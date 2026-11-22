/**
 * W2-PR3 / Codex R14 PR 3121 (P1) — cancelRemovedQueueEntries.
 *
 * Прежнее поведение: неудача отмены удалённой записи превращалась в тихий
 * toast.warning, после чего мастер показывал success и закрывался —
 * частичное сохранение (правки применены, удалённая позиция осталась
 * активной) оставалось незамеченным. Теперь вызов бросает
 * QueueEntryCancelError со списком неснятых ID, а вызывающие пути
 * (edit-delta / patient-update / cart-update) не сообщают успех и не
 * закрывают мастер.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  api: { post: vi.fn() },
}));

import { api } from '../../../api/client';
import {
  cancelRemovedQueueEntries,
  getRemovedQueueEntryIds,
  QueueEntryCancelError,
} from '../wizardUtils';

const apiPost = api.post as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  apiPost.mockReset();
});

const cartWith = (ids: Array<string | number>) =>
  ids.map((id) => ({ original_queue_id: id, service_id: 1, quantity: 1 }));

describe('cancelRemovedQueueEntries (R14 PR 3121)', () => {
  it('ничего не делает и не бьёт в API, если удалённых записей нет', async () => {
    apiPost.mockResolvedValue({});

    await expect(
      cancelRemovedQueueEntries([101, 102], cartWith([101, 102]), 'test')
    ).resolves.toBeUndefined();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('отменяет каждую удалённую запись и завершается без ошибок', async () => {
    apiPost.mockResolvedValue({});

    await expect(
      cancelRemovedQueueEntries([101, 102], cartWith([101]), 'test')
    ).resolves.toBeUndefined();

    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(apiPost).toHaveBeenCalledWith('/online-queue/entries/102/cancel');
  });

  it('при неудаче ОТМЕНЫ бросает QueueEntryCancelError с ID неснятых записей', async () => {
    // 102 отменяется успешно, 103 — отказ (например, 409 «есть оплата»).
    apiPost
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error('Request failed with status code 409'));

    let caught: unknown;
    try {
      await cancelRemovedQueueEntries([101, 102, 103], cartWith([101]), 'test');
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(QueueEntryCancelError);
    const cancelError = caught as QueueEntryCancelError;
    expect(cancelError.failedIds).toEqual([103]);
    expect(cancelError.message).toContain('103');
    // Частичное сохранение названо явно.
    expect(cancelError.message).toContain('Изменения сохранены');
  });

  it('собирает ВСЕ неудачные ID, а не только первый', async () => {
    apiPost.mockRejectedValue(new Error('network down'));

    let caught: unknown;
    try {
      await cancelRemovedQueueEntries([201, 202], cartWith([]), 'test');
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(QueueEntryCancelError);
    expect((caught as QueueEntryCancelError).failedIds).toEqual([201, 202]);
  });
});

describe('getRemovedQueueEntryIds — REG-FE-085 (mixed string|number ids)', () => {
  // REG-FE-085 (follow-up audit 2026-11-02): числовой 42 и строковый "42"
  // именуют ОДНУ запись очереди (read-модель и корзина живут в смешанных
  // типах). Прежний raw Set<string|number> считал их разными —
  // СОХРАНЯЕМАЯ запись помечалась к отмене.
  it('не отменяет сохраняемую запись при числовом original и строковом в корзине (42 vs "42")', () => {
    expect(getRemovedQueueEntryIds([42], cartWith(['42']))).toEqual([]);
  });

  it('не отменяет сохраняемую запись при строковом original и числовом в корзине ("42" vs 42)', () => {
    expect(getRemovedQueueEntryIds(['42'], cartWith([42]))).toEqual([]);
  });

  it('отменяет ЗАМЕНЁННУЮ запись: разные id в смешанных типах', () => {
    expect(getRemovedQueueEntryIds([42, '7'], cartWith(['42']))).toEqual(['7']);
  });

  it('не путает 42 и "042": разные записи остаются разными', () => {
    // Строковая нормализация не должна схлопывать РАЗНЫЕ идентификаторы.
    expect(getRemovedQueueEntryIds(['042'], cartWith([42]))).toEqual(['042']);
  });

  it('cancelRemovedQueueEntries не бьёт в API для mixed-type сохраняемой записи', async () => {
    apiPost.mockResolvedValue({});

    await expect(
      cancelRemovedQueueEntries([42], cartWith(['42']), 'mixed-types')
    ).resolves.toBeUndefined();
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('cancelRemovedQueueEntries отменяет реальную удалённую запись с mixed-типами в наборе', async () => {
    apiPost.mockResolvedValue({});

    await expect(
      cancelRemovedQueueEntries([42, '100'], cartWith(['42']), 'mixed-types')
    ).resolves.toBeUndefined();

    expect(apiPost).toHaveBeenCalledTimes(1);
    expect(apiPost).toHaveBeenCalledWith('/online-queue/entries/100/cancel');
  });
});
