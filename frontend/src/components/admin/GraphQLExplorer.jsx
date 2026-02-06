import React, { useState, useEffect } from 'react';
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSBadge,
  MacOSAlert,
  MacOSLoadingSkeleton
} from '../ui/macos';
import {
  Database,
  Play,
  Copy,
  Download,
  RefreshCw,
  Code,
  Search,
  Filter,
  BookOpen,
  Zap,
  Activity
} from 'lucide-react';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';

const GraphQLExplorer = () => {
  const [activeTab, setActiveTab] = useState('explorer');
  const [query, setQuery] = useState('');
  const [variables, setVariables] = useState('{}');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [schema, setSchema] = useState(null);
  const [selectedExample, setSelectedExample] = useState('');
  const [error, setError] = useState(null);

  // Примеры GraphQL запросов
  const queryExamples = {
    'patients': {
      name: 'Получить список пациентов',
      query: `query GetPatients($filter: PatientFilter, $pagination: PaginationInput) {
  patients(filter: $filter, pagination: $pagination) {
    items {
      id
      fullName
      phone
      email
      birthDate
      createdAt
    }
    pagination {
      page
      perPage
      total
      pages
      hasNext
      hasPrev
    }
  }
}`,
      variables: {
        'filter': {
          'fullName': null
        },
        'pagination': {
          'page': 1,
          'perPage': 10
        }
      }
    },
    'doctors': {
      name: 'Получить список врачей',
      query: `query GetDoctors($filter: DoctorFilter) {
  doctors(filter: $filter) {
    items {
      id
      specialty
      cabinet
      priceDefault
      active
      user {
        id
        fullName
        email
        phone
      }
    }
    pagination {
      total
      pages
    }
  }
}`,
      variables: {
        'filter': {
          'active': true
        }
      }
    },
    'appointments': {
      name: 'Получить записи за сегодня',
      query: `query GetTodayAppointments($filter: AppointmentFilter) {
  appointments(filter: $filter) {
    items {
      id
      appointmentDate
      status
      paymentStatus
      patient {
        fullName
        phone
      }
      doctor {
        specialty
        user {
          fullName
        }
      }
      service {
        name
        price
      }
    }
  }
}`,
      variables: {
        'filter': {
          'dateFrom': new Date().toISOString().split('T')[0] + 'T00:00:00Z',
          'dateTo': new Date().toISOString().split('T')[0] + 'T23:59:59Z'
        }
      }
    },
    'visits': {
      name: 'Получить визиты пациента',
      query: `query GetPatientVisits($filter: VisitFilter) {
  visits(filter: $filter) {
    items {
      id
      visitDate
      status
      discountMode
      allFree
      totalAmount
      paymentStatus
      doctor {
        specialty
        user {
          fullName
        }
      }
    }
  }
}`,
      variables: {
        'filter': {
          'patientId': 1
        }
      }
    },
    'services': {
      name: 'Получить услуги по категории',
      query: `query GetServicesByCategory($filter: ServiceFilter) {
  services(filter: $filter) {
    items {
      id
      name
      code
      price
      category
      description
      durationMinutes
      active
      doctor {
        specialty
        user {
          fullName
        }
      }
    }
  }
}`,
      variables: {
        'filter': {
          'category': 'consultation',
          'active': true
        }
      }
    },
    'statistics': {
      name: 'Получить статистику',
      query: `query GetStatistics {
  appointmentStats {
    total
    today
    thisWeek
    thisMonth
  }
  visitStats {
    total
    today
    totalRevenue
  }
  queueStats {
    totalEntries
    activeQueues
    averageWaitTime
  }
}`,
      variables: {}
    },
    'createPatient': {
      name: 'Создать пациента (мутация)',
      query: `mutation CreatePatient($input: PatientInput!) {
  createPatient(input: $input) {
    success
    message
    errors
    patient {
      id
      fullName
      phone
      email
      createdAt
    }
  }
}`,
      variables: {
        'input': {
          'fullName': 'Иванов Иван Иванович',
          'phone': '+998901234567',
          'email': 'ivanov@example.com',
          'birthDate': '1990-01-01'
        }
      }
    },
    'createAppointment': {
      name: 'Создать запись (мутация)',
      query: `mutation CreateAppointment($input: AppointmentInput!) {
  createAppointment(input: $input) {
    success
    message
    errors
    appointment {
      id
      appointmentDate
      status
      patient {
        fullName
      }
      doctor {
        user {
          fullName
        }
      }
      service {
        name
        price
      }
    }
  }
}`,
      variables: {
        'input': {
          'patientId': 1,
          'doctorId': 1,
          'serviceId': 1,
          'appointmentDate': new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
          'notes': 'Первичная консультация'
        }
      }
    }
  };

  useEffect(() => {
    // Загружаем схему GraphQL при монтировании компонента
    loadSchema();
  }, []);

  const loadSchema = async () => {
    try {
      const response = await fetch('/api/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: `
            query IntrospectionQuery {
              __schema {
                types {
                  name
                  description
                  fields {
                    name
                    description
                    type {
                      name
                    }
                  }
                }
              }
            }
          `
        })
      });

      if (response.ok) {
        const data = await response.json();
        setSchema(data.data.__schema);
      }
    } catch (error) {
      logger.error('Ошибка загрузки схемы GraphQL:', error);
    }
  };

  const executeQuery = async () => {
    if (!query.trim()) {
      setError('Введите GraphQL запрос');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      let parsedVariables = {};
      if (variables.trim()) {
        try {
          parsedVariables = JSON.parse(variables);
        } catch (e) {
          setError('Неверный формат переменных JSON');
          setLoading(false);
          return;
        }
      }

      const response = await fetch('/api/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify({
          query: query,
          variables: parsedVariables
        })
      });

      const data = await response.json();
      setResult(data);

      if (data.errors) {
        setError('GraphQL запрос выполнен с ошибками');
      }
    } catch (error) {
      logger.error('Ошибка выполнения GraphQL запроса:', error);
      setError('Ошибка выполнения запроса: ' + error.message);
      setResult({ error: error.message });
    } finally {
      setLoading(false);
    }
  };

  const loadExample = (exampleKey) => {
    const example = queryExamples[exampleKey];
    if (example) {
      setQuery(example.query);
      setVariables(JSON.stringify(example.variables, null, 2));
      setSelectedExample(exampleKey);
    }
  };

  const copyQuery = () => {
    navigator.clipboard.writeText(query);
    toast.success('Запрос скопирован в буфер обмена');
  };

  const downloadResult = () => {
    if (!result) {
      toast.error('Нет результата для скачивания');
      return;
    }

    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `graphql-result-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Результат скачан');
  };

  const formatJSON = (obj) => {
    return JSON.stringify(obj, null, 2);
  };

  const renderExplorerTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Отображение ошибок */}
      {error && (
        <MacOSAlert
          type="error"
          title="Ошибка"
          description={error}
          onClose={() => setError(null)}
        />
      )}

      {/* Примеры запросов */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{
          margin: '0 0 16px 0',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          <BookOpen size={20} />
          Примеры запросов
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
          {Object.entries(queryExamples).map(([key, example]) => (
            <MacOSButton
              key={key}
              onClick={() => loadExample(key)}
              variant={selectedExample === key ? 'primary' : 'outline'}
              style={{
                padding: '8px',
                fontSize: 'var(--mac-font-size-sm)'
              }}
            >
              {example.name}
            </MacOSButton>
          ))}
        </div>
      </MacOSCard>

      {/* Редактор запроса */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h3 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              <Code size={20} />
              GraphQL Запрос
            </h3>
            <div style={{ display: 'flex', gap: '8px' }}>
              <MacOSButton
                onClick={copyQuery}
                variant="outline"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 8px',
                  fontSize: 'var(--mac-font-size-xs)'
                }}
              >
                <Copy size={14} />
                Копировать
              </MacOSButton>
              <MacOSButton
                onClick={executeQuery}
                disabled={loading}
                variant="primary"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 8px',
                  fontSize: 'var(--mac-font-size-xs)'
                }}
              >
                {loading ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                {loading ? 'Выполняется...' : 'Выполнить'}
              </MacOSButton>
            </div>
          </div>

          <MacOSTextarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите GraphQL запрос..."
            style={{
              width: '100%',
              height: '300px',
              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
              fontSize: 'var(--mac-font-size-sm)',
              lineHeight: '1.5',
              resize: 'vertical'
            }}
          />

          <div style={{ marginTop: '16px' }}>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>Переменные (JSON)</label>
            <MacOSTextarea
              value={variables}
              onChange={(e) => setVariables(e.target.value)}
              placeholder='{"key": "value"}'
              style={{
                width: '100%',
                height: '100px',
                fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                fontSize: 'var(--mac-font-size-sm)',
                lineHeight: '1.5',
                resize: 'vertical'
              }}
            />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h3 style={{
              margin: 0,
              color: 'var(--mac-text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              <Activity size={20} />
              Результат
            </h3>
            {result && (
              <MacOSButton
                onClick={downloadResult}
                variant="outline"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '4px 8px',
                  fontSize: 'var(--mac-font-size-xs)'
                }}
              >
                <Download size={14} />
                Скачать
              </MacOSButton>
            )}
          </div>

          <div style={{
            height: '400px',
            padding: '16px',
            backgroundColor: 'var(--mac-bg-secondary)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            overflow: 'auto',
            fontFamily: 'Monaco, Consolas, "Courier New", monospace',
            fontSize: 'var(--mac-font-size-sm)',
            lineHeight: '1.5'
          }}>
            {loading ? (
              <MacOSLoadingSkeleton
                type="text"
                count={8}
                style={{ height: '100%' }}
              />
            ) : result ? (
              <pre style={{
                margin: 0,
                whiteSpace: 'pre-wrap',
                color: result.errors ? 'var(--mac-error)' : 'var(--mac-text-primary)'
              }}>
                {formatJSON(result)}
              </pre>
            ) : (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: 'var(--mac-text-tertiary)'
              }}>
                Результат появится здесь после выполнения запроса
              </div>
            )}
          </div>
        </MacOSCard>
      </div>
    </div>
  );

  const renderSchemaTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{
          margin: '0 0 16px 0',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          <Database size={20} />
          GraphQL Схема
        </h3>

        {schema ? (
          <div style={{ display: 'grid', gap: '16px' }}>
            {schema.types
              .filter(type => !type.name.startsWith('__') && type.fields)
              .map((type, index) => (
                <div
                  key={index}
                  style={{
                    padding: '16px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    backgroundColor: 'var(--mac-bg-secondary)'
                  }}
                >
                  <h4 style={{
                    margin: '0 0 8px 0',
                    color: 'var(--mac-accent)',
                    fontSize: 'var(--mac-font-size-md)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    {type.name}
                  </h4>
                  {type.description && (
                    <p style={{
                      margin: '0 0 8px 0',
                      color: 'var(--mac-text-secondary)',
                      fontSize: 'var(--mac-font-size-sm)'
                    }}>
                      {type.description}
                    </p>
                  )}
                  <div style={{ display: 'grid', gap: '4px' }}>
                    {type.fields?.slice(0, 10).map((field, fieldIndex) => (
                      <div
                        key={fieldIndex}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: '4px 8px',
                          backgroundColor: 'var(--mac-bg-primary)',
                          borderRadius: 'var(--mac-radius-sm)',
                          fontSize: 'var(--mac-font-size-xs)'
                        }}
                      >
                        <span style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                          {field.name}
                        </span>
                        <span style={{ color: 'var(--mac-text-secondary)' }}>
                          {field.type?.name || 'Unknown'}
                        </span>
                      </div>
                    ))}
                    {type.fields?.length > 10 && (
                      <div style={{
                        padding: '4px',
                        textAlign: 'center',
                        color: 'var(--mac-text-tertiary)',
                        fontSize: 'var(--mac-font-size-xs)'
                      }}>
                        ... и еще {type.fields.length - 10} полей
                      </div>
                    )}
                  </div>
                </div>
              ))}
          </div>
        ) : (
          <MacOSLoadingSkeleton
            type="card"
            count={3}
            style={{ height: '200px' }}
          />
        )}
      </MacOSCard>
    </div>
  );

  const tabs = [
    { id: 'explorer', label: 'Исследователь', icon: Search },
    { id: 'schema', label: 'Схема', icon: Database }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Zap size={24} color="var(--mac-accent)" />
        <h2 style={{
          margin: 0,
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-xl)',
          fontWeight: 'var(--mac-font-weight-bold)'
        }}>
          GraphQL API Explorer
        </h2>
      </div>

      {/* Вкладки */}
      <div style={{
        display: 'flex',
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '16px 24px',
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                borderBottom: activeTab === tab.id ? '2px solid var(--mac-accent)' : '2px solid transparent',
                color: activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                fontWeight: activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Содержимое вкладок */}
      {activeTab === 'explorer' && renderExplorerTab()}
      {activeTab === 'schema' && renderSchemaTab()}
    </div>
  );
};

export default GraphQLExplorer;

