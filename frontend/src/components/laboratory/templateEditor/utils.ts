/**
 * L-H-6 fix: shared helpers для templateEditor.
 * Раньше жили в LabTemplateWorkbench.jsx как module-level functions.
 */

export const blankField = () => ({
  analyte_code: '',
  unit_code: '',
  field_key: '',
  label: '',
  value_type: 'numeric',
  unit: '',
  reference_mode: 'static_text',
  reference_text: '',
  reference_rule: null,
  visibility_rule: null,
  highlight_rule: null,
  choice_options: null,
  sort_order: 0,
  required: false
});

export const blankSection = (index) => ({
  key: `section_${index}`,
  title: `Раздел ${index}`,
  sort_order: index * 10,
  section_style: {},
  fields: [blankField()]
});

export const blankVersion = {
  layout_preset: 'lab_table_classic_v1',
  page_settings: { paper_size: 'A4', orientation: 'portrait' },
  branding_overrides: {
    document_title: '',
    document_subtitle: '',
    clinic_name: '',
    address: '',
    phone: '',
    logo_url: ''
  },
  signer_defaults: {
    lab_technician_label: 'Лаборант',
    lab_technician_name: '',
    approver_label: 'Подпись',
    approver_name: ''
  },
  footer_notes: '',
  sections: [blankSection(1)]
};

export const TEMPLATE_VERSION_ACTION_CAN_FIELD = {
  update: 'can_update',
  publish: 'can_publish',
  create_draft: 'can_create_draft'
};

export function hasTemplateVersionAction(version, action) {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(version?.available_actions)) {
    return version.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const flagName = TEMPLATE_VERSION_ACTION_CAN_FIELD[normalizedAction];
  if (flagName && Object.prototype.hasOwnProperty.call(version || {}, flagName)) {
    return Boolean(version[flagName]);
  }

  return false;
}

export function parseJsonInput(value) {
  if (!value?.trim()) {
    return null;
  }
  try {
    return JSON.parse(value);
  } catch {
    return Symbol.for('invalid-json');
  }
}

export function stringifyJson(value) {
  if (!value) {
    return '';
  }
  return JSON.stringify(value, null, 2);
}

export function buildVersionPayload(draftVersion) {
  const sections = draftVersion.sections.map((section, sectionIndex) => ({
    ...section,
    sort_order: section.sort_order ?? (sectionIndex + 1) * 10,
    section_style: section.section_style || {},
    fields: section.fields.map((field, fieldIndex) => {
      const referenceRule = parseJsonInput(field.reference_rule_text || '');
      const visibilityRule = parseJsonInput(field.visibility_rule_text || '');
      const highlightRule = parseJsonInput(field.highlight_rule_text || '');
      if ([referenceRule, visibilityRule, highlightRule].includes(Symbol.for('invalid-json'))) {
        throw new Error('Один из JSON-блоков правил заполнен некорректно');
      }
      return {
        ...field,
        sort_order: field.sort_order ?? (fieldIndex + 1) * 10,
        reference_rule: referenceRule,
        visibility_rule: visibilityRule,
        highlight_rule: highlightRule,
        reference_rule_text: undefined,
        visibility_rule_text: undefined,
        highlight_rule_text: undefined
      };
    })
  }));

  return {
    layout_preset: draftVersion.layout_preset,
    page_settings: draftVersion.page_settings || { paper_size: 'A4', orientation: 'portrait' },
    branding_overrides: draftVersion.branding_overrides || {},
    signer_defaults: draftVersion.signer_defaults || {},
    footer_notes: draftVersion.footer_notes || '',
    sections
  };
}

export function hydrateVersion(version) {
  if (!version) {
    return { ...blankVersion, sections: [blankSection(1)] };
  }
  return {
    layout_preset: version.layout_preset,
    page_settings: version.page_settings || { paper_size: 'A4', orientation: 'portrait' },
    branding_overrides: {
      clinic_name: '',
      address: '',
      phone: '',
      logo_url: '',
      document_title: '',
      document_subtitle: '',
      ...(version.branding_overrides || {})
    },
    signer_defaults: {
      lab_technician_label: 'Лаборант',
      lab_technician_name: '',
      approver_label: 'Подпись',
      approver_name: '',
      ...(version.signer_defaults || {})
    },
    footer_notes: version.footer_notes || '',
    sections: (version.sections || []).map((section) => ({
      ...section,
      fields: (section.fields || []).map((field) => ({
        ...field,
        reference_rule_text: stringifyJson(field.reference_rule),
        visibility_rule_text: stringifyJson(field.visibility_rule),
        highlight_rule_text: stringifyJson(field.highlight_rule)
      }))
    }))
  };
}
