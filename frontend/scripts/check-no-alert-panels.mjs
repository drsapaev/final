import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const panelFiles = [
  'src/pages/AdminPanel.jsx',
  'src/pages/CashierPanel.jsx',
  'src/pages/DoctorPanel.jsx',
  'src/pages/RegistrarPanel.jsx',
  'src/pages/LabPanel.jsx',
  'src/pages/PatientPanel.jsx',
  'src/pages/CardiologistPanelUnified.jsx',
  'src/pages/DermatologistPanelUnified.jsx',
  'src/pages/DentistPanelUnified.jsx',
  'src/components/cashier/RefundRequestsTable.jsx',
  'src/components/payment/CashPaymentModal.jsx',
  'src/components/laboratory/LabResultsManager.jsx'
];

const allowedPatterns = [
  /window\.confirm\(/g
];

const stripAllowed = (text) => {
  let result = text;
  for (const pattern of allowedPatterns) {
    result = result.replace(pattern, '');
  }
  return result;
};

const violations = [];

for (const relativePath of panelFiles) {
  const fullPath = resolve(process.cwd(), relativePath);
  const source = readFileSync(fullPath, 'utf8');
  const sanitized = stripAllowed(source);

  if (sanitized.includes('alert(')) {
    violations.push(relativePath);
  }
}

if (violations.length > 0) {
  console.error('❌ Guard failed: alert(...) found in panel workflows:');
  for (const file of violations) {
    console.error(` - ${file}`);
  }
  process.exit(1);
}

console.log('✅ Guard passed: no alert(...) in enforced panel workflows.');
