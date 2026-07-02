/**
 * Unit tests for tokenManager utility
 * 
 * Tests cover:
 * - Token storage and retrieval
 * - Token clearing
 * - User data management
 * - Edge cases
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { tokenManager, TOKEN_KEYS } from '../tokenManager';

describe('tokenManager', () => {
    beforeEach(() => {
        // Clear all mocks before each test
        vi.clearAllMocks();
        localStorage.getItem.mockReturnValue(null);
    });

    describe('TOKEN_KEYS', () => {
        it('should have correct storage key names', () => {
            expect(TOKEN_KEYS.TOKEN_KEY).toBe('auth_token');
            expect(TOKEN_KEYS.REFRESH_TOKEN_KEY).toBe('refresh_token');
            expect(TOKEN_KEYS.USER_KEY).toBe('user');
        });
    });

    describe('getAccessToken', () => {
        it('should return token from localStorage', () => {
            const mockToken = 'test-access-token';
            localStorage.getItem.mockReturnValue(mockToken);

            const result = tokenManager.getAccessToken();

            expect(localStorage.getItem).toHaveBeenCalledWith('auth_token');
            expect(result).toBe(mockToken);
        });

        it('should return null when no token exists', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = tokenManager.getAccessToken();

            expect(result).toBeNull();
        });
    });

    describe('setAccessToken', () => {
        it('should save token to localStorage', () => {
            const mockToken = 'new-access-token';

            tokenManager.setAccessToken(mockToken);

            expect(localStorage.setItem).toHaveBeenCalledWith('auth_token', mockToken);
        });

        it('should remove token when null is passed', () => {
            tokenManager.setAccessToken(null);

            expect(localStorage.removeItem).toHaveBeenCalledWith('auth_token');
        });
    });

    describe('getRefreshToken', () => {
        it('should return refresh token from localStorage', () => {
            const mockToken = 'test-refresh-token';
            localStorage.getItem.mockReturnValue(mockToken);

            const result = tokenManager.getRefreshToken();

            expect(localStorage.getItem).toHaveBeenCalledWith('refresh_token');
            expect(result).toBe(mockToken);
        });
    });

    describe('setRefreshToken', () => {
        it('should save refresh token to localStorage', () => {
            const mockToken = 'new-refresh-token';

            tokenManager.setRefreshToken(mockToken);

            expect(localStorage.setItem).toHaveBeenCalledWith('refresh_token', mockToken);
        });
    });

    describe('getUserData', () => {
        it('should return parsed user object from localStorage', () => {
            const mockUser = { id: 1, username: 'testuser', role: 'doctor' };
            localStorage.getItem.mockReturnValue(JSON.stringify(mockUser));

            const result = tokenManager.getUserData();

            expect(localStorage.getItem).toHaveBeenCalledWith('user');
            expect(result).toEqual(mockUser);
        });

        it('should return null when no user data exists', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = tokenManager.getUserData();

            expect(result).toBeNull();
        });

        it('should return null on JSON parse error', () => {
            localStorage.getItem.mockReturnValue('invalid-json');

            const result = tokenManager.getUserData();

            expect(result).toBeNull();
        });
    });

    describe('setUserData', () => {
        it('should save user object as JSON to localStorage', () => {
            const mockUser = { id: 1, username: 'testuser', role: 'doctor' };

            tokenManager.setUserData(mockUser);

            expect(localStorage.setItem).toHaveBeenCalledWith('user', JSON.stringify(mockUser));
        });

        it('should remove user when null is passed', () => {
            tokenManager.setUserData(null);

            expect(localStorage.removeItem).toHaveBeenCalledWith('user');
        });
    });

    describe('clearAll', () => {
        it('should remove all authentication data from localStorage', () => {
            tokenManager.clearAll();

            expect(localStorage.removeItem).toHaveBeenCalledWith('auth_token');
            expect(localStorage.removeItem).toHaveBeenCalledWith('refresh_token');
            expect(localStorage.removeItem).toHaveBeenCalledWith('user');
        });
    });

    describe('hasToken', () => {
        it('should return true when access token exists', () => {
            localStorage.getItem.mockReturnValue('some-token');

            const result = tokenManager.hasToken();

            expect(result).toBe(true);
        });

        it('should return false when no access token exists', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = tokenManager.hasToken();

            expect(result).toBe(false);
        });

        it('should return false for empty string token', () => {
            localStorage.getItem.mockReturnValue('');

            const result = tokenManager.hasToken();

            expect(result).toBe(false);
        });
    });

    describe('isTokenValid', () => {
        it('should return false when no token exists', () => {
            localStorage.getItem.mockReturnValue(null);

            const result = tokenManager.isTokenValid();

            expect(result).toBe(false);
        });

        it('should return false for invalid token format', () => {
            localStorage.getItem.mockReturnValue('invalid-token');

            const result = tokenManager.isTokenValid();

            expect(result).toBe(false);
        });

        it('should return true for valid JWT format without exp', () => {
            // Create a mock JWT without expiration
            const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
            const payload = btoa(JSON.stringify({ sub: '1', name: 'Test' }));
            const signature = 'signature';
            const mockJwt = `${header}.${payload}.${signature}`;

            localStorage.getItem.mockReturnValue(mockJwt);

            const result = tokenManager.isTokenValid();

            expect(result).toBe(true);
        });

        it('should return false for expired JWT', () => {
            // Create a mock JWT with past expiration
            const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
            const payload = btoa(JSON.stringify({ sub: '1', exp: Math.floor(Date.now() / 1000) - 3600 }));
            const signature = 'signature';
            const mockJwt = `${header}.${payload}.${signature}`;

            localStorage.getItem.mockReturnValue(mockJwt);

            const result = tokenManager.isTokenValid();

            expect(result).toBe(false);
        });

        it('should return true for valid non-expired JWT', () => {
            // Create a mock JWT with future expiration
            const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
            const payload = btoa(JSON.stringify({ sub: '1', exp: Math.floor(Date.now() / 1000) + 3600 }));
            const signature = 'signature';
            const mockJwt = `${header}.${payload}.${signature}`;

            localStorage.getItem.mockReturnValue(mockJwt);

            const result = tokenManager.isTokenValid();

            expect(result).toBe(true);
        });
    });
});
