export type LabWorklistView = 'actionable' | 'today' | 'overdue' | 'awaiting_specimen' | 'in_review' | 'ready';
export type LabWorklistSort = 'oldest' | 'newest' | 'name';

export interface LabWorklistQuery {
  view: LabWorklistView;
  sort: LabWorklistSort;
  q: string;
  barcode?: string;
  fromDate?: string;
  toDate?: string;
}

export interface LabWorklistPage {
  entries: Record<string, unknown>[];
  total: number;
  counts: Record<LabWorklistView, number>;
  next_cursor: string | null;
  date: string;
  timezone: string;
}

export const INITIAL_LAB_WORKLIST_QUERY: LabWorklistQuery = {
  view: 'actionable',
  sort: 'oldest',
  q: '',
};

export const LAB_WORKLIST_VIEWS: LabWorklistView[] = [
  'actionable', 'today', 'overdue', 'awaiting_specimen', 'in_review', 'ready',
];

export type LabSpecimenStatus = 'expected' | 'collected' | 'received' | 'accepted' | 'held' | 'rejected';
export type LabSpecimenAction = 'collect' | 'receive' | 'accept' | 'hold' | 'reject';
export type LabSpecimenCreateAction = 'recollect' | 'aliquot';
export type LabSpecimenAvailableAction = LabSpecimenAction | LabSpecimenCreateAction | 'assign' | 'print_label';

export interface LabSpecimenEvent {
  id: number;
  action: LabSpecimenAvailableAction | 'create';
  happened_at: string;
  actor_user_id: number | null;
  reason?: string | null;
}

export interface LabSpecimen {
  id: number;
  order_id: number;
  visit_id: number | null;
  barcode: string;
  material_code: string;
  container_code: string;
  status: LabSpecimenStatus;
  revision: number;
  collected_at: string | null;
  received_at: string | null;
  accepted_at: string | null;
  latest_reason: string | null;
  parent_specimen_id: number | null;
  replaces_specimen_id: number | null;
  available_actions: LabSpecimenAvailableAction[];
  visit_service_ids: number[];
  report_instance_ids: number[];
  events: LabSpecimenEvent[];
}

export interface LabSpecimenPage {
  items: LabSpecimen[];
  data_status: 'known' | 'unknown';
}

export interface LabSpecimenCreateInput {
  material_code: string;
  container_code: string;
  request_id: string;
  parent_specimen_id?: number;
  replaces_specimen_id?: number;
  visit_service_ids?: number[];
  report_instance_ids?: number[];
}

export interface LabSpecimenEventInput {
  action: LabSpecimenAction;
  expected_revision: number;
  request_id: string;
  reason?: string;
}

export interface LabSpecimenMutationInput {
  expected_revision: number;
  request_id: string;
}

export interface LabSpecimenAssignmentInput extends LabSpecimenMutationInput {
  visit_service_ids?: number[];
  report_instance_ids?: number[];
}
