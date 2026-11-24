import { useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/i18n/useTranslation';
import { Button, Textarea } from '../../ui/macos';

interface LocalSpeechResult {
  readonly isFinal: boolean;
  readonly 0: { transcript: string };
}
interface LocalRecognition {
  processLocally: boolean;
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<LocalSpeechResult> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
interface LocalRecognitionConstructor {
  new (): LocalRecognition;
  available?: (options: { langs: string[]; processLocally: true }) => Promise<string>;
  install?: (options: { langs: string[]; processLocally: true }) => Promise<boolean>;
}

type DocumentPolicy = { allowsFeature?: (feature: string) => boolean };

function microphoneBlocked(): boolean {
  if (typeof document === 'undefined') return false;
  const { permissionsPolicy, featurePolicy } = document as Document & {
    permissionsPolicy?: DocumentPolicy;
    featurePolicy?: DocumentPolicy;
  };
  return (permissionsPolicy?.allowsFeature?.('microphone') ?? featurePolicy?.allowsFeature?.('microphone')) === false;
}

function localRecognition(): LocalRecognitionConstructor | undefined {
  const browser = window as Window & {
    SpeechRecognition?: LocalRecognitionConstructor;
    webkitSpeechRecognition?: LocalRecognitionConstructor;
  };
  const candidate = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
  return candidate?.available && 'processLocally' in candidate.prototype ? candidate : undefined;
}

function abortRecognition(recognition: LocalRecognition | null) {
  try {
    recognition?.abort();
  } catch {
    // A failing browser engine must leave the manual editor usable.
  }
}

function DictationControls({
  lang, disabled, draft, onDraftChange, onInsert,
}: {
  lang: string;
  disabled: boolean;
  draft: string;
  onDraftChange: (text: string) => void;
  onInsert: (text: string) => void;
}) {
  const { t } = useTranslation();
  const [available, setAvailable] = useState<boolean>();
  const [canInstall, setCanInstall] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [phase, setPhase] = useState<'idle' | 'recording' | 'stopping' | 'error'>('idle');
  const active = useRef<LocalRecognition | null>(null);

  useEffect(() => {
    const recognizer = localRecognition();
    const availability = recognizer?.available;
    if (!availability || !lang || disabled) {
      setAvailable(false);
      return;
    }
    let current = true;
    void availability.call(recognizer, { langs: [lang], processLocally: true }).then(
      result => {
        if (!current) return;
        setAvailable(result === 'available');
        setCanInstall(result === 'downloadable' && typeof recognizer?.install === 'function');
      },
      () => { if (current) setAvailable(false); },
    );
    return () => {
      current = false;
      const recognition = active.current;
      active.current = null;
      abortRecognition(recognition);
    };
  }, [disabled, lang]);

  async function install() {
    const recognizer = localRecognition();
    if (!canInstall || installing || !recognizer?.install) return;
    setInstalling(true);
    setPhase('idle');
    try {
      const installed = await recognizer.install({ langs: [lang], processLocally: true });
      setAvailable(installed);
      if (installed) setCanInstall(false);
      else setPhase('error');
    } catch {
      setPhase('error');
    } finally {
      setInstalling(false);
    }
  }

  function failRecording() {
    const recognition = active.current;
    active.current = null;
    setPhase('error');
    abortRecognition(recognition);
  }

  function start() {
    if (!available || active.current || disabled) return;
    const Constructor = localRecognition();
    if (!Constructor) return;
    try {
      const recognition = new Constructor();
      recognition.processLocally = true;
      if (recognition.processLocally !== true) {
        setAvailable(false);
        return;
      }
      active.current = recognition;
      recognition.lang = lang;
      recognition.continuous = true;
      recognition.interimResults = false;
      const previous = draft;
      recognition.onresult = event => {
        if (active.current !== recognition) return;
        const spoken = Array.from(event.results)
          .filter(result => result.isFinal)
          .map(result => result[0].transcript.trim())
          .filter(Boolean).join(' ');
        onDraftChange([previous, spoken].filter(Boolean).join(' '));
      };
      recognition.onend = () => {
        if (active.current !== recognition) return;
        active.current = null;
        setPhase('idle');
      };
      recognition.onerror = () => {
        if (active.current === recognition) failRecording();
      };
      setPhase('recording');
      recognition.start();
    } catch {
      failRecording();
    }
  }

  function stop() {
    if (!active.current) return;
    setPhase('stopping');
    try {
      active.current.stop();
    } catch {
      failRecording();
    }
  }

  const recording = phase === 'recording' || phase === 'stopping';
  return (
    <div className="emr-workspace-follow-up">
      {available === undefined && <p role="status">{t('emr_workspace.loading')}</p>}
      {available === false && !canInstall && <p role="status">{t('emr_workspace.dictation_unavailable')}</p>}
      {canInstall && <Button type="button" size="small" variant="outline" disabled={installing}
        onClick={() => void install()}>{t(installing ? 'emr_workspace.loading' : 'emr_workspace.dictation_install')}</Button>}
      {available && <div className="emr-workspace-controls">
        <Button type="button" size="small" variant="outline" onClick={recording ? stop : start}
          disabled={phase === 'stopping' || disabled}>
          {t(recording ? 'emr_workspace.dictation_stop' : 'emr_workspace.dictation_start')}
        </Button>
        {recording && <span role="status">{t('emr_workspace.dictation_recording')}</span>}
      </div>}
      {phase === 'error' && <p role="alert">{t('emr_workspace.dictation_error')}</p>}
      {draft && <>
        <label className="emr-workspace-field">{t('emr_workspace.dictation_review')}
          <Textarea aria-label={t('emr_workspace.dictation_review')} value={draft} rows={3} maxLength={5000}
            readOnly={recording || disabled} onChange={event => onDraftChange(event.target.value)} />
        </label>
        <div className="emr-workspace-controls">
          <Button type="button" size="small" disabled={recording || !draft.trim() || disabled}
            onClick={() => { onInsert(draft.trim()); onDraftChange(''); }}>
            {t('emr_workspace.dictation_insert')}
          </Button>
          <Button type="button" size="small" variant="ghost" disabled={recording}
            onClick={() => onDraftChange('')}>{t('misc.cancel')}</Button>
        </div>
      </>}
    </div>
  );
}

export function FieldDictation({ disabled, onInsert }: { disabled: boolean; onInsert: (text: string) => void }) {
  const { t, language } = useTranslation();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  if (disabled || import.meta.env.VITE_EMR_DICTATION_DISABLED === 'true') return null;
  const lang = language.startsWith('uz') ? 'uz-UZ' : language.startsWith('ru') ? 'ru-RU' : '';
  return (
    <details className="emr-workspace-visit-section" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary>{t('emr_workspace.dictation')}</summary>
      {open && (microphoneBlocked()
        ? <p role="status">{t('emr_workspace.dictation_microphone_blocked')}</p>
        : <DictationControls key={lang} lang={lang} disabled={disabled} draft={draft}
            onDraftChange={setDraft} onInsert={onInsert} />)}
    </details>
  );
}
