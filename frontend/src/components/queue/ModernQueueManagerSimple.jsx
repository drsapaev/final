import React from 'react';

const ModernQueueManagerSimple = ({ selectedDate, selectedDoctor, searchQuery, onQueueUpdate, language, theme, doctors }) => {
  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '8px', marginBottom: '20px' }}>
      <h3>Онлайн-очередь (упрощенная версия)</h3>
      <p>Дата: {selectedDate}</p>
      <p>Врач: {selectedDoctor}</p>
      <p>Поиск: {searchQuery}</p>
      <p>Врачей: {doctors?.length || 0}</p>
      <button onClick={() => onQueueUpdate && onQueueUpdate()}>Обновить очередь</button>
    </div>
  );
};

export default ModernQueueManagerSimple;
