// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * Тест MCP интеграции в frontend
 */
import { mcpAPI } from '../api/mcpClient';

import logger from '../utils/logger';
export const testMCPIntegration = async () => {
  logger.log('🧪 Тестирование MCP интеграции в frontend...');
  
  try {
    // Тест 1: Проверка здоровья MCP
    logger.log('1️⃣ Проверка здоровья MCP...');
    const healthResponse = await mcpAPI.getMcpHealth();
    logger.log('✅ MCP Health:', healthResponse.data);
    
    // Тест 2: Получение статуса
    logger.log('2️⃣ Получение статуса MCP...');
    const statusResponse = await mcpAPI.getMcpStatus();
    logger.log('✅ MCP Status:', statusResponse.data);
    
    // Тест 3: Получение возможностей
    logger.log('3️⃣ Получение возможностей MCP...');
    const capabilitiesResponse = await mcpAPI.getMcpCapabilities();
    logger.log('✅ MCP Capabilities:', capabilitiesResponse.data);
    
    // Тест 4: Анализ жалобы
    logger.log('4️⃣ Анализ жалобы...');
    const complaintResponse = await mcpAPI.analyzeComplaint({
      complaint: 'Головная боль и тошнота уже 2 дня',
      patientInfo: { age: 35, gender: 'female' },
      provider: 'openai'
    });
    logger.log('✅ Анализ жалобы:', complaintResponse.data);
    
    // Тест 5: Подсказки МКБ-10
    logger.log('5️⃣ Подсказки МКБ-10...');
    const icd10Response = await mcpAPI.suggestIcd10({
      symptoms: ['головная боль', 'тошнота', 'светобоязнь'],
      diagnosis: 'Мигрень',
      provider: 'openai'
    });
    logger.log('✅ Подсказки МКБ-10:', icd10Response.data);
    
    logger.log('🎉 Все тесты MCP интеграции прошли успешно!');
    return true;
    
  } catch (error) {
    logger.error('❌ Ошибка тестирования MCP:', error);
    return false;
  }
};

// Автоматический тест при загрузке модуля
if (typeof window !== 'undefined') {
  window.testMCPIntegration = testMCPIntegration;
  logger.log('🔧 MCP тест доступен как window.testMCPIntegration()');
}
