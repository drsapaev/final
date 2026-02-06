/**
 * useEMRAI - AI suggestions for EMR fields
 * 
 * CRITICAL RULES:
 * - AI can ONLY SUGGEST, never modify EMR directly
 * - All suggestions require explicit user click to apply
 * - Applied suggestions go through setField (audit trail)
 * 
 * AI CAN:
 * - Generate text suggestions
 * - Propose diagnoses/formulations
 * - Indicate missing fields
 * - Summarize visit
 * 
 * AI CANNOT:
 * - Save data
 * - Modify state directly
 * - Sign EMR
 * - Act without user click
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../../../api/client';

/**
 * Suggestion shape
 * @typedef {Object} AISuggestion
 * @property {string} id - Unique suggestion ID
 * @property {string} targetField - Field to apply to (e.g., 'diagnosis')
 * @property {string} content - Suggested text
 * @property {number} confidence - AI confidence score (0-1)
 * @property {string} source - Source label ('AI')
 * @property {string} explanation - Why this suggestion
 * @property {string} model - AI model used
 */

/**
 * useEMRAI Hook
 * 
 * @param {Object} options
 * @param {Object} options.emrData - Current EMR data (read-only snapshot)
 * @param {string} options.specialty - Medical specialty (e.g., 'cardiology')
 * @param {string} options.language - Language for suggestions (default: 'ru')
 * @param {boolean} options.enabled - Enable AI suggestions
 * @param {number} options.debounceMs - Debounce before requesting suggestions
 * @param {Object} options.doctorContext - Doctor history context for better suggestions
 */
export function useEMRAI({
    emrData,
    specialty = 'general',
    language = 'ru',
    enabled = true,
    debounceMs = 2000,
    doctorContext = null,
}) {
    const [suggestions, setSuggestions] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [lastRequestTime, setLastRequestTime] = useState(null);
    const debounceRef = useRef(null);
    const abortControllerRef = useRef(null);

    /**
     * Request suggestions from AI backend
     */
    const requestSuggestions = useCallback(async (data, context = null) => {
        if (!enabled || !data) return;

        // Cancel previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        setIsLoading(true);
        setError(null);

        try {
            const requestBody = {
                emr_snapshot: data,
                specialty,
                language,
            };

            // Include doctor history context if available
            if (context || doctorContext) {
                requestBody.doctor_context = context || doctorContext;
            }

            const response = await apiClient.post('/ai/suggest', requestBody, {
                signal: abortControllerRef.current.signal,
            });

            setSuggestions(response.data.suggestions || []);
            setLastRequestTime(Date.now());
        } catch (err) {
            if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
                console.error('[useEMRAI] Error fetching suggestions:', err);
                setError(err.message || 'Не удалось получить подсказки AI');
            }
        } finally {
            setIsLoading(false);
        }
    }, [enabled, specialty, language, doctorContext]);

    /**
     * Debounced request
     */
    const debouncedRequest = useCallback((data) => {
        if (debounceRef.current) {
            clearTimeout(debounceRef.current);
        }
        debounceRef.current = setTimeout(() => {
            requestSuggestions(data);
        }, debounceMs);
    }, [requestSuggestions, debounceMs]);

    /**
     * Trigger suggestions when data changes
     */
    useEffect(() => {
        if (enabled && emrData) {
            debouncedRequest(emrData);
        }

        return () => {
            if (debounceRef.current) {
                clearTimeout(debounceRef.current);
            }
        };
    }, [enabled, emrData, debouncedRequest]);

    /**
     * Dismiss a suggestion
     */
    const dismissSuggestion = useCallback((suggestionId) => {
        setSuggestions(prev => prev.filter(s => s.id !== suggestionId));
    }, []);

    /**
     * Clear all suggestions
     */
    const clearSuggestions = useCallback(() => {
        setSuggestions([]);
    }, []);

    /**
     * Manually refresh suggestions
     */
    const refreshSuggestions = useCallback(() => {
        if (emrData) {
            requestSuggestions(emrData);
        }
    }, [emrData, requestSuggestions]);

    /**
     * Get suggestions for a specific field
     */
    const getSuggestionsForField = useCallback((fieldName) => {
        return suggestions.filter(s => s.targetField === fieldName);
    }, [suggestions]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    return {
        // Suggestions
        suggestions,
        getSuggestionsForField,

        // State
        isLoading,
        error,
        lastRequestTime,

        // Actions
        dismissSuggestion,
        clearSuggestions,
        refreshSuggestions,

        // Config
        enabled,
        specialty,
    };
}

export default useEMRAI;
