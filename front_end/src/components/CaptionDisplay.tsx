'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Menu,
  MenuItem,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  ContentCopy as ContentCopyIcon,
  MoreVert as MoreVertIcon,
  AutoAwesome as AutoAwesomeIcon,
  Tune as TuneIcon,
  AttachMoney as CostIcon,
  Speed as SpeedIcon,
  InfoOutlined as InfoIcon,
} from '@mui/icons-material';
import { CaptionResult, CaptionSettings } from '@/types/api';
import toast from 'react-hot-toast';

interface CaptionDisplayProps {
  captions: CaptionResult[];
  onRegenerate: (settings?: CaptionSettings, modelId?: string) => void;
  onOpenSettingsDialog: (currentSettings: CaptionSettings, currentModelId?: string) => void;
  isRegenerating?: boolean;
}

export default function CaptionDisplay({
  captions,
  onRegenerate,
  onOpenSettingsDialog,
  isRegenerating = false,
}: CaptionDisplayProps) {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [currentVersionIndex, setCurrentVersionIndex] = useState(0);
  const [showFullTone, setShowFullTone] = useState(false);
  const menuOpen = Boolean(anchorEl);
  
  // Sort captions by version (newest first) and get current caption
  const sortedCaptions = [...captions].sort((a, b) => b.version - a.version);
  const currentCaption = sortedCaptions[currentVersionIndex] || sortedCaptions[0];

  // Reset to newest version when captions array changes (new version added)
  useEffect(() => {
    setCurrentVersionIndex(0);
    setShowFullTone(false);
  }, [captions]);

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleCopyCaption = async () => {
    try {
      await navigator.clipboard.writeText(currentCaption.text);
      toast.success('Caption copied to clipboard!');
    } catch (error) {
      toast.error('Failed to copy caption');
    }
  };

  const handleQuickRegenerate = () => {
    handleMenuClose();
    onRegenerate(undefined, currentCaption.model_id); // Writer-only regeneration with same settings and model
  };

  const handleRegenerateWithNewSettings = () => {
    handleMenuClose();
    // Open the settings dialog with current settings pre-populated
    onOpenSettingsDialog(currentCaption.settings_used, currentCaption.model_id);
  };

  const formatSettingsDisplay = (settings: CaptionSettings, excludeTone = false) => {
    const parts = [];
    if (settings.hashtag_strategy) parts.push(`${settings.hashtag_strategy} hashtags`);
    else parts.push('Auto hashtags');
    if (settings.include_emojis === false) parts.push('No emojis');
    else parts.push('With emojis');
    if (settings.call_to_action) parts.push('Custom CTA');
    else parts.push('Auto CTA');
    return parts.length > 0 ? parts.join(' • ') : 'Auto settings';
  };

  const detectModes = (caption: CaptionResult) => {
    // Use tracked mode values from settings if available, otherwise fall back to inference
    const generationMode = caption.settings_used.generation_mode || 
      (caption.settings_used.hashtag_strategy && caption.settings_used.hashtag_strategy !== 'Balanced Mix') ||
      caption.settings_used.include_emojis === false ||
      (caption.settings_used.call_to_action && !caption.settings_used.call_to_action.includes('Tag a friend'))
      ? 'Custom' : 'Auto';
    
    // Use tracked processing mode or infer from model ID
    let processingMode = caption.settings_used.processing_mode;
    
    if (!processingMode) {
      // Fallback inference from model ID if not tracked
      const modelId = caption.usage_summary?.model_id || caption.model_id || '';
      const fastModelPatterns = ['gpt-3.5', 'gpt-35', 'gemini-1.5-flash', 'gemini-flash', 'claude-3-haiku', 'claude-haiku'];
      const isFastModel = fastModelPatterns.some(pattern => modelId.toLowerCase().includes(pattern));
      processingMode = isFastModel ? 'Fast' : 'Analytical';
    }

    return { generationMode, processingMode };
  };

  const renderModeChips = (generationMode: string, processingMode: string) => {
    return (
      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
        <Tooltip title={generationMode === 'Auto' ? 'Settings were automatically determined by the AI' : 'Settings were manually specified by the user'}>
          <Chip 
            label={`${generationMode} Settings`}
            size="small"
            variant="outlined"
            sx={{ 
              height: 22,
              fontSize: '0.6875rem',
              fontWeight: 500,
              borderColor: generationMode === 'Auto' ? 'success.main' : 'primary.main',
              color: generationMode === 'Auto' ? 'success.main' : 'primary.main',
              backgroundColor: 'transparent',
              '& .MuiChip-label': { px: 1 },
              transition: 'all 0.2s ease-in-out',
              '&:hover': {
                backgroundColor: generationMode === 'Auto' ? 'success.50' : 'primary.50',
              }
            }}
          />
        </Tooltip>
        <Tooltip title={processingMode === 'Fast' ? 'Speed-optimized processing for quick results' : 'Advanced model with enhanced capabilities for complex tasks'}>
          <Chip 
            label={`${processingMode}`}
            size="small"
            variant="outlined"
            sx={{ 
              height: 22,
              fontSize: '0.6875rem',
              fontWeight: 500,
              borderColor: processingMode === 'Fast' ? 'info.main' : 'warning.main',
              color: processingMode === 'Fast' ? 'info.main' : 'warning.main',
              backgroundColor: 'transparent',
              '& .MuiChip-label': { px: 1 },
              transition: 'all 0.2s ease-in-out',
              '&:hover': {
                backgroundColor: processingMode === 'Fast' ? 'info.50' : 'warning.50',
              }
            }}
          />
        </Tooltip>
      </Box>
    );
  };

  const renderToneDisplay = (tone: string) => {
    const wordLimit = 8;
    const words = tone.split(' ');
    
    if (words.length <= wordLimit || showFullTone) {
      return (
        <Box component="span">
          <Typography variant="caption" component="span" sx={{ color: 'text.secondary', fontWeight: 400, lineHeight: 1.4 }}>
            {tone}
          </Typography>
          {words.length > wordLimit && (
            <Button 
              size="small" 
              onClick={() => setShowFullTone(false)} 
              sx={{ 
                textTransform: 'none', 
                p: 0, 
                ml: 0.5, 
                minWidth: 'auto',
                fontSize: '0.6875rem',
                fontWeight: 400,
                color: 'primary.main',
                transition: 'color 0.2s ease-in-out',
                '&:hover': { 
                  backgroundColor: 'transparent', 
                  color: 'primary.dark',
                  textDecoration: 'underline' 
                }
              }}
            >
              (show less)
            </Button>
          )}
        </Box>
      );
    }

    const truncatedTone = words.slice(0, wordLimit).join(' ');
    return (
      <Box component="span">
        <Typography variant="caption" component="span" sx={{ color: 'text.secondary', fontWeight: 400, lineHeight: 1.4 }}>
          {truncatedTone}...
        </Typography>
        <Button 
          size="small" 
          onClick={() => setShowFullTone(true)} 
          sx={{ 
            textTransform: 'none', 
            p: 0, 
            ml: 0.5, 
            minWidth: 'auto',
            fontSize: '0.6875rem',
            fontWeight: 400,
            color: 'primary.main',
            transition: 'color 0.2s ease-in-out',
            '&:hover': { 
              backgroundColor: 'transparent', 
              color: 'primary.dark',
              textDecoration: 'underline' 
            }
          }}
        >
          (show more)
        </Button>
      </Box>
    );
  };

  const { generationMode, processingMode } = detectModes(currentCaption);

  return (
    <Paper 
      sx={{ 
        p: 2, 
        mt: 2, 
        backgroundColor: 'grey.50', 
        border: 1, 
        borderColor: 'divider',
        borderRadius: 2 
      }}
    >
      {/* Action Buttons */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            startIcon={<ContentCopyIcon />}
            onClick={handleCopyCaption}
            sx={{ 
              textTransform: 'none',
              fontWeight: 500,
              borderColor: 'grey.300',
              color: 'text.primary',
              '&:hover': {
                borderColor: 'primary.main',
                backgroundColor: 'primary.50'
              }
            }}
          >
            Copy
          </Button>
          
          <Button
            variant="contained"
            size="small"
            startIcon={isRegenerating ? <AutoAwesomeIcon className="animate-spin" /> : <RefreshIcon />}
            onClick={handleMenuClick}
            disabled={isRegenerating}
            sx={{ 
              textTransform: 'none',
              fontWeight: 500,
              boxShadow: 1,
              '&:hover': {
                boxShadow: 2
              }
            }}
          >
            {isRegenerating ? 'Generating...' : 'Regenerate'}
          </Button>
        </Box>

        {/* Version Navigation */}
        {sortedCaptions.length > 1 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
              v{currentCaption.version}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <IconButton
                size="small"
                onClick={() => setCurrentVersionIndex(Math.min(currentVersionIndex + 1, sortedCaptions.length - 1))}
                disabled={currentVersionIndex >= sortedCaptions.length - 1}
                sx={{ 
                  fontSize: '0.75rem',
                  color: 'text.secondary',
                  '&:hover': { backgroundColor: 'grey.100' },
                  '&:disabled': { color: 'grey.300' }
                }}
              >
                ←
              </IconButton>
              <IconButton
                size="small"
                onClick={() => setCurrentVersionIndex(Math.max(currentVersionIndex - 1, 0))}
                disabled={currentVersionIndex <= 0}
                sx={{ 
                  fontSize: '0.75rem',
                  color: 'text.secondary',
                  '&:hover': { backgroundColor: 'grey.100' },
                  '&:disabled': { color: 'grey.300' }
                }}
              >
                →
              </IconButton>
            </Box>
          </Box>
        )}
      </Box>

      {/* Caption Text */}
      <Typography 
        variant="body2" 
        sx={{ 
          mb: 2, 
          lineHeight: 1.6,
          whiteSpace: 'pre-wrap',
          backgroundColor: 'white',
          p: 2,
          borderRadius: 1,
          border: 1,
          borderColor: 'grey.200'
        }}
      >
        {currentCaption.text}
      </Typography>

      {/* Usage Summary - Minimal Professional Display */}
      {currentCaption.usage_summary && 
       currentCaption.usage_summary.total_cost_usd !== undefined && 
       currentCaption.usage_summary.total_latency_seconds !== undefined && (
        <Box sx={{ mb: 2 }}>
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            px: 2,
            py: 1,
            backgroundColor: 'grey.25',
            borderRadius: 1,
            border: '1px solid',
            borderColor: 'grey.100'
          }}>
            {/* Cost */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                Cost:
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'success.main' }}>
                ${(currentCaption.usage_summary.total_cost_usd || 0).toFixed(4)}
              </Typography>
            </Box>

            {/* Speed */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                Time:
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 600, color: 'info.main' }}>
                {((currentCaption.usage_summary.total_latency_seconds || 0)).toFixed(1)}s
              </Typography>
            </Box>
          </Box>
        </Box>
      )}

      {/* Settings Used - Professional Layout */}
      <Box sx={{ mt: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Typography variant="body2" sx={{ 
            fontWeight: 600, 
            color: 'text.primary',
            fontSize: '0.8125rem',
            letterSpacing: 0.25
          }}>
            Generation Details
          </Typography>
          {renderModeChips(generationMode, processingMode)}
        </Box>
        
        <Box sx={{ 
          pl: 0,
          py: 1.5,
          px: 2,
          backgroundColor: 'grey.25',
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'grey.100'
        }}>
          {/* Tone Display */}
          {currentCaption.settings_used.tone && (
            <Box sx={{ mb: 1 }}>
              <Typography variant="caption" component="span" sx={{ 
                fontWeight: 600, 
                color: 'text.primary', 
                mr: 1.5,
                fontSize: '0.6875rem',
                textTransform: 'uppercase', 
                letterSpacing: 0.5
              }}>
                Tone:
              </Typography>
              {renderToneDisplay(currentCaption.settings_used.tone)}
            </Box>
          )}
          
          {/* Other Settings */}
          <Box>
            <Typography variant="caption" component="span" sx={{ 
              fontWeight: 600, 
              color: 'text.primary', 
              mr: 1.5,
              fontSize: '0.6875rem',
              textTransform: 'uppercase', 
              letterSpacing: 0.5
            }}>
              Options:
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 400, lineHeight: 1.4 }}>
              {formatSettingsDisplay(currentCaption.settings_used, true)}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', mt: 1.5 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 400 }}>
          Generated {new Date(currentCaption.created_at).toLocaleString()}
        </Typography>
      </Box>

      {/* Regenerate Menu */}
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={handleMenuClose}
        PaperProps={{
          sx: { 
            minWidth: 280,
            boxShadow: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'grey.200'
          }
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem 
          onClick={handleQuickRegenerate} 
          disabled={isRegenerating}
          sx={{ 
            py: 1.5,
            '&:hover': { backgroundColor: 'grey.50' }
          }}
        >
          <RefreshIcon fontSize="small" sx={{ mr: 1.5, color: 'primary.main' }} />
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.25 }}>
              Quick Regenerate
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.3 }}>
              New creative variation with same settings
            </Typography>
          </Box>
        </MenuItem>
        
        <Divider sx={{ my: 0.5 }} />
        
        <MenuItem 
          onClick={handleRegenerateWithNewSettings} 
          disabled={isRegenerating}
          sx={{ 
            py: 1.5,
            '&:hover': { backgroundColor: 'grey.50' }
          }}
        >
          <TuneIcon fontSize="small" sx={{ mr: 1.5, color: 'primary.main' }} />
          <Box>
            <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.25 }}>
              Regenerate with New Settings
            </Typography>
            <Typography variant="caption" sx={{ color: 'text.secondary', lineHeight: 1.3 }}>
              Adjust tone, style, or other preferences
            </Typography>
          </Box>
        </MenuItem>
      </Menu>
    </Paper>
  );
} 