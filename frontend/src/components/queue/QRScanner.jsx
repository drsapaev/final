import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Alert,
  IconButton,
  Paper
} from '@mui/material';
import {
  QrCodeScanner as ScanIcon,
  Close as CloseIcon,
  CameraAlt as CameraIcon,
  FlashOn as FlashOnIcon,
  FlashOff as FlashOffIcon
} from '@mui/icons-material';

const QRScanner = ({ open, onClose, onScan }) => {
  const [error, setError] = useState('');
  const [hasCamera, setHasCamera] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [flashOn, setFlashOn] = useState(false);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (open) {
      startCamera();
    } else {
      stopCamera();
    }
    
    return () => stopCamera();
  }, [open]);

  const startCamera = async () => {
    try {
      setError('');
      
      // Проверяем поддержку камеры
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setError('Камера не поддерживается в этом браузере');
        return;
      }

      const constraints = {
        video: {
          facingMode: 'environment', // Задняя камера
          width: { ideal: 640 },
          height: { ideal: 480 }
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      streamRef.current = stream;
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setHasCamera(true);
        setIsScanning(true);
        
        // Начинаем сканирование
        startScanning();
      }
    } catch (err) {
      console.error('Ошибка доступа к камере:', err);
      setError('Не удалось получить доступ к камере. Проверьте разрешения.');
      setHasCamera(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsScanning(false);
    setHasCamera(false);
  };

  const startScanning = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    const scan = () => {
      if (!isScanning || !video.videoWidth || !video.videoHeight) {
        if (isScanning) {
          requestAnimationFrame(scan);
        }
        return;
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      try {
        // Здесь должна быть логика распознавания QR кода
        // Для демонстрации используем простую проверку
        const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
        
        // В реальном приложении здесь был бы QR код сканер
        // Например, используя библиотеку jsQR или qr-scanner
        
        // Симуляция успешного сканирования (для демо)
        // В реальности это будет результат от QR сканера
        
      } catch (err) {
        console.error('Ошибка сканирования:', err);
      }

      if (isScanning) {
        requestAnimationFrame(scan);
      }
    };

    video.addEventListener('loadedmetadata', () => {
      scan();
    });

    if (video.readyState >= video.HAVE_METADATA) {
      scan();
    }
  };

  const toggleFlash = async () => {
    if (!streamRef.current) return;

    try {
      const track = streamRef.current.getVideoTracks()[0];
      const capabilities = track.getCapabilities();
      
      if (capabilities.torch) {
        await track.applyConstraints({
          advanced: [{ torch: !flashOn }]
        });
        setFlashOn(!flashOn);
      }
    } catch (err) {
      console.error('Ошибка управления вспышкой:', err);
    }
  };

  const handleManualInput = () => {
    // Для демонстрации - симуляция сканирования QR кода
    const mockQRData = "test-token-from-qr";
    onScan(mockQRData);
    onClose();
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="sm" 
      fullWidth
      PaperProps={{
        sx: { minHeight: '70vh' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">Сканирование QR кода</Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ textAlign: 'center' }}>
          {hasCamera ? (
            <Box>
              <Paper 
                elevation={3} 
                sx={{ 
                  position: 'relative', 
                  display: 'inline-block',
                  borderRadius: 2,
                  overflow: 'hidden'
                }}
              >
                <video
                  ref={videoRef}
                  style={{
                    width: '100%',
                    maxWidth: '400px',
                    height: 'auto',
                    display: 'block'
                  }}
                  playsInline
                  muted
                />
                
                {/* Overlay для прицела */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: '200px',
                    height: '200px',
                    border: '2px solid #fff',
                    borderRadius: '8px',
                    boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)',
                    pointerEvents: 'none'
                  }}
                />

                {/* Кнопки управления */}
                <Box
                  sx={{
                    position: 'absolute',
                    bottom: 16,
                    right: 16,
                    display: 'flex',
                    gap: 1
                  }}
                >
                  <IconButton
                    onClick={toggleFlash}
                    sx={{ 
                      bgcolor: 'rgba(0, 0, 0, 0.6)', 
                      color: 'white',
                      '&:hover': { bgcolor: 'rgba(0, 0, 0, 0.8)' }
                    }}
                  >
                    {flashOn ? <FlashOffIcon /> : <FlashOnIcon />}
                  </IconButton>
                </Box>
              </Paper>

              <canvas
                ref={canvasRef}
                style={{ display: 'none' }}
              />

              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                Наведите камеру на QR код для сканирования
              </Typography>
            </Box>
          ) : (
            <Box sx={{ py: 4 }}>
              <CameraIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Камера недоступна
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Не удалось получить доступ к камере или она не поддерживается
              </Typography>
              
              <Button
                variant="outlined"
                onClick={startCamera}
                startIcon={<ScanIcon />}
              >
                Попробовать снова
              </Button>
            </Box>
          )}
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>
          Отмена
        </Button>
        <Button 
          onClick={handleManualInput}
          variant="contained"
          startIcon={<ScanIcon />}
        >
          Тестовое сканирование
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default QRScanner;
