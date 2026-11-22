import { describe, expect, it } from 'vitest';
import { mapAdminQueueDirections } from '../adminQueueDirections';

describe('mapAdminQueueDirections', () => {
    it('normalizes omitted optional collections for a stable domain view', () => {
        const mapped = mapAdminQueueDirections({
            as_of_day: '2026-10-18',
            directions: [
                {
                    profile: {
                        id: 2,
                        key: 'lab',
                        title: 'Laboratory',
                        queue_tags: ['lab'],
                        is_active: true,
                        show_on_qr_page: false,
                        display_order: 0,
                    },
                    resolved_mode: 'overview',
                    configuration_state: 'incomplete',
                    effective_availability: 'unavailable',
                    public_availability: false,
                    permanent_address_exists: false,
                },
            ],
            unattached: {},
        });

        expect(mapped.directions[0]).toMatchObject({
            resolved_mode: 'overview',
            configuration_reasons: [],
            effective_availability_reasons: [],
            booking_targets: [],
            current_day_queues: [],
            precreate_by_tag: [],
            allowed_next_actions: [],
        });
        expect(mapped.unattached).toEqual({ queue_tags: [], services: [], resources: [] });
    });
});
