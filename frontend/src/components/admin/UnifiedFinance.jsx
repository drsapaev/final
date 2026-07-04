import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import BillingManager from './BillingManager';
import DynamicPricingManager from './DynamicPricingManager';
import DiscountBenefitsManager from './DiscountBenefitsManager';
import AdminFinanceOverview from './AdminFinanceOverview';
import { useTheme } from '../../contexts/ThemeContext';
import ErrorBoundary from '../common/ErrorBoundary';

// Простой компонент вкладок для админки
const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  return (
    <div className="admin-tab-bar-flex-dyn" style={{ '--admin-bg': 'var(--mac-card-bg)', '--admin-bd': '1px solid var(--mac-card-border)' }}>
      {tabs.map((tab) =>
      <button
        key={tab.id}
        onClick={() => onTabChange(tab.id)}
        className="admin-tab-btn-dyn"
        style={{
          '--admin-tab-bg': activeTab === tab.id ? 'color-mix(in srgb, var(--mac-accent-blue), transparent 88%)' : 'transparent',
          '--admin-tab-color': activeTab === tab.id ? 'var(--mac-accent-blue)' : 'var(--mac-text-primary)',
          '--admin-tab-fw': activeTab === tab.id ? '600' : '400',
        }}>
        
          {tab.label}
        </button>
      )}
    </div>);

};

AdminTabs.propTypes = {
  tabs: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired
  })).isRequired,
  activeTab: PropTypes.string.isRequired,
  onTabChange: PropTypes.func.isRequired
};

const UnifiedFinance = ({ renderFinance }) => {
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
  { id: 'overview', label: 'Обзор', icon: 'DollarSign' },
  { id: 'billing', label: 'Счета', icon: 'Receipt' },
  { id: 'pricing', label: 'Ценообразование', icon: 'TrendingUp' },
  { id: 'discounts', label: 'Скидки и льготы', icon: 'Percent' }];


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
      <AdminTabs
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
