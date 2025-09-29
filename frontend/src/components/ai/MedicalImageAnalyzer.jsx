import React, { useState, useCallback } from 'react';
import { 
  Upload, 
  Image, 
  FileText, 
  AlertCircle, 
  CheckCircle, 
  Loader, 
  Eye,
  Download,
  Share2,
  Stethoscope,
  Brain,
  Heart
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const MedicalImageAnalyzer = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [imageType, setImageType] = useState('xray');
  const [metadata, setMetadata] = useState({
    body_part: '',
    patient_age: '',
    patient_gender: '',
    clinical_info: '',
    organ: '',
    lesion_location: '',
    lesion_history: ''
  });
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const imageTypes = [
    { value: 'xray', label: 'Рентген', icon: <Image className="w-4 h-4" />, endpoint: 'analyze-xray' },
    { value: 'ultrasound', label: 'УЗИ', icon: <Heart className="w-4 h-4" />, endpoint: 'analyze-ultrasound' },
    { value: 'dermatoscopy', label: 'Дерматоскопия', icon: <Eye className="w-4 h-4" />, endpoint: 'analyze-dermatoscopy' },
    { value: 'ct', label: 'КТ', icon: <Brain className="w-4 h-4" />, endpoint: 'analyze-medical-image' },
    { value: 'mri', label: 'МРТ', icon: <Brain className="w-4 h-4" />, endpoint: 'analyze-medical-image' },
    { value: 'endoscopy', label: 'Эндоскопия', icon: <Stethoscope className="w-4 h-4" />, endpoint: 'analyze-medical-image' }
  ];

  const handleFileSelect = useCallback((event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        toast.error('Пожалуйста, выберите изображение');
        return;
      }
      
      if (file.size > 10 * 1024 * 1024) { // 10MB limit
        toast.error('Размер файла не должен превышать 10MB');
        return;
      }

      setSelectedFile(file);
      
      // Создаем превью
      const reader = new FileReader();
      reader.onload = (e) => setPreviewUrl(e.target.result);
      reader.readAsDataURL(file);
    }
  }, []);

  const handleMetadataChange = useCallback((field, value) => {
    setMetadata(prev => ({ ...prev, [field]: value }));
  }, []);

  const analyzeImage = async () => {
    if (!selectedFile) {
      toast.error('Выберите изображение для анализа');
      return;
    }

    setAnalyzing(true);
    setResult(null);

    try {
      const selectedImageType = imageTypes.find(type => type.value === imageType);
      const formData = new FormData();
      formData.append('image', selectedFile);
      
      // Добавляем метаданные в зависимости от типа изображения
      const relevantMetadata = {};
      if (imageType === 'xray') {
        relevantMetadata.body_part = metadata.body_part;
        relevantMetadata.patient_age = metadata.patient_age;
        relevantMetadata.patient_gender = metadata.patient_gender;
        relevantMetadata.clinical_info = metadata.clinical_info;
      } else if (imageType === 'ultrasound') {
        relevantMetadata.organ = metadata.organ;
        relevantMetadata.patient_age = metadata.patient_age;
        relevantMetadata.patient_gender = metadata.patient_gender;
        relevantMetadata.clinical_indication = metadata.clinical_info;
      } else if (imageType === 'dermatoscopy') {
        relevantMetadata.lesion_location = metadata.lesion_location;
        relevantMetadata.patient_age = metadata.patient_age;
        relevantMetadata.patient_gender = metadata.patient_gender;
        relevantMetadata.lesion_history = metadata.lesion_history;
      } else {
        relevantMetadata.patient_age = metadata.patient_age;
        relevantMetadata.patient_gender = metadata.patient_gender;
        relevantMetadata.clinical_info = metadata.clinical_info;
        formData.append('image_type', imageType);
      }

      if (Object.keys(relevantMetadata).length > 0) {
        formData.append('metadata', JSON.stringify(relevantMetadata));
      }

      const response = await api.post(`/ai/${selectedImageType.endpoint}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
      toast.success('Анализ завершен!');
    } catch (error) {
      console.error('Ошибка анализа:', error);
      toast.error(error.response?.data?.detail || 'Ошибка при анализе изображения');
    } finally {
      setAnalyzing(false);
    }
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `medical_analysis_${imageType}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const renderMetadataFields = () => {
    switch (imageType) {
      case 'xray':
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Область исследования
              </label>
              <input
                type="text"
                value={metadata.body_part}
                onChange={(e) => handleMetadataChange('body_part', e.target.value)}
                placeholder="Например: грудная клетка, позвоночник"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </>
        );
      case 'ultrasound':
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Исследуемый орган
              </label>
              <input
                type="text"
                value={metadata.organ}
                onChange={(e) => handleMetadataChange('organ', e.target.value)}
                placeholder="Например: печень, почки, сердце"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </>
        );
      case 'dermatoscopy':
        return (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Локализация образования
              </label>
              <input
                type="text"
                value={metadata.lesion_location}
                onChange={(e) => handleMetadataChange('lesion_location', e.target.value)}
                placeholder="Например: спина, лицо, рука"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Анамнез образования
              </label>
              <textarea
                value={metadata.lesion_history}
                onChange={(e) => handleMetadataChange('lesion_history', e.target.value)}
                placeholder="История появления и изменения образования"
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </>
        );
      default:
        return null;
    }
  };

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
            <h3 className="text-sm font-medium text-red-800">Ошибка анализа</h3>
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
            Результат анализа
          </h3>
          <div className="flex space-x-2">
            <button
              onClick={exportResult}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              Экспорт
            </button>
          </div>
        </div>

        {/* Заключение */}
        {result.conclusion && (
          <div className="mb-4 p-4 bg-blue-50 rounded-lg">
            <h4 className="font-medium text-blue-900 mb-2">Заключение</h4>
            <p className="text-blue-800">{result.conclusion}</p>
          </div>
        )}

        {/* Уровень уверенности */}
        {result.confidence_level && (
          <div className="mb-4">
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
              Уверенность: {result.confidence_level}
            </span>
          </div>
        )}

        {/* Патологические находки */}
        {result.pathological_findings && result.pathological_findings.length > 0 && (
          <div className="mb-4">
            <h4 className="font-medium text-gray-900 mb-2">Патологические находки</h4>
            <div className="space-y-2">
              {result.pathological_findings.map((finding, index) => (
                <div key={index} className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                  <div className="font-medium text-yellow-800">{finding.finding}</div>
                  {finding.location && (
                    <div className="text-sm text-yellow-700">Локализация: {finding.location}</div>
                  )}
                  {finding.description && (
                    <div className="text-sm text-yellow-700 mt-1">{finding.description}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Нормальные находки */}
        {result.normal_findings && result.normal_findings.length > 0 && (
          <div className="mb-4">
            <h4 className="font-medium text-gray-900 mb-2">Нормальные структуры</h4>
            <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
              {result.normal_findings.map((finding, index) => (
                <li key={index}>{finding}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Рекомендации */}
        {result.recommendations && (
          <div className="mb-4">
            <h4 className="font-medium text-gray-900 mb-2">Рекомендации</h4>
            <div className="space-y-2 text-sm text-gray-600">
              {result.recommendations.additional_studies && result.recommendations.additional_studies.length > 0 && (
                <div>
                  <strong>Дополнительные исследования:</strong>
                  <ul className="list-disc list-inside ml-4">
                    {result.recommendations.additional_studies.map((study, index) => (
                      <li key={index}>{study}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.recommendations.follow_up && (
                <div>
                  <strong>Наблюдение:</strong> {result.recommendations.follow_up}
                </div>
              )}
              {result.recommendations.specialist_consultation && (
                <div>
                  <strong>Консультация специалиста:</strong> {result.recommendations.specialist_consultation}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Срочные находки */}
        {result.urgent_findings && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center">
              <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
              <h4 className="font-medium text-red-800">Требует срочного внимания</h4>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <Brain className="h-6 w-6 text-blue-600 mr-2" />
            AI Анализ Медицинских Изображений
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Загрузите медицинское изображение для автоматического анализа с помощью искусственного интеллекта
          </p>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Левая панель - загрузка и настройки */}
            <div className="space-y-6">
              {/* Выбор типа изображения */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Тип медицинского изображения
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {imageTypes.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setImageType(type.value)}
                      className={`flex items-center justify-center px-3 py-2 border rounded-md text-sm font-medium transition-colors ${
                        imageType === type.value
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      {type.icon}
                      <span className="ml-2">{type.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Загрузка файла */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Загрузить изображение
                </label>
                <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-gray-300 border-dashed rounded-md hover:border-gray-400 transition-colors">
                  <div className="space-y-1 text-center">
                    <Upload className="mx-auto h-12 w-12 text-gray-400" />
                    <div className="flex text-sm text-gray-600">
                      <label
                        htmlFor="file-upload"
                        className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500"
                      >
                        <span>Выберите файл</span>
                        <input
                          id="file-upload"
                          name="file-upload"
                          type="file"
                          className="sr-only"
                          accept="image/*"
                          onChange={handleFileSelect}
                        />
                      </label>
                      <p className="pl-1">или перетащите сюда</p>
                    </div>
                    <p className="text-xs text-gray-500">PNG, JPG, JPEG до 10MB</p>
                  </div>
                </div>
                {selectedFile && (
                  <p className="mt-2 text-sm text-gray-600">
                    Выбран файл: {selectedFile.name}
                  </p>
                )}
              </div>

              {/* Метаданные */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-700">Дополнительная информация</h3>
                
                {/* Общие поля */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Возраст пациента
                    </label>
                    <input
                      type="text"
                      value={metadata.patient_age}
                      onChange={(e) => handleMetadataChange('patient_age', e.target.value)}
                      placeholder="Например: 45 лет"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Пол
                    </label>
                    <select
                      value={metadata.patient_gender}
                      onChange={(e) => handleMetadataChange('patient_gender', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Не указан</option>
                      <option value="мужской">Мужской</option>
                      <option value="женский">Женский</option>
                    </select>
                  </div>
                </div>

                {/* Специфичные поля */}
                {renderMetadataFields()}

                {/* Клиническая информация */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Клиническая информация
                  </label>
                  <textarea
                    value={metadata.clinical_info}
                    onChange={(e) => handleMetadataChange('clinical_info', e.target.value)}
                    placeholder="Жалобы, анамнез, предварительный диагноз"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Кнопка анализа */}
              <button
                onClick={analyzeImage}
                disabled={!selectedFile || analyzing}
                className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {analyzing ? (
                  <>
                    <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                    Анализируем...
                  </>
                ) : (
                  <>
                    <Brain className="h-5 w-5 mr-2" />
                    Анализировать изображение
                  </>
                )}
              </button>
            </div>

            {/* Правая панель - превью и результат */}
            <div className="space-y-6">
              {/* Превью изображения */}
              {previewUrl && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Превью изображения</h3>
                  <div className="border border-gray-200 rounded-lg p-4">
                    <img
                      src={previewUrl}
                      alt="Preview"
                      className="max-w-full h-auto max-h-64 mx-auto rounded"
                    />
                  </div>
                </div>
              )}

              {/* Результат анализа */}
              {renderResult()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MedicalImageAnalyzer;



