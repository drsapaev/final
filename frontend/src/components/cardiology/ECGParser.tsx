
/**
 * ECG Parser Component
 * Парсинг SCP/XML форматов ЭКГ
 * Phase 3: stale MASTER_TODO_LIST reference removed.
 */
import logger from '../../utils/logger';
import i18n from '../../i18n';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

// ECGPARSER-FE-002 (audit 3886 round 25): strict numeric validation for
// clinical measurements. The old code classified values with parseInt():
// parseInt('120bad') === 120 silently accepted garbage as a verified
// measurement, and parseInt(null) === NaN failed BOTH range checks and
// fell into the unconditional "normal" else-branch — an absent heart rate
// or axis was reported as normal. A value is a measurement only when the
// ENTIRE value is a finite number; everything else is "not measured"
// (null) and must never be classified as a normal finding.
export const toFiniteNumber = (raw: unknown): number | null => {
  if (typeof raw === 'number') {
    return Number.isFinite(raw) ? raw : null;
  }
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (/^[+-]?\d+(?:\.\d+)?$/.test(trimmed)) {
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : null;
    }
  }
  return null;
};

// Парсер для SCP формата
// C-1 fix: previously this returned hardcoded fake parameters (heartRate: 75,
// prInterval: 160, etc.) regardless of file contents. Those fake values were
// then persisted to cardio_ecg_records via POST /cardio/ecg — a patient-safety
// risk because doctors could make clinical decisions based on fabricated data.
//
// Until a real SCP-ECG library is integrated, we hard-fail: return success=false
// so the caller (ECGViewer.parseECGFileData) shows a clear warning to the doctor
// and does NOT persist fake parameters to the database.
export const parseSCPFile = async (file: File) => {
  try {
    const buffer = await file.arrayBuffer();

    // Minimal SCP-ECG validation: file must be at least 6 bytes
    // (CRC uint16 + length uint32 header). Files smaller than this are
    // definitely not valid SCP-ECG.
    if (buffer.byteLength < 6) {
      return {
        success: false,
        error: t18('cardio.cardio_parser_scp_too_small'),
      };
    }

    // Real SCP-ECG parsing requires a dedicated library (e.g. ecg-scp).
    // Until integrated, we refuse to fabricate parameters — see C-1 fix note.
    logger.warn('[ECGParser] SCP-ECG parsing not implemented — refusing to fabricate parameters', {
      fileName: file?.name,
      fileSize: buffer.byteLength,
    });

    return {
      success: false,
      error: t18('cardio.cardio_parser_scp_not_implemented'),
      format: 'SCP',
      raw: buffer,
    };
  } catch (error) {
    logger.error('Ошибка парсинга SCP:', error);
    return {
      success: false,
      error: t18('cardio.cardio_parser_scp_read_failed'),
    };
  }
};

// Парсер для XML формата (HL7 aECG)
export const parseXMLFile = async (file: File) => {
  try {
    const text = await file.text();
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(text, 'text/xml');

    // Проверяем на ошибки парсинга
    const parserError = xmlDoc.querySelector('parsererror');
    if (parserError) {
      throw new Error('Invalid XML format');
    }

    // Извлекаем параметры из HL7 aECG формата.
    // ECGPARSER-FE-001/002/003 (audit 3886 round 25): every numeric
    // measurement is strict-validated at parse time — a malformed value
    // (e.g. '120bad') becomes "not measured" (null), never a fabricated
    // number, and absent tags stay explicit nulls instead of strings
    // that downstream parseInt() would misclassify.
    const parameters = {
      heartRate: toFiniteNumber(extractXMLValue(xmlDoc, 'heartRate', 'value')),
      prInterval: toFiniteNumber(extractXMLValue(xmlDoc, 'prInterval', 'value')),
      qrsInterval: toFiniteNumber(extractXMLValue(xmlDoc, 'qrsInterval', 'value')),
      qtInterval: toFiniteNumber(extractXMLValue(xmlDoc, 'qtInterval', 'value')),
      qtcInterval: toFiniteNumber(extractXMLValue(xmlDoc, 'qtcInterval', 'value')),
      // ECGPARSER-FE-003 + RETRO-3965-01 (post-merge review 3968): the
      // generic `axis` feeds the −30…+90 electrical axis classification
      // AND the structured /cardio/ecg `axis` column — both are QRS-axis
      // scales. A P-wave axis is NOT a substitute for the QRS electrical
      // axis (a P-only document previously produced a spurious QRS
      // left/right/normal classification and persisted the P value as
      // the QRS axis). `axis` is therefore the qrsAxis only; when the
      // document has no qrsAxis it stays an explicit null ("not
      // measured"). The P-wave axis survives as its own measurement
      // (`pAxis`) in the parsed parameters and the raw parameters dict —
      // never relabeled, never classified on the QRS scale.
      axis: toFiniteNumber(extractXMLValue(xmlDoc, 'qrsAxis', 'value')),
      pAxis: toFiniteNumber(extractXMLValue(xmlDoc, 'pAxis', 'value')),

      // Ритм
      rhythm: extractXMLValue(xmlDoc, 'rhythm', 'code'),

      // Интерпретация
      interpretation: extractXMLText(xmlDoc, 'interpretation'),

      // Дата записи
      recordingDate: extractXMLValue(xmlDoc, 'effectiveTime', 'value'),

      // Информация о пациенте
      patientInfo: {
        id: extractXMLValue(xmlDoc, 'patientRole', 'id'),
        age: extractXMLValue(xmlDoc, 'patient', 'age'),
        sex: extractXMLValue(xmlDoc, 'patient', 'administrativeGenderCode')
      },

      // Отведения
      leads: extractLeads(xmlDoc)
    };

    // ECGPARSER-FE-001 (audit 3886 round 25): a well-formed XML document
    // is NOT evidence of an ECG recording. The old parser returned
    // success:true for ANY syntactically valid XML (<unrelated/>, an empty
    // <ClinicalDocument/>) with every measurement null; the viewer then
    // ran the analysis and persisted a source:'device' /cardio/ecg record
    // whose findings claimed a normal HR and axis that were never
    // measured. At least one recognized aECG measurement (a numeric
    // interval, a rhythm code or lead waveform data) is required before
    // the document can be treated as a parsed ECG. Free-text
    // <interpretation> alone is NOT sufficient — it is the tag most likely
    // to appear in unrelated XML.
    const hasRecognizedEcgMeasurement =
      parameters.heartRate !== null ||
      parameters.prInterval !== null ||
      parameters.qrsInterval !== null ||
      parameters.qtInterval !== null ||
      parameters.qtcInterval !== null ||
      parameters.axis !== null ||
      parameters.rhythm !== null ||
      parameters.leads.some((lead) => lead.data !== null);

    if (!hasRecognizedEcgMeasurement) {
      logger.warn(
        '[ECGParser] well-formed XML without recognized ECG measurements — refusing to classify as a parsed ECG',
        { fileName: file?.name }
      );
      return {
        success: false,
        error: t18('cardio.cardio_parser_xml_not_ecg'),
        format: 'XML',
      };
    }

    return {
      success: true,
      parameters,
      format: 'XML',
      raw: text
    };

  } catch (error) {
    logger.error('Ошибка парсинга XML:', error);
    return {
      success: false,
      error: t18('cardio.cardio_parser_xml_parse_failed')
    };
  }
};

// Вспомогательная функция для извлечения значений из XML
function extractXMLValue(xmlDoc: Document, tagName: string, attribute: string) {
  const element = xmlDoc.querySelector(tagName);
  if (element) {
    if (attribute) {
      return element.getAttribute(attribute);
    }
    return element.textContent;
  }
  return null;
}

// Извлечение текста из XML
function extractXMLText(xmlDoc: Document, tagName: string) {
  const element = xmlDoc.querySelector(tagName);
  return element ? element.textContent : null;
}

// Извлечение данных отведений
function extractLeads(xmlDoc: Document) {
  const leads: { name: string | null; data: string | null }[] = [];
  const leadElements = xmlDoc.querySelectorAll('lead');

  leadElements.forEach((lead: Element) => {
    leads.push({
      name: lead.getAttribute('name'),
      data: lead.querySelector('digits')?.textContent ?? null
    });
  });

  return leads;
}

// Главная функция парсинга
export const parseECGFile = async (file: File) => {
  const fileName = file.name.toLowerCase();

  if (fileName.endsWith('.scp')) {
    return await parseSCPFile(file);
  } else if (fileName.endsWith('.xml')) {
    return await parseXMLFile(file);
  } else if (fileName.endsWith('.pdf')) {
    // PDF файлы не парсим, только отображаем
    return {
      success: true,
      parameters: null,
      format: 'PDF',
      message: t18('cardio.cardio_parser_pdf_view_only')
    };
  } else {
    return {
      success: false,
      error: t18('cardio.cardio_parser_unsupported_format')
    };
  }
};

// Анализ параметров ЭКГ
export const analyzeECGParameters = (parameters: Record<string, unknown>) => {
  const findings: string[] = [];
  const alerts: string[] = [];

  if (!parameters) return { findings, alerts };

  // Анализ ЧСС
  // ECGPARSER-FE-002 (audit 3886 round 25): отсутствующая/нечисловая ЧСС —
  // это явное «не измерено», а не молчаливая «нормальная ЧСС». Старый код
  // делал parseInt(parameters.heartRate): parseInt(null) === NaN не
  // проходил ни одну проверку диапазона и попадал в безусловный else.
  const hr = toFiniteNumber(parameters.heartRate);
  if (hr === null) {
    findings.push(t18('cardio.cardio_parser_hr_not_measured'));
  } else if (hr > 100) {
    findings.push(t18('cardio.cardio_parser_tachycardia'));
    if (hr > 150) alerts.push(t18('cardio.cardio_parser_severe_tachycardia'));
  } else if (hr < 60) {
    findings.push(t18('cardio.cardio_parser_bradycardia'));
    if (hr < 40) alerts.push(t18('cardio.cardio_parser_severe_bradycardia'));
  } else {
    findings.push(t18('cardio.cardio_parser_normal_hr'));
  }

  // Анализ интервала PR (строгая числовая валидация: '120bad' больше не
  // принимается как измерение — ECGPARSER-FE-002)
  const pr = toFiniteNumber(parameters.prInterval);
  if (pr !== null) {
    if (pr > 200) {
      findings.push(t18('cardio.cardio_parser_pr_prolonged'));
      if (pr > 300) alerts.push(t18('cardio.cardio_parser_av_block'));
    } else if (pr < 120) {
      findings.push(t18('cardio.cardio_parser_pr_short'));
      alerts.push(t18('cardio.cardio_parser_wpw_possible'));
    }
  }

  // Анализ QRS (ECGPARSER-FE-002: классификация только по строгим числам)
  const qrs = toFiniteNumber(parameters.qrsInterval);
  if (qrs !== null) {
    if (qrs > 120) {
      findings.push(t18('cardio.cardio_parser_qrs_wide'));
      alerts.push(t18('cardio.cardio_parser_bundle_branch_block'));
    } else if (qrs < 80) {
      findings.push(t18('cardio.cardio_parser_qrs_narrow'));
    }
  }

  // Анализ QT (QT и QTc остаются раздельными источниками)
  const qt = toFiniteNumber(parameters.qtInterval);
  const qtc = toFiniteNumber(parameters.qtcInterval);

  if (qtc !== null || qt !== null) {
    if ((qtc !== null && qtc > 450) || (qt !== null && qt > 450)) {
      findings.push(t18('cardio.cardio_parser_qt_prolonged'));
      if ((qtc !== null && qtc > 500) || (qt !== null && qt > 500)) {
        alerts.push(t18('cardio.cardio_parser_qt_critical'));
      }
    } else if ((qtc !== null && qtc < 340) || (qt !== null && qt < 340)) {
      findings.push(t18('cardio.cardio_parser_qt_short'));
    }
  }

  // Анализ электрической оси
  // ECGPARSER-FE-002: неопределённая ось — явное «не измерено», а не
  // «нормальное положение ЭОС» (NaN-ветка старого кода).
  const axis = toFiniteNumber(parameters.axis);
  if (axis === null) {
    findings.push(t18('cardio.cardio_parser_axis_not_measured'));
  } else if (axis < -30) {
    findings.push(t18('cardio.cardio_parser_axis_left'));
  } else if (axis > 90) {
    findings.push(t18('cardio.cardio_parser_axis_right'));
  } else {
    findings.push(t18('cardio.cardio_parser_axis_normal'));
  }

  return {
    findings,
    alerts,
    summary: generateSummary(findings, alerts)
  };
};

// Генерация текстового заключения
function generateSummary(findings: string[], alerts: string[]) {
  let summary = t18('cardio.cardio_parser_analysis_prefix');

  if (alerts.length > 0) {
    summary += t18('cardio.cardio_parser_attention_prefix') + alerts.join('. ') + '. ';
  }

  if (findings.length > 0) {
    summary += t18('cardio.cardio_parser_findings_prefix') + findings.join(', ') + '.';
  } else {
    summary += t18('cardio.cardio_parser_normal_params');
  }

  return summary;
}

// Экспорт параметров в структурированный формат
export const exportECGParameters = (parameters: Record<string, unknown>) => {
  return {
    basic: {
      heartRate: parameters.heartRate,
      rhythm: parameters.rhythm || t18('cardio.cardio_parser_sinus_rhythm')
    },
    intervals: {
      pr: parameters.prInterval,
      qrs: parameters.qrsInterval,
      qt: parameters.qtInterval,
      qtc: parameters.qtcInterval
    },
    axis: {
      // RETRO-3972-01 (post-merge review 4000): the P-wave axis is its own
      // measurement — an absent (undefined/null) or legally measured-0 P
      // axis must never be silently relabeled as the QRS axis. `??` (not
      // `||`): 0° is a measured axis, not an absence.
      p: parameters.pAxis ?? null,
      // `axis` IS the QRS axis (ECGPARSER-FE-003 contract); the explicit
      // qrsAxis key stays accepted for callers that pass it, also 0-safe.
      qrs: parameters.qrsAxis ?? parameters.axis ?? null,
      t: parameters.tAxis
    },
    interpretation: parameters.interpretation,
    recordingDate: parameters.recordingDate
  } as Record<string, unknown>;
};

export default {
  parseECGFile,
  parseSCPFile,
  parseXMLFile,
  analyzeECGParameters,
  exportECGParameters
};