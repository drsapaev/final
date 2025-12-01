// Тестовый скрипт для проверки логики дедупликации QR-записей
// Симулируем данные от сервера, как они приходят в RegistrarPanel.jsx

// Мокаем данные от сервера (как приходят от /api/v1/registrar/queues/today)
const mockServerData = {
  queues: [
    {
      specialty: 'cardiology',
      entries: [
        {
          id: 290,
          type: 'online_queue',
          patient_id: 123,
          patient_name: 'Куп Одам',
          number: 4,
          status: 'waiting',
          phone: '+998928884575'
        }
      ]
    },
    {
      specialty: 'dermatology',
      entries: [
        {
          id: 291,
          type: 'online_queue',
          patient_id: 123,  // Тот же пациент!
          patient_name: 'Куп Одам',
          number: 3,
          status: 'waiting',
          phone: '+998928884575'
        }
      ]
    },
    {
      specialty: 'stomatology',
      entries: [
        {
          id: 292,
          type: 'online_queue',
          patient_id: 123,  // Тот же пациент!
          patient_name: 'Куп Одам',
          number: 3,
          status: 'waiting',
          phone: '+998928884575'
        }
      ]
    },
    {
      specialty: 'laboratory',
      entries: [
        {
          id: 293,
          type: 'online_queue',
          patient_id: 123,  // Тот же пациент!
          patient_name: 'Куп Одам',
          number: 3,
          status: 'waiting',
          phone: '+998928884575'
        }
      ]
    }
  ]
};

// Симулируем логику из RegistrarPanel.jsx
function testDeduplication() {
  const dateParam = '2025-12-01';
  const appointmentsMap = new Map();
  const logger = {
    info: (...args) => console.log('[INFO]', ...args),
    error: (...args) => console.error('[ERROR]', ...args)
  };

  console.log('=== ТЕСТИРОВАНИЕ ЛОГИКИ ДЕДУПЛИКАЦИИ ===');

  mockServerData.queues.forEach(queue => {
    console.log(`📋 Обработка очереди: ${queue.specialty}, записей: ${queue.entries?.length || 0}`);
    if (queue.entries && Array.isArray(queue.entries)) {
      queue.entries.forEach((entry, index) => {
        try {
          const fullEntry = entry;
          const entryId = fullEntry.id;
          const entryType = entry.type || 'unknown';

          // ✅ ИСПРАВЛЕНО: Для online_queue записей используем дедупликацию по patient_id + date
          let dedupKey = entryId; // По умолчанию дедуплицируем по ID записи
          if (entryType === 'online_queue' && fullEntry.patient_id && dateParam) {
            dedupKey = `online_${fullEntry.patient_id}_${dateParam}`;
            console.log(`🔑 QR-запись: используем ключ дедупликации ${dedupKey} для patient_id=${fullEntry.patient_id}`);
          }

          // ✅ ИСПРАВЛЕНО: Проверяем, есть ли уже запись с таким ключом дедупликации
          if (appointmentsMap.has(dedupKey)) {
            // ✅ ИСПРАВЛЕНО: Если запись уже есть, добавляем номер очереди только если нет очереди с таким queue_tag
            const existingAppointment = appointmentsMap.get(dedupKey);
            const queueNum = fullEntry.number !== undefined && fullEntry.number !== null ? fullEntry.number : (index + 1);
            const currentQueueTag = (queue.specialty || queue.queue_tag || '').toString().toLowerCase().trim();

            const queueTagExists = existingAppointment.queue_numbers.some((qn) => {
              const existingTag = (qn.queue_tag || qn.specialty || '').toString().toLowerCase().trim();
              return existingTag && existingTag === currentQueueTag;
            });

            if (!queueTagExists) {
              existingAppointment.queue_numbers.push({
                number: queueNum,
                status: fullEntry.status || 'waiting',
                specialty: queue.specialty || queue.queue_tag || null,
                queue_name: queue.specialist_name || queue.specialty || 'Очередь',
                queue_tag: queue.specialty || queue.queue_tag || null
              });
              console.log(`🔄 Добавлен queue_number ${queueNum} (${queue.specialty}) для существующей записи ${dedupKey}`);
            } else {
              console.log(`⏭️ Пропущен дубликат очереди ${queue.specialty} (номер ${queueNum}) для записи ${dedupKey}`);
            }
            return; // Пропускаем добавление дубликата
          }

          // Создаем новую запись
          const appointment = {
            id: dedupKey, // ✅ ИСПРАВЛЕНО: Используем dedupKey вместо entryId
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

          // ✅ Сохраняем в Map для дедупликации
          appointmentsMap.set(dedupKey, appointment);
          console.log(`✅ Добавлена запись ${dedupKey} с queue_numbers:`, appointment.queue_numbers);

        } catch (err) {
          console.error('❌ Ошибка обработки записи очереди:', err, entry);
        }
      });
    }
  });

  // Результат
  const appointmentsData = Array.from(appointmentsMap.values());
  console.log('\n=== РЕЗУЛЬТАТ ===');
  console.log(`Всего уникальных записей: ${appointmentsData.length}`);

  appointmentsData.forEach((appointment, index) => {
    console.log(`Запись ${index + 1}:`);
    console.log(`  ID: ${appointment.id}`);
    console.log(`  Пациент: ${appointment.patient_fio} (${appointment.patient_phone})`);
    console.log(`  Количество номеров очередей: ${appointment.queue_numbers.length}`);
    appointment.queue_numbers.forEach((qn, i) => {
      console.log(`    ${i + 1}. ${qn.specialty}: №${qn.number}`);
    });
  });

  return appointmentsData;
}

// Запускаем тест
const result = testDeduplication();

console.log('\n=== ПРОВЕРКА РЕЗУЛЬТАТА ===');
if (result.length === 1 && result[0].queue_numbers.length === 4) {
  console.log('✅ ТЕСТ ПРОЙДЕН: Одна запись с 4 номерами очередей');
} else {
  console.log('❌ ТЕСТ НЕ ПРОЙДЕН: Ожидалась 1 запись с 4 номерами, получено:', result.length, 'записей');
  result.forEach(r => console.log(`  - ${r.queue_numbers.length} номеров`));
}
