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
 *      активная услуга тега с requires_doctor=true и назначенным врачом
 *      (doctor-owner fallback morning pipeline);
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
  /** (а) — doctor-owned leg: активная doctor-required услуга тега с врачом. */
  doctorService: ChecklistServiceDto | null;
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
    const doctorService =
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
    if (owningProfileVisible && profileKey && entryMethodsByProfileKey[profileKey]) {
      permanentAddress = readPermanentAddressSupported(
        entryMethodsByProfileKey[profileKey],
      );
    }

    const axis: DirectionAxis = activeResource
      ? 'resource'
      : doctorService
        ? 'doctor'
        : null;

    checklist[tag] = {
      tag,
      axis,
      activeResource,
      doctorService,
      executorReady: activeResource != null || doctorService != null,
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
