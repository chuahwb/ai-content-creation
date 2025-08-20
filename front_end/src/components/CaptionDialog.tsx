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
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  AutoAwesome as AutoAwesomeIcon,
  Tune as TuneIcon,
  Speed as SpeedIcon,
  Psychology as PsychologyIcon,
  Visibility as VisibilityIcon,
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
    caption_length: 'Auto', // Default to Auto for optimal experience
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
      setSettings({ 
        include_emojis: true,
        caption_length: 'Auto'
      });
      setAdvancedOpen(false);
    }
    
    if (initialModelId && open) {
      setSelectedModelId(initialModelId);
    }
  }, [initialSettings, initialModelId, open]);

  const handleGenerate = () => {
    // Set generation_mode based on whether advanced options are used
    const finalSettings = advancedOpen ? {
      ...settings,
      generation_mode: 'Custom' as const
    } : {
      generation_mode: 'Auto' as const
    };
    onGenerate(finalSettings, selectedModelId);
  };

  const handleClose = () => {
    if (!isGenerating) {
      onClose();
      // Reset state
      setAdvancedOpen(false);
      setSettings({ 
        include_emojis: true,
        caption_length: 'Auto'
      });
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
            Analyzes your image, marketing strategy, and visual style to create optimized captions automatically. 
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

                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {/* User Instructions */}
                  <Box>
                    <Typography variant="subtitle2" sx={{ 
                      fontWeight: 600, 
                      mb: 1, 
                      color: 'text.primary',
                      fontSize: '0.8125rem'
                    }}>
                      Custom Instructions
                    </Typography>
                    <TextField
                      fullWidth
                      size="small"
                      multiline
                      rows={3}
                      label=""
                      placeholder="e.g., 'Focus on sustainability and eco-friendly benefits', 'Tell a story about the craftsmanship', 'Emphasize the limited-time nature of this offer'"
                      value={settings.user_instructions || ''}
                      onChange={(e) => setSettings(prev => ({ ...prev, user_instructions: e.target.value }))}
                      helperText="Specify the core message, themes, or key points you want emphasized"
                      sx={{ 
                        '& .MuiInputBase-input': { fontSize: '0.875rem' },
                        '& .MuiFormHelperText-root': { fontSize: '0.6875rem' },
                        '& .MuiOutlinedInput-notchedOutline': { borderColor: 'grey.300' },
                        '& .MuiOutlinedInput-root': {
                          '&:hover .MuiOutlinedInput-notchedOutline': {
                            borderColor: 'primary.main',
                          },
                          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                            borderColor: 'primary.main',
                            borderWidth: 2,
                          }
                        }
                      }}
                    />
                  </Box>

                  {/* Caption Length - Ultra Compact */}
                  <Box>
                    <Typography variant="subtitle2" sx={{ 
                      fontWeight: 600, 
                      mb: 1, 
                      color: 'text.primary',
                      fontSize: '0.8125rem'
                    }}>
                      Caption Length
                    </Typography>
                    <RadioGroup
                      value={settings.caption_length || 'Auto'}
                      onChange={(e) => setSettings(prev => ({ ...prev, caption_length: e.target.value as 'Auto' | 'Short' | 'Medium' | 'Long' }))}
                      sx={{ gap: 0.5 }}
                    >
                      {[
                        { 
                          value: 'Auto', 
                          label: 'Auto', 
                          description: 'Optimal length chosen based on content and platform',
                          lines: 3,
                          isRecommended: true
                        },
                        { 
                          value: 'Short', 
                          label: 'Short', 
                          description: 'Punchy hooks under 125 characters - instant attention grabbers',
                          lines: 1
                        },
                        { 
                          value: 'Medium', 
                          label: 'Medium', 
                          description: 'Balanced storytelling 125-500 characters - context with engagement',
                          lines: 5
                        },
                        { 
                          value: 'Long', 
                          label: 'Long', 
                          description: 'In-depth content 500+ characters - detailed storytelling and education',
                          lines: 8
                        }
                      ].map((option) => (
                        <Box
                          key={option.value}
                          sx={{
                            border: '1px solid',
                            borderColor: settings.caption_length === option.value ? 'primary.main' : 'grey.200',
                            borderRadius: 1,
                            backgroundColor: settings.caption_length === option.value ? 'primary.25' : 'white',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease-in-out',
                            '&:hover': {
                              borderColor: 'primary.main',
                              backgroundColor: settings.caption_length === option.value ? 'primary.50' : 'primary.25',
                            }
                          }}
                          onClick={() => setSettings(prev => ({ ...prev, caption_length: option.value as 'Auto' | 'Short' | 'Medium' | 'Long' }))}
                        >
                          <FormControlLabel
                            control={
                              <Radio
                                checked={settings.caption_length === option.value}
                                value={option.value}
                                size="small"
                                sx={{ color: 'primary.main' }}
                              />
                            }
                            label={
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                                <Typography variant="body2" sx={{ 
                                  fontWeight: 600,
                                  color: 'text.primary',
                                  fontSize: '0.8125rem'
                                }}>
                                  {option.label}
                                </Typography>
                                {option.isRecommended && (
                                  <Chip
                                    label="Best"
                                    size="small"
                                    variant="outlined"
                                    sx={{ 
                                      fontSize: '0.6875rem', 
                                      height: 16,
                                      borderColor: 'success.main',
                                      color: 'success.main',
                                      backgroundColor: 'transparent'
                                    }}
                                  />
                                )}
                                {/* Visual Length Indicator */}
                                <Box sx={{ display: 'flex', gap: 0.5, ml: 1 }}>
                                  {option.value === 'Auto' ? (
                                    // Auto - Dynamic representation with gradient dots
                                    <>
                                      <Box
                                        sx={{
                                          width: 3,
                                          height: 3,
                                          borderRadius: '50%',
                                          background: settings.caption_length === option.value 
                                            ? 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)'
                                            : 'linear-gradient(45deg, #bbb 30%, #ddd 90%)'
                                        }}
                                      />
                                      <Box
                                        sx={{
                                          width: 4,
                                          height: 4,
                                          borderRadius: '50%',
                                          background: settings.caption_length === option.value 
                                            ? 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)'
                                            : 'linear-gradient(45deg, #bbb 30%, #ddd 90%)'
                                        }}
                                      />
                                      <Box
                                        sx={{
                                          width: 3,
                                          height: 3,
                                          borderRadius: '50%',
                                          background: settings.caption_length === option.value 
                                            ? 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)'
                                            : 'linear-gradient(45deg, #bbb 30%, #ddd 90%)'
                                        }}
                                      />
                                    </>
                                  ) : (
                                    // Fixed lengths - Regular dots
                                    Array.from({ length: option.value === 'Short' ? 1 : option.value === 'Medium' ? 3 : 5 }).map((_, i) => (
                                      <Box
                                        key={i}
                                        sx={{
                                          width: 3,
                                          height: 3,
                                          borderRadius: '50%',
                                          backgroundColor: settings.caption_length === option.value ? 'primary.main' : 'grey.300'
                                        }}
                                      />
                                    ))
                                  )}
                                </Box>
                                {/* Preview Icon */}
                                <Tooltip
                                  title={
                                    /* Tooltip - Visual Preview Only */
                                    <Box sx={{ 
                                      backgroundColor: 'white', 
                                      borderRadius: 2, 
                                      p: 1.5,
                                      boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
                                      minWidth: 200,
                                      maxWidth: 250
                                    }}>
                                      {/* Mock Image Placeholder */}
                                      <Box sx={{ 
                                        width: '100%', 
                                        height: 50, 
                                        backgroundColor: 'grey.100', 
                                        borderRadius: 1, 
                                        mb: 1,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                      }}>
                                        <Typography variant="caption" sx={{ color: 'grey.400', fontSize: '0.6875rem' }}>
                                          Your Image
                                        </Typography>
                                      </Box>

                                      {/* Mock Social Media Post Header */}
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                        <Box sx={{ 
                                          width: 18, 
                                          height: 18, 
                                          borderRadius: '50%', 
                                          backgroundColor: 'primary.main',
                                          display: 'flex',
                                          alignItems: 'center',
                                          justifyContent: 'center'
                                        }}>
                                          <Typography sx={{ color: 'white', fontSize: '0.625rem', fontWeight: 600 }}>
                                            B
                                          </Typography>
                                        </Box>
                                        <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.625rem', color: 'text.primary' }}>
                                          Your Brand
                                        </Typography>
                                      </Box>

                                      {/* Mock Caption Lines - Aligned with Expected Lengths */}
                                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                        {option.value === 'Short' && (
                                          // Short: Under 125 characters - Single punchy line
                                          <Box
                                            sx={{
                                              height: 8,
                                              width: '60%',
                                              backgroundColor: '#1976d2',
                                              borderRadius: 1
                                            }}
                                          />
                                        )}
                                        {option.value === 'Auto' && (
                                          // Auto: Dynamic, adaptive representation
                                          <Box sx={{ position: 'relative', overflow: 'hidden' }}>
                                            {/* Dynamic Lines with Gradient and Animation Effect */}
                                            <Box 
                                              sx={{ 
                                                height: 8, 
                                                width: '90%', 
                                                background: 'linear-gradient(90deg, #1976d2 0%, #42a5f5 50%, #1976d2 100%)',
                                                borderRadius: 1,
                                                position: 'relative',
                                                '&::after': {
                                                  content: '""',
                                                  position: 'absolute',
                                                  top: 0,
                                                  left: 0,
                                                  right: 0,
                                                  bottom: 0,
                                                  background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                                                  borderRadius: 1,
                                                  animation: 'shimmer 2s ease-in-out infinite',
                                                  overflow: 'hidden'
                                                }
                                              }} 
                                            />
                                            <Box 
                                              sx={{ 
                                                height: 8, 
                                                width: '75%', 
                                                background: 'linear-gradient(90deg, #1976d2 0%, #42a5f5 100%)',
                                                borderRadius: 1,
                                                mt: 1,
                                                opacity: 0.9
                                              }} 
                                            />
                                            <Box 
                                              sx={{ 
                                                height: 6, 
                                                width: '40%', 
                                                background: 'linear-gradient(90deg, #42a5f5 0%, #1976d2 100%)',
                                                borderRadius: 1,
                                                mt: 1,
                                                opacity: 0.8
                                              }} 
                                            />
                                            
                                            {/* Smart indicator - small animated dot */}
                                            <Box
                                              sx={{
                                                position: 'absolute',
                                                top: -2,
                                                right: -8,
                                                width: 6,
                                                height: 6,
                                                borderRadius: '50%',
                                                background: 'linear-gradient(45deg, #4caf50 0%, #81c784 100%)',
                                                boxShadow: '0 0 8px rgba(76, 175, 80, 0.4)',
                                                animation: 'pulse 1.5s ease-in-out infinite'
                                              }}
                                            />
                                            
                                            {/* Add CSS keyframes for animations */}
                                            <style jsx>{`
                                              @keyframes shimmer {
                                                0% { transform: translateX(-100%); }
                                                100% { transform: translateX(300%); }
                                              }
                                              @keyframes pulse {
                                                0%, 100% { 
                                                  opacity: 0.6; 
                                                  transform: scale(0.8);
                                                }
                                                50% { 
                                                  opacity: 1; 
                                                  transform: scale(1.2);
                                                }
                                              }
                                            `}</style>
                                          </Box>
                                        )}
                                        {option.value === 'Medium' && (
                                          // Medium: 3-5 sentences (125-500 characters)
                                          <>
                                            <Box sx={{ height: 8, width: '98%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '95%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '88%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '92%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '65%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                          </>
                                        )}
                                        {option.value === 'Long' && (
                                          // Long: 500+ characters - Detailed storytelling (6-8 lines)
                                          <>
                                            <Box sx={{ height: 8, width: '98%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '96%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '94%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '97%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '91%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '89%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '85%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                            <Box sx={{ height: 8, width: '58%', backgroundColor: '#1976d2', borderRadius: 1 }} />
                                          </>
                                        )}
                                      </Box>
                                    </Box>
                                  }
                                  placement="right"
                                  arrow
                                  enterDelay={100}
                                  leaveDelay={100}
                                  PopperProps={{
                                    sx: {
                                      '& .MuiTooltip-tooltip': {
                                        backgroundColor: 'transparent',
                                        maxWidth: 'none',
                                        p: 0,
                                        boxShadow: 'none'
                                      },
                                      '& .MuiTooltip-arrow': {
                                        color: 'white'
                                      }
                                    }
                                  }}
                                >
                                  <IconButton
                                    size="small"
                                    sx={{ 
                                      ml: 'auto',
                                      p: 0.5,
                                      color: 'grey.400',
                                      '&:hover': {
                                        color: 'primary.main',
                                        backgroundColor: 'primary.50'
                                      }
                                    }}
                                    onClick={(e) => e.stopPropagation()} // Prevent radio selection when clicking preview
                                  >
                                    <VisibilityIcon sx={{ fontSize: '1rem' }} />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            }
                            sx={{
                              m: 0,
                              p: 1,
                              width: '100%',
                              alignItems: 'center',
                              '& .MuiFormControlLabel-label': { flex: 1 }
                            }}
                          />
                          {/* Description as subtitle */}
                          <Typography variant="caption" sx={{ 
                            color: 'text.secondary',
                            fontSize: '0.6875rem',
                            px: 1,
                            pb: 1,
                            display: 'block',
                            lineHeight: 1.2
                          }}>
                            {option.description}
                          </Typography>
                        </Box>
                      ))}
                    </RadioGroup>
                  </Box>

                                    {/* Style & Format - Enhanced */}
                  <Box>
                    <Typography variant="subtitle2" sx={{ 
                      fontWeight: 600, 
                      mb: 1, 
                      color: 'text.primary',
                      fontSize: '0.8125rem'
                    }}>
                      Style & Format
                    </Typography>
                    
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {/* Tone of Voice - Compact */}
                      <Box sx={{
                        border: '1px solid',
                        borderColor: 'grey.200',
                        borderRadius: 1,
                        backgroundColor: 'white',
                        p: 1
                      }}>
                        <FormControl fullWidth size="small" variant="standard">
                          <InputLabel sx={{ fontSize: '0.75rem', color: 'text.secondary', position: 'relative', transform: 'none', mb: 0.5 }}>
                            Tone of Voice
                          </InputLabel>
                          <Select
                            value={settings.tone || ''}
                            onChange={(e) => setSettings(prev => ({ ...prev, tone: e.target.value as string }))}
                            disableUnderline
                            displayEmpty
                            renderValue={(selected) => {
                              if (!selected) {
                                return (
                                  <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary', fontSize: '0.8125rem' }}>
                                    Auto (System decides)
                                  </Typography>
                                );
                              }
                              const option = toneOptions.find(opt => opt.value === selected);
                              return (
                                <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                                  {option?.label || selected}
                                </Typography>
                              );
                            }}
                            sx={{ 
                              '& .MuiSelect-select': { 
                                fontSize: '0.8125rem',
                                fontWeight: 500,
                                pt: 0.5,
                                pb: 0
                              }
                            }}
                          >
                            <MenuItem value="">
                              <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary', fontSize: '0.8125rem' }}>
                                Auto (System decides)
                              </Typography>
                            </MenuItem>
                            {toneOptions.map(option => (
                              <MenuItem key={option.value} value={option.value}>
                                <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>{option.label}</Typography>
                              </MenuItem>
                            ))}
                          </Select>
                        </FormControl>
                      </Box>

                      {/* Call to Action - Compact */}
                      <Box sx={{
                        border: '1px solid',
                        borderColor: 'grey.200',
                        borderRadius: 1,
                        backgroundColor: 'white',
                        p: 1
                      }}>
                        <Typography variant="caption" sx={{ 
                          fontSize: '0.75rem', 
                          color: 'text.secondary',
                          display: 'block',
                          mb: 0.5
                        }}>
                          Call to Action
                        </Typography>
                        <TextField
                          fullWidth
                          size="small"
                          variant="standard"
                          placeholder="e.g., Shop Now, Learn More, Link in Bio"
                          value={settings.call_to_action || ''}
                          onChange={(e) => setSettings(prev => ({ ...prev, call_to_action: e.target.value }))}
                          InputProps={{
                            disableUnderline: true,
                            sx: { 
                              fontSize: '0.8125rem',
                              fontWeight: 500
                            }
                          }}
                        />
                        <Typography variant="caption" sx={{ 
                          fontSize: '0.6875rem', 
                          color: 'text.secondary',
                          display: 'block',
                          mt: 0.5
                        }}>
                          Leave blank for automatic generation
                        </Typography>
                      </Box>

                      {/* Emojis and Hashtags - Compact Row */}
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        {/* Include Emojis Toggle - Compact */}
                        <Box sx={{ 
                          flex: 1,
                          border: '1px solid',
                          borderColor: 'grey.200',
                          borderRadius: 1,
                          p: 1,
                          backgroundColor: 'white',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between'
                        }}>
                          <Typography variant="body2" sx={{ fontSize: '0.8125rem', fontWeight: 500 }}>
                            Include Emojis
                          </Typography>
                          <Switch
                            checked={settings.include_emojis ?? true}
                            onChange={(e) => setSettings(prev => ({ ...prev, include_emojis: e.target.checked }))}
                            color="primary"
                            size="small"
                          />
                        </Box>

                        {/* Hashtag Strategy - Compact */}
                        <Box sx={{
                          flex: 1,
                          border: '1px solid',
                          borderColor: 'grey.200',
                          borderRadius: 1,
                          backgroundColor: 'white',
                          p: 1
                        }}>
                          <FormControl fullWidth size="small" variant="standard">
                            <InputLabel sx={{ fontSize: '0.75rem', color: 'text.secondary', position: 'relative', transform: 'none', mb: 0.5 }}>
                              Hashtags
                            </InputLabel>
                            <Select
                              value={settings.hashtag_strategy || ''}
                              onChange={(e) => setSettings(prev => ({ ...prev, hashtag_strategy: e.target.value as string }))}
                              disableUnderline
                              displayEmpty
                              renderValue={(selected) => {
                                if (!selected) {
                                  return (
                                    <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary', fontSize: '0.8125rem' }}>
                                      Auto (Balanced)
                                    </Typography>
                                  );
                                }
                                const option = hashtagOptions.find(opt => opt.value === selected);
                                return (
                                  <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>
                                    {option?.label || selected}
                                  </Typography>
                                );
                              }}
                              sx={{ 
                                '& .MuiSelect-select': { 
                                  fontSize: '0.8125rem',
                                  fontWeight: 500,
                                  pt: 0.5,
                                  pb: 0
                                }
                              }}
                            >
                              <MenuItem value="">
                                <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary', fontSize: '0.8125rem' }}>
                                  Auto (Balanced)
                                </Typography>
                              </MenuItem>
                              {hashtagOptions.map(option => (
                                <MenuItem key={option.value} value={option.value}>
                                  <Typography variant="body2" sx={{ fontSize: '0.8125rem' }}>{option.label}</Typography>
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </Box>
                      </Box>
                    </Box>
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