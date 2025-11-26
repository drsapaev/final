import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import MedicalImageAnalyzer from '../ai/MedicalImageAnalyzer';
import TreatmentRecommendations from '../ai/TreatmentRecommendations';
import DrugInteractionChecker from '../ai/DrugInteractionChecker';
import RiskAssessment from '../ai/RiskAssessment';
import VoiceToText from '../ai/VoiceToText';
import SmartScheduling from '../ai/SmartScheduling';
import QualityControl from '../ai/QualityControl';
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

const UnifiedAITools = () => {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'ai-imaging';
  const { isDark } = useTheme();

  const getActiveTab = (section) => {
    switch (section) {
      case 'ai-imaging': return 'imaging';
      case 'treatment-recommendations': return 'treatment';
      case 'drug-interactions': return 'drugs';
      case 'risk-assessment': return 'risk';
      case 'voice-to-text': return 'voice';
      case 'smart-scheduling': return 'scheduling';
      case 'quality-control': return 'quality';
      default: return 'imaging';
    }
  };

  const [activeTab, setActiveTab] = useState(getActiveTab(section));

  // Обновляем активную вкладку при изменении секции
  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
    { id: 'imaging', label: 'Medical Imaging', icon: 'Image' },
    { id: 'treatment', label: 'Treatment Recs', icon: 'Heart' },
    { id: 'drugs', label: 'Drug Interactions', icon: 'Pill' },
    { id: 'risk', label: 'Risk Assessment', icon: 'AlertTriangle' },
    { id: 'voice', label: 'Voice to Text', icon: 'Mic' },
    { id: 'scheduling', label: 'Smart Scheduling', icon: 'Calendar' },
    { id: 'quality', label: 'Quality Control', icon: 'CheckCircle' }
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'imaging':
        return <MedicalImageAnalyzer />;
      case 'treatment':
        return <TreatmentRecommendations />;
      case 'drugs':
        return <DrugInteractionChecker />;
      case 'risk':
        return <RiskAssessment />;
      case 'voice':
        return <VoiceToText />;
      case 'scheduling':
        return <SmartScheduling />;
      case 'quality':
        return <QualityControl />;
      default:
        return <MedicalImageAnalyzer />;
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

export default UnifiedAITools;
