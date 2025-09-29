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
import { toast } from 'react-toastify';
import api from '../../utils/api';

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
      console.error('Ошибка доступа к микрофону:', error);
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
      console.error('Ошибка транскрипции:', error);
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
      console.error('Ошибка обработки:', error);
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
    <div className="space-y-4">
      <div className="flex items-center justify-center space-x-4">
        {!isRecording ? (
          <button
            onClick={startRecording}
            className="flex items-center justify-center w-16 h-16 bg-red-500 hover:bg-red-600 text-white rounded-full transition-colors"
          >
            <Mic className="w-8 h-8" />
          </button>
        ) : (
          <>
            <button
              onClick={pauseRecording}
              className="flex items-center justify-center w-12 h-12 bg-yellow-500 hover:bg-yellow-600 text-white rounded-full transition-colors"
            >
              {isPaused ? <Play className="w-6 h-6" /> : <Pause className="w-6 h-6" />}
            </button>
            <button
              onClick={stopRecording}
              className="flex items-center justify-center w-16 h-16 bg-red-500 hover:bg-red-600 text-white rounded-full transition-colors"
            >
              <Square className="w-8 h-8" />
            </button>
          </>
        )}
      </div>

      <div className="text-center">
        <div className="text-2xl font-mono font-bold text-gray-700">
          {formatTime(recordingTime)}
        </div>
        {isRecording && (
          <div className="flex items-center justify-center mt-2">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse mr-2"></div>
            <span className="text-sm text-red-600">
              {isPaused ? 'Пауза' : 'Запись...'}
            </span>
          </div>
        )}
      </div>

      <div className="flex justify-center space-x-4">
        <input
          type="file"
          accept="audio/*"
          onChange={handleFileUpload}
          ref={fileInputRef}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors"
        >
          <Upload className="w-4 h-4 mr-2" />
          Загрузить файл
        </button>
        
        {audioBlob && (
          <button
            onClick={resetRecording}
            className="flex items-center px-4 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded-md transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Сбросить
          </button>
        )}
      </div>

      {audioUrl && (
        <div className="flex justify-center">
          <audio controls src={audioUrl} className="w-full max-w-md" />
        </div>
      )}
    </div>
  );

  const renderSettings = () => (
    <div className="bg-gray-50 p-4 rounded-lg space-y-4">
      <h4 className="font-medium text-gray-900 flex items-center">
        <Settings className="w-4 h-4 mr-2" />
        Настройки
      </h4>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Язык</label>
          <select
            value={settings.language}
            onChange={(e) => setSettings(prev => ({ ...prev, language: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ru">Русский</option>
            <option value="en">English</option>
            <option value="uz">O'zbek</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Тип документа</label>
          <select
            value={settings.document_type}
            onChange={(e) => setSettings(prev => ({ ...prev, document_type: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="consultation">Консультация</option>
            <option value="prescription">Рецепт</option>
            <option value="discharge">Выписка</option>
            <option value="examination">Обследование</option>
          </select>
        </div>
        
        <div className="flex items-center">
          <input
            type="checkbox"
            id="medical_context"
            checked={settings.medical_context}
            onChange={(e) => setSettings(prev => ({ ...prev, medical_context: e.target.checked }))}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <label htmlFor="medical_context" className="ml-2 text-sm text-gray-700">
            Медицинский контекст
          </label>
        </div>
      </div>
    </div>
  );

  const renderTextInput = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Введите текст для обработки
        </label>
        <textarea
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          className="w-full h-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder={
            activeTab === 'validation' 
              ? 'Введите JSON данные медицинской записи...'
              : 'Введите медицинский текст для обработки...'
          }
        />
      </div>
      
      <div className="flex justify-center">
        <button
          onClick={() => {
            switch (activeTab) {
              case 'structuring':
                handleStructuring();
                break;
              case 'entities':
                handleEntityExtraction();
                break;
              case 'summary':
                handleSummaryGeneration();
                break;
              case 'validation':
                handleValidation();
                break;
            }
          }}
          disabled={loading || !textInput.trim()}
          className="flex items-center px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
              Обрабатываем...
            </>
          ) : (
            <>
              <Zap className="h-5 w-5 mr-2" />
              Обработать
            </>
          )}
        </button>
      </div>
    </div>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <XCircle className="h-5 w-5 text-red-400 mr-2" />
            <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
          </div>
          <p className="mt-2 text-sm text-red-700">{result.error}</p>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
            Результат обработки
          </h3>
          <div className="flex space-x-2">
            {result.text && (
              <button
                onClick={() => copyToClipboard(result.text)}
                className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <Copy className="h-4 w-4 mr-1" />
                Копировать
              </button>
            )}
            <button
              onClick={exportResult}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              Экспорт
            </button>
          </div>
        </div>

        {/* Специальное отображение для транскрипции */}
        {activeTab === 'transcription' && result.text && (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-blue-900">Транскрибированный текст</h4>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setIsEditing(!isEditing)}
                    className="text-blue-600 hover:text-blue-800"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                  {isEditing && (
                    <button
                      onClick={saveEditedText}
                      className="text-green-600 hover:text-green-800"
                    >
                      <Save className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>
              
              {isEditing ? (
                <textarea
                  value={editableResult}
                  onChange={(e) => setEditableResult(e.target.value)}
                  className="w-full h-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              ) : (
                <p className="text-gray-700 whitespace-pre-wrap">{result.text}</p>
              )}
            </div>

            {result.segments && result.segments.length > 0 && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h4 className="font-medium text-gray-900 mb-2">Сегменты</h4>
                <div className="space-y-2">
                  {result.segments.map((segment, index) => (
                    <div key={index} className="flex items-start space-x-3 text-sm">
                      <span className="text-blue-600 font-mono">
                        {segment.start.toFixed(1)}s
                      </span>
                      <span className="text-gray-700 flex-1">{segment.text}</span>
                      <span className="text-gray-500">
                        {(segment.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Язык:</span>
                <span className="ml-1 font-medium">{result.language}</span>
              </div>
              <div>
                <span className="text-gray-600">Длительность:</span>
                <span className="ml-1 font-medium">{result.duration?.toFixed(1)}s</span>
              </div>
              <div>
                <span className="text-gray-600">Достоверность:</span>
                <span className="ml-1 font-medium">{(result.confidence * 100).toFixed(0)}%</span>
              </div>
              <div>
                <span className="text-gray-600">Контекст:</span>
                <span className="ml-1 font-medium">{result.medical_context ? 'Медицинский' : 'Общий'}</span>
              </div>
            </div>
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'transcription' && (
          <div className="space-y-4">
            {Object.entries(result).map(([key, value]) => (
              <div key={key} className="border-l-4 border-blue-400 pl-4">
                <h4 className="font-medium text-gray-900 capitalize mb-2">
                  {key.replace(/_/g, ' ')}
                </h4>
                <div className="text-sm text-gray-600">
                  {typeof value === 'object' && value !== null ? (
                    <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <p>{String(value)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <Volume2 className="h-6 w-6 text-blue-600 mr-2" />
            AI Голосовой Ввод для Медицинских Карт
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Преобразование речи в текст и автоматическое структурирование медицинской информации
          </p>
        </div>

        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {renderSettings()}
          
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                {activeTab === 'transcription' ? 'Запись аудио' : 'Ввод текста'}
              </h3>
              
              {activeTab === 'transcription' ? renderRecordingControls() : renderTextInput()}
              
              {activeTab === 'transcription' && audioBlob && (
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={handleTranscription}
                    disabled={loading}
                    className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <>
                        <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                        Транскрибируем...
                      </>
                    ) : (
                      <>
                        <Brain className="h-5 w-5 mr-2" />
                        Транскрибировать
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Результат</h3>
              {renderResult()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoiceToText;



