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
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Button,
  ButtonGroup,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import {
  Healing,
  LocalHospital,
  Brightness1,
  CropSquare,
  ChangeHistory,
  Close,
  RemoveCircleOutline,
  Build,
  Psychology,
  Refresh,
  ZoomIn,
  ZoomOut,
} from '@mui/icons-material';

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
    let ToothIcon = Brightness1; // По умолчанию круг (моляры)
    if ([13, 12, 11, 21, 22, 23, 33, 32, 31, 41, 42, 43].includes(toothNumber)) {
      ToothIcon = CropSquare; // Резцы
    } else if ([14, 15, 24, 25, 34, 35, 44, 45].includes(toothNumber)) {
      ToothIcon = ChangeHistory; // Премоляры
    }
    
    return (
      <Tooltip
        key={toothNumber}
        title={
          <Box>
            <Typography variant="caption">Зуб №{toothNumber}</Typography>
            <Typography variant="caption" display="block">
              Статус: {STATUS_NAMES[status]}
            </Typography>
            {toothData.note && (
              <Typography variant="caption" display="block">
                {toothData.note}
              </Typography>
            )}
          </Box>
        }
      >
        <IconButton
          onClick={() => handleToothClick(toothNumber)}
          sx={{
            color: STATUS_COLORS[status],
            border: isSelected ? '2px solid' : 'none',
            borderColor: 'primary.main',
            transform: `scale(${zoom})`,
            transition: 'all 0.2s',
            '&:hover': {
              transform: `scale(${zoom * 1.2})`,
            },
          }}
          disabled={readOnly && !onToothClick}
        >
          {status === TOOTH_STATUS.MISSING ? (
            <Close />
          ) : status === TOOTH_STATUS.IMPLANT ? (
            <Build />
          ) : status === TOOTH_STATUS.ROOT ? (
            <RemoveCircleOutline />
          ) : (
            <ToothIcon fontSize="large" />
          )}
        </IconButton>
      </Tooltip>
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
            <LocalHospital sx={{ mr: 1, verticalAlign: 'middle' }} />
            Зубная карта
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {/* Режим просмотра */}
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(e, newMode) => newMode && setViewMode(newMode)}
              size="small"
            >
              <ToggleButton value="adult">
                Постоянные
              </ToggleButton>
              <ToggleButton value="child">
                Молочные
              </ToggleButton>
            </ToggleButtonGroup>
            
            {/* Масштаб */}
            <ButtonGroup size="small">
              <Button onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}>
                <ZoomOut />
              </Button>
              <Button onClick={() => setZoom(Math.min(2, zoom + 0.1))}>
                <ZoomIn />
              </Button>
            </ButtonGroup>
            
            {!readOnly && (
              <Button
                size="small"
                startIcon={<Refresh />}
                onClick={handleClearAll}
              >
                Очистить
              </Button>
            )}
          </Box>
        </Box>

        {/* Инструменты выбора статуса */}
        {!readOnly && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>
              Выберите состояние для отметки:
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {Object.entries(STATUS_NAMES).map(([status, name]) => (
                <Chip
                  key={status}
                  label={name}
                  onClick={() => setSelectedStatus(status)}
                  sx={{
                    bgcolor: selectedStatus === status ? STATUS_COLORS[status] : 'transparent',
                    color: selectedStatus === status ? 'white' : STATUS_COLORS[status],
                    border: `2px solid ${STATUS_COLORS[status]}`,
                    '&:hover': {
                      bgcolor: STATUS_COLORS[status],
                      color: 'white',
                    },
                  }}
                />
              ))}
            </Box>
          </Box>
        )}

        {/* Зубная карта */}
        <Paper sx={{ p: 3, bgcolor: 'background.default' }}>
          <Box sx={{ position: 'relative' }}>
            {/* Верхняя челюсть */}
            <Box sx={{ mb: 4 }}>
              <Typography variant="caption" align="center" display="block" sx={{ mb: 1 }}>
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
            </Box>

            {/* Линия между челюстями */}
            <Box sx={{ height: '2px', bgcolor: 'divider', my: 2 }} />

            {/* Нижняя челюсть */}
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
                {/* Правая сторона (4 квадрант) */}
                <Box>
                  {renderTeethRow(currentTeeth.lowerRight, true)}
                </Box>
                
                {/* Разделитель */}
                <Box sx={{ width: '1px', bgcolor: 'divider', mx: 1 }} />
                
                {/* Левая сторона (3 квадрант) */}
                <Box>
                  {renderTeethRow(currentTeeth.lowerLeft)}
                </Box>
              </Box>
              
              <Typography variant="caption" align="center" display="block" sx={{ mt: 1 }}>
                Нижняя челюсть
              </Typography>
            </Box>
          </Box>
        </Paper>

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
                <Chip
                  key={status}
                  label={`${STATUS_NAMES[status]}: ${count}`}
                  size="small"
                  sx={{
                    bgcolor: STATUS_COLORS[status],
                    color: 'white',
                  }}
                />
              ))}
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default TeethChart;

