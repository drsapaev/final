/**
 * Echo Form Component
 * Форма для ввода результатов ЭхоКГ
 * Согласно MASTER_TODO_LIST строка 248
 */
import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Alert,
  Checkbox,
  Input,
  Textarea,
} from '../ui/macos';
import {
  Heart,
  BarChart3,
  Save,
  ChevronDown,
  ChevronRight,
  Upload,
  Sparkles,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const EchoForm = ({ patientId, visitId, onSave, initialData = null }) => {
  const [echoData, setEchoData] = useState({
    // Левый желудочек
    leftVentricle: {
      edd: '', // КДР
      esd: '', // КСР
      ef: '',  // ФВ
      fs: '',  // ФС
      ivs: '', // МЖП
      pw: '',  // ЗС
    },
    // Правый желудочек
    rightVentricle: {
      rvdd: '', // КДР ПЖ
      rvot: '', // ВТ ПЖ
    },
    // Предсердия
    atria: {
      la: '', // ЛП
      ra: '', // ПП
    },
    // Клапаны
    valves: {
      mitral: {
        e: '',
        a: '',
        e_a: '',
        decel_time: '',
      },
      tricuspid: {
        e: '',
        a: '',
        e_a: '',
      },
      aortic: {
        peak_velocity: '',
        mean_gradient: '',
        ava: '',
      },
      pulmonary: {
        peak_velocity: '',
        mean_gradient: '',
      },
    },
    // Дополнительные параметры
    additional: {
      pericardium: '',
      aorta: '',
      comments: '',
    },
    // Заключение
    conclusion: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    leftVentricle: true,
    rightVentricle: false,
    atria: false,
    valves: false,
    additional: false,
  });

  useEffect(() => {
    if (initialData) {
      setEchoData(initialData);
    }
  }, [initialData]);

  const handleChange = (section, field, value) => {
    setEchoData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }));
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError('');
      
      const response = await api.post('/cardiology/echo-results', {
        patient_id: patientId,
        visit_id: visitId,
        echo_data: echoData
      });

      if (response.status === 200) {
        setSuccess('Результаты ЭхоКГ сохранены успешно');
        if (onSave) {
          onSave(response.data);
        }
      }
    } catch (err) {
      setError('Ошибка при сохранении результатов ЭхоКГ');
      logger.error('Echo form save error:', err);
    } finally {
      setLoading(false);
    }
  };

  const renderSection = (title, section, fields, expanded) => (
    <div style={{ marginBottom: 24 }}>
      <div 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          padding: '12px 16px',
          backgroundColor: 'var(--mac-bg-secondary)',
          border: '1px solid var(--mac-border)',
          borderRadius: '8px',
          cursor: 'pointer'
        }}
        onClick={() => toggleSection(section)}
      >
        <Typography variant="subtitle1" style={{ fontWeight: 500 }}>
          {title}
        </Typography>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {expanded ? <ChevronDown style={{ width: 16, height: 16 }} /> : <ChevronRight style={{ width: 16, height: 16 }} />}
        </div>
      </div>
      
      {expanded && (
        <div style={{ padding: 16, marginTop: 8, border: '1px solid var(--mac-border)', borderRadius: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {fields.map(field => (
              <div key={field.key}>
                <Input
                  label={field.label}
                  value={echoData[section][field.key]}
                  onChange={(e) => handleChange(section, field.key, e.target.value)}
                  placeholder={field.placeholder}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  return (
    <Card>
      <CardContent>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <Typography variant="h6">
            <Heart style={{ marginRight: 8, verticalAlign: 'middle' }} />
            Результаты ЭхоКГ
          </Typography>
          
          <div style={{ display: 'flex', gap: 8 }}>
            <Button
              variant="outline"
              onClick={() => {/* AI анализ */}}
            >
              <Sparkles style={{ width: 16, height: 16, marginRight: 8 }} />
              AI Анализ
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={loading}
            >
              <Save style={{ width: 16, height: 16, marginRight: 8 }} />
              Сохранить
            </Button>
          </div>
        </div>

        {error && (
          <Alert severity="error" style={{ marginBottom: 16 }}>
            <AlertTriangle style={{ width: 16, height: 16, marginRight: 8 }} />
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" style={{ marginBottom: 16 }}>
            <CheckCircle style={{ width: 16, height: 16, marginRight: 8 }} />
            {success}
          </Alert>
        )}

        {/* Левый желудочек */}
        {renderSection(
          'Левый желудочек',
          'leftVentricle',
          [
            { key: 'edd', label: 'КДР', placeholder: 'Норма: 35-55 мм' },
            { key: 'esd', label: 'КСР', placeholder: 'Норма: 20-35 мм' },
            { key: 'ef', label: 'ФВ', placeholder: 'Норма: 55-75%' },
            { key: 'fs', label: 'ФС', placeholder: 'Норма: 28-45%' },
            { key: 'ivs', label: 'МЖП', placeholder: 'Норма: 6-11 мм' },
            { key: 'pw', label: 'ЗС', placeholder: 'Норма: 6-11 мм' },
          ],
          expandedSections.leftVentricle
        )}

        {/* Правый желудочек */}
        {renderSection(
          'Правый желудочек',
          'rightVentricle',
          [
            { key: 'rvdd', label: 'КДР ПЖ', placeholder: 'Норма: 19-28 мм' },
            { key: 'rvot', label: 'ВТ ПЖ', placeholder: 'Норма: 19-28 мм' },
          ],
          expandedSections.rightVentricle
        )}

        {/* Предсердия */}
        {renderSection(
          'Предсердия',
          'atria',
          [
            { key: 'la', label: 'ЛП', placeholder: 'Норма: 19-40 мм' },
            { key: 'ra', label: 'ПП', placeholder: 'Норма: 19-40 мм' },
          ],
          expandedSections.atria
        )}

        {/* Клапаны */}
        {renderSection(
          'Клапаны',
          'valves',
          [
            { key: 'mitral.e', label: 'Митральный клапан E', placeholder: 'Норма: 0.6-1.3 м/с' },
            { key: 'mitral.a', label: 'Митральный клапан A', placeholder: 'Норма: 0.4-0.8 м/с' },
            { key: 'aortic.peak_velocity', label: 'Аортальный клапан', placeholder: 'Норма: 1.0-1.7 м/с' },
            { key: 'tricuspid.e', label: 'Трехстворчатый клапан E', placeholder: 'Норма: 0.3-0.7 м/с' },
          ],
          expandedSections.valves
        )}

        {/* Дополнительные параметры */}
        {renderSection(
          'Дополнительные параметры',
          'additional',
          [
            { key: 'pericardium', label: 'Перикард', placeholder: 'Описание состояния перикарда' },
            { key: 'aorta', label: 'Аорта', placeholder: 'Описание состояния аорты' },
          ],
          expandedSections.additional
        )}

        {/* Комментарии */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            Комментарии
          </Typography>
          <Textarea
            value={echoData.additional.comments}
            onChange={(e) => handleChange('additional', 'comments', e.target.value)}
            placeholder="Дополнительные замечания и наблюдения..."
            rows={4}
          />
        </div>

        {/* Заключение */}
        <div style={{ marginTop: 24 }}>
          <Typography variant="subtitle1" style={{ marginBottom: 8 }}>
            Заключение
          </Typography>
          <Textarea
            value={echoData.conclusion}
            onChange={(e) => setEchoData(prev => ({ ...prev, conclusion: e.target.value }))}
            placeholder="Заключение по результатам ЭхоКГ..."
            rows={6}
          />
        </div>
      </CardContent>
    </Card>
  );
};

export default EchoForm;