/**
 * Unit tests for logger utility
 *
 * Tests cover:
 * - PHI sanitization
 * - Basic logging methods
 * - Error handling
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

// Import logger and sanitize
import logger, { sanitize } from '../logger';

// logger is still implicit-any; cast to a permissive shape so the test's
// typeof checks and method calls compile without a concrete Logger type.
interface LoggerShape {
  log: (...args: unknown[]) => void;
  warn: (...args: unknown[]) => void;
  error: (...args: unknown[]) => void;
  debug: (...args: unknown[]) => void;
  info: (...args: unknown[]) => void;
  group: (...args: unknown[]) => void;
  groupEnd: (...args: unknown[]) => void;
  table: (...args: unknown[]) => void;
  time: (...args: unknown[]) => void;
  timeEnd: (...args: unknown[]) => void;
}
const loggerTyped = logger as unknown as LoggerShape;
const sanitizeTyped = sanitize as unknown as (input: unknown) => unknown;

describe('logger', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('basic logging methods', () => {
        it('should have log method', () => {
            expect(typeof loggerTyped.log).toBe('function');
        });

        it('should have warn method', () => {
            expect(typeof loggerTyped.warn).toBe('function');
        });

        it('should have error method', () => {
            expect(typeof loggerTyped.error).toBe('function');
        });

        it('should have debug method', () => {
            expect(typeof loggerTyped.debug).toBe('function');
        });

        it('should have info method', () => {
            expect(typeof loggerTyped.info).toBe('function');
        });

        it('should have group method', () => {
            expect(typeof loggerTyped.group).toBe('function');
        });

        it('should have groupEnd method', () => {
            expect(typeof loggerTyped.groupEnd).toBe('function');
        });

        it('should have table method', () => {
            expect(typeof loggerTyped.table).toBe('function');
        });

        it('should have time method', () => {
            expect(typeof loggerTyped.time).toBe('function');
        });

        it('should have timeEnd method', () => {
            expect(typeof loggerTyped.timeEnd).toBe('function');
        });
    });

    describe('sanitize function', () => {
        it('should export sanitize function', () => {
            expect(typeof sanitize).toBe('function');
        });

        it('should not modify primitive email strings', () => {
            // Primitives are returned as-is (PHI filtering works on object keys)
            const input = 'Contact: patient@example.com';
            const result = sanitizeTyped(input);

            // Primitives should be unchanged
            expect(result).toBe(input);
        });

        it('should not modify primitive strings', () => {
            // Primitives are returned as-is (PHI filtering works on object keys)
            const input = 'Phone: +7 (999) 123-45-67';
            const result = sanitizeTyped(input);

            // Primitives should be unchanged
            expect(result).toBe(input);
        });

        it('should redact PHI fields in objects', () => {
            const input = {
                id: 123,
                patient_name: 'John Doe',
                email: 'john@example.com',
                status: 'active'
            };
            const result = sanitizeTyped(input) as Record<string, unknown>;

            // PHI fields should be redacted
            expect(result.patient_name).toBe('[REDACTED]');
            expect(result.email).toBe('[REDACTED]');
            // Non-PHI fields should remain
            expect(result.id).toBe(123);
            expect(result.status).toBe('active');
        });

        it('should handle nested objects', () => {
            const input = {
                user: {
                    name: 'Test User',
                    phone: '+7 999 123 4567'
                }
            };
            const result = sanitizeTyped(input) as { user: Record<string, unknown> };

            expect(result.user.name).toBe('[REDACTED]');
            expect(result.user.phone).toBe('[REDACTED]');
        });

        it('should handle arrays', () => {
            const input = ['test@email.com', 'normal text'];
            const result = sanitizeTyped(input);

            expect(Array.isArray(result)).toBe(true);
            expect((result as unknown[]).length).toBe(2);
        });

        it('should handle null and undefined gracefully', () => {
            expect(sanitizeTyped(null)).toBeNull();
            expect(sanitizeTyped(undefined)).toBeUndefined();
        });

        it('should handle empty strings', () => {
            const result = sanitizeTyped('');
            expect(result).toBe('');
        });

        it('should handle numbers', () => {
            expect(sanitizeTyped(123)).toBe(123);
            expect(sanitizeTyped(0)).toBe(0);
        });

        it('should handle booleans', () => {
            expect(sanitizeTyped(true)).toBe(true);
            expect(sanitizeTyped(false)).toBe(false);
        });
    });

    describe('log output - should not throw', () => {
        it('should call log method without throwing', () => {
            expect(() => loggerTyped.log('Test message')).not.toThrow();
        });

        it('should call warn method without throwing', () => {
            expect(() => loggerTyped.warn('Warning message')).not.toThrow();
        });

        it('should call error method without throwing', () => {
            expect(() => loggerTyped.error('Error message')).not.toThrow();
        });

        it('should handle multiple arguments', () => {
            expect(() => loggerTyped.log('Message', { data: 'value' }, 123)).not.toThrow();
        });

        it('should handle Error objects', () => {
            const error = new Error('Test error');
            expect(() => loggerTyped.error('Error:', error)).not.toThrow();
        });
    });

    describe('performance', () => {
        it('should handle rapid logging without errors', () => {
            expect(() => {
                for (let i = 0; i < 100; i++) {
                    loggerTyped.log(`Message ${i}`);
                }
            }).not.toThrow();
        });

        it('should handle large objects', () => {
            const largeObject: Record<string, string> = {};
            for (let i = 0; i < 100; i++) {
                largeObject[`key${i}`] = `value${i}`;
            }
            expect(() => loggerTyped.log('Large object:', largeObject)).not.toThrow();
        });
    });

    describe('special characters handling', () => {
        it('should handle strings with special characters', () => {
            const specialChars = 'Test: <script>alert("XSS")</script>';
            expect(() => loggerTyped.log(specialChars)).not.toThrow();
        });

        it('should handle unicode characters', () => {
            const unicode = 'Тест: 日本語 🎉 émoji';
            expect(() => loggerTyped.log(unicode)).not.toThrow();
        });

        it('should handle newlines and tabs', () => {
            const multiline = 'Line 1\nLine 2\tTabbed';
            expect(() => loggerTyped.log(multiline)).not.toThrow();
        });
    });

    describe('circular reference handling', () => {
        it('should handle circular references without throwing', () => {
            const obj: { name: string; self?: unknown } = { name: 'test' };
            obj.self = obj; // Create circular reference

            expect(() => sanitizeTyped(obj)).not.toThrow();
        });

        it('should handle deeply nested objects', () => {
            let nested: Record<string, unknown> = { value: 'deep' };
            for (let i = 0; i < 20; i++) {
                nested = { child: nested };
            }

            expect(() => sanitizeTyped(nested)).not.toThrow();
        });
    });
});
