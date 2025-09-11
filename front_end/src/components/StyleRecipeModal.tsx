'use client';

import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  TextField,
  Paper,
  Alert,
  CircularProgress,
  Divider,
  Stack,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Chip,
  Switch,
  FormGroup,
  FormControlLabel,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Close as CloseIcon,
  Style as StyleIcon,
  PlayArrow as PlayArrowIcon,
  Restore as RestoreIcon,
  Delete as DeleteIcon,
  ExpandLess as ExpandLessIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { BrandPresetResponse, PipelineRunResponse, PipelineFormData, StyleRecipeEnvelope, BrandKitInput, BrandColor } from '@/types/api';
import { PipelineAPI } from '@/lib/api';
import ImageWithAuth from './ImageWithAuth';
import CompactColorPreview from './CompactColorPreview';
import ColorPaletteModal from './ColorPaletteModal';
import LogoUploader from './LogoUploader';
import CompactLogoDisplay from './CompactLogoDisplay';


interface StyleRecipeModalProps {
  preset: BrandPresetResponse;
  open: boolean;
  onClose: () => void;
  onRunStarted: (run: PipelineRunResponse) => void;
}

// Supported image formats for the new subject image
const SUPPORTED_IMAGE_FORMATS = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
  'image/gif': ['.gif'],
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const platforms = [
  'Instagram Post (1:1 Square)',
  'Instagram Story/Reel (9:16 Vertical)',
  'Facebook Post (Mixed)',
  'Pinterest Pin (2:3 Vertical)',
  'Xiaohongshu (Red Note) (3:4 Vertical)',
];

export default function StyleRecipeModal({
  preset,
  open,
  onClose,
  onRunStarted,
}: StyleRecipeModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [promptText, setPromptText] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  // --- New state for advanced controls ---
  const [sourcePlatform, setSourcePlatform] = useState<string>(platforms[0]);
  const [renderText, setRenderText] = useState(false);
  const [applyBranding, setApplyBranding] = useState(false);
  const [language, setLanguage] = useState('en');
  const [showCustomLanguage, setShowCustomLanguage] = useState(false);
  const [brandKit, setBrandKit] = useState<BrandKitInput | undefined>(undefined);
  const [brandingExpanded, setBrandingExpanded] = useState(false);
  const [colorPaletteModalOpen, setColorPaletteModalOpen] = useState(false);

  // --- Original (saved) values state ---
  const [originalSettings, setOriginalSettings] = useState<Partial<StyleRecipeEnvelope & { brand_kit?: BrandKitInput }>>({});

  // --- Effect to pre-populate state when modal opens ---
  React.useEffect(() => {
    if (open && preset) {
      const { style_recipe, brand_kit: presetBrandKit } = preset;
      
      // Migrate colors from old string[] format to new BrandColor[] format if needed
      const migrateColors = (colors: any[]): BrandColor[] => {
        if (!colors || colors.length === 0) return [];
        
        // Check if colors are already in new format (objects with hex, role properties)
        if (typeof colors[0] === 'object' && colors[0].hex && colors[0].role) {
          return colors as BrandColor[];
        }
        
        // Migrate from old string[] format
        const roles = ['primary', 'accent', 'neutral_light', 'neutral_dark'];
        return colors.map((color, index) => ({
          hex: color as string,
          role: roles[index] || 'accent',
          label: undefined,
          ratio: undefined,
        }));
      };
      
      // Migrate brand kit colors if needed
      let migratedBrandKit = presetBrandKit;
      if (migratedBrandKit?.colors) {
        migratedBrandKit = {
          ...migratedBrandKit,
          colors: migrateColors(migratedBrandKit.colors)
        };
      }
      
      const savedSettings = {
        render_text: style_recipe?.render_text ?? false,
        apply_branding: style_recipe?.apply_branding ?? false,
        source_platform: style_recipe?.source_platform || platforms[0],
        language: style_recipe?.language || 'en',
        brand_kit: migratedBrandKit,
      };

              // Set current values
        setSourcePlatform(savedSettings.source_platform);
        setRenderText(savedSettings.render_text);
        setApplyBranding(savedSettings.apply_branding);
        setLanguage(savedSettings.language);
        setBrandKit(savedSettings.brand_kit);
        
        // Auto-expand branding section if any branding/rendering options are enabled
        if (savedSettings.render_text || savedSettings.apply_branding) {
          setBrandingExpanded(true);
        }
      
      // Store original values for comparison
      setOriginalSettings(savedSettings);
      
    } else {
      // Reset all state when closing or if no preset
      setSourcePlatform(platforms[0]);
      setRenderText(false);
      setApplyBranding(false);
      setLanguage('en');
      setShowCustomLanguage(false);
      setBrandKit(undefined);
      setOriginalSettings({});
      setBrandingExpanded(false);
    }
  }, [open, preset]);

        // --- Helper functions to check for preset modifications ---
  const isOverridden = (key: keyof typeof originalSettings) => {
    if (!originalSettings || Object.keys(originalSettings).length === 0) return false;
    
    if (key === 'brand_kit') {
      // Simple JSON string comparison for deep equality check
      return JSON.stringify(brandKit) !== JSON.stringify(originalSettings.brand_kit);
    }
    
    const currentValues: { [key: string]: any } = { 
        render_text: renderText, 
        apply_branding: applyBranding, 
        source_platform: sourcePlatform, 
        language: language 
    };
    return currentValues[key] !== originalSettings[key as keyof typeof originalSettings];
  };
  
  const handleReset = (key: keyof typeof originalSettings) => {
      if (!originalSettings) return;
      if (key === 'render_text') setRenderText(originalSettings.render_text!);
      if (key === 'apply_branding') setApplyBranding(originalSettings.apply_branding!);
      if (key === 'source_platform') setSourcePlatform(originalSettings.source_platform!);
      if (key === 'language') setLanguage(originalSettings.language!);
      if (key === 'brand_kit') setBrandKit(originalSettings.brand_kit);
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      // Validate file size (50MB max)
      if (file.size > 50 * 1024 * 1024) {
        toast.error('File size must be less than 50MB');
        return;
      }
      setSelectedFile(file);
      toast.success(`Image "${file.name}" selected for style adaptation`);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: SUPPORTED_IMAGE_FORMATS,
    multiple: false,
    onDragEnter: () => setDragActive(true),
    onDragLeave: () => setDragActive(false),
    onDropAccepted: () => setDragActive(false),
    onDropRejected: (rejectedFiles) => {
      setDragActive(false);
      if (rejectedFiles.length > 0) {
        const file = rejectedFiles[0];
        if (file.errors.some(error => error.code === 'file-invalid-type')) {
          toast.error('Please upload a valid image file (JPG, PNG, WebP, or GIF)');
        } else if (file.errors.some(error => error.code === 'file-too-large')) {
          toast.error('File size must be less than 50MB');
        } else {
          toast.error('Invalid file. Please try again.');
        }
      }
    },
  });

  const handleRemoveFile = () => {
    setSelectedFile(null);
  };

  const handleSubmit = async () => {
    if (!selectedFile) {
      toast.error('Please upload an image for the style adaptation');
      return;
    }

    setIsSubmitting(true);
    
    try {
      // Prepare form data for the API call
      const formData: PipelineFormData = {
        mode: 'easy_mode', // Default mode for style recipes
        platform_name: sourcePlatform, // Use the selected platform from state
        creativity_level: 2, // Default creativity
        num_variants: 3, // Default variants
        render_text: renderText,
        apply_branding: applyBranding,
        language: language,
        brand_kit: applyBranding ? brandKit : undefined,
        preset_id: preset.id,
        preset_type: 'STYLE_RECIPE',
        image_file: selectedFile,
        adaptation_prompt: promptText.trim() || undefined,
      };

      // Submit the run
      const response = await PipelineAPI.submitRun(formData);
      
      toast.success('Style adaptation started successfully!');
      onRunStarted(response);
      
      // Close modal and reset form
      onClose();
      setSelectedFile(null);
      setPromptText('');
      
    } catch (error: any) {
      console.error('Error starting style adaptation:', error);
      toast.error(error?.message || 'Failed to start style adaptation. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (isSubmitting) return; // Prevent closing during submission
    setSelectedFile(null);
    setPromptText('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth={false}
      fullWidth={false}
      PaperProps={{
        sx: {
          borderRadius: 2,
          maxHeight: '90vh',
          width: '95vw',
          maxWidth: '800px',
          margin: 'auto',
          display: 'flex',
          flexDirection: 'column'
        }
      }}
    >
      <Box sx={{ 
        p: 2.5,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        flex: 1,
        minHeight: 0
      }}>
        <DialogTitle sx={{ p: 0, mb: 1 }}>
          <Typography variant="h6" fontWeight="bold">
            Style Recipe: {preset?.name}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Adapt this style to a new subject image
          </Typography>
        </DialogTitle>

        {/* Scrollable content area */}
        <Box sx={{ 
          flex: 1, 
          overflowY: 'auto', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: 1.5,
          pr: 0.5 // Small padding for scrollbar
        }}>
            {/* Top Row: Platform & Language Settings (Compact) */}
            <Box sx={{ display: 'flex', gap: 1.5, mb: 1, flexWrap: 'wrap' }}>
              <Paper sx={{ 
                flex: 1, 
                minWidth: '280px', 
                p: 1.5, 
                bgcolor: isOverridden('source_platform') ? 'warning.50' : 'grey.50',
                border: 1,
                borderColor: isOverridden('source_platform') ? 'warning.main' : 'grey.300'
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'between', mb: 1 }}>
                  <Typography variant="body2" fontWeight="medium">
                    Target Platform
                  </Typography>
                  {!isOverridden('source_platform') && (
                    <Chip 
                      label="From Recipe" 
                      size="small" 
                      color="primary" 
                      variant="outlined"
                      sx={{ height: 20, fontSize: '0.7rem', ml: 'auto' }}
                    />
                  )}
                </Box>
                <FormControl fullWidth size="small">
                  <Select
                    value={sourcePlatform}
                    onChange={(e) => setSourcePlatform(e.target.value)}
                    displayEmpty
                  >
                    {platforms.map((p) => (
                      <MenuItem key={p} value={p}>{p}</MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {isOverridden('source_platform') && 
                  <Chip 
                    icon={<RestoreIcon />} 
                    label="Reset" 
                    onClick={() => handleReset('source_platform')} 
                    size="small" 
                    color="warning"
                    sx={{mt:0.5}}
                  />
                }
              </Paper>

              <Paper sx={{ 
                flex: 1, 
                minWidth: '280px', 
                p: 1.5, 
                bgcolor: isOverridden('language') ? 'warning.50' : 'grey.50',
                border: 1,
                borderColor: isOverridden('language') ? 'warning.main' : 'grey.300'
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'between', mb: 1 }}>
                  <Typography variant="body2" fontWeight="medium">
                    Output Language
                  </Typography>
                  {!isOverridden('language') && (
                    <Chip 
                      label="From Recipe" 
                      size="small" 
                      color="primary" 
                      variant="outlined"
                      sx={{ height: 20, fontSize: '0.7rem', ml: 'auto' }}
                    />
                  )}
                </Box>
                <FormControl fullWidth size="small">
                  <Select
                    value={showCustomLanguage ? 'other' : language}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === 'other') {
                        setShowCustomLanguage(true);
                        setLanguage('');
                      } else {
                        setShowCustomLanguage(false);
                        setLanguage(value);
                      }
                    }}
                    displayEmpty
                  >
                    <MenuItem value="en">English</MenuItem>
                    <MenuItem value="zh">中文</MenuItem>
                    <MenuItem value="other">Other...</MenuItem>
                  </Select>
                </FormControl>
                {isOverridden('language') && 
                  <Chip 
                    icon={<RestoreIcon />} 
                    label="Reset" 
                    onClick={() => handleReset('language')} 
                    size="small" 
                    color="warning"
                    sx={{mt:0.5}}
                  />
                }
                {showCustomLanguage && (
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="e.g., es, fr, ja"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value.toLowerCase())}
                    sx={{ mt: 1 }}
                  />
                )}
              </Paper>
            </Box>

            {/* Main Content Row: File Upload + Instructions */}
            <Box sx={{ display: 'flex', gap: 1.5, mb: 1, flexDirection: { xs: 'column', md: 'row' } }}>
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" fontWeight="medium" sx={{ mb: 1 }}>
                  Upload New Subject <span style={{ color: 'red' }}>*</span>
                </Typography>
                
                <AnimatePresence mode="wait">
                  {selectedFile ? (
                    <motion.div
                      key="file-selected"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Paper
                        variant="outlined"
                        sx={{
                          p: 1.5,
                          border: '2px solid',
                          borderColor: 'success.main',
                          bgcolor: 'success.50',
                        }}
                      >
                        <Box display="flex" alignItems="center" justifyContent="space-between">
                          <Box sx={{ minWidth: 0, flex: 1 }}>
                            <Typography variant="body2" fontWeight="medium" noWrap>
                              {selectedFile.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {formatFileSize(selectedFile.size)} • Ready
                            </Typography>
                          </Box>
                          <Button
                            variant="outlined"
                            size="small"
                            onClick={handleRemoveFile}
                            disabled={isSubmitting}
                            sx={{ ml: 1, flexShrink: 0 }}
                          >
                            Change
                          </Button>
                        </Box>
                      </Paper>
                    </motion.div>
                  ) : (
                    <motion.div
                      key="file-upload"
                      initial={{ opacity: 0, scale: 0.95 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.2 }}
                    >
                      <Paper
                        {...getRootProps()}
                        variant="outlined"
                        sx={{
                          p: 2,
                          textAlign: 'center',
                          cursor: 'pointer',
                          border: '2px dashed',
                          borderColor: dragActive || isDragActive ? 'primary.main' : 'grey.300',
                          bgcolor: dragActive || isDragActive ? 'primary.50' : 'transparent',
                          transition: 'all 0.2s ease-in-out',
                          '&:hover': {
                            borderColor: 'primary.main',
                            bgcolor: 'primary.50',
                          },
                        }}
                      >
                        <input {...getInputProps()} />
                        <CloudUploadIcon
                          sx={{
                            fontSize: 32,
                            color: dragActive || isDragActive ? 'primary.main' : 'grey.400',
                            mb: 1,
                          }}
                        />
                        <Typography variant="body2" gutterBottom>
                          {dragActive || isDragActive ? 'Drop here' : 'Drop or browse'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          JPG, PNG, WebP • Max 50MB
                        </Typography>
                      </Paper>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Box>

              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" fontWeight="medium" sx={{ mb: 1 }}>
                  Additional Instructions
                </Typography>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  variant="outlined"
                  placeholder="e.g., 'Make it more vibrant'"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  disabled={isSubmitting}
                  size="small"
                />
              </Box>
            </Box>

            {/* Bottom Section: Branding & Rendering (Collapsible) */}
            <Paper sx={{ border: 1, borderColor: 'divider' }}>
              <Box 
                sx={{ 
                  p: 1.5, 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  cursor: 'pointer',
                  bgcolor: 'grey.50'
                }}
                onClick={() => setBrandingExpanded(!brandingExpanded)}
              >
                <Typography variant="body2" fontWeight="medium">
                  Branding & Rendering Options
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {renderText && 'Text • '}{applyBranding && 'Branding • '}
                    {!renderText && !applyBranding && 'None selected'}
                  </Typography>
                  {brandingExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                </Box>
              </Box>
              
              <Collapse in={brandingExpanded}>
                <Box sx={{ p: 1.5, borderTop: 1, borderColor: 'divider' }}>
                  {/* Switches Row */}
                  <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5, mb: 1.5 }}>
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 1,
                      p: 1,
                      bgcolor: isOverridden('render_text') ? 'warning.50' : 'grey.50',
                      borderRadius: 1,
                      border: 1,
                      borderColor: isOverridden('render_text') ? 'warning.main' : 'grey.300'
                    }}>
                      <FormControlLabel
                        control={<Switch checked={renderText} onChange={(e) => setRenderText(e.target.checked)} />}
                        label="Render Text"
                        sx={{ m: 0 }}
                        componentsProps={{
                          typography: { variant: 'body2' }
                        }}
                      />
                      {renderText && !isOverridden('render_text') && (
                        <Chip 
                          label="From Recipe" 
                          size="small" 
                          color="primary" 
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.7rem', ml: 'auto' }}
                        />
                      )}
                      {isOverridden('render_text') && 
                        <Chip 
                          icon={<RestoreIcon />} 
                          label="Reset" 
                          onClick={() => handleReset('render_text')} 
                          size="small" 
                          color="warning"
                          sx={{ ml: 'auto' }}
                        />
                      }
                    </Box>
                    
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 1,
                      p: 1,
                      bgcolor: isOverridden('apply_branding') ? 'warning.50' : 'grey.50',
                      borderRadius: 1,
                      border: 1,
                      borderColor: isOverridden('apply_branding') ? 'warning.main' : 'grey.300'
                    }}>
                      <FormControlLabel
                        control={<Switch checked={applyBranding} onChange={(e) => setApplyBranding(e.target.checked)} />}
                        label="Apply Brand Kit"
                        sx={{ m: 0 }}
                        componentsProps={{
                          typography: { variant: 'body2' }
                        }}
                      />
                      {applyBranding && !isOverridden('apply_branding') && (
                        <Chip 
                          label="From Recipe" 
                          size="small" 
                          color="primary" 
                          variant="outlined"
                          sx={{ height: 20, fontSize: '0.7rem', ml: 'auto' }}
                        />
                      )}
                      {isOverridden('apply_branding') && 
                        <Chip 
                          icon={<RestoreIcon />} 
                          label="Reset" 
                          onClick={() => handleReset('apply_branding')} 
                          size="small" 
                          color="warning"
                          sx={{ ml: 'auto' }}
                        />
                      }
                    </Box>
                  </Box>

                  {/* Brand Kit Content */}
                  <AnimatePresence>
                    {applyBranding && (
                      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                        <Paper sx={{ 
                          p: 1.5, 
                          bgcolor: isOverridden('brand_kit') ? 'warning.50' : 'grey.50', 
                          border: 1, 
                          borderColor: isOverridden('brand_kit') ? 'warning.main' : 'grey.300'
                        }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body2" fontWeight="medium">
                                Brand Kit Configuration
                              </Typography>
                              {!isOverridden('brand_kit') && (
                                <Chip 
                                  label="From Recipe" 
                                  size="small" 
                                  color="primary" 
                                  variant="outlined"
                                  sx={{ height: 20, fontSize: '0.7rem' }}
                                />
                              )}
                            </Box>
                            {isOverridden('brand_kit') && 
                              <Chip 
                                icon={<RestoreIcon />} 
                                label="Reset Brand Kit" 
                                onClick={() => handleReset('brand_kit')} 
                                size="small" 
                                color="warning"
                              />
                            }
                          </Box>
                          
                          {/* Brand Kit Grid Layout */}
                          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
                            {/* Colors Section */}
                            <Box>
                              <Typography variant="caption" fontWeight="medium" sx={{ mb: 1, display: 'block' }}>
                                Brand Colors
                              </Typography>
                              <CompactColorPreview
                                colors={brandKit?.colors || []}
                                onEditClick={() => setColorPaletteModalOpen(true)}
                                onRemove={() => setBrandKit(prev => ({...(prev || {}), colors: []}))}
                                showRatios={false}
                                maxDisplayColors={5}
                              />
                            </Box>
                            
                            {/* Logo Section */}
                            <Box>
                              <Typography variant="caption" fontWeight="medium" sx={{ mb: 1, display: 'block' }}>
                                Brand Logo
                              </Typography>
                              {brandKit?.logo_file_base64 ? (
                                <Paper 
                                  sx={{ 
                                    p: 1.5, 
                                    border: 1, 
                                    borderColor: 'divider',
                                    backgroundColor: 'background.paper',
                                    borderRadius: 1
                                  }}
                                >
                                  <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                                    {/* Logo Preview */}
                                    <Box sx={{ flexShrink: 0 }}>
                                      <Paper
                                        sx={{
                                          width: 40,
                                          height: 40,
                                          border: 1,
                                          borderColor: 'divider',
                                          borderRadius: 1,
                                          overflow: 'hidden',
                                          display: 'flex',
                                          alignItems: 'center',
                                          justifyContent: 'center',
                                          backgroundColor: 'background.paper',
                                        }}
                                      >
                                        <Box
                                          component="img"
                                          src={brandKit.logo_file_base64}
                                          alt="Brand Logo"
                                          sx={{
                                            maxWidth: '100%',
                                            maxHeight: '100%',
                                            objectFit: 'contain',
                                          }}
                                        />
                                      </Paper>
                                    </Box>

                                    {/* Logo Information */}
                                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                                      <Typography variant="caption" fontWeight="medium" sx={{ display: 'block' }}>
                                        Brand Logo
                                      </Typography>
                                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                        PNG Format • Optimized
                                      </Typography>
                                    </Box>

                                    {/* Remove Button */}
                                    <Box sx={{ flexShrink: 0 }}>
                                      <IconButton 
                                        onClick={() => setBrandKit(prev => ({...(prev || {}), logo_file_base64: undefined, logo_analysis: undefined}))}
                                        size="small"
                                        color="error"
                                        sx={{ p: 0.25 }}
                                      >
                                        <DeleteIcon sx={{ fontSize: 14 }} />
                                      </IconButton>
                                    </Box>
                                  </Box>
                                </Paper>
                              ) : (
                                <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 1 }}>
                                  <LogoUploader
                                    onLogoUpload={(file, analysis) => {
                                      setBrandKit(prev => ({...(prev || {}), logo_file_base64: analysis.preview_url, logo_analysis: analysis}));
                                    }}
                                    onLogoRemove={() => setBrandKit(prev => ({...(prev || {}), logo_file_base64: undefined, logo_analysis: undefined}))}
                                    currentLogo={null}
                                  />
                                </Box>
                              )}
                            </Box>
                          </Box>
                          
                          {/* Brand Voice Section - Full Width */}
                          <Box sx={{ mt: 1.5 }}>
                            <Typography variant="caption" fontWeight="medium" sx={{ mb: 1, display: 'block' }}>
                              Brand Voice
                            </Typography>
                            <TextField
                              fullWidth
                              size="small"
                              placeholder="e.g., 'Friendly and approachable'"
                              value={brandKit?.brand_voice_description || ''}
                              onChange={(e) => setBrandKit(prev => ({...(prev || {}), brand_voice_description: e.target.value}))}
                              sx={{ bgcolor: 'background.paper' }}
                            />
                          </Box>
                        </Paper>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </Box>
              </Collapse>
            </Paper>

          {/* Warning/Info */}
          <Alert severity="info" sx={{ fontSize: '0.85rem' }}>
            This adaptation will apply the saved style recipe to your new subject image 
            while applying them to the new subject image you upload.
          </Alert>
        </Box>
      </Box>

      <DialogActions sx={{ p: 2.5, pt: 1.5, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
        <Button
          onClick={handleClose}
          disabled={isSubmitting}
          variant="outlined"
        >
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          disabled={!selectedFile || isSubmitting}
          variant="contained"
          startIcon={isSubmitting ? <CircularProgress size={20} /> : <PlayArrowIcon />}
        >
          {isSubmitting ? 'Starting...' : 'Run Style Adaptation'}
        </Button>
      </DialogActions>

      {/* Color Palette Modal */}
      <ColorPaletteModal
        open={colorPaletteModalOpen}
        onClose={() => setColorPaletteModalOpen(false)}
        colors={brandKit?.colors || []}
        onChange={(colors) => setBrandKit(prev => ({...(prev || {}), colors}))}
        maxColors={7}
        logoFile={null}
        title="Brand Color Palette"
      />
    </Dialog>
  );
} 