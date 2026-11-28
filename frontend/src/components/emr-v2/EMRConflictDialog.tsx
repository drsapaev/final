import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from '../../i18n/useTranslation';
import Button from '../ui/macos/Button';
import Modal from '../ui/macos/Modal';
import './EMRConflictDialog.css';

const editorShortcuts = new Set(['s', 'ы', 'z', 'я', 'y', 'н', 'enter']);

interface EMRConflictInfo {
    serverVersion?: string | number;
    yourVersion?: string | number;
    lastEditedBy?: number;
    lastEditedAt?: string;
}

interface EMRConflictDialogProps {
    conflict?: EMRConflictInfo | null;
    isSigned?: boolean;
    onReload?: () => Promise<unknown>;
    onCompare?: () => void;
    onAmend?: () => void;
    loading?: boolean;
}

/** A 409 conflict stays open until the doctor chooses how to resolve it. */
export function EMRConflictDialog({
    conflict,
    isSigned = false,
    onReload,
    onCompare,
    onAmend,
    loading = false,
}: EMRConflictDialogProps = {}) {
    const { t, language } = useTranslation();
    const discardHintId = useId();
    const actionsRef = useRef<HTMLDivElement>(null);
    const reloadPending = useRef(false);
    const [reloadState, setReloadState] = useState<'idle' | 'loading' | 'error'>('idle');
    const isOpen = Boolean(conflict);

    useEffect(() => {
        if (!isOpen) return;
        // Focus the first real action because backdrop dismissal is disabled.
        const frame = requestAnimationFrame(() => actionsRef.current?.querySelector('button')?.focus());
        return () => cancelAnimationFrame(frame);
    }, [isOpen]);

    if (!conflict) return null;

    const busy = loading || reloadState === 'loading';
    const lastEdit = new Date(conflict.lastEditedAt ?? '');
    const date = Number.isNaN(lastEdit.getTime()) ? '' : new Intl.DateTimeFormat(language, {
        dateStyle: 'medium', timeStyle: 'short',
    }).format(lastEdit);
    const canAct = () => !loading && !reloadPending.current;

    async function reload() {
        if (!onReload || !canAct()) return;
        reloadPending.current = true;
        setReloadState('loading');
        try {
            const result = await onReload();
            // The hook returns a loaded record on success, or an outcome
            // marker when the read was denied or superseded.
            setReloadState(result && typeof result === 'object' && 'data' in result && result.data ? 'idle' : 'error');
        } catch {
            setReloadState('error');
        } finally {
            reloadPending.current = false;
        }
    }

    return (
        <Modal isOpen title={t('emr_workspace.version_conflict_title')} className="emr-conflict-dialog"
            closeOnBackdrop={false} closeOnEscape={false} onKeyDown={event => {
                // Native undo can still reach the previously edited field behind the dialog.
                if ((event.ctrlKey || event.metaKey) && editorShortcuts.has(event.key.toLowerCase())) {
                    event.preventDefault();
                }
            }}>
            {busy ? <p key="loading" role="status">{t('emr_workspace.loading')}</p>
                : reloadState === 'error' ? <p key="error" role="alert" className="emr-conflict-dialog__error">
                    {t('emr_workspace.version_conflict_reload_error')}
                </p>
                : <p>{t('emr_workspace.version_conflict_description')}</p>}
            <dl className="emr-conflict-dialog__versions">
                <div>
                    <dt>{t('emr_workspace.version_conflict_local')}</dt>
                    <dd>{conflict.yourVersion == null ? '—' : `v${conflict.yourVersion}`}</dd>
                </div>
                <div>
                    <dt>{t('emr_workspace.version_conflict_server')}</dt>
                    <dd>{conflict.serverVersion == null ? '—' : `v${conflict.serverVersion}`}</dd>
                </div>
                {date && <div>
                    <dt>{t('emr_workspace.version_conflict_edited_at')}</dt>
                    <dd>{date}</dd>
                </div>}
                {conflict.lastEditedBy != null && conflict.lastEditedBy > 0 && <div>
                    <dt>{t('emr_workspace.version_conflict_edited_by')}</dt>
                    <dd>№{conflict.lastEditedBy}</dd>
                </div>}
            </dl>
            <div className="emr-conflict-dialog__actions" ref={actionsRef}>
                {onCompare && <Button type="button" variant="primary" aria-disabled={busy}
                    onClick={() => { if (canAct()) onCompare(); }}>
                    {t('emr_workspace.version_conflict_compare')}
                </Button>}
                {onReload && <>
                    <Button type="button" variant="secondary" aria-disabled={busy} aria-describedby={discardHintId}
                        onClick={() => void reload()}>
                        {t('emr_workspace.version_conflict_reload')}
                    </Button>
                    <p id={discardHintId} className="emr-conflict-dialog__hint">
                        {t('emr_workspace.version_conflict_discard')}
                    </p>
                </>}
                {isSigned && onAmend && <Button type="button" variant="secondary" aria-disabled={busy}
                    onClick={() => { if (canAct()) onAmend(); }}>
                    {t('misc.emr_amend')}
                </Button>}
            </div>
        </Modal>
    );
}

export default EMRConflictDialog;
