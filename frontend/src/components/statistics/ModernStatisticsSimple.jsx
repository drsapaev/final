import PropTypes from 'prop-types';
const ModernStatistics = ({ appointments, onExport, onRefresh }) => {
  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', borderRadius: '8px', marginBottom: '20px' }}>
      <h3>Статистика (упрощенная версия)</h3>
      <p>Всего записей: {appointments?.length || 0}</p>
      <p>Загружено: {new Date().toLocaleString()}</p>
      <button onClick={onRefresh}>Обновить</button>
      <button onClick={onExport}>Экспорт</button>
    </div>
  );
};


ModernStatistics.propTypes = {
  ...(ModernStatistics.propTypes || {}),
  appointments: PropTypes.any,
  length: PropTypes.any,
  onExport: PropTypes.any,
  onRefresh: PropTypes.any,
};

export default ModernStatistics;
