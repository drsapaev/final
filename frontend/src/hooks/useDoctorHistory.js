/**
 * useDoctorHistory - Fetch doctor's previous EMR entries for AI context
 * 
 * PURPOSE:
 * - Provide context to AI for better suggestions
 * - NOT for direct autocomplete
 * - AI uses this to generate more relevant suggestions
 * 
 * RULES:
 * - History is INPUT to AI, not output
 * - No direct field population
 * - All suggestions still require click
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';

/**
 * useDoctorHistory Hook
 * 
 * @param {Object} options
 * @param {number} options.doctorId - Doctor ID
 * @param {string} options.specialty - Doctor specialty
 * @param {string} options.fieldName - Field to get history for
 * @param {string} options.currentText - Current text (for similarity)
 * @param {number} options.limit - Max entries to fetch
 * @param {boolean} options.enabled - Enable fetching
 */
export function useDoctorHistory({
    doctorId,
    specialty = 'general',
    fieldName,
    currentText = '',
    limit = 10,
    enabled = true,
}) {
    const [history, setHistory] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const abortControllerRef = useRef(null);

    /**
     * Fetch history from backend
     */
    const fetchHistory = useCallback(async () => {
        if (!enabled || !doctorId || !fieldName) return;

        // Cancel previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        setIsLoading(true);
        setError(null);

        try {
            const response = await apiClient.get('/v2/emr/doctor-history', {
                params: {
                    doctor_id: doctorId,
                    specialty,
                    field_name: fieldName,
                    search_text: currentText.slice(0, 100), // Limit search text
                    limit,
                },
                signal: abortControllerRef.current.signal,
            });

            setHistory(response.data.entries || []);
        } catch (err) {
            if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
                console.error('[useDoctorHistory] Error:', err);
                setError(err.message);
                // Return empty on error - not critical
                setHistory([]);
            }
        } finally {
            setIsLoading(false);
        }
    }, [enabled, doctorId, specialty, fieldName, currentText, limit]);

    /**
     * Get unique phrases from history
     */
    const getUniquePhrases = useCallback(() => {
        const phrases = new Set();
        history.forEach(entry => {
            if (entry.content) {
                // Split by sentences/newlines
                entry.content.split(/[.\n]/).forEach(phrase => {
                    const trimmed = phrase.trim();
                    if (trimmed.length > 10 && trimmed.length < 200) {
                        phrases.add(trimmed);
                    }
                });
            }
        });
        return Array.from(phrases);
    }, [history]);

    /**
     * Get history as AI context
     */
    const getAIContext = useCallback(() => {
        if (history.length === 0) return null;

        return {
            doctor_id: doctorId,
            specialty,
            field_name: fieldName,
            previous_entries: history.slice(0, 5).map(e => ({
                content: e.content?.slice(0, 500), // Limit content size
                diagnosis: e.diagnosis,
                created_at: e.created_at,
            })),
            unique_phrases: getUniquePhrases().slice(0, 20),
        };
    }, [history, doctorId, specialty, fieldName, getUniquePhrases]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, []);

    return {
        // Data
        history,
        getUniquePhrases,
        getAIContext,

        // State
        isLoading,
        error,
        hasHistory: history.length > 0,

        // Actions
        fetchHistory,
        refresh: fetchHistory,
    };
}

export default useDoctorHistory;
