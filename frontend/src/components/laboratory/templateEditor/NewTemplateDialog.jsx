import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert, Button, Dialog, DialogTitle, DialogContent, DialogActions, Input, Label, Textarea, Icon,
} from '../../ui/macos';
import { useTranslation } from '../../../i18n/adapter';

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
  const { t } = useTranslation();
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
      <DialogTitle>Новый шаблон</DialogTitle>
      <DialogContent>
        <form onSubmit={handleSubmit} id="new-template-form" className="ltw-form-grid">
          <div>
            <Label htmlFor="new-template-code" className="ltw-label">Код шаблона</Label>
            <Input
              id="new-template-code"
              aria-label="Код шаблона"
              aria-invalid={Boolean(codeConflict)}
              value={form.code}
              onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
              placeholder="Напр. hematology_basic"
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
              aria-label="Название шаблона"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Напр. Общий анализ крови"
              className="ltw-input-full"
              required
            />
          </div>
          <div>
            <Label htmlFor="new-template-family" className="ltw-label">Семейство</Label>
            <select
              id="new-template-family"
              aria-label="Семейство шаблона"
              value={form.family}
              onChange={(e) => setForm((prev) => ({ ...prev, family: e.target.value }))}
              className="macos-input ltw-input-full"
            >
              <option value="hematology">Гематология</option>
              <option value="biochemistry">Биохимия</option>
              <option value="coagulation">Коагулология</option>
              <option value="urinalysis">Общий анализ мочи</option>
              <option value="immunology">Иммунология</option>
              <option value="microbiology">Микробиология</option>
              <option value="endocrinology">Эндокринология</option>
              <option value="other">Прочее</option>
            </select>
          </div>
          <div>
            <Label htmlFor="new-template-description" className="ltw-label">{t('common.description')}</Label>
            <Textarea
              id="new-template-description"
              aria-label="Описание шаблона"
              value={form.description}
              onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Краткое описание шаблона"
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
          <Icon name="plus" size={16} />
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

