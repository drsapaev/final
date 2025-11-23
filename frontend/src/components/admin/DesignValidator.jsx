import React, { useState, useEffect } from 'react';
import { Card, Button, Badge } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { validateComponentDesign, generateDesignReport } from '../../utils/designValidator';

/**
 * Компонент для валидации дизайна панелей
 */
const DesignValidator = ({ componentName = 'CardiologistPanel', onValidationComplete }) => {
  const { getColor, getSpacing, getFontSize } = useTheme();
  const [isValidating, setIsValidating] = useState(false);
  const [validationResults, setValidationResults] = useState(null);
  const [selectedComponent, setSelectedComponent] = useState('CardiologistPanelUnified');

  // Список доступных компонентов для проверки
  const availableComponents = [
    { id: 'CardiologistPanelUnified', name: 'Панель кардиолога', path: 'frontend/src/pages/CardiologistPanelUnified.jsx' },
    { id: 'RegistrarPanel', name: 'Панель регистратора', path: 'frontend/src/pages/RegistrarPanel.jsx' },
    { id: 'DentistPanelUnified', name: 'Панель стоматолога', path: 'frontend/src/pages/DentistPanelUnified.jsx' },
    { id: 'AdminPanel', name: 'Админ панель', path: 'frontend/src/pages/AdminPanel.jsx' }
  ];

  const validateComponent = async (componentId) => {
    setIsValidating(true);

    try {
      // В реальном приложении здесь будет загрузка кода компонента
      // Пока симулируем валидацию
      const mockCode = `
        const styles = {
          backgroundColor: '#ffffff',
          padding: '16px',
          fontSize: '14px',
          color: '#333333',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
        };
      `;

      const results = validateComponentDesign(mockCode, componentId);
      setValidationResults(results);

      if (onValidationComplete) {
        onValidationComplete(results);
      }
    } catch (error) {
      console.error('Ошибка валидации:', error);
    } finally {
      setIsValidating(false);
    }
  };

  const getComplianceColor = (score) => {
    if (score >= 90) return 'success';
    if (score >= 70) return 'warning';
    return 'danger';
  };

  const getComplianceText = (score) => {
    if (score >= 90) return 'Отличное соответствие';
    if (score >= 70) return 'Хорошее соответствие';
    if (score >= 50) return 'Требует улучшений';
    return 'Критические проблемы';
  };

  return (
    <Card padding="lg">
      <div style={{
        fontSize: getFontSize('lg'),
        fontWeight: '600',
        marginBottom: getSpacing('lg'),
        color: getColor('text')
      }}>
        🛠️ Валидация дизайн-системы
      </div>

      <div style={{ marginBottom: getSpacing('lg') }}>
        <label style={{
          display: 'block',
          fontSize: getFontSize('sm'),
          fontWeight: '500',
          color: getColor('textSecondary'),
          marginBottom: getSpacing('sm')
        }}>
          Выберите компонент для проверки:
        </label>
        <select
          value={selectedComponent}
          onChange={(e) => setSelectedComponent(e.target.value)}
          style={{
            width: '100%',
            padding: `${getSpacing('sm')} ${getSpacing('md')}`,
            border: `1px solid ${getColor('border')}`,
            borderRadius: '6px',
            backgroundColor: getColor('surface'),
            color: getColor('text'),
            fontSize: getFontSize('base')
          }}
        >
          {availableComponents.map(comp => (
            <option key={comp.id} value={comp.id}>{comp.name}</option>
          ))}
        </select>
      </div>

      <Button
        onClick={() => validateComponent(selectedComponent)}
        disabled={isValidating}
        style={{ marginBottom: getSpacing('lg') }}
      >
        {isValidating ? 'Проверяем...' : 'Запустить валидацию'}
      </Button>

      {validationResults && (
        <div style={{
          border: `1px solid ${getColor('border')}`,
          borderRadius: '8px',
          padding: getSpacing('lg'),
          backgroundColor: getColor('surface')
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: getSpacing('lg')
          }}>
            <h3 style={{
              fontSize: getFontSize('lg'),
              fontWeight: '600',
              color: getColor('text')
            }}>
              Результаты валидации: {validationResults.component}
            </h3>
            <Badge variant={getComplianceColor(validationResults.summary.complianceScore)}>
              {getComplianceText(validationResults.summary.complianceScore)} ({validationResults.summary.complianceScore}%)
            </Badge>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
            gap: getSpacing('lg'),
            marginBottom: getSpacing('lg')
          }}>
            <div style={{
              padding: getSpacing('md'),
              backgroundColor: getColor('background'),
              borderRadius: '6px',
              border: `1px solid ${getColor('border')}`
            }}>
              <div style={{
                fontSize: getFontSize('sm'),
                color: getColor('textSecondary'),
                marginBottom: getSpacing('xs')
              }}>Ошибки</div>
              <div style={{
                fontSize: getFontSize('xl'),
                fontWeight: '600',
                color: getColor('danger', 600)
              }}>{validationResults.summary.totalErrors}</div>
            </div>

            <div style={{
              padding: getSpacing('md'),
              backgroundColor: getColor('background'),
              borderRadius: '6px',
              border: `1px solid ${getColor('border')}`
            }}>
              <div style={{
                fontSize: getFontSize('sm'),
                color: getColor('textSecondary'),
                marginBottom: getSpacing('xs')
              }}>Предупреждения</div>
              <div style={{
                fontSize: getFontSize('xl'),
                fontWeight: '600',
                color: getColor('warning', 600)
              }}>{validationResults.summary.totalWarnings}</div>
            </div>

            <div style={{
              padding: getSpacing('md'),
              backgroundColor: getColor('background'),
              borderRadius: '6px',
              border: `1px solid ${getColor('border')}`
            }}>
              <div style={{
                fontSize: getFontSize('sm'),
                color: getColor('textSecondary'),
                marginBottom: getSpacing('xs')
              }}>Соответствие</div>
              <div style={{
                fontSize: getFontSize('xl'),
                fontWeight: '600',
                color: getColor('success', 600)
              }}>{validationResults.summary.complianceScore}%</div>
            </div>
          </div>

          {/* Детальные результаты */}
          {Object.entries(validationResults).map(([category, result]) => {
            if (category === 'component' || category === 'summary') return null;

            return (
              <div key={category} style={{ marginBottom: getSpacing('lg') }}>
                <h4 style={{
                  fontSize: getFontSize('base'),
                  fontWeight: '600',
                  marginBottom: getSpacing('md'),
                  color: getColor('text'),
                  textTransform: 'capitalize'
                }}>
                  {category === 'colors' && 'Цвета'}
                  {category === 'spacing' && 'Отступы'}
                  {category === 'typography' && 'Типография'}
                  {category === 'shadows' && 'Тени'}
                </h4>

                {result.errors.length > 0 && (
                  <div style={{ marginBottom: getSpacing('md') }}>
                    <div style={{
                      fontSize: getFontSize('sm'),
                      fontWeight: '600',
                      color: getColor('danger', 600),
                      marginBottom: getSpacing('sm')
                    }}>
                      Ошибки ({result.errors.length}):
                    </div>
                    <div style={{
                      padding: getSpacing('md'),
                      backgroundColor: getColor('danger', 50),
                      border: `1px solid ${getColor('danger', 200)}`,
                      borderRadius: '6px'
                    }}>
                      {result.errors.map((error, index) => (
                        <div key={index} style={{
                          fontSize: getFontSize('sm'),
                          color: getColor('danger', 700),
                          marginBottom: getSpacing('xs')
                        }}>
                          • {error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {result.warnings.length > 0 && (
                  <div>
                    <div style={{
                      fontSize: getFontSize('sm'),
                      fontWeight: '600',
                      color: getColor('warning', 600),
                      marginBottom: getSpacing('sm')
                    }}>
                      Предупреждения ({result.warnings.length}):
                    </div>
                    <div style={{
                      padding: getSpacing('md'),
                      backgroundColor: getColor('warning', 50),
                      border: `1px solid ${getColor('warning', 200)}`,
                      borderRadius: '6px'
                    }}>
                      {result.warnings.map((warning, index) => (
                        <div key={index} style={{
                          fontSize: getFontSize('sm'),
                          color: getColor('warning', 700),
                          marginBottom: getSpacing('xs')
                        }}>
                          • {warning}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};

export default DesignValidator;
