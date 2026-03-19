const CANONICAL_SPECIALTIES = new Set([
    'general',
    'cardiology',
    'dermatology',
    'dentistry',
    'lab',
]);

const SPECIALTY_ALIASES = {
    '': 'general',
    doctor: 'general',
    therapy: 'general',
    cardio: 'cardiology',
    cardiologist: 'cardiology',
    derma: 'dermatology',
    dermatologist: 'dermatology',
    dentist: 'dentistry',
    dental: 'dentistry',
    stomatology: 'dentistry',
    stomatologist: 'dentistry',
    laboratory: 'lab',
};

const SPECIALTY_SKELETONS = {
    general: {},
    cardiology: {
        ecg: {},
        echo: {},
        cardio_labs: {},
    },
    dermatology: {
        photos: [],
        skin_type: '',
        conditions: [],
        localization: {},
    },
    dentistry: {
        tooth_status: {},
        hygiene_indices: {},
        periodontal_pockets: {},
        measurements: {},
        radiographs: {},
    },
    lab: {
        results: [],
        references: [],
        clinician_interpretation: '',
        signed_snapshot: {},
    },
};

export function normalizeSpecialty(value, fallback = 'general') {
    const raw = String(value || '').trim().toLowerCase();
    const normalizedFallback = String(fallback || '').trim().toLowerCase();
    const fallbackValue = CANONICAL_SPECIALTIES.has(normalizedFallback)
        ? normalizedFallback
        : (SPECIALTY_ALIASES[normalizedFallback] || 'general');

    if (!raw) {
        return fallbackValue;
    }

    if (CANONICAL_SPECIALTIES.has(raw)) {
        return raw;
    }

    return SPECIALTY_ALIASES[raw] || fallbackValue;
}

export function isCanonicalSpecialty(value) {
    return CANONICAL_SPECIALTIES.has(String(value || '').trim().toLowerCase());
}

export function buildSpecialtySkeleton(specialty) {
    const canonical = normalizeSpecialty(specialty);
    return structuredClone(SPECIALTY_SKELETONS[canonical] || {});
}

export function normalizeEMRData(data, specialty = 'general') {
    const payload = data && typeof data === 'object' ? structuredClone(data) : {};
    const canonicalSpecialty = normalizeSpecialty(
        payload.specialty,
        specialty,
    );
    const specialtyData = payload.specialty_data && typeof payload.specialty_data === 'object'
        ? payload.specialty_data
        : {};

    payload.specialty = canonicalSpecialty;
    payload.specialty_data = {
        ...buildSpecialtySkeleton(canonicalSpecialty),
        ...specialtyData,
    };

    return payload;
}

export function buildInitialEMRData(specialty = 'general') {
    return normalizeEMRData({
        complaints: '',
        anamnesis_morbi: '',
        anamnesis_vitae: '',
        examination: '',
        diagnosis: {
            main: '',
            icd10_code: '',
            secondary: [],
        },
        vitals: {},
        plan: {
            examinations: [],
            treatment: '',
            consultations: [],
        },
        recommendations: '',
        notes: '',
        medications: {
            text: '',
            list: [],
        },
    }, specialty);
}
