import UserManagement from './UserManagement';
import { MacOSAlert } from '../ui/macos';

const AdvancedUserManagement = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <MacOSAlert
        type="info"
        title="Расширенное управление пользователями"
        description="Этот экран сохраняет прямой legacy-доступ к базовой таблице пользователей. Для повседневных задач используйте раздел Пользователи, где собраны связанные действия управления аккаунтами."
      />

      <UserManagement />
    </div>
  );
};

export default AdvancedUserManagement;
