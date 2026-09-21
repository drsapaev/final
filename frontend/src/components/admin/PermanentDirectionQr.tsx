import { useTranslation } from '../../i18n/useTranslation';
/**
 * RQ-18 — permanent direction QR block (admin half of S-15).
 *
 * Rendered inside the AdminSetupDirections checklist card for every
 * QR-visible owning profile (the extension point deliberately left by
 * runtime-PR 3339: «QR появится здесь после RQ-18»).
 *
 * Contract honesty (directive §5/§12/§13):
 *  - `supported === null` (entry-methods read failed / unknown) renders
 *    an honest UNKNOWN state — it NEVER renders as «not provisioned»;
 *  - the public code is recovered after reload via the IDEMPOTENT
 *    provision contract (re-provision returns the SAME code,
 *    created=false) — no GET-public-code endpoint is added;
 *  - `created=false` while `supported=false` means the address EXISTS but
 *    the direction is not bookable right now — the QR is shown WITH an
 *    explicit not-bookable note (never a false «готово»);
 *  - the permanent address is NOT a token: no expiry/TTL phrasing is
 *    ever shown; the permanent/non-token explanation is always present;
 *  - the QR payload is the ABSOLUTE canonical frontend origin
 *    (`window.location.origin` — the deploy-contract browser origin,
 *    precedent `api/runtime.ts getBrowserOrigin`) + `/q/<public_code>`.
 *    No hardcoded deployment domain, no backend API origin;
 *  - the downloadable PNG contains the address only — no short-lived
 *    token, no PII; the filename carries the opaque public code only.
 *
 * Styles live in admin.css (RQ-18 section) — no inline styles (UI ratchet).
 */
import { useCallback, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { Copy, Download, QrCode } from 'lucide-react';
import { Button } from '../ui/macos';
import { provisionPublicAddress, type PublicAddressProvisionResponse } from '../../api/queueDirections';
import { logger } from '../../utils/logger';

interface PermanentDirectionQrProps {
    /** QR-visible owning profile key (provision path parameter). */
    profileKey: string;
    /** Checklist tag — only for stable test ids. */
    tag: string;
    /**
     * (д) honest flag from entry-methods: true = provisioned AND bookable;
     * false = not provisioned OR not bookable right now; null = unknown
     * (read failure) — never collapsed into «not provisioned».
     */
    supported: boolean | null;
}

type BlockState = 'idle' | 'loading' | 'shown' | 'error';

export function absolutePermanentUrl(publicCode: string): string {
    return `${window.location.origin}/q/${publicCode}`;
}

export default function PermanentDirectionQr({ profileKey, tag, supported }: PermanentDirectionQrProps) {
    const { t } = useTranslation();
    const [state, setState] = useState<BlockState>('idle');
    const [provisioned, setProvisioned] = useState<PublicAddressProvisionResponse | null>(null);
    const [createdNow, setCreatedNow] = useState<boolean | null>(null);
    const [copied, setCopied] = useState(false);
    const qrWrapRef = useRef<HTMLDivElement | null>(null);

    const provision = useCallback(async () => {
        try {
            setState('loading');
            const res = await provisionPublicAddress(profileKey);
            setProvisioned(res);
            setCreatedNow(res.created);
            setCopied(false);
            setState('shown');
        } catch (err) {
            logger.warn(`permanent QR provision failed for ${profileKey}`, err);
            setState('error');
        }
    }, [profileKey]);

    const copyLink = useCallback(async () => {
        if (!provisioned) return;
        try {
            await navigator.clipboard.writeText(absolutePermanentUrl(provisioned.public_code));
            setCopied(true);
        } catch (err) {
            logger.warn('clipboard copy failed', err);
        }
    }, [provisioned]);

    const downloadPng = useCallback(() => {
        // Serialize the rendered QRCodeSVG → canvas → PNG. The payload is
        // the permanent address only: no token, no TTL, no PII.
        const svg = qrWrapRef.current?.querySelector('svg');
        if (!svg || !provisioned) return;
        const xml = new XMLSerializer().serializeToString(svg);
        const svgBlob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
        const url = URL.createObjectURL(svgBlob);
        const image = new Image();
        const finishDownload = (href: string, revoke: boolean) => {
            const link = document.createElement('a');
            link.download = `qr-direction-${provisioned.public_code}.png`;
            link.href = href;
            link.click();
            if (revoke) URL.revokeObjectURL(url);
        };
        image.onload = () => {
            try {
                const canvas = document.createElement('canvas');
                const padding = 24;
                canvas.width = image.width + padding * 2;
                canvas.height = image.height + padding * 2;
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    // jsdom / no-2d fallback: download the SVG itself.
                    finishDownload(url, true);
                    return;
                }
                // canvas 2D cannot resolve var(--mac-*) — resolve the token at
                // runtime (ModernQueueManager precedent); plain-word fallback.
                let bg = 'white';
                try {
                    bg = getComputedStyle(document.documentElement)
                        .getPropertyValue('--mac-bg-primary')
                        .trim() || 'white';
                } catch {
                    bg = 'white';
                }
                ctx.fillStyle = bg;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(image, padding, padding);
                finishDownload(canvas.toDataURL('image/png'), true);
            } catch {
                finishDownload(url, true);
            }
        };
        image.onerror = () => finishDownload(url, true);
        image.src = url;
    }, [provisioned]);

    const url = provisioned ? absolutePermanentUrl(provisioned.public_code) : '';

    return (
        <div
            className="admin-sdx-qr-block"
            data-testid={`setup-qr-block-${tag}`}
        >
            <div className="admin-sdx-qr-head">
                <QrCode className="admin-sdx-qr-icon" size={14} />
                <span className="admin-sdx-qr-title">{t('admin2.qrdx_block_title')}</span>
            </div>

            {supported === null && (
                <div className="admin-sdx-qr-unknown" data-testid={`setup-qr-unknown-${tag}`}>
                    {t('admin2.qrdx_unknown')}
                </div>
            )}

            {supported !== null && state !== 'shown' && state !== 'error' && (
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                        void provision();
                    }}
                    disabled={state === 'loading'}
                    data-testid={
                        supported
                            ? `setup-qr-show-${tag}`
                            : `setup-qr-provision-${tag}`
                    }
                >
                    {supported ? t('admin2.qrdx_show') : t('admin2.qrdx_create')}
                </Button>
            )}

            {state === 'error' && (
                <div>
                    <div className="admin-sdx-qr-error" data-testid={`setup-qr-error-${tag}`}>
                        {t('admin2.qrdx_failed')}
                    </div>
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                            void provision();
                        }}
                        data-testid={`setup-qr-retry-${tag}`}
                    >
                        {t('admin2.qrdx_show')}
                    </Button>
                </div>
            )}

            {state === 'shown' && provisioned && (
                <div className="admin-sdx-qr-body">
                    <div className="admin-sdx-qr-canvas" ref={qrWrapRef} data-testid={`setup-qr-image-${tag}`}>
                        <QRCodeSVG value={url} size={148} role="img" aria-label={t('admin2.qrdx_sr_qr', { url })} />
                    </div>
                    <div className="admin-sdx-qr-url" data-testid={`setup-qr-url-${tag}`}>{url}</div>
                    {supported !== true && (
                        <div className="admin-sdx-qr-note-warn" data-testid={`setup-qr-not-bookable-note-${tag}`}>
                            {t('admin2.qrdx_not_bookable_note')}
                        </div>
                    )}
                    <div className="admin-sdx-qr-actions">
                        <Button variant="secondary" size="sm" onClick={downloadPng} data-testid={`setup-qr-download-${tag}`}>
                            <Download className="admin-sdx-icon-l" size={12} /> {t('admin2.qrdx_download')}
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => { void copyLink(); }} data-testid={`setup-qr-copy-${tag}`}>
                            <Copy className="admin-sdx-icon-l" size={12} />{' '}
                            {copied ? t('admin2.qrdx_copied') : t('admin2.qrdx_copy')}
                        </Button>
                    </div>
                </div>
            )}

            <p className="admin-sdx-qr-permanent-note" data-testid={`setup-qr-permanent-note-${tag}`}>
                {t('admin2.qrdx_permanent_note')}
            </p>
        </div>
    );
}
