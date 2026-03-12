import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../client', () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from '../client';
import {
  BOARD_DISPLAY_METADATA_V1_FIELDS,
  fetchBoardDisplayStateV1,
  normalizeBoardDisplayStateV1,
} from '../boardDisplay';

describe('boardDisplay API adapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls the new board-display endpoint with board_key path', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        board_key: 'main_board',
        display_metadata: {},
      },
    });

    await fetchBoardDisplayStateV1('main_board');

    expect(api.get).toHaveBeenCalledWith('/display/boards/main_board/state');
  });

  it('normalizes only the supported v1 metadata fields', () => {
    const result = normalizeBoardDisplayStateV1({
      board_key: 'main_board',
      display_metadata: {
        brand: 'Main Board',
        logo: '/static/logo.png',
        announcement: 'Welcome',
        announcement_ru: 'Добро пожаловать',
        announcement_uz: 'Xush kelibsiz',
        announcement_en: 'Welcome',
        primary_color: '#111111',
        bg_color: '#ffffff',
        text_color: '#222222',
        contrast_default: true,
        kiosk_default: false,
        sound_default: false,
        is_paused: true,
      },
    });

    expect(result).toEqual({
      boardKey: 'main_board',
      brand: 'Main Board',
      logo: '/static/logo.png',
      announcement: 'Welcome',
      announcement_ru: 'Добро пожаловать',
      announcement_uz: 'Xush kelibsiz',
      announcement_en: 'Welcome',
      primary_color: '#111111',
      bg_color: '#ffffff',
      text_color: '#222222',
      contrast_default: true,
      kiosk_default: false,
      sound_default: false,
    });
  });

  it('does not silently fabricate unresolved fields', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        board_key: 'main_board',
        display_metadata: {
          brand: 'Board',
          announcement: 'Test',
          announcement_ru: null,
          announcement_uz: null,
          announcement_en: null,
          primary_color: '#000',
          bg_color: '#fff',
          text_color: '#333',
          logo: '/static/logo.png',
          contrast_default: true,
          kiosk_default: false,
          sound_default: true,
        },
      },
    });

    const result = await fetchBoardDisplayStateV1('main_board');

    expect(BOARD_DISPLAY_METADATA_V1_FIELDS).toEqual([
      'brand',
      'logo',
      'announcement',
      'announcement_ru',
      'announcement_uz',
      'announcement_en',
      'primary_color',
      'bg_color',
      'text_color',
      'contrast_default',
      'kiosk_default',
      'sound_default',
    ]);
    expect(Object.keys(result).sort()).toEqual([
      'announcement',
      'announcement_en',
      'announcement_ru',
      'announcement_uz',
      'bg_color',
      'boardKey',
      'brand',
      'contrast_default',
      'kiosk_default',
      'logo',
      'primary_color',
      'sound_default',
      'text_color',
    ]);
    expect(result).not.toHaveProperty('is_paused');
    expect(result).not.toHaveProperty('is_closed');
  });

  it('rejects an empty board key', async () => {
    await expect(fetchBoardDisplayStateV1('   ')).rejects.toThrow(
      'boardKey must not be empty'
    );
    expect(api.get).not.toHaveBeenCalled();
  });
});
