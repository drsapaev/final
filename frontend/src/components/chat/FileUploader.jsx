
import { useRef, useState } from 'react';
import { Paperclip } from 'lucide-react';
import './FileUploader.css';
import PropTypes from 'prop-types';
import { validateFile } from '../../utils/fileValidator';  // PR-36 / P0-4
import { toast } from 'react-toastify';
import { useTranslation } from '../../i18n/adapter';

const FileUploader = ({ onUpload, disabled }) => {
  const { t } = useTranslation();
  const fileInputRef = useRef(null);
  const [isValidating, setIsValidating] = useState(false);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (file) {
      // PR-36 / P0-4: Validate file via magic-number check before upload.
      // Previously: file was passed directly to onUpload() with only the
      // UX-only `accept` attribute as a guard (trivially bypassed).
      // Now: validateFile() reads the file header and verifies the magic
      // number matches the declared MIME type. Blocks spoofed uploads
      // (e.g., .exe renamed to .jpg).
      setIsValidating(true);
      try {
        const result = await validateFile(file, {
          allowedCategories: ['images', 'documents'],
          maxSize: 25 * 1024 * 1024, // 25MB — matches nginx client_max_body_size
        });
        if (!result.valid) {
          const msg = result.errors.join('; ');
          toast.error(`Файл отклонён: ${msg}`);
          e.target.value = null;
          return;
        }
        if (result.warnings.length > 0) {
          result.warnings.forEach((w) => toast.warn(w));
        }
        onUpload(file);
      } catch (_err) {
        toast.error('Не удалось проверить файл. Попробуйте ещё раз.');
        return;
      } finally {
        setIsValidating(false);
      }
      // Reset input
      e.target.value = null;
    }
  };

  return (
    <div className="file-uploader">
            <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
        aria-label="Выбрать файл для прикрепления"
        disabled={disabled} />
      
            <button
        type="button"
        className="file-uploader-btn"
        onClick={() => fileInputRef.current?.click()}
        disabled={disabled || isValidating}
        title="Прикрепить файл"
        aria-label="Прикрепить файл">
        
                <Paperclip size={18} />
            </button>
        </div>);

};


FileUploader.propTypes = {
  ...(FileUploader.propTypes || {}),
  disabled: PropTypes.any,
  onUpload: PropTypes.any,
};

export default FileUploader;
