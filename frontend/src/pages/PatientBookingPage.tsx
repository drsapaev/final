import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  createPublicBookingIdempotencyKey,
  createPatientPublicBookingRequest,
  resubmitPatientPublicBookingRequest,
  getPublicBookingAvailability,
  getPublicBookingErrorCode,
  getPublicBookingOptions,
  getPublicBookingPath,
  hasPublicBookingResubmitHandoff,
  getPublicBookingResubmitHandoffLocale,
  isUnknownPublicBookingOutcome,
  PUBLIC_BOOKING_SELECTION_TTL_MS,
  savePublicBookingSelection,
  takePendingPublicBookingResume,
  type PublicBookingAvailability,
  type PublicBookingLocale,
  type PublicBookingOptions,
  type PublicBookingResubmitSelection,
  type PublicBookingRequestBody,
  type PublicBookingRequestResubmitBody,
} from '../api/publicBooking';
import { getState } from '../stores/auth';

type Copy = {
  title: string;
  intro: string;
  service: string;
  doctor: string;
  date: string;
  time: string;
  timezone: string;
  choose: string;
  loading: string;
  loadingSlots: string;
  retry: string;
  unavailable: string;
  modeClosed: string;
  choosePair: string;
  noSlots: string;
  slotsError: string;
  optionsError: string;
  loginRequired: string;
  activate: string;
  login: string;
  submit: string;
  resubmit: string;
  submitting: string;
  requestSent: string;
  requestResubmitted: string;
  requestNotice: string;
  nonReserving: string;
  responseTime: string;
  expired: string;
  policyChanged: string;
  policyConfirm: string;
  policyAck: string;
  refresh: string;
  slotExpired: string;
  duplicate: string;
  rateLimited: string;
  profileRequired: string;
  requestUnknown: string;
  requestFailed: string;
  retrySame: string;
  resubmitContextExpired: string;
  contact: string;
  home: string;
  switchLanguage: string;
};

const COPY: Record<PublicBookingLocale, Copy> = {
  ru: {
    title: 'Онлайн-запись',
    intro: 'Выберите услугу, врача, дату и доступное время. Заявка не занимает время в расписании.',
    service: 'Услуга',
    doctor: 'Врач',
    date: 'Дата',
    time: 'Доступное время',
    timezone: 'Все часы указаны по времени Ташкента.',
    choose: 'Выберите',
    loading: 'Загружаем доступные варианты…',
    loadingSlots: 'Проверяем расписание…',
    retry: 'Повторить загрузку',
    unavailable: 'Онлайн-запись сейчас недоступна. Пожалуйста, свяжитесь с клиникой.',
    modeClosed: 'Этот способ записи пока не подключён. Пожалуйста, свяжитесь с клиникой.',
    choosePair: 'Для этой услуги выберите одного из доступных врачей.',
    noSlots: 'На эту дату свободного времени нет. Выберите другой день.',
    slotsError: 'Не удалось проверить расписание. Повторите попытку.',
    optionsError: 'Не удалось загрузить варианты записи. Повторите попытку.',
    loginRequired: 'Чтобы отправить заявку, войдите в свою карточку пациента. Если клиника уже завела для вас карточку, её можно активировать.',
    activate: 'Активировать карточку',
    login: 'Войти как пациент',
    submit: 'Отправить заявку',
    resubmit: 'Отправить новое время',
    submitting: 'Проверяем и отправляем…',
    requestSent: 'Заявка отправлена регистратору. Это ещё не подтверждённая запись.',
    requestResubmitted: 'Новое время отправлено регистратору в рамках вашей прежней заявки.',
    requestNotice: 'Регистратор повторно проверит выбранное время. До подтверждения время может занять другой пациент.',
    nonReserving: 'Отправка заявки не резервирует время.',
    responseTime: 'Точный срок ответа пока не обещан. Для отмены или переноса свяжитесь с регистратором.',
    expired: 'Выбор устарел и был очищен. Проверьте актуальные варианты и выберите время заново.',
    policyChanged: 'Условия записи изменились. Проверьте текущие варианты и подтвердите продолжение.',
    policyConfirm: 'Условия изменились',
    policyAck: 'Я проверил(а) обновлённые условия и хочу продолжить.',
    refresh: 'Проверить актуальные варианты',
    slotExpired: 'Выбранное время уже недоступно. Выберите другое время.',
    duplicate: 'У вас уже есть активная заявка на эти услугу, врача и время. Новая заявка не создана; свяжитесь с регистратором, если нужна помощь.',
    rateLimited: 'Слишком много заявок за короткое время. Подождите и попробуйте позже.',
    profileRequired: 'Для онлайн-заявки нужна собственная карточка пациента в клинике. Обратитесь к регистратору, чтобы проверить или активировать её.',
    requestUnknown: 'Не удалось подтвердить результат отправки. Чтобы избежать дубликата, повтор можно выполнить только для той же заявки.',
    requestFailed: 'Не удалось безопасно проверить заявку. Не отправляйте её повторно; свяжитесь с регистратором.',
    retrySame: 'Повторно проверить ту же заявку',
    resubmitContextExpired: 'Данные для изменения прежней заявки устарели или потеряны. Откройте её в личном кабинете и начните выбор времени заново.',
    contact: 'Связаться с клиникой',
    home: 'На главную',
    switchLanguage: 'O‘zbekcha',
  },
  'uz-Latn': {
    title: 'Onlayn yozilish',
    intro: 'Xizmat, shifokor, sana va bo‘sh vaqtni tanlang. So‘rov jadvaldagi vaqtni band qilmaydi.',
    service: 'Xizmat',
    doctor: 'Shifokor',
    date: 'Sana',
    time: 'Bo‘sh vaqt',
    timezone: 'Barcha vaqtlar Toshkent vaqti bilan ko‘rsatilgan.',
    choose: 'Tanlang',
    loading: 'Mavjud variantlar yuklanmoqda…',
    loadingSlots: 'Jadval tekshirilmoqda…',
    retry: 'Qayta yuklash',
    unavailable: 'Onlayn yozilish hozir mavjud emas. Iltimos, klinika bilan bog‘laning.',
    modeClosed: 'Bu yozilish turi hali ulanmagan. Iltimos, klinika bilan bog‘laning.',
    choosePair: 'Bu xizmat uchun mavjud shifokorlardan birini tanlang.',
    noSlots: 'Bu sanada bo‘sh vaqt yo‘q. Boshqa kunni tanlang.',
    slotsError: 'Jadvalni tekshirib bo‘lmadi. Qayta urinib ko‘ring.',
    optionsError: 'Yozilish variantlarini yuklab bo‘lmadi. Qayta urinib ko‘ring.',
    loginRequired: 'So‘rov yuborish uchun bemor kartangizga kiring. Klinikada kartangiz oldindan ochilgan bo‘lsa, uni faollashtirishingiz mumkin.',
    activate: 'Kartani faollashtirish',
    login: 'Bemor sifatida kirish',
    submit: 'So‘rov yuborish',
    resubmit: 'Yangi vaqtni yuborish',
    submitting: 'Tekshirilmoqda va yuborilmoqda…',
    requestSent: 'So‘rov registratorga yuborildi. Bu hali tasdiqlangan qabul emas.',
    requestResubmitted: 'Yangi vaqt avvalgi so‘rovingiz doirasida registratorga yuborildi.',
    requestNotice: 'Registrator tanlangan vaqtni qayta tekshiradi. Tasdiqlanguncha vaqtni boshqa bemor egallashi mumkin.',
    nonReserving: 'So‘rov vaqtni band qilmaydi.',
    responseTime: 'Hozircha aniq javob muddati belgilanmagan. Bekor qilish yoki ko‘chirish uchun registratorga murojaat qiling.',
    expired: 'Tanlov eskirdi va tozalandi. Joriy variantlarni tekshirib, vaqtni qayta tanlang.',
    policyChanged: 'Yozilish shartlari o‘zgardi. Joriy variantlarni tekshiring va davom etishni tasdiqlang.',
    policyConfirm: 'Shartlar o‘zgardi',
    policyAck: 'Yangilangan shartlarni tekshirdim va davom etmoqchiman.',
    refresh: 'Joriy variantlarni tekshirish',
    slotExpired: 'Tanlangan vaqt endi mavjud emas. Boshqa vaqtni tanlang.',
    duplicate: 'Bu xizmat, shifokor va vaqt uchun faol so‘rovingiz bor. Yangi so‘rov yaratilmadi; yordam uchun registratorga murojaat qiling.',
    rateLimited: 'Qisqa vaqt ichida juda ko‘p so‘rov yuborildi. Biroz kutib, keyinroq urinib ko‘ring.',
    profileRequired: 'Onlayn so‘rov uchun klinikada o‘zingizning bemor kartangiz bo‘lishi kerak. Uni tekshirish yoki faollashtirish uchun registratorga murojaat qiling.',
    requestUnknown: 'Yuborish natijasini tasdiqlab bo‘lmadi. Takroriy so‘rovni oldini olish uchun faqat ayni so‘rovni qayta tekshirish mumkin.',
    requestFailed: 'So‘rovni xavfsiz tekshirib bo‘lmadi. Uni qayta yubormang; registrator bilan bog‘laning.',
    retrySame: 'Ayni so‘rovni qayta tekshirish',
    resubmitContextExpired: 'Avvalgi so‘rovni o‘zgartirish ma’lumotlari eskirgan yoki yo‘qolgan. Bemor kabinetida so‘rovni ochib, vaqt tanlashni qaytadan boshlang.',
    contact: 'Klinika bilan bog‘lanish',
    home: 'Bosh sahifa',
    switchLanguage: 'Русский',
  },
};

function tashkentToday(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function addCalendarDays(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00.000Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function isDateWithinHorizon(date: string, today: string, maxDate?: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(date)
    && Boolean(maxDate)
    && date >= today
    && date <= (maxDate ?? '');
}

function displayTime(value: string): string | null {
  const match = /^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?$/.exec(value);
  return match ? value.slice(0, 5) : null;
}

function isPatientSession(): boolean {
  const state = getState();
  return Boolean(state.token)
    && String((state.profile as unknown as Record<string, unknown> | null)?.role ?? '').toLowerCase() === 'patient';
}

interface PatientBookingResubmitContext {
  requestId: string;
  expectedVersion: number;
  serviceSlug: string;
  doctorSlug: string;
}

type PatientBookingAttempt =
  | { kind: 'create'; body: PublicBookingRequestBody; key: string }
  | {
    kind: 'resubmit';
    requestId: string;
    body: PublicBookingRequestResubmitBody;
    key: string;
  };

function getPatientBookingResubmitContext(state: unknown, now = Date.now()): PatientBookingResubmitContext | null {
  if (!state || typeof state !== 'object') return null;
  const value = (state as { publicBookingResubmit?: unknown }).publicBookingResubmit;
  if (!value || typeof value !== 'object') return null;
  const candidate = value as Partial<PatientBookingResubmitContext>;
  const expectedVersion = candidate.expectedVersion;
  const isHandoff = hasPublicBookingResubmitHandoff(state);
  const createdAt = (candidate as typeof candidate & { createdAt?: unknown }).createdAt;
  if (isHandoff && (getPublicBookingResubmitHandoffLocale(state) === null
    || typeof createdAt !== 'number'
    || !Number.isSafeInteger(createdAt)
    || createdAt <= 0
    || now < createdAt
    || now - createdAt > PUBLIC_BOOKING_SELECTION_TTL_MS)) return null;
  if (typeof candidate.requestId !== 'string'
    || !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(candidate.requestId)
    || typeof expectedVersion !== 'number'
    || !Number.isSafeInteger(expectedVersion)
    || expectedVersion < 1
    || typeof candidate.serviceSlug !== 'string'
    || candidate.serviceSlug.length < 1
    || candidate.serviceSlug.length > 120
    || typeof candidate.doctorSlug !== 'string'
    || candidate.doctorSlug.length < 1
    || candidate.doctorSlug.length > 120) return null;
  return {
    requestId: candidate.requestId,
    expectedVersion,
    serviceSlug: candidate.serviceSlug,
    doctorSlug: candidate.doctorSlug,
  };
}

function hasPatientBookingResubmitState(state: unknown): boolean {
  return hasPublicBookingResubmitHandoff(state)
    || Boolean(state && typeof state === 'object'
      && Object.prototype.hasOwnProperty.call(state, 'publicBookingResubmit'));
}

function getErrorMessage(code: string | null, copy: Copy): string {
  switch (code) {
    case 'public_booking_unavailable':
    case 'booking_request_unavailable': return copy.unavailable;
    case 'booking_time_unavailable': return copy.slotExpired;
    case 'booking_settings_version_conflict':
    case 'booking_mode_changed': return copy.policyChanged;
    case 'booking_request_duplicate': return copy.duplicate;
    case 'booking_request_rate_limited': return copy.rateLimited;
    case 'patient_profile_required': return copy.profileRequired;
    case 'booking_request_idempotency_conflict': return copy.requestFailed;
    default: return copy.optionsError;
  }
}

export default function PatientBookingPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const routeResubmitContext = getPatientBookingResubmitContext(location.state);
  const hasRouteResubmitState = hasPatientBookingResubmitState(location.state);
  const locale: PublicBookingLocale = location.pathname.startsWith('/ru/') ? 'ru' : 'uz-Latn';
  const copy = COPY[locale];
  const [resume, setResume] = useState<ReturnType<typeof takePendingPublicBookingResume>>(null);
  const [resumeLoaded, setResumeLoaded] = useState(false);
  const resumedResubmitContext = resume?.kind === 'selection' && resume.selection.resubmit
    ? resume.selection.resubmit
    : null;
  const resubmitContext = routeResubmitContext ?? resumedResubmitContext;
  const hasResubmitNavigationState = hasRouteResubmitState
    || Boolean(resumedResubmitContext)
    || Boolean(resume?.kind === 'expired' && resume.resubmitRequired);
  const [options, setOptions] = useState<PublicBookingOptions | null>(null);
  const [availability, setAvailability] = useState<PublicBookingAvailability | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [serviceSlug, setServiceSlug] = useState(() => resubmitContext?.serviceSlug ?? '');
  const [doctorSlug, setDoctorSlug] = useState(() => resubmitContext?.doctorSlug ?? '');
  const [date, setDate] = useState('');
  const [time, setTime] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [completed, setCompleted] = useState(false);
  const [completionMessage, setCompletionMessage] = useState('');
  const [needsPolicyReview, setNeedsPolicyReview] = useState(false);
  const [policyAcknowledgedVersion, setPolicyAcknowledgedVersion] = useState<number | null>(null);
  const [unknownOutcome, setUnknownOutcome] = useState(false);
  const attemptRef = useRef<PatientBookingAttempt | null>(null);
  const resumeConsumed = useRef(false);
  const availabilityRequestGeneration = useRef(0);
  const selectedTimeRef = useRef(time);
  selectedTimeRef.current = time;
  const availabilitySelectionRef = useRef({
    serviceSlug,
    doctorSlug,
    date,
    settingsVersion: options?.settings_version ?? null,
  });
  availabilitySelectionRef.current = {
    serviceSlug,
    doctorSlug,
    date,
    settingsVersion: options?.settings_version ?? null,
  };
  const invalidateAvailabilityRequests = () => {
    availabilityRequestGeneration.current += 1;
  };
  const today = tashkentToday();
  const bookingHorizon = options?.booking_horizon_days;
  const maxDate = Number.isInteger(bookingHorizon) && (bookingHorizon ?? -1) >= 0
    ? addCalendarDays(today, bookingHorizon ?? 0)
    : undefined;
  const bookingConfigurationUsable = Boolean(options?.available
    && options.mode === 'registrar_request'
    && Number.isInteger(bookingHorizon)
    && (bookingHorizon ?? -1) >= 0);

  useEffect(() => {
    if (resumeConsumed.current) return;
    resumeConsumed.current = true;
    const pending = takePendingPublicBookingResume();
    setResume(pending);
    if (pending?.kind === 'selection') {
      setServiceSlug(pending.selection.serviceSlug);
      setDoctorSlug(pending.selection.doctorSlug);
      setDate(pending.selection.date);
      setTime(pending.selection.time);
    } else if (pending?.kind === 'expired') {
      setNotice(copy.expired);
    }
    setResumeLoaded(true);
  }, [copy.expired]);

  useEffect(() => () => {
    availabilityRequestGeneration.current += 1;
  }, []);

  useEffect(() => {
    if (!resumeLoaded) return undefined;
    let active = true;
    setOptionsLoading(true);
    setOptions(null);
    setAvailability(null);
    setError('');
    getPublicBookingOptions(locale).then((result) => {
      if (!active) return;
      setOptions(result);
      if (resume?.kind === 'selection') {
        const selection = resume.selection;
        const compatible = result.compatible_pairs.some((pair) => pair.service_slug === selection.serviceSlug
          && pair.doctor_slug === selection.doctorSlug);
        if (!result.available || result.mode !== 'registrar_request' || !compatible) {
          setServiceSlug('');
          setDoctorSlug('');
          setDate('');
          setTime('');
          setError(!result.available || result.mode !== 'registrar_request' ? copy.unavailable : copy.slotExpired);
        } else if (result.settings_version !== selection.settingsVersion) {
          setNeedsPolicyReview(true);
          setNotice(copy.policyChanged);
        }
      }
    }).catch(() => {
      if (active) setError(copy.optionsError);
    }).finally(() => {
      if (active) setOptionsLoading(false);
    });
    return () => { active = false; };
  }, [copy.optionsError, copy.policyChanged, copy.slotExpired, copy.unavailable, locale, resume, resumeLoaded]);

  const eligibleDoctors = useMemo(() => {
    if (!options || !serviceSlug) return [];
    const allowed = new Set(options.compatible_pairs
      .filter((pair) => pair.service_slug === serviceSlug)
      .map((pair) => pair.doctor_slug));
    return options.doctors.filter((doctor) => allowed.has(doctor.slug));
  }, [options, serviceSlug]);

  const pairIsAllowed = Boolean(options?.compatible_pairs.some((pair) => pair.service_slug === serviceSlug
    && pair.doctor_slug === doctorSlug));

  useEffect(() => {
    if (!resumeLoaded || !options || !options.available || options.mode !== 'registrar_request'
      || !pairIsAllowed || !date || !isDateWithinHorizon(date, today, maxDate)) {
      setAvailability(null);
      setAvailabilityLoading(false);
      if (date && maxDate && !isDateWithinHorizon(date, today, maxDate)) {
        setTime('');
        setError(copy.slotExpired);
      }
      return undefined;
    }
    let active = true;
    setAvailability(null);
    setAvailabilityLoading(true);
    getPublicBookingAvailability({ serviceSlug, doctorSlug, date }).then((result) => {
      if (!active) return;
      if (result.date !== date || result.timezone !== 'Asia/Tashkent') {
        setAvailability(null);
        setError(copy.slotsError);
        return;
      }
      if (result.settings_version !== options.settings_version) {
        setAvailability(null);
        setNeedsPolicyReview(true);
        setPolicyAcknowledgedVersion(null);
        setError(copy.policyChanged);
        return;
      }
      setAvailability(result);
      const returnedTimes = result.slots.map(displayTime).filter((slot): slot is string => Boolean(slot));
      if (selectedTimeRef.current && !returnedTimes.includes(selectedTimeRef.current)) {
        setTime('');
        setError(copy.slotExpired);
      }
    }).catch(() => {
      if (active) {
        setAvailability(null);
        setError(copy.slotsError);
      }
    }).finally(() => {
      if (active) setAvailabilityLoading(false);
    });
    return () => { active = false; };
  }, [copy.policyChanged, copy.slotExpired, copy.slotsError, date, doctorSlug, maxDate, options, pairIsAllowed, resumeLoaded, serviceSlug, today]);

  const patient = isPatientSession();
  const otherRoleSignedIn = Boolean(getState().token) && !patient;
  const formLocked = completed || unknownOutcome || submitting;
  const slots = availability?.slots.map(displayTime).filter((slot): slot is string => Boolean(slot)) ?? [];

  const saveSelectionAndNavigate = (path: string) => {
    if (!serviceSlug || !doctorSlug || !date || !time || !options) return;
    const createdAt = Date.now();
    savePublicBookingSelection({
      locale,
      serviceSlug,
      doctorSlug,
      date,
      time,
      settingsVersion: availability?.settings_version ?? options.settings_version,
      createdAt,
      ...(resubmitContext ? {
        resubmit: {
          requestId: resubmitContext.requestId,
          expectedVersion: resubmitContext.expectedVersion,
          serviceSlug: resubmitContext.serviceSlug,
          doctorSlug: resubmitContext.doctorSlug,
        } satisfies PublicBookingResubmitSelection,
      } : {}),
    });
    if (resubmitContext) {
      navigate(path, {
        state: {
          publicBookingResubmitRequired: true,
          publicBookingLocale: locale,
          publicBookingResubmit: { ...resubmitContext, locale, createdAt },
        },
      });
    } else {
      navigate(path);
    }
  };

  const sendAttempt = async (attempt: PatientBookingAttempt) => {
    setSubmitting(true);
    setError('');
    try {
      if (attempt.kind === 'resubmit') {
        await resubmitPatientPublicBookingRequest(attempt.requestId, attempt.body, attempt.key);
      } else {
        await createPatientPublicBookingRequest(attempt.body, attempt.key);
      }
      attemptRef.current = null;
      setUnknownOutcome(false);
      setCompleted(true);
      const successMessage = attempt.kind === 'resubmit' ? copy.requestResubmitted : copy.requestSent;
      setCompletionMessage(successMessage);
      setNotice(successMessage);
    } catch (requestError) {
      if (isUnknownPublicBookingOutcome(requestError)) {
        attemptRef.current = attempt;
        setUnknownOutcome(true);
        setError(copy.requestUnknown);
      } else {
        attemptRef.current = null;
        setUnknownOutcome(false);
        const code = getPublicBookingErrorCode(requestError);
        setError(getErrorMessage(code, copy));
        if (code === 'booking_settings_version_conflict' || code === 'booking_mode_changed') {
          setNeedsPolicyReview(true);
          setPolicyAcknowledgedVersion(null);
          setNotice(copy.policyChanged);
          setError('');
          setOptionsLoading(true);
          try {
            const freshOptions = await getPublicBookingOptions(locale);
            setOptions(freshOptions);
          } catch {
            setError(copy.optionsError);
          } finally {
            setOptionsLoading(false);
          }
        }
        if (code === 'booking_time_unavailable') {
          setTime('');
          try {
            const latest = await getPublicBookingAvailability({ serviceSlug, doctorSlug, date });
            if (latest.settings_version === options?.settings_version) setAvailability(latest);
            else {
              setNeedsPolicyReview(true);
              setPolicyAcknowledgedVersion(null);
              setAvailability(null);
            }
          } catch {
            setAvailability(null);
            setError(copy.slotsError);
          }
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    if (hasResubmitNavigationState
      && (!resubmitContext
        || (hasPublicBookingResubmitHandoff(location.state)
          && !getPatientBookingResubmitContext(location.state)))) {
      setError(copy.resubmitContextExpired);
      return;
    }
    if (unknownOutcome && attemptRef.current) {
      await sendAttempt(attemptRef.current);
      return;
    }
    if ((hasResubmitNavigationState && !resubmitContext)
      || !patient || !options || options.mode !== 'registrar_request' || !pairIsAllowed
      || !availability || !time || !date || !serviceSlug || !doctorSlug) return;
    if (resubmitContext && (serviceSlug !== resubmitContext.serviceSlug
      || doctorSlug !== resubmitContext.doctorSlug)) return;
    if (!isDateWithinHorizon(date, today, maxDate)) {
      setTime('');
      setError(copy.slotExpired);
      return;
    }
    if (needsPolicyReview && policyAcknowledgedVersion !== options.settings_version) {
      setError(copy.policyChanged);
      return;
    }

    setSubmitting(true);
    try {
      const freshOptions = await getPublicBookingOptions(locale);
      if (!freshOptions.available || freshOptions.mode !== 'registrar_request') {
        setOptions(freshOptions);
        setError(copy.unavailable);
        return;
      }
      const freshHorizon = freshOptions.booking_horizon_days;
      const freshMaxDate = Number.isInteger(freshHorizon) && (freshHorizon ?? -1) >= 0
        ? addCalendarDays(today, freshHorizon ?? 0)
        : undefined;
      if (!isDateWithinHorizon(date, today, freshMaxDate)) {
        setOptions(freshOptions);
        setAvailability(null);
        setTime('');
        setError(copy.slotExpired);
        return;
      }
      const freshPairIsAllowed = freshOptions.compatible_pairs.some((pair) => pair.service_slug === serviceSlug
        && pair.doctor_slug === doctorSlug);
      if (!freshPairIsAllowed) {
        setOptions(freshOptions);
        setServiceSlug('');
        setDoctorSlug('');
        setTime('');
        setError(copy.slotExpired);
        return;
      }
      const freshAvailability = await getPublicBookingAvailability({ serviceSlug, doctorSlug, date });
      if (freshAvailability.date !== date || freshAvailability.timezone !== 'Asia/Tashkent') {
        setAvailability(null);
        setError(copy.slotsError);
        return;
      }
      if (freshAvailability.settings_version !== freshOptions.settings_version) {
        setOptions(freshOptions);
        setAvailability(null);
        setNeedsPolicyReview(true);
        setPolicyAcknowledgedVersion(null);
        setError(copy.policyChanged);
        return;
      }
      setOptions(freshOptions);
      setAvailability(freshAvailability);
      const freshSlots = freshAvailability.slots.map(displayTime).filter((slot): slot is string => Boolean(slot));
      if (!freshSlots.includes(time)) {
        setTime('');
        setError(copy.slotExpired);
        return;
      }
      if (freshOptions.settings_version !== options.settings_version) {
        setNeedsPolicyReview(true);
        setPolicyAcknowledgedVersion(null);
        setNotice(copy.policyChanged);
        return;
      }
      if (needsPolicyReview && policyAcknowledgedVersion !== freshOptions.settings_version) {
        setError(copy.policyChanged);
        return;
      }

      const key = createPublicBookingIdempotencyKey();
      const attempt: PatientBookingAttempt = resubmitContext
        ? {
          kind: 'resubmit',
          requestId: resubmitContext.requestId,
          body: {
            expected_version: resubmitContext.expectedVersion,
            appointment_date: date,
            appointment_time: time,
            expected_settings_version: freshOptions.settings_version,
          },
          key,
        }
        : {
          kind: 'create',
          body: {
            service_slug: serviceSlug,
            doctor_slug: doctorSlug,
            appointment_date: date,
            appointment_time: time,
            expected_settings_version: freshOptions.settings_version,
          },
          key,
        };
      attemptRef.current = attempt;
      await sendAttempt(attempt);
    } catch {
      setError(copy.slotsError);
    } finally {
      setSubmitting(false);
    }
  };

  const retryOptions = async () => {
    setError('');
    setOptionsLoading(true);
    try {
      const result = await getPublicBookingOptions(locale);
      setOptions(result);
      if (resume?.kind === 'selection') {
        const compatible = result.compatible_pairs.some((pair) => pair.service_slug === resume.selection.serviceSlug
          && pair.doctor_slug === resume.selection.doctorSlug);
        if (!result.available || result.mode !== 'registrar_request' || !compatible) {
          setServiceSlug('');
          setDoctorSlug('');
          setDate('');
          setTime('');
          setError(!result.available || result.mode !== 'registrar_request' ? copy.unavailable : copy.slotExpired);
        } else if (result.settings_version !== resume.selection.settingsVersion) {
          setNeedsPolicyReview(true);
          setNotice(copy.policyChanged);
        }
      }
    } catch {
      setError(copy.optionsError);
    } finally {
      setOptionsLoading(false);
    }
  };

  const retryAvailability = async () => {
    if (!serviceSlug || !doctorSlug || !date || !options) return;
    const requestGeneration = ++availabilityRequestGeneration.current;
    const requestedSelection = { serviceSlug, doctorSlug, date, settingsVersion: options.settings_version };
    const isCurrentRequest = () => requestGeneration === availabilityRequestGeneration.current
      && availabilitySelectionRef.current.serviceSlug === requestedSelection.serviceSlug
      && availabilitySelectionRef.current.doctorSlug === requestedSelection.doctorSlug
      && availabilitySelectionRef.current.date === requestedSelection.date
      && availabilitySelectionRef.current.settingsVersion === requestedSelection.settingsVersion;
    setError('');
    setAvailability(null);
    setAvailabilityLoading(true);
    try {
      const latest = await getPublicBookingAvailability({ serviceSlug, doctorSlug, date });
      if (!isCurrentRequest()) return;
      if (!isDateWithinHorizon(date, today, maxDate)
        || latest.date !== date || latest.timezone !== 'Asia/Tashkent') {
        setAvailability(null);
        setError(copy.slotsError);
      } else if (latest.settings_version !== options.settings_version) {
        setNeedsPolicyReview(true);
        setPolicyAcknowledgedVersion(null);
        setError(copy.policyChanged);
      } else {
        setAvailability(latest);
      }
    } catch {
      if (isCurrentRequest()) setError(copy.slotsError);
    } finally {
      if (isCurrentRequest()) setAvailabilityLoading(false);
    }
  };

  const selectedService = options?.services.find((service) => service.slug === serviceSlug);
  const selectedDoctor = options?.doctors.find((doctor) => doctor.slug === doctorSlug);

  return (
    <div className="public-site">
      <a className="public-site__skip-link" href="#main-content">{locale === 'ru' ? 'Перейти к основному содержимому' : 'Asosiy mazmunga o‘tish'}</a>
      <header className="public-site__header">
        <a className="public-site__brand" href={locale === 'ru' ? '/ru' : '/'}>
          <span className="public-site__brand-mark" aria-hidden="true">K</span>
          <span>Doktor KosMed Clinic</span>
        </a>
        <Link
          className="public-site__language"
          to={getPublicBookingPath(locale === 'ru' ? 'uz-Latn' : 'ru')}
          state={location.state}
        >
          {copy.switchLanguage}
        </Link>
      </header>
      <main id="main-content" lang={locale} className="public-site__main public-site__section" tabIndex={-1}>
        <h1>{copy.title}</h1>
        <p className="public-site__muted">{copy.intro}</p>

        {notice && !(needsPolicyReview && notice === copy.policyChanged)
          ? <p role="status" aria-live="polite" className="public-site__empty">{notice}</p>
          : null}
        {error ? <p role="alert" className="public-site__empty">{error}</p> : null}

        {optionsLoading || !resumeLoaded ? <p role="status">{copy.loading}</p> : null}
        {!optionsLoading && !options && error ? (
          <button type="button" className="public-site__button public-site__button--primary" onClick={retryOptions}>{copy.retry}</button>
        ) : null}
        {!optionsLoading && options && !options.available ? (
          <section className="public-site__section" aria-labelledby="booking-unavailable-title">
            <h2 id="booking-unavailable-title">{copy.unavailable}</h2>
            <a className="public-site__button public-site__button--primary" href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
          </section>
        ) : null}
        {!optionsLoading && options?.available && options.mode !== 'registrar_request' ? (
          <section className="public-site__section" aria-labelledby="booking-mode-title">
            <h2 id="booking-mode-title">{copy.modeClosed}</h2>
            <a className="public-site__button public-site__button--primary" href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
          </section>
        ) : null}
        {!optionsLoading && hasResubmitNavigationState && !resubmitContext ? (
          <section className="public-site__section" role="alert">
            <h2>{copy.unavailable}</h2>
            <p>{copy.resubmitContextExpired}</p>
            <a className="public-site__button public-site__button--primary" href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
          </section>
        ) : null}
        {!optionsLoading && options?.available && options.mode === 'registrar_request' && !bookingConfigurationUsable ? (
          <section className="public-site__section" aria-labelledby="booking-config-unavailable-title">
            <h2 id="booking-config-unavailable-title">{copy.unavailable}</h2>
            <a className="public-site__button public-site__button--primary" href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
          </section>
        ) : null}
        {!optionsLoading && bookingConfigurationUsable && options && resubmitContext && !pairIsAllowed ? (
          <section className="public-site__section" role="alert">
            <h2>{copy.unavailable}</h2>
            <a className="public-site__button public-site__button--primary" href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
          </section>
        ) : null}
        {!optionsLoading && bookingConfigurationUsable && options && !completed
          && (!hasResubmitNavigationState || Boolean(resubmitContext && pairIsAllowed)) ? (
          <form className="public-site__booking-form" onSubmit={handleSubmit} aria-label={copy.title}>
            <label className="public-site__booking-field" htmlFor="public-booking-service">
              {copy.service}
              <select id="public-booking-service" className="public-site__booking-control" value={serviceSlug} disabled={formLocked || Boolean(resubmitContext)} required
                onChange={(event) => { invalidateAvailabilityRequests(); setServiceSlug(event.target.value); setDoctorSlug(''); setDate(''); setTime(''); setAvailability(null); setError(''); setNotice(''); }}>
                <option value="">{copy.choose}</option>
                {options.services.map((service) => <option key={service.slug} value={service.slug}>{service.name}</option>)}
              </select>
            </label>
            <label className="public-site__booking-field" htmlFor="public-booking-doctor">
              {copy.doctor}
              <select id="public-booking-doctor" className="public-site__booking-control" value={doctorSlug} disabled={formLocked || !serviceSlug || Boolean(resubmitContext)} required
                onChange={(event) => { invalidateAvailabilityRequests(); setDoctorSlug(event.target.value); setDate(''); setTime(''); setAvailability(null); setError(''); setNotice(''); }}>
                <option value="">{copy.choose}</option>
                {eligibleDoctors.map((doctor) => <option key={doctor.slug} value={doctor.slug}>{doctor.name}</option>)}
              </select>
            </label>
            {serviceSlug && eligibleDoctors.length === 0 ? <p className="public-site__muted">{copy.choosePair}</p> : null}
            <label className="public-site__booking-field" htmlFor="public-booking-date">
              {copy.date}
            <input id="public-booking-date" aria-label={copy.date} className="public-site__booking-control" type="date" value={date} min={today} max={maxDate}
                disabled={formLocked || !doctorSlug || !maxDate} required
                onChange={(event) => { invalidateAvailabilityRequests(); setDate(event.target.value); setTime(''); setError(''); setNotice(''); }} />
            </label>
            {availabilityLoading ? <p role="status">{copy.loadingSlots}</p> : null}
            {!availability && !availabilityLoading && serviceSlug && doctorSlug && date ? (
              <button type="button" className="public-site__button" onClick={retryAvailability}>{copy.refresh}</button>
            ) : null}
            {availability && !availabilityLoading ? (
              <fieldset className="public-site__section public-site__booking-fieldset" disabled={formLocked}>
                <legend>{copy.time}</legend>
                <p className="public-site__muted">{copy.timezone}</p>
                {slots.length === 0 ? <p className="public-site__muted">{copy.noSlots}</p> : (
                  <div className="public-site__booking-times">
                    {slots.map((slot) => (
                      <label key={slot} className="public-site__booking-time">
                        <input type="radio" aria-label={slot} name="public-booking-time" value={slot} checked={time === slot} required
                          onChange={() => { setTime(slot); setError(''); }} />
                        {slot}
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>
            ) : null}
            {needsPolicyReview ? (
              <fieldset className="public-site__section public-site__booking-policy">
                <legend>{copy.policyConfirm}</legend>
                <p>{copy.policyChanged}</p>
                <label className="public-site__booking-policy-ack">
                  <input type="checkbox" aria-label={copy.policyAck} checked={policyAcknowledgedVersion === options.settings_version}
                    onChange={(event) => setPolicyAcknowledgedVersion(event.target.checked ? options.settings_version : null)} />
                  {copy.policyAck}
                </label>
              </fieldset>
            ) : null}
            {!patient ? (
              <section className="public-site__section" aria-labelledby="booking-login-title">
                <h2 id="booking-login-title">{otherRoleSignedIn ? copy.profileRequired : copy.loginRequired}</h2>
                {serviceSlug && doctorSlug && date && time ? (
                  <div className="public-site__booking-actions">
                    <button type="button" className="public-site__button public-site__button--primary" disabled={formLocked}
                      onClick={() => saveSelectionAndNavigate('/patient/login')}>{copy.login}</button>
                    {!otherRoleSignedIn ? <button type="button" className="public-site__button" disabled={formLocked}
                      onClick={() => saveSelectionAndNavigate('/patient/activate')}>{copy.activate}</button>
                      : null}
                  </div>
                ) : null}
              </section>
            ) : (
              <section className="public-site__section" aria-label={copy.requestNotice}>
                <p><strong>{copy.nonReserving}</strong> {copy.requestNotice}</p>
                <p className="public-site__muted">{copy.responseTime}</p>
                <button type="submit" className="public-site__button public-site__button--primary"
                  disabled={formLocked || !serviceSlug || !doctorSlug || !date || !time || !availability || !slots.includes(time)
                    || (needsPolicyReview && policyAcknowledgedVersion !== options.settings_version)}>
                  {submitting ? copy.submitting : resubmitContext ? copy.resubmit : copy.submit}
                </button>
              </section>
            )}
            {unknownOutcome ? (
              <button type="submit" className="public-site__button" disabled={submitting}>
                {submitting ? copy.submitting : copy.retrySame}
              </button>
            ) : null}
          </form>
        ) : null}
        {completed ? (
          <section className="public-site__section" role="status" aria-live="polite">
            <h2>{completionMessage || copy.requestSent}</h2>
            <p>{copy.nonReserving} {copy.requestNotice}</p>
            <p className="public-site__muted">{copy.responseTime}</p>
            {selectedService && selectedDoctor ? <p>{selectedService.name} · {selectedDoctor.name} · {date} {time}</p> : null}
          </section>
        ) : null}
        <footer className="public-site__footer">
          <a href={locale === 'ru' ? '/ru' : '/'}>{copy.home}</a>
          <a href={locale === 'ru' ? '/ru/contacts' : '/contacts'}>{copy.contact}</a>
        </footer>
      </main>
    </div>
  );
}
