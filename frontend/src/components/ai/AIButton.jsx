import React, { useState, useRef, useEffect } from 'react';
import { Button } from '../../components/ui/macos';
import { Brain, Sparkles, Bot } from 'lucide-react';

const AIButton = ({ 
  onClick, 
  loading = false, 
  variant = 'default',
  size = 'medium',
  fullWidth = false,
  tooltip = 'AI анализ',
  icon = true,
  text = 'AI анализ',
  color = 'primary',
  providers = null,
  onProviderSelect = null,
  disabled = false
}) => {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (anchorRef.current && !anchorRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleClick = (event) => {
    if (providers && providers.length > 0) {
      setOpen((v) => !v);
    } else {
      onClick();
    }
  };

  const handleProviderClick = (provider) => {
    setOpen(false);
    if (onProviderSelect) onProviderSelect(provider);
    onClick(provider);
  };

  const getProviderIcon = (provider) => {
    switch (provider) {
      case 'openai':
        return <Bot style={{ width: 16, height: 16 }} />;
      case 'gemini':
        return <Sparkles style={{ width: 16, height: 16 }} />;
      case 'deepseek':
        return <Brain style={{ width: 16, height: 16 }} />;
      default:
        return <Brain style={{ width: 16, height: 16 }} />;
    }
  };

  const getProviderName = (provider) => {
    switch (provider) {
      case 'openai':
        return 'OpenAI';
      case 'gemini':
        return 'Google Gemini';
      case 'deepseek':
        return 'DeepSeek';
      default:
        return provider;
    }
  };

  return (
    <div style={{ position: 'relative', display: fullWidth ? 'block' : 'inline-block' }} ref={anchorRef} title={tooltip}>
      <Button
        variant={variant === 'contained' ? 'primary' : variant === 'outlined' ? 'outline' : 'default'}
        size={size === 'small' ? 'small' : size === 'large' ? 'large' : 'default'}
        fullWidth={fullWidth}
        onClick={handleClick}
        disabled={loading || disabled}
        style={{ minWidth: fullWidth ? '100%' : undefined }}
      >
        {loading ? (
          'Анализ...'
        ) : (
          <>
            {icon && <Brain style={{ width: 16, height: 16, marginRight: 8 }} />}
            {text}
          </>
        )}
      </Button>

      {providers && open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 6, minWidth: 220,
          background: 'var(--mac-bg-primary)', border: '1px solid var(--mac-border)', borderRadius: 8,
          boxShadow: 'var(--mac-shadow-lg)', zIndex: 20
        }}>
          {providers.map((provider) => (
            <button
              key={provider}
              onClick={() => handleProviderClick(provider)}
              style={{
                display: 'flex', alignItems: 'center', width: '100%', padding: '8px 12px',
                background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left'
              }}
            >
              <span style={{ marginRight: 8 }}>{getProviderIcon(provider)}</span>
              <span>{getProviderName(provider)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default AIButton;

