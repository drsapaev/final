/**
 * RQ-17 — checklist readiness computation pins (brief §3 (а)–(д), §5).
 *
 * Read-side contract: statuses are ALWAYS recomputed from API payloads;
 * these tests pin the exact readiness semantics used by the checklist:
 *  - resource axis = ACTIVE QueueResource (draft never counts — gate §3.1);
 *  - doctor axis = active requires_doctor service with assigned doctor;
 *  - (б) active services of the tag;
 *  - (в)/(г) active owning profile / QR visibility;
 *  - (д) permanent_address.supported from the entry-methods enumeration
 *    (null when unknown — no honest claim without a supported flag).
 */
import { describe, expect, it } from 'vitest';
import {
    buildChecklist,
    candidateTags,
    collectKnownTags,
    readPermanentAddressSupported,
} from '../setupDirectionsReadiness';

const svc = (over: Record<string, unknown>) => ({
    id: 1,
    name: 'Service',
    active: true,
    requires_doctor: false,
    queue_tag: 'lab',
    doctor_id: null,
    ...over,
});

const profile = (over: Record<string, unknown>) => ({
    key: 'lab-key',
    title_ru: 'Лаборатория',
    is_active: true,
    show_on_qr_page: true,
    queue_tags: ['lab'],
    ...over,
});

const resource = (over: Record<string, unknown>) => ({
    id: 1,
    code: 'res-lab',
    queue_tag: 'lab',
    display_name: 'Lab resource',
    active: false,
    start_number_online: 1,
    max_online_per_day: 15,
    default_cabinet: null,
    ...over,
});

describe('collectKnownTags', () => {
    it('unions profile tags, service tags and registry rows (sorted)', () => {
        const tags = collectKnownTags(
            [svc({ queue_tag: 'ultrasound' }), svc({ queue_tag: null })],
            [profile({ queue_tags: ['lab', 'ultrasound'] })],
            [resource({ queue_tag: 'lab' })],
        );
        expect(tags).toEqual(['lab', 'ultrasound']);
    });
});

describe('buildChecklist — axis (а)', () => {
    it('resource axis requires an ACTIVE registry row — draft never counts', () => {
        const draftOnly = buildChecklist(
            [svc({})],
            [profile({})],
            [resource({ active: false })],
        );
        expect(draftOnly['lab'].axis).toBeNull();
        expect(draftOnly['lab'].executorReady).toBe(false);
        expect(draftOnly['lab'].activeResource).toBeNull();

        const active = buildChecklist(
            [svc({})],
            [profile({})],
            [resource({ active: true })],
        );
        expect(active['lab'].axis).toBe('resource');
        expect(active['lab'].executorReady).toBe(true);
    });

    it('doctor axis = active requires_doctor service with an assigned doctor', () => {
        const withoutDoctor = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: null })],
            [profile({})],
            [],
        );
        expect(withoutDoctor['lab'].axis).toBeNull();

        const withDoctor = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: 42 })],
            [profile({})],
            [],
        );
        expect(withDoctor['lab'].axis).toBe('doctor');
        expect(withDoctor['lab'].doctorService?.doctor_id).toBe(42);
    });

    it('inactive services never carry the axis or (б)', () => {
        const checklist = buildChecklist(
            [
                svc({ active: false, requires_doctor: true, doctor_id: 42 }),
                svc({ active: false }),
            ],
            [],
            [],
        );
        expect(checklist['lab'].axis).toBeNull();
        expect(checklist['lab'].activeServices).toHaveLength(0);
        expect(checklist['lab'].executorReady).toBe(false);
    });
});

describe('buildChecklist — profile steps (в)/(г)', () => {
    it('owning profile must be active; visibility is its own step', () => {
        const checklist = buildChecklist(
            [svc({})],
            [profile({ show_on_qr_page: false })],
            [],
        );
        expect(checklist['lab'].owningProfile).not.toBeNull();
        expect(checklist['lab'].owningProfileVisible).toBe(false);

        const noProfile = buildChecklist(
            [svc({})],
            [profile({ is_active: false })],
            [],
        );
        expect(noProfile['lab'].owningProfile).toBeNull();
        expect(noProfile['lab'].owningProfileVisible).toBe(false);
    });
});

describe('buildChecklist — permanent address (д)', () => {
    it('reads permanent_address.supported only for QR-visible profiles', () => {
        const checklist = buildChecklist(
            [svc({})],
            [profile({ show_on_qr_page: true })],
            [],
            {
                'lab-key': {
                    entry_methods: [
                        { method: 'session_qr', supported: true },
                        { method: 'permanent_address', supported: true },
                    ],
                },
            },
        );
        expect(checklist['lab'].permanentAddress).toBe(true);
    });

    it('unknown when profile is not QR-visible or read failed', () => {
        const hidden = buildChecklist(
            [svc({})],
            [profile({ show_on_qr_page: false })],
            [],
            { 'lab-key': { entry_methods: [{ method: 'permanent_address', supported: true }] } },
        );
        expect(hidden['lab'].permanentAddress).toBeNull();

        const failed = buildChecklist(
            [svc({})],
            [profile({})],
            [],
            { 'lab-key': null },
        );
        expect(failed['lab'].permanentAddress).toBeNull();
    });
});

describe('readPermanentAddressSupported', () => {
    it('finds the permanent_address method and honest flag', () => {
        expect(
            readPermanentAddressSupported({
                entry_methods: [{ method: 'permanent_address', supported: false }],
            }),
        ).toBe(false);
        expect(readPermanentAddressSupported({ entry_methods: [] })).toBeNull();
        expect(readPermanentAddressSupported(null)).toBeNull();
    });
});

describe('candidateTags — «ноль технических ключей» (§4(3))', () => {
    it('offers existing profile/service tags only — registry-only tags are not choices', () => {
        const tags = candidateTags(
            [svc({ queue_tag: 'lab' })],
            [profile({ queue_tags: ['lab', 'ultrasound'] })],
        );
        expect(tags).toEqual(['lab', 'ultrasound']);
    });
});
