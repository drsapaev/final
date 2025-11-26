import React from 'react';
import { Box, Typography, Progress, CircularProgress } from '../../components/ui/macos';
import { Brain, Sparkles } from 'lucide-react';

const AILoader = ({ 
  variant = 'circular',
  text = 'AI анализирует данные...',
  subtext = null,
  size = 'medium',
  fullScreen = false,
  showIcon = true,
  progress = null
}) => {
  const getSizeProps = () => {
    switch (size) {
      case 'small':
        return { iconSize: 24, progressSize: 30, fontSize: 'body2' };
      case 'large':
        return { iconSize: 48, progressSize: 60, fontSize: 'h6' };
      default:
        return { iconSize: 36, progressSize: 45, fontSize: 'body1' };
    }
  };

  const { iconSize, progressSize, fontSize } = getSizeProps();

  const content = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
      {showIcon && variant === 'circular' && (
        <div style={{ position: 'relative', display: 'inline-flex' }}>
          <CircularProgress size={progressSize} />
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Brain style={{ width: iconSize, height: iconSize, color: 'var(--mac-accent-blue)' }} />
          </div>
        </div>
      )}

      {variant === 'linear' && (
        <div style={{ width: '100%', maxWidth: 400 }}>
          {showIcon && (
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 6 }}>
              <Sparkles style={{ width: iconSize, height: iconSize, color: 'var(--mac-accent-blue)' }} />
            </div>
          )}
          <Progress value={progress} />
        </div>
      )}

      {text && (
        <Typography variant={fontSize} color="textPrimary" style={{ fontWeight: 500, textAlign: 'center' }}>
          {text}
        </Typography>
      )}

      {subtext && (
        <Typography variant="caption" color="textSecondary" style={{ textAlign: 'center' }}>
          {subtext}
        </Typography>
      )}

      {progress !== null && (
        <Typography variant="caption" color="textSecondary">{Math.round(progress)}%</Typography>
      )}
    </div>
  );

  if (fullScreen) {
    return (
      <div style={{
        position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'rgba(0,0,0,0.5)', zIndex: 9999
      }}>
        <div style={{
          background: 'var(--mac-bg-primary)', borderRadius: 12, padding: 24, minWidth: 320,
          border: '1px solid var(--mac-border)', boxShadow: 'var(--mac-shadow-lg)'
        }}>
          {content}
        </div>
      </div>
    );
  }

  return (
    <Box style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 12 }}>
      {content}
    </Box>
  );
};

export default AILoader;

