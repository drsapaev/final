import React, { useState } from 'react';
import {
  Button,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  CircularProgress
} from '@mui/material';
import {
  Psychology,
  AutoAwesome,
  SmartToy,
  PsychologyOutlined
} from '@mui/icons-material';

const AIButton = ({ 
  onClick, 
  loading = false, 
  variant = 'contained',
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
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);

  const handleClick = (event) => {
    if (providers && providers.length > 0) {
      setAnchorEl(event.currentTarget);
    } else {
      onClick();
    }
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleProviderClick = (provider) => {
    handleClose();
    if (onProviderSelect) {
      onProviderSelect(provider);
    }
    onClick(provider);
  };

  const getProviderIcon = (provider) => {
    switch (provider) {
      case 'openai':
        return <SmartToy />;
      case 'gemini':
        return <AutoAwesome />;
      case 'deepseek':
        return <Psychology />;
      default:
        return <Psychology />;
    }
  };

  const getProviderName = (provider) => {
    switch (provider) {
      case 'openai':
        return 'OpenAI GPT-4';
      case 'gemini':
        return 'Google Gemini';
      case 'deepseek':
        return 'DeepSeek';
      default:
        return provider;
    }
  };

  if (variant === 'icon') {
    return (
      <>
        <Tooltip title={tooltip}>
          <span>
            <IconButton
              onClick={handleClick}
              color={color}
              disabled={loading || disabled}
              size={size}
            >
              {loading ? (
                <CircularProgress size={24} />
              ) : (
                <Psychology />
              )}
            </IconButton>
          </span>
        </Tooltip>
        
        {providers && (
          <Menu
            anchorEl={anchorEl}
            open={open}
            onClose={handleClose}
          >
            {providers.map((provider) => (
              <MenuItem
                key={provider}
                onClick={() => handleProviderClick(provider)}
              >
                <ListItemIcon>
                  {getProviderIcon(provider)}
                </ListItemIcon>
                <ListItemText>
                  {getProviderName(provider)}
                </ListItemText>
              </MenuItem>
            ))}
          </Menu>
        )}
      </>
    );
  }

  return (
    <>
      <Button
        variant={variant}
        color={color}
        size={size}
        fullWidth={fullWidth}
        onClick={handleClick}
        disabled={loading || disabled}
        startIcon={icon && !loading && <Psychology />}
      >
        {loading ? (
          <>
            <CircularProgress size={20} sx={{ mr: 1 }} />
            Анализ...
          </>
        ) : (
          text
        )}
      </Button>

      {providers && (
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleClose}
        >
          {providers.map((provider) => (
            <MenuItem
              key={provider}
              onClick={() => handleProviderClick(provider)}
            >
              <ListItemIcon>
                {getProviderIcon(provider)}
              </ListItemIcon>
              <ListItemText>
                {getProviderName(provider)}
              </ListItemText>
            </MenuItem>
          ))}
        </Menu>
      )}
    </>
  );
};

export default AIButton;
