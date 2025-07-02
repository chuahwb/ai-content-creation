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
  parentRefinementJobId?: string; // For chain refinements
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
  parentRefinementJobId,
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
    
    const img = imageRef.current;
    const containerRect = img.parentElement?.getBoundingClientRect();
    if (!containerRect) return null;
    
    // Get actual displayed image dimensions (accounting for object-fit: contain)
    const containerWidth = containerRect.width;
    const containerHeight = containerRect.height;
    const imageAspectRatio = img.naturalWidth / img.naturalHeight;
    const containerAspectRatio = containerWidth / containerHeight;
    
    let displayedWidth, displayedHeight, offsetX, offsetY;
    
    if (imageAspectRatio > containerAspectRatio) {
      // Image is wider - constrained by width
      displayedWidth = containerWidth;
      displayedHeight = containerWidth / imageAspectRatio;
      offsetX = 0;
      offsetY = (containerHeight - displayedHeight) / 2;
    } else {
      // Image is taller - constrained by height  
      displayedHeight = containerHeight;
      displayedWidth = containerHeight * imageAspectRatio;
      offsetX = (containerWidth - displayedWidth) / 2;
      offsetY = 0;
    }
    
    // Calculate coordinates relative to the actual displayed image
    const x = (event.clientX - containerRect.left - offsetX) / displayedWidth;
    const y = (event.clientY - containerRect.top - offsetY) / displayedHeight;
    
    // Clamp coordinates to [0, 1] range
    const clampedX = Math.max(0, Math.min(1, x));
    const clampedY = Math.max(0, Math.min(1, y));
    
    return { x: clampedX, y: clampedY };
  };

  const handleMouseDown = (event: React.MouseEvent<HTMLElement>) => {
    if (!isDrawingMode) return;
    
    const coords = getImageCoordinates(event);
    if (coords && coords.x >= 0 && coords.x <= 1 && coords.y >= 0 && coords.y <= 1) {
      setIsDrawing(true);
      setStartPoint(coords);
      setMaskCoordinates(null);
      event.preventDefault();
    }
  };

  const handleMouseMove = (event: React.MouseEvent<HTMLElement>) => {
    if (!isDrawing || !startPoint || !isDrawingMode) return;
    
    const coords = getImageCoordinates(event);
    if (coords) {
      // Ensure coordinates stay within image bounds
      const clampedCoords = {
        x: Math.max(0, Math.min(1, coords.x)),
        y: Math.max(0, Math.min(1, coords.y))
      };
      
      const width = Math.abs(clampedCoords.x - startPoint.x);
      const height = Math.abs(clampedCoords.y - startPoint.y);
      const x = Math.min(startPoint.x, clampedCoords.x);
      const y = Math.min(startPoint.y, clampedCoords.y);
      
      // Only set mask if it meets minimum size requirements (at least 5% of image in each dimension)
      if (width >= 0.05 && height >= 0.05) {
        setMaskCoordinates({ x, y, width, height });
      }
      event.preventDefault();
    }
  };

  const handleMouseUp = (event: React.MouseEvent<HTMLElement>) => {
    if (isDrawing) {
      setIsDrawing(false);
      setStartPoint(null);
      event.preventDefault();
    }
  };

  const clearMask = () => {
    setMaskCoordinates(null);
  };

  const handleSubmit = async () => {
    setIsSubmitting(true);
    
    try {
      const formData = new FormData();
      
      // Common fields - handle chain refinements vs original refinements
      if (parentRefinementJobId) {
        // Chain refinement: refining a refined image
        formData.append('parent_image_id', parentRefinementJobId);
        formData.append('parent_image_type', 'refinement');
        // Don't set generation_index for chain refinements
      } else {
        // Original refinement: refining a generated image
        formData.append('parent_image_id', `image_${imageIndex}`);
        formData.append('parent_image_type', 'original');
        formData.append('generation_index', imageIndex?.toString() || '0');
      }

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
      const result = await PipelineAPI.submitRefinement(runId, formData);
      
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
          height: '80vh',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
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
        flexShrink: 0,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AutoFixHighIcon sx={{ fontSize: 28 }} />
          <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
            {parentRefinementJobId ? 'Refine Further' : `Refine Image - Option ${(imageIndex || 0) + 1}`}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} sx={{ color: 'white' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden' }}>
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
            height: '100%',
          }}>
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              mb: 2, 
              flexShrink: 0,
              minHeight: '40px', // Reserve consistent space for button area
            }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Current Image
              </Typography>
              {/* Always render button container to prevent layout shift */}
              <Box sx={{ width: '40px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
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
            </Box>
            
            {imagePath ? (
              <>
                {/* Fixed height image container to prevent layout shifts */}
                <Box
                  sx={{
                    height: 'calc(100% - 80px)', // Reserve space for buttons at bottom
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    overflow: 'hidden',
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 2,
                    backgroundColor: 'white',
                  }}
                >
                  <Box
                    sx={{
                      position: 'relative',
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: isDrawingMode ? 'crosshair' : 'default',
                      '&::before': isDrawingMode ? {
                        content: '""',
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: 'rgba(33, 150, 243, 0.05)',
                        border: '2px dashed rgba(33, 150, 243, 0.3)',
                        borderRadius: 1,
                        zIndex: 0,
                      } : {},
                    }}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp} // Stop drawing if mouse leaves container
                  >
                    <Box
                      ref={imageRef}
                      component="img"
                      src={PipelineAPI.getFileUrl(runId, imagePath)}
                      sx={{
                        maxWidth: '100%',
                        maxHeight: '100%',
                        width: 'auto',
                        height: 'auto',
                        objectFit: 'contain',
                        opacity: isDrawingMode ? 0.7 : 1,
                        transition: 'opacity 0.2s ease',
                        userSelect: 'none',
                        pointerEvents: 'none', // Let parent handle mouse events
                      }}
                      draggable={false}
                    />
                    
                    {/* Improved mask overlay with proper bounds */}
                    {maskCoordinates && imageRef.current && (
                      (() => {
                        const img = imageRef.current;
                        if (!img || !img.parentElement) return null;
                        
                        // Calculate actual displayed image dimensions and position
                        const containerRect = img.parentElement.getBoundingClientRect();
                        const containerWidth = containerRect.width;
                        const containerHeight = containerRect.height;
                        const imageAspectRatio = img.naturalWidth / img.naturalHeight;
                        const containerAspectRatio = containerWidth / containerHeight;
                        
                        let displayedWidth, displayedHeight, offsetX, offsetY;
                        
                        if (imageAspectRatio > containerAspectRatio) {
                          // Image is wider - constrained by width
                          displayedWidth = containerWidth;
                          displayedHeight = containerWidth / imageAspectRatio;
                          offsetX = 0;
                          offsetY = (containerHeight - displayedHeight) / 2;
                        } else {
                          // Image is taller - constrained by height
                          displayedHeight = containerHeight;
                          displayedWidth = containerHeight * imageAspectRatio;
                          offsetX = (containerWidth - displayedWidth) / 2;
                          offsetY = 0;
                        }
                        
                        // Convert normalized coordinates to pixel positions
                        const maskLeft = offsetX + (maskCoordinates.x * displayedWidth);
                        const maskTop = offsetY + (maskCoordinates.y * displayedHeight);
                        const maskWidth = maskCoordinates.width * displayedWidth;
                        const maskHeight = maskCoordinates.height * displayedHeight;
                        
                        return (
                          <Box
                            sx={{
                              position: 'absolute',
                              left: `${maskLeft}px`,
                              top: `${maskTop}px`,
                              width: `${maskWidth}px`,
                              height: `${maskHeight}px`,
                              border: '2px dashed #2196f3',
                              backgroundColor: 'rgba(33, 150, 243, 0.1)',
                              pointerEvents: 'none',
                              borderRadius: 1,
                            }}
                          />
                        );
                      })()
                    )}
                  </Box>
                </Box>
                
                {/* Always present button area to prevent layout shifts */}
                <Box sx={{ 
                  height: '60px', 
                  mt: 1.5, 
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {maskCoordinates && tabValue === 2 ? (
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
                  ) : (
                    // Invisible placeholder to maintain layout
                    <Box sx={{ height: '32px' }} />
                  )}
                </Box>
              </>
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
          </Box>

          {/* Right side - Refinement Options */}
          <Box sx={{ width: '60%', display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Refinement Type Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 3, pt: 2, flexShrink: 0 }}>
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
            <Box sx={{ 
              flex: 1, 
              p: 3, 
              overflow: 'auto',
              minHeight: 0, // Allow flex child to shrink
            }}>
              {/* Subject Repair Tab */}
              <TabPanel value={tabValue} index={0}>
                <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <Stack spacing={2.5}>
                    <Alert severity="info" icon={<InfoIcon />} sx={{ py: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
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
                      <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, mb: 1, fontSize: '0.875rem' }}>
                        Reference Image (Optional)
                      </Typography>
                      <Typography variant="body2" color="textSecondary" sx={{ mb: 1.5, fontSize: '0.8rem', lineHeight: 1.3 }}>
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
                          sx={{ fontWeight: 500, borderRadius: 2, fontSize: '0.875rem' }}
                        >
                          Choose Image
                        </Button>
                        
                        {referenceImage && (
                          <Chip 
                            label={referenceImage.name}
                            onDelete={() => setReferenceImage(null)}
                            color="success"
                            variant="outlined"
                            size="small"
                            sx={{ maxWidth: 180, fontSize: '0.75rem' }}
                          />
                        )}
                      </Stack>
                    </Box>
                  </Stack>
                </Box>
              </TabPanel>

              {/* Text Repair Tab */}
              <TabPanel value={tabValue} index={1}>
                <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <Stack spacing={2.5}>
                    <Alert severity="info" icon={<InfoIcon />} sx={{ py: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
                        Fix spelling errors, improve text clarity, and enhance text rendering quality
                      </Typography>
                    </Alert>
                    
                    <TextField
                      fullWidth
                      label="What text issues would you like to fix?"
                      multiline
                      rows={3}
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
                </Box>
              </TabPanel>

              {/* Prompt Refinement Tab - Optimized for no scrolling */}
              <TabPanel value={tabValue} index={2}>
                <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <Stack spacing={2.5}>
                    <Alert severity="info" icon={<InfoIcon />} sx={{ py: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
                        Apply global or regional enhancements to improve overall image quality and appearance
                      </Typography>
                    </Alert>
                    
                    <TextField
                      fullWidth
                      label="How would you like to enhance the image?"
                      multiline
                      rows={3}
                      value={promptInstructions}
                      onChange={(e) => setPromptInstructions(e.target.value)}
                      placeholder="e.g., 'Add warm sunset lighting', 'Enhance colors and contrast', 'Improve image sharpness'"
                      variant="outlined"
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          borderRadius: 2,
                        }
                      }}
                    />

                    {/* Regional Editing Instructions - Compact */}
                    <Paper sx={{ p: 2, backgroundColor: 'success.light', borderRadius: 2, border: 1, borderColor: 'success.main' }}>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <CropFreeIcon sx={{ fontSize: 16, color: 'success.dark' }} />
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'success.dark', fontSize: '0.875rem' }}>
                          Regional Editing Available
                        </Typography>
                      </Stack>
                      <Typography variant="body2" color="success.dark" sx={{ fontSize: '0.8rem', lineHeight: 1.3 }}>
                        {maskCoordinates ? 
                          "✓ Region selected! Refinement will be applied only to the selected area." :
                          "Click the draw button above to select a specific region, or leave unselected for global enhancement."
                        }
                      </Typography>
                    </Paper>
                  </Stack>
                </Box>
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
        gap: 1,
        flexShrink: 0,
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