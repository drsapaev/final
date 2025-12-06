import React, { useState, useRef, useCallback } from 'react';
import { 
  Mic, 
  MicOff, 
  Play, 
  Pause, 
  Square, 
  Upload, 
  FileText, 
  Brain, 
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  Loader,
  Download,
  Copy,
  Edit3,
  Save,
  RefreshCw,
  Volume2,
  Settings,
  Zap
} from 'lucide-react';
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSBadge,
  MacOSLoadingSkeleton
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

import logger from '../../utils/logger';
const VoiceToText = () => {
  const [activeTab, setActiveTab] = useState('transcription');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  
  // Состояния для записи
  const [isRecording, setIsRecording] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  
  // Состояния для настроек
  const [settings, setSettings] = useState({
    language: 'ru',
    medical_context: true,
    document_type: 'consultation'
  });
  
  // Состояния для текстовых операций
  const [textInput, setTextInput] = useState('');
  const [editableResult, setEditableResult] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  
  // Refs
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const fileInputRef = useRef(null);

  const tabs = [
    { id: 'transcription', label: 'Транскрипция', icon: <Mic className="w-4 h-4" /> },
    { id: 'structuring', label: 'Структурирование', icon: <FileText className="w-4 h-4" /> },
    { id: 'entities', label: 'Извлечение сущностей', icon: <Brain className="w-4 h-4" /> },
    { id: 'summary', label: 'Резюме', icon: <Edit3 className="w-4 h-4" /> },
    { id: 'validation', label: 'Валидация', icon: <CheckCircle className="w-4 h-4" /> }
  ];

  // Функции для записи аудио
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        } 
      });
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(audioBlob);
        setAudioUrl(URL.createObjectURL(audioBlob));
        stream.getTracks().forEach(track => track.stop());
      };
      
      mediaRecorder.start(1000); // Записываем данные каждую секунду
      setIsRecording(true);
      setIsPaused(false);
      
      // Запускаем таймер
      timerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
      
      toast.success('Запись началась');
    } catch (error) {
      logger.error('Ошибка доступа к микрофону:', error);
      toast.error('Не удалось получить доступ к микрофону');
    }
  }, []);

  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      if (isPaused) {
        mediaRecorderRef.current.resume();
        timerRef.current = setInterval(() => {
          setRecordingTime(prev => prev + 1);
        }, 1000);
        setIsPaused(false);
        toast.success('Запись возобновлена');
      } else {
        mediaRecorderRef.current.pause();
        clearInterval(timerRef.current);
        setIsPaused(true);
        toast.success('Запись приостановлена');
      }
    }
  }, [isRecording, isPaused]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      clearInterval(timerRef.current);
      setIsRecording(false);
      setIsPaused(false);
      toast.success('Запись завершена');
    }
  }, [isRecording]);

  const resetRecording = useCallback(() => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingTime(0);
    setResult(null);
    setEditableResult('');
    setIsEditing(false);
  }, [audioUrl]);

  const handleFileUpload = useCallback((event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.type.startsWith('audio/')) {
        toast.error('Пожалуйста, выберите аудио файл');
        return;
      }
      
      if (file.size > 25 * 1024 * 1024) {
        toast.error('Файл слишком большой (максимум 25 МБ)');
        return;
      }
      
      setAudioBlob(file);
      setAudioUrl(URL.createObjectURL(file));
      toast.success('Файл загружен');
    }
  }, []);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleTranscription = async () => {
    if (!audioBlob) {
      toast.error('Сначала запишите или загрузите аудио');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'recording.webm');
      formData.append('language', settings.language);
      formData.append('medical_context', settings.medical_context);

      const response = await api.post('/ai/transcribe-audio', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
      setEditableResult(response.data.text || '');
      toast.success('Транскрипция завершена!');
    } catch (error) {
      logger.error('Ошибка транскрипции:', error);
      toast.error(error.response?.data?.detail || 'Ошибка при транскрипции');
    } finally {
      setLoading(false);
    }
  };

  const handleTextProcessing = async (endpoint, data) => {
    setLoading(true);
    setResult(null);

    try {
      const response = await api.post(`/ai/${endpoint}`, data);
      setResult(response.data);
      toast.success('Обработка завершена!');
    } catch (error) {
      logger.error('Ошибка обработки:', error);
      toast.error(error.response?.data?.detail || 'Ошибка при обработке текста');
    } finally {
      setLoading(false);
    }
  };

  const handleStructuring = () => {
    if (!textInput.trim()) {
      toast.error('Введите текст для структурирования');
      return;
    }
    
    handleTextProcessing('structure-medical-text', {
      text: textInput,
      document_type: settings.document_type
    });
  };

  const handleEntityExtraction = () => {
    if (!textInput.trim()) {
      toast.error('Введите текст для извлечения сущностей');
      return;
    }
    
    handleTextProcessing('extract-medical-entities', {
      text: textInput
    });
  };

  const handleSummaryGeneration = () => {
    if (!textInput.trim()) {
      toast.error('Введите текст консультации');
      return;
    }
    
    handleTextProcessing('generate-medical-summary', {
      consultation_text: textInput
    });
  };

  const handleValidation = () => {
    if (!textInput.trim()) {
      toast.error('Введите данные для валидации');
      return;
    }
    
    try {
      const recordData = JSON.parse(textInput);
      handleTextProcessing('validate-medical-record', {
        record_data: recordData
      });
    } catch (error) {
      toast.error('Введите корректный JSON');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success('Скопировано в буфер обмена');
    });
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `voice_to_text_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const saveEditedText = () => {
    if (result) {
      setResult({
        ...result,
        text: editableResult
      });
      setIsEditing(false);
      toast.success('Изменения сохранены');
    }
  };

  const renderRecordingControls = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '16px' }}>
          {!isRecording ? (
            <MacOSButton
              onClick={startRecording}
              style={{ 
                width: '64px', 
                height: '64px', 
                borderRadius: '50%',
                backgroundColor: 'var(--mac-error)',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Mic style={{ width: '32px', height: '32px', color: 'white' }} />
            </MacOSButton>
          ) : (
            <>
              <MacOSButton
                onClick={pauseRecording}
                style={{ 
                  width: '48px', 
                  height: '48px', 
                  borderRadius: '50%',
                  backgroundColor: 'var(--mac-warning)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                {isPaused ? (
                  <Play style={{ width: '24px', height: '24px', color: 'white' }} />
                ) : (
                  <Pause style={{ width: '24px', height: '24px', color: 'white' }} />
                )}
              </MacOSButton>
              <MacOSButton
                onClick={stopRecording}
                style={{ 
                  width: '64px', 
                  height: '64px', 
                  borderRadius: '50%',
                  backgroundColor: 'var(--mac-error)',
                  border: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
              >
                <Square style={{ width: '32px', height: '32px', color: 'white' }} />
              </MacOSButton>
            </>
          )}
        </div>

        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontFamily: 'var(--mac-font-mono)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-text-primary)'
          }}>
            {formatTime(recordingTime)}
          </div>
          {isRecording && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '8px' }}>
              <div style={{ 
                width: '12px', 
                height: '12px', 
                backgroundColor: 'var(--mac-error)', 
                borderRadius: '50%',
                animation: 'pulse 1s infinite',
                marginRight: '8px'
              }} />
              <span style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-error)'
              }}>
                {isPaused ? 'Пауза' : 'Запись...'}
              </span>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'center', gap: '16px' }}>
          <input
            type="file"
            accept="audio/*"
            onChange={handleFileUpload}
            ref={fileInputRef}
            style={{ display: 'none' }}
          />
          <MacOSButton
            onClick={() => fileInputRef.current?.click()}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Upload style={{ width: '16px', height: '16px' }} />
            Загрузить файл
          </MacOSButton>
          
          {audioBlob && (
            <MacOSButton
              onClick={resetRecording}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <RefreshCw style={{ width: '16px', height: '16px' }} />
              Сбросить
            </MacOSButton>
          )}
        </div>

        {audioUrl && (
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <audio 
              controls 
              src={audioUrl} 
              style={{ 
                width: '100%', 
                maxWidth: '400px',
                borderRadius: 'var(--mac-radius-md)'
              }} 
            />
          </div>
        )}
      </div>
    </MacOSCard>
  );

  const renderSettings = () => (
    <MacOSCard style={{ 
      padding: '16px', 
      backgroundColor: 'var(--mac-bg-secondary)', 
      border: '1px solid var(--mac-border)',
      marginBottom: '24px'
    }}>
      <h4 style={{ 
        fontWeight: 'var(--mac-font-weight-medium)', 
        color: 'var(--mac-text-primary)',
        margin: '0 0 16px 0',
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <Settings style={{ width: '16px', height: '16px' }} />
        Настройки
      </h4>
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px' 
      }}>
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '4px' 
          }}>
            Язык
          </label>
          <MacOSSelect
            value={settings.language}
            onChange={(e) => setSettings(prev => ({ ...prev, language: e.target.value }))}
            options={[
              { value: 'ru', label: 'Русский' },
              { value: 'en', label: 'English' },
              { value: 'uz', label: 'O\'zbek' }
            ]}
            style={{ width: '100%' }}
          />
        </div>
        
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '4px' 
          }}>
            Тип документа
          </label>
          <MacOSSelect
            value={settings.document_type}
            onChange={(e) => setSettings(prev => ({ ...prev, document_type: e.target.value }))}
            options={[
              { value: 'consultation', label: 'Консультация' },
              { value: 'prescription', label: 'Рецепт' },
              { value: 'discharge', label: 'Выписка' },
              { value: 'examination', label: 'Обследование' }
            ]}
            style={{ width: '100%' }}
          />
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MacOSCheckbox
            id="medical_context"
            checked={settings.medical_context}
            onChange={(e) => setSettings(prev => ({ ...prev, medical_context: e.target.checked }))}
          />
          <label htmlFor="medical_context" style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Медицинский контекст
          </label>
        </div>
      </div>
    </MacOSCard>
  );

  const renderStructuring = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <FileText style={{ width: '16px', height: '16px' }} />
            Структурирование медицинского текста
          </h4>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Автоматическое выделение разделов: жалобы, анамнез, осмотр, диагноз, лечение
          </p>
        </MacOSCard>
        
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Введите медицинский текст
          </label>
          <MacOSTextarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ 
              width: '100%', 
              height: '128px',
              fontSize: 'var(--mac-font-size-sm)'
            }}
            placeholder="Введите текст консультации, выписки или другого медицинского документа..."
          />
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={handleStructuring}
            disabled={loading || !textInput.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Структурируем...
              </>
            ) : (
              <>
                <FileText style={{ width: '20px', height: '20px' }} />
                Структурировать
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderEntities = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-accent-bg)', 
          border: '1px solid var(--mac-accent-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-accent)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Brain style={{ width: '16px', height: '16px' }} />
            Извлечение медицинских сущностей
          </h4>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Поиск симптомов, диагнозов, препаратов, процедур и других медицинских терминов
          </p>
        </MacOSCard>
        
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Введите текст для анализа
          </label>
          <MacOSTextarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ 
              width: '100%', 
              height: '128px',
              fontSize: 'var(--mac-font-size-sm)'
            }}
            placeholder="Введите медицинский текст для извлечения сущностей..."
          />
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={handleEntityExtraction}
            disabled={loading || !textInput.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Извлекаем сущности...
              </>
            ) : (
              <>
                <Brain style={{ width: '20px', height: '20px' }} />
                Извлечь сущности
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderSummary = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-success-bg)', 
          border: '1px solid var(--mac-success-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-success)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Edit3 style={{ width: '16px', height: '16px' }} />
            Генерация медицинского резюме
          </h4>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Создание краткого резюме консультации с ключевыми моментами и рекомендациями
          </p>
        </MacOSCard>
        
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Введите текст консультации
          </label>
          <MacOSTextarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ 
              width: '100%', 
              height: '128px',
              fontSize: 'var(--mac-font-size-sm)'
            }}
            placeholder="Введите полный текст консультации для создания резюме..."
          />
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={handleSummaryGeneration}
            disabled={loading || !textInput.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Создаем резюме...
              </>
            ) : (
              <>
                <Edit3 style={{ width: '20px', height: '20px' }} />
                Создать резюме
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderValidation = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-warning-bg)', 
          border: '1px solid var(--mac-warning-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle style={{ width: '16px', height: '16px' }} />
            Валидация медицинских записей
          </h4>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Проверка корректности медицинских данных, соответствия стандартам и выявление ошибок
          </p>
        </MacOSCard>
        
        <div>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Введите JSON данные записи
          </label>
          <MacOSTextarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            style={{ 
              width: '100%', 
              height: '128px',
              fontSize: 'var(--mac-font-size-sm)',
              fontFamily: 'var(--mac-font-mono)'
            }}
            placeholder='{"patient_id": "123", "diagnosis": "Гипертония", "medications": ["Амлодипин"], "vital_signs": {"bp": "140/90"}}'
          />
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={handleValidation}
            disabled={loading || !textInput.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Валидируем...
              </>
            ) : (
              <>
                <CheckCircle style={{ width: '20px', height: '20px' }} />
                Валидировать
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-error-bg)', 
          border: '1px solid var(--mac-error-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <XCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-error)',
              margin: 0
            }}>
              Ошибка
            </h3>
          </div>
          <p style={{ 
            marginTop: '8px',
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-error)',
            margin: '8px 0 0 0'
          }}>
            {result.error}
          </p>
        </MacOSCard>
      );
    }

    return (
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
            Результат обработки
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            {result.text && (
              <MacOSButton
                onClick={() => copyToClipboard(result.text)}
                variant="outline"
                style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
              >
                <Copy style={{ width: '16px', height: '16px' }} />
                Копировать
              </MacOSButton>
            )}
            <MacOSButton
              onClick={exportResult}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Download style={{ width: '16px', height: '16px' }} />
              Экспорт
            </MacOSButton>
          </div>
        </div>

        {/* Специальное отображение для транскрипции */}
        {activeTab === 'transcription' && result.text && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <MacOSCard style={{ 
              padding: '16px', 
              backgroundColor: 'var(--mac-info-bg)', 
              border: '1px solid var(--mac-info-border)' 
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <h4 style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  Транскрибированный текст
                </h4>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <MacOSButton
                    onClick={() => setIsEditing(!isEditing)}
                    variant="outline"
                    style={{ padding: '4px', minWidth: 'auto' }}
                  >
                    <Edit3 style={{ width: '16px', height: '16px' }} />
                  </MacOSButton>
                  {isEditing && (
                    <MacOSButton
                      onClick={saveEditedText}
                      variant="outline"
                      style={{ padding: '4px', minWidth: 'auto' }}
                    >
                      <Save style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                  )}
                </div>
              </div>
              
              {isEditing ? (
                <MacOSTextarea
                  value={editableResult}
                  onChange={(e) => setEditableResult(e.target.value)}
                  style={{ 
                    width: '100%', 
                    height: '128px',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}
                />
              ) : (
                <p style={{ 
                  color: 'var(--mac-text-primary)', 
                  whiteSpace: 'pre-wrap',
                  margin: 0,
                  fontSize: 'var(--mac-font-size-sm)'
                }}>
                  {result.text}
                </p>
              )}
            </MacOSCard>

            {result.segments && result.segments.length > 0 && (
              <MacOSCard style={{ 
                padding: '16px', 
                backgroundColor: 'var(--mac-bg-secondary)', 
                border: '1px solid var(--mac-border)' 
              }}>
                <h4 style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0'
                }}>
                  Сегменты
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {result.segments.map((segment, index) => (
                    <div key={index} style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', fontSize: 'var(--mac-font-size-sm)' }}>
                      <span style={{ 
                        color: 'var(--mac-accent)', 
                        fontFamily: 'var(--mac-font-mono)',
                        minWidth: '60px'
                      }}>
                        {segment.start.toFixed(1)}s
                      </span>
                      <span style={{ 
                        color: 'var(--mac-text-primary)', 
                        flex: 1
                      }}>
                        {segment.text}
                      </span>
                      <span style={{ 
                        color: 'var(--mac-text-secondary)',
                        minWidth: '40px'
                      }}>
                        {(segment.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </MacOSCard>
            )}

            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
              gap: '16px',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              <div>
                <span style={{ color: 'var(--mac-text-secondary)' }}>Язык:</span>
                <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                  {result.language}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--mac-text-secondary)' }}>Длительность:</span>
                <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                  {result.duration?.toFixed(1)}s
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--mac-text-secondary)' }}>Достоверность:</span>
                <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                  {(result.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--mac-text-secondary)' }}>Контекст:</span>
                <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                  {result.medical_context ? 'Медицинский' : 'Общий'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'transcription' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {Object.entries(result).map(([key, value]) => (
              <div key={key} style={{ 
                borderLeft: '4px solid var(--mac-accent)', 
                paddingLeft: '16px' 
              }}>
                <h4 style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0',
                  fontSize: 'var(--mac-font-size-sm)',
                  textTransform: 'capitalize'
                }}>
                  {key.replace(/_/g, ' ')}
                </h4>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  {typeof value === 'object' && value !== null ? (
                    <pre style={{ 
                      whiteSpace: 'pre-wrap', 
                      backgroundColor: 'var(--mac-bg-secondary)', 
                      padding: '8px', 
                      borderRadius: 'var(--mac-radius-sm)', 
                      fontSize: 'var(--mac-font-size-xs)', 
                      overflowX: 'auto', 
                      maxHeight: '256px',
                      margin: 0,
                      fontFamily: 'var(--mac-font-mono)'
                    }}>
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <p style={{ margin: 0 }}>{String(value)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </MacOSCard>
    );
  };

  return (
    <div style={{ 
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{ 
          paddingBottom: '24px', 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <Volume2 style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            AI Голосовой Ввод для Медицинских Карт
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Преобразование речи в текст и автоматическое структурирование медицинской информации
          </p>
        </div>

        {/* Вкладки */}
        <div style={{ 
          display: 'flex', 
          marginBottom: '24px'
        }}>
          {tabs.map(tab => {
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '12px 20px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                  fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                  fontSize: 'var(--mac-font-size-sm)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                  position: 'relative',
                  marginBottom: '-1px'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-primary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-secondary)';
                  }
                }}
              >
                <div style={{ 
                  width: '16px', 
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
                }}>
                  {tab.icon}
                </div>
                {tab.label}
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '0',
                    right: '0',
                    height: '3px',
                    backgroundColor: 'var(--mac-accent)',
                    borderRadius: '2px 2px 0 0'
                  }} />
                )}
              </button>
            );
          })}
        </div>
        
        {/* Разделительная линия */}
        <div style={{ 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }} />

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
          gap: '24px' 
        }}>
          <div>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              {activeTab === 'transcription' && 'Запись аудио'}
              {activeTab === 'structuring' && 'Структурирование текста'}
              {activeTab === 'entities' && 'Извлечение сущностей'}
              {activeTab === 'summary' && 'Создание резюме'}
              {activeTab === 'validation' && 'Валидация данных'}
            </h3>
            
            {renderSettings()}
            
            {activeTab === 'transcription' && renderRecordingControls()}
            {activeTab === 'structuring' && renderStructuring()}
            {activeTab === 'entities' && renderEntities()}
            {activeTab === 'summary' && renderSummary()}
            {activeTab === 'validation' && renderValidation()}
            
            {activeTab === 'transcription' && audioBlob && (
              <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
                <MacOSButton
                  onClick={handleTranscription}
                  disabled={loading}
                  style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                >
                  {loading ? (
                    <>
                      <Loader style={{ 
                        width: '20px', 
                        height: '20px',
                        animation: 'spin 1s linear infinite'
                      }} />
                      Транскрибируем...
                    </>
                  ) : (
                    <>
                      <Brain style={{ width: '20px', height: '20px' }} />
                      Транскрибировать
                    </>
                  )}
                </MacOSButton>
              </div>
            )}
          </div>

          <div>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Результат
            </h3>
            {renderResult()}
          </div>
        </div>
      </MacOSCard>
    </div>
  );
};

export default VoiceToText;



