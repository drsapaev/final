/**
 * useEMRVersion - Hook for EMR v2 feature flag
 * 
 * Determines which EMR version to show based on:
 * 1. EMR_V2_ENABLED global toggle
 * 2. User is in allowed users list
 * 3. User falls within rollout percentage
 *
 * Returns version to use and ability to manually switch (for allowed users)
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';

/**
 * Hash user ID to consistent 0-99 value for rollout percentage
 */
function getUserBucket(userId) {
    if (!userId) return 100; // No user = no access
    // Simple hash: user ID modulo 100
    return userId % 100;
}

/**
 * useEMRVersion Hook
 * 
 * @param {number} userId - Current user ID
 * @returns {Object} Version info and controls
 */
export function useEMRVersion(userId) {
    const [config, setConfig] = useState({
        enabled: false,
        rolloutPercentage: 0,
        allowedUserIds: [],
        shadowMode: false,
    });
    const [loading, setLoading] = useState(true);
    const [manualOverride, setManualOverride] = useState(null); // null = auto, 'v1' | 'v2'

    // Load feature flag config on mount
    useEffect(() => {
        const loadConfig = async () => {
            try {
                const response = await apiClient.get('/v2/emr/feature-flags');
                setConfig(response.data);
            } catch (error) {
                console.error('Failed to load EMR feature flags:', error);
                // Default to v1 on error
                setConfig({
                    enabled: false,
                    rolloutPercentage: 0,
                    allowedUserIds: [],
                    shadowMode: false,
                });
            } finally {
                setLoading(false);
            }
        };

        loadConfig();
    }, []);

    // Determine if user should see v2
    const shouldUseV2 = useCallback(() => {
        // If manually overridden, respect that
        if (manualOverride !== null) {
            return manualOverride === 'v2';
        }

        // If globally disabled, use v1
        if (!config.enabled) {
            return false;
        }

        // If user is in allowed list, use v2
        if (config.allowedUserIds?.includes(userId)) {
            return true;
        }

        // Check rollout percentage
        const userBucket = getUserBucket(userId);
        return userBucket < (config.rolloutPercentage || 0);
    }, [config, userId, manualOverride]);

    // Whether user can manually switch versions
    const canSwitch = config.allowedUserIds?.includes(userId) || (config.rolloutPercentage || 0) >= 100;

    // Switch to specific version
    const switchToVersion = useCallback((version) => {
        if (canSwitch && (version === 'v1' || version === 'v2')) {
            setManualOverride(version);
            // Persist preference in localStorage
            localStorage.setItem('emr_version_override', version);
        }
    }, [canSwitch]);

    // Reset to auto-detect
    const resetToAuto = useCallback(() => {
        setManualOverride(null);
        localStorage.removeItem('emr_version_override');
    }, []);

    // Load override from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem('emr_version_override');
        if (saved === 'v1' || saved === 'v2') {
            setManualOverride(saved);
        }
    }, []);

    const version = shouldUseV2() ? 'v2' : 'v1';

    return {
        // Current version to use
        version,

        // Whether using V2
        isV2: version === 'v2',

        // Whether user can manually switch
        canSwitch,

        // Switch functions
        switchToVersion,
        resetToAuto,

        // Current override status
        isOverridden: manualOverride !== null,

        // Shadow mode (render both, v2 hidden)
        shadowMode: config.shadowMode,

        // Loading state
        loading,

        // Raw config (for debugging)
        config,
    };
}

export default useEMRVersion;
