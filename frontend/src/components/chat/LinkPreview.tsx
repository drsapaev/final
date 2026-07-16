// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).


import { useState, useEffect } from 'react';
import './LinkPreview.css';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const LinkPreview = ({ url }) => {
  const { t } = useTranslation();
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
                logger.error('[LinkPreview] Не удалось получить preview ссылки', {
                    url,
                    error: e?.message || String(e),
                });
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


LinkPreview.propTypes = {
  ...(LinkPreview.propTypes || {}),
  url: PropTypes.any,
};

export default LinkPreview;
