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
  Tabs,
  Tab,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Slider,
  Alert,
  Paper,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  AutoFixHigh as AutoFixHighIcon,
  CloudUpload as CloudUploadIcon,
  Brush as BrushIcon,
  TextFields as TextFieldsIcon,
  Edit as EditIcon,
  Image as ImageIcon,
} from '@mui/icons-material';
import toast from 'react-hot-toast';

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

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`refinement-tabpanel-${index}`}
      aria-labelledby={`refinement-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
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

  // Form state
  const [subjectInstructions, setSubjectInstructions] = useState('');
  const [referenceImage, setReferenceImage] = useState<File | null>(null);
  const [textInstructions, setTextInstructions] = useState('');
  const [promptInstructions, setPromptInstructions] = useState('');
  const [creativityLevel, setCreativityLevel] = useState(2);
  const [maskCoordinates, setMaskCoordinates] = useState<any>(null);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
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

  const handleSubmit = async () => {
    setIsSubmitting(true);
    
    try {
      const formData = new FormData();
      
      // Common fields
      formData.append('parent_image_id', `image_${imageIndex}`);
      formData.append('parent_image_type', 'original');
      formData.append('generation_index', imageIndex?.toString() || '0');
      formData.append('creativity_level', creativityLevel.toString());

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
    setCreativityLevel(2);
    setMaskCoordinates(null);
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
      default: return <EditIcon />;
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
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2, minHeight: '70vh' }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 2,
        borderBottom: 1,
        borderColor: 'divider'
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <AutoFixHighIcon color="primary" sx={{ fontSize: 28 }} />
          <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
            Refine Image - Option {(imageIndex || 0) + 1}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} sx={{ color: 'grey.500' }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ px: 3, py: 0 }}>
        {/* Current Image Preview */}
        <Box sx={{ my: 3, textAlign: 'center' }}>
          <Typography variant="subtitle2" color="textSecondary" gutterBottom>
            Current Image
          </Typography>
          {imagePath && (
            <Box
              component="img"
              src={`/api/v1/files/${runId}/${imagePath}`}
              sx={{
                maxWidth: '100%',
                maxHeight: 200,
                objectFit: 'contain',
                borderRadius: 2,
                border: 1,
                borderColor: 'divider',
                backgroundColor: 'grey.50',
              }}
            />
          )}
        </Box>

        {/* Refinement Type Tabs */}
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{ borderBottom: 1, borderColor: 'divider', mb: 1 }}
        >
          <Tab 
            icon={getTabIcon(0)} 
            label="Subject Repair" 
            iconPosition="start"
            sx={{ fontWeight: 500 }}
          />
          <Tab 
            icon={getTabIcon(1)} 
            label="Text Repair" 
            iconPosition="start"
            sx={{ fontWeight: 500 }}
          />
          <Tab 
            icon={getTabIcon(2)} 
            label="Prompt Refinement" 
            iconPosition="start"
            sx={{ fontWeight: 500 }}
          />
        </Tabs>

        {/* Subject Repair Tab */}
        <TabPanel value={tabValue} index={0}>
          <Box sx={{ space: 3 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              <strong>Subject Repair:</strong> Replace or modify the main subject while preserving the background and overall composition.
            </Alert>
            
            <TextField
              fullWidth
              label="Refinement Instructions"
              multiline
              rows={3}
              value={subjectInstructions}
              onChange={(e) => setSubjectInstructions(e.target.value)}
              placeholder="Describe how you want to modify the main subject (e.g., 'Replace the burger with a pizza', 'Make the person younger', 'Change to a different product')"
              sx={{ mb: 3 }}
            />

            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
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
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Button
                  variant="outlined"
                  startIcon={<CloudUploadIcon />}
                  onClick={() => fileInputRef.current?.click()}
                  sx={{ fontWeight: 500 }}
                >
                  Choose Reference Image
                </Button>
                
                {referenceImage && (
                  <Chip 
                    label={referenceImage.name}
                    onDelete={() => setReferenceImage(null)}
                    color="success"
                    variant="outlined"
                  />
                )}
              </Box>
            </Box>
          </Box>
        </TabPanel>

        {/* Text Repair Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ space: 3 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              <strong>Text Repair:</strong> Fix spelling errors, improve text clarity, and enhance text rendering quality.
            </Alert>
            
            <TextField
              fullWidth
              label="Text Repair Instructions"
              multiline
              rows={4}
              value={textInstructions}
              onChange={(e) => setTextInstructions(e.target.value)}
              placeholder="Describe what text issues to fix (e.g., 'Fix spelling errors in the headline', 'Make the text more readable', 'Improve font clarity and contrast')"
              sx={{ mb: 3 }}
            />
          </Box>
        </TabPanel>

        {/* Prompt Refinement Tab */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ space: 3 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              <strong>Prompt Refinement:</strong> Apply global or regional enhancements to improve the overall image quality and appearance.
            </Alert>
            
            <TextField
              fullWidth
              label="Refinement Prompt"
              multiline
              rows={4}
              value={promptInstructions}
              onChange={(e) => setPromptInstructions(e.target.value)}
              placeholder="Describe the enhancements you want (e.g., 'Add warm sunset lighting', 'Enhance colors and contrast', 'Improve image sharpness', 'Add depth of field effect')"
              sx={{ mb: 3 }}
            />

            <Paper sx={{ p: 2, backgroundColor: 'grey.50', border: 1, borderColor: 'divider' }}>
              <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                Regional Editing (Advanced)
              </Typography>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Currently supports global editing. Regional masking will be available in a future update.
              </Typography>
              <Chip label="Global Editing" color="primary" variant="outlined" size="small" />
            </Paper>
          </Box>
        </TabPanel>

        {/* Creativity Level Slider */}
        <Box sx={{ mt: 4, p: 3, backgroundColor: 'grey.50', borderRadius: 2 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
            Creativity Level
          </Typography>
          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
            Control how much the refinement can change the original image
          </Typography>
          
          <Slider
            value={creativityLevel}
            onChange={(_, newValue) => setCreativityLevel(newValue as number)}
            aria-labelledby="creativity-level-slider"
            step={1}
            marks={[
              { value: 1, label: 'Conservative' },
              { value: 2, label: 'Balanced' },
              { value: 3, label: 'Creative' },
            ]}
            min={1}
            max={3}
            valueLabelDisplay="auto"
            sx={{ mt: 2 }}
          />
        </Box>
      </DialogContent>

      <DialogActions sx={{ 
        px: 3, 
        py: 2,
        borderTop: 1,
        borderColor: 'divider',
        gap: 1
      }}>
        <Button 
          onClick={handleClose} 
          variant="outlined"
          disabled={isSubmitting}
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSubmit}
          variant="contained"
          disabled={!isFormValid() || isSubmitting}
          startIcon={isSubmitting ? <CircularProgress size={20} /> : <AutoFixHighIcon />}
          sx={{ fontWeight: 500 }}
        >
          {isSubmitting ? 'Starting Refinement...' : 'Start Refinement'}
        </Button>
      </DialogActions>
    </Dialog>
  );
} 