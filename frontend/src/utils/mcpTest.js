/**
 * Тест MCP интеграции в frontend
 */
import { mcpAPI } from '../api/mcpClient';

export const testMCPIntegration = async () => {
  console.log('🧪 Тестирование MCP интеграции в frontend...');
  
  try {
    // Тест 1: Проверка здоровья MCP
    console.log('1️⃣ Проверка здоровья MCP...');
    const healthResponse = await mcpAPI.getMcpHealth();
    console.log('✅ MCP Health:', healthResponse.data);
    
    // Тест 2: Получение статуса
    console.log('2️⃣ Получение статуса MCP...');
    const statusResponse = await mcpAPI.getMcpStatus();
    console.log('✅ MCP Status:', statusResponse.data);
    
    // Тест 3: Получение возможностей
    console.log('3️⃣ Получение возможностей MCP...');
    const capabilitiesResponse = await mcpAPI.getMcpCapabilities();
    console.log('✅ MCP Capabilities:', capabilitiesResponse.data);
    
    // Тест 4: Анализ жалобы
    console.log('4️⃣ Анализ жалобы...');
    const complaintResponse = await mcpAPI.analyzeComplaint({
      complaint: 'Головная боль и тошнота уже 2 дня',
      patientInfo: { age: 35, gender: 'female' },
      provider: 'openai'
    });
    console.log('✅ Анализ жалобы:', complaintResponse.data);
    
    // Тест 5: Подсказки МКБ-10
    console.log('5️⃣ Подсказки МКБ-10...');
    const icd10Response = await mcpAPI.suggestIcd10({
      symptoms: ['головная боль', 'тошнота', 'светобоязнь'],
      diagnosis: 'Мигрень',
      provider: 'openai'
    });
    console.log('✅ Подсказки МКБ-10:', icd10Response.data);
    
    console.log('🎉 Все тесты MCP интеграции прошли успешно!');
    return true;
    
  } catch (error) {
    console.error('❌ Ошибка тестирования MCP:', error);
    return false;
  }
};

// Автоматический тест при загрузке модуля
if (typeof window !== 'undefined') {
  window.testMCPIntegration = testMCPIntegration;
  console.log('🔧 MCP тест доступен как window.testMCPIntegration()');
}
