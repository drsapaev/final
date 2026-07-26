/**
 * AI Content Validation and Sanitization
 *
 * Validates and sanitizes AI-generated content to prevent:
 * - AI Prompt Injection attacks
 * - XSS through AI responses
 * - Malformed medical data
 * - Inappropriate content
 */

import { sanitizeAIContent } from './sanitizer';
import logger from './logger';

/**
 * Suspicious patterns that might indicate prompt injection or malicious content
 */
const SUSPICIOUS_PATTERNS = [
// Script tags are handled by sanitizeAIContent/DOMPurify instead of regex parsing.
/javascript:/gi,
/on\w+\s*=/gi, // onclick, onerror, etc.

// Iframe/embed injection
/<iframe[\s\S]*?>/gi,
/<embed[\s\S]*?>/gi,
/<object[\s\S]*?>/gi,

// Data URIs (potential XSS)
/data:text\/html/gi,
/data:application\/javascript/gi,

// Prompt injection patterns
/ignore\s+previous\s+instructions/gi,
/disregard\s+all\s+prior\s+commands/gi,
/system\s*:\s*you\s+are/gi,

// SQL injection patterns
/;\s*drop\s+table/gi,
/union\s+select/gi,

// Command injection
/&&\s*rm\s+-rf/gi,
/;\s*curl\s+/gi];


/**
 * Medical data schemas for validation
 */
const MEDICAL_SCHEMAS = {
  icd10_code: {
    pattern: /^[A-Z]\d{2}(\.\d{1,2})?$/,
    maxLength: 8
  },

  medication_name: {
    pattern: /^[A-Za-zА-Яа-яёЁ0-9\s\-().,]+$/,
    maxLength: 200,
    minLength: 2
  },

  dosage: {
    pattern: /^[\d.,\s]+(мг|г|мл|ед|ME|IU|mg|g|ml|mcg|мкг)$/i,
    maxLength: 50
  },

  diagnosis: {
    maxLength: 1000,
    minLength: 3
  },

  treatment: {
    maxLength: 5000,
    minLength: 5
  }
};

/**
 * Validates AI response structure and content
 *
 * @param {any} response - AI response to validate
 * @param {object} options - Validation options
 * @returns {object} Validated and sanitized response
 */
interface FieldRule {
  type?: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: RegExp;
  sanitize?: boolean;
  minItems?: number;
  maxItems?: number;
  items?: FieldRule;
  default?: unknown;
  validator?: (value: unknown) => unknown;
}

interface AIValidationOptions {
  expectedType?: 'string' | 'object' | 'array';
  schema?: Record<string, unknown> | null;
  sanitize?: boolean;
  strictMode?: boolean;
  maxDepth?: number;
}

export function validateAIResponse(response: unknown, options: AIValidationOptions = {}): unknown {
  const {
    expectedType = 'object', // 'string', 'object', 'array'
    schema = null,
    sanitize = true,
    strictMode = true,
    maxDepth = 5
  } = options;

  // Null/undefined check
  if (response === null || response === undefined) {
    logger.warn('[AI Validator] Received null/undefined response');
    return null;
  }

  // Type validation
  const actualType = Array.isArray(response) ? 'array' : typeof response;
  if (actualType !== expectedType) {
    logger.warn(`[AI Validator] Type mismatch: expected ${expectedType}, got ${actualType}`);

    if (strictMode) {
      throw new Error(`Invalid AI response type: expected ${expectedType}, got ${actualType}`);
    }
  }

  // Deep clone to avoid mutating original.
  // audit/phase-6, BS-62: use structuredClone when available (modern browsers,
  // Node 17+) — JSON.parse(JSON.stringify()) loses Date objects (converts to
  // ISO string), throws on undefined/functions/cycles, and is 2-10x slower.
  // structuredClone preserves Dates, Maps, Sets, cycles, and is the API the
  // platform provides for this exact use case.
  let validated: unknown = typeof structuredClone === 'function'
    ? structuredClone(response)
    : JSON.parse(JSON.stringify(response));

  // Sanitize based on type
  if (sanitize) {
    validated = sanitizeAIResponseRecursive(validated, maxDepth);
  }

  // Schema validation if provided
  if (schema) {
    validated = validateAgainstSchema(validated as Record<string, unknown>, schema);
  }

  return validated;
}

/**
 * Recursively sanitize AI response
 */
function sanitizeAIResponseRecursive(obj: unknown, maxDepth: number = 5, currentDepth: number = 0): unknown {
  if (currentDepth >= maxDepth) {
    logger.warn('[AI Validator] Max depth reached, stopping recursion');
    return obj;
  }

  if (typeof obj === 'string') {
    return sanitizeAIString(obj);
  }

  if (Array.isArray(obj)) {
    return obj.map((item: unknown) => sanitizeAIResponseRecursive(item, maxDepth, currentDepth + 1));
  }

  if (typeof obj === 'object' && obj !== null) {
    const sanitized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      // Sanitize key
      const cleanKey = sanitizeAIString(String(key)) as string;

      // Sanitize value
      sanitized[cleanKey] = sanitizeAIResponseRecursive(value, maxDepth, currentDepth + 1);
    }
    return sanitized;
  }

  return obj;
}

/**
 * Sanitize AI string content
 */
function sanitizeAIString(str: unknown): unknown {
  if (typeof str !== 'string') return str;

  let result: string = str;
  // Check for suspicious patterns
  for (const pattern of SUSPICIOUS_PATTERNS) {
    if (pattern.test(result)) {
      logger.warn('[AI Validator] Suspicious pattern detected, sanitizing');
      // Remove the suspicious content
      result = result.replace(pattern, '');
    }
  }

  // Use sanitizeAIContent from sanitizer.js
  return sanitizeAIContent(result);
}

/**
 * Validate against schema
 */
function validateAgainstSchema(data: Record<string, unknown>, schema: Record<string, unknown> | ((data: unknown) => unknown)): unknown {
  if (typeof schema === 'function') {
    // Custom validation function
    return schema(data);
  }

  if (typeof schema === 'object') {
    // Object schema
    const validated: Record<string, unknown> = {};

    for (const [key, rule] of Object.entries(schema as Record<string, unknown>)) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        validated[key] = validateField(data[key], rule as FieldRule);
      } else if ((rule as { required?: boolean }).required) {
        throw new Error(`Required field missing: ${key}`);
      } else if ((rule as { default?: unknown }).default !== undefined) {
        validated[key] = (rule as { default?: unknown }).default;
      }
    }

    return validated;
  }

  return data;
}

/**
 * Validate individual field
 */
function validateField(value: unknown, rule: FieldRule): unknown {
  // Type validation
  if (rule.type && typeof value !== rule.type) {
    throw new Error(`Type mismatch for field: expected ${rule.type}, got ${typeof value}`);
  }

  // String validations
  if (typeof value === 'string') {
    let strValue: string = value;
    // Length validation
    if (rule.minLength && strValue.length < rule.minLength) {
      throw new Error(`String too short: minimum ${rule.minLength} characters`);
    }
    if (rule.maxLength && strValue.length > rule.maxLength) {
      logger.warn(`String too long, truncating to ${rule.maxLength} characters`);
      strValue = strValue.substring(0, rule.maxLength);
    }

    // Pattern validation
    if (rule.pattern && !rule.pattern.test(strValue)) {
      throw new Error('String does not match required pattern');
    }

    // Sanitize
    if (rule.sanitize !== false) {
      strValue = sanitizeAIString(strValue) as string;
    }
    value = strValue;
  }

  // Array validations
  if (Array.isArray(value)) {
    let arrValue: unknown[] = value;
    if (rule.minItems && arrValue.length < rule.minItems) {
      throw new Error(`Array too short: minimum ${rule.minItems} items`);
    }
    if (rule.maxItems && arrValue.length > rule.maxItems) {
      logger.warn(`Array too long, truncating to ${rule.maxItems} items`);
      arrValue = arrValue.slice(0, rule.maxItems);
    }

    // Validate items
    if (rule.items) {
      const itemsRule = rule.items;
      arrValue = arrValue.map((item: unknown) => validateField(item, itemsRule));
    }
    value = arrValue;
  }

  // Custom validator
  if (rule.validator && typeof rule.validator === 'function') {
    value = rule.validator(value);
  }

  return value;
}

/**
 * Validate ICD-10 suggestions
 */
export function validateICD10Suggestions(suggestions: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(suggestions)) {
    logger.error('[AI Validator] ICD10 suggestions must be an array');
    return [];
  }

  return suggestions.
  filter((suggestion) => {
    const s = suggestion as Record<string, unknown>;
    // Must have code and description
    if (!s.code || !s.description) {
      logger.warn('[AI Validator] Invalid ICD10 suggestion: missing code or description');
      return false;
    }

    // Validate ICD-10 code format
    if (!MEDICAL_SCHEMAS.icd10_code.pattern.test(s.code as string)) {
      logger.warn(`[AI Validator] Invalid ICD10 code format: ${s.code}`);
      return false;
    }

    return true;
  }).
  map((suggestion) => {
    const s = suggestion as Record<string, unknown>;
    return {
      code: sanitizeAIString((s.code as string).toUpperCase()),
      description: sanitizeAIString(s.description),
      confidence: typeof s.confidence === 'number' ?
      Math.min(Math.max(s.confidence, 0), 1) :
      0.5,
      category: s.category ? sanitizeAIString(s.category) : null
    };
  });
}

/**
 * Validate medication recommendations
 */
export function validateMedicationRecommendations(medications: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(medications)) {
    logger.error('[AI Validator] Medications must be an array');
    return [];
  }

  return medications.
  filter((med) => {
    const m = med as Record<string, unknown>;
    // Must have name
    if (!m.name) {
      logger.warn('[AI Validator] Invalid medication: missing name');
      return false;
    }

    // Validate medication name
    const nameSchema = MEDICAL_SCHEMAS.medication_name;
    const medName = m.name as string;
    if (medName.length < nameSchema.minLength ||
    medName.length > nameSchema.maxLength ||
    !nameSchema.pattern.test(medName)) {
      logger.warn(`[AI Validator] Invalid medication name: ${m.name}`);
      return false;
    }

    return true;
  }).
  map((med) => {
    const m = med as Record<string, unknown>;
    return {
      name: sanitizeAIString(m.name),
      dosage: m.dosage ? sanitizeAIString(String(m.dosage)) : null,
      frequency: m.frequency ? sanitizeAIString(String(m.frequency)) : null,
      duration: m.duration ? sanitizeAIString(String(m.duration)) : null,
      instructions: m.instructions ? sanitizeAIString(m.instructions) : null,
      warnings: Array.isArray(m.warnings) ?
    m.warnings.map((w: unknown) => sanitizeAIString(String(w))) :
    []
    };
  });
}

/**
 * Validate treatment plan
 */
export function validateTreatmentPlan(plan: unknown): Record<string, unknown> | null {
  if (!plan || typeof plan !== 'object') {
    logger.error('[AI Validator] Invalid treatment plan structure');
    return null;
  }

  const schema: Record<string, FieldRule> = {
    diagnosis: {
      type: 'string',
      required: true,
      minLength: MEDICAL_SCHEMAS.diagnosis.minLength,
      maxLength: MEDICAL_SCHEMAS.diagnosis.maxLength,
      sanitize: true
    },
    treatment: {
      type: 'string',
      required: true,
      minLength: MEDICAL_SCHEMAS.treatment.minLength,
      maxLength: MEDICAL_SCHEMAS.treatment.maxLength,
      sanitize: true
    },
    medications: {
      type: 'object',
      required: false,
      validator: validateMedicationRecommendations
    },
    recommendations: {
      type: 'object',
      required: false,
      sanitize: true
    },
    follow_up: {
      type: 'string',
      required: false,
      maxLength: 1000,
      sanitize: true
    }
  };

  try {
    return validateAgainstSchema(plan as Record<string, unknown>, schema) as Record<string, unknown>;
  } catch (error) {
    logger.error('[AI Validator] Treatment plan validation failed:', error);
    return null;
  }
}

/**
 * Validate clinical recommendations
 */
export function validateClinicalRecommendations(recommendations: unknown): Record<string, unknown> | null {
  if (!recommendations || typeof recommendations !== 'object') {
    return null;
  }

  const rec = recommendations as Record<string, unknown>;

  return {
    differential_diagnosis: Array.isArray(rec.differential_diagnosis) ?
    rec.differential_diagnosis.map((d: unknown) => sanitizeAIString(String(d))) :
    [],

    recommended_tests: Array.isArray(rec.recommended_tests) ?
    rec.recommended_tests.map((t: unknown) => sanitizeAIString(String(t))) :
    [],

    red_flags: Array.isArray(rec.red_flags) ?
    rec.red_flags.map((f: unknown) => sanitizeAIString(String(f))) :
    [],

    treatment_options: Array.isArray(rec.treatment_options) ?
    rec.treatment_options.map((o: unknown) => sanitizeAIString(String(o))) :
    [],

    urgency_level: rec.urgency_level ?
    sanitizeAIString(String(rec.urgency_level)) :
    'routine'
  };
}

/**
 * Validate AI chat message
 */
export function validateAIChatMessage(message: unknown): Record<string, unknown> | null {
  if (!message || typeof message !== 'object') {
    return null;
  }

  const msg = message as Record<string, unknown>;

  return {
    content: sanitizeAIString(String(msg.content || '')),
    role: ['user', 'assistant', 'system'].includes(msg.role as string) ?
    msg.role :
    'assistant',
    timestamp: msg.timestamp instanceof Date ?
    msg.timestamp :
    new Date(),
    metadata: msg.metadata ? sanitizeAIResponseRecursive(msg.metadata, 3) : null
  };
}

/**
 * Detect potential prompt injection
 */
export function detectPromptInjection(text: unknown): boolean {
  if (typeof text !== 'string') return false;

  const injectionPatterns = [
  /ignore\s+(previous|prior|all)\s+(instructions|commands|prompts)/gi,
  /disregard\s+(previous|all)\s+(instructions|commands)/gi,
  /new\s+instructions:/gi,
  /system\s*:\s*(you\s+are|act\s+as|pretend)/gi,
  /\/\s*system/gi,
  /<\|im_start\|>/gi,
  /<\|im_end\|>/gi];


  for (const pattern of injectionPatterns) {
    if (pattern.test(text)) {
      logger.warn('[AI Validator] Potential prompt injection detected');
      return true;
    }
  }

  return false;
}

/**
 * Safe wrapper for AI API calls
 */
export async function safeAICall(apiFunction: (...args: unknown[]) => unknown | Promise<unknown>, ...args: unknown[]): Promise<Record<string, unknown>> {
  try {
    const response = await apiFunction(...args);

    // Validate response
    const validated = validateAIResponse(response, {
      expectedType: 'object',
      sanitize: true,
      strictMode: false
    });

    return {
      success: true,
      data: validated,
      error: null
    };
  } catch (error) {
    logger.error('[AI Validator] AI call failed:', error);

    return {
      success: false,
      data: null,
      error: error instanceof Error ? error.message : 'AI request failed'
    };
  }
}

export default {
  validateAIResponse,
  validateICD10Suggestions,
  validateMedicationRecommendations,
  validateTreatmentPlan,
  validateClinicalRecommendations,
  validateAIChatMessage,
  detectPromptInjection,
  safeAICall
};
