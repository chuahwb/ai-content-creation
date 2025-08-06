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
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  CircularProgress,
  Alert,
  Chip,
  Paper,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  Palette as PaletteIcon,
  Business as BusinessIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { BrandPresetResponse, BrandPresetListResponse } from '@/types/api';
import { PipelineAPI } from '@/lib/api';

interface BrandKitPresetModalProps {
  open: boolean;
  onClose: () => void;
  onPresetSelected: (preset: BrandPresetResponse) => void;
}

export default function BrandKitPresetModal({
  open,
  onClose,
  onPresetSelected,
}: BrandKitPresetModalProps) {
  const [presets, setPresets] = useState<BrandPresetResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load brand kit presets when modal opens
  useEffect(() => {
    if (open) {
      loadBrandKitPresets();
    }
  }, [open]);

  const loadBrandKitPresets = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await PipelineAPI.getBrandPresets();
      // Filter to only show pure brand kit presets (brand kit data + minimal input_snapshot)
      const brandKitPresets = response.presets.filter(preset => 
        preset.preset_type === 'INPUT_TEMPLATE' && 
        (preset.brand_kit?.colors?.length || preset.brand_kit?.brand_voice_description || preset.brand_kit?.logo_file_base64) &&
        preset.preset_source_type === 'brand-kit' &&
        preset.input_snapshot?.platform_name === 'Brand Kit (Universal)'
      );
      setPresets(brandKitPresets);
    } catch (err) {
      setError('Failed to load brand kit presets. Please try again.');
      console.error('Error loading brand kit presets:', err);
    } finally {
      setLoading(false);
    }
  };

  const handlePresetSelect = (preset: BrandPresetResponse) => {
    onPresetSelected(preset);
  };

  const formatLastUsed = (lastUsedAt: string | null) => {
    if (!lastUsedAt) return 'Never used';
    const date = new Date(lastUsedAt);
    return date.toLocaleDateString();
  };



  const renderContent = () => {
    if (loading) {
      return (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      );
    }

    if (error) {
      return (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      );
    }

    if (presets.length === 0) {
      return (
        <Paper sx={{ p: 4, textAlign: 'center', backgroundColor: 'grey.50' }}>
          <BusinessIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            No Brand Kits Found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Create your first brand kit by adding colors and voice guidelines in the Brand Kit section, then clicking "Save Kit".
          </Typography>
        </Paper>
      );
    }

    return (
      <List>
        {presets.map((preset, index) => (
          <motion.div
            key={preset.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.1 }}
          >
            <ListItem
              sx={{ 
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                mb: 1,
                cursor: 'pointer',
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
                transition: 'background-color 0.2s',
                p: 2,
              }}
              onClick={() => handlePresetSelect(preset)}
            >
              {/* Main content in horizontal layout */}
              <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', gap: 2 }}>
                {/* Icon */}
                <PaletteIcon color="primary" sx={{ fontSize: 28 }} />
                
                {/* Brand kit preview (logo + colors) */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {/* Logo preview */}
                  {preset.brand_kit?.logo_file_base64 && (
                    <Box sx={{ 
                      width: 32, 
                      height: 32, 
                      borderRadius: 1,
                      border: 1,
                      borderColor: 'divider',
                      overflow: 'hidden',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: 'background.paper'
                    }}>
                      <img 
                        src={preset.brand_kit.logo_file_base64} 
                        alt="Logo" 
                        style={{ 
                          maxWidth: '100%', 
                          maxHeight: '100%', 
                          objectFit: 'contain' 
                        }} 
                      />
                    </Box>
                  )}
                  
                  {/* Color preview */}
                  {preset.brand_kit?.colors && preset.brand_kit.colors.length > 0 && (
                    <Box sx={{ display: 'flex', gap: 0.5 }}>
                      {preset.brand_kit.colors.slice(0, 5).map((color, index) => (
                        <Box
                          key={index}
                          sx={{
                            width: 20,
                            height: 20,
                            backgroundColor: color,
                            borderRadius: '50%',
                            border: 1,
                            borderColor: 'divider',
                          }}
                        />
                      ))}
                      {preset.brand_kit.colors.length > 5 && (
                        <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5, alignSelf: 'center' }}>
                          +{preset.brand_kit.colors.length - 5}
                        </Typography>
                      )}
                    </Box>
                  )}
                </Box>

                {/* Brand kit info */}
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      {preset.name}
                    </Typography>
                    <Chip 
                      label="Brand Kit" 
                      size="small" 
                      color="primary" 
                      variant="outlined"
                    />
                  </Box>
                  
                  {/* Compact description */}
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                    {preset.brand_kit?.colors?.length || 0} colors
                    {preset.brand_kit?.brand_voice_description && ', voice guidelines'}
                    {preset.brand_kit?.logo_file_base64 && ', logo'}
                  </Typography>
                  
                  {/* Voice preview (truncated) */}
                  {preset.brand_kit?.brand_voice_description && (
                    <Typography variant="caption" color="text.secondary" sx={{ 
                      fontStyle: 'italic',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      display: 'block',
                      maxWidth: '100%'
                    }}>
                      "{preset.brand_kit.brand_voice_description}"
                    </Typography>
                  )}
                </Box>

                {/* Usage stats */}
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    Used {preset.usage_count} times
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {formatLastUsed(preset.last_used_at)}
                  </Typography>
                </Box>
              </Box>
            </ListItem>
          </motion.div>
        ))}
      </List>
    );
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="md" 
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 }
      }}
    >
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            <PaletteIcon color="primary" />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Load Brand Kit
            </Typography>
          </Box>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Select a saved brand kit to apply its colors, voice guidelines, and logo to your current project.
        </Typography>
        
        <Divider sx={{ mb: 2 }} />
        
        {renderContent()}
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>
          Cancel
        </Button>
      </DialogActions>
    </Dialog>
  );
} 