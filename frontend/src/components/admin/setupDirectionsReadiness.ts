/**
 * RQ-17 — checklist readiness computation (brief §3 steps (а)–(д), §4(1)).
 *
 * Pure module: statuses are ALWAYS recomputed from API payloads — the
 * checklist never stores readiness locally (brief §5: «статус всегда
 * пересчитывается из API, не хранится локально»).
 *
 * Steps per tag row:
 *  (а) исполнитель по оси D-01: resource-owned — ACTIVE QueueResource с
 *      exact queue_tag (resource routing predicate); doctor-owned —
 *      ЭЛИГИБЕЛЬНАЯ активная Doctor-запись соответствующей specialty
 *      (brief §3(а) буквально; round-3 owner-ревью P1): read-side
 *      `/services/admin/doctors` отдаёт только активных врачей, а
 *      specialty сопоставляется тегу направления (specialty/tag
 *      mapping; alias-семейства SSOT core/specialties.py —
 *      round-4 owner-ревью P2: dentistry-врач владеет тегом
 *      stomatology). FK `Service.doctor_id` НЕ является критерием (а):
 *      деактивированный врач с оставшимся FK давал ложное «готово», а
 *      новый канонический Doctor без проставленного FK — ложное «нет
 *      исполнителя»;
 *  (б) ≥ 1 активная услуга с этим queue_tag;
 *  (в) активный QueueProfile владеет тегом;
 *  (г) профиль visible (show_on_qr_page);
 *  (д) provision-статус постоянного адреса (entry-methods read-side;
 *      null = статус неизвестен/профиль не QR-visible).
 */

export interface ChecklistServiceDto {
  id: number;
  name?: string;
  active?: boolean;
  doctor_id?: number | null;
  requires_doctor?: boolean | null;
  queue_tag?: string | null;
  [key: string]: unknown;
}

export interface ChecklistProfileDto {
  key?: string;
  title?: string;
  title_ru?: string;
  queue_tags?: string[];
  is_active?: boolean;
  show_on_qr_page?: boolean;
  [key: string]: unknown;
}

export interface ChecklistResourceDto {
  id: number;
  queue_tag: string;
  display_name?: string;
  active?: boolean;
  [key: string]: unknown;
}

/** Read-side `GET /services/admin/doctors` — активные Doctor-записи. */
export interface ChecklistDoctorDto {
  id: number;
  specialty?: string | null;
  cabinet?: string | null;
  active?: boolean;
  [key: string]: unknown;
}

/** Read-side `GET /queue/directions/{profile_key}/entry-methods`. */
export interface EntryMethodsDto {
  direction_key?: string;
  entry_methods?: Array<{ method?: string; supported?: boolean }>;
  [key: string]: unknown;
}

export type DirectionAxis = 'resource' | 'doctor' | null;

export interface TagReadiness {
  tag: string;
  axis: DirectionAxis;
  /** (а) — ACTIVE QueueResource (resource-owned leg). */
  activeResource: ChecklistResourceDto | null;
  /**
   * (а) — doctor-owned leg: элигибельная активная Doctor-запись
   * соответствующей specialty (brief §3(а)). Сервис-привязка
   * (требуется runtime-владельцу тега — single_active_service_doctor)
   * отражена отдельно в doctorBoundService.
   */
  eligibleDoctors: ChecklistDoctorDto[];
  /**
   * Инфо-поле: активная requires_doctor-услуга тега с назначенным врачом
   * (сервис-привязка runtime-владельца; НЕ критерий (а)).
   */
  doctorBoundService: ChecklistServiceDto | null;
  /** (а) — исполнитель готов хотя бы по одной оси. */
  executorReady: boolean;
  /** (б) — активные услуги тега (все). */
  activeServices: ChecklistServiceDto[];
  /** Активные doctorless-услуги тега (нижняя нога инварианта §3.1 — подсказка для ресурсной оси). */
  activeDoctorlessServices: ChecklistServiceDto[];
  /** (в) — активный профиль-владелец тега. */
  owningProfile: ChecklistProfileDto | null;
  /** (г) — профиль QR-visible. */
  owningProfileVisible: boolean;
  /** (д) — provision постоянного адреса; null = неизвестно (не QR-visible/ошибка чтения). */
  permanentAddress: boolean | null;
}

export type Checklist = Record<string, TagReadiness>;

/** Union of tags worth a checklist row: profiles first, then services, then registry rows. */
export function collectKnownTags(
  services: ChecklistServiceDto[],
  profiles: ChecklistProfileDto[],
  resources: ChecklistResourceDto[],
): string[] {
  const tags = new Set<string>();
  for (const profile of profiles) {
    for (const tag of profile.queue_tags || []) {
      if (tag) {
        tags.add(tag);
      }
    }
  }
  for (const service of services) {
    if (service.queue_tag) {
      tags.add(service.queue_tag);
    }
  }
  for (const resource of resources) {
    if (resource.queue_tag) {
      tags.add(resource.queue_tag);
    }
  }
  return Array.from(tags).sort((a, b) => a.localeCompare(b));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * Нормализация для specialty/tag mapping: теги направлений в этой системе
 * каноничны по naming'у specialty (QUEUE_GROUPS: cardiology, dermatology,
 * stomatology, laboratory, …). Принадлежность врача направлению —
 * нормализованное равенство specialty и queue_tag С УЧЁТОМ alias-семейств
 * (см. specialtyFamilyKey): `Doctor.specialty` — свободная строка с
 * историческими написаниями, а `Service.queue_tag` — точный routing-ключ.
 */
export function specialtyTagKey(value: unknown): string {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

/**
 * Alias-семейство specialty (read-side matching) — зеркало SSOT
 * `backend/app/core/specialties.py` (NEEDS DECISION D-1): dentist-семейство
 * исторически живёт в четырёх написаниях — `dentistry` (каноническое
 * хранимое значение), `dental` (админская DoctorModal), `stomatology`
 * (ключ queue-механики/профилей), `dentist` (legacy). Read-side
 * `specialty_variants` считает их одним семейством: любой вариант
 * находится при фильтре по любому другому (здоровая конфигурация
 * `Doctor.specialty = dentistry` + `Service.queue_tag = stomatology` —
 * ВРАЧ ЕСТЬ, round-4 owner-ревью P2). Non-dental specialties проходят
 * без переименования; `general` — sentinel незаполненного профиля,
 * в семейства не входит и элигибельности не даёт.
 */
const DENTAL_FAMILY_SPELLINGS: ReadonlySet<string> = new Set([
  'dentistry',
  'dental',
  'stomatology',
  'dentist',
]);
const DENTAL_CANONICAL_SPECIALTY = 'dentistry';

/** Ключ alias-семейства для уже нормализованного specialty-ключа или null. */
function specialtyFamilyKey(specialtyKey: string): string | null {
  if (DENTAL_FAMILY_SPELLINGS.has(specialtyKey)) {
    return DENTAL_CANONICAL_SPECIALTY;
  }
  return null;
}

/** Sentinel незаполненного профиля врача (core/specialties.py; incomplete
 * profile не может быть владельцем очереди — тот же контракт, что и у
 * runtime-элигибельности `eligible_real_doctor`). */
const INCOMPLETE_SPECIALTY_SENTINEL = 'general';

/**
 * (а) doctor-owned leg: элигибельные активные Doctor-записи, чья specialty
 * соответствует тегу направления. Read-side `/services/admin/doctors`
 * возвращает только активных записей; элигибельность дополнительно требует
 * реальной (не-sentinel/непустой) specialty — строка с пустой/`general`
 * specialty не может быть владельцем направления. Соответствие —
 * alias-family matching (зеркало read-side SSOT
 * `core/specialties.py::specialty_variants`): точное нормализованное
 * равенство ИЛИ одно семейство написаний (dentistry/dental/stomatology/
 * dentist). Exact string equality здесь НЕдостаточен: канонический
 * `Doctor.specialty = dentistry` при queue-теге `stomatology`
 * (ключ механики профилей) — здоровая конфигурация, а не «нет
 * исполнителя» (round-4 owner-ревью P2).
 */
export function eligibleDoctorsForTag(
  doctors: ChecklistDoctorDto[],
  tag: string,
): ChecklistDoctorDto[] {
  const tagKey = specialtyTagKey(tag);
  if (!tagKey) {
    return [];
  }
  const tagFamily = specialtyFamilyKey(tagKey);
  return doctors.filter((doctor) => {
    if (doctor.active === false) {
      return false;
    }
    const specialtyKey = specialtyTagKey(doctor.specialty);
    if (
      !specialtyKey ||
      specialtyKey === INCOMPLETE_SPECIALTY_SENTINEL
    ) {
      return false;
    }
    if (specialtyKey === tagKey) {
      return true;
    }
    // Alias-семейство (backend specialty_variants): врач dentistry —
    // владелец тега stomatology и наоборот; dental/dentist — то же
    // семейство. Незнакомые specialty совпадают только точно.
    return tagFamily !== null && specialtyFamilyKey(specialtyKey) === tagFamily;
  });
}

/** `permanent_address.supported` из перечисления entry-methods (brief §3(д)). */
export function readPermanentAddressSupported(response: unknown): boolean | null {
  if (!isRecord(response)) {
    return null;
  }
  const methods = response.entry_methods;
  if (!Array.isArray(methods)) {
    return null;
  }
  for (const entry of methods) {
    if (isRecord(entry) && entry.method === 'permanent_address') {
      return entry.supported === true;
    }
  }
  return null;
}

export function buildChecklist(
  services: ChecklistServiceDto[],
  profiles: ChecklistProfileDto[],
  resources: ChecklistResourceDto[],
  entryMethodsByProfileKey: Record<string, EntryMethodsDto | null> = {},
  doctors: ChecklistDoctorDto[] = [],
  // RQ-18 follow-up round-3 (P2): post-provision recheck answers override
  // the entry-methods flag per profile (undefined = no answer yet,
  // boolean = proven, null = recheck failed → honest unknown). Kept
  // SEPARATE from the methods map: an unknown must never destroy the
  // last-known payload, or the row could never leave unknown again.
  postProvisionSupportByProfileKey: Record<string, boolean | null | undefined> = {},
): Checklist {
  const checklist: Checklist = {};
  const tags = collectKnownTags(services, profiles, resources);

  for (const tag of tags) {
    const activeServices = services.filter(
      (s) => s.queue_tag === tag && s.active !== false,
    );
    const activeDoctorlessServices = activeServices.filter(
      (s) => s.requires_doctor !== true,
    );
    const activeResource =
      resources.find((r) => r.queue_tag === tag && r.active === true) || null;

    // (а) doctor-owned leg — по реальным Doctor-записям specialty/tag
    // mapping (brief §3(а)), НЕ по FK услуги; сервис-привязка — инфо
    const eligibleDoctors = eligibleDoctorsForTag(doctors, tag);
    const doctorBoundService =
      activeServices.find(
        (s) => s.requires_doctor === true && s.doctor_id != null,
      ) || null;

    const owningProfile =
      profiles.find(
        (p) =>
          p.is_active !== false &&
          (p.queue_tags || []).includes(tag),
      ) || null;
    const owningProfileVisible =
      owningProfile != null && owningProfile.show_on_qr_page === true;

    let permanentAddress: boolean | null = null;
    const profileKey = owningProfile?.key;
    if (owningProfileVisible && profileKey) {
      // RQ-18 follow-up round-3 (P2): a recheck answer (true/false/unknown)
      // is the freshest truth for this profile; without one, the last
      // known entry-methods payload stays authoritative.
      const recheckOverride = postProvisionSupportByProfileKey[profileKey];
      if (recheckOverride !== undefined) {
        permanentAddress = recheckOverride;
      } else if (entryMethodsByProfileKey[profileKey]) {
        permanentAddress = readPermanentAddressSupported(
          entryMethodsByProfileKey[profileKey],
        );
      }
    }

    const axis: DirectionAxis = activeResource
      ? 'resource'
      : eligibleDoctors.length > 0
        ? 'doctor'
        : null;

    checklist[tag] = {
      tag,
      axis,
      activeResource,
      eligibleDoctors,
      doctorBoundService,
      executorReady: activeResource != null || eligibleDoctors.length > 0,
      activeServices,
      activeDoctorlessServices,
      owningProfile,
      owningProfileVisible,
      permanentAddress,
    };
  }

  return checklist;
}

/** Candidate tags for wizard/manager selects — выбор из существующих значений (§4(3)). */
export function candidateTags(
  services: ChecklistServiceDto[],
  profiles: ChecklistProfileDto[],
): string[] {
  return collectKnownTags(services, profiles, []);
}
