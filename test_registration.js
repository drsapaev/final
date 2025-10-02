// Тестовый скрипт для проверки регистрации
// Запустить в консоли браузера (F12)

console.log('🧪 Тест регистрации пациентов');

// Текущие записи в таблице
const currentRecords = document.querySelectorAll('.enhanced-table tbody tr');
console.log(`📊 Текущих записей в таблице: ${currentRecords.length}`);

// Функция для ожидания
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Функция для проверки обновления таблицы
const checkTableUpdate = async () => {
  await wait(1000); // Ждем 1 секунду

  const newRecords = document.querySelectorAll('.enhanced-table tbody tr');
  console.log(`📊 Записей после обновления: ${newRecords.length}`);

  if (newRecords.length > currentRecords.length) {
    console.log('✅ Таблица обновилась! Новая запись появилась');
  } else {
    console.log('❌ Таблица НЕ обновилась');
  }
};

// Проверяем через 1 секунду
checkTableUpdate();

