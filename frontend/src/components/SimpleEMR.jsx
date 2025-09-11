import React, { useState } from 'react';

const SimpleEMR = () => {
  const [records, setRecords] = useState([
    {
      id: 1,
      patientName: 'Иван Петров',
      patientId: 'P001',
      doctor: 'Др. Сидорова',
      date: '2024-01-15',
      diagnosis: 'Гипертония',
      symptoms: 'Головная боль, повышенное давление',
      treatment: 'Лозартан 50мг, контроль давления',
      status: 'Активна'
    },
    {
      id: 2,
      patientName: 'Мария Козлова',
      patientId: 'P002',
      doctor: 'Др. Волков',
      date: '2024-01-14',
      diagnosis: 'ОРВИ',
      symptoms: 'Кашель, насморк, температура 37.5°C',
      treatment: 'Парацетамол, обильное питье',
      status: 'Вылечена'
    },
    {
      id: 3,
      patientName: 'Алексей Смирнов',
      patientId: 'P003',
      doctor: 'Др. Петрова',
      date: '2024-01-13',
      diagnosis: 'Сахарный диабет',
      symptoms: 'Жажда, частое мочеиспускание',
      treatment: 'Метформин 500мг, диета',
      status: 'Активна'
    }
  ]);

  const [newRecord, setNewRecord] = useState({
    patientName: '',
    patientId: '',
    doctor: '',
    diagnosis: '',
    symptoms: '',
    treatment: ''
  });

  const [showAddForm, setShowAddForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('Все');

  const handleAddRecord = () => {
    if (newRecord.patientName && newRecord.diagnosis) {
      const record = {
        id: records.length + 1,
        ...newRecord,
        date: new Date().toISOString().split('T')[0],
        status: 'Активна'
      };
      setRecords([...records, record]);
      setNewRecord({
        patientName: '',
        patientId: '',
        doctor: '',
        diagnosis: '',
        symptoms: '',
        treatment: ''
      });
      setShowAddForm(false);
    }
  };

  const updateRecordStatus = (id, status) => {
    setRecords(records.map(record => 
      record.id === id ? { ...record, status } : record
    ));
  };

  const deleteRecord = (id) => {
    setRecords(records.filter(record => record.id !== id));
  };

  const filteredRecords = records.filter(record => {
    const matchesSearch = record.patientName.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         record.diagnosis.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         record.doctor.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = filterStatus === 'Все' || record.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#1976d2', marginBottom: '20px' }}>
        🏥 Электронные Медицинские Записи (EMR)
      </h1>

      {/* Поиск и фильтры */}
      <div style={{ 
        display: 'flex', 
        gap: '10px', 
        marginBottom: '20px',
        flexWrap: 'wrap',
        alignItems: 'center'
      }}>
        <input
          type="text"
          placeholder="Поиск по пациенту, диагнозу или врачу..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            width: '300px',
            fontSize: '14px'
          }}
        />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        >
          <option value="Все">Все статусы</option>
          <option value="Активна">Активные</option>
          <option value="Вылечена">Вылеченные</option>
          <option value="Архивная">Архивные</option>
        </select>
        <button 
          onClick={() => setShowAddForm(!showAddForm)}
          style={{
            padding: '8px 16px',
            backgroundColor: '#4caf50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px'
          }}
        >
          {showAddForm ? 'Отмена' : '+ Новая запись'}
        </button>
      </div>

      {/* Форма добавления */}
      {showAddForm && (
        <div style={{
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px',
          backgroundColor: '#f9f9f9'
        }}>
          <h3>Добавить новую медицинскую запись</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '10px' }}>
            <input
              type="text"
              placeholder="Имя пациента"
              value={newRecord.patientName}
              onChange={(e) => setNewRecord({...newRecord, patientName: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <input
              type="text"
              placeholder="ID пациента"
              value={newRecord.patientId}
              onChange={(e) => setNewRecord({...newRecord, patientId: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <input
              type="text"
              placeholder="Врач"
              value={newRecord.doctor}
              onChange={(e) => setNewRecord({...newRecord, doctor: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <input
              type="text"
              placeholder="Диагноз"
              value={newRecord.diagnosis}
              onChange={(e) => setNewRecord({...newRecord, diagnosis: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <textarea
              placeholder="Симптомы"
              value={newRecord.symptoms}
              onChange={(e) => setNewRecord({...newRecord, symptoms: e.target.value})}
              style={{ 
                padding: '8px', 
                border: '1px solid #ddd', 
                borderRadius: '4px',
                gridColumn: '1 / -1',
                minHeight: '60px',
                resize: 'vertical'
              }}
            />
            <textarea
              placeholder="Лечение"
              value={newRecord.treatment}
              onChange={(e) => setNewRecord({...newRecord, treatment: e.target.value})}
              style={{ 
                padding: '8px', 
                border: '1px solid #ddd', 
                borderRadius: '4px',
                gridColumn: '1 / -1',
                minHeight: '60px',
                resize: 'vertical'
              }}
            />
          </div>
          <button 
            onClick={handleAddRecord}
            style={{
              padding: '10px 20px',
              backgroundColor: '#1976d2',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              marginTop: '10px'
            }}
          >
            Добавить запись
          </button>
        </div>
      )}

      {/* Статистика */}
      <div style={{ 
        display: 'flex', 
        gap: '20px', 
        marginBottom: '20px',
        flexWrap: 'wrap'
      }}>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#e3f2fd', 
          borderRadius: '4px',
          border: '1px solid #1976d2'
        }}>
          Всего записей: <strong>{records.length}</strong>
        </div>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#fff3e0', 
          borderRadius: '4px',
          border: '1px solid #ff9800'
        }}>
          Активных: <strong>{records.filter(r => r.status === 'Активна').length}</strong>
        </div>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#e8f5e8', 
          borderRadius: '4px',
          border: '1px solid #4caf50'
        }}>
          Вылеченных: <strong>{records.filter(r => r.status === 'Вылечена').length}</strong>
        </div>
      </div>

      {/* Таблица записей */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse', 
          border: '1px solid #ddd',
          backgroundColor: 'white'
        }}>
          <thead>
            <tr style={{ backgroundColor: '#f5f5f5' }}>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>ID</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Пациент</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Врач</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Дата</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Диагноз</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Статус</th>
              <th style={{ padding: '12px', textAlign: 'left', border: '1px solid #ddd' }}>Действия</th>
            </tr>
          </thead>
          <tbody>
            {filteredRecords.map(record => (
              <tr key={record.id}>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{record.id}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <div>
                    <strong>{record.patientName}</strong>
                    <br />
                    <small style={{ color: '#666' }}>ID: {record.patientId}</small>
                  </div>
                </td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{record.doctor}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>{record.date}</td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <div>
                    <strong>{record.diagnosis}</strong>
                    <br />
                    <small style={{ color: '#666' }}>{record.symptoms}</small>
                  </div>
                </td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    backgroundColor: record.status === 'Активна' ? '#ff9800' : 
                                   record.status === 'Вылечена' ? '#4caf50' : '#9e9e9e',
                    color: 'white',
                    fontSize: '12px'
                  }}>
                    {record.status}
                  </span>
                </td>
                <td style={{ padding: '12px', border: '1px solid #ddd' }}>
                  <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => updateRecordStatus(record.id, 'Вылечена')}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#4caf50',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      Вылечена
                    </button>
                    <button
                      onClick={() => updateRecordStatus(record.id, 'Архивная')}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#9e9e9e',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      Архив
                    </button>
                    <button
                      onClick={() => deleteRecord(record.id)}
                      style={{
                        padding: '4px 8px',
                        backgroundColor: '#f44336',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '11px'
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {filteredRecords.length === 0 && (
        <div style={{ 
          textAlign: 'center', 
          padding: '40px', 
          color: '#666',
          backgroundColor: '#f9f9f9',
          borderRadius: '8px',
          marginTop: '20px'
        }}>
          <p>Записи не найдены</p>
        </div>
      )}
    </div>
  );
};

export default SimpleEMR;
