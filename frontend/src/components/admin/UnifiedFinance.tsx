
import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import BillingManager from './BillingManager';
import DynamicPricingManager from './DynamicPricingManager';
import DiscountBenefitsManager from './DiscountBenefitsManager';
import AdminFinanceOverview from './AdminFinanceOverview';
import ErrorBoundary from '../common/ErrorBoundary';
import { MacOSTab } from '../ui/macos';
import React from 'react';
import { useTranslation } from '../../i18n/useTranslation';


const UnifiedFinance = ({ renderFinance }) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'finance';

  const getActiveTab = (section) => {
    switch (section) {
      case 'finance':return 'overview';
      case 'billing':return 'billing';
      case 'dynamic-pricing':return 'pricing';
      case 'discount-benefits':return 'discounts';
      default:return 'overview';
    }
  };

  const [activeTab, setActiveTab] = useState(getActiveTab(section));

  // Обновляем активную вкладку при изменении секции
  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
  { id: 'overview', label: t('admin2.uf_tab_overview'), icon: 'DollarSign' },
  { id: 'billing', label: t('admin2.uf_tab_billing'), icon: 'Receipt' },
  { id: 'pricing', label: t('admin2.uf_tab_pricing'), icon: 'TrendingUp' },
  { id: 'discounts', label: t('admin2.uf_tab_discounts'), icon: 'Percent' }];


  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderFinance ? renderFinance() : <AdminFinanceOverview />;
      case 'billing':
        return <BillingManager />;
      case 'pricing':
        return <DynamicPricingManager />;
      case 'discounts':
        return <DiscountBenefitsManager />;
      default:
        return renderFinance ? renderFinance() : <AdminFinanceOverview />;
    }
  };

  return (
    <div className="admin-unified-root-no-color">
      <MacOSTab
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab} />
      
      <div className="admin-unified-content">
        <ErrorBoundary>
          {/* P-025 fix: catch runtime errors in child panels */}
          {renderContent()}
        </ErrorBoundary>
      </div>
    </div>);

};

UnifiedFinance.propTypes = {
  renderFinance: PropTypes.func
};

export default UnifiedFinance;
