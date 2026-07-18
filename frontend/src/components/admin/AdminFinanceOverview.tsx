import type { CSSProperties } from 'react';

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
  Skeleton as SkeletonRaw,
  Select,
} from '../ui/macos';
import useDoctors from '../../hooks/useDoctors';
import useFinance from '../../hooks/useFinance';
import usePatients from '../../hooks/usePatients';
import { useModal } from '../../hooks/useModal';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import formatCurrency from '../../utils/formatCurrency';
import FinanceModal from './FinanceModal';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
import React from "react";
const Skeleton = SkeletonRaw as unknown as React.ComponentType<Record<string, unknown>>;

function getCategoryOptions(t) {
  return [
    { value: '', label: t('admin2.fo_cat_all') },
    { value: 'Консультация врача', label: t('admin2.fo_cat_consultation') },
    { value: 'Диагностика', label: t('admin2.fo_cat_diagnostics') },
    { value: 'Лечение', label: t('admin2.fo_cat_treatment') },
    { value: 'Анализы', label: t('admin2.fo_cat_tests') },
    { value: 'Процедуры', label: t('admin2.fo_cat_procedures') },
    { value: 'Зарплата персонала', label: t('admin2.fo_cat_salary') },
    { value: 'Коммунальные услуги', label: t('admin2.fo_cat_utilities') },
    { value: 'Медикаменты', label: t('admin2.fo_cat_medications') },
  ];
}


function getTransactionTypeLabel(type, t) {
  const typeMap = {
    income: t('admin2.fo_type_income'),
    expense: t('admin2.fo_type_expense'),
  };
  return typeMap[type] || type;
}

function getTransactionStatusLabel(status, t) {
  const statusMap = {
    pending: t('admin2.fo_status_pending'),
    completed: t('admin2.fo_status_completed'),
    cancelled: t('admin2.fo_status_cancelled'),
    refunded: t('admin2.fo_status_refunded'),
  };
  return statusMap[status] || status;
}

function getTransactionStatusVariant(status) {
  const variantMap = {
    pending: 'warning',
    completed: 'success',
    cancelled: 'danger',
    refunded: 'info',
  };
  return variantMap[status] || 'secondary';
}

function getPaymentMethodLabel(method, t) {
  const methodMap = {
    cash: t('admin2.fo_method_cash'),
    card: t('admin2.fo_method_card'),
    transfer: t('admin2.fo_method_transfer'),
    mobile: t('admin2.fo_method_mobile'),
  };
  return methodMap[method] || method;
}

function formatTransactionDate(transactionDate, t) {
  if (!transactionDate) return t('admin2.fo_no_date');
  const parsed = new Date(transactionDate);
  if (Number.isNaN(parsed.getTime())) return transactionDate;
  return parsed.toLocaleDateString('ru-RU');
}

function truncateDescription(description = '') {
  return description.length > 50 ? `${description.substring(0, 50)}...` : description;
}

const AdminFinanceOverview = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
    const ok = await (confirm as unknown as (opts: Record<string, unknown>) => Promise<boolean>)({
      title: t('admin.delete_transaction_title'),
      message: t('admin2.fo_delete_transaction_message', { description: transaction.description }),
      description: t('admin2.fo_action_irreversible'),
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
                {t('admin2.fo_total_income')}
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
                {t('admin2.fo_total_expense')}
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
                {t('admin2.fo_net_profit')}
              </p>
              <p className="admin-fs-2xl-fw-bold-m-4px-0-0-0-col-dyn" style={{ '--admin-col0': financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties}>
                {formatCurrency(financialStats.netProfit)}
              </p>
            </div>
            <Calendar className="admin-w-32-h-32-col-dyn" style={{ '--admin-col0': financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties} />
          </div>
        </MacOSCard>

        <MacOSCard className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="admin-fs-sm-fw-med-secondary-m-0">
                {t('admin2.fo_total_transactions')}
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
            {t('admin2.fo_finance_accounting')}
          </h2>
          <Button onClick={handleCreateTransaction}>
            <Plus className="w-4 h-4 mr-2" />
            {t('admin2.fo_add_transaction')}
          </Button>
        </div>

        <div className="admin-d-flex-ai-center-gap-16-mb-24-fw-wrap">
          <div className="admin-flex-1-1-260px">
            <Input
              type="text"
              placeholder={t('admin2.fo_search_placeholder')}
              value={financeSearchTerm}
              onChange={(event) => setFinanceSearchTerm(event.target.value)}
              icon={Search}
              iconPosition="left"
            />
          </div>
          <Select
            value={filterType}
            onChange={(value: any) => setFilterType(String(value))}
            options={[
              { value: '', label: t('admin2.fo_filter_type_all') },
              { value: 'income', label: t('admin2.fo_filter_type_income') },
              { value: 'expense', label: t('admin2.fo_filter_type_expense') },
            ]}
          />
          <Select
            value={filterCategory}
            onChange={(value: any) => setFilterCategory(String(value))}
            options={getCategoryOptions(t)}
          />
          <Select
            value={filterDateRange}
            onChange={(value: any) => setFilterDateRange(String(value))}
            options={[
              { value: '', label: t('admin2.fo_filter_date_all') },
              { value: 'today', label: t('admin2.fo_filter_date_today') },
              { value: 'week', label: t('admin2.fo_filter_date_week') },
              { value: 'month', label: t('admin2.fo_filter_date_month') },
              { value: 'year', label: t('admin2.fo_filter_date_year') },
            ]}
          />
          <Select
            value={financeFilterStatus}
            onChange={(value: any) => setFinanceFilterStatus(String(value))}
            options={[
              { value: '', label: t('admin2.fo_filter_status_all') },
              { value: 'pending', label: t('admin2.fo_status_pending') },
              { value: 'completed', label: t('admin2.fo_status_completed') },
              { value: 'cancelled', label: t('admin2.fo_status_cancelled') },
              { value: 'refunded', label: t('admin2.fo_status_refunded') },
            ]}
          />
        </div>

        <div className="admin-ovx-auto">
          {financeLoading ? (
            <Skeleton type="table" count={5} />
          ) : financeError ? (
            <MacOSEmptyState
              icon={CreditCard}
              title={t('admin2.fo_error_title')}
              description={t('admin2.fo_error_desc')}
              action={(
                <Button onClick={refreshFinance}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  {t('admin2.fo_refresh_btn')}
                </Button>
              )}
            />
          ) : transactions.length === 0 ? (
            <MacOSEmptyState
              icon={CreditCard}
              title={t('admin2.fo_empty_title')}
              description={financeSearchTerm || filterType || filterCategory || filterDateRange || financeFilterStatus
                ? t('admin2.fo_empty_desc_filtered')
                : t('admin2.fo_empty_desc')}
              action={(
                <Button onClick={handleCreateTransaction}>
                  <Plus className="w-4 h-4 mr-2" />
                  {t('admin2.fo_add_first_transaction')}
                </Button>
              )}
            />
          ) : (
            <div className="admin-table-wrapper">
            <table className="w-full" aria-label={t('admin2.fo_table_aria')}>
              <thead>
                <tr className="admin-bd-b-1px-solid-var-mac-se">
                  {[
                    { key: 'type', label: t('admin2.fo_col_type') },
                    { key: 'category', label: t('admin2.fo_col_category') },
                    { key: 'amount', label: t('admin2.fo_col_amount') },
                    { key: 'description', label: t('admin2.fo_col_description') },
                    { key: 'date', label: t('admin2.fo_col_date') },
                    { key: 'status', label: t('admin2.fo_col_status') },
                    { key: 'actions', label: t('admin2.fo_col_actions') },
                  ].map(({ key, label }) => (
                    <th
                      key={key}
                      scope="col"
                      className="admin-ta-left-p-var-mac-spacing-3-va-fw-semi-fs-sm-var-mac-table-header"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(transactions as Array<Record<string, any>>).map((transaction) => (
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
                      <Badge variant={(String(transaction.type) === 'income' ? 'success' : 'danger') as "default" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "outline"}>
                        {getTransactionTypeLabel(transaction.type, t)}
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
                      <p className="admin-fw-med-m-0-col-dyn" style={{ '--admin-col0': transaction.type === 'income' ? 'var(--mac-success)' : 'var(--mac-danger)' } as CSSProperties}>
                        {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
                      </p>
                      <p className="admin-fs-sm-secondary-m-4px-0-0-0">
                        {getPaymentMethodLabel(transaction.paymentMethod, t)}
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
                      {formatTransactionDate(transaction.transactionDate, t)}
                    </td>
                    <td className="admin-p-var-mac-spacing-3-va">
                      <Badge variant={getTransactionStatusVariant(transaction.status)}>
                        {getTransactionStatusLabel(transaction.status, t)}
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
                          aria-label={t('admin2.fo_edit_aria')}
                          title={t('admin2.fo_edit_btn')}
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
                          aria-label={t('admin2.fo_delete_aria')}
                          title={t('admin2.fo_delete_btn')}
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
      {confirmDialog as unknown as React.ReactNode}
    </div>
  );
};

export default AdminFinanceOverview;
