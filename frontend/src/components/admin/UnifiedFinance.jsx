import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import BillingManager from './BillingManager';
import DynamicPricingManager from './DynamicPricingManager';
import DiscountBenefitsManager from './DiscountBenefitsManager';
import { useTheme } from '../../contexts/ThemeContext';

// Простой компонент вкладок для админки
const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  const { isDark } = useTheme();
  const colors = {
    bg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.98)',
    border: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)',
    text: isDark ? '#f8fafc' : '#0f172a',
    textSecondary: isDark ? '#cbd5e1' : '#64748b',
    active: isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)',
    activeText: '#3b82f6'
  };

  return (
    <div style={{
      display: 'flex',
      gap: '4px',
      padding: '8px',
      background: colors.bg,
      borderRadius: '8px',
      border: `1px solid ${colors.border}`,
      marginBottom: '20px'
    }}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          style={{
            padding: '8px 16px',
            border: 'none',
            borderRadius: '6px',
            background: activeTab === tab.id ? colors.active : 'transparent',
            color: activeTab === tab.id ? colors.activeText : colors.text,
            fontSize: '14px',
            fontWeight: activeTab === tab.id ? '600' : '400',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
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
  const { isDark } = useTheme();

  const getActiveTab = (section) => {
    switch (section) {
      case 'finance': return 'overview';
      case 'billing': return 'billing';
      case 'dynamic-pricing': return 'pricing';
      case 'discount-benefits': return 'discounts';
      default: return 'overview';
    }
  };

  const [activeTab, setActiveTab] = useState(getActiveTab(section));

  // Обновляем активную вкладку при изменении секции
  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
    { id: 'overview', label: 'Finance Overview', icon: 'DollarSign' },
    { id: 'billing', label: 'Billing', icon: 'Receipt' },
    { id: 'pricing', label: 'Dynamic Pricing', icon: 'TrendingUp' },
    { id: 'discounts', label: 'Discount Benefits', icon: 'Percent' }
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'overview':
        return renderFinance ? renderFinance() : <div>Finance Overview Content</div>;
      case 'billing':
        return <BillingManager />;
      case 'pricing':
        return <DynamicPricingManager />;
      case 'discounts':
        return <DiscountBenefitsManager />;
      default:
        return renderFinance ? renderFinance() : <div>Finance Overview Content</div>;
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <AdminTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <div style={{ flex: 1, overflow: 'auto' }}>
        {renderContent()}
      </div>
    </div>
  );
};

UnifiedFinance.propTypes = {
  renderFinance: PropTypes.func
};

export default UnifiedFinance;
