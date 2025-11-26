/**
 * Teeth Chart Component
 * Интерактивная зубная карта
 * Согласно MASTER_TODO_LIST строка 284
 */
import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Badge,
} from '../ui/macos';
import {
  Heart,
  Hospital,
  Circle,
  Square,
  Triangle,
  X,
  Minus,
  Wrench,
  Brain,
  RefreshCw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';

// Статусы зубов
const TOOTH_STATUS = {
  HEALTHY: 'healthy',
  CARIES: 'caries',
  FILLED: 'filled',
  CROWN: 'crown',
  IMPLANT: 'implant',
  MISSING: 'missing',
  ROOT: 'root',
  BRIDGE: 'bridge',
};

// Цвета для статусов
const STATUS_COLORS = {
  [TOOTH_STATUS.HEALTHY]: '#4caf50',
  [TOOTH_STATUS.CARIES]: '#f44336',
  [TOOTH_STATUS.FILLED]: '#2196f3',
  [TOOTH_STATUS.CROWN]: '#ff9800',
  [TOOTH_STATUS.IMPLANT]: '#9c27b0',
  [TOOTH_STATUS.MISSING]: '#9e9e9e',
  [TOOTH_STATUS.ROOT]: '#795548',
  [TOOTH_STATUS.BRIDGE]: '#00bcd4',
};

// Названия статусов
const STATUS_NAMES = {
  [TOOTH_STATUS.HEALTHY]: 'Здоров',
  [TOOTH_STATUS.CARIES]: 'Кариес',
  [TOOTH_STATUS.FILLED]: 'Пломба',
  [TOOTH_STATUS.CROWN]: 'Коронка',
  [TOOTH_STATUS.IMPLANT]: 'Имплант',
  [TOOTH_STATUS.MISSING]: 'Отсутствует',
  [TOOTH_STATUS.ROOT]: 'Корень',
  [TOOTH_STATUS.BRIDGE]: 'Мост',
};

// Нумерация зубов по FDI (международная)
const TEETH_NUMBERS = {
  upperRight: [18, 17, 16, 15, 14, 13, 12, 11],
  upperLeft: [21, 22, 23, 24, 25, 26, 27, 28],
  lowerLeft: [38, 37, 36, 35, 34, 33, 32, 31],
  lowerRight: [41, 42, 43, 44, 45, 46, 47, 48],
};

// Молочные зубы
const DECIDUOUS_TEETH = {
  upperRight: [55, 54, 53, 52, 51],
  upperLeft: [61, 62, 63, 64, 65],
  lowerLeft: [75, 74, 73, 72, 71],
  lowerRight: [81, 82, 83, 84, 85],
};

const TeethChart = ({ onToothClick, initialData = {}, readOnly = false }) => {
  const [teethData, setTeethData] = useState(initialData);
  const [selectedTooth, setSelectedTooth] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState(TOOTH_STATUS.CARIES);
  const [viewMode, setViewMode] = useState('adult'); // adult, child
  const [zoom, setZoom] = useState(1);

  // Обработка клика по зубу
  const handleToothClick = (toothNumber) => {
    if (readOnly) {
      onToothClick && onToothClick(toothNumber, teethData[toothNumber]);
      return;
    }

    setSelectedTooth(toothNumber);
    
    // Обновляем статус зуба
    const newData = {
      ...teethData,
      [toothNumber]: {
        ...teethData[toothNumber],
        status: selectedStatus,
        updatedAt: new Date().toISOString(),
      },
    };
    
    setTeethData(newData);
    onToothClick && onToothClick(toothNumber, newData[toothNumber]);
  };

  // Очистить все данные
  const handleClearAll = () => {
    setTeethData({});
    setSelectedTooth(null);
  };

  // Отрисовка одного зуба
  const renderTooth = (toothNumber, position) => {
    const toothData = teethData[toothNumber] || { status: TOOTH_STATUS.HEALTHY };
    const isSelected = selectedTooth === toothNumber;
    const status = toothData.status || TOOTH_STATUS.HEALTHY;
    
    // Определяем форму зуба
    let ToothIcon = Circle; // По умолчанию круг (моляры)
    if ([13, 12, 11, 21, 22, 23, 33, 32, 31, 41, 42, 43].includes(toothNumber)) {
      ToothIcon = Square; // Резцы
    } else if ([14, 15, 24, 25, 34, 35, 44, 45].includes(toothNumber)) {
      ToothIcon = Triangle; // Премоляры
    }
    
    return (
      <div
        key={toothNumber}
        title={`Зуб №${toothNumber} • ${STATUS_NAMES[status]}`}
      >
        <button
          onClick={() => handleToothClick(toothNumber)}
          style={{
            color: STATUS_COLORS[status],
            border: isSelected ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
            transform: `scale(${zoom})`,
            transition: 'transform 0.2s',
            background: 'transparent',
            width: 28,
            height: 28,
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer'
          }}
          disabled={readOnly && !onToothClick}
        >
          {status === TOOTH_STATUS.MISSING ? (
            <X />
          ) : status === TOOTH_STATUS.IMPLANT ? (
            <Wrench />
          ) : status === TOOTH_STATUS.ROOT ? (
            <Minus />
          ) : (
            <ToothIcon />
          )}
        </button>
      </div>
    );
  };

  // Отрисовка ряда зубов
  const renderTeethRow = (teeth, reverse = false) => {
    const teethToRender = reverse ? [...teeth].reverse() : teeth;
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
        {teethToRender.map((toothNumber) => renderTooth(toothNumber))}
      </Box>
    );
  };

  const currentTeeth = viewMode === 'adult' ? TEETH_NUMBERS : DECIDUOUS_TEETH;

  return (
    <Card>
      <CardContent>
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            <Hospital style={{ marginRight: 8, verticalAlign: 'middle' }} />
            Зубная карта
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {/* Режим просмотра */}
            {/* Режим отображения */}
            <div style={{ display: 'flex', border: '1px solid var(--mac-border)', borderRadius: 8, overflow: 'hidden' }}>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'adult' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'adult' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                }}
                onClick={() => setViewMode('adult')}
              >
                Постоянные
              </button>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'child' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'child' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                }}
                onClick={() => setViewMode('child')}
              >
                Молочные
              </button>
            </div>
            
            {/* Масштаб */}
            <div style={{ display: 'flex', border: '1px solid var(--mac-border)', borderRadius: 8, overflow: 'hidden' }}>
              <button
                onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <ZoomOut style={{ width: 16, height: 16 }} />
              </button>
              <button
                onClick={() => setZoom(Math.min(2, zoom + 0.1))}
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <ZoomIn style={{ width: 16, height: 16 }} />
              </button>
            </div>
            
            {!readOnly && (
              <Button
                variant="outline"
                onClick={handleClearAll}
              >
                <RefreshCw style={{ width: 16, height: 16, marginRight: 8 }} />
                Очистить
              </Button>
            )}
          </Box>
        </Box>

        {/* Инструменты выбора статуса */}
        {!readOnly && (
          <div style={{ marginBottom: 24 }}>
            <Typography variant="subtitle2" style={{ marginBottom: 8 }}>
              Выберите состояние для отметки:
            </Typography>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.entries(STATUS_NAMES).map(([status, name]) => (
                <Badge
                  key={status}
                  variant={selectedStatus === status ? 'primary' : 'info'}
                  style={{
                    backgroundColor: selectedStatus === status ? STATUS_COLORS[status] : 'transparent',
                    color: selectedStatus === status ? 'white' : STATUS_COLORS[status],
                    border: `2px solid ${STATUS_COLORS[status]}`,
                    cursor: 'pointer',
                    padding: '8px 12px',
                    borderRadius: 4,
                  }}
                  onClick={() => setSelectedStatus(status)}
                >
                  {name}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Зубная карта */}
        <div style={{ padding: 24, backgroundColor: 'var(--mac-bg-primary)', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
          <div style={{ position: 'relative' }}>
            {/* Верхняя челюсть */}
            <div style={{ marginBottom: 32 }}>
              <Typography variant="caption" style={{ textAlign: 'center', display: 'block', marginBottom: 8 }}>
                Верхняя челюсть
              </Typography>
              
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
                {/* Правая сторона (1 квадрант) */}
                <Box>
                  <Typography variant="caption" align="center" display="block">
                    Правая
                  </Typography>
                  {renderTeethRow(currentTeeth.upperRight, true)}
                </Box>
                
                {/* Разделитель */}
                <Box sx={{ width: '1px', bgcolor: 'divider', mx: 1 }} />
                
                {/* Левая сторона (2 квадрант) */}
                <Box>
                  <Typography variant="caption" align="center" display="block">
                    Левая
                  </Typography>
                  {renderTeethRow(currentTeeth.upperLeft)}
                </Box>
              </Box>
              {/* Закрываем внутренние боксы верхней челюсти */}
              
            </div>

            {/* Линия между челюстями */}
            <Box sx={{ height: '2px', bgcolor: 'divider', my: 2 }} />

            {/* Нижняя челюсть */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
                {/* Правая сторона (4 квадрант) */}
                <div>
                  {renderTeethRow(currentTeeth.lowerRight, true)}
                </div>
                
                {/* Разделитель */}
                <div style={{ width: 1, backgroundColor: 'var(--mac-border)', margin: '0 8px' }} />
                
                {/* Левая сторона (3 квадрант) */}
                <div>
                  {renderTeethRow(currentTeeth.lowerLeft)}
                </div>
              </div>
              
              <Typography variant="caption" align="center" display="block" sx={{ mt: 1 }}>
                Нижняя челюсть
              </Typography>
            </div>
          </div>
        </div>

        {/* Легенда */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Обозначения:
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {Object.entries(STATUS_NAMES).map(([status, name]) => (
              <Box key={status} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box
                  sx={{
                    width: 20,
                    height: 20,
                    bgcolor: STATUS_COLORS[status],
                    borderRadius: '50%',
                  }}
                />
                <Typography variant="caption">{name}</Typography>
              </Box>
            ))}
          </Box>
        </Box>

        {/* Статистика */}
        {Object.keys(teethData).length > 0 && (
          <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              Статистика:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
              {Object.entries(
                Object.values(teethData).reduce((acc, tooth) => {
                  const status = tooth.status || TOOTH_STATUS.HEALTHY;
                  acc[status] = (acc[status] || 0) + 1;
                  return acc;
                }, {})
              ).map(([status, count]) => (
                <Badge key={status} variant="info" style={{
                  backgroundColor: STATUS_COLORS[status],
                  color: 'white',
                  padding: '4px 8px',
                  borderRadius: 6
                }}>
                  {`${STATUS_NAMES[status]}: ${count}`}
                </Badge>
              ))}
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default TeethChart;

