import type { CSSProperties } from 'react';

import { useState, useEffect } from 'react';
import {
  Settings,
  Save,
  RefreshCw,
  Calendar,
  Percent,
  CheckCircle,
  AlertCircle,
  Info,
  Clock,
  DollarSign,
  Shield
} from 'lucide-react';
import {
  MacOSCard,
  Button,
  Input,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
  MacOSStatCard,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { fetchBenefitSettings, saveBenefitSettings } from '../../api/adminSettings';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
/**
 * Компонент для управления настройками льгот в админке
 */
const BenefitSettings = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [settings, setSettings] = useState<Record<string, any>>({
    repeat_visit_days: 21,
    repeat_visit_discount: 0,
    benefit_consultation_free: true,
    all_free_auto_approve: false
  });
  const [originalSettings, setOriginalSettings] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [error, setError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const data = await fetchBenefitSettings();
      setSettings(data);
      setOriginalSettings(data);
      setLastUpdated(new Date(data?.updated_at as any));
    } catch (error) {
      logger.error('Error loading benefit settings:', error);
      setError(error.response?.data?.detail || t('admin2.bs_error_load_settings'));
      toast.error(t('admin2.bs_toast_load_error'));
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setShowConfirmModal(true);
  };

  const confirmSave = async () => {
    setSaving(true);
    setShowConfirmModal(false);
    try {
      const response = await saveBenefitSettings(settings);
      toast.success(response?.message || t('admin2.bs_toast_saved'));
      setOriginalSettings(settings);
      setLastUpdated(new Date());
    } catch (error) {
      logger.error('Error saving benefit settings:', error);
      toast.error(error.response?.data?.detail || t('admin2.bs_toast_save_error'));
    } finally {
      setSaving(false);
    }
  };

  const resetSettings = () => {
    setSettings(originalSettings);
  };

  const hasChanges = () => {
    return JSON.stringify(settings) !== JSON.stringify(originalSettings);
  };

  const handleInputChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }));
  };

  if (loading) {
    return (
      <div className="admin-benefit-container">
        <MacOSCard className="p-6">
          <div className="admin-flex-center-12 mb-6">
            <Settings className="admin-icon-32-blue" />
            <h2 className="admin-benefit-h2">
              {t('admin2.bs_title')}
            </h2>
          </div>
          <Skeleton height="600px" />
        </MacOSCard>
      </div>
    );
  }

  // Критическая ошибка загрузки
  if (error && !settings?.updated_at as any) {
    return (
      <div className="admin-benefit-container">
        <MacOSCard className="p-6">
          <div className="admin-flex-center-12 mb-6">
            <Settings className="admin-icon-32-blue" />
            <h2 className="admin-benefit-h2">
              {t('admin2.bs_title')}
            </h2>
          </div>
          <MacOSEmptyState
            icon={AlertCircle}
            title={t('admin2.bs_empty_title')}
            description={t('admin2.bs_empty_desc')}
            action={
              <Button onClick={loadSettings} variant="primary">
                <RefreshCw className="w-4 h-4 mr-2" />
                {t('admin2.bs_btn_retry')}
              </Button>
            }
          />
        </MacOSCard>
      </div>
    );
  }

  return (
    <div className="admin-benefit-container">
      <MacOSCard className="p-6">
        <div className="flex flex-col gap-6">
          {/* Критическая ошибка */}
          {error && (
            <Alert
              type="error"
              title={t('admin2.bs_alert_load_error_title')}
              message={error}
              onClose={() => setError(null)}
            />
          )}

          {/* Header */}
          <div className="admin-benefit-header">
            <div>
              <h2 className="admin-benefit-h2-with-icon">
                <Settings className="admin-icon-32-blue" />
                {t('admin2.bs_title')}
              </h2>
              <p className="admin-setting-desc">
                {t('admin2.bs_header_subtitle')}
              </p>
            </div>

            <div className="admin-flex-center-16">
              {lastUpdated && (
                <div className="admin-benefit-updated">
                  {t('admin2.bs_updated_at', { date: lastUpdated.toLocaleDateString('ru-RU'), time: lastUpdated.toLocaleTimeString('ru-RU') })}
                </div>
              )}

              <Button
                onClick={loadSettings}
                disabled={loading}
                variant="outline"
                className="admin-action-btn"
              >
                <RefreshCw className="admin-refresh-conditional" style={{ '--admin-spin-anim': loading ? 'admin-spin 1s linear infinite' : 'none' } as CSSProperties} />
                {t('admin2.bs_btn_refresh')}
              </Button>
            </div>
          </div>

          {/* Настройки */}
          <div className="admin-grid-auto-400-24">
            {/* Повторные визиты */}
            <MacOSCard className="admin-settings-card" style={{ '--admin-card-transform': settings.repeat_visit_discount > 0 ? 'scale(1.02)' : 'scale(1)' } as CSSProperties}>
              <div className="admin-setting-card-header">
                <div className="admin-icon-bg-success">
                  <Calendar className="admin-icon-20-success" />
                </div>
                <div>
                  <div className="admin-setting-title">
                    <h3 className="admin-setting-h3">
                      {t('admin2.bs_card_repeat_visits_title')}
                    </h3>
                    <Badge
                      variant={settings.repeat_visit_discount > 0 ? 'success' : 'secondary'}
                      size="small"
                    >
                      {settings.repeat_visit_discount > 0 ? t('admin2.bs_status_active') : t('admin2.bs_status_inactive')}
                    </Badge>
                  </div>
                  <p className="admin-setting-desc">
                    {t('admin2.bs_card_repeat_visits_desc')}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                {/* Окно повторного визита */}
                <div>
                  <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                    {t('admin2.bs_label_repeat_window')}
                  </label>
                  <div className="admin-flex-center-12">
                    <div className="admin-input-icon-wrap">
                      <Clock className="admin-input-icon" />
                      <Input
                        type="number"
                        min="1"
                        max="365"
                        value={settings.repeat_visit_days}
                        onChange={(e) => handleInputChange('repeat_visit_days', parseInt(e.target.value) || 21)}
                        placeholder="21"
                        className="admin-input-with-icon"
                      />
                    </div>
                    <span className="admin-unit-span">
                      {t('admin2.bs_unit_days')}
                    </span>
                  </div>
                  <p className="admin-help-p">
                    {t('admin2.bs_help_repeat_window')}
                  </p>
                </div>

                {/* Скидка на повторный визит */}
                <div>
                  <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                    {t('admin2.bs_label_repeat_discount')}
                  </label>
                  <div className="admin-flex-center-12">
                    <div className="admin-input-icon-wrap">
                      <Percent className="admin-input-icon" />
                      <Input
                        type="number"
                        min="0"
                        max="100"
                        value={settings.repeat_visit_discount}
                        onChange={(e) => handleInputChange('repeat_visit_discount', parseInt(e.target.value) || 0)}
                        placeholder="0"
                        className="admin-input-with-icon"
                      />
                    </div>
                    <span className="admin-unit-span">
                      %
                    </span>
                  </div>
                  <p className="admin-help-p">
                    {t('admin2.bs_help_repeat_discount')}
                  </p>
                </div>

                {/* Информационная карточка */}
                <MacOSCard className="admin-info-card-accent">
                  <div className="admin-info-row">
                    <Info className="admin-info-icon-blue" />
                    <div className="admin-info-text-blue">
                      <p className="admin-info-p-mt-8">
                        {t('admin2.bs_info_repeat_title')}
                      </p>
                      <ul className="admin-info-list">
                        <li>{t('admin2.bs_info_repeat_li_1')}</li>
                        <li>{t('admin2.bs_info_repeat_li_2')}</li>
                        <li>{t('admin2.bs_info_repeat_li_3')}</li>
                      </ul>
                    </div>
                  </div>
                </MacOSCard>
              </div>
            </MacOSCard>

            {/* Льготные визиты */}
            <MacOSCard className="admin-settings-card" style={{ '--admin-card-transform': settings.benefit_consultation_free ? 'scale(1.02)' : 'scale(1)' } as CSSProperties}>
              <div className="admin-setting-card-header">
                <div className="admin-icon-bg-warning">
                  <Shield className="admin-icon-20-warning" />
                </div>
                <div>
                  <div className="admin-setting-title">
                    <h3 className="admin-setting-h3">
                      {t('admin2.bs_card_benefit_visits_title')}
                    </h3>
                    <Badge
                      variant={settings.benefit_consultation_free ? 'success' : 'warning'}
                      size="small"
                    >
                      {settings.benefit_consultation_free ? t('admin2.bs_status_free') : t('admin2.bs_status_paid')}
                    </Badge>
                  </div>
                  <p className="admin-setting-desc">
                    {t('admin2.bs_card_benefit_visits_desc')}
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-4">
                {/* Льготные консультации бесплатны */}
                <div>
                  <div className="admin-info-row">
                    <Checkbox
                      checked={settings.benefit_consultation_free}
                      onChange={(checked) => handleInputChange('benefit_consultation_free', checked)}
                    />
                    <div>
                      <span className="admin-setting-label-block">
                        {t('admin2.bs_chk_benefit_free')}
                      </span>
                      <p className="admin-setting-p-tertiary">
                        {t('admin2.bs_chk_benefit_free_desc')}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Автоодобрение All Free */}
                <div>
                  <div className="admin-info-row">
                    <Checkbox
                      checked={settings.all_free_auto_approve}
                      onChange={(checked) => handleInputChange('all_free_auto_approve', checked)}
                    />
                    <div>
                      <span className="admin-setting-label-block">
                        {t('admin2.bs_chk_auto_approve')}
                      </span>
                      <p className="admin-setting-p-tertiary">
                        {t('admin2.bs_chk_auto_approve_desc')}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Предупреждение об автоодобрении */}
                {settings.all_free_auto_approve && (
                  <MacOSCard className="admin-info-card-warning">
                    <div className="admin-info-row">
                      <AlertCircle className="admin-info-icon-warning" />
                      <div className="admin-info-text-warning">
                        <p className="admin-info-p-mt-4">
                          {t('admin2.bs_warning_title')}
                        </p>
                        <p className="admin-text-xs admin-m-0">
                          {t('admin2.bs_warning_auto_approve_desc')}
                        </p>
                      </div>
                    </div>
                  </MacOSCard>
                )}

                {/* Информационная карточка */}
                <MacOSCard className="admin-info-card-warning">
                  <div className="admin-info-row">
                    <Info className="admin-info-icon-warning" />
                    <div className="admin-info-text-warning">
                      <p className="admin-info-p-mt-8">
                        {t('admin2.bs_info_benefit_types_title')}
                      </p>
                      <ul className="admin-info-list">
                        <li>• <strong>{t('admin2.bs_info_benefit_type_lgotnyy')}</strong>{t('admin2.bs_info_benefit_type_lgotnyy_desc')}</li>
                        <li>• <strong>All Free</strong>{t('admin2.bs_info_benefit_type_allfree_desc')}</li>
                      </ul>
                    </div>
                  </div>
                </MacOSCard>
              </div>
            </MacOSCard>
          </div>

          {/* Действия */}
          <div className="admin-actions-bar">
            <div className="flex items-center justify-center gap-2">
              {hasChanges() && (
                <div className="admin-unsaved-badge">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {t('admin2.bs_unsaved_changes')}
                </div>
              )}
            </div>

            <div className="admin-flex-gap-12-wrap">
              {hasChanges() && (
                <Button
                  onClick={resetSettings}
                  variant="outline"
                  disabled={saving}
                  className="admin-action-btn"
                >
                  {t('admin2.bs_btn_cancel')}
                </Button>
              )}

              <Button
                onClick={saveSettings}
                disabled={saving || !hasChanges()}
                className="admin-action-btn-primary"
              >
                {saving ? (
                  <RefreshCw className="admin-icon-16-spin-mr-8 admin-mr-0" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {saving ? t('admin2.bs_btn_saving') : t('admin2.bs_btn_save')}
              </Button>
            </div>
          </div>

          {/* Статистика настроек */}
          <div className="admin-grid-auto-200">
            <MacOSStatCard
              title={t('admin2.bs_stat_repeat_window_title')}
              value={`${settings.repeat_visit_days} ${t('admin2.bs_unit_days')}`}
              icon={Calendar}
              color="blue"
              trend={settings.repeat_visit_discount > 0 ? t('admin2.bs_trend_discount_active') : t('admin2.bs_trend_discount_inactive')}
              trendColor={settings.repeat_visit_discount > 0 ? 'var(--mac-success)' : 'var(--mac-text-secondary)'}
            />

            <MacOSStatCard
              title={t('admin2.bs_stat_discount_title')}
              value={`${settings.repeat_visit_discount}%`}
              icon={Percent}
              color={settings.repeat_visit_discount > 0 ? 'green' : 'orange'}
              trend={settings.repeat_visit_discount > 0 ? t('admin2.bs_trend_applied') : t('admin2.bs_trend_not_applied')}
              trendColor={settings.repeat_visit_discount > 0 ? 'var(--mac-success)' : 'var(--mac-warning)'}
            />

            <MacOSStatCard
              title={t('admin2.bs_stat_benefit_title')}
              value={settings.benefit_consultation_free ? t('admin2.bs_status_free') : t('admin2.bs_status_paid')}
              icon={Shield}
              color={settings.benefit_consultation_free ? 'green' : 'orange'}
              trend={settings.benefit_consultation_free ? t('admin2.bs_status_active') : t('admin2.bs_status_inactive')}
              trendColor={settings.benefit_consultation_free ? 'var(--mac-success)' : 'var(--mac-warning)'}
            />

            <MacOSStatCard
              title={t('admin2.bs_stat_auto_approve_title')}
              value={settings.all_free_auto_approve ? t('admin2.bs_status_enabled') : t('admin2.bs_status_disabled')}
              icon={CheckCircle}
              color={settings.all_free_auto_approve ? 'orange' : 'blue'}
              trend={settings.all_free_auto_approve ? t('admin2.bs_trend_auto') : t('admin2.bs_trend_manual')}
              trendColor={settings.all_free_auto_approve ? 'var(--mac-warning)' : 'var(--mac-info)'}
            />
          </div>

          {/* Предварительный просмотр */}
          <MacOSCard className="admin-preview-card">
            <h4 className="admin-preview-h4">
              {t('admin2.bs_preview_title')}
            </h4>
            <div className="admin-preview-grid">
              <div className="flex items-center justify-center gap-2">
                <Calendar className="admin-icon-14-tertiary" />
                <span className="text-[var(--mac-text-secondary)]">
                  {t('admin2.bs_preview_window', { days: settings.repeat_visit_days })}
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <DollarSign className="admin-icon-14-tertiary" />
                <span className="text-[var(--mac-text-secondary)]">
                  {t('admin2.bs_preview_discount', { discount: settings.repeat_visit_discount })}
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <CheckCircle className="admin-icon-14-color" style={{ '--admin-icon-color': settings.benefit_consultation_free ? 'var(--mac-success)' : 'var(--mac-text-tertiary)' } as CSSProperties} />
                <span className="text-[var(--mac-text-secondary)]">
                  {t('admin2.bs_preview_benefits', { state: settings.benefit_consultation_free ? t('admin2.bs_status_free') : t('admin2.bs_status_paid') })}
                </span>
              </div>
              <div className="flex items-center justify-center gap-2">
                <Shield className="admin-icon-14-color" style={{ '--admin-icon-color': settings.all_free_auto_approve ? 'var(--mac-warning)' : 'var(--mac-text-tertiary)' } as CSSProperties} />
                <span className="text-[var(--mac-text-secondary)]">
                  All Free: {settings.all_free_auto_approve ? t('admin2.bs_status_auto_approve') : t('admin2.bs_status_manual_approve')}
                </span>
              </div>
            </div>
          </MacOSCard>
        </div>
      </MacOSCard>

      {/* Модальное окно подтверждения */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title={t('admin2.bs_modal_confirm_title')}
        size="small"
      >
        <div className="p-6">
          <p className="admin-confirm-p">
            {t('admin2.bs_modal_confirm_text')}
          </p>

          <div className="admin-flex-end-12">
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}
              disabled={saving}
            >
              {t('admin2.bs_modal_cancel')}
            </Button>
            <Button
              onClick={confirmSave}
              disabled={saving}
              aria-label="Confirm benefit settings save"
              className="admin-confirm-primary"
            >
              {saving ? (
                <>
                  <RefreshCw className="admin-refresh-mr-8-conditional" style={{ '--admin-spin-anim': 'admin-spin 1s linear infinite' } as CSSProperties} />
                  {t('admin2.bs_btn_saving')}
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 mr-2" />
                  {t('admin2.bs_modal_confirm')}
                </>
              )}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default BenefitSettings;

