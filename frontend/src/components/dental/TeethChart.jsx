/**
 * Teeth Chart Component
 * Интерактивная зубная карта
 * Согласно MASTER_TODO_LIST строка 284
 *
 * H6 fix: status / color / label / FDI-number constants now imported
 * from dentalConstants.js (SSOT) instead of being redefined here.
 */
import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Badge,
} from '../ui/macos';
import {

  Hospital,
  Circle,
  Square,
  Triangle,
  X,
  Minus,
  Wrench,

  RefreshCw,
  ZoomIn,
  ZoomOut } from
'lucide-react';
import PropTypes from 'prop-types';
import {
  TOOTH_STATUS,
  TOOTH_STATUS_COLORS as STATUS_COLORS,
  TOOTH_STATUS_LABELS as STATUS_NAMES,
  ADULT_TEETH as TEETH_NUMBERS,
  DECIDUOUS_TEETH,
} from './dentalConstants';
import { useTranslation } from '../../i18n/useTranslation';

const TeethChart = ({ onToothClick, initialData = {}, readOnly = false }) => {
  const { t } = useTranslation();
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
        updatedAt: new Date().toISOString()
      }
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
  const renderTooth = (toothNumber) => {
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
        title={t('dental.dental_tc_tooth_title', { toothNumber, status: STATUS_NAMES[status] })}>
        
        <button
          onClick={() => handleToothClick(toothNumber)}
          aria-label={t('dental.dental_tc_tooth_aria', { toothNumber, status: STATUS_NAMES[status] })}
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
          disabled={readOnly && !onToothClick}>
          
          {status === TOOTH_STATUS.MISSING ?
          <X /> :
          status === TOOTH_STATUS.IMPLANT ?
          <Wrench /> :
          status === TOOTH_STATUS.ROOT ?
          <Minus /> :

          <ToothIcon />
          }
        </button>
      </div>);

  };

  // Отрисовка ряда зубов
  const renderTeethRow = (teeth, reverse = false) => {
    const teethToRender = reverse ? [...teeth].reverse() : teeth;
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
        {teethToRender.map((toothNumber) => renderTooth(toothNumber))}
      </Box>);

  };

  const currentTeeth = viewMode === 'adult' ? TEETH_NUMBERS : DECIDUOUS_TEETH;

  return (
    <Card>
      <CardContent>
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            <Hospital style={{ marginRight: 8, verticalAlign: 'middle' }} />
            {t('dental.dental_tc_chart_title')}
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
                  cursor: 'pointer'
                }}
                onClick={() => setViewMode('adult')}>
                
                {t('dental.dental_tc_adult')}
              </button>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'child' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'child' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer'
                }}
                onClick={() => setViewMode('child')}>
                
                {t('dental.dental_tc_deciduous')}
              </button>
            </div>
            
            {/* Масштаб */}
            <div style={{ display: 'flex', border: '1px solid var(--mac-border)', borderRadius: 8, overflow: 'hidden' }}>
              <button
                onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}
                aria-label={t('dental.dental_tc_aria_zoom_out')}
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                
                <ZoomOut style={{ width: 16, height: 16 }} />
              </button>
              <button
                onClick={() => setZoom(Math.min(2, zoom + 0.1))}
                aria-label={t('dental.dental_tc_aria_zoom_in')}
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                
                <ZoomIn style={{ width: 16, height: 16 }} />
              </button>
            </div>
            
            {!readOnly &&
            <Button
              variant="outline"
              onClick={handleClearAll}>
              
                <RefreshCw style={{ width: 16, height: 16, marginRight: 8 }} />
                {t('dental.dental_tc_btn_clear')}
              </Button>
            }
          </Box>
        </Box>

        {/* Инструменты выбора статуса */}
        {!readOnly &&
        <div style={{ marginBottom: 24 }}>
            <Typography variant="subtitle2" style={{ marginBottom: 8 }}>
              {t('dental.dental_tc_status_prompt')}
            </Typography>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {Object.entries(STATUS_NAMES).map(([status, name]) =>
            <Badge
              key={status}
              variant={selectedStatus === status ? 'primary' : 'info'}
              style={{
                backgroundColor: selectedStatus === status ? STATUS_COLORS[status] : 'transparent',
                color: selectedStatus === status ? 'white' : STATUS_COLORS[status],
                border: `2px solid ${STATUS_COLORS[status]}`,
                cursor: 'pointer',
                padding: '8px 12px',
                borderRadius: 4
              }}
              onClick={() => setSelectedStatus(status)}>
              
                  {name}
                </Badge>
            )}
            </div>
          </div>
        }

        {/* Зубная карта */}
        <div style={{ padding: 24, backgroundColor: 'var(--mac-bg-primary)', border: '1px solid var(--mac-border)', borderRadius: 8 }}>
          <div style={{ position: 'relative' }}>
            {/* Верхняя челюсть */}
            <div style={{ marginBottom: 32 }}>
              <Typography variant="caption" style={{ textAlign: 'center', display: 'block', marginBottom: 8 }}>
                {t('dental.dental_tc_upper_jaw')}
              </Typography>
              
              <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
                {/* Правая сторона (1 квадрант) */}
                <Box>
                  <Typography variant="caption" align="center" display="block">
                    {t('dental.dental_tc_right_side')}
                  </Typography>
                  {renderTeethRow(currentTeeth.upperRight, true)}
                </Box>
                
                {/* Разделитель */}
                <Box sx={{ width: '1px', bgcolor: 'divider', mx: 1 }} />
                
                {/* Левая сторона (2 квадрант) */}
                <Box>
                  <Typography variant="caption" align="center" display="block">
                    {t('dental.dental_tc_left_side')}
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
                {t('dental.dental_tc_lower_jaw')}
              </Typography>
            </div>
          </div>
        </div>

        {/* Легенда */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('dental.dental_tc_legend_title')}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            {Object.entries(STATUS_NAMES).map(([status, name]) =>
            <Box key={status} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box
                sx={{
                  width: 20,
                  height: 20,
                  bgcolor: STATUS_COLORS[status],
                  borderRadius: '50%'
                }} />
              
                <Typography variant="caption">{name}</Typography>
              </Box>
            )}
          </Box>
        </Box>

        {/* Статистика */}
        {Object.keys(teethData).length > 0 &&
        <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>
              {t('dental.dental_tc_stats_title')}
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
              {Object.entries(
              Object.values(teethData).reduce((acc, tooth) => {
                const status = tooth.status || TOOTH_STATUS.HEALTHY;
                acc[status] = (acc[status] || 0) + 1;
                return acc;
              }, {})
            ).map(([status, count]) =>
            <Badge key={status} variant="info" style={{
              backgroundColor: STATUS_COLORS[status],
              color: 'white',
              padding: '4px 8px',
              borderRadius: 6
            }}>
                  {`${STATUS_NAMES[status]}: ${count}`}
                </Badge>
            )}
            </Box>
          </Box>
        }
      </CardContent>
    </Card>);

};


TeethChart.propTypes = {
  ...(TeethChart.propTypes || {}),
  initialData: PropTypes.any,
  onToothClick: PropTypes.any,
  readOnly: PropTypes.any,
};

export default TeethChart;
