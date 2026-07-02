import { apiRequest } from '../api/client';
import logger from '../utils/logger';

const EMR_TEMPLATE_FIELD_HINTS = {
  complaints: ['complaint', 'symptom', 'pain', 'жалоб'],
  anamnesisMorbi: ['anamnesis', 'history', 'onset', 'забол'],
  anamnesisVitae: ['chronic', 'allergy', 'medical history', 'анамнез'],
  examination: ['examination', 'objective', 'status', 'осмотр'],
  diagnosis: ['diagnosis', 'icd', 'код', 'диагноз'],
  'plan.treatment': ['treatment', 'plan', 'therapy', 'назнач'],
};

let backendEmrTemplatesPromise = null;

export async function loadBackendEmrTemplates() {
  if (!backendEmrTemplatesPromise) {
    backendEmrTemplatesPromise = apiRequest('get', '/emr/templates', {
      params: { is_public: true },
    })
      .then((response) => (Array.isArray(response) ? response : []))
      .catch((error) => {
        logger.debug(
          '[EMRTemplateLibrary] Backend EMR templates unavailable',
          error?.message || error,
        );
        return [];
      });
  }

  return backendEmrTemplatesPromise;
}

export function buildBackendTemplateSnippet(template) {
  const sections = Array.isArray(template?.template_structure?.sections)
    ? template.template_structure.sections
    : [];
  const sectionTitles = sections
    .map((section) => section.section_title || section.section_name)
    .filter(Boolean)
    .slice(0, 2);
  const fieldLabels = sections
    .flatMap((section) => (Array.isArray(section.fields) ? section.fields : []))
    .map((field) => field.label)
    .filter(Boolean)
    .slice(0, 3);

  return [
    template?.name,
    ...sectionTitles,
    ...fieldLabels,
    template?.description,
  ]
    .filter(Boolean)
    .join(' · ');
}

export function backendTemplateMatches(fieldName, text, template) {
  const hints = EMR_TEMPLATE_FIELD_HINTS[fieldName] || [];
  const haystack = [
    template?.name,
    template?.description,
    template?.specialty,
    template?.template_structure?.template_name,
    ...(Array.isArray(template?.template_structure?.sections)
      ? template.template_structure.sections.flatMap((section) => [
          section.section_name,
          section.section_title,
          ...(Array.isArray(section.fields)
            ? section.fields.map((field) => field.label)
            : []),
        ])
      : []),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  const lowerText = text.toLowerCase();
  if (!hints.length) {
    return true;
  }

  return (
    hints.some((hint) => haystack.includes(hint)) ||
    (lowerText.length >= 3 && haystack.includes(lowerText.slice(0, 12)))
  );
}

export function mergeTemplateSuggestions(primary, secondary) {
  const seen = new Set();
  const merged = [];

  for (const suggestion of [...primary, ...secondary]) {
    const key = `${suggestion.text}::${suggestion.source}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(suggestion);
  }

  return merged;
}
