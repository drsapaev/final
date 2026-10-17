import { isAxiosError } from 'axios';
import { apiClient } from './client';

export type PublicSiteMediaKind = 'clinic_logo' | 'doctor_portrait';

// Keep the endpoint response shape at this API boundary; screen components
// consume this narrow adapter type instead of depending on generated schemas.
export interface PublicSiteMedia {
  id: number;
  asset_kind: PublicSiteMediaKind;
  doctor_id: number | null;
  mime_type: string;
  byte_size: number;
  is_published: boolean;
  published_at: string | null;
  created_at: string;
  media_url: string;
}

export interface PublicSiteDoctorOption {
  id: number;
  displayName: string;
  active: boolean;
}

export interface PublicSiteDoctorWebsiteContent {
  id: number;
  active: boolean;
  owner_active: boolean | null;
  show_on_website: boolean;
  missing_fields: string[];
}

export const PUBLIC_SITE_DOCTOR_PAGE_SIZE = 25;

interface AdminDoctorResponse {
  id: number;
  active: boolean;
  name?: string | null;
  full_name?: string | null;
  user?: { full_name?: string | null } | null;
}

export async function listPublicSiteMedia(): Promise<PublicSiteMedia[]> {
  const response = await apiClient.get<PublicSiteMedia[]>('/admin/public-site/media');
  return response.data;
}

export async function listPublicSiteDoctors(
  skip = 0,
  limit = PUBLIC_SITE_DOCTOR_PAGE_SIZE,
): Promise<PublicSiteDoctorOption[]> {
  const response = await apiClient.get<AdminDoctorResponse[]>('/admin/doctors', {
    params: { active_only: false, limit, skip },
  });

  const doctors = response.data
    .map((doctor) => ({
      id: doctor.id,
      displayName: (doctor.user?.full_name || doctor.full_name || doctor.name || '').trim() || `#${doctor.id}`,
      active: doctor.active,
    }));

  const nameCounts = new Map<string, number>();
  doctors.forEach((doctor) => nameCounts.set(doctor.displayName, (nameCounts.get(doctor.displayName) ?? 0) + 1));
  return doctors.map((doctor) => nameCounts.get(doctor.displayName)! > 1
    ? { ...doctor, displayName: `${doctor.displayName} (#${doctor.id})` }
    : doctor);
}

export async function getPublicSiteDoctorWebsiteContent(
  doctorId: number,
): Promise<PublicSiteDoctorWebsiteContent> {
  const response = await apiClient.get<PublicSiteDoctorWebsiteContent>(
    `/admin/doctors/${doctorId}/website-content`,
  );
  return response.data;
}

export function isPublicSiteDoctorEligible(
  content: PublicSiteDoctorWebsiteContent,
): boolean {
  return content.active
    && content.owner_active === true
    && content.show_on_website
    && content.missing_fields.length === 0;
}

export async function uploadPublicSiteMedia(
  file: File,
  assetKind: PublicSiteMediaKind,
  doctorId?: number,
): Promise<PublicSiteMedia> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('asset_kind', assetKind);
  if (assetKind === 'doctor_portrait' && doctorId !== undefined) {
    formData.append('doctor_id', String(doctorId));
  }

  const response = await apiClient.post<PublicSiteMedia>('/admin/public-site/media', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function publishPublicSiteMedia(mediaId: number): Promise<PublicSiteMedia> {
  const response = await apiClient.put<PublicSiteMedia>(`/admin/public-site/media/${mediaId}/publish`);
  return response.data;
}

export async function unpublishPublicSiteMedia(mediaId: number): Promise<PublicSiteMedia> {
  const response = await apiClient.put<PublicSiteMedia>(`/admin/public-site/media/${mediaId}/unpublish`);
  return response.data;
}

export function getPublicSiteMediaErrorKey(error: unknown): string {
  if (!isAxiosError(error)) return 'publicSiteMedia.genericError';

  if (!error.response) {
    return error.code === 'ERR_CANCELED'
      ? 'publicSiteMedia.genericError'
      : 'publicSiteMedia.networkError';
  }

  const status = error.response?.status;
  const code = (error.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code;

  if (status === 503 || code === 'public_media_storage_unavailable') {
    return 'publicSiteMedia.storageUnavailable';
  }
  if (status === 413 || code === 'public_media_file_too_large') {
    return 'publicSiteMedia.fileTooLarge';
  }
  if (code === 'public_media_empty_file' || code === 'public_media_unsupported_image') {
    return 'publicSiteMedia.invalidImage';
  }
  return 'publicSiteMedia.genericError';
}
