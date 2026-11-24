import { api } from './client';
import type { PublicSiteAnalyticsReportDto } from '../types/api';

export type PublicSiteAnalyticsReportData = PublicSiteAnalyticsReportDto;

export async function getPublicSiteAnalyticsReport(
  signal: AbortSignal,
): Promise<PublicSiteAnalyticsReportData> {
  const { data } = await api.get<PublicSiteAnalyticsReportDto>('/admin/public-site/analytics', { signal });
  return data;
}
