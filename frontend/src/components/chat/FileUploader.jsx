
import { useRef } from 'react';
import { Paperclip } from 'lucide-react';
import './FileUploader.css';
import PropTypes from 'prop-types';

const FileUploader = ({ onUpload, disabled }) => {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onUpload(file);
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
        disabled={disabled}
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
