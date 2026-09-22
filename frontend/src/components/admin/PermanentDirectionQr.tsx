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
import {
    fetchDirectionEntryMethods,
    provisionPublicAddress,
    type PublicAddressProvisionResponse,
} from '../../api/queueDirections';
import { readPermanentAddressSupported } from './setupDirectionsReadiness';
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
    /**
     * RQ-18 follow-up (P2-3): the block re-reads entry-methods after a
     * successful provision and reports the fresh flag so the parent
     * checklist row stays truthful (a freshly provisioned healthy
     * direction must not keep claiming «запись недоступна», and a
     * direction deactivated mid-provision must not keep claiming ready).
     */
    onSupportedChange?: (
        profileKey: string,
        supported: boolean | null,
        generation?: number,
    ) => void;
    /**
     * RQ-18 follow-up round-4 (P2-2): the parent's full-read generation.
     * Every full read bumps it; a recheck answer is tagged with the
     * generation it was issued in and is dropped by the parent when a
     * NEWER full read already landed (the late-stale-overwrite race).
     */
    supportGeneration?: number;
}

type BlockState = 'idle' | 'loading' | 'shown' | 'error';

export function absolutePermanentUrl(publicCode: string): string {
    return `${window.location.origin}/q/${publicCode}`;
}

export default function PermanentDirectionQr({ profileKey, tag, supported, onSupportedChange, supportGeneration }: PermanentDirectionQrProps) {
    const { t } = useTranslation();
    const [state, setState] = useState<BlockState>('idle');
    const [provisioned, setProvisioned] = useState<PublicAddressProvisionResponse | null>(null);
    // RQ-18 follow-up round-5 (P2-2): the in-block post-provision override
    // CARRIES THE GENERATION it was issued in. The round-4 guard protected
    // only the parent checklist row — the child's own local state could
    // still be painted by a LATE provision response (an unconditional
    // `null` after the await) and then never cleaned up by the stale
    // recheck's early return, leaving the block stuck on «статус
    // неизвестен» until the next Refresh. A generation-tagged override is
    // simply IGNORED when a newer full read has landed: no lingering
    // unknown, the fresh parent flag owns the block again.
    const [postProvisionOverride, setPostProvisionOverride] = useState<{
        generation: number;
        value: boolean | null;
    } | null>(null);
    const [copied, setCopied] = useState(false);
    const qrWrapRef = useRef<HTMLDivElement | null>(null);
    // RQ-18 follow-up round-4 (P2-2): latest-generation ref — the provision
    // callback's closure would otherwise capture a STALE generation when
    // the parent refreshed between renders (the prop is frozen at the
    // render the callback was created in).
    const supportGenerationRef = useRef(supportGeneration ?? 0);
    supportGenerationRef.current = supportGeneration ?? supportGenerationRef.current;

    // The parent flag was read BEFORE the provision — a recheck answer from
    // the CURRENT generation wins; an override from an older generation is
    // stale and silently ignored.
    const overrideApplies =
        postProvisionOverride !== null &&
        postProvisionOverride.generation === supportGenerationRef.current;
    const effectiveSupported = overrideApplies
        ? postProvisionOverride.value
        : supported;

    const provision = useCallback(async () => {
        try {
            setState('loading');
            // Round-4 (P2-2): the generation this recheck belongs to —
            // captured BEFORE the request so a Refresh that lands while it
            // is in flight makes this answer stale for both the parent
            // override and the local block state.
            const recheckGeneration = supportGenerationRef.current;
            const res = await provisionPublicAddress(profileKey);
            setProvisioned(res);
            setCopied(false);
            setState('shown');
            // RQ-18 follow-up (P2-3): the `supported` prop is stale by
            // construction after a provision (it was read before).
            // RQ-18 follow-up round-2 (P2): the post-provision status is
            // ATOMIC — until the re-read answers, the state is UNKNOWN
            // (both here and in the parent checklist row).
            // RQ-18 follow-up round-5 (P2-2): the unknown is generation-
            // tagged — if a newer full read already landed while the
            // provision was in flight, this override is inert locally
            // (the tagged comparison) exactly as it is dropped by the
            // generation-guarded parent.
            setPostProvisionOverride({ generation: recheckGeneration, value: null });
            onSupportedChange?.(profileKey, null, recheckGeneration);
            try {
                const methods = await fetchDirectionEntryMethods(profileKey);
                if (supportGenerationRef.current > recheckGeneration) {
                    // A newer full read already landed — this recheck is
                    // stale for the fresh generation; drop it entirely.
                    // The tagged local override is already inert.
                    return;
                }
                const fresh = readPermanentAddressSupported(methods);
                setPostProvisionOverride({ generation: recheckGeneration, value: fresh });
                onSupportedChange?.(profileKey, fresh, recheckGeneration);
            } catch (err) {
                logger.warn(`entry-methods re-read failed for ${profileKey}`, err);
                if (supportGenerationRef.current > recheckGeneration) {
                    return;
                }
                // stays unknown — honest, never a confident claim
                setPostProvisionOverride({ generation: recheckGeneration, value: null });
            }
        } catch (err) {
            logger.warn(`permanent QR provision failed for ${profileKey}`, err);
            setState('error');
        }
    }, [profileKey, onSupportedChange]);

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

            {effectiveSupported === null && (
                <div className="admin-sdx-qr-unknown" data-testid={`setup-qr-unknown-${tag}`}>
                    {t('admin2.qrdx_unknown')}
                </div>
            )}

            {effectiveSupported !== null && state !== 'shown' && state !== 'error' && (
                <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                        void provision();
                    }}
                    disabled={state === 'loading'}
                    data-testid={
                        effectiveSupported
                            ? `setup-qr-show-${tag}`
                            : `setup-qr-provision-${tag}`
                    }
                >
                    {effectiveSupported ? t('admin2.qrdx_show') : t('admin2.qrdx_create')}
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
                    {/* honest states: note ONLY for a definitive false — an
                        unknown status (null) renders the unknown banner
                        above, never a confident «недоступно» claim. */}
                    {effectiveSupported === false && (
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
