import { api } from './client';

interface DisplayDeviceTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  board_name: string;
}

export class DisplayDeviceProvisioningRequiredError extends Error {
  readonly code = 'DISPLAY_DEVICE_PROVISIONING_REQUIRED';

  constructor() {
    super('Display device provisioning is required');
    this.name = 'DisplayDeviceProvisioningRequiredError';
  }
}

async function exchange(
  boardName: string,
  credential?: { deviceId: number; secret: string },
): Promise<string> {
  try {
    const response = await api.post<DisplayDeviceTokenResponse>(
      '/display/devices/token',
      credential
        ? { board_name: boardName, device_id: credential.deviceId, secret: credential.secret }
        : { board_name: boardName },
      { withCredentials: true },
    );
    const token = response.data?.access_token;
    if (
      typeof token !== 'string'
      || !token
      || response.data?.board_name !== boardName
    ) {
      throw new Error('Display token did not match the selected board');
    }
    return token;
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 401) throw new DisplayDeviceProvisioningRequiredError();
    // Do not propagate Axios request config, which can contain the one-time
    // device secret, into UI errors or logging.
    throw new Error('Display device authorization failed');
  }
}

export function exchangeDisplayDeviceCredential(
  deviceId: number,
  secret: string,
  expectedBoardName: string,
): Promise<string> {
  return exchange(expectedBoardName, { deviceId, secret });
}

export function exchangeDisplayDeviceSession(boardName: string): Promise<string> {
  return exchange(boardName);
}

export async function forgetDisplayDeviceSession(boardName: string): Promise<void> {
  try {
    await api.delete('/display/devices/token', {
      params: { board_name: boardName },
      withCredentials: true,
    });
  } catch {
    throw new Error('Display device session could not be cleared');
  }
}
