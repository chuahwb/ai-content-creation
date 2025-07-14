'use client';

import React, { useState, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Alert,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Stack,
  ToggleButton,
  Divider,
} from '@mui/material';
import {
  Close as CloseIcon,
  AutoFixHigh as AutoFixHighIcon,
  CloudUpload as CloudUploadIcon,
  Brush as BrushIcon,
  Image as ImageIcon,
  Info as InfoIcon,
  CropFree as CropFreeIcon,
  BuildCircle as BuildCircleIcon,
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

interface MaskCoordinate {
  x: number;
  y: number;
  width: number;
  height: number;
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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRepairSubmitting, setIsRepairSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  // Form state
  const [promptInstructions, setPromptInstructions] = useState('');
  const [referenceImage, setReferenceImage] = useState<File | null>(null);
  
  // Regional editing state
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [maskCoordinates, setMaskCoordinates] = useState<MaskCoordinate | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);

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

  const generateMaskFile = async (): Promise<File | null> => {
    if (!maskCoordinates || !imageRef.current) return null;
    
    try {
      const img = imageRef.current;
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        throw new Error('Could not get canvas context');
      }
      
      // Set canvas size to match the actual image dimensions
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      
      // Fill with black (preserve area)
      ctx.fillStyle = 'black';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      
      // Draw white rectangle for edit area
      ctx.fillStyle = 'white';
      const x = maskCoordinates.x * canvas.width;
      const y = maskCoordinates.y * canvas.height;
      const width = maskCoordinates.width * canvas.width;
      const height = maskCoordinates.height * canvas.height;
      
      ctx.fillRect(x, y, width, height);
      
      // Convert canvas to blob
      return new Promise((resolve) => {
        canvas.toBlob((blob) => {
          if (blob) {
            const file = new File([blob], 'mask.png', { type: 'image/png' });
            resolve(file);
          } else {
            resolve(null);
          }
        }, 'image/png');
      });
    } catch (error) {
      console.error('Error generating mask file:', error);
      toast.error('Failed to generate mask file');
      return null;
    }
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

      // Prompt refinement fields
      formData.append('refine_type', 'prompt');
      formData.append('prompt', promptInstructions || 'Enhance the overall image quality and appeal');
      
      // Add optional reference image
      if (referenceImage) {
        formData.append('reference_image', referenceImage);
      }
      
      // Generate and attach mask file if coordinates are provided
      if (maskCoordinates) {
        const maskFile = await generateMaskFile();
        if (maskFile) {
          formData.append('mask_file', maskFile);
        } else {
          toast.error('Failed to generate mask file. Proceeding with global enhancement.');
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

  const handleRepair = async () => {
    setIsRepairSubmitting(true);
    
    try {
      const formData = new FormData();
      
      // Common fields for subject repair
      if (parentRefinementJobId) {
        // Chain refinement: repairing a refined image
        formData.append('parent_image_id', parentRefinementJobId);
        formData.append('parent_image_type', 'refinement');
      } else {
        // Original refinement: repairing a generated image
        formData.append('parent_image_id', `image_${imageIndex}`);
        formData.append('parent_image_type', 'original');
        formData.append('generation_index', imageIndex?.toString() || '0');
      }

      // Subject repair fields (completely input-free)
      formData.append('refine_type', 'subject');
      // Note: No instructions needed - subject repair is fully automatic

      // Submit repair request
      const result = await PipelineAPI.submitRefinement(runId, formData);
      
      toast.success('Quick repair started! Check progress in real-time.');
      onRefinementSubmit(result);
      handleClose();
      
    } catch (error: any) {
      console.error('Repair submission error:', error);
      
      // Provide specific error messages for common subject repair issues
      if (error.message && error.message.includes('reference image')) {
        toast.error('Quick repair is not available - no reference image was used during generation');
      } else if (error.message && error.message.includes('not available')) {
        toast.error('Quick repair is not available for this image');
      } else {
        toast.error(error.message || 'Failed to start repair');
      }
    } finally {
      setIsRepairSubmitting(false);
    }
  };

  const handleClose = () => {
    // Reset form state
    setPromptInstructions('');
    setReferenceImage(null);
    setIsDrawingMode(false);
    setMaskCoordinates(null);
    setIsDrawing(false);
    setStartPoint(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  const isFormValid = () => {
    return promptInstructions.trim().length > 0;
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
          height: '85vh',
          maxHeight: '85vh',
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
              minHeight: '40px',
            }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Current Image
              </Typography>
              <Box sx={{ width: '40px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Tooltip title={isDrawingMode ? "Exit drawing mode" : "Draw region to refine"}>
                  <ToggleButton
                    value="draw"
                    selected={isDrawingMode}
                    onChange={toggleDrawingMode}
                    size="small"
                    sx={{ 
                      borderRadius: 2,
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        backgroundColor: 'primary.light',
                        transform: 'scale(1.05)',
                      }
                    }}
                  >
                    <CropFreeIcon fontSize="small" />
                  </ToggleButton>
                </Tooltip>
              </Box>
            </Box>
            
            {imagePath ? (
              <>
                <Box
                  sx={{
                    height: 'calc(100% - 80px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    position: 'relative',
                    overflow: 'hidden',
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 2,
                    backgroundColor: 'white',
                    transition: 'all 0.3s ease',
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
                        animation: 'pulse 2s infinite',
                      } : {},
                    }}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
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
                        pointerEvents: 'none',
                      }}
                      draggable={false}
                    />
                    
                    {/* Mask overlay */}
                    {maskCoordinates && imageRef.current && (
                      (() => {
                        const img = imageRef.current;
                        if (!img || !img.parentElement) return null;
                        
                        const containerRect = img.parentElement.getBoundingClientRect();
                        const containerWidth = containerRect.width;
                        const containerHeight = containerRect.height;
                        const imageAspectRatio = img.naturalWidth / img.naturalHeight;
                        const containerAspectRatio = containerWidth / containerHeight;
                        
                        let displayedWidth, displayedHeight, offsetX, offsetY;
                        
                        if (imageAspectRatio > containerAspectRatio) {
                          displayedWidth = containerWidth;
                          displayedHeight = containerWidth / imageAspectRatio;
                          offsetX = 0;
                          offsetY = (containerHeight - displayedHeight) / 2;
                        } else {
                          displayedHeight = containerHeight;
                          displayedWidth = containerHeight * imageAspectRatio;
                          offsetX = (containerWidth - displayedWidth) / 2;
                          offsetY = 0;
                        }
                        
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
                              animation: 'fadeIn 0.3s ease',
                            }}
                          />
                        );
                      })()
                    )}
                  </Box>
                </Box>
                
                <Box sx={{ 
                  height: '60px', 
                  mt: 1.5, 
                  display: 'flex',
                  alignItems: 'flex-start',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {maskCoordinates ? (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip 
                        label="Region Selected" 
                        color="primary" 
                        size="small" 
                        variant="outlined"
                        sx={{ animation: 'fadeIn 0.3s ease' }}
                      />
                      <Button 
                        size="small" 
                        onClick={clearMask}
                        sx={{ 
                          fontSize: '0.7rem',
                          transition: 'all 0.2s ease',
                          '&:hover': {
                            transform: 'scale(1.05)',
                          }
                        }}
                      >
                        Clear
                      </Button>
                    </Stack>
                  ) : (
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
            <Box sx={{ 
              flex: 1, 
              p: 3, 
              overflow: 'auto',
              minHeight: 0,
            }}>
              <Stack spacing={3}>
                <Alert severity="info" icon={<InfoIcon />} sx={{ py: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
                    Apply global or regional enhancements to improve overall image quality and appearance
                  </Typography>
                </Alert>
                
                <TextField
                  fullWidth
                  label="How would you like to enhance the image? *"
                  multiline
                  rows={3}
                  value={promptInstructions}
                  onChange={(e) => setPromptInstructions(e.target.value)}
                  placeholder="e.g., 'Add warm sunset lighting', 'Enhance colors and contrast', 'Improve image sharpness'"
                  variant="outlined"
                  required
                  sx={{
                    '& .MuiOutlinedInput-root': {
                      borderRadius: 2,
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                      },
                      '&.Mui-focused': {
                        boxShadow: '0 4px 12px rgba(102, 126, 234, 0.2)',
                      }
                    }
                  }}
                />

                <Box>
                  <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, mb: 1, fontSize: '0.875rem' }}>
                    Reference Image (Optional)
                  </Typography>
                  <Typography variant="body2" color="textSecondary" sx={{ mb: 1.5, fontSize: '0.8rem', lineHeight: 1.3 }}>
                    Upload a reference image to guide the refinement process
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
                      sx={{ 
                        fontWeight: 500, 
                        borderRadius: 2, 
                        fontSize: '0.875rem',
                        transition: 'all 0.2s ease',
                        '&:hover': {
                          transform: 'translateY(-1px)',
                          boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
                        }
                      }}
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
                        sx={{ 
                          maxWidth: 180, 
                          fontSize: '0.75rem',
                          animation: 'fadeIn 0.3s ease'
                        }}
                      />
                    )}
                  </Stack>
                </Box>

                <Paper sx={{ 
                  p: 2, 
                  backgroundColor: 'success.light', 
                  borderRadius: 2, 
                  border: 1, 
                  borderColor: 'success.main',
                  transition: 'all 0.2s ease',
                }}>
                  <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                    <CropFreeIcon sx={{ fontSize: 16, color: 'success.dark' }} />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'success.dark', fontSize: '0.875rem' }}>
                      Regional Editing (Optional)
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
        justifyContent: 'space-between',
      }}>
        <Tooltip title="One-click repair using original reference image (only available if reference image was used during generation)">
          <Button 
            onClick={handleRepair}
            variant="outlined"
            disabled={isSubmitting || isRepairSubmitting}
            startIcon={isRepairSubmitting ? <CircularProgress size={18} /> : <BuildCircleIcon />}
            sx={{ 
              fontWeight: 600,
              borderRadius: 2,
              px: 3,
              py: 1,
              borderColor: 'warning.main',
              color: 'warning.dark',
              backgroundColor: 'warning.light',
              transition: 'all 0.2s ease',
              '&:hover': {
                backgroundColor: 'warning.main',
                color: 'white',
                transform: 'translateY(-1px)',
                boxShadow: '0 4px 12px rgba(237, 108, 2, 0.3)',
              },
              '&:disabled': {
                backgroundColor: 'grey.100',
                borderColor: 'grey.300',
                color: 'grey.500',
              }
            }}
          >
            {isRepairSubmitting ? 'Repairing...' : 'Quick Repair'}
          </Button>
        </Tooltip>
        
        <Stack direction="row" spacing={1}>
          <Button 
            onClick={handleClose} 
            variant="outlined"
            disabled={isSubmitting || isRepairSubmitting}
            sx={{ 
              fontWeight: 500,
              borderRadius: 2,
              px: 3,
              transition: 'all 0.2s ease',
              '&:hover': {
                transform: 'translateY(-1px)',
              }
            }}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit}
            variant="contained"
            disabled={!isFormValid() || isSubmitting || isRepairSubmitting}
            startIcon={isSubmitting ? <CircularProgress size={20} /> : <AutoFixHighIcon />}
            sx={{ 
              fontWeight: 500,
              borderRadius: 2,
              px: 3,
              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
              transition: 'all 0.2s ease',
              '&:hover': {
                background: 'linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%)',
                transform: 'translateY(-1px)',
                boxShadow: '0 6px 16px rgba(102, 126, 234, 0.3)',
              }
            }}
          >
            {isSubmitting ? 'Starting Refinement...' : 'Start Refinement'}
          </Button>
        </Stack>
      </DialogActions>

      <style jsx global>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </Dialog>
  );
} 