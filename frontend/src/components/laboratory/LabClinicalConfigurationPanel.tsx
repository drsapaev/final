import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AxiosResponse } from 'axios';
import { Check, FileText, RefreshCw, Save, Send, SquarePen } from 'lucide-react';

import { api } from '../../api/client';
import { useAppData } from '../../contexts/AppDataContext';
import { useTranslation } from '../../i18n/useTranslation';
import { Alert, Badge, Button, Card, CardContent, CardHeader, Input, Textarea } from '../ui/macos';

interface ClinicalConfigurationVersion {
  id: number;
  version_no: number;
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'ARCHIVED';
  configuration_snapshot: Record<string, unknown>;
  primary_lab_physician_user_id: number | null;
  substitute_lab_physician_user_id: number | null;
  approved_by_user_id: number | null;
  approved_role_code: string | null;
  approval_authority_snapshot: Record<string, unknown> | null;
  approved_at: string | null;
  created_at: string;
}

interface AnalyzerMappingApproval {
  version_id: number;
  profile_id: number;
  version_no: number;
  equipment_id: number;
  equipment_name: string;
  equipment_model: string | null;
  adapter_key: string;
  protocol_code: string;
  mapping_profile: Record<string, unknown>;
  simulator_validation_status: 'NOT_RUN' | 'PASS' | 'FAIL';
  physical_validation_status: 'NOT_RUN' | 'PASS' | 'FAIL';
}

type Feedback = 'saved' | 'submitted' | 'approved' | 'mappingApproved' | 'invalid' | 'error' | null;
type TranslationFn = (key: string, options?: Record<string, unknown>) => string;

const EMPTY_SNAPSHOT = JSON.stringify({
  method_instructions: [],
  reference_intervals: [],
  critical_values: [],
  qc_rules: [],
  not_applicable_reasons: {},
}, null, 2);

function assigneeValue(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : Number.NaN;
}

const LabClinicalConfigurationPanel = ({ onClose }: { onClose: () => void }) => {
  const { t } = useTranslation();
  const { currentUser } = useAppData();
  const actor = currentUser as (typeof currentUser & { is_active?: boolean });
  const isAdmin = actor?.role === 'Admin';
  const isLab = actor?.role === 'Lab' && actor.is_active !== false;
  const [versions, setVersions] = useState<ClinicalConfigurationVersion[]>([]);
  const [analyzerApprovals, setAnalyzerApprovals] = useState<AnalyzerMappingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editingVersionId, setEditingVersionId] = useState<number | null>(null);
  const [primaryId, setPrimaryId] = useState('');
  const [substituteId, setSubstituteId] = useState('');
  const [snapshotText, setSnapshotText] = useState(EMPTY_SNAPSHOT);
  const [feedback, setFeedback] = useState<Feedback>(null);

  const loadVersions = useCallback(async () => {
    try {
      setLoading(true);
      const [configurationResponse, analyzerResponse] = await Promise.all([
        api.get(
          '/clinic/lab-clinical-configurations',
          { headers: { 'Cache-Control': 'no-cache' } },
        ) as Promise<AxiosResponse<ClinicalConfigurationVersion[]>>,
        api.get(
          '/clinic/lab-equipment-integration-approvals',
          { headers: { 'Cache-Control': 'no-cache' } },
        ) as Promise<AxiosResponse<AnalyzerMappingApproval[]>>,
      ]);
      setVersions(Array.isArray(configurationResponse.data) ? configurationResponse.data : []);
      setAnalyzerApprovals(Array.isArray(analyzerResponse.data) ? analyzerResponse.data : []);
    } catch {
      setFeedback('error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

  const orderedVersions = useMemo(
    () => [...versions].sort((left, right) => right.version_no - left.version_no),
    [versions],
  );

  const resetEditor = () => {
    setEditingVersionId(null);
    setPrimaryId('');
    setSubstituteId('');
    setSnapshotText(EMPTY_SNAPSHOT);
    setFeedback(null);
  };

  const editVersion = (version: ClinicalConfigurationVersion) => {
    setEditingVersionId(version.id);
    setPrimaryId(version.primary_lab_physician_user_id?.toString() ?? '');
    setSubstituteId(version.substitute_lab_physician_user_id?.toString() ?? '');
    setSnapshotText(JSON.stringify(version.configuration_snapshot, null, 2));
    setFeedback(null);
  };

  const mutate = async (operation: () => Promise<void>) => {
    try {
      setBusy(true);
      setFeedback(null);
      await operation();
    } catch {
      setFeedback('error');
    } finally {
      setBusy(false);
    }
  };

  const saveDraft = () => mutate(async () => {
    const primary = assigneeValue(primaryId);
    const substitute = assigneeValue(substituteId);
    if (Number.isNaN(primary) || Number.isNaN(substitute)) {
      setFeedback('invalid');
      return;
    }
    let snapshot: unknown;
    try {
      snapshot = JSON.parse(snapshotText);
    } catch {
      setFeedback('invalid');
      return;
    }
    if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) {
      setFeedback('invalid');
      return;
    }
    const body = {
      configuration_snapshot: snapshot,
      primary_lab_physician_user_id: primary,
      substitute_lab_physician_user_id: substitute,
    };
    const response = editingVersionId
      ? await api.put(
        `/clinic/lab-clinical-configurations/${editingVersionId}`,
        body,
      ) as AxiosResponse<ClinicalConfigurationVersion>
      : await api.post(
        '/clinic/lab-clinical-configurations',
        body,
      ) as AxiosResponse<ClinicalConfigurationVersion>;
    setEditingVersionId(response.data.id);
    setFeedback('saved');
    await loadVersions();
  });

  const submitDraft = () => {
    if (editingVersionId == null) return;
    return mutate(async () => {
      await api.post(`/clinic/lab-clinical-configurations/${editingVersionId}/submit`);
      resetEditor();
      setFeedback('submitted');
      await loadVersions();
    });
  };

  const approveVersion = (versionId: number) => mutate(async () => {
    await api.post(`/clinic/lab-clinical-configurations/${versionId}/approve`);
    setFeedback('approved');
    await loadVersions();
  });

  const approveAnalyzerMapping = (versionId: number) => mutate(async () => {
    await api.post(`/clinic/lab-equipment-integration-versions/${versionId}/clinical-approval`);
    setFeedback('mappingApproved');
    await loadVersions();
  });

  const canApprove = (version: ClinicalConfigurationVersion) => Boolean(
    isLab
    && currentUser?.id != null
    && version.status === 'PENDING_APPROVAL'
    && [version.primary_lab_physician_user_id, version.substitute_lab_physician_user_id]
      .some((assignee) => assignee != null && String(assignee) === String(currentUser.id)),
  );

  const feedbackKey = feedback ? `labClinicalConfig.${feedback}` : null;

  return (
    <Card variant="filled" padding="none" aria-labelledby="lab-clinical-config-title">
      <CardHeader className="lab-flex-between-wrap">
        <div>
          <h2 id="lab-clinical-config-title" className="lab-panel-title">
            <FileText size={20} aria-hidden="true" />
            <span>{t('labClinicalConfig.title')}</span>
          </h2>
          <p>{t('labClinicalConfig.description')}</p>
        </div>
        <div className="lab-flex-center-8">
          <Button type="button" variant="outline" size="small" onClick={() => void loadVersions()} disabled={loading || busy}>
            <RefreshCw size={14} aria-hidden="true" />
            {t('labClinicalConfig.refresh')}
          </Button>
          <Button type="button" variant="ghost" size="small" onClick={onClose}>
            {t('labClinicalConfig.close')}
          </Button>
        </div>
      </CardHeader>

      <CardContent>
        <p className="lab-workspace-empty">{t('labClinicalConfig.noPatientData')}</p>
        {feedbackKey && (
          <Alert
            type={feedback === 'error' || feedback === 'invalid' ? 'error' : 'info'}
            role={feedback === 'error' || feedback === 'invalid' ? 'alert' : 'status'}
            description={t(feedbackKey)}
          />
        )}

        <section aria-labelledby="lab-clinical-config-versions">
          <div className="lab-flex-between-wrap">
            <h3 id="lab-clinical-config-versions">{t('labClinicalConfig.versions')}</h3>
            {isAdmin && (
              <Button type="button" size="small" variant="outline" onClick={resetEditor} disabled={busy}>
                <SquarePen size={14} aria-hidden="true" />
                {t('labClinicalConfig.newDraft')}
              </Button>
            )}
          </div>
          {loading ? (
            <p role="status">{t('labClinicalConfig.loading')}</p>
          ) : orderedVersions.length === 0 ? (
            <p>{t('labClinicalConfig.empty')}</p>
          ) : (
            <ul className="lab-list-reset">
              {orderedVersions.map((version) => {
                const assigned = canApprove(version);
                return (
                  <li key={version.id} className="lab-card-secondary">
                    <div className="lab-flex-between-wrap">
                      <h4>{t('labClinicalConfig.version', { version: version.version_no })}</h4>
                      <Badge variant={version.status === 'APPROVED' ? 'success' : version.status === 'PENDING_APPROVAL' ? 'warning' : 'info'}>
                        {t(`labClinicalConfig.status.${version.status.toLowerCase()}`)}
                      </Badge>
                    </div>
                    <p>
                      {t('labClinicalConfig.primary')}: {version.primary_lab_physician_user_id ?? t('labClinicalConfig.unassigned')}
                      {' · '}
                      {t('labClinicalConfig.substitute')}: {version.substitute_lab_physician_user_id ?? t('labClinicalConfig.unassigned')}
                    </p>
                    <p>{t('labClinicalConfig.instructionCount', {
                      count: Array.isArray(version.configuration_snapshot.method_instructions)
                        ? version.configuration_snapshot.method_instructions.length
                        : 0,
                    })}</p>
                    {isAdmin && version.status === 'DRAFT' && (
                      <Button type="button" size="small" variant="outline" onClick={() => editVersion(version)} disabled={busy}>
                        <SquarePen size={14} aria-hidden="true" />
                        {t('labClinicalConfig.editDraft')}
                      </Button>
                    )}
                    {assigned && (
                      <Button type="button" size="small" variant="primary" onClick={() => void approveVersion(version.id)} disabled={busy}>
                        <Check size={14} aria-hidden="true" />
                        {t('labClinicalConfig.approve')}
                      </Button>
                    )}
                    {version.approved_by_user_id != null && (
                      <p>{t('labClinicalConfig.approvedBy', { userId: version.approved_by_user_id })}</p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section aria-labelledby="lab-analyzer-approval-title" className="lab-card-secondary">
          <h3 id="lab-analyzer-approval-title">{t('labClinicalConfig.analyzerApprovals')}</h3>
          <p>{t('labClinicalConfig.analyzerApprovalsDescription')}</p>
          {analyzerApprovals.length === 0 ? (
            <p>{t('labClinicalConfig.analyzerApprovalsEmpty')}</p>
          ) : (
            <ul className="lab-list-reset">
              {analyzerApprovals.map((profile) => (
                <li key={profile.version_id} className="lab-card-secondary">
                  <h4>{t('labClinicalConfig.analyzerProfile', {
                    equipment: profile.equipment_name,
                    model: profile.equipment_model ?? t('labClinicalConfig.unassigned'),
                    version: profile.version_no,
                  })}</h4>
                  <p>{profile.adapter_key} · {profile.protocol_code}</p>
                  <p>{t('labClinicalConfig.simulatorStatus', { status: profile.simulator_validation_status })}</p>
                  <p>{t('labClinicalConfig.physicalStatus', { status: profile.physical_validation_status })}</p>
                  <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                    {JSON.stringify(profile.mapping_profile, null, 2)}
                  </pre>
                  {isLab && currentUser?.id != null && (
                    <Button
                      type="button"
                      size="small"
                      variant="primary"
                      onClick={() => void approveAnalyzerMapping(profile.version_id)}
                      disabled={busy}
                    >
                      <Check size={14} aria-hidden="true" />
                      {t('labClinicalConfig.approveAnalyzerMapping')}
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {isAdmin && (
          <section aria-labelledby="lab-clinical-config-editor">
            <h3 id="lab-clinical-config-editor">
              {editingVersionId == null
                ? t('labClinicalConfig.editorNew')
                : t('labClinicalConfig.editorVersion', { id: editingVersionId })}
            </h3>
            <div className="lab-flex-between-wrap">
              <label>
                {t('labClinicalConfig.primary')}
                <Input type="number" min="1" step="1" value={primaryId} onChange={(event) => setPrimaryId(event.target.value)} />
              </label>
              <label>
                {t('labClinicalConfig.substitute')}
                <Input type="number" min="1" step="1" value={substituteId} onChange={(event) => setSubstituteId(event.target.value)} />
              </label>
            </div>
            <label>
              {t('labClinicalConfig.snapshot')}
              <Textarea
                rows={12}
                value={snapshotText}
                onChange={(event) => setSnapshotText(event.target.value)}
                spellCheck={false}
                aria-describedby="lab-clinical-config-json-help"
              />
            </label>
            <p id="lab-clinical-config-json-help">{t('labClinicalConfig.snapshotHelp')}</p>
            <div className="lab-flex-center-8">
              <Button type="button" variant="primary" onClick={() => void saveDraft()} disabled={busy}>
                <Save size={14} aria-hidden="true" />
                {t('labClinicalConfig.saveDraft')}
              </Button>
              {editingVersionId != null && versions.some((version) => version.id === editingVersionId && version.status === 'DRAFT') && (
                <Button type="button" variant="outline" onClick={() => void submitDraft()} disabled={busy}>
                  <Send size={14} aria-hidden="true" />
                  {t('labClinicalConfig.submit')}
                </Button>
              )}
            </div>
          </section>
        )}
      </CardContent>
    </Card>
  );
};

export default LabClinicalConfigurationPanel;

