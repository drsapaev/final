// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, X, File as FileIcon, AlertCircle, Loader } from 'lucide-react';
import logger from '../../utils/logger';
import { convertHEICToJPEG, isHEICFile } from '../../utils/heicConverter';
import '../../styles/animations.css';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';

const FileUpload = ({
  onFilesSelected,
  maxSize = 10 * 1024 * 1024, // 10MB
  accept = {
    'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp'],
    'image/heic': ['.heic'],
    'image/heif': ['.heif']
  },
  multiple = true,
  disabled = false,
  showPreviews = true,
  clearOnSelect = false,
  className,
  style
}) => {
  const [converting, setConverting] = useState<boolean>(false);
  const [error, setError] = useState<unknown>(null);
  const [previews, setPreviews] = useState<unknown[]>([]);

  const handleDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
    setError(null);
    setConverting(true);

    if (rejectedFiles && rejectedFiles.length > 0) {
      const rejectedFile = rejectedFiles[0].file || rejectedFiles[0];
      if (rejectedFile.size > maxSize) {
        setError(`File size too large (max ${maxSize / 1024 / 1024}MB)`);
      } else {
        setError('File type not supported or invalid');
      }
      setConverting(false);
      return;
    }

    try {
      const processedFiles = [];
      const newPreviews = [];

      for (const file of acceptedFiles) {
        let fileToProcess = file;

        // Check if HEIC/HEIF
        if (isHEICFile(file)) {
          try {
            fileToProcess = await convertHEICToJPEG(file, 0.9);
          } catch {
            logger.warn(`Could not convert ${file.name}, using original`);
          }
        }

        processedFiles.push(fileToProcess);

        // Generate preview for images
        if (fileToProcess.type.startsWith('image/')) {
          const previewUrl = URL.createObjectURL(fileToProcess);
          newPreviews.push({
            id: Math.random().toString(36).substr(2, 9),
            file: fileToProcess,
            url: previewUrl,
            originalName: file.name
          });
        } else {
          newPreviews.push({
            id: Math.random().toString(36).substr(2, 9),
            file: fileToProcess,
            url: null,
            originalName: file.name
          });
        }
      }

      if (!clearOnSelect) {
        setPreviews((prev) => [...prev, ...newPreviews]);
      } else {
        // Clean up new previews immediately if we are clearing
        newPreviews.forEach((p) => {
          if (p.url) URL.revokeObjectURL(p.url);
        });
      }

      if (onFilesSelected) {
        onFilesSelected(processedFiles);
      }
    } catch (err) {
      setError(err.message || 'Error processing files');
    } finally {
      setConverting(false);
    }
  }, [maxSize, onFilesSelected, clearOnSelect]);

  const { getRootProps, getInputProps, isDragActive, isFocused } = useDropzone({
    onDrop: handleDrop,
    maxSize,
    accept,
    multiple,
    disabled: disabled || converting
  });

  const removeFile = (id) => {
    setPreviews((prev) => {
      const newPreviews = prev.filter((p) => p.id !== id);
      // Revoke URL to avoid memory leaks
      const removed = prev.find((p) => p.id === id);
      if (removed && removed.url) URL.revokeObjectURL(removed.url);

      return newPreviews;
    });
  };

  // Cleanup URLs on unmount
  React.useEffect(() => {
    return () => {
      previews.forEach((p) => {
        if (p.url) URL.revokeObjectURL(p.url);
      });
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const containerStyle = {
    padding: 'var(--mac-spacing-6)',
    border: `2px dashed ${
      isDragActive || isFocused
        ? 'var(--mac-accent-blue, #007AFF)'
        : 'var(--mac-border, #E5E5E5)'
    }`,
    borderRadius: 'var(--mac-radius-md)',
    backgroundColor: isDragActive ? 'var(--mac-bg-secondary, #F5F5F7)' : 'var(--mac-bg-primary, #FFFFFF)',
    cursor: disabled ? 'default' : 'pointer',
    textAlign: 'center',
    transition: 'all 0.2s ease',
    opacity: disabled ? 0.6 : 1,
    outline: 'none',
    ...style
  };

  return (
    <div className={className}>
            <div {...getRootProps()} style={containerStyle} aria-label="File upload dropzone">
                <Input
                  {...getInputProps()}
                  aria-describedby={error ? 'file-upload-error' : undefined}
                />

                {converting ?
        <div
          role="status"
          aria-live="polite"
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
        >
                        <Loader className="animate-spin" size={32} style={{ color: 'var(--mac-accent-blue, #007AFF)' }} />
                        <p style={{ color: 'var(--mac-text-secondary, #8E8E93)', margin: 0 }}>
                            Processing files...
                        </p>
                    </div> :

        <>
                        <Upload
            size={32}
            style={{
              color: isDragActive ? 'var(--mac-accent-blue, #007AFF)' : 'var(--mac-text-tertiary, #C7C7CC)',
              marginBottom: 'var(--mac-spacing-3)'
            }} />

                        <p style={{ margin: '0 0 4px', color: 'var(--mac-text-primary, #1D1D1F)', fontWeight: 'var(--mac-font-weight-medium)' }}>
                            {isDragActive ? 'Drop files here' : 'Click or drag files to upload'}
                        </p>
                        <p style={{ margin: 0, fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary, #8E8E93)' }}>
                            Supports JPG, PNG, HEIC up to {maxSize / 1024 / 1024}MB
                        </p>
                    </>
        }
            </div>

            {error &&
      <div
        id="file-upload-error"
        role="alert"
        style={{
        marginTop: 'var(--mac-spacing-3)',
        padding: 'var(--mac-spacing-3)',
        backgroundColor: '#FFF2F2',
        color: '#D32F2F',
        borderRadius: 'var(--mac-radius-md)',
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--mac-spacing-2)',
        fontSize: 'var(--mac-font-size-base)'
      }}>
                    <AlertCircle size={16} />
                    {error}
                </div>
      }

            {showPreviews && previews.length > 0 &&
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
        gap: 'var(--mac-spacing-3)',
        marginTop: 'var(--mac-spacing-4)'
      }}>
                    {previews.map((preview) =>
        <div key={preview.id} style={{ position: 'relative', group: 'preview-item' }}>
                            <div style={{
            width: '100%',
            paddingTop: '100%',
            position: 'relative',
            borderRadius: 'var(--mac-radius-md)',
            overflow: 'hidden',
            backgroundColor: 'var(--mac-bg-secondary)',
            border: '1px solid var(--mac-border, #E5E5E5)'
          }}>
                                {preview.url ?
            <img
              src={preview.url}
              alt={preview.originalName}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                objectFit: 'cover'
              }} /> :


            <div style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: 'var(--mac-spacing-2)'
            }}>
                                        <FileIcon size={24} color="var(--mac-text-tertiary)" />
                                    </div>
            }
                            </div>

                            <button
            onClick={(e) => {
              e.stopPropagation();
              removeFile(preview.id);
            }}
            style={{
              position: 'absolute',
              top: '-6px',
              right: '-6px',
              width: '20px',
              height: '20px',
              borderRadius: '50%',
              backgroundColor: 'var(--mac-text-tertiary)',
              color: 'white',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              padding: 0
            }}
            title="Remove"
            aria-label={`Remove ${preview.originalName}`}>

                                <X size={12} />
                            </button>

                            <p style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-text-secondary, #8E8E93)',
            marginTop: 'var(--mac-spacing-1)',
            textAlign: 'center',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}>
                                {preview.originalName}
                            </p>
                        </div>
        )}
                </div>
      }
        </div>);

};


FileUpload.propTypes = {
  ...(FileUpload.propTypes || {}),
  accept: PropTypes.any,
  className: PropTypes.any,
  clearOnSelect: PropTypes.any,
  disabled: PropTypes.any,
  maxSize: PropTypes.any,
  multiple: PropTypes.any,
  onFilesSelected: PropTypes.any,
  showPreviews: PropTypes.any,
  style: PropTypes.any,
};

export default FileUpload;
