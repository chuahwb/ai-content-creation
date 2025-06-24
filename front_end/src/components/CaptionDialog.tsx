'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  IconButton,
  Chip,
  Alert,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  AutoAwesome as AutoAwesomeIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';
import { CaptionSettings } from '@/types/api';

interface CaptionDialogProps {
  open: boolean;
  onClose: () => void;
  onGenerate: (settings: CaptionSettings) => void;
  isGenerating?: boolean;
  imageIndex: number;
  initialSettings?: CaptionSettings;
  error?: string;
}

export default function CaptionDialog({
  open,
  onClose,
  onGenerate,
  isGenerating = false,
  imageIndex,
  initialSettings,
  error,
}: CaptionDialogProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [settings, setSettings] = useState<CaptionSettings>({
    include_emojis: true, // Default to true for better engagement
  });

  // Populate settings when initialSettings is provided (for regeneration)
  useEffect(() => {
    if (initialSettings && open) {
      setSettings(initialSettings);
      setAdvancedOpen(true); // Auto-expand advanced options when regenerating
    } else if (open) {
      // Reset to defaults when opening for new generation
      setSettings({ include_emojis: true });
      setAdvancedOpen(false);
    }
  }, [initialSettings, open]);

  const handleGenerate = () => {
    // If advanced options are not opened, send empty settings for auto-mode
    const finalSettings = advancedOpen ? settings : {};
    onGenerate(finalSettings);
  };

  const handleClose = () => {
    if (!isGenerating) {
      onClose();
      // Reset state
      setAdvancedOpen(false);
      setSettings({ include_emojis: true });
    }
  };

  const toneOptions = [
    { value: 'professional', label: 'Professional & Polished' },
    { value: 'friendly', label: 'Friendly & Casual' },
    { value: 'witty', label: 'Witty & Playful' },
    { value: 'inspirational', label: 'Inspirational & Aspirational' },
    { value: 'direct', label: 'Direct & Sales-focused' },
  ];

  const hashtagOptions = [
    { value: 'none', label: 'None (No hashtags)' },
    { value: 'niche', label: 'Niche & Specific' },
    { value: 'broad', label: 'Broad & Trending' },
    { value: 'balanced', label: 'Balanced Mix' },
  ];

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          maxHeight: '90vh',
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1,
        borderBottom: 1,
        borderColor: 'divider'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesomeIcon color="primary" />
          <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
            {initialSettings ? 'Regenerate Caption' : 'Generate Caption'}
          </Typography>
          <Chip 
            label={`Option ${imageIndex + 1}`} 
            size="small" 
            color="primary" 
            variant="outlined"
          />
        </Box>
        <IconButton 
          onClick={handleClose} 
          disabled={isGenerating}
          sx={{ color: 'grey.500' }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 3, pb: 2 }}>
        {/* Error Display */}
        {error && (
          <Alert severity="error" sx={{ mb: 3 }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              Caption Generation Error
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 0.5 }}>
              {error}
            </Typography>
          </Alert>
        )}

        {/* Auto Mode Description */}
        <Box sx={{ mb: 3, p: 2, backgroundColor: 'primary.50', borderRadius: 2, border: 1, borderColor: 'primary.100' }}>
          <Typography variant="body2" sx={{ fontWeight: 500, color: 'primary.main', mb: 1 }}>
            ✨ Auto Mode (Recommended)
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Our AI will analyze your image, marketing strategy, and visual style to create the perfect caption automatically. 
            No configuration needed!
          </Typography>
        </Box>

        {/* Advanced Options Accordion */}
        <Accordion 
          expanded={advancedOpen} 
          onChange={(_, expanded) => setAdvancedOpen(expanded)}
          sx={{ 
            boxShadow: 'none', 
            border: 1, 
            borderColor: 'divider',
            borderRadius: 2,
            '&:before': { display: 'none' },
            '&.Mui-expanded': { margin: 0 }
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            sx={{ 
              backgroundColor: 'grey.50',
              borderRadius: advancedOpen ? '8px 8px 0 0' : 2,
              minHeight: 56,
              '&.Mui-expanded': { minHeight: 56 }
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TuneIcon color="action" fontSize="small" />
              <Typography variant="subtitle2" sx={{ fontWeight: 500 }}>
                Advanced Options
              </Typography>
              {!advancedOpen && (
                <Chip 
                  label="Optional" 
                  size="small" 
                  variant="outlined" 
                  sx={{ ml: 1, fontSize: '0.7rem' }}
                />
              )}
            </Box>
          </AccordionSummary>
          
          <AccordionDetails sx={{ pt: 3, pb: 2 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Caption Tone */}
              <FormControl fullWidth>
                <InputLabel>Caption Tone</InputLabel>
                <Select
                  value={settings.tone || ''}
                  label="Caption Tone"
                  onChange={(e) => setSettings(prev => ({ ...prev, tone: e.target.value as any }))}
                >
                  <MenuItem value="">
                    <em>Auto (Let AI decide)</em>
                  </MenuItem>
                  {toneOptions.map(option => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Call to Action */}
              <TextField
                fullWidth
                label="Call to Action (CTA)"
                placeholder="e.g., Shop Now, Learn More, Link in Bio"
                value={settings.cta || ''}
                onChange={(e) => setSettings(prev => ({ ...prev, cta: e.target.value }))}
                helperText="Leave blank for AI to generate automatically"
              />

              {/* Include Emojis Toggle */}
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.include_emojis ?? true}
                    onChange={(e) => setSettings(prev => ({ ...prev, include_emojis: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Include Emojis"
                sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  ml: 0,
                  '& .MuiFormControlLabel-label': { flex: 1 }
                }}
              />

              {/* Hashtag Strategy */}
              <FormControl fullWidth>
                <InputLabel>Hashtag Strategy</InputLabel>
                <Select
                  value={settings.hashtag_strategy || ''}
                  label="Hashtag Strategy"
                  onChange={(e) => setSettings(prev => ({ ...prev, hashtag_strategy: e.target.value as any }))}
                >
                  <MenuItem value="">
                    <em>Auto (Balanced Mix)</em>
                  </MenuItem>
                  {hashtagOptions.map(option => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </AccordionDetails>
        </Accordion>
      </DialogContent>

      <DialogActions sx={{ 
        px: 3, 
        py: 2, 
        borderTop: 1, 
        borderColor: 'divider',
        backgroundColor: 'grey.50'
      }}>
        <Button 
          onClick={handleClose} 
          disabled={isGenerating}
          color="inherit"
        >
          Cancel
        </Button>
        <Button
          onClick={handleGenerate}
          variant="contained"
          disabled={isGenerating}
          startIcon={<AutoAwesomeIcon />}
          sx={{ 
            fontWeight: 600,
            px: 3,
            background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
            '&:hover': {
              background: 'linear-gradient(45deg, #1976D2 30%, #0288D1 90%)',
            }
          }}
        >
          {isGenerating ? 'Generating...' : (initialSettings ? 'Regenerate Caption' : 'Generate Caption')}
        </Button>
      </DialogActions>
    </Dialog>
  );
} 