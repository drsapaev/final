import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wizardPath = path.resolve(__dirname, '../AppointmentWizardV2.tsx');
const wizardUtilsPath = path.resolve(__dirname, '../wizardUtils.ts');
const patientStepPath = path.resolve(__dirname, '../PatientStepV2.tsx');
const cartStepPath = path.resolve(__dirname, '../CartStepV2.tsx');
const serviceResolverPath = path.resolve(__dirname, '../../../utils/serviceCodeResolver.js');

// UX Audit Stage 3 (Wizard issue 5.2):
// Helper-функции вынесены в wizardUtils.js, а step-компоненты — в
// PatientStepV2.jsx и CartStepV2.jsx. Поэтому читаем все 4 файла.
const readWizardSource = () => fs.readFileSync(wizardPath, 'utf8');
const readWizardUtilsSource = () => fs.readFileSync(wizardUtilsPath, 'utf8');
const readPatientStepSource = () => fs.readFileSync(patientStepPath, 'utf8');
const readCartStepSource = () => fs.readFileSync(cartStepPath, 'utf8');
// Combined source: основной файл + утилиты + step-компоненты — для contract-проверок.
const readCombinedWizardSource = () =>
  readWizardSource() +
  '\n\n// === wizardUtils.js ===\n\n' + readWizardUtilsSource() +
  '\n\n// === PatientStepV2.jsx ===\n\n' + readPatientStepSource() +
  '\n\n// === CartStepV2.jsx ===\n\n' + readCartStepSource();
const readServiceResolverSource = () => fs.readFileSync(serviceResolverPath, 'utf8');

const extractSourceBlock = (source, startMarker, endMarker) => {
  const start = source.indexOf(startMarker);
  expect(start).toBeGreaterThanOrEqual(0);
  const end = source.indexOf(endMarker, start);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end);
};

describe('AppointmentWizardV2 registrar metadata contract', () => {
  it('loads registrar services and doctors through the unified api client', () => {
    const source = readCombinedWizardSource();
    const servicesLoadBlock = extractSourceBlock(
      source,
      'const loadServices = useCallback(async () => {',
      'const getServiceName = useCallback((item) => {',
    );
    const doctorsLoadBlock = extractSourceBlock(
      source,
      'const loadDoctors = useCallback(async () => {',
      'useEffect(() => {',
    );

    expect(servicesLoadBlock).toContain('api.get(\'/registrar/services\')');
    expect(doctorsLoadBlock).toContain('api.get(\'/registrar/doctors\')');
    expect(servicesLoadBlock).not.toContain('fetch(`${API_BASE}/registrar/services`');
    expect(doctorsLoadBlock).not.toContain('fetch(`${API_BASE}/registrar/doctors`');
    expect(servicesLoadBlock).not.toContain('\'Authorization\': `Bearer ${tokenManager.getAccessToken()}`');
    expect(doctorsLoadBlock).not.toContain('\'Authorization\': `Bearer ${tokenManager.getAccessToken()}`');
  });

  it('preserves existing queue identity when grouping edit-mode cart items', () => {
    const source = readCombinedWizardSource();
    const groupingBlock = extractSourceBlock(
      source,
      'const groupCartItemsByVisit = () => {',
      'const getDepartmentByService = (serviceId) => {',
    );
    const newServiceBlock = extractSourceBlock(
      source,
      'const newServicesWithDoctorId = [];',
      'const newServices = [];',
    );

    expect(groupingBlock).toContain('original_queue_id: item.original_queue_id || null');
    expect(newServiceBlock).toContain('const hasExistingQueueIdentity = Boolean(serviceItem.original_queue_id);');
    expect(newServiceBlock).toContain('const isNewService = !hasExistingQueueIdentity');
    expect(source).toContain('const resolveExplicitQueueEntryId = (record, { allowLegacyId = true } = {}) => {');
    expect(source).toContain('if (!allowLegacyId || hasQueueIdentityValue(record.queue_id))');
    expect(source).toContain('return resolveExplicitQueueEntryId(record) ?? getFirstQueueNumberId(record);');
  });

  it('maps service-array initial data back to queue_numbers before edit saves', () => {
    const source = readServiceResolverSource();

    expect(source).toContain('const resolveOriginalQueueId = (serviceData = {}) => {');
    expect(source).toContain('initialData.queue_numbers.find');
    expect(source).toContain('}, resolveOriginalQueueId(serviceItem))');
    expect(source).toContain('}, resolveOriginalQueueId({ name: serviceName, code: serviceCode }))');
    expect(source).toContain('}, resolveOriginalQueueId({ code: normalizedCode || serviceCode, service_id: foundService?.id || null }))');
  });

  it('normalizes edit-mode gender and persists selected existing-patient gender before submit', () => {
    const source = readCombinedWizardSource();
    const initBlock = extractSourceBlock(
      source,
      'useEffect(() => {',
      '  // Safeguard: Ensure wizardData structure is valid',
    );
    const patientIdBlock = extractSourceBlock(
      source,
      'let patientId = wizardData.patient.id;',
      '// === ШАГ 1: ОПРЕДЕЛЯЕМ ИЛИ НАХОДИМ patient_id ===',
    );

    // UX Audit Stage 3: helper now in wizardUtils.js as `export const`.
    expect(source).toContain('normalizeGenderForForm = (value) => {');
    expect(source).toContain('[\'m\', \'male\', \'man\', \'men\', \'1\',');
    expect(source).toContain('[\'f\', \'female\', \'woman\', \'women\', \'2\',');
    // UX Audit Stage 3 (Wizard issue 5.2): helper functions moved to wizardUtils.js.
    // Tests now check for `export const ...` and tolerate line breaks.
    expect(source).toContain('resolvePatientGenderValue');
    expect(source).toContain('firstNonEmpty(');
    expect(source).toContain('record?.patient_sex');
    expect(source).toContain('genderToPatientSexForApi');
    expect(source).toContain('resolveInitialPatientId');
    expect(initBlock).toContain('id: resolveInitialPatientId(initialData)');
    expect(initBlock).toContain('const genderValue = resolvePatientGenderValue(initialData);');
    expect(initBlock).toContain('return normalizeGenderForForm(genderValue);');
    expect(initBlock).toContain('const hydrateMissingEditGender = async () => {');
    expect(initBlock).toContain('fetch(`${API_BASE}/api/v1/patients/${patientId}`');
    expect(initBlock).toContain('if (prev.patient.gender) return prev;');
    expect(source).toContain('const selectedGender = normalizeGenderForForm(safeData.gender);');
    // UX Audit R-3.3 (Phase 4): inline style replaced with conditional className.
    // Old: background: selectedGender === gender
    // New: className with --selected/--unselected variant
    expect(source).toContain('selectedGender === gender');
    expect(source).toContain('patient-step-v2__gender-radio--selected');
    expect(source).toContain('const selectedPatientSex = genderToPatientSexForApi(wizardData.patient.gender);');
    expect(source).toContain('sex: selectedPatientSex');
    expect(source).not.toContain('gender: wizardData.patient.gender');
    expect(patientIdBlock).toContain('const initialPatientId = resolveInitialPatientId(initialData);');
    expect(patientIdBlock).toContain('patientId = initialPatientId;');
    // UX Audit Stage 3: raw fetch replaced with updatePatient() from api/patients.
    // Old: body: JSON.stringify({ sex: selectedPatientSex })
    // New: updatePatient(patientId, { sex: selectedPatientSex })
    expect(source).toContain('updatePatient(patientId, { sex: selectedPatientSex })');
  });

  it('filters services only for real department tabs, not registrar view tabs', () => {
    const source = readCombinedWizardSource();
    const servicesLoadBlock = extractSourceBlock(
      source,
      'const loadServices = useCallback(async () => {',
      'const getServiceName = useCallback((item) => {',
    );

    // PR-25: filter map renamed to _FALLBACK, function signature changed to accept queueProfiles
    expect(source).toContain('WIZARD_DEPARTMENT_FILTER_KEYS');
    expect(source).toContain('getWizardDepartmentFilterKeys');
    expect(source).toContain('echokg');
    expect(servicesLoadBlock).toContain('getWizardDepartmentFilterKeys(activeTab');
    expect(servicesLoadBlock).toContain('if (departmentFilterKeys.length > 0)');
    expect(servicesLoadBlock).not.toContain('if (activeTab && activeTab !== \'all\')');
  });

  it('loads all services in edit mode while keeping category tabs active', () => {
    const source = readCombinedWizardSource();
    const initBlock = extractSourceBlock(
      source,
      'useEffect(() => {',
      '  // Safeguard: Ensure wizardData structure is valid',
    );
    const servicesLoadBlock = extractSourceBlock(
      source,
      'const loadServices = useCallback(async () => {',
      'const getServiceName = useCallback((item) => {',
    );
    const displayedServicesBlock = extractSourceBlock(
      source,
      'const getDisplayedServices = () => {',
      'const displayedServices = getDisplayedServices();',
    );

    expect(source).toContain('const serviceCodeToWizardCategory = (value) => {');
    expect(source).toContain('const activeTabToWizardCategory = (value) => {');
    expect(source).toContain('const resolveInitialServiceCategory = (items = [], activeTabValue = \'\') => {');
    expect(initBlock).toContain('const initialCartItems = (() => {');
    expect(initBlock).toContain('setActiveServiceCategory(resolveInitialServiceCategory(initialCartItems, activeTab));');
    expect(initBlock).toContain('setActiveServiceCategory(activeTabToWizardCategory(activeTab));');
    expect(initBlock).toContain('setServiceSearchQuery(\'\');');
    expect(source).toContain('editMode={editMode}');
    // PR-25: now uses dynamic queueProfiles param
    expect(servicesLoadBlock).toContain('editMode ? [] : getWizardDepartmentFilterKeys(activeTab');
    expect(displayedServicesBlock).not.toContain('if (editMode) {');
    expect(displayedServicesBlock).toContain('switch (activeCategory)');
    expect(displayedServicesBlock).toContain('case \'specialists\':');
    expect(displayedServicesBlock).toContain('case \'laboratory\':');
    expect(displayedServicesBlock).toContain('case \'procedures\':');
    expect(displayedServicesBlock).toContain('case \'other\':');
  });

  it('treats service_details as existing services in edit mode to avoid duplicate queues', () => {
    const source = readCombinedWizardSource();
    const existingServicesBlock = extractSourceBlock(
      source,
      'const originalServiceCodes = new Set();',
      'logger.log(\'📋 Исходные услуги определены:\'',
    );

    expect(existingServicesBlock).toContain('Array.isArray(initialData.service_details)');
    expect(existingServicesBlock).toContain('const serviceId = serviceDetail.service_id || serviceDetail.id || null;');
    expect(existingServicesBlock).toContain('if (serviceId) originalServiceIds.add(serviceId);');
    expect(existingServicesBlock).toContain('const queueId = resolveExplicitQueueEntryId(serviceDetail, { allowLegacyId: false });');
    expect(existingServicesBlock).not.toContain('serviceDetail.queue_id ||');
    expect(existingServicesBlock).toContain('const queueId = resolveExplicitQueueEntryId(q);');
    expect(existingServicesBlock).not.toContain('if (q.id) originalQueueIds.add(q.id)');
    expect(existingServicesBlock).toContain('if (queueId) originalQueueIds.add(queueId);');
  });

  it('does not call registrar cart for edit mode when no new services were added', () => {
    const source = readCombinedWizardSource();
    const editSaveBlock = extractSourceBlock(
      source,
      'const hasNewServices = newServices.length > 0 || newServicesWithoutDoctor.length > 0;',
      'const cartData = {',
    );

    expect(editSaveBlock).toContain('if (editMode && hasNewServices) {');
    expect(editSaveBlock).toContain('const editDeltaServices = [');
    expect(editSaveBlock).toContain('applyRegistrarEditDelta({');
    expect(editSaveBlock).toContain('existingQueueEntryIds: Array.from(originalQueueIds)');
    expect(editSaveBlock).toContain('if (editMode && !hasNewServices) {');
    expect(editSaveBlock).toContain('bypassing registrar/cart to avoid duplicate visits');
    expect(editSaveBlock).toContain('visits = [];');
    expect(editSaveBlock).toContain('if (visits.length === 0 && editMode) {');
  });

  it('uses stable unique keys for doctor options in cart rows', () => {
    const source = readCombinedWizardSource();

    expect(source).toContain('doctorOptions.map((doctor, index)');
    expect(source).toContain('key={`${doctor.id ?? \'doctor\'}-${doctor.specialty ?? \'\'}-${index}`}');
  });
});
