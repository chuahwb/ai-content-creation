'use client';

import React, { useState, useEffect } from 'react';
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
  Tooltip,
  Divider,
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
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { BrandPreset, BrandPresetListResponse, BrandPresetResponse } from '@/types/api';
import { PipelineAPI } from '@/lib/api';

interface PresetManagementModalProps {
  open: boolean;
  onClose: () => void;
  onPresetSelected: (preset: BrandPresetResponse) => void;
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

export default function PresetManagementModal({ 
  open, 
  onClose, 
  onPresetSelected 
}: PresetManagementModalProps) {
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

  // Load presets when modal opens
  useEffect(() => {
    if (open) {
      loadPresets();
    }
  }, [open]);

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
    toast.success(`${preset.preset_type === 'INPUT_TEMPLATE' ? 'Template' : 'Recipe'} "${preset.name}" applied`);
  };

  const handleRenameClick = () => {
    if (selectedPreset) {
      setRenameName(selectedPreset.name);
      setRenameDialogOpen(true);
    }
    handleMenuClose();
  };

  const handleDeleteClick = () => {
    setDeleteDialogOpen(true);
    handleMenuClose();
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
      loadPresets(); // Refresh list
    } catch (err) {
      toast.error('Failed to rename preset');
      console.error('Error renaming preset:', err);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!selectedPreset) return;
    
    try {
      await PipelineAPI.deleteBrandPreset(selectedPreset.id);
      toast.success('Preset deleted successfully');
      setDeleteDialogOpen(false);
      loadPresets(); // Refresh list
    } catch (err) {
      toast.error('Failed to delete preset');
      console.error('Error deleting preset:', err);
    }
  };

  const getPresetsByType = (type: string) => {
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
                        Model: {preset.model_id}
                      </Typography>
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
      <Dialog open={renameDialogOpen} onClose={() => setRenameDialogOpen(false)}>
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
          <Button onClick={() => setRenameDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleRenameConfirm} disabled={!renameName.trim()}>
            Rename
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Preset</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete "{selectedPreset?.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
} 