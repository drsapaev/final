
import React, { useState, useEffect } from 'react';
import './LinkPreview.css';

const LinkPreview = ({ url }) => {
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchPreview = async () => {
            try {
                const response = await fetch(`/api/v1/utils/link-preview?url=${encodeURIComponent(url)}`);
                if (response.ok) {
                    const data = await response.json();
                    if (!data.error) {
                        setPreview(data);
                    }
                }
            } catch (e) {
                console.error('Failed to fetch link preview:', e);
            } finally {
                setLoading(false);
            }
        };

        fetchPreview();
    }, [url]);

    if (loading) return null;
    if (!preview) return <a href={url} target="_blank" rel="noopener noreferrer">{url}</a>;

    return (
        <a href={url} target="_blank" rel="noopener noreferrer" className="link-preview-card">
            {preview.image && (
                <div className="link-preview-image">
                    <img src={preview.image} alt={preview.title} />
                </div>
            )}
            <div className="link-preview-content">
                <div className="link-preview-title">{preview.title || url}</div>
                {preview.description && (
                    <div className="link-preview-description">{preview.description}</div>
                )}
                <div className="link-preview-domain">{new URL(url).hostname}</div>
            </div>
        </a>
    );
};

export default LinkPreview;
