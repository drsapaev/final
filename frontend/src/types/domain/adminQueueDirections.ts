/**
 * Frontend domain view of the Admin queue-directions read model.
 * Raw OpenAPI shapes are mapped at the API boundary before components use them.
 */

export type QueueDirectionMode = 'booking' | 'overview' | 'unresolved';
export type QueueDirectionConfigurationState = 'ready' | 'incomplete' | 'conflict' | 'unavailable';
export type QueueDirectionAvailability = 'available' | 'unavailable' | 'conflict';
export type QueueDirectionOwner = 'doctor' | 'resource';

export interface QueueDirectionProfile {
    id: number;
    key: string;
    title: string;
    title_ru?: string | null;
    queue_tags: string[];
    department_key?: string | null;
    is_active: boolean;
    show_on_qr_page: boolean;
    display_order: number;
    icon?: string | null;
    color?: string | null;
}

export interface QueueDirectionReason {
    code: string;
    severity: 'info' | 'warning' | 'error';
    subject_type?: 'queue_profile' | 'department' | 'queue_tag' | null;
    subject_key?: string | null;
}

export interface QueueDirectionBookingTarget {
    owner_type: QueueDirectionOwner;
    owner_id: number;
    queue_tag: string;
    label: string;
    is_active: boolean;
    eligible_for_new_booking: boolean;
    existing_daily_queue_ids: number[];
}

export interface QueueDirectionDailyQueueReference {
    daily_queue_id: number;
    queue_tag: string;
    owner_type: QueueDirectionOwner | 'unresolved';
    owner_id?: number | null;
}

export interface QueueDirectionPrecreateTag {
    queue_tag: string;
    state: 'eligible' | 'already_exists' | 'blocked';
    can_precreate: boolean;
    active_service_count: number;
    owner_type?: QueueDirectionOwner | null;
    owner_id?: number | null;
    existing_daily_queue_ids: number[];
    reason_codes: string[];
}

export interface QueueDirectionNextAction {
    kind:
        | 'restore_profile'
        | 'configure_ownership'
        | 'review_configuration'
        | 'publish_profile'
        | 'provision_permanent_address';
    entity_type: 'queue_profile' | 'queue_tag' | 'department';
    entity_id?: number | null;
    entity_key?: string | null;
}

export interface QueueAdminDirection {
    profile: QueueDirectionProfile;
    resolved_mode: QueueDirectionMode;
    configuration_state: QueueDirectionConfigurationState;
    configuration_reasons: QueueDirectionReason[];
    effective_availability: QueueDirectionAvailability;
    effective_availability_reasons: string[];
    booking_targets: QueueDirectionBookingTarget[];
    current_day_queues: QueueDirectionDailyQueueReference[];
    public_availability: boolean;
    permanent_address_exists: boolean;
    precreate_by_tag: QueueDirectionPrecreateTag[];
    allowed_next_actions: QueueDirectionNextAction[];
}

export interface QueueDirectionUnattachedService {
    service_id: number;
    name: string;
    code?: string | null;
    queue_tag?: string | null;
    active: boolean;
}

export interface QueueDirectionUnattachedResource {
    resource_id: number;
    queue_tag: string;
    display_name: string;
    active: boolean;
}

export interface QueueDirectionUnattachedCatalog {
    queue_tags: string[];
    services: QueueDirectionUnattachedService[];
    resources: QueueDirectionUnattachedResource[];
}

export interface QueueAdminDirections {
    as_of_day: string;
    directions: QueueAdminDirection[];
    unattached: QueueDirectionUnattachedCatalog;
}
