import { useChat } from '../contexts/ChatContext';

// Ре-экспортируем хук из контекста для обратной совместимости
export { useChat };

// Экспорт по умолчанию тоже нужен
export default useChat;
