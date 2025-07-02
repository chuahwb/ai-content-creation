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
  const menuOpen = Boolean(anchorEl);
  
  // Sort captions by version (newest first) and get current caption
  const sortedCaptions = [...captions].sort((a, b) => b.version - a.version);
  const currentCaption = sortedCaptions[currentVersionIndex] || sortedCaptions[0];

  // Reset to newest version when captions array changes (new version added)
  useEffect(() => {
    setCurrentVersionIndex(0);
  }, [captions.length]);

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

  const formatSettingsDisplay = (settings: CaptionSettings) => {
    const parts = [];
    if (settings.tone) parts.push(`${settings.tone} tone`);
    if (settings.hashtag_strategy) parts.push(`${settings.hashtag_strategy} hashtags`);
    if (settings.include_emojis === false) parts.push('no emojis');
    if (settings.call_to_action) parts.push('custom CTA');
    return parts.length > 0 ? parts.join(', ') : 'auto settings';
  };

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
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesomeIcon color="primary" fontSize="small" />
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Generated Caption
          </Typography>
          <Chip 
            label={`v${currentCaption.version}`} 
            size="small" 
            color="primary" 
            variant="outlined"
            sx={{ fontSize: '0.7rem' }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title="Copy caption">
            <IconButton size="small" onClick={handleCopyCaption}>
              <ContentCopyIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="Regenerate options">
            <IconButton 
              size="small" 
              onClick={handleMenuClick}
              disabled={isRegenerating}
            >
              <MoreVertIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Version Navigation - only show if multiple versions */}
      {sortedCaptions.length > 1 && (
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          gap: 1, 
          mb: 2,
          p: 1,
          backgroundColor: 'white',
          borderRadius: 1,
          border: 1,
          borderColor: 'grey.200'
        }}>
          <Button
            size="small"
            onClick={() => setCurrentVersionIndex(Math.min(currentVersionIndex + 1, sortedCaptions.length - 1))}
            disabled={currentVersionIndex >= sortedCaptions.length - 1}
            sx={{ minWidth: 'auto', px: 1 }}
          >
            ← Older
          </Button>
          
          <Typography variant="caption" sx={{ 
            fontWeight: 600, 
            color: 'primary.main',
            mx: 2,
            fontSize: '0.75rem'
          }}>
            {currentVersionIndex + 1} of {sortedCaptions.length}
          </Typography>
          
          <Button
            size="small"
            onClick={() => setCurrentVersionIndex(Math.max(currentVersionIndex - 1, 0))}
            disabled={currentVersionIndex <= 0}
            sx={{ minWidth: 'auto', px: 1 }}
          >
            Newer →
          </Button>
        </Box>
      )}

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

      {/* Settings Used */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="caption" color="textSecondary">
          Settings: {formatSettingsDisplay(currentCaption.settings_used)}
        </Typography>
        <Typography variant="caption" color="textSecondary">
          {new Date(currentCaption.created_at).toLocaleString()}
        </Typography>
      </Box>

      {/* Regenerate Menu */}
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={handleMenuClose}
        PaperProps={{
          sx: { minWidth: 200 }
        }}
      >
        <MenuItem onClick={handleQuickRegenerate} disabled={isRegenerating}>
          <RefreshIcon fontSize="small" sx={{ mr: 1 }} />
          <Box>
            <Typography variant="body2">Quick Regenerate</Typography>
            <Typography variant="caption" color="textSecondary">
              New creative take, same settings
            </Typography>
          </Box>
        </MenuItem>
        
        <Divider />
        
        <MenuItem onClick={handleRegenerateWithNewSettings} disabled={isRegenerating}>
          <TuneIcon fontSize="small" sx={{ mr: 1 }} />
          <Box>
            <Typography variant="body2">Regenerate with New Settings</Typography>
            <Typography variant="caption" color="textSecondary">
              Change tone, CTA, or other options
            </Typography>
          </Box>
        </MenuItem>
      </Menu>
    </Paper>
  );
} 