/**
 * Lab Results Manager Component
 * Управление результатами лабораторных исследований
 * Согласно MASTER_TODO_LIST строка 287
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Input,
  Alert,
  Badge,
  Select,
  Option,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Progress,
} from '../ui/macos';
import {
  TestTube,
  X,
  Plus,
  Edit,
  Trash2,

  Download,
  Upload,

  Send,



  TrendingUp,
  TrendingDown,

  Microscope,
  Hospital,
  Brain } from
'lucide-react';
import { api } from '../../api/client';
import { AIButton, AIAssistant } from '../ai';

import notify from '../../services/notify';
import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import PropTypes from 'prop-types';
// Категории анализов
const LAB_CATEGORIES = {
  blood: { name: 'Анализы крови', icon: <TestTube style={{ color: 'var(--mac-accent-red)' }} /> },
  urine: { name: 'Анализы мочи', icon: <TestTube style={{ color: 'var(--mac-accent-orange)' }} /> },
  biochemistry: { name: 'Биохимия', icon: <Microscope style={{ color: 'var(--mac-accent-blue)' }} /> },
  hormones: { name: 'Гормоны', icon: <Hospital style={{ color: 'var(--mac-accent-purple)' }} /> },
  other: { name: 'Другие', icon: <TestTube /> }
};

// P-02 fix: вычисление возраста из birth_date для проброса в AI.
// Если birth_date невалидна или пациент не указал — возвращаем null
// и AI-кнопка блокируется (см. handleOpenAIAnalysis).
function calculateAgeFromBirthDate(birthDate) {
  if (!birthDate) return null;
  const birth = new Date(birthDate);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const monthDiff = now.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < birth.getDate())) {
    age -= 1;
  }
  return age >= 0 && age < 130 ? age : null;
}

// Нормализация пола: backend хранит M|F|X, AI ожидает male|female|other
function normalizeSexForAI(sex) {
  if (!sex) return null;
  const s = String(sex).trim().toUpperCase();
  if (s === 'M' || s === 'MALE') return 'male';
  if (s === 'F' || s === 'FEMALE') return 'female';
  return 'other';
}

// Статусы результатов
const RESULT_STATUS = {
  pending: { label: 'Ожидается', color: 'warning' },
  in_progress: { label: 'В работе', color: 'info' },
  completed: { label: 'Готов', color: 'success' },
  abnormal: { label: 'Отклонения', color: 'error' }
};

const tabButtonClassName = (isActive) => `theme-tab-button${isActive ? ' theme-tab-button--active' : ''}`;

// QW-6 fix: inline-валидация числовых полей формы результата.
// Раньше value, reference_min, reference_max принимали любой текст —
// пользователь мог ввести "выше нормы" в числовое поле и сохранить.
// Теперь валидация происходит при вводе, и кнопка «Сохранить» блокируется
// при ошибке. Также проверяется, что min < max.
function isNumericString(value) {
  if (value === '' || value == null) return true; // пустое — допустимо (необязательное поле)
  const num = Number(value);
  return !Number.isNaN(num) && Number.isFinite(num);
}

function validateResultForm(form) {
  const errors = {};

  // value — должно быть числом, если указано
  if (form.value && !isNumericString(form.value)) {
    errors.value = 'Значение должно быть числом';
  }

  // reference_min — должно быть числом, если указано
  if (form.reference_min && !isNumericString(form.reference_min)) {
    errors.reference_min = 'Минимум должен быть числом';
  }

  // reference_max — должно быть числом, если указано
  if (form.reference_max && !isNumericString(form.reference_max)) {
    errors.reference_max = 'Максимум должен быть числом';
  }

  // Если указаны оба — min должен быть < max
  if (
    form.reference_min
    && form.reference_max
    && isNumericString(form.reference_min)
    && isNumericString(form.reference_max)
    && Number(form.reference_min) >= Number(form.reference_max)
  ) {
    errors.reference_max = 'Максимум должен быть больше минимума';
  }

  return errors;
}

const LabResultsManager = ({ patientId, visitId, onUpdate, patientAge = null, patientGender = null }) => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [activeTab, setActiveTab] = useState('all');
  const [results, setResults] = useState([]);
  const [selectedResult, setSelectedResult] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [uploadDialog, setUploadDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showAIAnalysis, setShowAIAnalysis] = useState(false);
  const [, setAiAnalysisResults] = useState(null);
  // P-08 fix: выбор конкретных результатов для отправки пациенту.
  // Раньше sendToPatient отправлял ВСЕ результаты визита — включая
  // незавершённые. Теперь пользователь явно выбирает чекбоксами.
  const [selectedResultIds, setSelectedResultIds] = useState(new Set());
  // P-02 fix: данные пациента, загружаемые по patientId, если возраст/пол
  // не переданы через props. Без них AI-анализ блокируется, чтобы не
  // интерпретировать результаты с захардкоженными значениями.
  const [patientProfile, setPatientProfile] = useState(null);
  const [patientProfileLoading, setPatientProfileLoading] = useState(false);
  const [aiBlockedReason, setAiBlockedReason] = useState('');

  // Форма результата
  const [resultForm, setResultForm] = useState({
    test_name: '',
    category: 'blood',
    value: '',
    unit: '',
    reference_min: '',
    reference_max: '',
    status: 'pending',
    notes: '',
    performed_date: new Date().toISOString().split('T')[0]
  });

  const loadResults = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`/visits/${visitId}/lab-results`);
      setResults(response.data || []);
    } catch (error) {
      logger.error('Ошибка загрузки результатов:', error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [visitId]);

  // P-02 fix: загрузка профиля пациента, чтобы получить birth_date и sex
  // для AI-интерпретации. Используется только если возраст/пол не переданы
  // через props (prop patientAge/patientGender имеют приоритет — позволяют
  // родительскому компоненту передать уже известные данные без доп. запроса).
  useEffect(() => {
    if (!patientId) {
      setPatientProfile(null);
      return;
    }
    // Если возраст/пол уже переданы через props — запрос не нужен
    if (patientAge != null && patientGender) {
      setPatientProfile(null);
      return;
    }
    let cancelled = false;
    setPatientProfileLoading(true);
    api.get(`/patients/${patientId}`)
      .then((response) => {
        if (cancelled) return;
        setPatientProfile(response?.data || response || null);
      })
      .catch((error) => {
        if (cancelled) return;
        logger.error('Не удалось загрузить профиль пациента для AI-анализа:', error);
        setPatientProfile(null);
      })
      .finally(() => {
        if (!cancelled) setPatientProfileLoading(false);
      });
    return () => { cancelled = true; };
  }, [patientId, patientAge, patientGender]);

  // P-02 fix: вычисляем финальные возраст/пол с приоритетом props над загруженным профилем.
  const resolvedPatientAge = patientAge ??
    (patientProfile?.birth_date ? calculateAgeFromBirthDate(patientProfile.birth_date) : null);
  const resolvedPatientGender = patientGender ??
    normalizeSexForAI(patientProfile?.sex);

  // P-02 fix: AI-анализ блокируется, если нет возраста или пола.
  // Референсные интервалы многих анализов (гемоглобин, креатинин, гормоны)
  // зависят от этих параметров — интерпретация с заглушкой опасна.
  useEffect(() => {
    if (patientProfileLoading) {
      setAiBlockedReason('Загрузка данных пациента…');
      return;
    }
    if (resolvedPatientAge == null) {
      setAiBlockedReason(
        'AI-анализ недоступен: не указана дата рождения пациента. ' +
        'Заполните профиль пациента и повторите попытку.'
      );
      return;
    }
    if (!resolvedPatientGender) {
      setAiBlockedReason(
        'AI-анализ недоступен: не указан пол пациента. ' +
        'Референсные интервалы зависят от пола — интерпретация невозможна.'
      );
      return;
    }
    setAiBlockedReason('');
  }, [patientProfileLoading, resolvedPatientAge, resolvedPatientGender]);

  // P-02 fix: открытие AI-диалога с явной блокировкой при отсутствии данных.
  // Раньше кнопка была активна и передавала patientId ? 35 : null —
  // то есть AI получал захардкоженный возраст для любого пациента.
  const handleOpenAIAnalysis = () => {
    if (results.length === 0) return;
    if (resolvedPatientAge == null || !resolvedPatientGender) {
      notify.error?.(aiBlockedReason || 'AI-анализ недоступен: проверьте данные пациента');
      return;
    }
    setShowAIAnalysis(true);
  };

  // Загрузка результатов
  useEffect(() => {
    if (visitId) {
      loadResults();
    }
  }, [visitId, loadResults]);

  // Фильтрация результатов
  const filteredResults = activeTab === 'all' ?
  results :
  results.filter((r) => r.category === activeTab);

  // QW-6 fix: производное состояние ошибок валидации формы.
  // Пересчитывается при каждом изменении resultForm.
  const formErrors = validateResultForm(resultForm);
  const hasFormErrors = Object.keys(formErrors).length > 0;

  // Подсчет по категориям
  const getCategoryCount = (category) => {
    return results.filter((r) => r.category === category).length;
  };

  // Определение статуса по значению
  const determineStatus = (value, min, max) => {
    const numValue = parseFloat(value);
    const numMin = parseFloat(min);
    const numMax = parseFloat(max);

    if (isNaN(numValue) || isNaN(numMin) || isNaN(numMax)) {
      return 'completed';
    }

    if (numValue < numMin || numValue > numMax) {
      return 'abnormal';
    }

    return 'completed';
  };

  // Сохранение результата
  const handleSaveResult = async () => {
    // QW-6 fix: блокируем сохранение при ошибках валидации.
    if (hasFormErrors) {
      notify.error?.('Проверьте корректность числовых полей');
      return;
    }
    try {
      const status = determineStatus(
        resultForm.value,
        resultForm.reference_min,
        resultForm.reference_max
      );

      const dataToSave = {
        ...resultForm,
        status,
        visit_id: visitId,
        patient_id: patientId
      };

      if (selectedResult) {
        await api.put(`/lab-results/${selectedResult.id}`, dataToSave);
      } else {
        await api.post('/lab-results', dataToSave);
      }

      loadResults();
      setDialogOpen(false);
      resetForm();
      onUpdate && onUpdate();

    } catch (error) {
      logger.error('Ошибка сохранения результата:', error);
    }
  };

  // Удаление результата
  const handleDeleteResult = async (resultId) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление результата',
      message: 'Удалить результат?',
      description: 'Это действие необратимо.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) return;

    try {
      await api.delete(`/lab-results/${resultId}`);
      loadResults();
      onUpdate && onUpdate();
    } catch (error) {
      logger.error('Ошибка удаления результата:', error);
    }
  };

  // Загрузка файла с результатами
  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('visit_id', visitId);
    formData.append('patient_id', patientId);

    try {
      setLoading(true);
      const response = await api.post('/lab-results/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.results) {
        setResults((prev) => [...prev, ...response.data.results]);
      }

      setUploadDialog(false);
      onUpdate && onUpdate();

    } catch (error) {
      logger.error('Ошибка загрузки файла:', error);
    } finally {
      setLoading(false);
    }
  };

  // Экспорт в PDF
  const exportToPDF = async () => {
    let url = null;
    try {
      const response = await api.get(`/visits/${visitId}/lab-results/pdf`, {
        responseType: 'blob'
      });

      url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `lab_results_${visitId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      logger.error('Ошибка экспорта PDF:', error);
    } finally {
      // P-07 fix: явно освобождаем object URL, чтобы избежать memory leak
      // при каждом экспорте. Раньше URL.createObjectURL вызывался, но
      // revokeObjectURL — никогда. При повторных экспортах в длинной
      // сессии память утекала по ~размеру PDF на каждый клик.
      if (url) {
        window.URL.revokeObjectURL(url);
      }
    }
  };

  // P-08 fix: отправка пациенту только выбранных результатов.
  // Раньше отправлялись ВСЕ результаты визита без возможности выбора,
  // что могло привести к отправке незавершённых или неподтверждённых данных.
  // Теперь: если ничего не выбрано — спрашиваем подтверждение «Отправить все?»;
  // если выбраны — отправляем только их и показываем явный список в подтверждении.
  const toggleResultSelection = (resultId) => {
    setSelectedResultIds((prev) => {
      const next = new Set(prev);
      if (next.has(resultId)) {
        next.delete(resultId);
      } else {
        next.add(resultId);
      }
      return next;
    });
  };

  const sendToPatient = async () => {
    const selectedIds = Array.from(selectedResultIds);
    const sendingAll = selectedIds.length === 0;
    const selectedResults = sendingAll
      ? results
      : results.filter((r) => selectedResultIds.has(r.id));

    if (selectedResults.length === 0) {
      notify.error('Нет результатов для отправки');
      return;
    }

    // P-08 fix: явное подтверждение с количеством и составом.
    const listPreview = selectedResults
      .slice(0, 5)
      .map((r) => `• ${r.test_name}: ${r.value} ${r.unit || ''}`)
      .join('\n');
    const moreNote = selectedResults.length > 5
      ? `\n…и ещё ${selectedResults.length - 5}`
      : '';

    const ok = await confirm({
      title: 'Отправка результатов пациенту',
      message: `Будет отправлено в Telegram: ${selectedResults.length} ${selectedResults.length === 1 ? 'результат' : 'результатов'}.`,
      description: `${listPreview}${moreNote}\n\nКанал: Telegram\nОтменить отправку после доставки невозможно.`,
      confirmLabel: 'Отправить',
      cancelLabel: 'Отмена',
      intent: 'primary',
    });
    if (!ok) return;

    try {
      await api.post(`/patients/${patientId}/send-lab-results`, {
        visit_id: visitId,
        method: 'telegram',
        // P-08 fix: явно передаём выбранные ID. Если ничего не выбрано —
        // backend получит пустой массив и (по контракту useLabResults)
        // отправит все результаты визита. Это поведение сохранено для
        // обратной совместимости, но теперь это осознанный выбор пользователя.
        result_ids: selectedIds,
      });

      notify.success(
        `Отправлено в Telegram: ${selectedResults.length} ${selectedResults.length === 1 ? 'результат' : 'результатов'}`
      );
      // Сбрасываем выбор после успешной отправки
      setSelectedResultIds(new Set());
    } catch (error) {
      logger.error('Ошибка отправки результатов:', error);
      notify.error(
        error?.response?.data?.detail || error?.message || 'Не удалось отправить результаты'
      );
    }
  };

  // Сброс формы
  const resetForm = () => {
    setResultForm({
      test_name: '',
      category: 'blood',
      value: '',
      unit: '',
      reference_min: '',
      reference_max: '',
      status: 'pending',
      notes: '',
      performed_date: new Date().toISOString().split('T')[0]
    });
    setSelectedResult(null);
  };

  // Отображение значения с индикатором
  const renderValue = (result) => {
    const isAbnormal = result.status === 'abnormal';
    const value = parseFloat(result.value);
    const min = parseFloat(result.reference_min);
    const max = parseFloat(result.reference_max);

    let trend = null;
    if (!isNaN(value) && !isNaN(min) && !isNaN(max)) {
      if (value < min) trend = 'low';else
      if (value > max) trend = 'high';
    }

    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="body2" color={isAbnormal ? 'error' : 'text.primary'}>
          {result.value} {result.unit}
        </Typography>
        {trend === 'low' && <TrendingDown color="error" fontSize="small" />}
        {trend === 'high' && <TrendingUp color="error" fontSize="small" />}
      </Box>);

  };

  return (
    <Box>
      <Card>
        <CardContent>
          <Box style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <Typography variant="h6">
              <TestTube style={{ marginRight: 8, verticalAlign: 'middle' }} />
              Лабораторные исследования
            </Typography>
            
            <Box style={{ display: 'flex', gap: 8 }}>
              <Button size="small" onClick={() => setDialogOpen(true)}>
                <Plus style={{ width: 16, height: 16, marginRight: 8 }} />
                Добавить результат
              </Button>
              <Button size="small" onClick={() => setUploadDialog(true)}>
                <Upload style={{ width: 16, height: 16, marginRight: 8 }} />
                Загрузить файл
              </Button>
              <Button size="small" onClick={exportToPDF}>
                <Download style={{ width: 16, height: 16, marginRight: 8 }} />
                Экспорт PDF
              </Button>
              <Button
                size="small"
                onClick={sendToPatient}
                title="Отправить выбранные результаты в Telegram пациенту"
                aria-label="Отправить выбранные результаты в Telegram пациенту"
              >
                <Send style={{ width: 16, height: 16, marginRight: 8 }} />
                Отправить в Telegram
                {/* P-08 fix: badge с количеством выбранных результатов. */}
                {selectedResultIds.size > 0 && (
                  <Badge variant="primary" style={{ marginLeft: 8 }}>
                    {selectedResultIds.size}
                  </Badge>
                )}
              </Button>
              <AIButton
                text="AI Анализ"
                size="small"
                onClick={handleOpenAIAnalysis}
                disabled={results.length === 0 || patientProfileLoading || Boolean(aiBlockedReason)}
                tooltip={aiBlockedReason || (results.length === 0
                  ? 'Нет результатов для анализа'
                  : 'AI интерпретация результатов с учётом возраста и пола пациента')} />
              
            </Box>
          </Box>

          {/* Табы категорий */}
          <div className="theme-tab-strip" style={{ marginBottom: 16 }}>
            <button
              className={tabButtonClassName(activeTab === 'all')}
              onClick={() => setActiveTab('all')}>
              
              Все
              <Badge variant="primary">{results.length}</Badge>
            </button>
            {Object.entries(LAB_CATEGORIES).map(([key, category]) =>
            <button
              key={key}
              className={tabButtonClassName(activeTab === key)}
              onClick={() => setActiveTab(key)}>
              
                {category.icon}
                {category.name}
                <Badge variant="primary">{getCategoryCount(key)}</Badge>
              </button>
            )}
          </div>

          {/* Таблица результатов */}
          {loading ?
          <Progress /> :
          filteredResults.length > 0 ?
          <div className="clinic-ops-table-wrap">
              <table className="clinic-ops-table">
                <thead>
                  <tr>
                    {/* P-08 fix: колонка выбора для отправки пациенту. */}
                    <th style={{ textAlign: 'center', width: '40px' }}>
                      <input
                        type="checkbox"
                        aria-label="Выбрать все результаты для отправки"
                        title="Выбрать все видимые результаты"
                        checked={
                          filteredResults.length > 0 &&
                          filteredResults.every((r) => selectedResultIds.has(r.id))
                        }
                        ref={(el) => {
                          if (el) el.indeterminate =
                            selectedResultIds.size > 0 &&
                            !filteredResults.every((r) => selectedResultIds.has(r.id));
                        }}
                        onChange={(e) => {
                          setSelectedResultIds((prev) => {
                            const next = new Set(prev);
                            if (e.target.checked) {
                              filteredResults.forEach((r) => next.add(r.id));
                            } else {
                              filteredResults.forEach((r) => next.delete(r.id));
                            }
                            return next;
                          });
                        }}
                      />
                    </th>
                    <th style={{ textAlign: 'left' }}>Исследование</th>
                    <th style={{ textAlign: 'left' }}>Результат</th>
                    <th style={{ textAlign: 'left' }}>Норма</th>
                    <th style={{ textAlign: 'left' }}>Статус</th>
                    <th style={{ textAlign: 'left' }}>Дата</th>
                    <th style={{ textAlign: 'right' }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((result) =>
                <tr key={result.id}>
                      <td style={{ textAlign: 'center' }}>
                        {/* P-08 fix: индивидуальный выбор для отправки. */}
                        <input
                          type="checkbox"
                          aria-label={`Выбрать ${result.test_name} для отправки`}
                          checked={selectedResultIds.has(result.id)}
                          onChange={() => toggleResultSelection(result.id)}
                        />
                      </td>
                      <td>
                        <Typography variant="body2" style={{ fontWeight: 500 }}>
                          {result.test_name}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {LAB_CATEGORIES[result.category]?.name}
                        </Typography>
                      </td>
                      
                      <td>{renderValue(result)}</td>
                      
                      <td>
                        <Typography variant="caption">
                          {result.reference_min} - {result.reference_max} {result.unit}
                        </Typography>
                      </td>
                      
                      <td>
                        <Badge
                      variant={RESULT_STATUS[result.status]?.color}>
                      
                          {RESULT_STATUS[result.status]?.label}
                        </Badge>
                      </td>
                      
                      <td>
                        <Typography variant="caption">
                          {new Date(result.performed_date).toLocaleDateString()}
                        </Typography>
                      </td>
                      
                      <td style={{ textAlign: 'right' }}>
                        <Button
                      type="button"
                      size="small"
                      title={`Edit lab result ${result.test_name || result.id}`}
                      aria-label={`Edit lab result ${result.test_name || result.id}`}
                      onClick={() => {
                        setSelectedResult(result);
                        setResultForm(result);
                        setDialogOpen(true);
                      }}>
                      
                          <Edit aria-hidden="true" style={{ width: 16, height: 16 }} />
                        </Button>
                        <Button
                      type="button"
                      size="small"
                      variant="danger"
                      title={`Delete lab result ${result.test_name || result.id}`}
                      aria-label={`Delete lab result ${result.test_name || result.id}`}
                      onClick={() => handleDeleteResult(result.id)}>

                          <Trash2 aria-hidden="true" style={{ width: 16, height: 16 }} />
                        </Button>
                      </td>
                    </tr>
                )}
                </tbody>
              </table>
            </div> :

          <Alert severity="info">
              Нет результатов анализов. Добавьте новый результат или загрузите файл.
            </Alert>
          }

          {/* Сводка по отклонениям */}
          {results.filter((r) => r.status === 'abnormal').length > 0 &&
          <Alert severity="warning" sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Обнаружены отклонения:
              </Typography>
              {results.
            filter((r) => r.status === 'abnormal').
            map((result, index) =>
            <Typography key={index} variant="body2">
                    • {result.test_name}: {result.value} {result.unit} 
                    (норма: {result.reference_min}-{result.reference_max})
                  </Typography>
            )}
            </Alert>
          }
        </CardContent>
      </Card>

      {/* Диалог добавления/редактирования */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedResult ? 'Редактировать результат' : 'Добавить результат'}
        </DialogTitle>
        
        <DialogContent>
          <Box style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '8px' }}>
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 2 }}>
                <Input
                  label="Название исследования"
                  value={resultForm.test_name}
                  onChange={(e) => setResultForm({ ...resultForm, test_name: e.target.value })} />
                
              </Box>
              
              <Box style={{ flex: 1 }}>
                <Select
                  label="Категория"
                  value={resultForm.category}
                  onChange={(e) => setResultForm({ ...resultForm, category: e.target.value })}>
                  
                  {Object.entries(LAB_CATEGORIES).map(([key, category]) =>
                  <Option key={key} value={key}>
                      {category.name}
                    </Option>
                  )}
                </Select>
              </Box>
            </Box>
            
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 2 }}>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  label="Результат"
                  value={resultForm.value}
                  onChange={(e) => setResultForm({ ...resultForm, value: e.target.value })}
                  error={Boolean(formErrors.value)}
                />
                {/* QW-6 fix: inline-сообщение об ошибке под полем. */}
                {formErrors.value && (
                  <Typography variant="caption" color="error" style={{ display: 'block', marginTop: '4px' }}>
                    {formErrors.value}
                  </Typography>
                )}
              </Box>

              <Box style={{ flex: 1 }}>
                <Input
                  label="Ед."
                  value={resultForm.unit}
                  onChange={(e) => setResultForm({ ...resultForm, unit: e.target.value })} />

              </Box>

              <Box style={{ flex: 1 }}>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  label="Мин. норма"
                  value={resultForm.reference_min}
                  onChange={(e) => setResultForm({ ...resultForm, reference_min: e.target.value })}
                  error={Boolean(formErrors.reference_min)}
                />
                {formErrors.reference_min && (
                  <Typography variant="caption" color="error" style={{ display: 'block', marginTop: '4px' }}>
                    {formErrors.reference_min}
                  </Typography>
                )}
              </Box>

              <Box style={{ flex: 1 }}>
                <Input
                  type="number"
                  inputMode="decimal"
                  step="any"
                  label="Макс. норма"
                  value={resultForm.reference_max}
                  onChange={(e) => setResultForm({ ...resultForm, reference_max: e.target.value })}
                  error={Boolean(formErrors.reference_max)}
                />
                {formErrors.reference_max && (
                  <Typography variant="caption" color="error" style={{ display: 'block', marginTop: '4px' }}>
                    {formErrors.reference_max}
                  </Typography>
                )}
              </Box>
            </Box>
            
            <Box style={{ display: 'flex', gap: '16px' }}>
              <Box style={{ flex: 1 }}>
                <Input
                  type="date"
                  label="Дата выполнения"
                  value={resultForm.performed_date}
                  onChange={(e) => setResultForm({ ...resultForm, performed_date: e.target.value })} />
                
              </Box>
            </Box>
            
            <Box>
              <Input
                multiline
                rows={2}
                label="Примечания"
                value={resultForm.notes}
                onChange={(e) => setResultForm({ ...resultForm, notes: e.target.value })} />
              
            </Box>
          </Box>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => {
            setDialogOpen(false);
            resetForm();
          }}>
            Отмена
          </Button>
          <Button variant="contained" onClick={handleSaveResult} disabled={!resultForm.test_name || hasFormErrors}>
            {selectedResult ? 'Сохранить' : 'Добавить'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог загрузки файла */}
      <Dialog open={uploadDialog} onClose={() => setUploadDialog(false)}>
        <DialogTitle>Загрузить файл с результатами</DialogTitle>
        
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            Поддерживаются форматы: PDF, Excel, CSV
          </Alert>
          
          <input
            type="file"
            accept=".pdf,.xlsx,.xls,.csv"
            aria-label="Загрузить файл с результатами лабораторных исследований"
            onChange={handleFileUpload}
            style={{ display: 'none' }}
            id="lab-file-upload" />
          
          
          <label htmlFor="lab-file-upload">
            <Button
              variant="contained"
              component="span"
              fullWidth
              startIcon={<Upload />}>
              
              Выбрать файл
            </Button>
          </label>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={() => setUploadDialog(false)}>
            Закрыть
          </Button>
        </DialogActions>
      </Dialog>

      {/* AI Analysis Dialog */}
      {showAIAnalysis &&
      <Dialog
        open={showAIAnalysis}
        onClose={() => setShowAIAnalysis(false)}
        maxWidth="md"
        fullWidth>
        
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6">
                <Brain style={{ marginRight: 8, verticalAlign: 'middle' }} />
                AI Интерпретация результатов
              </Typography>
              <Button
                type="button"
                size="small"
                title="Close lab AI analysis"
                aria-label="Close lab AI analysis"
                onClick={() => setShowAIAnalysis(false)}>
                <X aria-hidden="true" style={{ width: 16, height: 16 }} />
              </Button>
            </Box>
          </DialogTitle>
          
          <DialogContent>
            {/* P-02 fix: явное отображение данных пациента, на основе которых
                строится AI-интерпретация. Пользователь видит реальные значения
                вместо молчаливого хардкода. */}
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="caption" component="div">
                <strong>Пациент:</strong> {resolvedPatientAge != null ? `${resolvedPatientAge} лет` : 'возраст неизвестен'}
                {', '}
                <strong>Пол:</strong> {resolvedPatientGender
                  ? ({ male: 'мужской', female: 'женский', other: 'другой' }[resolvedPatientGender] || resolvedPatientGender)
                  : 'не указан'}
              </Typography>
            </Alert>
            <AIAssistant
            analysisType="lab"
            data={{
              results: results.map((r) => ({
                name: r.test_name,
                value: r.value,
                unit: r.unit,
                reference: `${r.reference_min}-${r.reference_max}`
              })),
              // P-02 fix: ранее было `patientId ? 35 : null` — хардкод возраста.
              // Теперь передаются реальные значения, проверенные выше.
              patient_age: resolvedPatientAge,
              patient_gender: resolvedPatientGender
            }}
            onResult={(result) => {
              setAiAnalysisResults(result);
            }} />
          
          </DialogContent>
          
          <DialogActions>
            <Button onClick={() => setShowAIAnalysis(false)}>
              Закрыть
            </Button>
          </DialogActions>
        </Dialog>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </Box>);

};


LabResultsManager.propTypes = {
  ...(LabResultsManager.propTypes || {}),
  onUpdate: PropTypes.any,
  patientId: PropTypes.any,
  visitId: PropTypes.any,
  // P-02 fix: опциональные props, позволяющие родителю передать уже известные
  // возраст/пол и избежать лишнего запроса GET /patients/{id}. Если не переданы —
  // компонент загрузит профиль сам. AI блокируется до получения данных.
  patientAge: PropTypes.number,
  patientGender: PropTypes.oneOf(['male', 'female', 'other']),
};

export default LabResultsManager;
