import { useCallback, useEffect, useState } from 'react';
import type { AxiosResponse } from 'axios';
import { Activity, CheckCircle2, PlugZap, RefreshCw, Save, X } from 'lucide-react';

import { api } from '../../api/client';
import { Alert, Badge, Button, Card, Checkbox, Input, Select, Textarea } from '../ui/macos';

type TranslationFn = (key: string, options?: Record<string, unknown>) => string;
type DeviceRole = 'analyzer' | 'printer' | 'label_printer' | 'scanner' | 'local_agent';

interface ProfileVersion {
  id: number;
  version_no: number;
  status: 'DRAFT' | 'ACTIVE' | 'RETIRED';
  adapter_key: string;
  protocol_code: string;
  transport_code: string;
  mapping_profile: Record<string, unknown>;
  transport_settings: Record<string, unknown>;
  device_settings: Record<string, unknown>;
  simulator_validation_status: 'NOT_RUN' | 'PASS' | 'FAIL';
  simulator_evidence_ref: string | null;
  physical_validation_status: 'NOT_RUN' | 'PASS' | 'FAIL';
  physical_evidence_ref: string | null;
  clinical_approved_by_user_id?: number | null;
  clinical_approved_at?: string | null;
  clinical_approval_configuration_version_id?: number | null;
}

interface IntegrationProfile {
  id: number;
  equipment_id: number;
  device_role: DeviceRole;
  versions: ProfileVersion[];
}

interface Props {
  equipmentId: number | string;
  equipmentName: string;
  t: TranslationFn;
  onClose: () => void;
}

const roleValues: DeviceRole[] = ['analyzer', 'printer', 'label_printer', 'scanner', 'local_agent'];
const transportValues = ['tcp_ip', 'rs232', 'local_agent', 'file_drop', 'manual'];
const protocolValuesFor = (role: DeviceRole) => role === 'analyzer'
  ? ['astm_clsi', 'hl7_v2', 'custom']
  : ['file', 'manual', 'custom'];
const defaultProtocolFor = (role: DeviceRole) => role === 'analyzer' ? 'hl7_v2' : 'manual';
const defaultTransportFor = (role: DeviceRole) => role === 'analyzer' || role === 'local_agent'
  ? 'local_agent'
  : 'file_drop';
const defaultAdapterFor = (role: DeviceRole) => role === 'analyzer' ? 'hl7_v2' : 'manual';
const defaultDeviceSettingsFor = (role: DeviceRole) => {
  if (role === 'printer') return '{"media_width_mm":80,"media_height_mm":200}';
  if (role === 'label_printer') return '{"label_width_mm":100,"label_height_mm":40,"barcode_symbology":"Code128","default_for_lab_labels":false}';
  if (role === 'scanner') return '{"barcode_symbologies":["Code128"]}';
  return '{}';
};
const probePlaceholderFor = (role: DeviceRole) => `admin2.lab_int_probe_${role}_placeholder`;

const decodeJsonObject = (value: string): Record<string, unknown> => {
  const decoded: unknown = JSON.parse(value);
  if (!decoded || typeof decoded !== 'object' || Array.isArray(decoded)) {
    throw new Error('object_required');
  }
  return decoded as Record<string, unknown>;
};

const LabEquipmentIntegrationPanel = ({ equipmentId, equipmentName, t, onClose }: Props) => {
  const [profile, setProfile] = useState<IntegrationProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null);
  const [deviceRole, setDeviceRole] = useState<DeviceRole>('analyzer');
  const [adapterKey, setAdapterKey] = useState('hl7_v2');
  const [protocolCode, setProtocolCode] = useState('hl7_v2');
  const [transportCode, setTransportCode] = useState('local_agent');
  const [customProtocolCode, setCustomProtocolCode] = useState('');
  const [mappingJson, setMappingJson] = useState('');
  const [transportJson, setTransportJson] = useState('');
  const [deviceJson, setDeviceJson] = useState('{}');
  const [defaultLabelProfile, setDefaultLabelProfile] = useState(false);
  const [syntheticMessage, setSyntheticMessage] = useState('');
  const [physicalStatus, setPhysicalStatus] = useState('');
  const [physicalEvidence, setPhysicalEvidence] = useState('');

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get(
        `/clinic/equipment/${equipmentId}/lab-integration`,
      ) as AxiosResponse<IntegrationProfile | null>;
      setProfile(response.data);
      if (response.data) {
        const role = response.data.device_role;
        const latest = response.data.versions
          .slice()
          .sort((left, right) => right.version_no - left.version_no)[0];
        setDeviceRole(role);
        setAdapterKey(defaultAdapterFor(role));
        setProtocolCode(defaultProtocolFor(role));
        setTransportCode(defaultTransportFor(role));
        setDeviceJson((current) => current === '{}'
          ? latest
            ? JSON.stringify(latest.device_settings, null, 2)
            : defaultDeviceSettingsFor(role)
          : current);
        setDefaultLabelProfile(latest?.device_settings.default_for_lab_labels === true);
      }
    } catch {
      setMessage({ type: 'error', text: t('admin2.lab_int_error') });
    } finally {
      setLoading(false);
    }
  }, [equipmentId, t]);

  useEffect(() => {
    void loadProfile();
  }, [loadProfile]);

  const currentVersion = profile?.versions
    .slice()
    .sort((left, right) => right.version_no - left.version_no)[0] ?? null;

  const run = async (operation: () => Promise<void>) => {
    try {
      setBusy(true);
      setMessage(null);
      await operation();
    } catch {
      setMessage({ type: 'error', text: t('admin2.lab_int_error') });
    } finally {
      setBusy(false);
    }
  };

  const createProfile = () => run(async () => {
    const response = await api.post(
      `/clinic/equipment/${equipmentId}/lab-integration`,
      { device_role: deviceRole },
    ) as AxiosResponse<IntegrationProfile>;
    setProfile(response.data);
    setMessage({ type: 'success', text: t('admin2.lab_int_profile_saved') });
  });

  const createVersion = () => run(async () => {
    const mappingProfile = mappingJson.trim() ? decodeJsonObject(mappingJson) : {};
    const transportSettings = transportJson.trim() ? decodeJsonObject(transportJson) : {};
    const deviceSettings = deviceJson.trim() ? decodeJsonObject(deviceJson) : {};
    if (profile?.device_role === 'label_printer') {
      deviceSettings.default_for_lab_labels = defaultLabelProfile;
    }
    const response = await api.post(
      `/clinic/lab-equipment-integrations/${profile?.id}/versions`,
      {
        adapter_key: adapterKey,
        protocol_code: protocolCode === 'custom' ? customProtocolCode.trim() : protocolCode,
        transport_code: transportCode,
        mapping_profile: mappingProfile,
        transport_settings: transportSettings,
        device_settings: deviceSettings,
      },
    ) as AxiosResponse<ProfileVersion>;
    setMessage({ type: 'success', text: t('admin2.lab_int_version_saved') });
    await loadProfile();
    setSyntheticMessage('');
    setPhysicalStatus('');
    setPhysicalEvidence('');
    void response;
  });

  const runSimulator = () => {
    if (!currentVersion) return;
    void run(async () => {
      await api.post(
        `/clinic/lab-equipment-integration-versions/${currentVersion.id}/simulator-check`,
        { message: syntheticMessage },
      );
      setMessage({ type: 'success', text: t('admin2.lab_int_simulator_saved') });
      await loadProfile();
    });
  };

  const savePhysicalValidation = () => {
    if (!currentVersion) return;
    void run(async () => {
      await api.post(
        `/clinic/lab-equipment-integration-versions/${currentVersion.id}/physical-validation`,
        { status: physicalStatus, evidence_ref: physicalEvidence },
      );
      setMessage({ type: 'success', text: t('admin2.lab_int_physical_saved') });
      await loadProfile();
    });
  };

  const activate = () => {
    if (!currentVersion) return;
    void run(async () => {
      await api.post(`/clinic/lab-equipment-integration-versions/${currentVersion.id}/activate`);
      setMessage({ type: 'success', text: t('admin2.lab_int_activated') });
      await loadProfile();
    });
  };

  const statusText = (state: string) => {
    const key = state === 'PASS' ? 'lab_int_pass' : state === 'FAIL' ? 'lab_int_fail' : 'lab_int_not_run';
    return t(`admin2.${key}`);
  };

  const changeDeviceSettings = (value: string) => {
    setDeviceJson(value);
    if (profile?.device_role === 'label_printer') {
      try {
        setDefaultLabelProfile(
          decodeJsonObject(value).default_for_lab_labels === true,
        );
      } catch {
        // Keep the last explicit checkbox state until the JSON is valid again.
      }
    }
  };

  const changeDefaultLabelProfile = (checked: boolean) => {
    setDefaultLabelProfile(checked);
    setDeviceJson((current) => {
      try {
        const settings = decodeJsonObject(current);
        settings.default_for_lab_labels = checked;
        return JSON.stringify(settings, null, 2);
      } catch {
        return current;
      }
    });
  };

  return (
    <Card className="admin-p-24-ov-hidden" aria-labelledby="lab-integration-title">
      <div className="admin-d-flex-jc-between-ai-center-mb-16">
        <div>
          <h3 id="lab-integration-title" className="admin-fs-lg-fw-semi-primary-m-0">
            {t('admin2.lab_int_panel_title')}
          </h3>
          <p className="admin-secondary-fs-sm-m-0">
            {equipmentName} · {t('admin2.lab_int_panel_description')}
          </p>
        </div>
        <Button type="button" variant="outline" aria-label={t('admin2.lab_int_close')} onClick={onClose}>
          <X aria-hidden="true" className="w-4 h-4" />
        </Button>
      </div>

      {message && (
        <div role="status" aria-live="polite" className="mb-4">
          <Alert type={message.type} title={message.type === 'success' ? t('admin2.em_alert_success') : t('admin2.em_alert_error')} message={message.text} />
        </div>
      )}

      {loading ? (
        <p role="status">{t('admin2.lab_int_loading')}</p>
      ) : profile === null ? (
        <div className="admin-d-flex-fd-column-gap-12">
          <label>
            <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_role')}</span>
            <Select
              aria-label={t('admin2.lab_int_role')}
              value={deviceRole}
              onChange={(value: unknown) => {
                const nextRole = String(value) as DeviceRole;
                setDeviceRole(nextRole);
                setAdapterKey(defaultAdapterFor(nextRole));
                setProtocolCode(defaultProtocolFor(nextRole));
                setTransportCode(defaultTransportFor(nextRole));
                setMappingJson('');
                setTransportJson('');
                setDeviceJson(defaultDeviceSettingsFor(nextRole));
                setDefaultLabelProfile(false);
              }}
              options={roleValues.map((value) => ({ value, label: t(`admin2.lab_int_role_${value}`) }))}
              size="large"
            />
          </label>
          <Button type="button" disabled={busy} onClick={createProfile}>
            <PlugZap aria-hidden="true" className="w-4 h-4" /> {t('admin2.lab_int_register')}
          </Button>
        </div>
      ) : (
        <div className="admin-d-flex-fd-column-gap-16">
          <section aria-label={t('admin2.lab_int_versions')} className="admin-d-flex-fd-column-gap-8">
            <p className="admin-secondary-fs-sm-m-0">
              {t(`admin2.lab_int_role_${profile.device_role}`)} · {t('admin2.lab_int_versions')}
            </p>
            {profile.versions.length === 0 ? (
              <p>{t('admin2.lab_int_no_version')}</p>
            ) : profile.versions.map((version) => (
              <div key={version.id} className="admin-d-flex-jc-between-ai-center-fw-wrap-gap-8">
                <span>{t('admin2.lab_int_version_label', { version: version.version_no })} · {version.adapter_key} · {version.transport_code}</span>
                {profile.device_role === 'label_printer'
                  && version.status === 'ACTIVE'
                  && version.device_settings.default_for_lab_labels === true
                  && <Badge variant="success" text={t('admin2.lab_int_selected_default')} />}
                {profile.device_role === 'analyzer' && (
                  <Badge
                    variant={version.clinical_approved_by_user_id ? 'success' : 'warning'}
                    text={t(version.clinical_approved_by_user_id
                      ? 'admin2.lab_int_clinical_approval_approved'
                      : 'admin2.lab_int_clinical_approval_pending')}
                  />
                )}
                <Badge variant={version.status === 'ACTIVE' ? 'success' : version.status === 'DRAFT' ? 'warning' : 'gray'} text={t(`admin2.lab_int_status_${version.status.toLowerCase()}`)} />
              </div>
            ))}
          </section>

          <section className="admin-d-flex-fd-column-gap-12" aria-label={t('admin2.lab_int_new_version')}>
            <h4 className="admin-fs-md-fw-semi-primary-m-0">{t('admin2.lab_int_new_version')}</h4>
            <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-12">
              <label>
                <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_adapter_key')}</span>
                <Input aria-label={t('admin2.lab_int_adapter_key')} value={adapterKey} onChange={(event) => setAdapterKey(event.target.value)} />
              </label>
              <label>
                <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_protocol')}</span>
                <Select
                  aria-label={t('admin2.lab_int_protocol')}
                  value={protocolCode}
                  onChange={(value: unknown) => {
                    const next = String(value);
                    setProtocolCode(next);
                    if (next === 'hl7_v2' || next === 'astm_clsi') setAdapterKey(next);
                  }}
                  options={protocolValuesFor(profile.device_role).map((value) => ({ value, label: t(`admin2.lab_int_protocol_${value}`) }))}
                  size="large"
                />
              </label>
              {protocolCode === 'custom' && (
                <label>
                  <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_custom_protocol_code')}</span>
                  <Input
                    aria-label={t('admin2.lab_int_custom_protocol_code')}
                    value={customProtocolCode}
                    onChange={(event) => setCustomProtocolCode(event.target.value)}
                    placeholder="vendor_protocol"
                  />
                </label>
              )}
              <label>
                <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_transport')}</span>
                <Select
                  aria-label={t('admin2.lab_int_transport')}
                  value={transportCode}
                  onChange={(value: unknown) => setTransportCode(String(value))}
                  options={transportValues.map((value) => ({ value, label: t(`admin2.lab_int_transport_${value}`) }))}
                  size="large"
                />
              </label>
            </div>
            {profile.device_role === 'analyzer' && <label>
              <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_mapping')}</span>
              <Textarea aria-label={t('admin2.lab_int_mapping')} value={mappingJson} onChange={(event) => setMappingJson(event.target.value)} placeholder={t('admin2.lab_int_mapping_hint')} rows={4} />
            </label>}
            {profile.device_role === 'label_printer' && (
              <Checkbox
                aria-label={t('admin2.lab_int_default_label_profile')}
                label={t('admin2.lab_int_default_label_profile')}
                description={t('admin2.lab_int_default_label_profile_hint')}
                checked={defaultLabelProfile}
                onChange={changeDefaultLabelProfile}
              />
            )}
            <label>
              <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_transport_settings')}</span>
              <Textarea aria-label={t('admin2.lab_int_transport_settings')} value={transportJson} onChange={(event) => setTransportJson(event.target.value)} placeholder={t('admin2.lab_int_transport_hint')} rows={3} />
            </label>
            <label>
              <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_device_settings')}</span>
              <Textarea aria-label={t('admin2.lab_int_device_settings')} value={deviceJson} onChange={(event) => changeDeviceSettings(event.target.value)} rows={3} />
            </label>
            <Button type="button" disabled={busy} onClick={createVersion}>
              {busy ? <RefreshCw aria-hidden="true" className="w-4 h-4" /> : <Save aria-hidden="true" className="w-4 h-4" />}
              {t('admin2.lab_int_create_version')}
            </Button>
          </section>

          {currentVersion?.status === 'DRAFT' && (
            <>
              <section className="admin-d-flex-fd-column-gap-8" aria-label={t('admin2.lab_int_simulator')}>
                <h4 className="admin-fs-md-fw-semi-primary-m-0"><Activity aria-hidden="true" className="inline w-4 h-4" /> {t('admin2.lab_int_simulator')}</h4>
                <p className="admin-secondary-fs-sm-m-0">{t('admin2.lab_int_synthetic_only')}</p>
                <label>
                  <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_synthetic_message')}</span>
                  <Textarea aria-label={t('admin2.lab_int_synthetic_message')} value={syntheticMessage} onChange={(event) => setSyntheticMessage(event.target.value)} placeholder={t(probePlaceholderFor(profile.device_role))} rows={5} />
                </label>
                <p>{t('admin2.lab_int_simulator_status')}: {statusText(currentVersion.simulator_validation_status)}</p>
                <Button type="button" disabled={busy || !syntheticMessage.trim() || (protocolCode === 'custom' && !customProtocolCode.trim())} onClick={runSimulator}>
                  <Activity aria-hidden="true" className="w-4 h-4" /> {t('admin2.lab_int_run_simulator')}
                </Button>
              </section>

              <section className="admin-d-flex-fd-column-gap-8" aria-label={t('admin2.lab_int_physical_validation')}>
                <h4 className="admin-fs-md-fw-semi-primary-m-0">{t('admin2.lab_int_physical_validation')}</h4>
                <label>
                  <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_physical_status')}</span>
                  <Select
                    aria-label={t('admin2.lab_int_physical_status')}
                    value={physicalStatus}
                    onChange={(value: unknown) => setPhysicalStatus(String(value))}
                    options={[
                      { value: '', label: t('admin2.lab_int_select_status') },
                      { value: 'PASS', label: t('admin2.lab_int_pass') },
                      { value: 'FAIL', label: t('admin2.lab_int_fail') },
                    ]}
                    size="large"
                  />
                </label>
                <label>
                  <span className="admin-d-block-fs-sm-fw-med-primary-mb-4">{t('admin2.lab_int_evidence_ref')}</span>
                  <Input aria-label={t('admin2.lab_int_evidence_ref')} value={physicalEvidence} onChange={(event) => setPhysicalEvidence(event.target.value)} placeholder="clinic-evidence://..." />
                </label>
                <p>{t('admin2.lab_int_physical_status')}: {statusText(currentVersion.physical_validation_status)}</p>
                <Button type="button" disabled={busy || !physicalStatus || !physicalEvidence.trim()} onClick={savePhysicalValidation}>
                  {t('admin2.lab_int_save_physical')}
                </Button>
              </section>

              <section className="admin-d-flex-fd-column-gap-8" aria-label={t('admin2.lab_int_activation')}>
                <p>{t('admin2.lab_int_activation_rule')}</p>
                <Button
                  type="button"
                  disabled={busy || currentVersion.simulator_validation_status !== 'PASS' || currentVersion.physical_validation_status !== 'PASS' || !currentVersion.simulator_evidence_ref || !currentVersion.physical_evidence_ref}
                  onClick={activate}
                >
                  <CheckCircle2 aria-hidden="true" className="w-4 h-4" /> {t('admin2.lab_int_activate')}
                </Button>
              </section>
            </>
          )}
          {currentVersion?.status === 'ACTIVE' && (
            <Alert type="success" title={t('admin2.lab_int_status_active')} message={t('admin2.lab_int_active_notice')} />
          )}
          <Button type="button" variant="outline" onClick={() => void loadProfile()} disabled={busy}>
            {t('admin2.lab_int_refresh')}
          </Button>
        </div>
      )}
    </Card>
  );
};

export default LabEquipmentIntegrationPanel;
