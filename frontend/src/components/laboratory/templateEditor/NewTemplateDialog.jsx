import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Button, Dialog, DialogTitle, DialogContent, DialogActions, Input, Label, Textarea, Icon,
} from '../../ui/macos';

/**
 * L-H-6 fix: NewTemplateDialog выделен в отдельный файл (~90 строк).
 *
 * Phase 4+: New Template Dialog (was always-visible form).
 * Form fields: code, name, family (select), description.
 */
function NewTemplateDialog({ open, onClose, onCreate, saving }) {
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

  const handleSubmit = (e) => {
    e.preventDefault();
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
              value={form.code}
              onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
              placeholder="Напр. hematology_basic"
              className="ltw-input-full"
              required
            />
          </div>
          <div>
            <Label htmlFor="new-template-name" className="ltw-label">Название</Label>
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
            {/* PR-59: replaced free-text Input with <select> to prevent typo-induced fragmentation */}
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
            <Label htmlFor="new-template-description" className="ltw-label">Описание</Label>
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
        <Button variant="outline" onClick={onClose}>Отмена</Button>
        <Button variant="primary" type="submit" form="new-template-form" disabled={saving}>
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
};

export default NewTemplateDialog;
