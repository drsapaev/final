import type { CSSProperties } from 'react';

import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import {
  Building2,
  Layers,
  Wrench,
  Key,
  HardDrive,
  Settings,
  BarChart3,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Activity } from



'lucide-react';
import {
  MacOSCard,
  Button,
  SegmentedControl as SegmentedControlRaw,
  MacOSStatCard,
  Skeleton as SkeletonRaw,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
} from '../ui/macos';
import BranchManagement from './BranchManagement';
import EquipmentManagement from './EquipmentManagement';
import LicenseManagement from './LicenseManagement';
import BackupManagement from './BackupManagement';
import DepartmentManagement from './DepartmentManagement';
import ClinicSettings from './ClinicSettings';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const SegmentedControl = SegmentedControlRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Skeleton = SkeletonRaw as unknown as React.ComponentType<Record<string, unknown>>;
const ClinicManagement = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [activeTab, setActiveTab] = useState('overview');
  const [systemHealth, setSystemHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [error] = useState(null);
  // UX Audit Admin #3.1: showConfirmModal + pendingAction removed — dead code.
  // setShowConfirmModal(true) was never called anywhere in the file.
  // Other admin components use useConfirm() hook (P-013 fix).

  const tabs = [
  { id: 'overview', label: t('admin2.cm_tab_overview'), icon: BarChart3 },
  { id: 'branches', label: t('admin2.cm_tab_branches'), icon: Building2 },
  { id: 'departments', label: t('admin2.cm_tab_departments'), icon: Layers },
  { id: 'equipment', label: t('admin2.cm_tab_equipment'), icon: Wrench },
  { id: 'licenses', label: t('admin2.cm_tab_licenses'), icon: Key },
  { id: 'backups', label: t('admin2.cm_tab_backups'), icon: HardDrive },
  { id: 'settings', label: t('admin2.cm_tab_settings'), icon: Settings }];


  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async () => {
    try {
      setLoading(true);

      // Загружаем статистику и состояние системы параллельно
      // Эти эндпоинты помечены как некритичные в interceptor, чтобы не перенаправлять на login
      const [statsResponse, healthResponse] = await Promise.allSettled([
      api.get('/clinic/stats').catch((err) => Promise.reject(err)),
      api.get('/clinic/health').catch((err) => Promise.reject(err))]
      );

      // P0 fix: removed hardcoded fake-stats fallback. On API failure, set null
      // so the existing <MacOSEmptyState title="Статистика недоступна" /> renders
      // instead of fabricated numbers (admin was seeing "3 branches, 8 licenses,
      // 12 backups" even when the backend was down).
      if (statsResponse.status === 'fulfilled') {
        setStats(statsResponse.value.data);
      } else {
        logger.error('Ошибка загрузки статистики:', statsResponse.reason);
        setStats(null);
      }

      if (healthResponse.status === 'fulfilled') {
        setSystemHealth(healthResponse.value.data);
      } else {
        logger.error('Ошибка загрузки состояния системы:', healthResponse.reason);
        setSystemHealth(null);
      }
    } catch (error) {
      logger.error('Ошибка загрузки данных системы:', error);
      setStats(null);
      setSystemHealth(null);
      setMessage({ type: 'error', text: t('admin2.cm_err_load_system_data') });
    } finally {
      setLoading(false);
    }
  };










  const getHealthLabel = (status) => {
    switch (status) {
      case 'healthy':return t('admin2.cm_health_healthy');
      case 'warning':return t('admin2.cm_health_warning');
      case 'critical':return t('admin2.cm_health_critical');
      default:return t('admin2.cm_health_unknown');
    }
  };

  // UX Audit Admin #3.1: handleConfirmAction removed — dead code.








  const renderOverview = () =>
  <div className="flex flex-col gap-6">
      {/* Состояние системы */}
      <MacOSCard className="p-4">
          <div className="admin-d-flex-ai-center-jc-between-mb-16">
          <h3 className="admin-fs-lg-fw-semi-primary-m-0-2">
            {t('admin2.cm_system_status_title')}
          </h3>
          <Button
          variant="outline"
          onClick={loadSystemData}
          disabled={loading}
          title="Refresh system status"
          aria-label="Refresh system status"
          className="admin-p-6px-12px-minw-auto">
          
            <RefreshCw className="admin-w-16-h-16-anim-dyn" style={{ '--admin-anim0': loading ? 'spin 1s linear infinite' : 'none' } as CSSProperties} />
          </Button>
        </div>
        
        {systemHealth ?
      <div className="flex flex-col gap-4">
            <div className="admin-flex-center-12">
              <Badge
            variant={systemHealth.status === 'healthy' ? 'success' :
            systemHealth.status === 'warning' ? 'warning' : 'error'}
            text={getHealthLabel(systemHealth.status)} />
          
              <span className="text-sm text-[var(--mac-text-secondary)]">
                {t('admin2.cm_last_check', { date: new Date().toLocaleString() })}
              </span>
            </div>
            
            {systemHealth.warnings && systemHealth.warnings.length > 0 &&
        <div className="flex flex-col gap-2">
                <h4 className="admin-fs-sm-fw-med-primary-1">
                  {t('admin2.cm_warnings_label')}
                </h4>
                {systemHealth.warnings.map((warning, index) =>
          <div key={index} className="admin-d-flex-ai-center-gap-8-fs-sm-warning">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{warning}</span>
                  </div>
          )}
              </div>
        }
          </div> :

      <MacOSEmptyState
        icon={Activity}
        title={t('admin2.cm_loading_system_status')}
        description={t('admin2.cm_loading_system_status_desc')} />

      }
      </MacOSCard>

      {/* Статистика */}
      {stats ?
    <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <MacOSStatCard
        title={t('admin2.cm_stat_branches')}
        value={stats.total_branches}
        subtitle={t('admin2.cm_stat_branches_active', { count: stats.active_branches })}
        icon={Building2}
        iconColor="var(--mac-accent-blue)"
        trend="positive" />
      

          <MacOSStatCard
        title={t('admin2.cm_stat_equipment')}
        value={stats.total_equipment}
        subtitle={t('admin2.cm_stat_equipment_active', { count: stats.active_equipment })}
        icon={Wrench}
        iconColor="var(--mac-success)"
        trend="positive" />
      

          <MacOSStatCard
        title={t('admin2.cm_stat_licenses')}
        value={stats.total_licenses}
        subtitle={t('admin2.cm_stat_licenses_active', { count: stats.active_licenses })}
        icon={Key}
        iconColor="var(--mac-warning)"
        trend="positive" />
      

          <MacOSStatCard
        title={t('admin2.cm_stat_backups')}
        value={stats.total_backups}
        subtitle={t('admin2.cm_stat_backups_recent', { count: stats.recent_backups })}
        icon={HardDrive}
        iconColor="var(--mac-error)"
        trend="neutral" />
      
        </div> :

    <MacOSEmptyState
      icon={BarChart3}
      title={t('admin2.cm_stats_unavailable')}
      description={t('admin2.cm_stats_unavailable_desc')} />

    }

      {/* UX Audit Admin #1.8+4.4: блок «Быстрые действия» удалён.
          4 кнопки дублировали SegmentedControl табы (branches/equipment/licenses/backups).
          64 строки JSX + 8 inline onMouseEnter/onMouseLeave → 0.
          SegmentedControl выше (строка ~400) обеспечивает навигацию. */}

      {/* Системная информация */}
      {/* UX Audit Admin #2.5: динамические данные из systemHealth вместо hardcoded. */}
      <MacOSCard className="p-4">
          <h3 className="admin-fs-lg-fw-semi-primary-mb-16">
            {t('admin2.cm_system_info')}
          </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16-fw-wrap">
          <div className="flex flex-col gap-2">
            <div className="admin-d-flex-jc-between-fs-sm-5">
              <span className="text-[var(--mac-text-secondary)]">{t('admin2.cm_label_system_status')}</span>
              <Badge variant={systemHealth?.overall_status === 'healthy' ? 'success' : 'error'}
                text={systemHealth?.overall_status === 'healthy' ? t('admin2.cm_status_running') : t('admin2.cm_status_error')} />
            </div>
            <div className="admin-d-flex-jc-between-fs-sm-3">
              <span className="text-[var(--mac-text-secondary)]">{t('admin2.cm_label_db_status')}</span>
              <Badge variant={systemHealth?.db === 'healthy' ? 'success' : 'error'}
                text={systemHealth?.db === 'healthy' ? t('admin2.cm_db_connected') : t('admin2.cm_db_unavailable')} />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <div className="admin-d-flex-jc-between-fs-sm-2">
              <span className="text-[var(--mac-text-secondary)]">{t('admin2.cm_label_last_update')}</span>
              <span className="admin-fw-med-primary-1">
                {new Date().toLocaleDateString()}
              </span>
            </div>
            <div className="admin-d-flex-jc-between-fs-sm">
              <span className="text-[var(--mac-text-secondary)]">{t('admin2.cm_label_security')}</span>
              <Badge variant={systemHealth?.security === 'active' ? 'success' : 'warning'}
                text={systemHealth?.security === 'active' ? t('admin2.cm_security_active') : t('admin2.cm_security_check_settings')} />
            </div>
          </div>
        </div>
      </MacOSCard>
    </div>;



  // Состояние загрузки
  if (loading) {
    return (
      <div className="admin-p-0-bgc-bg-primary-2">
        <MacOSCard className="p-6">
          <div className="admin-d-flex-ai-center-gap-12-mb-24-1">
            <Building2 className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0-1">
              {t('admin2.cm_page_title')}
            </h2>
          </div>
          <Skeleton height="600px" />
        </MacOSCard>
      </div>);

  }

  // Критическая ошибка загрузки
  if (error && !stats) {
    return (
      <div className="admin-p-0-bgc-bg-primary-1">
        <MacOSCard className="p-6">
          <div className="admin-d-flex-ai-center-gap-12-mb-24">
            <Building2 className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              {t('admin2.cm_page_title')}
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertTriangle}
            title={t('admin2.cm_load_data_failed')}
            description={t('admin2.cm_load_data_failed_desc')}
            action={
            <Button onClick={loadSystemData} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('admin2.cm_retry')}
              </Button>
            } />
          
        </MacOSCard>
      </div>);

  }

  return (
    <div className="admin-p-0-bgc-bg-primary">
      <MacOSCard className="admin-p-0-ov-hidden">
        <div className="admin-p-16-ov-hidden">
          {/* Заголовок */}
          <div className="admin-d-flex-jc-between-ai-center-mb-24-pb-24-bd-b-1px-solid-var-mac-bo">
          <div>
            <h1 className="admin-fs-var-mac-font-size-3x-fw-bold-primary-m-0-0-8px-0">
              {t('admin2.cm_page_title')}
            </h1>
            <p className="admin-secondary-fs-sm-m-0-2">
              {t('admin2.cm_page_subtitle')}
            </p>
          </div>
        </div>

        {/* Сообщения */}
        {message.text &&
          <Alert
            type={message.type === 'success' ? 'success' : 'error'}
            title={message.type === 'success' ? t('admin2.cm_success') : t('admin2.cm_status_error')}
            message={message.text}
            className="mb-6" />

          }

        {/* Некритические ошибки */}
        {error && stats &&
          <Alert
            type="warning"
            title={t('admin2.cm_warning')}
            message={error}
            className="mb-6" />

          }

        {/* Навигация по вкладкам */}
        <div className="admin-maxw-100pct-ovx-auto-pb-6-mb-24-scrollba-thin">
          <SegmentedControl
            aria-label={t('admin2.cm_tabs_aria')}
            value={activeTab}
            onChange={(v: any) => setActiveTab(String(v))}
            options={tabs.map((tab) => {
              const IconComponent = tab.icon;
              return {
                value: tab.id,
                label: (
                  <span className="admin-d-inline-flex-ai-center-gap-8">
                    {IconComponent && <IconComponent size={14 as unknown as "small" | "default" | "large" | "xlarge"} aria-hidden="true" />}
                    {tab.label}
                  </span>
                )
              };
            })}
            size="large"
            className="admin-minw-max-content-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-14-bsh-var-mac-main-shell-s" />
        </div>

        {/* Содержимое вкладок */}
        {activeTab === 'overview' && renderOverview()}
        {activeTab === 'branches' && <BranchManagement />}
        {activeTab === 'departments' && <DepartmentManagement />}
        {activeTab === 'equipment' && <EquipmentManagement />}
        {activeTab === 'licenses' && <LicenseManagement />}
        {activeTab === 'backups' && <BackupManagement />}
        {activeTab === 'settings' && <ClinicSettings />}
        </div>
      </MacOSCard>

      {/* UX Audit Admin #3.1: dead Modal removed — was never opened. */}
    </div>);

};

export default ClinicManagement;
