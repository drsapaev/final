import { useTranslation } from '../../i18n/useTranslation';
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
  Badge,
  Button,
  MacOSEmptyState,
  Input,
  Skeleton,
  Select,
} from '../ui/macos';
import useDoctors from '../../hooks/useDoctors';
import useFinance from '../../hooks/useFinance';
import usePatients from '../../hooks/usePatients';
import { useModal } from '../../hooks/useModal.jsx';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import formatCurrency from '../../utils/formatCurrency';
import FinanceModal from './FinanceModal';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

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
  const { t } = useTranslation();
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
    refresh: refreshFinance,
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
      title: t('admin.delete_transaction_title'),
      message: `Удалить транзакцию «${transaction.description}»?`,
      description: 'Это действие необратимо.',
      confirmLabel: t('admin.delete_confirm'),
      cancelLabel: t('admin.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      await deleteTransaction(transaction.id);
    } catch (error) {
      logger.error('Ошибка удаления финансовой транзакции:', error);
      notify.error(t('admin.transaction_delete_error'));
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
    <div className="flex flex-col gap-6">
      <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-fs-sm-fw-med-secondary-m-0">
                Общий доход
              </p>
              <p className="admin-fs-2xl-fw-bold-success-m-4px-0-0-0">
                {formatCurrency(financialStats.totalIncome)}
              </p>
            </div>
            <DollarSign className="admin-w-32-h-32-success" />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-fs-sm-fw-med-secondary-m-0">
                Общие расходы
              </p>
              <p className="admin-fs-2xl-fw-bold-error-m-4px-0-0-0">
                {formatCurrency(financialStats.totalExpense)}
              </p>
            </div>
            <CreditCard className="admin-w-32-h-32-error" />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-fs-sm-fw-med-secondary-m-0">
                Чистая прибыль
              </p>
              <p className="admin-fs-2xl-fw-bold-m-4px-0-0-0-col-dyn" style={{ '--admin-col0': financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)' }}>
                {formatCurrency(financialStats.netProfit)}
              </p>
            </div>
            <Calendar className="admin-w-32-h-32-col-dyn" style={{ '--admin-col0': financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)' }} />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-fs-sm-fw-med-secondary-m-0">
                Всего транзакций
              </p>
              <p className="admin-fs-2xl-fw-bold-primary-m-4px-0-0-0">
                {financialStats.transactionCount}
              </p>
            </div>
            <Receipt className="admin-w-32-h-32-accent" />
          </div>
        </MacOSCard>
      </div>

      <MacOSCard variant="default" className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-0">
        <div className="admin-p-16-d-flex-ai-center-jc-between-mb-24">
          <h2 className="admin-fs-20-fw-600-primary-m-0">
            Финансовый учет
          </h2>
          <Button onClick={handleCreateTransaction}>
            <Plus className="w-4 h-4 mr-2" />
            Добавить транзакцию
          </Button>
        </div>

        <div className="admin-d-flex-ai-center-gap-16-mb-24-fw-wrap">
          <div className="admin-flex-1-1-260px">
            <Input
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

        <div className="admin-ovx-auto">
          {financeLoading ? (
            <Skeleton type="table" count={5} />
          ) : financeError ? (
            <MacOSEmptyState
              icon={CreditCard}
              title="Ошибка загрузки транзакций"
              description="Не удалось загрузить список транзакций"
              action={(
                <Button onClick={refreshFinance}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
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
                <Button onClick={handleCreateTransaction}>
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить первую транзакцию
                </Button>
              )}
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="w-full" aria-label="Таблица транзакций">
              <thead>
                <tr className="admin-bd-b-1px-solid-var-mac-se">
                  {['Тип', 'Категория', 'Сумма', 'Описание', 'Дата', 'Статус', 'Действия'].map((heading) => (
                    <th
                      key={heading}
                      scope="col"
                      className="admin-ta-left-p-var-mac-spacing-3-va-fw-semi-fs-sm-var-mac-table-header"
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
                    className="admin-bd-b-1px-solid-var-mac-se-tr-all-var-mac-duration"
                    onMouseEnter={(event) => {
                      event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td className="admin-p-var-mac-spacing-3-va">
                      <Badge variant={transaction.type === 'income' ? 'success' : 'error'}>
                        {getTransactionTypeLabel(transaction.type)}
                      </Badge>
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <div>
                        <p className="admin-fw-med-primary-m-0">
                          {transaction.category}
                        </p>
                        {transaction.patientName && (
                          <p className="admin-fs-sm-secondary-m-4px-0-0-0">
                            {transaction.patientName}
                          </p>
                        )}
                      </div>
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <p className="admin-fw-med-m-0-col-dyn" style={{ '--admin-col0': transaction.type === 'income' ? 'var(--mac-success)' : 'var(--mac-danger)' }}>
                        {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
                      </p>
                      <p className="admin-fs-sm-secondary-m-4px-0-0-0">
                        {getPaymentMethodLabel(transaction.paymentMethod)}
                      </p>
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <p className="admin-fs-sm-secondary-m-0">
                        {truncateDescription(transaction.description)}
                      </p>
                      {transaction.reference && (
                        <p className="admin-fs-xs-tertiary-m-4px-0-0-0">
                          {transaction.reference}
                        </p>
                      )}
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va-fs-sm-secondary">
                      {formatTransactionDate(transaction.transactionDate)}
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <Badge variant={getTransactionStatusVariant(transaction.status)}>
                        {getTransactionStatusLabel(transaction.status)}
                      </Badge>
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <div className="admin-d-flex-ai-center-gap-var-mac-spacing-2">
                        <button
                          type="button"
                          onClick={() => handleEditTransaction(transaction)}
                          className="admin-p-var-mac-spacing-2-radius-var-mac-radius-sm-bgc-transparent-bd-none-cur-pointer-secondary-tr-all-var-mac-duration"
                          onMouseEnter={(event) => {
                            event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          aria-label="Редактировать транзакцию"
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteTransaction(transaction)}
                          className="admin-p-var-mac-spacing-2-radius-var-mac-radius-sm-bgc-transparent-bd-none-cur-pointer-error-tr-all-var-mac-duration"
                          onMouseEnter={(event) => {
                            event.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
                          }}
                          onMouseLeave={(event) => {
                            event.currentTarget.style.backgroundColor = 'transparent';
                          }}
                          aria-label="Удалить транзакцию"
                          title="Удалить"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
