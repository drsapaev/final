// P2-4b: the cosmetic-procedure save path for the derma panel.
//
// The legacy POST /derma/procedures endpoint is closed (410, review
// follow-up P2-4a); procedures are now appended to the visit EMR (emr/v2)
// under specialty_data.procedures — the same server contract the
// cardiology EchoForm uses for its echo block (load → merge → save).
import { api } from './client';
import type { EMRSaveRequestDto } from '../types/api';
import { buildInitialEMRData, normalizeEMRData } from '../utils/emrSpecialty';

export interface CosmeticProcedureEmrEntry {
    procedure_date: string;
    procedure_type: string;
    area_treated?: string;
    products_used?: string;
    results?: string;
    follow_up?: string;
    recorded_at: string;
}

interface ExistingEmr {
    data?: Record<string, unknown> | null;
    row_version?: number;
}

function errorStatus(error: unknown): number | undefined {
    return (error as { response?: { status?: number } })?.response?.status;
}

async function loadExistingEmr(
    visitId: string | number,
    client: Pick<typeof api, 'get' | 'post'>,
): Promise<ExistingEmr | null> {
    try {
        const response = await client.get(`/v2/emr/${visitId}`);
        return (response.data as ExistingEmr) || null;
    } catch (error) {
        if (errorStatus(error) === 404) {
            return null;
        }
        throw error;
    }
}

export function buildProcedureEmrPayload(
    existingEmr: ExistingEmr | null,
    entry: CosmeticProcedureEmrEntry,
): EMRSaveRequestDto {
    const currentData = (existingEmr?.data as Record<string, unknown>)
        || buildInitialEMRData('dermatology');
    const specialtyData = (currentData.specialty_data as Record<string, unknown>) || {};
    const procedures = Array.isArray(specialtyData.procedures)
        ? (specialtyData.procedures as unknown[])
        : [];

    return {
        data: normalizeEMRData(
            {
                ...currentData,
                specialty: currentData.specialty || 'dermatology',
                specialty_data: {
                    ...specialtyData,
                    procedures: [...procedures, entry],
                },
            },
            'dermatology',
        ),
        row_version: existingEmr?.row_version ?? 0,
        is_draft: true,
    };
}

export async function saveCosmeticProcedureToEmr(
    visitId: string | number,
    entry: CosmeticProcedureEmrEntry,
    client: Pick<typeof api, 'get' | 'post'> = api,
): Promise<void> {
    // One optimistic-locking retry: the visit EMR may be autosaved by the
    // EMR container between our read and write (409 conflict).
    let existingEmr = await loadExistingEmr(visitId, client);
    for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            await client.post(`/v2/emr/${visitId}`, buildProcedureEmrPayload(existingEmr, entry));
            return;
        } catch (error) {
            if (errorStatus(error) === 409 && attempt === 0) {
                existingEmr = await loadExistingEmr(visitId, client);
                continue;
            }
            throw error;
        }
    }
}
