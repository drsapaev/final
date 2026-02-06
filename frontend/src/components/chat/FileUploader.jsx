
import React, { useRef } from 'react';
import { Paperclip, Image as ImageIcon, X } from 'lucide-react';
import './FileUploader.css';

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
                disabled={disabled}
            />
            <button
                type="button"
                className="file-uploader-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled}
                title="Прикрепить файл"
            >
                <Paperclip size={18} />
            </button>
        </div>
    );
};

export default FileUploader;
