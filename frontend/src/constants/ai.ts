// AI Constants for EMR System
// Константы для работы с искусственным интеллектом в медицинской системе

export const AI_ANALYSIS_TYPES = {
  COMPLAINT: 'complaint',
  ANAMNESIS: 'anamnesis',
  EXAMINATION: 'examination',
  RECOMMENDATION: 'recommendation',
  ICD10: 'icd10',
  IMAGE_ANALYSIS: 'image_analysis',
  SKIN_LESION: 'skin_lesion'
};

export const MCP_PROVIDERS = {
  DEEPSEEK: 'deepseek',
  GEMINI: 'gemini',
  OPENAI: 'openai'
};

export const AI_PROMPT_TEMPLATES = {
  COMPLAINT_ANALYSIS: 'Проанализируй жалобы пациента и предложи возможные диагнозы, необходимые обследования и план лечения.',
  ANAMNESIS_GENERATION: 'На основе жалоб пациента сгенерируй детальный анамнез заболевания.',
  EXAMINATION_RECOMMENDATIONS: 'Рекомендуй необходимые физикальные обследования на основе жалоб пациента.',
  TREATMENT_PLAN: 'Составь план лечения на основе диагноза и жалоб пациента.',
  ICD10_SUGGESTIONS: 'Предложи коды МКБ-10 для указанного диагноза.'
};

export const AI_RESPONSE_FORMATS = {
  STRUCTURED: 'structured',
  TEXT: 'text',
  JSON: 'json'
};

export const AI_CACHE_DURATION = {
  COMPLAINT_ANALYSIS: 30 * 60 * 1000, // 30 минут
  ICD10_SUGGESTIONS: 60 * 60 * 1000,  // 1 час
  IMAGE_ANALYSIS: 15 * 60 * 1000      // 15 минут
};

export const AI_ERROR_MESSAGES = {
  NETWORK_ERROR: 'Ошибка подключения к AI сервису',
  RATE_LIMIT: 'Превышен лимит запросов к AI сервису',
  INVALID_RESPONSE: 'AI вернул некорректный ответ',
  TIMEOUT: 'Превышено время ожидания ответа от AI',
  UNAUTHORIZED: 'Недостаточно прав для использования AI функций'
};

export const ATTACHMENT_CATEGORIES = {
  EXAMINATION: 'examination',
  DOCUMENTS: 'documents',
  BEFORE_AFTER: 'before_after',
  LAB_RESULTS: 'lab_results'
};

export const ATTACHMENT_CATEGORY_LABELS = {
  [ATTACHMENT_CATEGORIES.EXAMINATION]: 'Обследование',
  [ATTACHMENT_CATEGORIES.DOCUMENTS]: 'Документы',
  [ATTACHMENT_CATEGORIES.BEFORE_AFTER]: 'До/После',
  [ATTACHMENT_CATEGORIES.LAB_RESULTS]: 'Анализы'
};
