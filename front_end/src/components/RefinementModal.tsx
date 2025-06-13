'use client';

import React, { useState, useRef, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Tabs,
  Tab,
  Alert,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Divider,
  Stack,
  ToggleButton,
} from '@mui/material';
import {
  Close as CloseIcon,
  AutoFixHigh as AutoFixHighIcon,
  CloudUpload as CloudUploadIcon,
  Brush as BrushIcon,
  TextFields as TextFieldsIcon,
  Image as ImageIcon,
  Info as InfoIcon,
  CropFree as CropFreeIcon,
} from '@mui/icons-material';
import toast from 'react-hot-toast';
import { PipelineAPI } from '@/lib/api';

interface RefinementModalProps {
  open: boolean;
  onClose: () => void;
  runId: string;
  imageIndex: number | null;
  imagePath: string | null;
  onRefinementSubmit: (refinementData: any) => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

interface MaskCoordinate {
  x: number;
  y: number;
  width: number;
  height: number;
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`refinement-tabpanel-${index}`}
      aria-labelledby={`refinement-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2 }}>{children}</Box>}
    </div>
  );
}

export default function RefinementModal({
  open,
  onClose,
  runId,
  imageIndex,
  imagePath,
  onRefinementSubmit
}: RefinementModalProps) {
  const [tabValue, setTabValue] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Form state
  const [subjectInstructions, setSubjectInstructions] = useState('');
  const [referenceImage, setReferenceImage] = useState<File | null>(null);
  const [textInstructions, setTextInstructions] = useState('');
  const [promptInstructions, setPromptInstructions] = useState('');
  
  // Regional editing state
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [maskCoordinates, setMaskCoordinates] = useState<MaskCoordinate | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    // Reset drawing mode when switching tabs
    setIsDrawingMode(false);
    setMaskCoordinates(null);
  };

  const handleReferenceImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) { // 10MB limit
        toast.error('Reference image must be smaller than 10MB');
        return;
      }
      setReferenceImage(file);
      toast.success(`Reference image selected: ${file.name}`);
    }
  };

  const toggleDrawingMode = () => {
    setIsDrawingMode(!isDrawingMode);
    if (!isDrawingMode) {
      setMaskCoordinates(null);
    }
  };

  const getImageCoordinates = (event: React.MouseEvent<HTMLElement>) => {
    if (!imageRef.current) return null;
    
    const rect = imageRef.current.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width);
    const y = ((event.clientY - rect.top) / rect.height);
    
    return { x, y };
  };

  const handleMouseDown = (event: React.MouseEvent<HTMLElement>) => {
    if (!isDrawingMode) return;
    
    const coords = getImageCoordinates(event);
    if (coords) {
      setIsDrawing(true);
      setStartPoint(coords);
      setMaskCoordinates(null);
    }
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLElement>) => {
    if (!isDrawing || !startPoint || !isDrawingMode) return;
    
    const coords = getImageCoordinates(event);
    if (coords) {
      const width = Math.abs(coords.x - startPoint.x);
      const height = Math.abs(coords.y - startPoint.y);
      const x = Math.min(startPoint.x, coords.x);
      const y = Math.min(startPoint.y, coords.y);
      
      setMaskCoordinates({ x, y, width, height });
    }
  };

  const handleMouseUp = () => {
    if (isDrawing) {
      setIsDrawing(false);
      setStartPoint(null);
    }
  };

  const clearMask = () => {
    setMaskCoordinates(null);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    
    try {
      const formData = new FormData();
      
      // Common fields
      formData.append('parent_image_id', `image_${imageIndex}`);
      formData.append('parent_image_type', 'original');
      formData.append('generation_index', imageIndex?.toString() || '0');

      // Tab-specific fields
      if (tabValue === 0) { // Subject Repair
        formData.append('refine_type', 'subject');
        formData.append('instructions', subjectInstructions || 'Replace the main subject with a modern version');
        if (referenceImage) {
          formData.append('reference_image', referenceImage);
        }
      } else if (tabValue === 1) { // Text Repair
        formData.append('refine_type', 'text');
        formData.append('instructions', textInstructions || 'Fix and improve text elements');
      } else if (tabValue === 2) { // Prompt Refinement
        formData.append('refine_type', 'prompt');
        formData.append('prompt', promptInstructions || 'Enhance the overall image quality');
        if (maskCoordinates) {
          formData.append('mask_data', JSON.stringify(maskCoordinates));
        }
      }

      // Submit refinement request
      const response = await fetch(`/api/v1/runs/${runId}/refine`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const result = await response.json();
      
      toast.success('Refinement started! Check progress in real-time.');
      onRefinementSubmit(result);
      handleClose();
      
    } catch (error: any) {
      console.error('Refinement submission error:', error);
      toast.error(error.message || 'Failed to start refinement');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    // Reset form state
    setTabValue(0);
    setSubjectInstructions('');
    setReferenceImage(null);
    setTextInstructions('');
    setPromptInstructions('');
    setIsDrawingMode(false);
    setMaskCoordinates(null);
    setIsDrawing(false);
    setStartPoint(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  const getTabIcon = (index: number) => {
    switch (index) {
      case 0: return <ImageIcon />;
      case 1: return <TextFieldsIcon />;
      case 2: return <BrushIcon />;
      default: return <AutoFixHighIcon />;
    }
  };

  const isFormValid = () => {
    if (tabValue === 0) { // Subject Repair
      return subjectInstructions.trim().length > 0;
    } else if (tabValue === 1) { // Text Repair
      return textInstructions.trim().length > 0;
    } else if (tabValue === 2) { // Prompt Refinement
      return promptInstructions.trim().length > 0;
    }
    return false;
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { 
          borderRadius: 3,
          minHeight: '75vh',
          maxHeight: '90vh',
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 2,
        px: 3,
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        borderRadius: '12px 12px 0 0',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AutoFixHighIcon sx={{ fontSize: 28 }} />
          <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
            Refine Image - Option {(imageIndex || 0) + 1}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} sx={{ color: 'white' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0 }}>
        <Box sx={{ display: 'flex', height: '100%' }}>
          {/* Left side - Current Image */}
          <Box sx={{ 
            width: '40%', 
            p: 3, 
            backgroundColor: 'grey.50',
            borderRight: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Current Image
              </Typography>
              {tabValue === 2 && (
                <Tooltip title={isDrawingMode ? "Exit drawing mode" : "Draw region to refine"}>
                  <ToggleButton
                    value="draw"
                    selected={isDrawingMode}
                    onChange={toggleDrawingMode}
                    size="small"
                    sx={{ borderRadius: 2 }}
                  >
                    <CropFreeIcon fontSize="small" />
                  </ToggleButton>
                </Tooltip>
              )}
            </Box>
            
            {imagePath ? (
              <Box
                sx={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 300,
                  position: 'relative',
                }}
              >
                <Box
                  sx={{
                    position: 'relative',
                    maxWidth: '100%',
                    maxHeight: '100%',
                    cursor: isDrawingMode ? 'crosshair' : 'default',
                  }}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                >
                  <Box
                    ref={imageRef}
                    component="img"
                    src={PipelineAPI.getFileUrl(runId, imagePath)}
                    sx={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                      borderRadius: 2,
                      border: 2,
                      borderColor: 'divider',
                      backgroundColor: 'white',
                      boxShadow: 2,
                      opacity: isDrawingMode ? 0.7 : 1,
                      transition: 'opacity 0.2s ease',
                    }}
                    draggable={false}
                  />
                  
                  {/* Mask overlay */}
                  {maskCoordinates && imageRef.current && (
                    <Box
                      sx={{
                        position: 'absolute',
                        left: `${maskCoordinates.x * 100}%`,
                        top: `${maskCoordinates.y * 100}%`,
                        width: `${maskCoordinates.width * 100}%`,
                        height: `${maskCoordinates.height * 100}%`,
                        border: '2px dashed #2196f3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        pointerEvents: 'none',
                      }}
                    />
                  )}
                </Box>
              </Box>
            ) : (
              <Box sx={{ 
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'column',
                color: 'text.secondary'
              }}>
                <ImageIcon sx={{ fontSize: 64, mb: 2 }} />
                <Typography variant="body1">Image not available</Typography>
              </Box>
            )}
            
            {maskCoordinates && tabValue === 2 && (
              <Box sx={{ mt: 2 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip 
                    label="Region Selected" 
                    color="primary" 
                    size="small" 
                    variant="outlined"
                  />
                  <Button 
                    size="small" 
                    onClick={clearMask}
                    sx={{ fontSize: '0.7rem' }}
                  >
                    Clear
                  </Button>
                </Stack>
              </Box>
            )}
          </Box>

          {/* Right side - Refinement Options */}
          <Box sx={{ width: '60%', display: 'flex', flexDirection: 'column' }}>
            {/* Refinement Type Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3, pt: 2 }}>
              <Tabs
                value={tabValue}
                onChange={handleTabChange}
                variant="fullWidth"
                sx={{ 
                  '& .MuiTab-root': {
                    fontWeight: 500,
                    textTransform: 'none',
                    fontSize: '0.95rem',
                  }
                }}
              >
                <Tab 
                  icon={getTabIcon(0)} 
                  label="Subject Repair" 
                  iconPosition="start"
                />
                <Tab 
                  icon={getTabIcon(1)} 
                  label="Text Repair" 
                  iconPosition="start"
                />
                <Tab 
                  icon={getTabIcon(2)} 
                  label="Prompt Refinement" 
                  iconPosition="start"
                />
              </Tabs>
            </Box>

            {/* Tab Content */}
            <Box sx={{ flex: 1, p: 3 }}>
              {/* Subject Repair Tab */}
              <TabPanel value={tabValue} index={0}>
                <Stack spacing={3}>
                  <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      Replace or modify the main subject while preserving background and composition
                    </Typography>
                  </Alert>
                  
                  <TextField
                    fullWidth
                    label="What would you like to change about the subject?"
                    multiline
                    rows={3}
                    value={subjectInstructions}
                    onChange={(e) => setSubjectInstructions(e.target.value)}
                    placeholder="e.g., 'Replace the burger with a pizza', 'Make the person younger', 'Change to a different product'"
                    variant="outlined"
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 2,
                      }
                    }}
                  />

                  <Box>
                    <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, mb: 1 }}>
                      Reference Image (Optional)
                    </Typography>
                    <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                      Upload a reference image to guide the subject replacement
                    </Typography>
                    
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleReferenceImageUpload}
                      style={{ display: 'none' }}
                    />
                    
                    <Stack direction="row" spacing={2} alignItems="center">
                      <Button
                        variant="outlined"
                        startIcon={<CloudUploadIcon />}
                        onClick={() => fileInputRef.current?.click()}
                        sx={{ fontWeight: 500, borderRadius: 2 }}
                      >
                        Choose Image
                      </Button>
                      
                      {referenceImage && (
                        <Chip 
                          label={referenceImage.name}
                          onDelete={() => setReferenceImage(null)}
                          color="success"
                          variant="outlined"
                          sx={{ maxWidth: 200 }}
                        />
                      )}
                    </Stack>
                  </Box>
                </Stack>
              </TabPanel>

              {/* Text Repair Tab */}
              <TabPanel value={tabValue} index={1}>
                <Stack spacing={3}>
                  <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      Fix spelling errors, improve text clarity, and enhance text rendering quality
                    </Typography>
                  </Alert>
                  
                  <TextField
                    fullWidth
                    label="What text issues would you like to fix?"
                    multiline
                    rows={4}
                    value={textInstructions}
                    onChange={(e) => setTextInstructions(e.target.value)}
                    placeholder="e.g., 'Fix spelling errors in the headline', 'Make the text more readable', 'Improve font clarity and contrast'"
                    variant="outlined"
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 2,
                      }
                    }}
                  />
                </Stack>
              </TabPanel>

              {/* Prompt Refinement Tab */}
              <TabPanel value={tabValue} index={2}>
                <Stack spacing={3}>
                  <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      Apply global or regional enhancements to improve overall image quality and appearance
                    </Typography>
                  </Alert>
                  
                  <TextField
                    fullWidth
                    label="How would you like to enhance the image?"
                    multiline
                    rows={4}
                    value={promptInstructions}
                    onChange={(e) => setPromptInstructions(e.target.value)}
                    placeholder="e.g., 'Add warm sunset lighting', 'Enhance colors and contrast', 'Improve image sharpness', 'Add depth of field effect'"
                    variant="outlined"
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 2,
                      }
                    }}
                  />

                  {/* Regional Editing Instructions */}
                  <Paper sx={{ p: 3, backgroundColor: 'success.light', borderRadius: 2, border: 1, borderColor: 'success.main' }}>
                    <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, color: 'success.dark' }}>
                      Regional Editing Available
                    </Typography>
                    <Typography variant="body2" color="success.dark" sx={{ mb: 1 }}>
                      Click the <CropFreeIcon sx={{ fontSize: 16, mx: 0.5 }} /> button to select a specific region of the image to refine.
                    </Typography>
                    <Typography variant="body2" color="success.dark">
                      {maskCoordinates ? 
                        "Region selected! The refinement will be applied only to the selected area." :
                        "No region selected. The refinement will be applied globally."
                      }
                    </Typography>
                  </Paper>
                </Stack>
              </TabPanel>
            </Box>
          </Box>
        </Box>
      </DialogContent>

      <DialogActions sx={{ 
        px: 3, 
        py: 2,
        borderTop: 1,
        borderColor: 'divider',
        backgroundColor: 'grey.50',
        borderRadius: '0 0 12px 12px',
        gap: 1
      }}>
        <Button 
          onClick={handleClose} 
          variant="outlined"
          disabled={isSubmitting}
          sx={{ 
            fontWeight: 500,
            borderRadius: 2,
            px: 3
          }}
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit}
          variant="contained"
          disabled={!isFormValid() || isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} /> : <AutoFixHighIcon />}
          sx={{ 
            fontWeight: 500,
            borderRadius: 2,
            px: 3,
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            '&:hover': {
              background: 'linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%)',
            }
          }}
        >
          {isSubmitting ? 'Starting Refinement...' : 'Start Refinement'}
        </Button>
      </DialogActions>
    </Dialog>
  );
} 