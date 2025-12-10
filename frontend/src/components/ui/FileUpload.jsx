import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import heic2any from 'heic2any';
import { Upload, X, File as FileIcon, Image as ImageIcon, AlertCircle, Loader } from 'lucide-react';

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
    const [converting, setConverting] = useState(false);
    const [error, setError] = useState(null);
    const [previews, setPreviews] = useState([]);

    // Convert HEIC to JPEG
    const convertHEICtoJPEG = async (file) => {
        try {
            const blob = await heic2any({
                blob: file,
                toType: 'image/jpeg',
                quality: 0.9,
            });

            // Handle generic blob or array of blobs
            const resultBlob = Array.isArray(blob) ? blob[0] : blob;

            const convertedFile = new File(
                [resultBlob],
                file.name.replace(/\.heic$/i, '.jpg').replace(/\.heif$/i, '.jpg'),
                { type: 'image/jpeg' }
            );

            return convertedFile;
        } catch (err) {
            console.error('HEIC conversion error:', err);
            throw new Error('Failed to convert HEIC image');
        }
    };

    const handleDrop = useCallback(async (acceptedFiles, rejectedFiles) => {
        setError(null);
        setConverting(true);

        if (rejectedFiles && rejectedFiles.length > 0) {
            if (rejectedFiles[0].size > maxSize) {
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
                if (
                    file.type === 'image/heic' ||
                    file.type === 'image/heif' ||
                    file.name.toLowerCase().endsWith('.heic') ||
                    file.name.toLowerCase().endsWith('.heif')
                ) {
                    try {
                        fileToProcess = await convertHEICtoJPEG(file);
                    } catch (e) {
                        console.warn(`Could not convert ${file.name}, using original`);
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
                setPreviews(prev => [...prev, ...newPreviews]);
            } else {
                // Clean up new previews immediately if we are clearing
                newPreviews.forEach(p => {
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

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop: handleDrop,
        maxSize,
        accept,
        multiple,
        disabled: disabled || converting
    });

    const removeFile = (id) => {
        setPreviews(prev => {
            const newPreviews = prev.filter(p => p.id !== id);
            // Revoke URL to avoid memory leaks
            const removed = prev.find(p => p.id === id);
            if (removed && removed.url) URL.revokeObjectURL(removed.url);

            return newPreviews;
        });
    };

    // Cleanup URLs on unmount
    React.useEffect(() => {
        return () => {
            previews.forEach(p => {
                if (p.url) URL.revokeObjectURL(p.url);
            });
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const containerStyle = {
        padding: '24px',
        border: `2px dashed ${isDragActive ? 'var(--mac-accent-blue, #007AFF)' : 'var(--mac-border, #E5E5E5)'}`,
        borderRadius: '8px',
        backgroundColor: isDragActive ? 'var(--mac-bg-secondary, #F5F5F7)' : 'var(--mac-bg-primary, #FFFFFF)',
        cursor: disabled ? 'default' : 'pointer',
        textAlign: 'center',
        transition: 'all 0.2s ease',
        opacity: disabled ? 0.6 : 1,
        ...style
    };

    return (
        <div className={className}>
            <div {...getRootProps()} style={containerStyle}>
                <input {...getInputProps()} />

                {converting ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                        <Loader className="animate-spin text-blue-500" size={32} />
                        <p style={{ color: 'var(--mac-text-secondary, #8E8E93)', margin: 0 }}>
                            Processing files...
                        </p>
                    </div>
                ) : (
                    <>
                        <Upload
                            size={32}
                            style={{
                                color: isDragActive ? 'var(--mac-accent-blue, #007AFF)' : 'var(--mac-text-tertiary, #C7C7CC)',
                                marginBottom: '12px'
                            }}
                        />
                        <p style={{ margin: '0 0 4px', color: 'var(--mac-text-primary, #1D1D1F)', fontWeight: 500 }}>
                            {isDragActive ? 'Drop files here' : 'Click or drag files to upload'}
                        </p>
                        <p style={{ margin: 0, fontSize: '12px', color: 'var(--mac-text-secondary, #8E8E93)' }}>
                            Supports JPG, PNG, HEIC up to {maxSize / 1024 / 1024}MB
                        </p>
                    </>
                )}
            </div>

            {error && (
                <div style={{
                    marginTop: '12px',
                    padding: '12px',
                    backgroundColor: '#FFF2F2',
                    color: '#D32F2F',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '14px'
                }}>
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {showPreviews && previews.length > 0 && (
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(100px, 1fr))',
                    gap: '12px',
                    marginTop: '16px'
                }}>
                    {previews.map((preview) => (
                        <div key={preview.id} style={{ position: 'relative', group: 'preview-item' }}>
                            <div style={{
                                width: '100%',
                                paddingTop: '100%',
                                position: 'relative',
                                borderRadius: '8px',
                                overflow: 'hidden',
                                backgroundColor: '#F5F5F7',
                                border: '1px solid var(--mac-border, #E5E5E5)'
                            }}>
                                {preview.url ? (
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
                                        }}
                                    />
                                ) : (
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
                                        padding: '8px'
                                    }}>
                                        <FileIcon size={24} color="#8E8E93" />
                                    </div>
                                )}
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
                                    backgroundColor: '#8E8E93',
                                    color: 'white',
                                    border: 'none',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    cursor: 'pointer',
                                    padding: 0
                                }}
                                title="Remove"
                            >
                                <X size={12} />
                            </button>

                            <p style={{
                                fontSize: '11px',
                                color: 'var(--mac-text-secondary, #8E8E93)',
                                marginTop: '4px',
                                textAlign: 'center',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                            }}>
                                {preview.originalName}
                            </p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
};

export default FileUpload;
