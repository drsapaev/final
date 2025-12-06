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
import { api } from '../../utils/api';
import logger from '../../utils/logger';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput, 
  MacOSSelect, 
  MacOSTextarea 
} from '../ui/macos';

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
    { value: 'xray', label: 'Рентген', icon: <Image style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-xray' },
    { value: 'ultrasound', label: 'УЗИ', icon: <Heart style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-ultrasound' },
    { value: 'dermatoscopy', label: 'Дерматоскопия', icon: <Eye style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-dermatoscopy' },
    { value: 'ct', label: 'КТ', icon: <Brain style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-medical-image' },
    { value: 'mri', label: 'МРТ', icon: <Brain style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-medical-image' },
    { value: 'endoscopy', label: 'Эндоскопия', icon: <Stethoscope style={{ width: '16px', height: '16px' }} />, endpoint: 'analyze-medical-image' }
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
      logger.error('Ошибка анализа:', error);
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
          <div style={{ marginBottom: '16px' }}>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Область исследования
            </label>
            <MacOSInput
              type="text"
              value={metadata.body_part}
              onChange={(e) => handleMetadataChange('body_part', e.target.value)}
              placeholder="Например: грудная клетка, позвоночник"
              style={{ width: '100%' }}
            />
          </div>
        );
      case 'ultrasound':
        return (
          <div style={{ marginBottom: '16px' }}>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Исследуемый орган
            </label>
            <MacOSInput
              type="text"
              value={metadata.organ}
              onChange={(e) => handleMetadataChange('organ', e.target.value)}
              placeholder="Например: печень, почки, сердце"
              style={{ width: '100%' }}
            />
          </div>
        );
      case 'dermatoscopy':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginBottom: '16px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Локализация образования
              </label>
              <MacOSInput
                type="text"
                value={metadata.lesion_location}
                onChange={(e) => handleMetadataChange('lesion_location', e.target.value)}
                placeholder="Например: спина, лицо, рука"
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
                Анамнез образования
              </label>
              <MacOSTextarea
                value={metadata.lesion_history}
                onChange={(e) => handleMetadataChange('lesion_history', e.target.value)}
                placeholder="История появления и изменения образования"
                rows={2}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-danger)',
              margin: 0
            }}>
              Ошибка анализа
            </h3>
          </div>
          <p style={{ 
            marginTop: '8px',
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-danger)',
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
            Результат анализа
          </h3>
          <MacOSButton
            onClick={exportResult}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Download style={{ width: '16px', height: '16px' }} />
            Экспорт
          </MacOSButton>
        </div>

        {/* Заключение */}
        {result.conclusion && (
          <MacOSCard style={{ 
            padding: '16px', 
            backgroundColor: 'var(--mac-bg-primary)', 
            border: '1px solid var(--mac-border)',
            marginBottom: '16px'
          }}>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Заключение
            </h4>
            <p style={{ 
              color: 'var(--mac-text-primary)', 
              margin: 0,
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              {result.conclusion}
            </p>
          </MacOSCard>
        )}

        {/* Уровень уверенности */}
        {result.confidence_level && (
          <div style={{ marginBottom: '16px' }}>
            <span style={{ 
              display: 'inline-flex', 
              alignItems: 'center', 
              padding: '4px 8px', 
              borderRadius: 'var(--mac-radius-full)', 
              fontSize: 'var(--mac-font-size-xs)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              backgroundColor: 'var(--mac-bg-secondary)', 
              color: 'var(--mac-text-primary)',
              border: '1px solid var(--mac-border)'
            }}>
              Уверенность: {result.confidence_level}
            </span>
          </div>
        )}

        {/* Патологические находки */}
        {result.pathological_findings && result.pathological_findings.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Патологические находки
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {result.pathological_findings.map((finding, index) => (
                <MacOSCard key={index} style={{ 
                  padding: '12px', 
                  backgroundColor: 'var(--mac-bg-primary)', 
                  border: '1px solid var(--mac-border)' 
                }}>
                  <div style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-warning)',
                    marginBottom: '4px'
                  }}>
                    {finding.finding}
                  </div>
                  {finding.location && (
                    <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-warning)',
                      marginBottom: '4px'
                    }}>
                      Локализация: {finding.location}
                    </div>
                  )}
                  {finding.description && (
                    <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-warning)',
                      margin: 0
                    }}>
                      {finding.description}
                    </div>
                  )}
                </MacOSCard>
              ))}
            </div>
          </div>
        )}

        {/* Нормальные находки */}
        {result.normal_findings && result.normal_findings.length > 0 && (
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Нормальные структуры
            </h4>
            <ul style={{ 
              listStyleType: 'disc', 
              paddingLeft: '20px', 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)',
              margin: 0,
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              {result.normal_findings.map((finding, index) => (
                <li key={index}>{finding}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Рекомендации */}
        {result.recommendations && (
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Рекомендации
            </h4>
            <div style={{ 
              display: 'flex', 
              flexDirection: 'column', 
              gap: '8px', 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)' 
            }}>
              {result.recommendations.additional_studies && result.recommendations.additional_studies.length > 0 && (
                <div>
                  <strong style={{ color: 'var(--mac-text-primary)' }}>Дополнительные исследования:</strong>
                  <ul style={{ 
                    listStyleType: 'disc', 
                    paddingLeft: '20px', 
                    marginTop: '4px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px'
                  }}>
                    {result.recommendations.additional_studies.map((study, index) => (
                      <li key={index}>{study}</li>
                    ))}
                  </ul>
                </div>
              )}
              {result.recommendations.follow_up && (
                <div>
                  <strong style={{ color: 'var(--mac-text-primary)' }}>Наблюдение:</strong> {result.recommendations.follow_up}
                </div>
              )}
              {result.recommendations.specialist_consultation && (
                <div>
                  <strong style={{ color: 'var(--mac-text-primary)' }}>Консультация специалиста:</strong> {result.recommendations.specialist_consultation}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Срочные находки */}
        {result.urgent_findings && (
          <MacOSCard style={{ 
            padding: '16px', 
            backgroundColor: 'var(--mac-bg-primary)', 
            border: '1px solid var(--mac-border)' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-danger)',
                margin: 0
              }}>
                Требует срочного внимания
              </h4>
            </div>
          </MacOSCard>
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
            <Brain style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
            AI Анализ Медицинских Изображений
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Загрузите медицинское изображение для автоматического анализа с помощью искусственного интеллекта
          </p>
        </div>

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
          gap: '24px' 
        }}>
          {/* Левая панель - загрузка и настройки */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Выбор типа изображения */}
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '12px' 
                }}>
                  Тип медицинского изображения
                </h3>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', 
                  gap: '12px' 
                }}>
                  {imageTypes.map((type) => (
                    <MacOSButton
                      key={type.value}
                      onClick={() => setImageType(type.value)}
                      variant={imageType === type.value ? 'primary' : 'outline'}
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'center', 
                        gap: '8px',
                        padding: '12px 16px',
                        fontSize: 'var(--mac-font-size-sm)',
                        minHeight: '48px',
                        backgroundColor: imageType === type.value ? 'var(--mac-accent-blue)' : 'transparent',
                        border: imageType === type.value ? 'none' : '1px solid var(--mac-border)',
                        color: imageType === type.value ? 'white' : 'var(--mac-text-primary)',
                        borderRadius: 'var(--mac-radius-md)',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                      }}
                    >
                      <div style={{ 
                        width: '16px', 
                        height: '16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}>
                        {type.icon}
                      </div>
                      <span style={{ 
                        whiteSpace: 'nowrap',
                        fontWeight: 'var(--mac-font-weight-medium)'
                      }}>
                        {type.label}
                      </span>
                    </MacOSButton>
                  ))}
                </div>
              </MacOSCard>

              {/* Загрузка файла */}
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '12px' 
                }}>
                  Загрузить изображение
                </h3>
                <div style={{ 
                  border: '2px dashed var(--mac-border)', 
                  borderRadius: 'var(--mac-radius-md)', 
                  padding: 0, 
                  textAlign: 'center',
                  backgroundColor: 'var(--mac-bg-secondary)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.target.style.borderColor = 'var(--mac-accent-blue)';
                  e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.borderColor = 'var(--mac-border)';
                  e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                    <Upload style={{ width: '48px', height: '48px', color: 'var(--mac-text-secondary)' }} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                      <label
                        htmlFor="file-upload"
                        style={{ 
                          cursor: 'pointer', 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          color: 'var(--mac-accent-blue)',
                          textDecoration: 'underline'
                        }}
                      >
                        <span>Выберите файл</span>
                        <input
                          id="file-upload"
                          name="file-upload"
                          type="file"
                          style={{ display: 'none' }}
                          accept="image/*"
                          onChange={handleFileSelect}
                        />
                      </label>
                      <span>или перетащите сюда</span>
                    </div>
                    <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: 0 }}>
                      PNG, JPG, JPEG до 10MB
                    </p>
                  </div>
                </div>
                {selectedFile && (
                  <p style={{ 
                    marginTop: '8px', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: '8px 0 0 0'
                  }}>
                    Выбран файл: {selectedFile.name}
                  </p>
                )}
              </MacOSCard>

              {/* Метаданные */}
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '16px' 
                }}>
                  Дополнительная информация
                </h3>
                
                {/* Общие поля */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                  gap: '16px',
                  marginBottom: '16px'
                }}>
                  <div>
                    <label style={{ 
                      display: 'block', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)', 
                      marginBottom: '4px' 
                    }}>
                      Возраст пациента
                    </label>
                    <MacOSInput
                      type="text"
                      value={metadata.patient_age}
                      onChange={(e) => handleMetadataChange('patient_age', e.target.value)}
                      placeholder="Например: 45 лет"
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
                      Пол
                    </label>
                    <MacOSSelect
                      value={metadata.patient_gender}
                      onChange={(e) => handleMetadataChange('patient_gender', e.target.value)}
                      options={[
                        { value: '', label: 'Не указан' },
                        { value: 'мужской', label: 'Мужской' },
                        { value: 'женский', label: 'Женский' }
                      ]}
                      style={{ width: '100%' }}
                    />
                  </div>
                </div>

                {/* Специфичные поля */}
                {renderMetadataFields()}

                {/* Клиническая информация */}
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '4px' 
                  }}>
                    Клиническая информация
                  </label>
                  <MacOSTextarea
                    value={metadata.clinical_info}
                    onChange={(e) => handleMetadataChange('clinical_info', e.target.value)}
                    placeholder="Жалобы, анамнез, предварительный диагноз"
                    rows={3}
                    style={{ width: '100%' }}
                  />
                </div>
              </MacOSCard>

              {/* Кнопка анализа */}
              <MacOSButton
                onClick={analyzeImage}
                disabled={!selectedFile || analyzing}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  gap: '8px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  border: 'none',
                  width: '100%',
                  padding: '12px 24px'
                }}
              >
                {analyzing ? (
                  <>
                    <Loader style={{ 
                      width: '20px', 
                      height: '20px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Анализируем...
                  </>
                ) : (
                  <>
                    <Brain style={{ width: '20px', height: '20px' }} />
                    Анализировать изображение
                  </>
                )}
              </MacOSButton>
            </div>

            {/* Правая панель - превью и результат */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Превью изображения */}
              {previewUrl && (
                <MacOSCard style={{ padding: '24px' }}>
                  <h3 style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)', 
                    marginBottom: '12px' 
                  }}>
                    Превью изображения
                  </h3>
                  <div style={{ 
                    border: '1px solid var(--mac-border)', 
                    borderRadius: 'var(--mac-radius-md)', 
                    padding: '16px',
                    backgroundColor: 'var(--mac-bg-secondary)',
                    textAlign: 'center'
                  }}>
                    <img
                      src={previewUrl}
                      alt="Preview"
                      style={{ 
                        maxWidth: '100%', 
                        height: 'auto', 
                        maxHeight: '256px', 
                        margin: '0 auto', 
                        borderRadius: 'var(--mac-radius-sm)'
                      }}
                    />
                  </div>
                </MacOSCard>
              )}

              {/* Результат анализа */}
              {renderResult()}
            </div>
          </div>
        </MacOSCard>
      </div>
    );
};

export default MedicalImageAnalyzer;



