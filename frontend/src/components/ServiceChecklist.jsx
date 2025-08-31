import React from 'react';

const ServiceChecklist = ({ value = [], onChange, department }) => {
  const services = {
    cardio: [
      { id: 'cardio_consultation', name: 'Консультация кардиолога', price: 60000, group: 'Кардиология' },
      { id: 'cardio_ekg', name: 'ЭКГ', price: 25000, group: 'Кардиология' },
      { id: 'cardio_echo', name: 'ЭхоКГ', price: 120000, group: 'Кардиология' },
      { id: 'cardio_holter', name: 'Холтер мониторинг', price: 200000, group: 'Кардиология' }
    ],
    derma: [
      { id: 'derma_consultation', name: 'Консультация дерматолога', price: 50000, group: 'Дерматология' },
      { id: 'derma_biopsy', name: 'Биопсия кожи', price: 150000, group: 'Дерматология' },
      { id: 'cosm_cleaning', name: 'Чистка лица', price: 80000, group: 'Косметология' },
      { id: 'cosm_botox', name: 'Инъекции ботокса', price: 300000, group: 'Косметология' },
      { id: 'cosm_laser', name: 'Лазерная терапия', price: 250000, group: 'Косметология' }
    ],
    dental: [
      { id: 'dental_consultation', name: 'Консультация стоматолога', price: 40000, group: 'Стоматология' },
      { id: 'dental_treatment', name: 'Лечение кариеса', price: 100000, group: 'Стоматология' },
      { id: 'dental_extraction', name: 'Удаление зуба', price: 80000, group: 'Стоматология' },
      { id: 'dental_prosthetics', name: 'Протезирование', price: 500000, group: 'Стоматология' }
    ],
    lab: [
      { id: 'lab_blood', name: 'Общий анализ крови', price: 30000, group: 'Лабораторные' },
      { id: 'lab_urine', name: 'Общий анализ мочи', price: 20000, group: 'Лабораторные' },
      { id: 'lab_biochem', name: 'Биохимия крови', price: 80000, group: 'Лабораторные' },
      { id: 'lab_biopsy', name: 'Биопсия', price: 150000, group: 'Лабораторные' }
    ],
    procedures: [
      { id: 'proc_injection', name: 'Инъекция', price: 15000, group: 'Процедуры' },
      { id: 'proc_infusion', name: 'Капельница', price: 50000, group: 'Процедуры' },
      { id: 'proc_physio', name: 'Физиотерапия', price: 35000, group: 'Процедуры' },
      { id: 'proc_massage', name: 'Массаж', price: 40000, group: 'Процедуры' }
    ]
  };

  const depServices = services[department?.toLowerCase()] || [];
  const groups = [...new Set(depServices.map(s => s.group))];
  const totalCost = depServices.filter(s => value.includes(s.id)).reduce((sum, s) => sum + s.price, 0);

  return (
    <div style={{ border: '1px solid #e5e5e5', borderRadius: '8px', padding: '12px', marginBottom: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontWeight: 600 }}>Услуги</span>
        <span style={{ fontSize: '14px', color: '#28a745', fontWeight: 600 }}>{totalCost.toLocaleString()} UZS</span>
      </div>
      {groups.map(group => (
        <div key={group} style={{ marginBottom: '8px' }}>
          <div style={{ fontWeight: 500, fontSize: '12px', color: '#666', marginBottom: '4px' }}>{group}</div>
          {depServices.filter(s => s.group === group).map(service => (
            <label key={service.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <input
                type="checkbox"
                checked={value.includes(service.id)}
                onChange={(e) => {
                  const newValue = e.target.checked 
                    ? [...value, service.id]
                    : value.filter(id => id !== service.id);
                  onChange(newValue);
                }}
              />
              <span style={{ fontSize: '12px', flex: 1 }}>{service.name}</span>
              <span style={{ fontSize: '12px', color: '#666' }}>{service.price.toLocaleString()} UZS</span>
            </label>
          ))}
        </div>
      ))}
    </div>
  );
};

export default ServiceChecklist;
