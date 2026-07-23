import { useTranslation } from '../../i18n/useTranslation';
import { api } from '../../api/client';
import { useState } from 'react';
import type { CSSProperties } from 'react';
import { Card, Button,
  Input } from '../ui/macos';
import tokenManager from '../../utils/tokenManager';
import {
  Shield,
  Smartphone,
  Mail,
  Phone,

  QrCode,
  Download,
  Copy,
  CheckCircle,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Eye,
  EyeOff } from
'lucide-react';
import PropTypes from 'prop-types';

/**
 * Мастер настройки Two-Factor Authentication
 * Пошаговая настройка всех методов 2FA
 */
const TwoFactorSetupWizard = ({ onComplete, onCancel }: { onComplete?: () => void; onCancel?: () => void }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedMethod, setSelectedMethod] = useState('totp');
  const [setupData, setSetupData] = useState(null);
  const [verificationCode, setVerificationCode] = useState('');
  const [backupCodes, setBackupCodes] = useState([]);
  const [recoveryEmail, setRecoveryEmail] = useState('');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [showSecret, setShowSecret] = useState(false);

  const steps = [
  { id: 1, title: t('final.twofactor_step1_title'), description: t('final.twofactor_step1_desc') },
  { id: 2, title: t('final.twofactor_step2_title'), description: t('final.twofactor_step2_desc') },
  { id: 3, title: t('final.twofactor_step3_title'), description: t('final.twofactor_step3_desc') },
  { id: 4, title: t('final.twofactor_step4_title'), description: t('final.twofactor_step4_desc') },
  { id: 5, title: t('final.twofactor_step5_title'), description: t('final.twofactor_step5_desc') }];


  const methods = [
  {
    id: 'totp',
    name: t('misc.tfsw_method_totp_name'),
    description: t('misc.tfsw_method_totp_desc'),
    icon: Smartphone,
    color: 'blue',
    recommended: true
  },
  {
    id: 'sms',
    name: t('misc.tfsw_method_sms_name'),
    description: t('misc.tfsw_method_sms_desc'),
    icon: Phone,
    color: 'green'
  },
  {
    id: 'email',
    name: t('misc.tfsw_method_email_name'),
    description: t('misc.tfsw_method_email_desc'),
    icon: Mail,
    color: 'purple'
  }];


  const handleMethodSelect = (methodId) => {
    setSelectedMethod(methodId);
    setError('');
  };

  const handleSetup = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.post('/2fa/setup', {
        method: selectedMethod,
        recovery_email: recoveryEmail || null,
        recovery_phone: recoveryPhone || null,
      }) as unknown as { json: () => Promise<Record<string, unknown>>; ok: boolean; status: number; data: Record<string, unknown> };

      const data = await response.json();

      if (response.ok) {
        setSetupData(data);
        setBackupCodes((data.backup_codes as unknown[]) || []);
        setCurrentStep(3);
        setSuccess(t('misc.tfsw_setup_created'));
      } else {
        setError(String(data.detail || t('misc.tfsw_setup_error')));
      }
    } catch {
      setError(t('misc.tfsw_setup_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleVerification = async () => {
    if (!verificationCode) {
      setError(t('misc.tfsw_code_required'));
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await api.post('/2fa/verify-setup', {
        method: selectedMethod,
        code: verificationCode,
      }) as unknown as { json: () => Promise<Record<string, unknown>>; ok: boolean; status: number; data: Record<string, unknown> };

      const data = await response.json();

      if (response.ok) {
        setCurrentStep(4);
        setSuccess(t('misc.tfsw_code_confirmed'));
      } else {
        setError(String(data.detail || t('misc.tfsw_invalid_code')));
      }
    } catch {
      setError(t('misc.tfsw_code_verify_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = () => {
    if (onComplete) {
      onComplete();
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSuccess(t('misc.tfsw_copied_to_clipboard'));
  };

  const downloadBackupCodes = () => {
    const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'backup-codes.txt';
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderStepIndicator = () =>
  <div className="flex items-center justify-center space-x-4 mb-8">
      {steps.map((step, index) =>
    <div key={step.id} className="flex items-center">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${currentStep >= step.id ?
      'bg-blue-600 text-white' :
      'bg-gray-200 text-gray-600'}`
      }>
            {currentStep > step.id ?
        <CheckCircle className="w-4 h-4" /> :

        step.id
        }
          </div>
          {index < steps.length - 1 &&
      <div className={`w-8 h-0.5 ${currentStep > step.id ? 'bg-blue-600' : 'bg-gray-200'}`
      } />
      }
        </div>
    )}
    </div>;


  const renderStep1 = () =>
  <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">{t('misc.tfsw_step1_title')}</h3>
        <p className="text-gray-600">
          {t('misc.tfsw_step1_desc')}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {methods.map((method) => {
        const IconComponent = method.icon;
        return (
          <button
            key={method.id}
            aria-label={`Select ${method.name} 2FA method`}
            onClick={() => handleMethodSelect(method.id)}
            className={`p-6 border-2 rounded-lg text-left transition-all ${selectedMethod === method.id ?
            'border-blue-500 bg-blue-50' :
            'border-gray-200 hover:border-gray-300'}`
            }>
            
              <div className="flex items-start space-x-3">
                <div className={`p-2 rounded-lg ${selectedMethod === method.id ? 'bg-blue-100' : 'bg-gray-100'}`
              }>
                  <IconComponent className={`w-6 h-6 ${selectedMethod === method.id ? 'text-blue-600' : 'text-gray-600'}`
                } />
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="font-semibold">{method.name}</h4>
                    {method.recommended &&
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">
                        {t('misc.tfsw_recommended')}
                      </span>
                  }
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{method.description}</p>
                </div>
              </div>
            </button>);

      })}
      </div>

      <div className="flex justify-end">
        <Button
        onClick={() => setCurrentStep(2)}
        disabled={!selectedMethod}>
        
          {t('misc.tfsw_next')}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>;


  const renderStep2 = () =>
  <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">{t('misc.tfsw_step2_title', { method: methods.find((m) => m.id === selectedMethod)?.name })}</h3>
        <p className="text-gray-600">
          {t('misc.tfsw_step2_desc')}
        </p>
      </div>

      <div className="space-y-4">
        {(selectedMethod === 'sms' || selectedMethod === 'email') &&
      <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {selectedMethod === 'sms' ? t('misc.tfsw_label_phone') : t('misc.tfsw_label_email')}
            </label>
            <Input
          type={selectedMethod === 'sms' ? 'tel' : 'email'}
          aria-label={selectedMethod === 'sms' ? '2FA setup phone number' : '2FA setup email address'}
          value={selectedMethod === 'sms' ? recoveryPhone : recoveryEmail}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
            if (selectedMethod === 'sms') {
              setRecoveryPhone(e.target.value);
            } else {
              setRecoveryEmail(e.target.value);
            }
          }}
          placeholder={selectedMethod === 'sms' ? '+7 (999) 123-45-67' : 'user@example.com'}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        
          </div>
      }

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('misc.tfsw_label_recovery_email')}
          </label>
          <Input
          type="email"
          aria-label="Recovery email"
          value={recoveryEmail}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRecoveryEmail(e.target.value)}
          placeholder="recovery@example.com"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('misc.tfsw_label_recovery_phone')}
          </label>
          <Input
          type="tel"
          aria-label="Recovery phone"
          value={recoveryPhone}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRecoveryPhone(e.target.value)}
          placeholder="+7 (999) 123-45-67"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
        
        </div>
      </div>

      <div className="flex justify-between">
        <Button
        onClick={() => setCurrentStep(1)}
        variant="outline">
        
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('misc.tfsw_back')}
        </Button>
        <Button
        onClick={handleSetup}
        disabled={loading}>
        
          {loading ?
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> :

        <Shield className="w-4 h-4 mr-2" />
        }
          {t('misc.tfsw_setup_button')}
        </Button>
      </div>
    </div>;


  const renderStep3 = () =>
  <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">{t('misc.tfsw_step3_title')}</h3>
        <p className="text-gray-600">
          {selectedMethod === 'totp' ?
        t('misc.tfsw_step3_desc_totp') :
        t('misc.tfsw_step3_desc_other')
        }
        </p>
      </div>

      {selectedMethod === 'totp' && setupData &&
    <div className="text-center">
          <div className="bg-white p-4 rounded-lg border inline-block">
            <div className="flex justify-center mb-4">
              <QrCode className="w-8 h-8 text-gray-600" />
            </div>
            <div className="text-sm text-gray-600 mb-2">
              {t('misc.tfsw_scan_qr')}
            </div>
            <div className="bg-gray-100 p-4 rounded-lg mb-4">
              {/* Здесь должен быть QR-код */}
              <div className="w-48 h-48 bg-gray-200 rounded flex items-center justify-center">
                <span className="text-gray-500">QR Code</span>
              </div>
            </div>
            <div className="text-sm text-gray-600 mb-2">
              {t('misc.tfsw_or_enter_secret')}
            </div>
            <div className="flex items-center space-x-2">
              <code className="px-3 py-2 bg-gray-100 rounded font-mono text-sm">
                {showSecret ? setupData.secret : '••••••••••••••••'}
              </code>
              <button
            onClick={() => setShowSecret(!showSecret)}
            aria-label={showSecret ? t('misc.tfsw_aria_hide_secret') : t('misc.tfsw_aria_show_secret')}
            className="text-gray-400 hover:text-gray-600">
            
                {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
              <button
            onClick={() => copyToClipboard(setupData.secret)}
            aria-label={t('misc.tfsw_aria_copy_secret')}
            className="text-gray-400 hover:text-gray-600">
            
                <Copy className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
    }

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('misc.tfsw_label_verification_code')}
        </label>
        <Input
        type="text"
        aria-label="2FA verification code"
        value={verificationCode}
        onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        placeholder="000000"
        className="w-full px-3 py-2 text-center text-2xl font-mono border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        maxLength={6} />
      
      </div>

      <div className="flex justify-between">
        <Button
        onClick={() => setCurrentStep(2)}
        variant="outline">
        
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('misc.tfsw_back')}
        </Button>
        <Button
        onClick={handleVerification}
        disabled={loading || verificationCode.length !== 6}>
        
          {loading ?
        <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> :

        <CheckCircle className="w-4 h-4 mr-2" />
        }
          {t('misc.tfsw_confirm_button')}
        </Button>
      </div>
    </div>;


  const renderStep4 = () =>
  <div className="space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold mb-2">{t('misc.tfsw_step4_title')}</h3>
        <p className="text-gray-600">
          {t('misc.tfsw_step4_desc')}
        </p>
      </div>

      <Card className="p-6">
        <div className="mb-4">
          <AlertCircle className="w-6 h-6 text-yellow-600 mb-2" />
          <h4 className="font-semibold text-yellow-800">{t('misc.tfsw_important')}</h4>
          <p className="text-sm text-yellow-700">
            {t('misc.tfsw_backup_warning')}
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
          {backupCodes.map((code, index) =>
        <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <code className="font-mono text-sm">{code}</code>
              <button
            onClick={() => copyToClipboard(code)}
            aria-label={t('misc.tfsw_aria_copy_backup_code', { index: index + 1 })}
            className="text-gray-400 hover:text-gray-600">
            
                <Copy className="w-4 h-4" />
              </button>
            </div>
        )}
        </div>

        <div className="flex space-x-2">
          <Button
          onClick={() => copyToClipboard(backupCodes.join('\n'))}
          variant="outline"
          size="small">
          
            <Copy className="w-4 h-4 mr-2" />
            {t('misc.tfsw_copy_all')}
          </Button>
          <Button
          onClick={downloadBackupCodes}
          variant="outline"
          size="small">
          
            <Download className="w-4 h-4 mr-2" />
            {t('misc.tfsw_download')}
          </Button>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button
        onClick={() => setCurrentStep(5)}>
        
          {t('misc.tfsw_continue')}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>;


  const renderStep5 = () =>
  <div className="text-center space-y-6">
      <div className="flex justify-center">
        <div className="p-4 bg-green-100 rounded-full">
          <CheckCircle className="w-12 h-12 text-green-600" />
        </div>
      </div>

      <div>
        <h3 className="text-xl font-semibold mb-2">{t('misc.tfsw_step5_title')}</h3>
        <p className="text-gray-600">
          {t('misc.tfsw_step5_desc')}
        </p>
      </div>

      <div className="bg-blue-50 p-4 rounded-lg">
        <h4 className="font-semibold text-blue-800 mb-2">{t('misc.tfsw_what_next')}</h4>
        <ul className="text-sm text-blue-700 space-y-1 text-left">
          <li>{t('misc.tfsw_next_step_app')}</li>
          <li>{t('misc.tfsw_next_step_backup')}</li>
          <li>{t('misc.tfsw_next_step_settings')}</li>
        </ul>
      </div>

      <div className="flex justify-center">
        <Button
        onClick={handleComplete}>
        
          <Shield className="w-4 h-4 mr-2" />
          {t('misc.tfsw_finish_button')}
        </Button>
      </div>
    </div>;


  return (
    <div className="max-w-2xl mx-auto">
      <Card className="p-8">
        {renderStepIndicator()}

        {currentStep === 1 && renderStep1()}
        {currentStep === 2 && renderStep2()}
        {currentStep === 3 && renderStep3()}
        {currentStep === 4 && renderStep4()}
        {currentStep === 5 && renderStep5()}

        {/* Уведомления */}
        {error &&
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-red-600" />
              <span className="text-sm text-red-800">{error}</span>
            </div>
          </div>
        }

        {success &&
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center space-x-2">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="text-sm text-green-800">{success}</span>
            </div>
          </div>
        }
      </Card>
    </div>);

};


TwoFactorSetupWizard.propTypes = {
  ...(TwoFactorSetupWizard.propTypes || {}),
  onComplete: PropTypes.any,
};

export default TwoFactorSetupWizard;
