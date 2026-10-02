/**
 * RQ-17 — checklist readiness computation pins (brief §3 (а)–(д), §5).
 *
 * Read-side contract: statuses are ALWAYS recomputed from API payloads;
 * these tests pin the exact readiness semantics used by the checklist:
 *  - resource axis = ACTIVE QueueResource (draft never counts — gate §3.1);
 *  - doctor axis = eligible ACTIVE Doctor record of the matching specialty
 *    (brief §3(а) literally; round-3 owner-ревью P1) — NOT the
 *    `Service.doctor_id` FK: a deactivated doctor with a stale FK must
 *    never read «готово», and a fresh canonical Doctor with no service
 *    binding yet must not read «исполнителя нет»;
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
    collectServiceAssignmentGaps,
    eligibleDoctorsForTag,
    readPermanentAddressSupported,
    specialtyTagKey,
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

const doctor = (over: Record<string, unknown>) => ({
    id: 42,
    specialty: 'lab',
    cabinet: '101',
    active: true,
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

    it('doctor axis = eligible active Doctor record of the matching specialty (brief §3(а), round-3 P1)', () => {
        // новый канонический Doctor существует, но doctor_id ещё не
        // проставлен услуге — исполнитель УЖЕ есть (ложного «нет
        // исполнителя» больше нет)
        const newDoctor = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: null })],
            [profile({ queue_tags: ['cardiology'] })],
            [],
            {},
            [doctor({ id: 7, specialty: 'cardiology' })],
        );
        expect(newDoctor['cardiology'].axis).toBe('doctor');
        expect(newDoctor['cardiology'].eligibleDoctors).toHaveLength(1);
        expect(newDoctor['cardiology'].executorReady).toBe(true);
        // сервис-привязка — отдельное инфо-поле, НЕ критерий (а)
        expect(newDoctor['cardiology'].doctorBoundService).toBeNull();

        // без элигибельного врача FK услуги ось НЕ строит
        const withoutDoctor = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: 42 })],
            [profile({})],
            [],
        );
        expect(withoutDoctor['lab'].axis).toBeNull();
        expect(withoutDoctor['lab'].executorReady).toBe(false);
    });

    it('deactivated doctor with a stale Service.doctor_id never yields a false-ready', () => {
        // /services/admin/doctors отдаёт только активных: деактивированный
        // врач в списке отсутствует; FK услуги на это не влияет
        const checklist = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: 42 })],
            [profile({})],
            [],
            {},
            [],
        );
        expect(checklist['lab'].axis).toBeNull();
        expect(checklist['lab'].executorReady).toBe(false);

        // явно переданный неактивный/несовпадающий врач тоже не считается
        const explicitInactive = buildChecklist(
            [svc({ requires_doctor: true, doctor_id: 42 })],
            [profile({})],
            [],
            {},
            [doctor({ id: 42, active: false })],
        );
        expect(explicitInactive['lab'].executorReady).toBe(false);
    });

    it('specialty/tag mapping: blank and general sentinels and mismatches are not owners', () => {
        expect(specialtyTagKey('  Lab ')).toBe('lab');

        const owners = eligibleDoctorsForTag(
            [
                doctor({ id: 1, specialty: 'lab' }),
                doctor({ id: 2, specialty: '  LAB  ' }), // нормализация — совпадает
                doctor({ id: 3, specialty: 'cardiology' }), // mismatch
                doctor({ id: 4, specialty: 'general' }), // incomplete sentinel
                doctor({ id: 5, specialty: '   ' }), // пустая specialty
                doctor({ id: 6, specialty: null }), // нет specialty
                doctor({ id: 7, active: false }), // неактивный
            ],
            'lab',
        );
        expect(owners.map((d) => d.id)).toEqual([1, 2]);
    });

    it('REGRESSION (round-4 P2): dentistry Doctor owns the stomatology tag (alias family, NOT exact equality)', () => {
        // Здоровая конфигурация из owner-ревью: канонический Doctor.specialty
        // = 'dentistry' (SSOT core/specialties.py D-1), а queue-механика
        // живёт на теге 'stomatology' (ключ профилей). До фикса exact
        // string equality давал ложное «нет исполнителя».
        const healthy = buildChecklist(
            [svc({ queue_tag: 'stomatology', requires_doctor: true, doctor_id: null })],
            [profile({ key: 'stom-key', queue_tags: ['stomatology'] })],
            [],
            {},
            [doctor({ id: 42, specialty: 'dentistry' })],
        );
        expect(healthy['stomatology'].axis).toBe('doctor');
        expect(healthy['stomatology'].executorReady).toBe(true);
        expect(healthy['stomatology'].eligibleDoctors.map((d) => d.id)).toEqual([42]);

        // Обратная симметрия: легаси-врач 'stomatology' владеет каноническим
        // тегом 'dentistry'
        const reverse = eligibleDoctorsForTag(
            [doctor({ id: 9, specialty: 'stomatology' })],
            'dentistry',
        );
        expect(reverse.map((d) => d.id)).toEqual([9]);
    });

    it('dental-family aliases (dentistry/dental/stomatology/dentist) match each other; cross-family and sentinels stay out', () => {
        // Зеркало backend specialty_variants: любой вариант семейства
        // находится фильтром по любому другому (D-1)
        const family = eligibleDoctorsForTag(
            [
                doctor({ id: 1, specialty: 'dentistry' }),
                doctor({ id: 2, specialty: 'dental' }),
                doctor({ id: 3, specialty: 'stomatology' }),
                doctor({ id: 4, specialty: 'dentist' }),
                doctor({ id: 5, specialty: '  Dentistry ' }), // нормализация + семейство
            ],
            'stomatology',
        );
        expect(family.map((d) => d.id)).toEqual([1, 2, 3, 4, 5]);

        // Чужие семейства по-прежнему не владельцы
        const foreign = eligibleDoctorsForTag(
            [
                doctor({ id: 6, specialty: 'cardiology' }),
                doctor({ id: 7, specialty: 'lab' }),
                doctor({ id: 8, specialty: 'general' }), // sentinel не входит в семейства
                doctor({ id: 9, specialty: 'dentistic' }), // неизвестное — только exact
                doctor({ id: 10, active: false, specialty: 'dentist' }), // неактивный
            ],
            'dentistry',
        );
        expect(foreign).toHaveLength(0);
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

describe('collectServiceAssignmentGaps — Workstream A (Tasks 2/5)', () => {
    it('doctor_missing: pinned service whose doctor is not in the active roster', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 10, name: 'ЭхоКГ', requires_doctor: true, doctor_id: 999, queue_tag: 'cardio', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'cardiology' })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('doctor_missing');
        expect(gaps[0].pinnedDoctorId).toBe(999);
        expect(gaps[0].serviceCode ?? null).toBeNull();
    });

    it('specialty_mismatch: pinned doctor present but of the wrong specialty family', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 11, name: 'Кардио-услуга', requires_doctor: true, doctor_id: 42, queue_tag: 'cardio', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'dentistry' })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('specialty_mismatch');
    });

    it('missing_specialty_mapping: doctor-performed service without department_key', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 12, name: 'Рентгенография зуба', requires_doctor: true, doctor_id: null, queue_tag: 'stomatology', department_key: null })],
            [doctor({ id: 42, specialty: 'dentistry' })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('missing_specialty_mapping');
        expect(gaps[0].pinnedDoctorId).toBeNull();
    });

    it('healthy rows: pinned eligible doctor and doctorless services produce no gaps', () => {
        const gaps = collectServiceAssignmentGaps(
            [
                svc({ id: 13, name: 'ЭхоКГ врача 42', requires_doctor: true, doctor_id: 42, queue_tag: 'cardio', department_key: 'cardiology' }),
                svc({ id: 14, name: 'Лаборатория', requires_doctor: false, doctor_id: null, queue_tag: 'lab', department_key: null }),
                svc({ id: 15, name: 'Неактивная', active: false, requires_doctor: true, doctor_id: 999, queue_tag: 'cardio', department_key: 'cardiology' }),
            ],
            [doctor({ id: 42, specialty: 'cardiology' })],
        );
        expect(gaps).toEqual([]);
    });

    it('dental alias family keeps a dentistry doctor eligible for a stomatology department_key', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 16, name: 'Рентген зуба закреплённая', requires_doctor: true, doctor_id: 42, queue_tag: 'stomatology', department_key: 'stomatology' })],
            [doctor({ id: 42, specialty: 'dentistry' })],
        );
        expect(gaps).toEqual([]);
    });
});

describe('collectServiceAssignmentGaps — PR #3511 review P1 (round 5): pin without flags', () => {
    it('unflagged pinned service participates in the contract: missing doctor is a gap (was silently skipped)', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 20, name: 'ЭхоКГ закреплённая', requires_doctor: false, doctor_id: 999, queue_tag: 'cardio', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'cardiology' })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('doctor_missing');
        expect(gaps[0].pinnedDoctorId).toBe(999);
    });

    it('unflagged pinned service with wrong-specialty doctor is a specialty_mismatch gap', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 21, name: 'Кардио-услуга без флага', requires_doctor: false, doctor_id: 42, queue_tag: 'cardio', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'dentistry' })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('specialty_mismatch');
    });

    it('healthy unflagged pin produces no gap (control)', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 22, name: 'ЭхоКГ врача 42', requires_doctor: false, doctor_id: 42, queue_tag: 'cardio', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'cardiology' })],
        );
        expect(gaps).toEqual([]);
    });

    it('resource_queue_conflict: pinned service (flagged or not) on an ACTIVE resource tag is an owner conflict', () => {
        const res = (over: Record<string, unknown>) => resource({ id: 77, queue_tag: 'ecg', active: true, ...over });
        const services = [
            svc({ id: 23, name: 'Пин без флага на ecg', requires_doctor: false, doctor_id: 42, queue_tag: 'ecg', department_key: 'cardiology' }),
            svc({ id: 24, name: 'Пин с флагом на ecg', requires_doctor: true, doctor_id: 42, queue_tag: 'ecg', department_key: 'cardiology' }),
        ];
        const gaps = collectServiceAssignmentGaps(
            services,
            [doctor({ id: 42, specialty: 'cardiology' })],
            [res({})],
        );
        expect(gaps.map((g) => [g.serviceId, g.reason])).toEqual([
            [23, 'resource_queue_conflict'],
            [24, 'resource_queue_conflict'],
        ]);
        expect(gaps[0].queueTag).toBe('ecg');
        expect(gaps[0].pinnedDoctorId).toBe(42);
    });

    it('a DRAFT (inactive) registry row is NOT a conflict; unpinned flagged K10 stays healthy', () => {
        const gaps = collectServiceAssignmentGaps(
            [
                svc({ id: 25, name: 'Пин на черновом ecg', requires_doctor: false, doctor_id: 42, queue_tag: 'ecg', department_key: 'cardiology' }),
                svc({ id: 26, name: 'K10 без пина', requires_doctor: true, doctor_id: null, queue_tag: 'ecg', department_key: 'cardiology' }),
            ],
            [doctor({ id: 42, specialty: 'cardiology' })],
            [resource({ id: 77, queue_tag: 'ecg', active: false })],
        );
        expect(gaps).toEqual([]);
    });

    it('tag normalization applies to the conflict match (trimmed/case-insensitive)', () => {
        const gaps = collectServiceAssignmentGaps(
            [svc({ id: 27, name: 'Пин на тег с пробелом', requires_doctor: false, doctor_id: 42, queue_tag: ' ECG ', department_key: 'cardiology' })],
            [doctor({ id: 42, specialty: 'cardiology' })],
            [resource({ id: 77, queue_tag: 'ecg', active: true })],
        );
        expect(gaps).toHaveLength(1);
        expect(gaps[0].reason).toBe('resource_queue_conflict');
    });
});
