import {
  Calendar,
  CreditCard,
  DollarSign,
  Edit,
  Plus,
  Receipt,
  RefreshCw,
  Search,
  Trash2,
} from 'lucide-react';

import {
  Card as MacOSCard,
  MacOSBadge,
  MacOSButton,
  MacOSEmptyState,
  MacOSInput,
  MacOSLoadingSkeleton,
  Select,
} from '../ui/macos';
import useDoctors from '../../hooks/useDoctors';
import useFinance from '../../hooks/useFinance';
import usePatients from '../../hooks/usePatients';
import { useModal } from '../../hooks/useModal.jsx';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import FinanceModal from './FinanceModal';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const adminSectionShellStyle = {
  background: 'var(--mac-gradient-sidebar)',
  border: '1px solid var(--mac-main-shell-border)',
  borderRadius: '24px',
  boxShadow: 'none',
  backdropFilter: 'var(--mac-blur-light)',
  WebkitBackdropFilter: 'var(--mac-blur-light)',
};

const categoryOptions = [
  { value: '', label: 'Все категории' },
  { value: 'Консультация врача', label: 'Консультация врача' },
  { value: 'Диагностика', label: 'Диагностика' },
  { value: 'Лечение', label: 'Лечение' },
  { value: 'Анализы', label: 'Анализы' },
  { value: 'Процедуры', label: 'Процедуры' },
  { value: 'Зарплата персонала', label: 'Зарплата персонала' },
  { value: 'Коммунальные услуги', label: 'Коммунальные услуги' },
  { value: 'Медикаменты', label: 'Медикаменты' },
];

function formatCurrency(amount) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'UZS',
    minimumFractionDigits: 0,
  }).format(amount);
}

function getTransactionTypeLabel(type) {
  const typeMap = {
    income: 'Доход',
    expense: 'Расход',
  };
  return typeMap[type] || type;
}

function getTransactionStatusLabel(status) {
  const statusMap = {
    pending: 'Ожидает',
    completed: 'Завершена',
    cancelled: 'Отменена',
    refunded: 'Возврат',
  };
  return statusMap[status] || status;
}

function getTransactionStatusVariant(status) {
  const variantMap = {
    pending: 'warning',
    completed: 'success',
    cancelled: 'error',
    refunded: 'info',
  };
  return variantMap[status] || 'secondary';
}

function getPaymentMethodLabel(method) {
  const methodMap = {
    cash: 'Наличные',
    card: 'Карта',
    transfer: 'Перевод',
    mobile: 'Мобильный',
  };
  return methodMap[method] || method;
}

function formatTransactionDate(transactionDate) {
  if (!transactionDate) return 'Не указано';
  const parsed = new Date(transactionDate);
  if (Number.isNaN(parsed.getTime())) return transactionDate;
  return parsed.toLocaleDateString('ru-RU');
}

function truncateDescription(description = '') {
  return description.length > 50 ? `${description.substring(0, 50)}...` : description;
}

const AdminFinanceOverview = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const {
    transactions,
    loading: financeLoading,
    error: financeError,
    searchTerm: financeSearchTerm,
    setSearchTerm: setFinanceSearchTerm,
    filterType,
    setFilterType,
    filterCategory,
    setFilterCategory,
    filterDateRange,
    setFilterDateRange,
    filterStatus: financeFilterStatus,
    setFilterStatus: setFinanceFilterStatus,
    createTransaction,
    updateTransaction,
    deleteTransaction,
    getFinancialStats,
  } = useFinance();

  const { patients } = usePatients();
  const { doctors, allDoctors } = useDoctors();
  const financeModal = useModal();

  const financialStats = getFinancialStats();

  const handleCreateTransaction = () => {
    financeModal.openModal(null);
  };

  const handleEditTransaction = (transaction) => {
    financeModal.openModal(transaction);
  };

  const handleDeleteTransaction = async (transaction) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление транзакции',
      message: `Удалить транзакцию «${transaction.description}»?`,
      description: 'Это действие необратимо.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      await deleteTransaction(transaction.id);
    } catch (error) {
      logger.error('Ошибка удаления финансовой транзакции:', error);
      notify.error('Ошибка при удалении финансовой транзакции');
    }
  };

  const handleSaveTransaction = async (transactionData) => {
    financeModal.setModalLoading(true);
    try {
      if (financeModal.selectedItem) {
        await updateTransaction(financeModal.selectedItem.id, transactionData);
      } else {
        await createTransaction(transactionData);
      }
      financeModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения финансовой транзакции:', error);
      throw error;
    } finally {
      financeModal.setModalLoading(false);
    }
  };

  const activeDoctors = allDoctors?.length ? allDoctors : doctors;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px',
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                Общий доход
              </p>
              <p style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)', margin: '4px 0 0 0' }}>
                {formatCurrency(financialStats.totalIncome)}
              </p>
            </div>
            <DollarSign style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                Общие расходы
              </p>
              <p style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-error)', margin: '4px 0 0 0' }}>
                {formatCurrency(financialStats.totalExpense)}
              </p>
            </div>
            <CreditCard style={{ width: '32px', height: '32px', color: 'var(--mac-error)' }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                Чистая прибыль
              </p>
              <p style={{
                fontSize: 'var(--mac-font-size-2xl)',
                fontWeight: 'var(--mac-font-weight-bold)',
                color: financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)',
                margin: '4px 0 0 0',
              }}>
                {formatCurrency(financialStats.netProfit)}
              </p>
            </div>
            <Calendar style={{
              width: '32px',
              height: '32px',
              color: financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)',
            }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                Всего транзакций
              </p>
              <p style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-text-primary)', margin: '4px 0 0 0' }}>
                {financialStats.transactionCount}
              </p>
            </div>
            <Receipt style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
          </div>
        </MacOSCard>
      </div>

      <MacOSCard variant="default" style={{ ...adminSectionShellStyle, padding: 0 }}>
        <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: 'var(--mac-text-primary)', margin: 0 }}>
            Финансовый учет
          </h2>
          <MacOSButton onClick={handleCreateTransaction}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить транзакцию
          </MacOSButton>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск транзакций..."
              value={financeSearchTerm}
              onChange={(event) => setFinanceSearchTerm(event.target.value)}
              icon={Search}
              iconPosition="left"
            />
          </div>
          <Select
            value={filterType}
            onChange={(value) => setFilterType(value)}
            options={[
              { value: '', label: 'Все типы' },
              { value: 'income', label: 'Доходы' },
              { value: 'expense', label: 'Расходы' },
            ]}
          />
          <Select
            value={filterCategory}
            onChange={(value) => setFilterCategory(value)}
            options={categoryOptions}
          />
          <Select
            value={filterDateRange}
            onChange={(value) => setFilterDateRange(value)}
            options={[
              { value: '', label: 'Все время' },
              { value: 'today', label: 'Сегодня' },
              { value: 'week', label: 'Неделя' },
              { value: 'month', label: 'Месяц' },
              { value: 'year', label: 'Год' },
            ]}
          />
          <Select
            value={financeFilterStatus}
            onChange={(value) => setFinanceFilterStatus(value)}
            options={[
              { value: '', label: 'Все статусы' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'completed', label: 'Завершена' },
              { value: 'cancelled', label: 'Отменена' },
              { value: 'refunded', label: 'Возврат' },
            ]}
          />
        </div>

        <div style={{ overflowX: 'auto' }}>
          {financeLoading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : financeError ? (
            <MacOSEmptyState
              icon={CreditCard}
              title="Ошибка загрузки транзакций"
              description="Не удалось загрузить список транзакций"
              action={(
                <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
              )}
            />
          ) : transactions.length === 0 ? (
            <MacOSEmptyState
              icon={CreditCard}
              title="Транзакции не найдены"
              description={financeSearchTerm || filterType || filterCategory || filterDateRange || financeFilterStatus
                ? 'Попробуйте изменить параметры поиска'
                : 'В системе пока нет транзакций'}
              action={(
                <MacOSButton onClick={handleCreateTransaction}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первую транзакцию
                </MacOSButton>
              )}
            />
          ) : (
            <table style={{ width: '100%' }} aria-label="Таблица транзакций">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--mac-separator)' }}>
                  {['Тип', 'Категория', 'Сумма', 'Описание', 'Дата', 'Статус', 'Действия'].map((heading) => (
                    <th
                      key={heading}
                      scope="col"
                      style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-semibold)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-table-header-text)' }}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {transactions.map((transaction) => (
                  <tr
                    key={transaction.id}
                    style={{ borderBottom: '1px solid var(--mac-separator)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                    onMouseEnter={(event) => {
                      event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <MacOSBadge variant={transaction.type === 'income' ? 'success' : 'error'}>
                        {getTransactionTypeLabel(transaction.type)}
                      </MacOSBadge>
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <div>
                        <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>
                          {transaction.category}
                        </p>
                        {transaction.patientName && (
                          <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>
                            {transaction.patientName}
                          </p>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: transaction.type === 'income' ? 'var(--mac-success)' : 'var(--mac-danger)', margin: 0 }}>
                        {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
                      </p>
                      <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>
                        {getPaymentMethodLabel(transaction.paymentMethod)}
                      </p>
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                        {truncateDescription(transaction.description)}
                      </p>
                      {transaction.reference && (
                        <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                          {transaction.reference}
                        </p>
                      )}
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                      {formatTransactionDate(transaction.transactionDate)}
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <MacOSBadge variant={getTransactionStatusVariant(transaction.status)}>
                        {getTransactionStatusLabel(transaction.status)}
                      </MacOSBadge>
                    </td>
                    <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                        <button
                          type="button"
                          onClick={() => handleEditTransaction(transaction)}
                          style={{ padding: 'var(--mac-spacing-2)', borderRadius: 'var(--mac-radius-sm)', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--mac-text-secondary)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                          onMouseEnter={(event) => {
                            event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          aria-label="Редактировать транзакцию"
                          title="Редактировать"
                        >
                          <Edit style={{ width: '16px', height: '16px' }} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteTransaction(transaction)}
                          style={{ padding: 'var(--mac-spacing-2)', borderRadius: 'var(--mac-radius-sm)', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--mac-danger)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                          onMouseEnter={(event) => {
                            event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          aria-label="Удалить транзакцию"
                          title="Удалить"
                        >
                          <Trash2 style={{ width: '16px', height: '16px' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </MacOSCard>

      <FinanceModal
        isOpen={financeModal.isOpen}
        onClose={() => financeModal.closeModal()}
        transaction={financeModal.selectedItem}
        onSave={handleSaveTransaction}
        loading={financeModal.loading}
        patients={patients}
        doctors={activeDoctors}
      />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>
  );
};

export default AdminFinanceOverview;
