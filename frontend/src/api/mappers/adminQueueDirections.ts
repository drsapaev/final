import type { AdminQueueDirectionsResponseDto } from '../../types/api';
import type {
    QueueAdminDirections,
    QueueDirectionNextAction,
} from '../../types/domain/adminQueueDirections';

/** Normalize optional OpenAPI arrays before the read model reaches React. */
export function mapAdminQueueDirections(
    dto: AdminQueueDirectionsResponseDto,
): QueueAdminDirections {
    return {
        as_of_day: dto.as_of_day,
        directions: (dto.directions || []).map((direction) => ({
            profile: {
                ...direction.profile,
                queue_tags: [...(direction.profile.queue_tags || [])],
            },
            resolved_mode: direction.resolved_mode,
            configuration_state: direction.configuration_state,
            configuration_reasons: (direction.configuration_reasons || []).map((reason) => ({ ...reason })),
            effective_availability: direction.effective_availability,
            effective_availability_reasons: [...(direction.effective_availability_reasons || [])],
            booking_targets: (direction.booking_targets || []).map((target) => ({
                ...target,
                existing_daily_queue_ids: [...(target.existing_daily_queue_ids || [])],
            })),
            current_day_queues: (direction.current_day_queues || []).map((queue) => ({ ...queue })),
            public_availability: direction.public_availability,
            permanent_address_exists: direction.permanent_address_exists,
            precreate_by_tag: (direction.precreate_by_tag || []).map((entry) => ({
                ...entry,
                existing_daily_queue_ids: [...(entry.existing_daily_queue_ids || [])],
                reason_codes: [...(entry.reason_codes || [])],
            })),
            allowed_next_actions: (direction.allowed_next_actions || []).map(
                (action): QueueDirectionNextAction => ({ ...action }),
            ),
        })),
        unattached: {
            queue_tags: [...(dto.unattached?.queue_tags || [])],
            services: (dto.unattached?.services || []).map((service) => ({ ...service })),
            resources: (dto.unattached?.resources || []).map((resource) => ({ ...resource })),
        },
    };
}
