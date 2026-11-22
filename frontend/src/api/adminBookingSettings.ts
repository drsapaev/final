import { api } from './client';
import type {
  PublicBookingSettingsOutDto,
  PublicBookingSettingsUpdateDto,
} from '../types/api';

export type PublicBookingMode = 'confirmed_appointment' | 'registrar_request';
export type PublicBookingSettings = Omit<PublicBookingSettingsOutDto, 'mode'> & {
  mode: PublicBookingMode | null;
};
export type PublicBookingSettingsUpdate = Omit<PublicBookingSettingsUpdateDto, 'mode'> & {
  mode: PublicBookingMode | null;
};

const settingsPath = '/admin/public-booking-settings';

export async function getPublicBookingSettings(): Promise<PublicBookingSettings> {
  const response = await api.get<PublicBookingSettings>(settingsPath);
  return response.data;
}

export async function updatePublicBookingSettings(
  update: PublicBookingSettingsUpdate,
): Promise<PublicBookingSettings> {
  const response = await api.put<PublicBookingSettings>(settingsPath, update);
  return response.data;
}
