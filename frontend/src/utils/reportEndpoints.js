/**
 * reportEndpoints — shared report-type → endpoint mapping (P2 dedup, Sprint 4).
 *
 * Replaces 2 copies that lived in ReportGenerator.jsx (REPORT_ENDPOINTS map)
 * and ReportsManager.jsx (getReportEndpoint function with inline map).
 *
 * The ReportGenerator copy was the superset (12 entries with aliases);
 * ReportsManager had a 5-entry subset. Consolidated here so both components
 * use the same source of truth.
 */
export const REPORT_ENDPOINTS = {
  patient_report: 'patient',
  appointments_report: 'appointments',
  financial_report: 'financial',
  queue_report: 'queue',
  doctor_performance_report: 'doctor-performance',
  // Aliases (from ReportGenerator copy)
  patients: 'patient',
  appointments: 'appointments',
  financial: 'financial',
  queue: 'queue',
  doctors: 'doctor-performance',
  performance: 'doctor-performance',
  revenue: 'financial',
  analytics: 'financial',
};

/**
 * Resolve a report type to its backend endpoint slug, or null if unknown.
 */
export const getReportEndpoint = (type) => REPORT_ENDPOINTS[type] || null;

export default REPORT_ENDPOINTS;
