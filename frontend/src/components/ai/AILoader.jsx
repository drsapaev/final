import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  LinearProgress,
  Paper,
  Stack,
  Fade,
  keyframes
} from '@mui/material';
import { Psychology, AutoAwesome } from '@mui/icons-material';

const pulse = keyframes`
  0% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.7;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
`;

const rotate = keyframes`
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
`;

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
    <Stack spacing={2} alignItems="center">
      {showIcon && variant === 'circular' && (
        <Box position="relative" display="inline-flex">
          <CircularProgress
            size={progressSize}
            thickness={2}
            sx={{
              color: 'primary.main',
              animationDuration: '1.5s'
            }}
          />
          <Box
            position="absolute"
            top={0}
            left={0}
            bottom={0}
            right={0}
            display="flex"
            alignItems="center"
            justifyContent="center"
          >
            <Psychology
              sx={{
                fontSize: iconSize,
                color: 'primary.main',
                animation: `${pulse} 2s ease-in-out infinite`
              }}
            />
          </Box>
        </Box>
      )}

      {variant === 'linear' && (
        <Box width="100%" maxWidth={400}>
          <Stack spacing={1}>
            {showIcon && (
              <Box display="flex" justifyContent="center">
                <AutoAwesome
                  sx={{
                    fontSize: iconSize,
                    color: 'primary.main',
                    animation: `${rotate} 3s linear infinite`
                  }}
                />
              </Box>
            )}
            <LinearProgress
              variant={progress !== null ? 'determinate' : 'indeterminate'}
              value={progress}
              sx={{
                height: 6,
                borderRadius: 3,
                '& .MuiLinearProgress-bar': {
                  borderRadius: 3
                }
              }}
            />
          </Stack>
        </Box>
      )}

      {text && (
        <Fade in timeout={500}>
          <Typography
            variant={fontSize}
            color="text.primary"
            align="center"
            sx={{ fontWeight: 500 }}
          >
            {text}
          </Typography>
        </Fade>
      )}

      {subtext && (
        <Fade in timeout={700}>
          <Typography
            variant="caption"
            color="text.secondary"
            align="center"
          >
            {subtext}
          </Typography>
        </Fade>
      )}

      {progress !== null && (
        <Typography variant="caption" color="text.secondary">
          {Math.round(progress)}%
        </Typography>
      )}
    </Stack>
  );

  if (fullScreen) {
    return (
      <Box
        position="fixed"
        top={0}
        left={0}
        right={0}
        bottom={0}
        display="flex"
        alignItems="center"
        justifyContent="center"
        bgcolor="rgba(0, 0, 0, 0.5)"
        zIndex={9999}
      >
        <Paper
          elevation={3}
          sx={{
            p: 4,
            borderRadius: 2,
            bgcolor: 'background.paper'
          }}
        >
          {content}
        </Paper>
      </Box>
    );
  }

  return (
    <Box
      display="flex"
      alignItems="center"
      justifyContent="center"
      p={3}
    >
      {content}
    </Box>
  );
};

export default AILoader;
