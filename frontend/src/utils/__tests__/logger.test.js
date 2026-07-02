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

describe('logger', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('basic logging methods', () => {
        it('should have log method', () => {
            expect(typeof logger.log).toBe('function');
        });

        it('should have warn method', () => {
            expect(typeof logger.warn).toBe('function');
        });

        it('should have error method', () => {
            expect(typeof logger.error).toBe('function');
        });

        it('should have debug method', () => {
            expect(typeof logger.debug).toBe('function');
        });

        it('should have info method', () => {
            expect(typeof logger.info).toBe('function');
        });

        it('should have group method', () => {
            expect(typeof logger.group).toBe('function');
        });

        it('should have groupEnd method', () => {
            expect(typeof logger.groupEnd).toBe('function');
        });

        it('should have table method', () => {
            expect(typeof logger.table).toBe('function');
        });

        it('should have time method', () => {
            expect(typeof logger.time).toBe('function');
        });

        it('should have timeEnd method', () => {
            expect(typeof logger.timeEnd).toBe('function');
        });
    });

    describe('sanitize function', () => {
        it('should export sanitize function', () => {
            expect(typeof sanitize).toBe('function');
        });

        it('should not modify primitive email strings', () => {
            // Primitives are returned as-is (PHI filtering works on object keys)
            const input = 'Contact: patient@example.com';
            const result = sanitize(input);

            // Primitives should be unchanged
            expect(result).toBe(input);
        });

        it('should not modify primitive strings', () => {
            // Primitives are returned as-is (PHI filtering works on object keys)
            const input = 'Phone: +7 (999) 123-45-67';
            const result = sanitize(input);

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
            const result = sanitize(input);

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
            const result = sanitize(input);

            expect(result.user.name).toBe('[REDACTED]');
            expect(result.user.phone).toBe('[REDACTED]');
        });

        it('should handle arrays', () => {
            const input = ['test@email.com', 'normal text'];
            const result = sanitize(input);

            expect(Array.isArray(result)).toBe(true);
            expect(result.length).toBe(2);
        });

        it('should handle null and undefined gracefully', () => {
            expect(sanitize(null)).toBeNull();
            expect(sanitize(undefined)).toBeUndefined();
        });

        it('should handle empty strings', () => {
            const result = sanitize('');
            expect(result).toBe('');
        });

        it('should handle numbers', () => {
            expect(sanitize(123)).toBe(123);
            expect(sanitize(0)).toBe(0);
        });

        it('should handle booleans', () => {
            expect(sanitize(true)).toBe(true);
            expect(sanitize(false)).toBe(false);
        });
    });

    describe('log output - should not throw', () => {
        it('should call log method without throwing', () => {
            expect(() => logger.log('Test message')).not.toThrow();
        });

        it('should call warn method without throwing', () => {
            expect(() => logger.warn('Warning message')).not.toThrow();
        });

        it('should call error method without throwing', () => {
            expect(() => logger.error('Error message')).not.toThrow();
        });

        it('should handle multiple arguments', () => {
            expect(() => logger.log('Message', { data: 'value' }, 123)).not.toThrow();
        });

        it('should handle Error objects', () => {
            const error = new Error('Test error');
            expect(() => logger.error('Error:', error)).not.toThrow();
        });
    });

    describe('performance', () => {
        it('should handle rapid logging without errors', () => {
            expect(() => {
                for (let i = 0; i < 100; i++) {
                    logger.log(`Message ${i}`);
                }
            }).not.toThrow();
        });

        it('should handle large objects', () => {
            const largeObject = {};
            for (let i = 0; i < 100; i++) {
                largeObject[`key${i}`] = `value${i}`;
            }
            expect(() => logger.log('Large object:', largeObject)).not.toThrow();
        });
    });

    describe('special characters handling', () => {
        it('should handle strings with special characters', () => {
            const specialChars = 'Test: <script>alert("XSS")</script>';
            expect(() => logger.log(specialChars)).not.toThrow();
        });

        it('should handle unicode characters', () => {
            const unicode = 'Тест: 日本語 🎉 émoji';
            expect(() => logger.log(unicode)).not.toThrow();
        });

        it('should handle newlines and tabs', () => {
            const multiline = 'Line 1\nLine 2\tTabbed';
            expect(() => logger.log(multiline)).not.toThrow();
        });
    });

    describe('circular reference handling', () => {
        it('should handle circular references without throwing', () => {
            const obj = { name: 'test' };
            obj.self = obj; // Create circular reference

            expect(() => sanitize(obj)).not.toThrow();
        });

        it('should handle deeply nested objects', () => {
            let nested = { value: 'deep' };
            for (let i = 0; i < 20; i++) {
                nested = { child: nested };
            }

            expect(() => sanitize(nested)).not.toThrow();
        });
    });
});
