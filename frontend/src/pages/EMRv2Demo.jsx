/**
 * EMR v2 Demo Page
 * 
 * Test page for EMR v2 components with MOCK ICD-10 data
 * Route: /emr-v2-demo
 */

import { useState, useCallback } from 'react';
import {
  EMRContainerV2,
  useEMRVersion } from
'../components/emr-v2';

import ICD10Autocomplete from '../components/emr/ICD10Autocomplete';

// Mock ICD-10 database for demo
const MOCK_ICD10_CODES = [
{ code: 'I10', name: 'Эссенциальная [первичная] гипертензия', confidence: 0.95 },
{ code: 'I11', name: 'Гипертензивная болезнь сердца', confidence: 0.9 },
{ code: 'I12', name: 'Гипертензивная болезнь почек', confidence: 0.85 },
{ code: 'I25', name: 'Хроническая ишемическая болезнь сердца', confidence: 0.8 },
{ code: 'J06', name: 'ОРВИ верхних дыхательных путей', confidence: 0.9 },
{ code: 'J18', name: 'Пневмония без уточнения возбудителя', confidence: 0.85 },
{ code: 'J45', name: 'Бронхиальная астма', confidence: 0.8 },
{ code: 'K29', name: 'Гастрит и дуоденит', confidence: 0.9 },
{ code: 'K80', name: 'Желчнокаменная болезнь', confidence: 0.85 },
{ code: 'E11', name: 'Сахарный диабет 2 типа', confidence: 0.9 },
{ code: 'E78', name: 'Нарушения обмена липопротеидов', confidence: 0.8 },
{ code: 'M54', name: 'Дорсалгия', confidence: 0.85 },
{ code: 'N18', name: 'Хроническая болезнь почек', confidence: 0.8 },
{ code: 'G43', name: 'Мигрень', confidence: 0.75 },
{ code: 'F32', name: 'Депрессивный эпизод', confidence: 0.7 }];


/**
 * ICD10 Autocomplete wrapper with mock data for demo
 */
const MockICD10Autocomplete = (props) => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = useCallback((query) => {
    setLoading(true);

    // Simulate API delay
    setTimeout(() => {
      const lowerQuery = query.toLowerCase();
      const filtered = MOCK_ICD10_CODES.filter(
        (code) =>
        code.code.toLowerCase().includes(lowerQuery) ||
        code.name.toLowerCase().includes(lowerQuery)
      );
      setSuggestions(filtered);
      setLoading(false);
    }, 200);
  }, []);

  return (
    <ICD10Autocomplete
      {...props}
      suggestions={suggestions}
      loading={loading}
      onSearch={handleSearch} />);


};

const EMRv2Demo = () => {
  const [visitId] = useState(1); // Demo visit ID
  const [patientId] = useState(1); // Demo patient ID

  // Check feature flags
  void useEMRVersion(1); // user ID 1

  return (
    <div>
            {/* 
        💡 Demo с mock ICD-10 данными:
        1. Начните вводить в поле МКБ-10 (например: I10, J06, K29)
        2. Выберите диагноз из списка
        3. Кнопка "📜 Мой опыт" появится в секции Лечение
               📌 Чтобы протестировать "Мой опыт":
        - Подпишите EMR с лечением → шаблон сохранится
        - Создайте новый EMR с тем же кодом → увидите свой шаблон
        */
      }
            <div style={{
        background: '#e3f2fd',
        padding: '12px 16px',
        borderRadius: '8px',
        margin: '8px',
        fontSize: '13px'
      }}>
                <strong>🧪 Demo Mode:</strong> ICD-10 использует mock данные.
                Попробуйте ввести: <code>I10</code>, <code>J06</code>, <code>K29</code>, <code>E11</code>
            </div>
            <EMRContainerV2
        visitId={visitId}
        patientId={patientId}
        ICD10Component={MockICD10Autocomplete} />
      
        </div>);


};

export default EMRv2Demo;