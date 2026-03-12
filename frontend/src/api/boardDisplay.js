import { api } from './client';
import { API_ENDPOINTS } from './endpoints';

export const BOARD_DISPLAY_METADATA_V1_FIELDS = Object.freeze([
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

function normalizeBoardKey(boardKey) {
  if (typeof boardKey !== 'string') {
    throw new Error('boardKey must be a string');
  }

  const normalized = boardKey.trim();
  if (!normalized) {
    throw new Error('boardKey must not be empty');
  }

  return normalized;
}

export function normalizeBoardDisplayStateV1(payload) {
  const metadata = payload?.display_metadata ?? {};

  return {
    boardKey: payload?.board_key ?? null,
    brand: metadata.brand ?? null,
    logo: metadata.logo ?? null,
    announcement: metadata.announcement ?? null,
    announcement_ru: metadata.announcement_ru ?? null,
    announcement_uz: metadata.announcement_uz ?? null,
    announcement_en: metadata.announcement_en ?? null,
    primary_color: metadata.primary_color ?? null,
    bg_color: metadata.bg_color ?? null,
    text_color: metadata.text_color ?? null,
    contrast_default:
      typeof metadata.contrast_default === 'boolean'
        ? metadata.contrast_default
        : null,
    kiosk_default:
      typeof metadata.kiosk_default === 'boolean'
        ? metadata.kiosk_default
        : null,
    sound_default:
      typeof metadata.sound_default === 'boolean'
        ? metadata.sound_default
        : null,
  };
}

export async function fetchBoardDisplayStateV1(boardKey) {
  const normalizedBoardKey = normalizeBoardKey(boardKey);
  const response = await api.get(
    API_ENDPOINTS.BOARD_DISPLAY.STATE(normalizedBoardKey)
  );
  return normalizeBoardDisplayStateV1(response.data);
}
