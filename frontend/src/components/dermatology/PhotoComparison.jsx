/**
 * Photo Comparison Component
 * Сравнение фото до/после с слайдером
 * Согласно MASTER_TODO_LIST строка 266
 */
import React, { useState, useRef, useEffect } from 'react';
import { 
  Box,
  Card,
  CardContent,
  Typography,
  Slider,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
  Paper,
  Tooltip,
} from '@mui/material';
import {
  CompareArrows,
  SwapHoriz,
  Fullscreen,
  ZoomIn, 
  ZoomOut,
  RestartAlt,
  ViewColumn,
  ViewStream,
} from '@mui/icons-material';

const PhotoComparison = ({ beforePhoto, afterPhoto, metadata = {} }) => {
  const [sliderPosition, setSliderPosition] = useState(50);
  const [viewMode, setViewMode] = useState('slider'); // slider, side-by-side, overlay
  const [zoom, setZoom] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(0);

  // Обновление размера контейнера
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Обработка перетаскивания слайдера
  const handleMouseDown = (e) => {
    setIsDragging(true);
    updateSliderPosition(e);
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      updateSliderPosition(e);
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const updateSliderPosition = (e) => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const percentage = (x / rect.width) * 100;
      setSliderPosition(Math.max(0, Math.min(100, percentage)));
    }
  };

  // Обработка касаний для мобильных
  const handleTouchStart = (e) => {
    setIsDragging(true);
    updateSliderPositionTouch(e);
  };

  const handleTouchMove = (e) => {
    if (isDragging) {
      updateSliderPositionTouch(e);
    }
  };

  const updateSliderPositionTouch = (e) => {
    if (containerRef.current && e.touches.length > 0) {
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.touches[0].clientX - rect.left;
      const percentage = (x / rect.width) * 100;
      setSliderPosition(Math.max(0, Math.min(100, percentage)));
    }
  };

  // Зум функции
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.25, 0.5));
  };

  const handleResetZoom = () => {
    setZoom(1);
    setSliderPosition(50);
  };

  // Полноэкранный режим
  const handleFullscreen = () => {
    if (containerRef.current) {
      if (containerRef.current.requestFullscreen) {
        containerRef.current.requestFullscreen();
      }
    }
  };

  if (!beforePhoto || !afterPhoto) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body1" color="text.secondary" align="center">
            Для сравнения необходимы фото до и после процедуры
          </Typography>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            <CompareArrows sx={{ mr: 1, verticalAlign: 'middle' }} />
            Сравнение результатов
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {/* Режим отображения */}
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={(e, newMode) => newMode && setViewMode(newMode)}
              size="small"
            >
              <ToggleButton value="slider">
                <Tooltip title="Слайдер">
                  <SwapHoriz />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="side-by-side">
                <Tooltip title="Рядом">
                  <ViewColumn />
                </Tooltip>
              </ToggleButton>
              <ToggleButton value="overlay">
                <Tooltip title="Наложение">
                  <ViewStream />
                </Tooltip>
              </ToggleButton>
            </ToggleButtonGroup>
            
            {/* Зум контролы */}
            <IconButton onClick={handleZoomOut} size="small">
              <ZoomOut />
            </IconButton>
            <Chip label={`${Math.round(zoom * 100)}%`} size="small" />
            <IconButton onClick={handleZoomIn} size="small">
              <ZoomIn />
            </IconButton>
            <IconButton onClick={handleResetZoom} size="small">
              <RestartAlt />
            </IconButton>
            <IconButton onClick={handleFullscreen} size="small">
              <Fullscreen />
            </IconButton>
          </Box>
        </Box>

        {/* Метаданные */}
        {metadata.zone && (
          <Box sx={{ mb: 2 }}>
            <Chip label={`Зона: ${metadata.zone}`} size="small" sx={{ mr: 1 }} />
            <Chip label={`Ракурс: ${metadata.angle || 'front'}`} size="small" sx={{ mr: 1 }} />
            <Chip label={`Освещение: ${metadata.lighting || 'natural'}`} size="small" />
          </Box>
        )}

        {/* Режим слайдера */}
        {viewMode === 'slider' && (
          <Box
            ref={containerRef}
            sx={{
              position: 'relative',
              width: '100%',
              height: '500px',
              overflow: 'hidden',
              cursor: isDragging ? 'grabbing' : 'grab',
              userSelect: 'none',
            }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleMouseUp}
          >
            {/* Фото ПОСЛЕ (нижний слой) */}
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                overflow: 'hidden',
              }}
            >
              <img
                src={afterPhoto}
                alt="После"
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'contain',
                  transform: `scale(${zoom})`,
                  transition: isDragging ? 'none' : 'transform 0.3s ease',
                }}
              />
            </Box>
            
            {/* Фото ДО (верхний слой с обрезкой) */}
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: `${sliderPosition}%`,
                height: '100%',
                overflow: 'hidden',
                borderRight: '2px solid white',
              }}
            >
              <img
                src={beforePhoto}
                alt="До"
                style={{
                  width: containerWidth || '100%',
                  height: '100%',
                  objectFit: 'contain',
                  transform: `scale(${zoom})`,
                  transition: isDragging ? 'none' : 'transform 0.3s ease',
                }}
              />
            </Box>
            
            {/* Слайдер-разделитель */}
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: `${sliderPosition}%`,
                width: '40px',
                height: '100%',
                marginLeft: '-20px',
                cursor: 'ew-resize',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Paper
                sx={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'white',
                  boxShadow: 3,
                }}
              >
                <SwapHoriz />
              </Paper>
            </Box>
            
            {/* Метки */}
            <Typography
              sx={{
                position: 'absolute',
                top: 10,
                left: 10,
                bgcolor: 'rgba(0,0,0,0.7)',
                color: 'white',
                px: 1,
                py: 0.5,
                borderRadius: 1,
                fontSize: '0.875rem',
              }}
            >
              ДО
            </Typography>
            <Typography
              sx={{
                position: 'absolute',
                top: 10,
                right: 10,
                bgcolor: 'rgba(0,0,0,0.7)',
                color: 'white',
                px: 1,
                py: 0.5,
                borderRadius: 1,
                fontSize: '0.875rem',
              }}
            >
              ПОСЛЕ
            </Typography>
          </Box>
        )}

        {/* Режим рядом */}
        {viewMode === 'side-by-side' && (
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2" align="center" gutterBottom>
                ДО
              </Typography>
              <Box sx={{ position: 'relative', overflow: 'hidden', height: '400px' }}>
                <img
                  src={beforePhoto}
                    alt="До"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    transform: `scale(${zoom})`,
                    transition: 'transform 0.3s ease',
                  }}
                />
              </Box>
            </Box>
            
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2" align="center" gutterBottom>
                ПОСЛЕ
              </Typography>
              <Box sx={{ position: 'relative', overflow: 'hidden', height: '400px' }}>
                <img
                  src={afterPhoto}
                    alt="После"
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    transform: `scale(${zoom})`,
                    transition: 'transform 0.3s ease',
                  }}
                />
              </Box>
            </Box>
          </Box>
        )}

        {/* Режим наложения */}
        {viewMode === 'overlay' && (
          <Box sx={{ position: 'relative', height: '500px', overflow: 'hidden' }}>
            <img
              src={beforePhoto}
                    alt="До"
              style={{
                position: 'absolute',
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                opacity: 1 - sliderPosition / 100,
                transform: `scale(${zoom})`,
                transition: 'transform 0.3s ease',
              }}
            />
            <img
              src={afterPhoto}
              alt="После"
              style={{
                position: 'absolute',
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                opacity: sliderPosition / 100,
                transform: `scale(${zoom})`,
                transition: 'transform 0.3s ease',
              }}
            />
            
            <Box sx={{ position: 'absolute', bottom: 20, left: 20, right: 20 }}>
              <Typography variant="caption" color="white" gutterBottom>
                Прозрачность
              </Typography>
              <Slider
                value={sliderPosition}
                onChange={(e, value) => setSliderPosition(value)}
                sx={{
                  color: 'white',
                  '& .MuiSlider-thumb': {
                    bgcolor: 'white',
                  },
                }}
              />
            </Box>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default PhotoComparison;