import { requestLab } from './labReporting';
import type {
  LabSpecimen,
  LabSpecimenAssignmentInput,
  LabSpecimenCreateInput,
  LabSpecimenEventInput,
  LabSpecimenMutationInput,
  LabSpecimenPage,
} from '../types/features/labWorkspace';

export const labSpecimensApi = {
  list(orderId: number, signal?: AbortSignal) {
    return requestLab(`/lab/orders/${orderId}/specimens`, { signal }) as Promise<LabSpecimenPage>;
  },
  create(orderId: number, body: LabSpecimenCreateInput) {
    return requestLab(`/lab/orders/${orderId}/specimens`, {
      method: 'POST', body: JSON.stringify(body),
    }) as Promise<LabSpecimen>;
  },
  createForVisit(visitId: number, body: LabSpecimenCreateInput) {
    return requestLab(`/lab/visits/${visitId}/specimens`, {
      method: 'POST', body: JSON.stringify(body),
    }) as Promise<LabSpecimen>;
  },
  addEvent(specimenId: number, body: LabSpecimenEventInput) {
    return requestLab(`/lab/specimens/${specimenId}/events`, {
      method: 'POST', body: JSON.stringify(body),
    }) as Promise<LabSpecimen>;
  },
  assign(specimenId: number, body: LabSpecimenAssignmentInput) {
    return requestLab(`/lab/specimens/${specimenId}/assignments`, {
      method: 'POST', body: JSON.stringify(body),
    }) as Promise<LabSpecimen>;
  },
  label(specimenId: number, body: LabSpecimenMutationInput) {
    return requestLab(`/lab/specimens/${specimenId}/label`, {
      method: 'POST', body: JSON.stringify(body), responseType: 'blob',
    }) as Promise<Blob>;
  },
  scan(orderId: number, barcode: string, signal?: AbortSignal) {
    return requestLab('/lab/specimens/scan', {
      method: 'POST', body: JSON.stringify({ barcode, order_id: orderId }), signal,
    }) as Promise<LabSpecimen>;
  },
};
