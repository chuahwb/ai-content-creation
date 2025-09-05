'use client';

import React from 'react';
import {
  Box,
  Typography,
  RadioGroup,
  FormControlLabel,
  Radio,
  TextField,
  Tooltip,
  IconButton,
  Paper,
  Collapse,
  useTheme,
  useMediaQuery,
  Chip,
} from '@mui/material';
import { Info as InfoIcon, Edit as EditIcon, AutoFixHigh as AutoFixHighIcon } from '@mui/icons-material';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';

type EditMode = 'defaultEdit' | 'instructedEdit';

interface EditModeSelectorProps {
  mode: EditMode;
  onModeChange: (mode: EditMode) => void;
  editInstruction: string;
  onEditInstructionChange: (instruction: string) => void;
  disabled?: boolean;
  visible?: boolean;
  embedded?: boolean; // When true, don't render the Paper wrapper
}

/**
 * EditModeSelector - A component with radio buttons for Default Edit vs Instructed Edit
 * and a textarea for editInstruction. Only visible when a reference image is present.
 */
const EditModeSelector: React.FC<EditModeSelectorProps> = ({
  mode,
  onModeChange,
  editInstruction,
  onEditInstructionChange,
  disabled = false,
  visible = true,
  embedded = false,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  if (!visible) {
    return null;
  }

  const handleModeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onModeChange(event.target.value as EditMode);
  };

  const handleInstructionChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onEditInstructionChange(event.target.value);
  };

  const content = (
    <>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <EditIcon sx={{ color: 'warning.main', mr: 1, fontSize: '1.25rem' }} />
        <Typography 
          variant="subtitle2" 
          component="legend" 
          sx={{ 
            fontWeight: 600,
            color: 'text.primary',
            fontSize: { xs: '0.875rem', sm: '1rem' }
          }}
        >
          Image Editing Mode
        </Typography>
        <Chip 
          label="With Image" 
          size="small" 
          sx={{ 
            ml: 1, 
            height: 20, 
            fontSize: '0.7rem',
            bgcolor: 'warning.50',
            color: 'warning.dark'
          }} 
        />
        <Tooltip 
          title="Default Edit preserves the main subject. Instructed Edit lets you specify which elements to preserve or modify."
          {...TOOLTIP_CONFIG}
        >
          <IconButton size="small" sx={{ ml: 'auto', p: 0.5 }}>
            <InfoIcon sx={INFO_ICON_STYLE} />
          </IconButton>
        </Tooltip>
      </Box>

      <RadioGroup
        value={mode}
        onChange={handleModeChange}
        row={!isMobile}
        sx={{ mb: 1.5 }}
      >
        <FormControlLabel
          value="defaultEdit"
          control={<Radio size={isMobile ? "small" : "medium"} />}
          label={
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <AutoFixHighIcon sx={{ mr: 0.5, fontSize: '1rem', color: 'success.main' }} />
              <Typography variant="body2" sx={{ fontSize: { xs: '0.875rem', sm: '0.95rem' } }}>
                Default Edit
              </Typography>
            </Box>
          }
          disabled={disabled}
          sx={{ mr: { xs: 0, sm: 3 }, mb: { xs: 1, sm: 0 } }}
        />
        <FormControlLabel
          value="instructedEdit"
          control={<Radio size={isMobile ? "small" : "medium"} />}
          label={
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <EditIcon sx={{ mr: 0.5, fontSize: '1rem', color: 'info.main' }} />
              <Typography variant="body2" sx={{ fontSize: { xs: '0.875rem', sm: '0.95rem' } }}>
                Instructed Edit
              </Typography>
            </Box>
          }
          disabled={disabled}
        />
      </RadioGroup>

      <Collapse in={mode === 'defaultEdit'}>
        <Box sx={{ 
          p: 1.5, 
          bgcolor: 'success.50', 
          borderRadius: 1, 
          border: 1, 
          borderColor: 'success.200',
          mb: 1
        }}>
          <Typography 
            variant="body2" 
            color="success.dark" 
            sx={{ 
              fontStyle: 'italic',
              fontSize: { xs: '0.8125rem', sm: '0.875rem' }
            }}
          >
            The main subject of the image will be preserved, using your creative brief for styling guidance.
          </Typography>
        </Box>
      </Collapse>

      <Collapse in={mode === 'instructedEdit'}>
        <Box sx={{ mt: 1 }}>
          <TextField
            fullWidth
            multiline
            rows={isMobile ? 2 : 3}
            value={editInstruction}
            onChange={handleInstructionChange}
            disabled={disabled}
            placeholder="Specify which elements to preserve or modify..."
            variant="outlined"
            label="Edit Instructions"
            size={isMobile ? "small" : "medium"}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 1.5,
                bgcolor: 'info.50',
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  bgcolor: 'background.paper',
                  '& fieldset': {
                    borderColor: 'info.main',
                  },
                },
                '&.Mui-focused': {
                  bgcolor: 'background.paper',
                  '& fieldset': {
                    borderWidth: 2,
                    borderColor: 'info.main',
                  },
                },
              },
              '& .MuiInputBase-input': {
                fontSize: { xs: '0.875rem', sm: '0.95rem' },
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
            💡 Examples: "Keep the main dish, change background to marble" • "Preserve product, make lighting warmer"
          </Typography>
        </Box>
      </Collapse>
    </>
  );

  return embedded ? content : (
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
          borderColor: 'warning.light',
          boxShadow: theme.shadows[1],
        }
      }}
    >
      {content}
    </Paper>
  );
};

export default EditModeSelector;
