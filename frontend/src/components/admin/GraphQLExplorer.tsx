// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Textarea,
  Alert,
  Skeleton,
} from '../ui/macos';
import {
  Database,
  Play,
  Copy,
  Download,
  RefreshCw,
  Code,
  Search,

  BookOpen,
  Zap,
  Activity } from
'lucide-react';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const GraphQLExplorer = () => {
  const { t } = useTranslation();
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
      name: t('admin2.gql_example_patients'),
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
      name: t('admin2.gql_example_doctors'),
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
      name: t('admin2.gql_example_appointments'),
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
      name: t('admin2.gql_example_visits'),
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
      name: t('admin2.gql_example_services'),
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
      name: t('admin2.gql_example_statistics'),
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
      name: t('admin2.gql_example_create_patient'),
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
          'fullName': t('admin2.gql2_example_full_name'),
          'phone': '+998901234567',
          'email': 'ivanov@example.com',
          'birthDate': '1990-01-01'
        }
      }
    },
    'createAppointment': {
      name: t('admin2.gql_example_create_appointment'),
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
          'notes': t('admin2.gql2_example_notes')
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
      const { data } = await api.post('/graphql', {
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
      });
      if (data?.data?.__schema) {
        setSchema(data.data.__schema);
      }
    } catch (error) {
      logger.error('Ошибка загрузки схемы GraphQL:', error);
    }
  };

  const executeQuery = async () => {
    if (!query.trim()) {
      setError(t('admin2.gql_error_empty_query'));
      return;
    }

    setLoading(true);
    setError(null);
    try {
      let parsedVariables = {};
      if (variables.trim()) {
        try {
          parsedVariables = JSON.parse(variables);
        } catch {
          setError(t('admin2.gql_error_invalid_json'));
          setLoading(false);
          return;
        }
      }

      const { data } = await api.post('/graphql', {
        query,
        variables: parsedVariables
      });
      setResult(data);

      if (data.errors) {
        setError(t('admin2.gql_error_graphql_errors'));
      }
    } catch (error) {
      logger.error('Ошибка выполнения GraphQL запроса:', error);
      setError(t('admin2.gql_error_execution', { message: error.message }));
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
    toast.success(t('admin2.gql_toast_copied'));
  };

  const downloadResult = () => {
    if (!result) {
      toast.error(t('admin2.gql_toast_no_result'));
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
    toast.success(t('admin2.gql_toast_downloaded'));
  };

  const formatJSON = (obj) => {
    return JSON.stringify(obj, null, 2);
  };

  const shellStyle = {
    padding: 'clamp(16px, 2vw, 24px)',
    borderRadius: '28px',
    border: '1px solid color-mix(in srgb, var(--mac-card-border), white 12%)',
    background: 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 7%) 0%, color-mix(in srgb, var(--mac-main-shell-bg), transparent 6%) 100%)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  const sectionCardStyle = {
    padding: 'var(--mac-spacing-6)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  const textareaStyle = {
    background: 'color-mix(in srgb, var(--mac-card-bg), white 4%)',
    border: '1px solid color-mix(in srgb, var(--mac-card-border), white 10%)',
    boxShadow: 'none'
  };

  const renderExplorerTab = () =>
  <div className="flex flex-col gap-6">
      {/* Отображение ошибок */}
      {error &&
    <Alert
      type="error"
      title={t('admin2.gql_alert_title_error')}
      description={error}
      onClose={() => setError(null)} />

    }

      {/* Примеры запросов */}
      <MacOSCard style={sectionCardStyle}>
        <h3 className="admin-m-0-0-16px-0-primary-d-flex-ai-center-gap-8-fs-lg-fw-semi-1">
          <BookOpen size={20} />
          {t('admin2.gql_heading_examples')}
        </h3>

        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-8">
          {Object.entries(queryExamples).map(([key, example]) =>
        <Button
          key={key}
          onClick={() => loadExample(key)}
          variant={selectedExample === key ? 'primary' : 'outline'}
          className="admin-p-8-fs-sm">
          
              {example.name}
            </Button>
        )}
        </div>
      </MacOSCard>

      {/* Редактор запроса */}
      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
        <MacOSCard style={sectionCardStyle}>
          <div className="admin-d-flex-fw-wrap-jc-between-ai-center-mb-16-gap-12-1">
            <h3 className="admin-m-0-primary-d-flex-ai-center-gap-8-fs-lg-fw-semi-1">
              <Code size={20} />
              {t('admin2.gql_heading_query')}
            </h3>
            <div className="admin-d-flex-gap-8">
              <Button
              onClick={copyQuery}
              variant="outline"
              className="admin-d-flex-ai-center-gap-4-p-4px-8px-fs-xs">
              
                <Copy size={14} />
                {t('admin2.gql_btn_copy')}
              </Button>
              <Button
              onClick={executeQuery}
              disabled={loading}
              variant="primary"
              className="admin-d-flex-ai-center-gap-4-p-4px-8px-fs-xs">
              
                {loading ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
                {loading ? t('admin2.gql_btn_executing') : t('admin2.gql_btn_execute')}
              </Button>
            </div>
          </div>

          <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('admin2.gql_placeholder_query')}
          minRows={10}
          maxRows={18}
          textareaStyle={textareaStyle}
          className="admin-w-100pct-ff-Monaco-Consolas-Cour-fs-sm-lh-1p5-rz-vertical-1" />
        

          <div className="mt-4">
            <label className="admin-d-block-fs-sm-fw-med-primary-mb-8">{t('admin2.gql_label_variables')}</label>
            <Textarea
            value={variables}
            onChange={(e) => setVariables(e.target.value)}
            placeholder='{"key": "value"}'
            minRows={5}
            maxRows={10}
            textareaStyle={textareaStyle}
            className="admin-w-100pct-ff-Monaco-Consolas-Cour-fs-sm-lh-1p5-rz-vertical" />
          
          </div>
        </MacOSCard>

        <MacOSCard style={sectionCardStyle}>
          <div className="admin-d-flex-fw-wrap-jc-between-ai-center-mb-16-gap-12">
            <h3 className="admin-m-0-primary-d-flex-ai-center-gap-8-fs-lg-fw-semi">
              <Activity size={20} />
              {t('admin2.gql_heading_result')}
            </h3>
            {result &&
          <Button
            onClick={downloadResult}
            variant="outline"
            className="admin-d-flex-ai-center-gap-4-p-4px-8px-fs-xs">
            
                <Download size={14} />
                {t('admin2.gql_btn_download')}
              </Button>
          }
          </div>

          <div className="admin-h-400-p-16-bg-color-mix-in-srgb-va-bd-1px-solid-color-mix--radius-var-mac-radius-md-ov-auto-ff-Monaco-Consolas-Cour-fs-sm-lh-1p5">
            {loading ?
          <Skeleton
            type="text"
            count={8}
            className="admin-h-100pct" /> :

          result ?
          <pre className="admin-m-0-ws-pre-wrap-col-dyn" style={{ '--admin-col0': result.errors ? 'var(--mac-error)' : 'var(--mac-text-primary)' }}>
                {formatJSON(result)}
              </pre> :

          <div className="admin-d-flex-ai-center-jc-center-h-100pct-tertiary">
                {t('admin2.gql_result_placeholder')}
              </div>
          }
          </div>
        </MacOSCard>
      </div>
    </div>;


  const renderSchemaTab = () =>
  <div className="flex flex-col gap-6">
      <MacOSCard style={sectionCardStyle}>
        <h3 className="admin-m-0-0-16px-0-primary-d-flex-ai-center-gap-8-fs-lg-fw-semi">
          <Database size={20} />
          {t('admin2.gql_heading_schema')}
        </h3>

        {schema ?
      <div className="admin-d-grid-gap-16">
            {schema.types.
        filter((type) => !type.name.startsWith('__') && type.fields).
        map((type, index) =>
        <div
          key={index}
          className="admin-p-16-bg-color-mix-in-srgb-va-bd-1px-solid-color-mix--radius-var-mac-radius-md">
          
                  <h4 className="admin-m-0-0-8px-0-accent-fs-var-mac-font-size-md-fw-semi">
                    {type.name}
                  </h4>
                  {type.description &&
          <p className="admin-m-0-0-8px-0-secondary-fs-sm">
                      {type.description}
                    </p>
          }
                  <div className="admin-d-grid-gap-4">
                    {type.fields?.slice(0, 10).map((field, fieldIndex) =>
            <div
              key={fieldIndex}
              className="admin-d-flex-jc-between-p-4px-8px-bg-color-mix-in-srgb-va-radius-var-mac-radius-sm-fs-xs">
              
                        <span className="admin-fw-semi-primary">
                          {field.name}
                        </span>
                        <span className="text-[var(--mac-text-secondary)]">
                          {field.type?.name || 'Unknown'}
                        </span>
                      </div>
            )}
                    {type.fields?.length > 10 &&
            <div className="admin-p-4-ta-center-tertiary-fs-xs">
                        {t('admin2.gql_more_fields', { count: type.fields.length - 10 })}
                      </div>
            }
                  </div>
                </div>
        )}
          </div> :

      <Skeleton
        type="card"
        count={3}
        className="admin-h-200" />

      }
      </MacOSCard>
    </div>;


  const tabs = [
  { id: 'explorer', label: t('admin2.gql_tab_explorer'), icon: Search },
  { id: 'schema', label: t('admin2.gql_tab_schema'), icon: Database }];


  return (
    <div style={shellStyle}>
      <div className="admin-d-flex-fw-wrap-ai-center-gap-16-mb-24">
        <Zap size={24} color="var(--mac-accent)" />
        <h2 className="admin-m-0-primary-fs-xl-fw-bold">
          GraphQL API Explorer
        </h2>
      </div>

      {/* Вкладки */}
      <div className="admin-d-flex-fw-wrap-gap-8-p-8-bd-1px-solid-color-mix--bg-color-mix-in-srgb-va-radius-18-mb-24">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-p-12px-18px-bd-1px-solid-transparen-cur-pointer-d-flex-ai-center-gap-8-radius-14-fs-sm-tr-all-var-mac-duration-bg-dyn-bsh-dyn-bd-c-dyn-col-dyn-fw-dyn" style={{ '--admin-bg0': activeTab === tab.id ? 'color-mix(in srgb, var(--mac-card-hover-bg), white 8%)' : 'transparent', '--admin-bsh1': activeTab === tab.id ? 'var(--mac-shadow-sm)' : 'none', '--admin-bd-c2': activeTab === tab.id ? 'color-mix(in srgb, var(--mac-card-border), white 12%)' : 'transparent', '--admin-col3': activeTab === tab.id ? 'var(--mac-accent)' : 'var(--mac-text-secondary)', '--admin-fw4': activeTab === tab.id ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)' }}>
              
              <Icon size={16} />
              {tab.label}
            </button>);

        })}
      </div>

      {/* Содержимое вкладок */}
      {activeTab === 'explorer' && renderExplorerTab()}
      {activeTab === 'schema' && renderSchemaTab()}
    </div>);

};

export default GraphQLExplorer;
