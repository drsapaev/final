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
  Button,
  Badge,
} from '../ui/macos';
import {
  ArrowLeftRight,
  RotateCcw,
  Fullscreen,
  ZoomIn, 
  ZoomOut,
  RefreshCw,
  Columns,
  Layout,
} from 'lucide-react';

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
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">
            <ArrowLeftRight style={{ marginRight: 8, verticalAlign: 'middle' }} />
            Сравнение результатов
          </Typography>
          
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {/* Режим отображения */}
            <div style={{ display: 'flex', border: '1px solid var(--mac-border)', borderRadius: 8, overflow: 'hidden' }}>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'slider' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'slider' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
                onClick={() => setViewMode('slider')}
                title="Слайдер"
              >
                <ArrowLeftRight style={{ width: 16, height: 16 }} />
              </button>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'side-by-side' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'side-by-side' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
                onClick={() => setViewMode('side-by-side')}
                title="Рядом"
              >
                <Columns style={{ width: 16, height: 16 }} />
              </button>
              <button
                style={{
                  padding: '8px 12px',
                  border: 'none',
                  background: viewMode === 'overlay' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: viewMode === 'overlay' ? 'white' : 'var(--mac-text-primary)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
                onClick={() => setViewMode('overlay')}
                title="Наложение"
              >
                <Layout style={{ width: 16, height: 16 }} />
              </button>
            </div>
            
            {/* Зум контролы */}
            <button
              onClick={handleZoomOut}
              style={{
                padding: '8px',
                border: '1px solid var(--mac-border)',
                borderRadius: 4,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ZoomOut style={{ width: 16, height: 16 }} />
            </button>
            <Badge variant="info">{Math.round(zoom * 100)}%</Badge>
            <button
              onClick={handleZoomIn}
              style={{
                padding: '8px',
                border: '1px solid var(--mac-border)',
                borderRadius: 4,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ZoomIn style={{ width: 16, height: 16 }} />
            </button>
            <button
              onClick={handleResetZoom}
              style={{
                padding: '8px',
                border: '1px solid var(--mac-border)',
                borderRadius: 4,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <RefreshCw style={{ width: 16, height: 16 }} />
            </button>
            <button
              onClick={handleFullscreen}
              style={{
                padding: '8px',
                border: '1px solid var(--mac-border)',
                borderRadius: 4,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Fullscreen style={{ width: 16, height: 16 }} />
            </button>
          </div>
        </div>

        {/* Метаданные */}
        {metadata.zone && (
          <div style={{ marginBottom: 16 }}>
            <Badge variant="info" style={{ marginRight: 8 }}>
              Зона: {metadata.zone}
            </Badge>
            <Badge variant="info" style={{ marginRight: 8 }}>
              Ракурс: {metadata.angle || 'front'}
            </Badge>
            <Badge variant="info" style={{ marginRight: 8 }}>
              Освещение: {metadata.lighting || 'natural'}
            </Badge>
          </div>
        )}

        {/* Режим слайдера */}
        {viewMode === 'slider' && (
          <div
            ref={containerRef}
            style={{
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
            <div
              style={{
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
            </div>
            
            {/* Фото ДО (верхний слой с обрезкой) */}
            <div
              style={{
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
            </div>
            
            {/* Слайдер-разделитель */}
            <div
              style={{
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
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: 'white',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                }}
              >
                <ArrowLeftRight style={{ width: 20, height: 20 }} />
              </div>
            </div>
            
            {/* Метки */}
            <div style={{
              position: 'absolute',
              top: 10,
              left: 10,
              backgroundColor: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: 4,
              fontSize: '14px',
            }}>
              ДО
            </div>
            <div style={{
              position: 'absolute',
              top: 10,
              right: 10,
              backgroundColor: 'rgba(0,0,0,0.7)',
              color: 'white',
              padding: '4px 8px',
              borderRadius: 4,
              fontSize: '14px',
            }}>
              ПОСЛЕ
            </div>
          </div>
        )}

        {/* Режим рядом */}
        {viewMode === 'side-by-side' && (
          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Typography variant="subtitle2" style={{ textAlign: 'center', marginBottom: 8 }}>
                ДО
              </Typography>
              <div style={{ position: 'relative', overflow: 'hidden', height: '400px' }}>
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
              </div>
            </div>
            
            <div style={{ flex: 1 }}>
              <Typography variant="subtitle2" style={{ textAlign: 'center', marginBottom: 8 }}>
                ПОСЛЕ
              </Typography>
              <div style={{ position: 'relative', overflow: 'hidden', height: '400px' }}>
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
              </div>
            </div>
          </div>
        )}

        {/* Режим наложения */}
        {viewMode === 'overlay' && (
          <div style={{ position: 'relative', height: '500px', overflow: 'hidden' }}>
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
            
            <div style={{ position: 'absolute', bottom: 20, left: 20, right: 20 }}>
              <Typography variant="caption" color="white" style={{ marginBottom: 8, display: 'block' }}>
                Прозрачность
              </Typography>
              <input
                type="range"
                min="0"
                max="100"
                value={sliderPosition}
                onChange={(e) => setSliderPosition(Number(e.target.value))}
                style={{
                  width: '100%',
                  height: '4px',
                  borderRadius: '2px',
                  background: 'rgba(255,255,255,0.3)',
                  outline: 'none',
                  appearance: 'none',
                }}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default PhotoComparison;

