'use client';

import React from 'react';
import {
  Box,
  Typography,
  TextField,
  Tooltip,
  IconButton,
  Paper,
  Alert,
  Collapse,
  useTheme,
  useMediaQuery,
  Chip,
} from '@mui/material';
import { Info as InfoIcon, TextFields as TextFieldsIcon, FormatQuote as FormatQuoteIcon } from '@mui/icons-material';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { TextOverlay } from '@/types/api';

interface TextOverlayComposerProps {
  value: string;
  onChange: (text: string) => void;
  disabled?: boolean;
  visible?: boolean;
  embedded?: boolean; // When true, don't render the Paper wrapper and title
}

/**
 * TextOverlayComposer - A component for composing text overlay content
 * Only visible when text rendering is enabled. Handles the "quotes for literals" convention.
 */
const TextOverlayComposer: React.FC<TextOverlayComposerProps> = ({
  value,
  onChange,
  disabled = false,
  visible = true,
  embedded = false,
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  
  if (!visible) {
    return null;
  }

  const handleTextChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onChange(event.target.value);
  };

  const hasQuotedText = value?.includes('"') || value?.includes("'");
  const hasContent = value && value.trim().length > 0;

  const content = (
    <>
      {!embedded && (
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <TextFieldsIcon sx={{ color: 'info.main', mr: 1, fontSize: '1.25rem' }} />
          <Typography 
            variant="subtitle2" 
            component="legend" 
            sx={{ 
              fontWeight: 600,
              color: 'text.primary',
              fontSize: { xs: '0.875rem', sm: '1rem' }
            }}
          >
            Text Overlay
          </Typography>
          <Chip 
            label="Text Rendering" 
            size="small" 
            sx={{ 
              ml: 1, 
              height: 20, 
              fontSize: '0.7rem',
              bgcolor: 'info.50',
              color: 'info.dark'
            }} 
          />
          <Tooltip 
            title='Use quotes for exact text: "Sale 50% Off!" or describe content: promotional headline about deals'
            {...TOOLTIP_CONFIG}
          >
            <IconButton size="small" sx={{ ml: 'auto', p: 0.5 }}>
              <InfoIcon sx={INFO_ICON_STYLE} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <Alert 
        severity="info" 
        icon={<FormatQuoteIcon />}
        sx={{ 
          mb: 2, 
          fontSize: '0.8125rem',
          '& .MuiAlert-message': { py: 0.5 }
        }}
      >
                  <Typography variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 500 }}>
            Text Convention: <code>&quot;Exact text&quot;</code> or <code>content description</code>
          </Typography>
      </Alert>

      <TextField
        fullWidth
        multiline
        rows={isMobile ? 2 : 3}
        value={value || ''}
        onChange={handleTextChange}
        disabled={disabled}
        placeholder='Use "quotes" for exact text or describe the content...'
        variant="outlined"
        label="Text Content"
        size={isMobile ? "small" : "medium"}
        sx={{
          mb: hasQuotedText ? 1.5 : 0,
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
            lineHeight: 1.5,
          },
        }}
      />

      <Collapse in={hasQuotedText}>
        <Alert 
          severity="success" 
          icon={<FormatQuoteIcon />}
          sx={{ 
            fontSize: '0.8125rem',
            '& .MuiAlert-message': { py: 0.5 }
          }}
        >
          <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
            ✓ Literal text detected - quoted text will appear exactly as written
          </Typography>
        </Alert>
      </Collapse>

      <Typography 
        variant="caption" 
        color="text.secondary" 
        sx={{ 
          mt: 1, 
          display: 'block',
          fontSize: { xs: '0.75rem', sm: '0.8125rem' },
          fontStyle: 'italic',
          opacity: hasContent ? 0.7 : 1
        }}
      >
        💡 Examples: <code>&quot;Flash Sale!&quot;</code> (exact) • <code>catchy product headline</code> (description)
      </Typography>
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
          borderColor: 'info.light',
          boxShadow: theme.shadows[1],
        }
      }}
    >
      {content}
    </Paper>
  );
};

export default TextOverlayComposer;
