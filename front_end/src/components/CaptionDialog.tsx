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
  IconButton,
  Chip,
  Alert,
  RadioGroup,
  Radio,
  CircularProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  AutoAwesome as AutoAwesomeIcon,
  Tune as TuneIcon,
  Speed as SpeedIcon,
  Psychology as PsychologyIcon,
} from '@mui/icons-material';
import { CaptionSettings, CaptionModelOption } from '@/types/api';
import { PipelineAPI } from '@/lib/api';

interface CaptionDialogProps {
  open: boolean;
  onClose: () => void;
  onGenerate: (settings: CaptionSettings, modelId?: string) => void;
  isGenerating?: boolean;
  imageIndex: number;
  initialSettings?: CaptionSettings;
  initialModelId?: string;
  error?: string;
}

export default function CaptionDialog({
  open,
  onClose,
  onGenerate,
  isGenerating = false,
  imageIndex,
  initialSettings,
  initialModelId,
  error,
}: CaptionDialogProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [settings, setSettings] = useState<CaptionSettings>({
    include_emojis: true, // Default to true for better engagement
  });
  const [selectedModelId, setSelectedModelId] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<CaptionModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Load available models when dialog opens
  useEffect(() => {
    if (open && availableModels.length === 0) {
      setLoadingModels(true);
      PipelineAPI.getCaptionModels()
        .then(response => {
          setAvailableModels(response.models);
          // Set default model if none selected
          if (!selectedModelId) {
            setSelectedModelId(initialModelId || response.default_model_id);
          }
        })
        .catch(error => {
          console.error('Failed to load caption models:', error);
        })
        .finally(() => {
          setLoadingModels(false);
        });
    }
  }, [open, availableModels.length, selectedModelId, initialModelId]);

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
    
    if (initialModelId && open) {
      setSelectedModelId(initialModelId);
    }
  }, [initialSettings, initialModelId, open]);

  const handleGenerate = () => {
    // If advanced options are not opened, send empty settings for auto-mode
    const finalSettings = advancedOpen ? settings : {};
    onGenerate(finalSettings, selectedModelId);
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
    { value: 'none', label: 'None' },
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
          borderRadius: 2,
          maxHeight: '90vh',
          boxShadow: 4,
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 2,
        borderBottom: '1px solid',
        borderColor: 'grey.200',
        backgroundColor: 'white'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h6" component="div" sx={{ fontWeight: 600, color: 'text.primary' }}>
            {initialSettings ? 'Regenerate Caption' : 'Generate Caption'}
          </Typography>
          <Chip 
            label={`Image ${imageIndex + 1}`} 
            size="small" 
            variant="outlined"
            sx={{ 
              borderColor: 'primary.main',
              color: 'primary.main',
              fontWeight: 500,
              fontSize: '0.6875rem'
            }}
          />
        </Box>
        <IconButton 
          onClick={handleClose} 
          disabled={isGenerating}
          sx={{ 
            color: 'grey.400',
            '&:hover': { 
              backgroundColor: 'grey.100',
              color: 'grey.600'
            }
          }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 3, pb: 2, px: 3 }}>
        {/* Error Display */}
        {error && (
          <Alert 
            severity="error" 
            sx={{ 
              mb: 3,
              borderRadius: 2,
              border: '1px solid',
              borderColor: 'error.200'
            }}
          >
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              Caption Generation Error
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
              {error}
            </Typography>
          </Alert>
        )}

        {/* Auto Mode Description */}
        <Box sx={{ 
          mb: 3, 
          p: 2.5, 
          backgroundColor: 'primary.25', 
          borderRadius: 2, 
          border: '1px solid', 
          borderColor: 'primary.100' 
        }}>
          <Typography variant="body2" sx={{ 
            fontWeight: 600, 
            color: 'primary.main', 
            mb: 1,
            fontSize: '0.8125rem'
          }}>
            Recommended: Auto Mode
          </Typography>
          <Typography variant="body2" sx={{ 
            color: 'text.secondary', 
            lineHeight: 1.5,
            fontSize: '0.8125rem'
          }}>
            Our AI analyzes your image, marketing strategy, and visual style to create optimized captions automatically. 
            Expand Advanced Options below only if you need specific customizations.
          </Typography>
        </Box>

        {/* Advanced Options Accordion */}
        <Accordion 
          expanded={advancedOpen} 
          onChange={(_, expanded) => setAdvancedOpen(expanded)}
          sx={{ 
            boxShadow: 'none', 
            border: '1px solid', 
            borderColor: 'grey.200',
            borderRadius: 2,
            backgroundColor: 'white',
            '&:before': { display: 'none' },
            '&.Mui-expanded': { margin: 0 }
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon sx={{ color: 'text.secondary' }} />}
            sx={{ 
              backgroundColor: 'grey.50',
              borderRadius: advancedOpen ? '8px 8px 0 0' : 2,
              minHeight: 56,
              transition: 'background-color 0.2s ease-in-out',
              '&:hover': {
                backgroundColor: 'grey.100'
              },
              '&.Mui-expanded': { minHeight: 56 }
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography variant="subtitle2" sx={{ 
                fontWeight: 600,
                color: 'text.primary',
                fontSize: '0.875rem'
              }}>
                Advanced Options
              </Typography>
              {!advancedOpen && (
                <Chip 
                  label="Optional" 
                  size="small" 
                  variant="outlined" 
                  sx={{ 
                    fontSize: '0.6875rem',
                    height: 20,
                    borderColor: 'grey.300',
                    color: 'text.secondary'
                  }}
                />
              )}
            </Box>
          </AccordionSummary>
          
          <AccordionDetails sx={{ pt: 3, pb: 3, px: 3 }}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {/* Model Selection */}
              <Box>
                <Typography variant="subtitle2" sx={{ 
                  fontWeight: 600, 
                  mb: 1.5, 
                  color: 'text.primary',
                  fontSize: '0.8125rem'
                }}>
                  Processing Model
                </Typography>
                <Typography variant="body2" sx={{ 
                  color: 'text.secondary', 
                  mb: 2,
                  fontSize: '0.75rem',
                  lineHeight: 1.4
                }}>
                  Choose between speed-optimized or capability-enhanced processing
                </Typography>
                
                {loadingModels ? (
                  <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
                    <CircularProgress size={24} />
                  </Box>
                ) : (
                  <RadioGroup
                    value={selectedModelId}
                    onChange={(e) => setSelectedModelId(e.target.value)}
                  >
                    {availableModels.map((model) => (
                      <Box
                        key={model.id}
                        sx={{
                          border: '1px solid',
                          borderColor: selectedModelId === model.id ? 'primary.main' : 'grey.200',
                          borderRadius: 2,
                          backgroundColor: selectedModelId === model.id ? 'primary.25' : 'white',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease-in-out',
                          mb: 1,
                          '&:hover': {
                            borderColor: 'primary.main',
                            backgroundColor: selectedModelId === model.id ? 'primary.50' : 'primary.25',
                          }
                        }}
                        onClick={() => setSelectedModelId(model.id)}
                      >
                        <FormControlLabel
                          control={
                            <Radio
                              checked={selectedModelId === model.id}
                              value={model.id}
                              size="small"
                              sx={{ color: 'primary.main' }}
                            />
                          }
                          label={
                            <Box sx={{ py: 0.5 }}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                <Typography variant="body2" sx={{ 
                                  fontWeight: 600,
                                  color: 'text.primary',
                                  fontSize: '0.8125rem'
                                }}>
                                  {model.name}
                                </Typography>
                                <Chip
                                  label={model.latency === 'Low' ? 'Fast' : 'Analytical'}
                                  size="small"
                                  variant="outlined"
                                  sx={{ 
                                    fontSize: '0.6875rem', 
                                    height: 20,
                                    borderColor: model.latency === 'Low' ? 'info.main' : 'warning.main',
                                    color: model.latency === 'Low' ? 'info.main' : 'warning.main',
                                    backgroundColor: 'transparent'
                                  }}
                                />
                              </Box>
                              <Typography variant="caption" sx={{ 
                                color: 'text.secondary',
                                fontSize: '0.6875rem',
                                lineHeight: 1.3
                              }}>
                                {model.description}
                              </Typography>
                            </Box>
                          }
                          sx={{
                            m: 0,
                            p: 1.5,
                            width: '100%',
                            alignItems: 'flex-start',
                            '& .MuiFormControlLabel-label': { flex: 1 }
                          }}
                        />
                      </Box>
                    ))}
                  </RadioGroup>
                )}
              </Box>

              {/* Caption Settings */}
              <Box>
                <Typography variant="subtitle2" sx={{ 
                  fontWeight: 600, 
                  mb: 2, 
                  color: 'text.primary',
                  fontSize: '0.8125rem'
                }}>
                  Caption Settings
                </Typography>

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                  {/* Caption Tone */}
                  <FormControl fullWidth size="small">
                    <InputLabel sx={{ fontSize: '0.875rem' }}>Tone of Voice</InputLabel>
                    <Select
                      value={settings.tone || ''}
                      label="Tone of Voice"
                      onChange={(e) => setSettings(prev => ({ ...prev, tone: e.target.value as string }))}
                      sx={{ 
                        '& .MuiSelect-select': { fontSize: '0.875rem' },
                        '& .MuiOutlinedInput-notchedOutline': { borderColor: 'grey.300' }
                      }}
                    >
                      <MenuItem value="">
                        <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                          Auto (AI decides)
                        </Typography>
                      </MenuItem>
                      {toneOptions.map(option => (
                        <MenuItem key={option.value} value={option.value}>
                          <Typography variant="body2">{option.label}</Typography>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  {/* Call to Action */}
                  <TextField
                    fullWidth
                    size="small"
                    label="Call to Action"
                    placeholder="e.g., Shop Now, Learn More, Link in Bio"
                    value={settings.call_to_action || ''}
                    onChange={(e) => setSettings(prev => ({ ...prev, call_to_action: e.target.value }))}
                    helperText="Leave blank for automatic generation"
                    sx={{ 
                      '& .MuiInputBase-input': { fontSize: '0.875rem' },
                      '& .MuiFormHelperText-root': { fontSize: '0.6875rem' },
                      '& .MuiOutlinedInput-notchedOutline': { borderColor: 'grey.300' }
                    }}
                  />

                  {/* Emojis and Hashtags Row */}
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    {/* Include Emojis Toggle */}
                    <Box sx={{ 
                      flex: 1,
                      border: '1px solid',
                      borderColor: 'grey.300',
                      borderRadius: 1,
                      p: 1.5,
                      backgroundColor: 'white'
                    }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={settings.include_emojis ?? true}
                            onChange={(e) => setSettings(prev => ({ ...prev, include_emojis: e.target.checked }))}
                            color="primary"
                            size="small"
                          />
                        }
                        label={
                          <Typography variant="body2" sx={{ fontSize: '0.875rem', fontWeight: 500 }}>
                            Include Emojis
                          </Typography>
                        }
                        sx={{ 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          ml: 0,
                          width: '100%',
                          '& .MuiFormControlLabel-label': { flex: 1 }
                        }}
                      />
                    </Box>

                    {/* Hashtag Strategy */}
                    <FormControl size="small" sx={{ flex: 1 }}>
                      <InputLabel sx={{ fontSize: '0.875rem' }}>Hashtags</InputLabel>
                      <Select
                        value={settings.hashtag_strategy || ''}
                        label="Hashtags"
                        onChange={(e) => setSettings(prev => ({ ...prev, hashtag_strategy: e.target.value as string }))}
                        sx={{ 
                          '& .MuiSelect-select': { fontSize: '0.875rem' },
                          '& .MuiOutlinedInput-notchedOutline': { borderColor: 'grey.300' }
                        }}
                      >
                        <MenuItem value="">
                          <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                            Auto (Balanced)
                          </Typography>
                        </MenuItem>
                        {hashtagOptions.map(option => (
                          <MenuItem key={option.value} value={option.value}>
                            <Typography variant="body2">{option.label}</Typography>
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </Box>
              </Box>
            </Box>
          </AccordionDetails>
        </Accordion>
      </DialogContent>

      <DialogActions sx={{ 
        px: 3, 
        py: 2.5, 
        borderTop: '1px solid', 
        borderColor: 'grey.200',
        backgroundColor: 'grey.25',
        gap: 1.5
      }}>
        <Button 
          onClick={handleClose} 
          disabled={isGenerating}
          variant="outlined"
          sx={{ 
            textTransform: 'none',
            fontWeight: 500,
            borderColor: 'grey.300',
            color: 'text.primary',
            '&:hover': {
              borderColor: 'grey.400',
              backgroundColor: 'grey.50'
            }
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={handleGenerate}
          variant="contained"
          disabled={isGenerating}
          sx={{ 
            textTransform: 'none',
            fontWeight: 600,
            px: 3,
            boxShadow: 1,
            '&:hover': {
              boxShadow: 2
            }
          }}
        >
          {isGenerating ? 'Generating...' : (initialSettings ? 'Regenerate Caption' : 'Generate Caption')}
        </Button>
      </DialogActions>
    </Dialog>
  );
} 