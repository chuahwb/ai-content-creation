'use client';

import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Menu,
  MenuItem,
  Chip,
  Alert,
  CircularProgress,
  TextField,
  DialogContentText,
  Grid,
  Tooltip,
  Divider,
  Paper,
} from '@mui/material';
import {
  BookmarkAdd as BookmarkAddIcon,
  MoreVert as MoreVertIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Close as CloseIcon,
  Palette as PaletteIcon,
  Style as StyleIcon,
  Info as InfoIcon,
  Add as AddIcon,
  Business as BusinessIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { BrandPreset, BrandPresetListResponse, BrandPresetResponse, BrandColor } from '@/types/api';
import { PipelineAPI } from '@/lib/api';
import EnhancedColorPaletteEditor from './EnhancedColorPaletteEditor';
import LogoUploader from './LogoUploader';
import CompactLogoDisplay from './CompactLogoDisplay';

interface PresetManagementModalProps {
  open: boolean;
  onClose: () => void;
  onPresetSelected: (preset: BrandPresetResponse) => void;
  onPresetSaved?: () => void;
}

export interface PresetManagementModalRef {
  refreshPresets: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`preset-tabpanel-${index}`}
      aria-labelledby={`preset-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const PresetManagementModal = forwardRef<PresetManagementModalRef, PresetManagementModalProps>(({ 
  open, 
  onClose, 
  onPresetSelected,
  onPresetSaved
}, ref) => {
  const [activeTab, setActiveTab] = useState(0);
  const [presets, setPresets] = useState<BrandPresetResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Menu states
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedPreset, setSelectedPreset] = useState<BrandPresetResponse | null>(null);
  
  // Dialog states
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [renameName, setRenameName] = useState('');
  
  // Brand Kit editing states
  const [brandKitDialogOpen, setBrandKitDialogOpen] = useState(false);
  const [brandKitEditMode, setBrandKitEditMode] = useState<'create' | 'edit'>('create');
  const [brandKitData, setBrandKitData] = useState<{
    name: string;
    colors: BrandColor[];
    brandVoice: string;
    logo: any;
  }>({
    name: '',
    colors: [],
    brandVoice: '',
    logo: null,
  });

  // Load presets when modal opens
  useEffect(() => {
    if (open) {
      loadPresets();
    }
  }, [open]);

  // Expose refresh method to parent component
  useImperativeHandle(ref, () => ({
    refreshPresets: loadPresets
  }));

  const loadPresets = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await PipelineAPI.getBrandPresets();
      setPresets(response.presets || []);
    } catch (err) {
      setError('Failed to load presets. Please try again.');
      console.error('Error loading presets:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, preset: BrandPresetResponse) => {
    setAnchorEl(event.currentTarget);
    setSelectedPreset(preset);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedPreset(null);
  };

  const handleUsePreset = (preset: BrandPresetResponse) => {
    onPresetSelected(preset);
    onClose();
    
    // Note: All preset application messaging is now handled by the PipelineForm
    // to provide comprehensive context and avoid duplicate notifications
  };

  const handleRenameClick = () => {
    if (selectedPreset) {
      setRenameName(selectedPreset.name);
      setRenameDialogOpen(true);
    }
    setAnchorEl(null); // Close menu but keep selectedPreset
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
    setAnchorEl(null); // Close menu but keep selectedPreset
  };

  const handleRenameConfirm = async () => {
    if (!selectedPreset || !renameName.trim()) return;
    
    try {
      await PipelineAPI.updateBrandPreset(selectedPreset.id, {
        name: renameName.trim(),
        version: selectedPreset.version,
      });
      
      toast.success('Preset renamed successfully');
      setRenameDialogOpen(false);
      setRenameName('');
      setSelectedPreset(null); // Clear selected preset after successful rename
      loadPresets(); // Refresh list
      onPresetSaved?.(); // Notify parent of preset change
    } catch (err) {
      toast.error('Failed to rename preset');
      console.error('Error renaming preset:', err);
    }
  };

  const handleRenameCancel = () => {
    setRenameDialogOpen(false);
    setRenameName('');
    setSelectedPreset(null); // Clear selected preset when canceling
  };

  const handleDeleteConfirm = async () => {
    if (!selectedPreset) return;
    
    try {
      await PipelineAPI.deleteBrandPreset(selectedPreset.id);
      toast.success('Preset deleted successfully');
      setDeleteDialogOpen(false);
      setSelectedPreset(null); // Clear selected preset after successful deletion
      loadPresets(); // Refresh list
      onPresetSaved?.(); // Notify parent of preset change
    } catch (err) {
      toast.error('Failed to delete preset');
      console.error('Error deleting preset:', err);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteDialogOpen(false);
    setSelectedPreset(null); // Clear selected preset when canceling
  };

  // Brand Kit functions
  const handleCreateBrandKit = () => {
    setBrandKitEditMode('create');
    setBrandKitData({
      name: '',
      colors: [],
      brandVoice: '',
      logo: null,
    });
    setBrandKitDialogOpen(true);
  };

  const handleEditBrandKit = (preset: BrandPresetResponse) => {
    setBrandKitEditMode('edit');
    
    // Extract logo information more intelligently
    let logoData = null;
    if (preset.brand_kit?.logo_file_base64) {
      // Try to extract format from base64 data URL
      const formatMatch = preset.brand_kit.logo_file_base64.match(/data:image\/([^;]+)/);
      const format = formatMatch ? formatMatch[1].toUpperCase() : 'Image';
      
      // Estimate file size from base64 (approximate)
      const base64Length = preset.brand_kit.logo_file_base64.length;
      const sizeKB = Math.round(base64Length * 0.75 / 1024);
      
      logoData = {
        analysis: {
          filename: `${preset.name}_logo.${format.toLowerCase()}`,
          file_size_kb: sizeKB,
          preview_url: preset.brand_kit.logo_file_base64,
          format: format,
          // Preserve original analysis if it exists
          ...(preset.brand_kit.logo_analysis || {})
        },
        base64: preset.brand_kit.logo_file_base64
      };
    }
    
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

    setBrandKitData({
      name: preset.name,
      colors: migrateColors(preset.brand_kit?.colors || []),
      brandVoice: preset.brand_kit?.brand_voice_description || '',
      logo: logoData,
    });
    setSelectedPreset(preset);
    setBrandKitDialogOpen(true);
  };

  const handleBrandKitSave = async () => {
    // Basic validation
    if (!brandKitData.name.trim()) {
      toast.error('Please enter a name for the brand kit');
      return;
    }

    // Validate brand kit has at least one field defined
    const hasColors = brandKitData.colors.length > 0;
    const hasVoice = brandKitData.brandVoice.trim().length > 0;
    const hasLogo = Boolean(brandKitData.logo?.base64);
    
    if (!hasColors && !hasVoice && !hasLogo) {
      toast.error('Please add at least one brand element: colors, voice description, or logo');
      return;
    }

    // Validate character limits
    if (brandKitData.brandVoice.length > 250) {
      toast.error('Brand voice description must be 250 characters or less');
      return;
    }

    // Validate colors format (basic hex validation)
    for (const color of brandKitData.colors) {
      const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
      if (!hexRegex.test(color.hex)) {
        toast.error(`Invalid color format: ${color.hex}. Please use valid hex colors (e.g., #FF0000)`);
        return;
      }
    }

    try {
      // Prepare brand kit data with proper logo analysis preservation
      const brandKitForSave: any = {
        colors: brandKitData.colors.length > 0 ? brandKitData.colors : undefined,
        brand_voice_description: brandKitData.brandVoice.trim() || undefined,
      };
      
      // Include logo data if present, preserving analysis
      if (brandKitData.logo?.base64) {
        brandKitForSave.logo_file_base64 = brandKitData.logo.base64;
        // Preserve logo analysis if available
        if (brandKitData.logo.analysis) {
          brandKitForSave.logo_analysis = brandKitData.logo.analysis;
        }
      }
      
      const presetData = {
        name: brandKitData.name.trim(),
        preset_type: 'INPUT_TEMPLATE' as const,
        brand_kit: brandKitForSave,
        // Minimal input_snapshot for brand kit presets - only required fields, no execution preferences
        input_snapshot: {
          platform_name: 'Brand Kit (Universal)', // Generic platform name indicating this is brand-agnostic
          creativity_level: 2, // Neutral default
          num_variants: 1, // Minimal default  
          render_text: false, // No text rendering for brand kit
          apply_branding: false, // Brand kit definition doesn't apply itself
          language: 'en', // Default language
        },
        preset_source_type: 'brand-kit',
        pipeline_version: '1.0.0',
      };

      if (brandKitEditMode === 'create') {
        await PipelineAPI.createBrandPreset(presetData);
        toast.success('Brand kit created successfully!');
      } else if (selectedPreset) {
        // Validate we have the required data for update
        if (!selectedPreset.id) {
          throw new Error('Missing preset ID for update');
        }
        
        const updateData = {
          name: presetData.name,
          brand_kit: presetData.brand_kit,
          version: selectedPreset.version,
        };
        
        await PipelineAPI.updateBrandPreset(selectedPreset.id, updateData);
        toast.success(`Brand kit "${presetData.name}" updated successfully!`);
      } else {
        throw new Error('Invalid edit mode: no preset selected for update');
      }

      setBrandKitDialogOpen(false);
      setSelectedPreset(null);
      loadPresets(); // Refresh the list to show updated data
      onPresetSaved?.(); // Notify parent of preset change
    } catch (error: any) {
      console.error('Error saving brand kit:', error);
      
      // Show more specific error messages
      if (error.response?.status === 404) {
        toast.error('Brand kit not found. It may have been deleted by another user.');
      } else if (error.response?.status === 409) {
        toast.error('Brand kit was modified by another user. Please refresh and try again.');
      } else if (error.response?.status === 422) {
        toast.error('Invalid brand kit data. Please check your inputs and try again.');
      } else {
        toast.error(error.message || `Failed to ${brandKitEditMode === 'create' ? 'create' : 'update'} brand kit`);
      }
    }
  };

  const handleBrandKitCancel = () => {
    setBrandKitDialogOpen(false);
    setSelectedPreset(null);
  };

  const getPresetsByType = (type: string) => {
    if (type === 'INPUT_TEMPLATE') {
      // For Templates tab: exclude brand kit presets (they appear in Brand Kit tab only)
      return presets.filter(preset => 
        preset.preset_type === type && 
        !(preset.preset_source_type === 'brand-kit' && 
          preset.input_snapshot?.platform_name === 'Brand Kit (Universal)')
      );
    }
    return presets.filter(preset => preset.preset_type === type);
  };

  const formatLastUsed = (lastUsedAt: string | null) => {
    if (!lastUsedAt) return 'Never used';
    const date = new Date(lastUsedAt);
    return date.toLocaleDateString();
  };

  const getTypeIcon = (type: string) => {
    return type === 'INPUT_TEMPLATE' ? <PaletteIcon /> : <StyleIcon />;
  };

  const getTypeLabel = (type: string) => {
    return type === 'INPUT_TEMPLATE' ? 'Template' : 'Recipe';
  };

  const getTypeDescription = (type: string) => {
    return type === 'INPUT_TEMPLATE' 
      ? 'Starting point for new creative work'
      : 'Saved style to remake or adapt';
  };

  const renderPresetList = (presetType: string) => {
    const filteredPresets = getPresetsByType(presetType);
    
    if (loading) {
      return (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      );
    }

    if (filteredPresets.length === 0) {
      return (
        <Box textAlign="center" p={4}>
          <Typography variant="body2" color="text.secondary">
            No {presetType === 'INPUT_TEMPLATE' ? 'templates' : 'recipes'} found
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            {presetType === 'INPUT_TEMPLATE' 
              ? 'Save form settings as templates to reuse them later'
              : 'Generate images and save successful styles as recipes'
            }
          </Typography>
        </Box>
      );
    }

    return (
      <List sx={{ width: '100%' }}>
        {filteredPresets.map((preset) => (
          <motion.div
            key={preset.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ListItem
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                mb: 1,
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
              }}
            >
              <ListItemText
                primary={
                  <Box display="flex" alignItems="center" gap={1}>
                    {getTypeIcon(preset.preset_type)}
                    <Typography variant="h6" component="span">
                      {preset.name}
                    </Typography>
                    <Chip
                      label={getTypeLabel(preset.preset_type)}
                      size="small"
                      variant="outlined"
                      sx={{ ml: 1 }}
                    />
                  </Box>
                }
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      {getTypeDescription(preset.preset_type)}
                    </Typography>
                    <Box display="flex" gap={2} mt={1}>
                      <Typography variant="caption" color="text.secondary">
                        Used: {preset.usage_count} times
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Last used: {formatLastUsed(preset.last_used_at ?? null)}
                      </Typography>
                    </Box>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Button
                  variant="contained"
                  size="small"
                  onClick={() => handleUsePreset(preset)}
                  sx={{ mr: 1 }}
                >
                  Use
                </Button>
                <IconButton
                  edge="end"
                  aria-label="more"
                  onClick={(e) => handleMenuOpen(e, preset)}
                >
                  <MoreVertIcon />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          </motion.div>
        ))}
      </List>
    );
  };

  const renderBrandKitList = () => {
    const brandKitPresets = presets.filter(preset => 
      preset.preset_type === 'INPUT_TEMPLATE' && 
      (preset.brand_kit?.colors?.length || preset.brand_kit?.brand_voice_description || preset.brand_kit?.logo_file_base64) &&
      preset.preset_source_type === 'brand-kit' &&
      preset.input_snapshot?.platform_name === 'Brand Kit (Universal)'
    );
    
    if (loading) {
      return (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      );
    }

    if (brandKitPresets.length === 0) {
      return (
        <Box textAlign="center" p={4}>
          <Typography variant="body2" color="text.secondary">
            No brand kits found
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            Create your first brand kit to ensure consistent branding across all content
          </Typography>
        </Box>
      );
    }

    return (
      <List sx={{ width: '100%' }}>
        {brandKitPresets.map((preset) => (
          <motion.div
            key={preset.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <ListItem
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                mb: 1,
                '&:hover': {
                  backgroundColor: 'action.hover',
                },
              }}
            >
              <ListItemText
                primary={
                  <Box display="flex" alignItems="center" gap={1}>
                    <BusinessIcon />
                    <Typography variant="h6" component="span">
                      {preset.name}
                    </Typography>
                  </Box>
                }
                secondary={
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Brand kit with {preset.brand_kit?.colors?.length || 0} colors
                      {preset.brand_kit?.brand_voice_description && ', voice guidelines'}
                      {preset.brand_kit?.logo_file_base64 && ', logo'}
                    </Typography>
                    <Box display="flex" gap={2} mt={1}>
                      <Typography variant="caption" color="text.secondary">
                        Used: {preset.usage_count} times
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        Last used: {formatLastUsed(preset.last_used_at ?? null)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                      {/* Logo preview */}
                      {preset.brand_kit?.logo_file_base64 && (
                        <Box sx={{ 
                          width: 24, 
                          height: 24, 
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
                              backgroundColor: typeof color === 'string' ? color : color.hex,
                              borderRadius: '50%',
                              border: 1,
                              borderColor: 'divider',
                            }}
                          />
                        ))}
                          {preset.brand_kit.colors.length > 5 && (
                            <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                              +{preset.brand_kit.colors.length - 5} more
                            </Typography>
                          )}
                        </Box>
                      )}
                    </Box>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Button
                  variant="contained"
                  size="small"
                  onClick={() => handleUsePreset(preset)}
                  sx={{ mr: 1 }}
                >
                  Use
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => handleEditBrandKit(preset)}
                  sx={{ mr: 1 }}
                >
                  Edit
                </Button>
                <IconButton
                  edge="end"
                  aria-label="more"
                  onClick={(e) => handleMenuOpen(e, preset)}
                >
                  <MoreVertIcon />
                </IconButton>
              </ListItemSecondaryAction>
            </ListItem>
          </motion.div>
        ))}
      </List>
    );
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { minHeight: '60vh' }
        }}
      >
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h5">Brand Presets & Style Memory</Typography>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs value={activeTab} onChange={handleTabChange} aria-label="preset tabs">
              <Tab 
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <PaletteIcon />
                    Templates ({getPresetsByType('INPUT_TEMPLATE').length})
                  </Box>
                }
              />
              <Tab 
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <StyleIcon />
                    Recipes ({getPresetsByType('STYLE_RECIPE').length})
                  </Box>
                }
              />
              <Tab 
                label={
                  <Box display="flex" alignItems="center" gap={1}>
                    <BusinessIcon />
                    Brand Kit ({presets.filter(preset => 
                      preset.preset_type === 'INPUT_TEMPLATE' && 
                      (preset.brand_kit?.colors?.length || preset.brand_kit?.brand_voice_description || preset.brand_kit?.logo_file_base64) &&
                      preset.preset_source_type === 'brand-kit' &&
                      preset.input_snapshot?.platform_name === 'Brand Kit (Universal)'
                    ).length})
                  </Box>
                }
              />
            </Tabs>
          </Box>
          
          <TabPanel value={activeTab} index={0}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Input Templates
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Save your form settings as templates to quickly start new projects with consistent parameters.
              </Typography>
            </Box>
            {renderPresetList('INPUT_TEMPLATE')}
          </TabPanel>
          
          <TabPanel value={activeTab} index={1}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="h6" gutterBottom>
                Style Recipes
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Saved styles from successful image generations. Use these to recreate similar aesthetics or adapt them to new concepts.
              </Typography>
            </Box>
            {renderPresetList('STYLE_RECIPE')}
          </TabPanel>
          
          <TabPanel value={activeTab} index={2}>
            <Box sx={{ mb: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box>
                <Typography variant="h6" gutterBottom>
                  Brand Kit Management
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Create and manage brand kits for consistent branding.
                </Typography>
              </Box>
              <Button
                variant="contained"
                size="small"
                onClick={handleCreateBrandKit}
                startIcon={<AddIcon />}
              >
                Create Brand Kit
              </Button>
            </Box>
            {renderBrandKitList()}
          </TabPanel>
        </DialogContent>
        
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
          <Button onClick={loadPresets} disabled={loading}>
            Refresh
          </Button>
        </DialogActions>
      </Dialog>

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleRenameClick}>
          <EditIcon sx={{ mr: 1 }} />
          Rename
        </MenuItem>
        <MenuItem onClick={handleDeleteClick}>
          <DeleteIcon sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onClose={handleRenameCancel}>
        <DialogTitle>Rename Preset</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Preset Name"
            fullWidth
            variant="outlined"
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleRenameCancel}>Cancel</Button>
          <Button onClick={handleRenameConfirm} disabled={!renameName.trim()}>
            Rename
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={handleDeleteCancel}>
        <DialogTitle>Delete Preset</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{selectedPreset?.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDeleteCancel}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Brand Kit Editor Dialog */}
      <Dialog open={brandKitDialogOpen} onClose={handleBrandKitCancel} maxWidth="md" fullWidth>
        <DialogTitle>
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="h6">
              {brandKitEditMode === 'create' ? 'Create Brand Kit' : 'Edit Brand Kit'}
            </Typography>
            <IconButton onClick={handleBrandKitCancel}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ py: 1 }}>
            {/* Brand Kit Name */}
            <Box sx={{ mb: 2.5 }}>
              <TextField
                fullWidth
                size="small"
                label="Brand Kit Name"
                value={brandKitData.name}
                onChange={(e) => setBrandKitData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., My Company Brand Kit"
                variant="outlined"
              />
            </Box>

            {/* Color Palette - Enhanced */}
            <Box sx={{ mb: 2.5 }}>
              <EnhancedColorPaletteEditor
                colors={brandKitData.colors}
                onChange={(colors) => setBrandKitData(prev => ({ ...prev, colors }))}
                showLabels={true}
                logoFile={brandKitData.logo?.file || null}
              />
            </Box>

            {/* Brand Voice - Compact Layout */}
            <Box sx={{ mb: 2.5 }}>
              <TextField
                fullWidth
                size="small"
                label="Brand Voice"
                value={brandKitData.brandVoice}
                onChange={(e) => {
                  const words = e.target.value.trim().split(/\s+/).filter(word => word.length > 0);
                  if (words.length <= 25 || e.target.value === '') {
                    setBrandKitData(prev => ({ ...prev, brandVoice: e.target.value }));
                  }
                }}
                placeholder="e.g., Friendly, professional, approachable"
                variant="outlined"
                helperText={
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Describe your brand personality in a few words</span>
                    <span style={{ 
                      color: brandKitData.brandVoice.trim().split(/\s+/).filter(w => w.length > 0).length > 25 ? 'red' : 'inherit' 
                    }}>
                      {brandKitData.brandVoice.trim() === '' ? 0 : brandKitData.brandVoice.trim().split(/\s+/).filter(w => w.length > 0).length}/25 words
                    </span>
                  </Box>
                }
                error={brandKitData.brandVoice.trim().split(/\s+/).filter(w => w.length > 0).length > 25}
              />
            </Box>

            {/* Logo Upload/Display - Full Width */}
            <Box sx={{ mb: 2.5 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600, color: 'text.primary' }}>
                Brand Logo
              </Typography>
              {brandKitData.logo?.analysis ? (
                <CompactLogoDisplay
                  logo={brandKitData.logo.analysis}
                  onRemove={() => {
                    setBrandKitData(prev => ({
                      ...prev,
                      logo: null
                    }));
                  }}
                  showRemoveButton={true}
                />
              ) : (
                <LogoUploader
                  onLogoUpload={(file, analysis) => {
                    setBrandKitData(prev => ({
                      ...prev,
                      logo: {
                        file,
                        analysis,
                        base64: analysis.preview_url
                      }
                    }));
                  }}
                  onLogoRemove={() => {
                    setBrandKitData(prev => ({
                      ...prev,
                      logo: null
                    }));
                  }}
                  currentLogo={null}
                  showLabels={false}
                />
              )}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleBrandKitCancel}>Cancel</Button>
          <Button onClick={handleBrandKitSave} variant="contained" disabled={!brandKitData.name.trim()}>
            {brandKitEditMode === 'create' ? 'Create Brand Kit' : 'Update Brand Kit'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
});

PresetManagementModal.displayName = 'PresetManagementModal';

export default PresetManagementModal;