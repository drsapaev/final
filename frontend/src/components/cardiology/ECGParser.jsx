/**
 * ECG Parser Component
 * Парсинг SCP/XML форматов ЭКГ
 * Phase 3: stale MASTER_TODO_LIST reference removed.
 */
import logger from '../../utils/logger';
// Парсер для SCP формата
// C-1 fix: previously this returned hardcoded fake parameters (heartRate: 75,
// prInterval: 160, etc.) regardless of file contents. Those fake values were
// then persisted to cardio_ecg_records via POST /cardio/ecg — a patient-safety
// risk because doctors could make clinical decisions based on fabricated data.
//
// Until a real SCP-ECG library is integrated, we hard-fail: return success=false
// so the caller (ECGViewer.parseECGFileData) shows a clear warning to the doctor
// and does NOT persist fake parameters to the database.
export const parseSCPFile = async (file) => {
  try {
    const buffer = await file.arrayBuffer();

    // Minimal SCP-ECG validation: file must be at least 6 bytes
    // (CRC uint16 + length uint32 header). Files smaller than this are
    // definitely not valid SCP-ECG.
    if (buffer.byteLength < 6) {
      return {
        success: false,
        error: 'Файл слишком мал для SCP-ECG формата (минимум 6 байт)',
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
      error: 'Парсинг SCP-ECG формата не реализован. Загрузите файл в формате XML/HL7 aECG или обратитесь к администратору для интеграции SCP-библиотеки.',
      format: 'SCP',
      raw: buffer,
    };
  } catch (error) {
    logger.error('Ошибка парсинга SCP:', error);
    return {
      success: false,
      error: 'Не удалось прочитать SCP файл',
    };
  }
};

// Парсер для XML формата (HL7 aECG)
export const parseXMLFile = async (file) => {
  try {
    const text = await file.text();
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(text, 'text/xml');

    // Проверяем на ошибки парсинга
    const parserError = xmlDoc.querySelector('parsererror');
    if (parserError) {
      throw new Error('Invalid XML format');
    }

    // Извлекаем параметры из HL7 aECG формата
    const parameters = {
      heartRate: extractXMLValue(xmlDoc, 'heartRate', 'value'),
      prInterval: extractXMLValue(xmlDoc, 'prInterval', 'value'),
      qrsInterval: extractXMLValue(xmlDoc, 'qrsInterval', 'value'),
      qtInterval: extractXMLValue(xmlDoc, 'qtInterval', 'value'),
      qtcInterval: extractXMLValue(xmlDoc, 'qtcInterval', 'value'),
      axis: extractXMLValue(xmlDoc, 'pAxis', 'value'),

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
      error: 'Не удалось распарсить XML файл'
    };
  }
};

// Вспомогательная функция для извлечения значений из XML
function extractXMLValue(xmlDoc, tagName, attribute) {
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
function extractXMLText(xmlDoc, tagName) {
  const element = xmlDoc.querySelector(tagName);
  return element ? element.textContent : null;
}

// Извлечение данных отведений
function extractLeads(xmlDoc) {
  const leads = [];
  const leadElements = xmlDoc.querySelectorAll('lead');

  leadElements.forEach((lead) => {
    leads.push({
      name: lead.getAttribute('name'),
      data: lead.querySelector('digits')?.textContent
    });
  });

  return leads;
}

// Главная функция парсинга
export const parseECGFile = async (file) => {
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
      message: 'PDF файлы можно только просматривать'
    };
  } else {
    return {
      success: false,
      error: 'Неподдерживаемый формат файла'
    };
  }
};

// Анализ параметров ЭКГ
export const analyzeECGParameters = (parameters) => {
  const findings = [];
  const alerts = [];

  if (!parameters) return { findings, alerts };

  // Анализ ЧСС
  const hr = parseInt(parameters.heartRate);
  if (hr > 100) {
    findings.push('Тахикардия');
    if (hr > 150) alerts.push('Выраженная тахикардия');
  } else if (hr < 60) {
    findings.push('Брадикардия');
    if (hr < 40) alerts.push('Выраженная брадикардия');
  } else {
    findings.push('Нормальная ЧСС');
  }

  // Анализ интервала PR
  const pr = parseInt(parameters.prInterval);
  if (pr > 200) {
    findings.push('Удлинение интервала PR');
    if (pr > 300) alerts.push('AV блокада');
  } else if (pr < 120) {
    findings.push('Укорочение интервала PR');
    alerts.push('Возможен синдром WPW');
  }

  // Анализ QRS
  const qrs = parseInt(parameters.qrsInterval);
  if (qrs > 120) {
    findings.push('Расширение комплекса QRS');
    alerts.push('Возможна блокада ножки пучка Гиса');
  } else if (qrs < 80) {
    findings.push('Узкий комплекс QRS');
  }

  // Анализ QT
  const qt = parseInt(parameters.qtInterval);
  const qtc = parseInt(parameters.qtcInterval);

  if (qtc > 450 || qt > 450) {
    findings.push('Удлинение интервала QT');
    if (qtc > 500 || qt > 500) {
      alerts.push('Критическое удлинение QT - риск аритмий');
    }
  } else if (qtc < 340 || qt < 340) {
    findings.push('Укорочение интервала QT');
  }

  // Анализ электрической оси
  const axis = parseInt(parameters.axis);
  if (axis < -30) {
    findings.push('Отклонение ЭОС влево');
  } else if (axis > 90) {
    findings.push('Отклонение ЭОС вправо');
  } else {
    findings.push('Нормальное положение ЭОС');
  }

  return {
    findings,
    alerts,
    summary: generateSummary(findings, alerts)
  };
};

// Генерация текстового заключения
function generateSummary(findings, alerts) {
  let summary = 'ЭКГ анализ: ';

  if (alerts.length > 0) {
    summary += 'ВНИМАНИЕ! ' + alerts.join('. ') + '. ';
  }

  if (findings.length > 0) {
    summary += 'Выявлено: ' + findings.join(', ') + '.';
  } else {
    summary += 'Параметры в пределах нормы.';
  }

  return summary;
}

// Экспорт параметров в структурированный формат
export const exportECGParameters = (parameters) => {
  return {
    basic: {
      heartRate: parameters.heartRate,
      rhythm: parameters.rhythm || 'Синусовый'
    },
    intervals: {
      pr: parameters.prInterval,
      qrs: parameters.qrsInterval,
      qt: parameters.qtInterval,
      qtc: parameters.qtcInterval
    },
    axis: {
      p: parameters.pAxis || parameters.axis,
      qrs: parameters.qrsAxis || parameters.axis,
      t: parameters.tAxis
    },
    interpretation: parameters.interpretation,
    recordingDate: parameters.recordingDate
  };
};

export default {
  parseECGFile,
  parseSCPFile,
  parseXMLFile,
  analyzeECGParameters,
  exportECGParameters
};