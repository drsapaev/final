import React, { useState, useEffect } from 'react';
import { Card, Button, Input, Label, Select } from '../ui/native';
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
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

const GraphQLExplorer = () => {
  const { theme, getColor, getSpacing } = useTheme();
  const [activeTab, setActiveTab] = useState('explorer');
  const [query, setQuery] = useState('');
  const [variables, setVariables] = useState('{}');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [schema, setSchema] = useState(null);
  const [selectedExample, setSelectedExample] = useState('');

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
        "filter": {
          "fullName": null
        },
        "pagination": {
          "page": 1,
          "perPage": 10
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
        "filter": {
          "active": true
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
        "filter": {
          "dateFrom": new Date().toISOString().split('T')[0] + "T00:00:00Z",
          "dateTo": new Date().toISOString().split('T')[0] + "T23:59:59Z"
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
        "filter": {
          "patientId": 1
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
        "filter": {
          "category": "consultation",
          "active": true
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
        "input": {
          "fullName": "Иванов Иван Иванович",
          "phone": "+998901234567",
          "email": "ivanov@example.com",
          "birthDate": "1990-01-01"
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
        "input": {
          "patientId": 1,
          "doctorId": 1,
          "serviceId": 1,
          "appointmentDate": new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
          "notes": "Первичная консультация"
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
      console.error('Ошибка загрузки схемы GraphQL:', error);
    }
  };

  const executeQuery = async () => {
    if (!query.trim()) {
      toast.error('Введите GraphQL запрос');
      return;
    }

    setLoading(true);
    try {
      let parsedVariables = {};
      if (variables.trim()) {
        try {
          parsedVariables = JSON.parse(variables);
        } catch (e) {
          toast.error('Неверный формат переменных JSON');
          setLoading(false);
          return;
        }
      }

      const response = await fetch('/api/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          query: query,
          variables: parsedVariables
        })
      });

      const data = await response.json();
      setResult(data);

      if (data.errors) {
        toast.error('GraphQL запрос выполнен с ошибками');
      } else {
        toast.success('GraphQL запрос выполнен успешно');
      }
    } catch (error) {
      console.error('Ошибка выполнения GraphQL запроса:', error);
      toast.error('Ошибка выполнения запроса');
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {/* Примеры запросов */}
      <Card style={{ padding: getSpacing('md') }}>
        <h3 style={{ 
          margin: `0 0 ${getSpacing('md')} 0`,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <BookOpen size={20} />
          Примеры запросов
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('sm') }}>
          {Object.entries(queryExamples).map(([key, example]) => (
            <Button
              key={key}
              onClick={() => loadExample(key)}
              style={{
                padding: getSpacing('sm'),
                backgroundColor: selectedExample === key ? getColor('primary', 100) : getColor('gray', 50),
                color: selectedExample === key ? getColor('primary', 700) : getColor('text', 700),
                border: `1px solid ${selectedExample === key ? getColor('primary', 300) : getColor('gray', 200)}`,
                fontSize: '14px'
              }}
            >
              {example.name}
            </Button>
          ))}
        </div>
      </Card>

      {/* Редактор запроса */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: getSpacing('lg') }}>
        <Card style={{ padding: getSpacing('lg') }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: getSpacing('md')
          }}>
            <h3 style={{ 
              margin: 0,
              color: getColor('text', 900),
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('sm')
            }}>
              <Code size={20} />
              GraphQL Запрос
            </h3>
            <div style={{ display: 'flex', gap: getSpacing('sm') }}>
              <Button 
                onClick={copyQuery}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: getSpacing('xs'),
                  padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
                  fontSize: '12px'
                }}
              >
                <Copy size={14} />
                Копировать
              </Button>
              <Button 
                onClick={executeQuery}
                disabled={loading}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: getSpacing('xs'),
                  backgroundColor: getColor('primary', 600),
                  color: 'white',
                  padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
                  fontSize: '12px'
                }}
              >
                {loading ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                {loading ? 'Выполняется...' : 'Выполнить'}
              </Button>
            </div>
          </div>

          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите GraphQL запрос..."
            style={{
              width: '100%',
              height: '300px',
              padding: getSpacing('md'),
              border: `1px solid ${getColor('gray', 300)}`,
              borderRadius: '6px',
              fontFamily: 'Monaco, Consolas, "Courier New", monospace',
              fontSize: '14px',
              lineHeight: '1.5',
              resize: 'vertical'
            }}
          />

          <div style={{ marginTop: getSpacing('md') }}>
            <Label>Переменные (JSON)</Label>
            <textarea
              value={variables}
              onChange={(e) => setVariables(e.target.value)}
              placeholder='{"key": "value"}'
              style={{
                width: '100%',
                height: '100px',
                padding: getSpacing('sm'),
                border: `1px solid ${getColor('gray', 300)}`,
                borderRadius: '6px',
                fontFamily: 'Monaco, Consolas, "Courier New", monospace',
                fontSize: '12px',
                marginTop: getSpacing('xs')
              }}
            />
          </div>
        </Card>

        <Card style={{ padding: getSpacing('lg') }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: getSpacing('md')
          }}>
            <h3 style={{ 
              margin: 0,
              color: getColor('text', 900),
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('sm')
            }}>
              <Activity size={20} />
              Результат
            </h3>
            {result && (
              <Button 
                onClick={downloadResult}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: getSpacing('xs'),
                  padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
                  fontSize: '12px'
                }}
              >
                <Download size={14} />
                Скачать
              </Button>
            )}
          </div>

          <div style={{
            height: '400px',
            padding: getSpacing('md'),
            backgroundColor: getColor('gray', 50),
            border: `1px solid ${getColor('gray', 200)}`,
            borderRadius: '6px',
            overflow: 'auto',
            fontFamily: 'Monaco, Consolas, "Courier New", monospace',
            fontSize: '12px',
            lineHeight: '1.5'
          }}>
            {loading ? (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                height: '100%',
                color: getColor('text', 500)
              }}>
                <RefreshCw size={20} className="animate-spin" style={{ marginRight: getSpacing('sm') }} />
                Выполняется запрос...
              </div>
            ) : result ? (
              <pre style={{ 
                margin: 0, 
                whiteSpace: 'pre-wrap',
                color: result.errors ? getColor('red', 600) : getColor('text', 700)
              }}>
                {formatJSON(result)}
              </pre>
            ) : (
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                height: '100%',
                color: getColor('text', 400)
              }}>
                Результат появится здесь после выполнения запроса
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );

  const renderSchemaTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ 
          margin: `0 0 ${getSpacing('md')} 0`,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Database size={20} />
          GraphQL Схема
        </h3>

        {schema ? (
          <div style={{ display: 'grid', gap: getSpacing('md') }}>
            {schema.types
              .filter(type => !type.name.startsWith('__') && type.fields)
              .map((type, index) => (
                <div
                  key={index}
                  style={{
                    padding: getSpacing('md'),
                    border: `1px solid ${getColor('gray', 200)}`,
                    borderRadius: '6px',
                    backgroundColor: getColor('gray', 50)
                  }}
                >
                  <h4 style={{ 
                    margin: `0 0 ${getSpacing('sm')} 0`,
                    color: getColor('primary', 600),
                    fontSize: '16px'
                  }}>
                    {type.name}
                  </h4>
                  {type.description && (
                    <p style={{ 
                      margin: `0 0 ${getSpacing('sm')} 0`,
                      color: getColor('text', 600),
                      fontSize: '14px'
                    }}>
                      {type.description}
                    </p>
                  )}
                  <div style={{ display: 'grid', gap: getSpacing('xs') }}>
                    {type.fields?.slice(0, 10).map((field, fieldIndex) => (
                      <div
                        key={fieldIndex}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
                          backgroundColor: 'white',
                          borderRadius: '4px',
                          fontSize: '12px'
                        }}
                      >
                        <span style={{ fontWeight: 'bold', color: getColor('text', 800) }}>
                          {field.name}
                        </span>
                        <span style={{ color: getColor('text', 500) }}>
                          {field.type?.name || 'Unknown'}
                        </span>
                      </div>
                    ))}
                    {type.fields?.length > 10 && (
                      <div style={{ 
                        padding: getSpacing('xs'),
                        textAlign: 'center',
                        color: getColor('text', 500),
                        fontSize: '12px'
                      }}>
                        ... и еще {type.fields.length - 10} полей
                      </div>
                    )}
                  </div>
                </div>
              ))}
          </div>
        ) : (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center',
            height: '200px',
            color: getColor('text', 500)
          }}>
            <RefreshCw size={20} className="animate-spin" style={{ marginRight: getSpacing('sm') }} />
            Загрузка схемы...
          </div>
        )}
      </Card>
    </div>
  );

  const tabs = [
    { id: 'explorer', label: 'Исследователь', icon: Search },
    { id: 'schema', label: 'Схема', icon: Database }
  ];

  return (
    <div style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: getSpacing('md'),
        marginBottom: getSpacing('lg')
      }}>
        <Zap size={24} color={getColor('primary', 600)} />
        <h2 style={{ 
          margin: 0, 
          color: getColor('text', 900),
          fontSize: '24px',
          fontWeight: 'bold'
        }}>
          GraphQL API Explorer
        </h2>
      </div>

      {/* Вкладки */}
      <div style={{ 
        display: 'flex', 
        borderBottom: `1px solid ${getColor('gray', 200)}`,
        marginBottom: getSpacing('lg')
      }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: `${getSpacing('md')} ${getSpacing('lg')}`,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: getSpacing('sm'),
                borderBottom: activeTab === tab.id ? `2px solid ${getColor('primary', 600)}` : '2px solid transparent',
                color: activeTab === tab.id ? getColor('primary', 600) : getColor('text', 600),
                fontWeight: activeTab === tab.id ? 'bold' : 'normal'
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

