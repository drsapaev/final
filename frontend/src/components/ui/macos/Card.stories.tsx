/**
 * Card Stories — canonical Card primitive (plan §PR-UI-18 item 2).
 *
 * PR-UI-06/PR-UI-11: Card is THE canonical surface component (the
 * MacOSCard alias was decommissioned after the 15-increment migration to
 * 0 import-consumers). Compound parts: CardHeader / CardTitle /
 * CardDescription / CardContent / CardFooter.
 */
import Card, {
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from './Card';
import Button from './Button';

export default {
  title: 'UI/MacOS/Card',
  component: Card,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'Canonical Card (PR-UI-06/11): compound layout primitive ' +
          '(Header/Title/Description/Content/Footer). MacOSCard alias decommissioned #2902.',
      },
    },
  },
};

export const Simple = {
  args: {
    children: 'Простая карточка с текстовым содержимым.',
  },
};

export const Compound = {
  render: () => (
    <Card>
      <CardHeader>
        <CardTitle>Очередь кардиологии</CardTitle>
        <CardDescription>Кабинет 12 · доктор А. А.</CardDescription>
      </CardHeader>
      <CardContent>
        Статистика приёма и список записей на сегодня. Содержимое карточки
        использует канонические токены --mac-* и поддерживает обе темы.
      </CardContent>
      <CardFooter>
        <Button variant="primary" size="sm">Открыть очередь</Button>
      </CardFooter>
    </Card>
  ),
};

export const Interactive = {
  render: () => (
    <Card interactive onClick={() => {}}>
      <CardHeader>
        <CardTitle>Интерактивная карточка</CardTitle>
        <CardDescription>Кликабельная поверхность (hover-состояние)</CardDescription>
      </CardHeader>
    </Card>
  ),
};
