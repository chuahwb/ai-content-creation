'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  IconButton,
  Typography,
  Box,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  Save as SaveIcon,
  Palette as PaletteIcon,
} from '@mui/icons-material';
import { BrandColor } from '../types/api';
import EnhancedColorPaletteEditor from './EnhancedColorPaletteEditor';
import toast from 'react-hot-toast';

interface ColorPaletteModalProps {
  open: boolean;
  onClose: () => void;
  colors: BrandColor[];
  onChange: (colors: BrandColor[]) => void;
  maxColors?: number;
  logoFile?: File | null;
  title?: string;
}

export default function ColorPaletteModal({
  open,
  onClose,
  colors,
  onChange,
  maxColors = 7,
  logoFile = null,
  title = 'Brand Color Palette',
}: ColorPaletteModalProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [localColors, setLocalColors] = useState<BrandColor[]>(colors);
  const [hasChanges, setHasChanges] = useState(false);

  // Sync with external changes when modal opens
  useEffect(() => {
    if (open) {
      setLocalColors(colors);
      setHasChanges(false);
    }
  }, [open, colors]);

  // Track changes
  useEffect(() => {
    const hasChangesNow = JSON.stringify(localColors) !== JSON.stringify(colors);
    setHasChanges(hasChangesNow);
  }, [localColors, colors]);

  const handleLocalChange = (newColors: BrandColor[]) => {
    setLocalColors(newColors);
  };

  const handleSave = () => {
    onChange(localColors);
    setHasChanges(false);
    toast.success('Colors updated successfully!', {
      icon: '🎨',
      duration: 2000,
    });
    onClose();
  };

  const handleCancel = () => {
    if (hasChanges) {
      if (window.confirm('You have unsaved changes. Are you sure you want to cancel?')) {
        setLocalColors(colors); // Reset to original
        setHasChanges(false);
        onClose();
      }
    } else {
      onClose();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      handleCancel();
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 's') {
      event.preventDefault();
      event.stopPropagation();
      if (hasChanges) {
        handleSave();
      }
    }
  };

  return (
    <Dialog
      open={open}
      onClose={(event, reason) => {
        // Prevent closing via backdrop/escape when there are unsaved changes
        if (reason === 'backdropClick' || reason === 'escapeKeyDown') {
          if (hasChanges) {
            return; // Block the close
          }
        }
        handleCancel();
      }}
      maxWidth="md"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: {
          maxHeight: isMobile ? '100vh' : '90vh',
          height: isMobile ? '100vh' : 'auto',
        },
      }}
      onKeyDown={handleKeyDown}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PaletteIcon sx={{ color: 'primary.main' }} />
            <Typography variant="h6">{title}</Typography>
            {hasChanges && (
              <Typography
                variant="caption"
                sx={{
                  backgroundColor: 'warning.light',
                  color: 'warning.contrastText',
                  px: 1,
                  py: 0.25,
                  borderRadius: 1,
                  fontWeight: 'medium',
                }}
              >
                Unsaved
              </Typography>
            )}
          </Box>
          <IconButton onClick={handleCancel} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent
        sx={{
          p: 0,
          '&.MuiDialogContent-root': {
            paddingTop: 0,
          },
        }}
      >
        <Box sx={{ p: 2, height: '100%' }}>
          <EnhancedColorPaletteEditor
            colors={localColors}
            onChange={handleLocalChange}
            maxColors={maxColors}
            showLabels={true}
            logoFile={logoFile}
          />
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2, borderTop: 1, borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            {localColors.length} color{localColors.length !== 1 ? 's' : ''} configured
            {hasChanges && ' • Press Ctrl/Cmd + S to save'}
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              onClick={handleCancel}
              variant="outlined"
              size="small"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              variant="contained"
              startIcon={<SaveIcon />}
              disabled={!hasChanges}
              size="small"
            >
              Save Changes
            </Button>
          </Box>
        </Box>
      </DialogActions>
    </Dialog>
  );
}