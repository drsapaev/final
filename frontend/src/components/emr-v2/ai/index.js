/**
 * EMR v2 AI Components
 * 
 * CRITICAL RULES:
 * - AI can ONLY SUGGEST, never modify EMR directly
 * - All suggestions require explicit user click to apply
 * - Applied suggestions go through setField (audit trail)
 * 
 * Components:
 * - AISuggestionPanel: Sidebar with all suggestions
 * - AISuggestionPopover: Inline popup for field
 * - SmartAssistButton: AI button (lightbulb)
 * - CompletenessChecker: "Check missing fields"
 */

// Hook
export { useEMRAI } from './useEMRAI';

// Sidebar panel
export { AISuggestionCard } from './AISuggestionCard';
export { AISuggestionPanel } from './AISuggestionPanel';

// Inline (IDE-like)
export { AISuggestionPopover } from './AISuggestionPopover';
export { SmartAssistButton } from './SmartAssistButton';
export { CompletenessChecker } from './CompletenessChecker';
export { PhraseSuggestions } from './PhraseSuggestions';
