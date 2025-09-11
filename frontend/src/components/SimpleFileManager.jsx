import React, { useState } from 'react';

const SimpleFileManager = () => {
  const [files, setFiles] = useState([
    {
      id: 1,
      name: 'medical_report_001.pdf',
      type: 'PDF',
      size: '2.3 MB',
      uploadDate: '2024-01-15',
      category: 'Медицинские отчеты',
      uploadedBy: 'Др. Сидорова',
      patientId: 'P001'
    },
    {
      id: 2,
      name: 'xray_chest_002.jpg',
      type: 'JPG',
      size: '1.8 MB',
      uploadDate: '2024-01-14',
      category: 'Рентген',
      uploadedBy: 'Др. Волков',
      patientId: 'P002'
    },
    {
      id: 3,
      name: 'lab_results_003.xlsx',
      type: 'XLSX',
      size: '456 KB',
      uploadDate: '2024-01-13',
      category: 'Лабораторные анализы',
      uploadedBy: 'Лаборант Петрова',
      patientId: 'P003'
    },
    {
      id: 4,
      name: 'prescription_004.pdf',
      type: 'PDF',
      size: '124 KB',
      uploadDate: '2024-01-12',
      category: 'Рецепты',
      uploadedBy: 'Др. Козлов',
      patientId: 'P001'
    },
    {
      id: 5,
      name: 'mri_brain_005.dcm',
      type: 'DICOM',
      size: '15.2 MB',
      uploadDate: '2024-01-11',
      category: 'МРТ',
      uploadedBy: 'Др. Смирнова',
      patientId: 'P004'
    }
  ]);

  const [newFile, setNewFile] = useState({
    name: '',
    category: 'Медицинские отчеты',
    patientId: '',
    uploadedBy: ''
  });

  const [showAddForm, setShowAddForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('Все');
  const [filterType, setFilterType] = useState('Все');

  const handleAddFile = () => {
    if (newFile.name && newFile.patientId) {
      const file = {
        id: files.length + 1,
        ...newFile,
        type: getFileType(newFile.name),
        size: generateFileSize(),
        uploadDate: new Date().toISOString().split('T')[0]
      };
      setFiles([...files, file]);
      setNewFile({
        name: '',
        category: 'Медицинские отчеты',
        patientId: '',
        uploadedBy: ''
      });
      setShowAddForm(false);
    }
  };

  const getFileType = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    const typeMap = {
      'pdf': 'PDF',
      'jpg': 'JPG',
      'jpeg': 'JPG',
      'png': 'PNG',
      'xlsx': 'XLSX',
      'docx': 'DOCX',
      'dcm': 'DICOM',
      'txt': 'TXT'
    };
    return typeMap[ext] || 'FILE';
  };

  const generateFileSize = () => {
    const sizes = ['124 KB', '456 KB', '1.2 MB', '2.3 MB', '5.7 MB', '15.2 MB'];
    return sizes[Math.floor(Math.random() * sizes.length)];
  };

  const deleteFile = (id) => {
    setFiles(files.filter(file => file.id !== id));
  };

  const downloadFile = (file) => {
    // Симуляция скачивания
    alert(`Скачивание файла: ${file.name}`);
  };

  const filteredFiles = files.filter(file => {
    const matchesSearch = file.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         file.patientId.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         file.uploadedBy.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = filterCategory === 'Все' || file.category === filterCategory;
    const matchesType = filterType === 'Все' || file.type === filterType;
    return matchesSearch && matchesCategory && matchesType;
  });

  const getFileIcon = (type) => {
    const icons = {
      'PDF': '📄',
      'JPG': '🖼️',
      'PNG': '🖼️',
      'XLSX': '📊',
      'DOCX': '📝',
      'DICOM': '🏥',
      'TXT': '📄',
      'FILE': '📁'
    };
    return icons[type] || '📁';
  };

  const getCategoryColor = (category) => {
    const colors = {
      'Медицинские отчеты': '#e3f2fd',
      'Рентген': '#fff3e0',
      'Лабораторные анализы': '#e8f5e8',
      'Рецепты': '#fce4ec',
      'МРТ': '#f3e5f5',
      'УЗИ': '#e0f2f1'
    };
    return colors[category] || '#f5f5f5';
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1 style={{ color: '#1976d2', marginBottom: '20px' }}>
        📁 Файловый Менеджер
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
          placeholder="Поиск по имени файла, ID пациента или загрузившему..."
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
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        >
          <option value="Все">Все категории</option>
          <option value="Медицинские отчеты">Медицинские отчеты</option>
          <option value="Рентген">Рентген</option>
          <option value="Лабораторные анализы">Лабораторные анализы</option>
          <option value="Рецепты">Рецепты</option>
          <option value="МРТ">МРТ</option>
          <option value="УЗИ">УЗИ</option>
        </select>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          style={{
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px'
          }}
        >
          <option value="Все">Все типы</option>
          <option value="PDF">PDF</option>
          <option value="JPG">JPG</option>
          <option value="XLSX">XLSX</option>
          <option value="DICOM">DICOM</option>
          <option value="DOCX">DOCX</option>
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
          {showAddForm ? 'Отмена' : '+ Добавить файл'}
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
          <h3>Добавить новый файл</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '10px' }}>
            <input
              type="text"
              placeholder="Имя файла (с расширением)"
              value={newFile.name}
              onChange={(e) => setNewFile({...newFile, name: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <input
              type="text"
              placeholder="ID пациента"
              value={newFile.patientId}
              onChange={(e) => setNewFile({...newFile, patientId: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <input
              type="text"
              placeholder="Загрузил"
              value={newFile.uploadedBy}
              onChange={(e) => setNewFile({...newFile, uploadedBy: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            />
            <select
              value={newFile.category}
              onChange={(e) => setNewFile({...newFile, category: e.target.value})}
              style={{ padding: '8px', border: '1px solid #ddd', borderRadius: '4px' }}
            >
              <option value="Медицинские отчеты">Медицинские отчеты</option>
              <option value="Рентген">Рентген</option>
              <option value="Лабораторные анализы">Лабораторные анализы</option>
              <option value="Рецепты">Рецепты</option>
              <option value="МРТ">МРТ</option>
              <option value="УЗИ">УЗИ</option>
            </select>
          </div>
          <button 
            onClick={handleAddFile}
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
            Добавить файл
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
          Всего файлов: <strong>{files.length}</strong>
        </div>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#fff3e0', 
          borderRadius: '4px',
          border: '1px solid #ff9800'
        }}>
          PDF: <strong>{files.filter(f => f.type === 'PDF').length}</strong>
        </div>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#e8f5e8', 
          borderRadius: '4px',
          border: '1px solid #4caf50'
        }}>
          Изображения: <strong>{files.filter(f => f.type === 'JPG' || f.type === 'PNG').length}</strong>
        </div>
        <div style={{ 
          padding: '10px 15px', 
          backgroundColor: '#fce4ec', 
          borderRadius: '4px',
          border: '1px solid #e91e63'
        }}>
          DICOM: <strong>{files.filter(f => f.type === 'DICOM').length}</strong>
        </div>
      </div>

      {/* Список файлов */}
      <div style={{ display: 'grid', gap: '10px' }}>
        {filteredFiles.map(file => (
          <div key={file.id} style={{
            border: '1px solid #ddd',
            borderRadius: '8px',
            padding: '15px',
            backgroundColor: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', flex: '1', minWidth: '300px' }}>
              <div style={{ fontSize: '24px' }}>
                {getFileIcon(file.type)}
              </div>
              <div style={{ flex: '1' }}>
                <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>
                  {file.name}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  {file.type} • {file.size} • {file.uploadDate}
                </div>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  Пациент: {file.patientId} • Загрузил: {file.uploadedBy}
                </div>
              </div>
              <div style={{
                padding: '4px 8px',
                borderRadius: '4px',
                backgroundColor: getCategoryColor(file.category),
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {file.category}
              </div>
            </div>
            <div style={{ display: 'flex', gap: '5px' }}>
              <button
                onClick={() => downloadFile(file)}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#1976d2',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                📥 Скачать
              </button>
              <button
                onClick={() => deleteFile(file.id)}
                style={{
                  padding: '6px 12px',
                  backgroundColor: '#f44336',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                🗑️ Удалить
              </button>
            </div>
          </div>
        ))}
      </div>

      {filteredFiles.length === 0 && (
        <div style={{ 
          textAlign: 'center', 
          padding: '40px', 
          color: '#666',
          backgroundColor: '#f9f9f9',
          borderRadius: '8px',
          marginTop: '20px'
        }}>
          <p>Файлы не найдены</p>
        </div>
      )}

      {/* Общая статистика по размерам */}
      <div style={{ 
        marginTop: '30px',
        padding: '20px',
        backgroundColor: '#f5f5f5',
        borderRadius: '8px'
      }}>
        <h3 style={{ marginBottom: '15px' }}>📊 Статистика по размерам</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
          {['PDF', 'JPG', 'XLSX', 'DICOM'].map(type => {
            const typeFiles = files.filter(f => f.type === type);
            return (
              <div key={type} style={{
                padding: '10px',
                backgroundColor: 'white',
                borderRadius: '4px',
                textAlign: 'center'
              }}>
                <div style={{ fontSize: '20px', marginBottom: '5px' }}>
                  {getFileIcon(type)}
                </div>
                <div style={{ fontWeight: 'bold' }}>{type}</div>
                <div style={{ color: '#666', fontSize: '14px' }}>
                  {typeFiles.length} файлов
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SimpleFileManager;
