import { api } from './client';

export interface DisplayDeviceCredential {
  deviceId: number;
  secret: string;
}

interface DisplayDeviceTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  board_name: string;
}

const STORAGE_PREFIX = 'clinic_display_device_v1:';

function storageKey(boardId: string): string {
  return `${STORAGE_PREFIX}${encodeURIComponent(boardId)}`;
}

export function readDisplayDeviceCredential(boardId: string): DisplayDeviceCredential | null {
  try {
    const raw = window.localStorage.getItem(storageKey(boardId));
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<DisplayDeviceCredential>;
    if (
      !Number.isSafeInteger(value.deviceId)
      || typeof value.secret !== 'string'
      || value.secret.length < 32
      || value.secret.length > 128
    ) {
      window.localStorage.removeItem(storageKey(boardId));
      return null;
    }
    return { deviceId: value.deviceId as number, secret: value.secret };
  } catch {
    return null;
  }
}

export function saveDisplayDeviceCredential(
  boardId: string,
  credential: DisplayDeviceCredential,
): void {
  window.localStorage.setItem(storageKey(boardId), JSON.stringify(credential));
}

export function forgetDisplayDeviceCredential(boardId: string): void {
  try {
    window.localStorage.removeItem(storageKey(boardId));
  } catch {
    // The public setup view can still be shown when browser storage is blocked.
  }
}

export async function exchangeDisplayDeviceCredential(
  credential: DisplayDeviceCredential,
  expectedBoardName: string,
): Promise<string> {
  try {
    const response = await api.post<DisplayDeviceTokenResponse>(
      '/display/devices/token',
      { device_id: credential.deviceId, secret: credential.secret },
    );
    const token = response.data?.access_token;
    if (
      typeof token !== 'string'
      || !token
      || response.data?.board_name !== expectedBoardName
    ) {
      throw new Error('Missing display token');
    }
    return token;
  } catch {
    // Do not propagate Axios request config, which can contain the one-time
    // device secret, into UI errors or logging.
    throw new Error('Display device authorization failed');
  }
}
