'use client';

import React from 'react';
import {
  TextField,
  Typography,
  Box,
  Tooltip,
  IconButton,
  Paper,
  Chip,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import { Info as InfoIcon, Create as CreateIcon } from '@mui/icons-material';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';

interface CreativeBriefInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string;
  placeholder?: string;
  hasImage?: boolean; // To show alternative completion state
}

/**
 * CreativeBriefInput - A robust textarea component for the main generalBrief
 * This replaces the legacy "prompt" field with a more descriptive creative brief input
 */
const CreativeBriefInput: React.FC<CreativeBriefInputProps> = ({
  value,
  onChange,
  disabled = false,
  error,
  placeholder = "Describe the visual style, mood, composition, or specific imagery you want to create...",
  hasImage = false
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value);
  };

  return (
    <Paper 
      elevation={0}
      sx={{ 
        p: { xs: 2, sm: 2.5 },
        mb: 2,
        border: 1,
        borderColor: 'divider',
        borderRadius: 2,
        bgcolor: 'background.paper',
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          borderColor: 'primary.light',
          boxShadow: theme.shadows[1],
        }
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
        <CreateIcon sx={{ color: 'primary.main', mr: 1, fontSize: '1.25rem' }} />
        <Typography 
          variant="subtitle2" 
          component="label" 
          sx={{ 
            fontWeight: 600, 
            color: 'text.primary',
            fontSize: { xs: '0.875rem', sm: '1rem' }
          }}
        >
          Creative Brief
        </Typography>
        <Chip 
          label={value ? "Provided ✓" : hasImage ? "Optional (Image provided)" : "Optional"} 
          size="small" 
          color={value ? "success" : hasImage ? "info" : "default"}
          variant="outlined" 
          sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
        />
        <Tooltip 
          title="Focus on visual aspects: style, mood, composition, colors, lighting. Campaign goals and text content are handled separately."
          {...TOOLTIP_CONFIG}
        >
          <IconButton size="small" sx={{ ml: 'auto', p: 0.5 }}>
            <InfoIcon sx={INFO_ICON_STYLE} />
          </IconButton>
        </Tooltip>
      </Box>
      
      <TextField
        fullWidth
        multiline
        rows={isMobile ? 3 : 3}
        value={value}
        onChange={handleChange}
        disabled={disabled}
        error={!!error}
        helperText={error}
        placeholder={placeholder}
        variant="outlined"
        size={isMobile ? "small" : "medium"}
        sx={{
          '& .MuiOutlinedInput-root': {
            borderRadius: 1.5,
            bgcolor: 'grey.50',
            transition: 'all 0.2s ease-in-out',
            '&:hover': {
              bgcolor: 'background.paper',
              '& fieldset': {
                borderColor: 'primary.main',
              },
            },
            '&.Mui-focused': {
              bgcolor: 'background.paper',
              '& fieldset': {
                borderWidth: 2,
                borderColor: 'primary.main',
              },
            },
          },
          '& .MuiInputBase-input': {
            fontSize: { xs: '0.875rem', sm: '0.95rem' },
            lineHeight: 1.5,
          },
        }}
      />
      
      <Typography 
        variant="caption" 
        color="text.secondary" 
        sx={{ 
          mt: 1, 
          display: 'block',
          fontSize: { xs: '0.75rem', sm: '0.8125rem' },
          fontStyle: 'italic'
        }}
      >
        💡 Examples: "Vibrant summer aesthetic with bright colors" • "Minimalist style with soft lighting"
      </Typography>
    </Paper>
  );
};

export default CreativeBriefInput;
