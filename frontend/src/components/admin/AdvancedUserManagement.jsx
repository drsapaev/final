import UserManagement from './UserManagement';
import {
  Alert,
} from '../ui/macos';

const AdvancedUserManagement = () => {
  return (
    <div className="admin-flex-col-16">
      <Alert
        type="info"
        title="Расширенное управление пользователями"
        description="Этот экран сохраняет прямой legacy-доступ к базовой таблице пользователей. Для повседневных задач используйте раздел Пользователи, где собраны связанные действия управления аккаунтами."
      />

      <UserManagement />
    </div>
  );
};

export default AdvancedUserManagement;
