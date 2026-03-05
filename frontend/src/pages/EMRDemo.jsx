import { Link } from 'react-router-dom';
import { Card, Button, Typography } from '../components/ui/macos';
import { FileText, ArrowRight, Users, ClipboardList, Stethoscope } from 'lucide-react';

const EMRDemo = () => {
  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <Typography variant="h2" style={{ marginBottom: 16 }}>
          🏥 EMR System Demo
        </Typography>
        <Typography variant="body1" style={{ color: 'var(--mac-text-secondary)', fontSize: 18 }}>
          Демонстрация улучшенной системы электронных медицинских карт
        </Typography>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24, marginBottom: 48 }}>
        <Card style={{ padding: 24, textAlign: 'center' }}>
          <Users style={{ width: 48, height: 48, color: 'var(--mac-accent-blue)', margin: '0 auto 16px' }} />
          <Typography variant="h4" style={{ marginBottom: 12 }}>
            Управление пациентами
          </Typography>
          <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)', marginBottom: 20 }}>
            Просмотр списка пациентов, поиск и фильтрация
          </Typography>
        </Card>

        <Card style={{ padding: 24, textAlign: 'center' }}>
          <FileText style={{ width: 48, height: 48, color: 'var(--mac-accent-green)', margin: '0 auto 16px' }} />
          <Typography variant="h4" style={{ marginBottom: 12 }}>
            Медицинские записи
          </Typography>
          <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)', marginBottom: 20 }}>
            Создание, редактирование и удаление записей
          </Typography>
        </Card>

        <Card style={{ padding: 24, textAlign: 'center' }}>
          <ClipboardList style={{ width: 48, height: 48, color: 'var(--mac-accent-purple)', margin: '0 auto 16px' }} />
          <Typography variant="h4" style={{ marginBottom: 12 }}>
            Шаблоны записей
          </Typography>
          <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)', marginBottom: 20 }}>
            Управление шаблонами для быстрого создания записей
          </Typography>
        </Card>
      </div>

      <Card style={{ padding: 32, textAlign: 'center', background: 'linear-gradient(135deg, var(--mac-accent-blue-light) 0%, var(--mac-accent-purple-light) 100%)' }}>
        <Stethoscope style={{ width: 64, height: 64, color: 'var(--mac-accent-blue)', margin: '0 auto 24px' }} />
        <Typography variant="h3" style={{ marginBottom: 16, color: 'var(--mac-text-primary)' }}>
          Новые возможности EMR системы
        </Typography>
        <Typography variant="body1" style={{ marginBottom: 32, color: 'var(--mac-text-secondary)', fontSize: 16 }}>
          ✨ Улучшенный UX с macOS дизайном<br/>
          🔄 CRUD операции для записей и шаблонов<br/>
          📱 Toast уведомления вместо Alert<br/>
          🎨 Структурированные формы с секциями<br/>
          🗑️ Кнопки удаления с подтверждением<br/>
          💾 Система автосохранения черновиков<br/>
          📁 Улучшенная загрузка файлов с drag-and-drop<br/>
          🤖 AI оптимизация с кэшированием
        </Typography>
        
        <Link to="/advanced-emr" style={{ textDecoration: 'none' }}>
          <Button 
            variant="primary" 
            size="large"
            style={{ 
              padding: '16px 32px', 
              fontSize: 18, 
              fontWeight: 600,
              background: 'var(--mac-accent-blue)',
              border: 'none',
              borderRadius: 12
            }}
          >
            <FileText style={{ width: 24, height: 24, marginRight: 12 }} />
            Открыть EMR System
            <ArrowRight style={{ width: 20, height: 20, marginLeft: 12 }} />
          </Button>
        </Link>
      </Card>

      <div style={{ marginTop: 48, padding: 24, backgroundColor: 'var(--mac-bg-secondary)', borderRadius: 12, border: '1px solid var(--mac-border)' }}>
        <Typography variant="h4" style={{ marginBottom: 16 }}>
          📋 Инструкции по использованию
        </Typography>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 16 }}>
          <div>
            <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 8 }}>
              1. Навигация по вкладкам
            </Typography>
            <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
              Переключайтесь между «Пациенты», «Медицинские записи» и «Шаблоны»
            </Typography>
          </div>
          <div>
            <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 8 }}>
              2. Создание записи
            </Typography>
            <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
              Нажмите «Новая запись» и заполните структурированную форму
            </Typography>
          </div>
          <div>
            <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 8 }}>
              3. Редактирование
            </Typography>
            <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
              Кликните на запись для редактирования или используйте кнопки действий
            </Typography>
          </div>
          <div>
            <Typography variant="subtitle2" style={{ fontWeight: 600, marginBottom: 8 }}>
              4. Удаление
            </Typography>
            <Typography variant="body2" style={{ color: 'var(--mac-text-secondary)' }}>
              Используйте кнопку корзины для удаления с подтверждением
            </Typography>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EMRDemo;
