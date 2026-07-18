
import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert as AlertRaw, Button, Dialog, DialogTitle, DialogContent, DialogActions, Input, Label, Textarea, Icon,
} from '../../ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';
import React from "react";
const Alert = AlertRaw as unknown as React.ComponentType<Record<string, unknown>>;

/**
 * L-H-6 fix: NewTemplateDialog выделен в отдельный файл (~110 строк).
 *
 * Phase 4+: New Template Dialog (was always-visible form).
 * Form fields: code, name, family (select), description.
 *
 * L-L-1 fix: inline-валидация уникальности code перед отправкой.
 * Раньше проверка происходила только на backend — пользователь получал
 * generic error. Теперь показываем явный Alert под полем, если code
 * уже существует в переданном списке templates.
 */
function NewTemplateDialog({ open, onClose, onCreate, saving, existingTemplates = [] }) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [form, setForm] = useState({
    code: '',
    name: '',
    family: 'hematology',
    description: ''
  });

  useEffect(() => {
    if (open) {
      setForm({ code: '', name: '', family: 'hematology', description: '' });
    }
  }, [open]);

  // L-L-1 fix: проверяем уникальность code на клиенте.
  const codeConflict = useMemo(() => {
    if (!form.code.trim()) return null;
    const conflict = existingTemplates.find(
      (t) => t.code.toLowerCase() === form.code.trim().toLowerCase()
    );
    return conflict || null;
  }, [form.code, existingTemplates]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (codeConflict) {
      return; // L-L-1 fix: блокируем отправку если code уже существует
    }
    onCreate(form);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t('misc.ntd_novyy_shablon')}</DialogTitle>
      <DialogContent>
        <form onSubmit={handleSubmit} id="new-template-form" className="ltw-form-grid">
          <div>
            <Label htmlFor="new-template-code" className="ltw-label">{t('misc.ntd_kod_shablona_2')}</Label>
            <Input
              id="new-template-code"
              aria-label={t('misc.ntd_kod_shablona')}
              aria-invalid={Boolean(codeConflict)}
              value={form.code}
              onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
              placeholder={t('misc.ntd_napr_hematology_basic')}
              className="ltw-input-full"
              required
            />
            {/* L-L-1 fix: inline-валидация уникальности code */}
            {codeConflict && (
              <Alert severity="error" sx={{ mt: 1 }}>
                Шаблон с кодом «{codeConflict.code}» уже существует
                {codeConflict.name ? ` (${codeConflict.name})` : ''}.
                Выберите другой код.
              </Alert>
            )}
          </div>
          <div>
            <Label htmlFor="new-template-name" className="ltw-label">{t('common.name')}</Label>
            <Input
              id="new-template-name"
              aria-label={t('misc.ntd_nazvanie_shablona')}
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder={t('misc.ntd_napr_obschiy_analiz_krovi')}
              className="ltw-input-full"
              required
            />
          </div>
          <div>
            <Label htmlFor="new-template-family" className="ltw-label">{t('misc.ntd_semeystvo')}</Label>
            <select
              id="new-template-family"
              aria-label={t('misc.ntd_semeystvo_shablona')}
              value={form.family}
              onChange={(e) => setForm((prev) => ({ ...prev, family: e.target.value }))}
              className="macos-input ltw-input-full"
            >
              <option value="hematology">{t('misc.ntd_gematologiya')}</option>
              <option value="biochemistry">{t('misc.ntd_biohimiya')}</option>
              <option value="coagulation">{t('misc.ntd_koagulologiya')}</option>
              <option value="urinalysis">{t('misc.ntd_obschiy_analiz_mochi')}</option>
              <option value="immunology">{t('misc.ntd_immunologiya')}</option>
              <option value="microbiology">{t('misc.ntd_mikrobiologiya')}</option>
              <option value="endocrinology">{t('misc.ntd_endokrinologiya')}</option>
              <option value="other">{t('misc.ntd_prochee')}</option>
            </select>
          </div>
          <div>
            <Label htmlFor="new-template-description" className="ltw-label">{t('common.description')}</Label>
            <Textarea
              id="new-template-description"
              aria-label={t('misc.ntd_opisanie_shablona')}
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder={t('misc.ntd_kratkoe_opisanie_shablona')}
              minRows={3}
              className="ltw-input-full"
            />
          </div>
        </form>
      </DialogContent>
      <DialogActions>
        <Button variant="outline" onClick={onClose}>{t('common.cancel')}</Button>
        <Button
          variant="primary"
          type="submit"
          form="new-template-form"
          disabled={saving || Boolean(codeConflict)}
        >
          <Icon name="plus" size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
          Создать
        </Button>
      </DialogActions>
    </Dialog>
  );
}

NewTemplateDialog.propTypes = {
  open: PropTypes.bool,
  onClose: PropTypes.func.isRequired,
  onCreate: PropTypes.func.isRequired,
  saving: PropTypes.bool,
  existingTemplates: PropTypes.array,
};

export default NewTemplateDialog;

