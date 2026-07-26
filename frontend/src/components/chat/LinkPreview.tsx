
import { useState, useEffect } from 'react';
import './LinkPreview.css';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
import { api } from '../../api/client';

const LinkPreview = ({ url }) => {
  const { t } = useTranslation();
    const [preview, setPreview] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // audit/phase-6, BS-64: previously this used raw fetch() with no
        // AbortController, no auth header, no CSRF, no rate-limit handling,
        // and no error normalization. On chat history scroll, the component
        // re-mounted and re-fetched for every URL in every visible message.
        // Switching to api.get() routes through the centralized axios client
        // which handles all of the above. We also wire an AbortController so
        // unmount during the in-flight request cancels it cleanly.
        const abortController = new AbortController();

        const fetchPreview = async () => {
            try {
                const response = await api.get(`/utils/link-preview`, {
                    params: { url },
                    signal: abortController.signal,
                });
                const data = response.data;
                if (data && !data.error) {
                    setPreview(data);
                }
            } catch (e) {
                // axios.isCancel from api/client throws CanceledError on abort;
                // silently ignore aborts (component unmounted).
                const errName = (e && (e.name || e.code)) || '';
                if (errName === 'CanceledError' || errName === 'AbortError' || errName === 'ERR_CANCELED') {
                    return;
                }
                logger.error('[LinkPreview] Не удалось получить preview ссылки', {
                    url,
                    error: e?.message || String(e),
                });
            } finally {
                // Only update state if not aborted.
                if (!abortController.signal.aborted) {
                    setLoading(false);
                }
            }
        };

        fetchPreview();

        return () => {
            abortController.abort();
        };
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


// audit/strict: removed self-referencing propTypes spread
LinkPreview.propTypes = {
  url: PropTypes.any,
};

export default LinkPreview;
