import { apiClient } from './client';

export type DentalMediaCategory = 'photo' | 'xray';

export interface DentalMediaItem {
  id: number;
  title: string | null;
  description: string | null;
  category: DentalMediaCategory;
  tooth: string | null;
  capture_date: string | null;
  mime_type: string;
  file_size: number;
  patient_id: number;
  visit_id: number;
  created_at: string;
  updated_at: string;
}

export interface DentalMediaList {
  items: DentalMediaItem[];
  total: number;
  page: number;
  size: number;
}

export interface DentalMediaMetadata {
  title?: string | null;
  description?: string | null;
  category?: DentalMediaCategory;
  tooth?: string | null;
  capture_date?: string | null;
}

export async function listDentalMedia(patientId: number, visitId: number, page = 1, size = 100): Promise<DentalMediaList> {
  const response = await apiClient.get<DentalMediaList>('/dental/media', {
    params: { patient_id: patientId, visit_id: visitId, page, size },
  });
  return response.data;
}

export async function uploadDentalMedia(
  patientId: number,
  visitId: number,
  category: DentalMediaCategory,
  file: File,
  metadata: Pick<DentalMediaMetadata, 'title' | 'description' | 'tooth' | 'capture_date'>,
): Promise<DentalMediaItem> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('patient_id', String(patientId));
  formData.append('visit_id', String(visitId));
  formData.append('category', category);
  if (metadata.title) formData.append('title', metadata.title);
  if (metadata.description) formData.append('description', metadata.description);
  if (metadata.tooth) formData.append('tooth', metadata.tooth);
  if (metadata.capture_date) formData.append('capture_date', metadata.capture_date);

  const response = await apiClient.post<DentalMediaItem>('/dental/media', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

export async function updateDentalMedia(mediaId: number, metadata: DentalMediaMetadata): Promise<DentalMediaItem> {
  const response = await apiClient.patch<DentalMediaItem>(`/dental/media/${mediaId}`, metadata);
  return response.data;
}

export async function deleteDentalMedia(mediaId: number): Promise<void> {
  await apiClient.delete(`/dental/media/${mediaId}`);
}

export async function loadDentalMediaContent(mediaId: number, visitId: number): Promise<Blob> {
  const response = await apiClient.get<Blob>(`/dental/media/${mediaId}/content`, {
    params: { visit_id: visitId },
    responseType: 'blob',
  });
  return response.data;
}
