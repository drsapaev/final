/**
 * ESLint custom rule: no-domain-type-duplication
 *
 * Bans re-declaring canonical domain entity names (Patient, Doctor,
 * Appointment, etc.) outside src/types/domain/. These names MUST live
 * in the domain layer as the single source of truth.
 *
 * Allowed locations:
 *   - src/types/domain/      (the SSOT itself)
 *   - test files             (test fixtures may define shapes)
 *   - re-export statements: `export type { Patient } from '@/types/domain/clinic'`
 *
 * Rationale: Wave 3 of Domain Adoption 100% consolidated these names into
 * the domain layer. Without enforcement, developers tend to re-declare
 * them locally when they need a "slightly different shape", which
 * re-introduces the duplication problem the domain layer was built to
 * solve. This rule makes that pattern an explicit lint error.
 *
 * To add a new domain name, extend DOMAIN_NAMES below.
 */

// Canonical domain entity names. Adding a name here makes re-declaring it
// outside src/types/domain/ an error. Update this list whenever a new
// top-level aggregate is added to src/types/domain/*.ts.
const DOMAIN_NAMES = new Set([
  // clinic.ts
  'Patient',
  'Doctor',
  'Appointment',
  'Service',
  'Department',
  'Transaction',
  'ReportConfig',
  'DepartmentStats',
  'ServiceCategory',
  'ServiceFilter',
  'DoctorScheduleSlot',
  'DoctorAvailability',
  'QueueNumberInfo',
  'AppointmentStatus',
  'AppointmentType',
  // queue.ts
  'QueueEntry',
  'QueueState',
  'QueueStats',
  'QueueFilters',
  'QueueSpecialist',
  'QueueData',
  'QueuePayload',
  'QrData',
  'QueueActionResponse',
  'LoadQueueSnapshotArgs',
  'GenerateDoctorQRCodeArgs',
  'GenerateClinicQRCodeArgs',
  'ReceptionSlotArgs',
  'QueueJoinSessionData',
  'QueueJoinInfo',
  'QrTokenInfo',
  'QueueProfile',
  'QueueProfilesResponse',
  // auth.ts
  'AuthUser',
  'AuthState',
  'AuthSessionState',
  'UserProfile',
  'Role',
  'RoleRecord',
  'Permission',
  'LoginCredentials',
  'LoginResponse',
  'TokenPayload',
  'SessionInfo',
  'AuthAction',
  // billing.ts
  'Invoice',
  'InvoiceItem',
  'Payment',
  'Discount',
  'DiscountApplication',
  'BillingSummary',
  'Refund',
  'PaymentProvider',
  'PaymentWebhook',
  'CartItemBilling',
  'PaymentResult',
  'PaymentMethod',
  'PaymentStatus',
  'DiscountMode',
  'RefundStatus',
  // emr.ts (top-level EMR aggregates)
  'EMRTemplate',
  'EMRSection',
  'EMRDiagnosis',
  'EMRPrescription',
  // ai.ts
  'AIChatMessage',
  'AISuggestion',
  'AISuggestionHistoryEntry',
  'AITranslationEntry',
  'AIBatchTranslationResult',
  'AIImageAnalysisResult',
  'AIProvider',
  'AIContext',
  // chat.ts
  'ChatMessage',
  'ChatConversation',
  'ChatAvailableUser',
  'ChatReaction',
  'ChatConversationsResponse',
  'ChatConversationResponse',
  'ChatUnreadCountResponse',
  'ChatAvailableUsersResponse',
  // mcp.ts
  'McpResult',
  'McpSuccess',
  'McpFailure',
  'McpChatMessage',
  'McpChatPayload',
  'McpChatData',
]);

function isTestFile(filename) {
  return (
    /\.test\.[jt]sx?$/.test(filename) ||
    filename.includes('/__tests__/') ||
    filename.includes('\\__tests__\\') ||
    filename.includes('/test/') ||
    filename.includes('\\test\\')
  );
}

function isDomainFile(filename) {
  const normalized = filename.replace(/\\/g, '/');
  return normalized.includes('/types/domain/');
}

function isTypesBarrelOrReExport(filename) {
  const normalized = filename.replace(/\\/g, '/');
  // Wave G6: types/auth.ts and types/auth-store.ts were deleted.
  // stores/auth.ts no longer re-exports domain types — consumers import
  // directly from types/domain/auth.
  // Remaining shims: hooks that still re-export for backwards compat.
  return (
    normalized.endsWith('/types/index.ts') ||
    normalized.endsWith('/hooks/useRoles.ts') ||
    normalized.endsWith('/hooks/useQueueManager.ts') ||
    normalized.endsWith('/utils/mcp.ts')
  );
}

export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Ban re-declaring canonical domain entity names outside src/types/domain/',
      category: 'Best Practices',
      recommended: true,
    },
    messages: {
      duplicate:
        'Domain entity "{{name}}" must not be re-declared here. ' +
        'Import it from "@/types/domain/*" instead. ' +
        'If you need a different shape, extend the domain type or use a ' +
        'local *Record/*Dto name — do not shadow the canonical name. ' +
        '(Wave 5: Domain Adoption 100% regression guard)',
    },
    schema: [],
  },
  create(context) {
    const filename = context.getFilename();

    // Skip test files, domain files, and the legacy re-export shims.
    if (isTestFile(filename) || isDomainFile(filename) || isTypesBarrelOrReExport(filename)) {
      return {};
    }

    return {
      // Catch `interface Patient { ... }` and `export interface Patient { ... }`
      TSInterfaceDeclaration(node) {
        if (DOMAIN_NAMES.has(node.id.name)) {
          context.report({
            node,
            messageId: 'duplicate',
            data: { name: node.id.name },
          });
        }
      },
      // Catch `type Patient = ...` and `export type Patient = ...`
      // (but NOT `export type { Patient } from '...'` — that's an export spec,
      // which is handled by TSExportAssignment / ExportNamedDeclaration below).
      TSTypeAliasDeclaration(node) {
        if (DOMAIN_NAMES.has(node.id.name)) {
          context.report({
            node,
            messageId: 'duplicate',
            data: { name: node.id.name },
          });
        }
      },
    };
  },
};
