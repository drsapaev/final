/**
 * AI Content Validation and Sanitization
 *
 * Validates and sanitizes AI-generated content to prevent:
 * - AI Prompt Injection attacks
 * - XSS through AI responses
 * - Malformed medical data
 * - Inappropriate content
 */

import { sanitizeAIContent, sanitizeHTML } from './sanitizer';
import logger from './logger';

/**
 * Suspicious patterns that might indicate prompt injection or malicious content
 */
const SUSPICIOUS_PATTERNS = [
  // Script injection
  /<script[\s\S]*?>[\s\S]*?<\/script>/gi,
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
  /;\s*curl\s+/gi
];

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
export function validateAIResponse(response, options = {}) {
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

  // Deep clone to avoid mutating original
  let validated = JSON.parse(JSON.stringify(response));

  // Sanitize based on type
  if (sanitize) {
    validated = sanitizeAIResponseRecursive(validated, maxDepth);
  }

  // Schema validation if provided
  if (schema) {
    validated = validateAgainstSchema(validated, schema);
  }

  return validated;
}

/**
 * Recursively sanitize AI response
 */
function sanitizeAIResponseRecursive(obj, maxDepth = 5, currentDepth = 0) {
  if (currentDepth >= maxDepth) {
    logger.warn('[AI Validator] Max depth reached, stopping recursion');
    return obj;
  }

  if (typeof obj === 'string') {
    return sanitizeAIString(obj);
  }

  if (Array.isArray(obj)) {
    return obj.map(item => sanitizeAIResponseRecursive(item, maxDepth, currentDepth + 1));
  }

  if (typeof obj === 'object' && obj !== null) {
    const sanitized = {};
    for (const [key, value] of Object.entries(obj)) {
      // Sanitize key
      const cleanKey = sanitizeAIString(String(key));

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
function sanitizeAIString(str) {
  if (typeof str !== 'string') return str;

  // Check for suspicious patterns
  for (const pattern of SUSPICIOUS_PATTERNS) {
    if (pattern.test(str)) {
      logger.warn('[AI Validator] Suspicious pattern detected, sanitizing');
      // Remove the suspicious content
      str = str.replace(pattern, '');
    }
  }

  // Use sanitizeAIContent from sanitizer.js
  return sanitizeAIContent(str);
}

/**
 * Validate against schema
 */
function validateAgainstSchema(data, schema) {
  if (typeof schema === 'function') {
    // Custom validation function
    return schema(data);
  }

  if (typeof schema === 'object') {
    // Object schema
    const validated = {};

    for (const [key, rule] of Object.entries(schema)) {
      if (data.hasOwnProperty(key)) {
        validated[key] = validateField(data[key], rule);
      } else if (rule.required) {
        throw new Error(`Required field missing: ${key}`);
      } else if (rule.default !== undefined) {
        validated[key] = rule.default;
      }
    }

    return validated;
  }

  return data;
}

/**
 * Validate individual field
 */
function validateField(value, rule) {
  // Type validation
  if (rule.type && typeof value !== rule.type) {
    throw new Error(`Type mismatch for field: expected ${rule.type}, got ${typeof value}`);
  }

  // String validations
  if (typeof value === 'string') {
    // Length validation
    if (rule.minLength && value.length < rule.minLength) {
      throw new Error(`String too short: minimum ${rule.minLength} characters`);
    }
    if (rule.maxLength && value.length > rule.maxLength) {
      logger.warn(`String too long, truncating to ${rule.maxLength} characters`);
      value = value.substring(0, rule.maxLength);
    }

    // Pattern validation
    if (rule.pattern && !rule.pattern.test(value)) {
      throw new Error('String does not match required pattern');
    }

    // Sanitize
    if (rule.sanitize !== false) {
      value = sanitizeAIString(value);
    }
  }

  // Array validations
  if (Array.isArray(value)) {
    if (rule.minItems && value.length < rule.minItems) {
      throw new Error(`Array too short: minimum ${rule.minItems} items`);
    }
    if (rule.maxItems && value.length > rule.maxItems) {
      logger.warn(`Array too long, truncating to ${rule.maxItems} items`);
      value = value.slice(0, rule.maxItems);
    }

    // Validate items
    if (rule.items) {
      value = value.map(item => validateField(item, rule.items));
    }
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
export function validateICD10Suggestions(suggestions) {
  if (!Array.isArray(suggestions)) {
    logger.error('[AI Validator] ICD10 suggestions must be an array');
    return [];
  }

  return suggestions
    .filter(suggestion => {
      // Must have code and description
      if (!suggestion.code || !suggestion.description) {
        logger.warn('[AI Validator] Invalid ICD10 suggestion: missing code or description');
        return false;
      }

      // Validate ICD-10 code format
      if (!MEDICAL_SCHEMAS.icd10_code.pattern.test(suggestion.code)) {
        logger.warn(`[AI Validator] Invalid ICD10 code format: ${suggestion.code}`);
        return false;
      }

      return true;
    })
    .map(suggestion => ({
      code: sanitizeAIString(suggestion.code.toUpperCase()),
      description: sanitizeAIString(suggestion.description),
      confidence: typeof suggestion.confidence === 'number'
        ? Math.min(Math.max(suggestion.confidence, 0), 1)
        : 0.5,
      category: suggestion.category ? sanitizeAIString(suggestion.category) : null
    }));
}

/**
 * Validate medication recommendations
 */
export function validateMedicationRecommendations(medications) {
  if (!Array.isArray(medications)) {
    logger.error('[AI Validator] Medications must be an array');
    return [];
  }

  return medications
    .filter(med => {
      // Must have name
      if (!med.name) {
        logger.warn('[AI Validator] Invalid medication: missing name');
        return false;
      }

      // Validate medication name
      const nameSchema = MEDICAL_SCHEMAS.medication_name;
      if (med.name.length < nameSchema.minLength ||
          med.name.length > nameSchema.maxLength ||
          !nameSchema.pattern.test(med.name)) {
        logger.warn(`[AI Validator] Invalid medication name: ${med.name}`);
        return false;
      }

      return true;
    })
    .map(med => ({
      name: sanitizeAIString(med.name),
      dosage: med.dosage ? sanitizeAIString(String(med.dosage)) : null,
      frequency: med.frequency ? sanitizeAIString(String(med.frequency)) : null,
      duration: med.duration ? sanitizeAIString(String(med.duration)) : null,
      instructions: med.instructions ? sanitizeAIString(med.instructions) : null,
      warnings: Array.isArray(med.warnings)
        ? med.warnings.map(w => sanitizeAIString(String(w)))
        : []
    }));
}

/**
 * Validate treatment plan
 */
export function validateTreatmentPlan(plan) {
  if (!plan || typeof plan !== 'object') {
    logger.error('[AI Validator] Invalid treatment plan structure');
    return null;
  }

  const schema = {
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
    return validateAgainstSchema(plan, schema);
  } catch (error) {
    logger.error('[AI Validator] Treatment plan validation failed:', error);
    return null;
  }
}

/**
 * Validate clinical recommendations
 */
export function validateClinicalRecommendations(recommendations) {
  if (!recommendations || typeof recommendations !== 'object') {
    return null;
  }

  return {
    differential_diagnosis: Array.isArray(recommendations.differential_diagnosis)
      ? recommendations.differential_diagnosis.map(d => sanitizeAIString(String(d)))
      : [],

    recommended_tests: Array.isArray(recommendations.recommended_tests)
      ? recommendations.recommended_tests.map(t => sanitizeAIString(String(t)))
      : [],

    red_flags: Array.isArray(recommendations.red_flags)
      ? recommendations.red_flags.map(f => sanitizeAIString(String(f)))
      : [],

    treatment_options: Array.isArray(recommendations.treatment_options)
      ? recommendations.treatment_options.map(o => sanitizeAIString(String(o)))
      : [],

    urgency_level: recommendations.urgency_level
      ? sanitizeAIString(String(recommendations.urgency_level))
      : 'routine'
  };
}

/**
 * Validate AI chat message
 */
export function validateAIChatMessage(message) {
  if (!message || typeof message !== 'object') {
    return null;
  }

  return {
    content: sanitizeAIString(String(message.content || '')),
    role: ['user', 'assistant', 'system'].includes(message.role)
      ? message.role
      : 'assistant',
    timestamp: message.timestamp instanceof Date
      ? message.timestamp
      : new Date(),
    metadata: message.metadata ? sanitizeAIResponseRecursive(message.metadata, 3) : null
  };
}

/**
 * Detect potential prompt injection
 */
export function detectPromptInjection(text) {
  if (typeof text !== 'string') return false;

  const injectionPatterns = [
    /ignore\s+(previous|prior|all)\s+(instructions|commands|prompts)/gi,
    /disregard\s+(previous|all)\s+(instructions|commands)/gi,
    /new\s+instructions:/gi,
    /system\s*:\s*(you\s+are|act\s+as|pretend)/gi,
    /\/\s*system/gi,
    /<\|im_start\|>/gi,
    /<\|im_end\|>/gi
  ];

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
export async function safeAICall(apiFunction, ...args) {
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
      error: error.message || 'AI request failed'
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
