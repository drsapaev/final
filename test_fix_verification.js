// Тест для проверки исправления - appointment.id должен быть entryId, а не dedupKey

const mockServerData = {
  queues: [
    {
      specialty: 'cardiology',
      entries: [
        {
          type: 'online_queue',
          data: {
            id: 294,
            patient_id: 150,
            patient_name: 'Сапарбаева Золола',
            number: 5,
            phone: '+998928832846'
          },
          created_at: '2025-12-01T03:41:40.455496',
          queue_time: '2025-12-01T03:41:40.455496'
        }
      ]
    },
    {
      specialty: 'dermatology',
      entries: [
        {
          type: 'online_queue',
          data: {
            id: 295,
            patient_id: 150,  // Тот же пациент!
            patient_name: 'Сапарбаева Золола',
            number: 4,
            phone: '+998928832846'
          },
          created_at: '2025-12-01T03:41:40.455496',
          queue_time: '2025-12-01T03:41:40.455496'
        }
      ]
    }
  ]
};

// Симулируем исправленную логику
function testFixedLogic() {
  const dateParam = '2025-12-01';
  const appointmentsMap = new Map();

  mockServerData.queues.forEach(queue => {
    if (queue.entries && Array.isArray(queue.entries)) {
      queue.entries.forEach((entry, index) => {
        const fullEntry = entry.data || entry;
        const entryId = fullEntry.id;
        const entryType = entry.type || 'unknown';

        let dedupKey = entryId; // По умолчанию дедуплицируем по ID записи
        if (entryType === 'online_queue' && fullEntry.patient_id && dateParam) {
          dedupKey = `online_${fullEntry.patient_id}_${dateParam}`;
        }

        if (appointmentsMap.has(dedupKey)) {
          // Добавляем номер очереди к существующей записи
          const existingAppointment = appointmentsMap.get(dedupKey);
          existingAppointment.queue_numbers.push({
            number: fullEntry.number || (index + 1),
            status: fullEntry.status || 'waiting',
            specialty: queue.specialty || null,
            queue_name: queue.specialist_name || queue.specialty || 'Очередь',
            queue_tag: queue.specialty || null
          });
          return;
        }

        // Создаем новую запись
        const appointment = {
          id: entryId, // ✅ ДОЛЖЕН БЫТЬ entryId (целое число) для API
          patient_id: fullEntry.patient_id,
          patient_fio: fullEntry.patient_name,
          patient_phone: fullEntry.phone,
          queue_numbers: [
            {
              number: fullEntry.number || (index + 1),
              status: fullEntry.status || 'waiting',
              specialty: queue.specialty || null,
              queue_name: queue.specialist_name || queue.specialty || 'Очередь',
              queue_tag: queue.specialty || null
            }
          ],
          source: 'online'
        };

        appointmentsMap.set(dedupKey, appointment);
      });
    }
  });

  const appointmentsData = Array.from(appointmentsMap.values());
  console.log('Результат:');
  appointmentsData.forEach((appointment, index) => {
    console.log(`Запись ${index + 1}:`);
    console.log(`  appointment.id: ${appointment.id} (тип: ${typeof appointment.id})`);
    console.log(`  patient_id: ${appointment.patient_id}`);
    console.log(`  queue_numbers: ${appointment.queue_numbers.length} записей`);
  });

  return appointmentsData;
}

const result = testFixedLogic();

console.log('\nПроверка исправления:');
const firstAppointment = result[0];
if (typeof firstAppointment.id === 'number' && firstAppointment.queue_numbers.length === 2) {
  console.log('✅ ИСПРАВЛЕНИЕ РАБОТАЕТ: appointment.id является числом, дедупликация работает');
} else {
  console.log('❌ ПРОБЛЕМА: appointment.id не является числом или дедупликация не работает');
}
