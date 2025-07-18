'use client';

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Slider,
  Button,
  Grid,
  Alert,
  CircularProgress,
  Chip,
  Paper,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Send as SendIcon,
  Refresh as RefreshIcon,
  BookmarkAdd as BookmarkAddIcon,
  Palette as PaletteIcon,
  Style as StyleIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { PipelineFormData, PipelineRunResponse, BrandPresetResponse } from '@/types/api';
import { PipelineAPI } from '@/lib/api';
import PresetManagementModal from './PresetManagementModal';

// Common ISO-639-1 language codes for validation
const VALID_LANGUAGE_CODES = [
  'en', 'zh', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'pt', 'ru', 
  'ar', 'hi', 'th', 'vi', 'nl', 'sv', 'no', 'da', 'fi', 'pl',
  'tr', 'he', 'cs', 'hu', 'ro', 'bg', 'hr', 'sk', 'sl', 'et',
  'lv', 'lt', 'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'is', 'fo'
];

// Form validation schema
const formSchema = z.object({
  mode: z.enum(['easy_mode', 'custom_mode', 'task_specific_mode']),
  platform_name: z.string().min(1, 'Platform is required'),
  creativity_level: z.number().min(1).max(3),
  num_variants: z.number().min(1).max(6),
  prompt: z.string().optional(),
  task_type: z.string().optional(),
  task_description: z.string().optional(),
  branding_elements: z.string().optional(),
  image_file: z.any().optional(),
  image_instruction: z.string().optional(),
  render_text: z.boolean(),
  apply_branding: z.boolean(),
  marketing_audience: z.string().optional(),
  marketing_objective: z.string().optional(),
  marketing_voice: z.string().optional(),
  marketing_niche: z.string().optional(),
  language: z.string()
    .optional()
    .refine((val) => {
      if (!val || val === 'en' || val === 'zh') return true;
      // For custom languages, check if it's a valid ISO-639-1 code
      if (val.length === 2 && VALID_LANGUAGE_CODES.includes(val.toLowerCase())) {
        return true;
      }
      return false;
    }, {
      message: 'Please enter a valid 2-letter ISO-639-1 language code (e.g., es, fr, ja, de, it)',
    }),
});

interface PipelineFormProps {
  onRunStarted: (run: PipelineRunResponse) => void;
}

const creativityLabels = {
  1: 'Focused & Photorealistic',
  2: 'Impressionistic & Stylized',
  3: 'Abstract & Illustrative',
};

const platforms = [
  'Instagram Post (1:1 Square)',
  'Instagram Story/Reel (9:16 Vertical)',
  'Facebook Post (Mixed)',
  'Pinterest Pin (2:3 Vertical)',
  'Xiaohongshu (Red Note) (3:4 Vertical)',
];

const taskTypes = [
  '1. Product Photography',
  '2. Promotional Graphics & Announcements',
  '3. Store Atmosphere & Decor',
  '4. Menu Spotlights',
  '5. Cultural & Community Content',
  '6. Recipes & Food Tips',
  '7. Brand Story & Milestones',
  '8. Behind the Scenes Imagery',
];

export default function PipelineForm({ onRunStarted }: PipelineFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [showCustomLanguage, setShowCustomLanguage] = useState(false);
  
  // Preset-related state
  const [activePreset, setActivePreset] = useState<BrandPresetResponse | null>(null);
  const [isRecipeActive, setIsRecipeActive] = useState(false);
  const [presetModalOpen, setPresetModalOpen] = useState(false);
  const [recipeOverrides, setRecipeOverrides] = useState<Record<string, any>>({});

  // Add state for save template functionality after the existing state declarations
  // Save template dialog state
  const [saveTemplateDialogOpen, setSaveTemplateDialogOpen] = useState(false);
  const [saveTemplateName, setSaveTemplateName] = useState('');
  const [saveTemplateLoading, setSaveTemplateLoading] = useState(false);

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<PipelineFormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      mode: 'easy_mode',
      platform_name: '',
      creativity_level: 1,
      num_variants: 3,
      render_text: false,
      apply_branding: false,
      language: 'en',
    },
  });

  const selectedMode = watch('mode');
  const requiresTaskType = selectedMode === 'task_specific_mode';
  const showAdvancedFields = selectedMode !== 'easy_mode';
  
  // Check if form is valid for template saving
  const isFormValidForTemplate = () => {
    const currentValues = watch();
    const validation = validateFormData(currentValues);
    return validation.isValid;
  };

  // Get validation error message for tooltip
  const getValidationErrorMessage = () => {
    const currentValues = watch();
    const validation = validateFormData(currentValues);
    return validation.error || '';
  };

  // File upload handling
  const onDrop = (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      setUploadedFile(file);
      setValue('image_file', file);
      
      // Create preview URL
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      
      toast.success(`Image uploaded: ${file.name}`);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp'],
    },
    multiple: false,
    maxSize: 10 * 1024 * 1024, // 10MB
  });

  const removeImage = () => {
    setUploadedFile(null);
    setPreviewUrl(null);
    setValue('image_file', undefined);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
  };

  // Preset handling functions
  const handlePresetSelected = (preset: BrandPresetResponse) => {
    setActivePreset(preset);
    applyPresetToForm(preset);
    setPresetModalOpen(false);
    toast.success(`${preset.preset_type === 'INPUT_TEMPLATE' ? 'Template' : 'Recipe'} "${preset.name}" applied`);
  };

  const applyPresetToForm = (preset: BrandPresetResponse) => {
    if (preset.preset_type === 'INPUT_TEMPLATE') {
      // Apply Input Template: Clear form first, then populate with template data
      const inputData = preset.input_snapshot;
      
      // First, reset form to clean state to avoid hybrid templates (but keep preset state)
      resetFormToDefaults(false);
      
      if (inputData) {
        // Use setTimeout to ensure proper form state transition and avoid placeholder overlap
        setTimeout(() => {
          // Now populate with template data - this ensures clean application
          setValue('mode', inputData.mode || 'easy_mode');
          setValue('prompt', inputData.prompt || '');
          setValue('creativity_level', inputData.creativity_level || 1);
          setValue('platform_name', inputData.platform_name || '');
          setValue('num_variants', inputData.num_variants || 3);
          setValue('task_type', inputData.task_type || '');
          setValue('task_description', inputData.task_description || '');
          setValue('branding_elements', inputData.branding_elements || '');
          setValue('render_text', inputData.render_text || false);
          setValue('apply_branding', inputData.apply_branding || false);
          setValue('language', inputData.language || 'en');
          setValue('marketing_audience', inputData.marketing_audience || '');
          setValue('marketing_objective', inputData.marketing_objective || '');
          setValue('marketing_voice', inputData.marketing_voice || '');
          setValue('marketing_niche', inputData.marketing_niche || '');
          setValue('image_instruction', inputData.image_instruction || '');
        }, 0);
      }
      setIsRecipeActive(false);
    } else if (preset.preset_type === 'STYLE_RECIPE') {
      // Apply Style Recipe: enter Recipe Active mode
      setIsRecipeActive(true);
      setRecipeOverrides({});
      
      // Clear form for recipe mode (user will provide new input)
      reset({
        mode: 'easy_mode',
        platform_name: '',
        creativity_level: 1,
        num_variants: 3,
        render_text: false,
        apply_branding: false,
        language: 'en',
      });
    }
  };

  const clearPreset = () => {
    setActivePreset(null);
    setIsRecipeActive(false);
    setRecipeOverrides({});
    toast.success('Preset cleared');
  };

  const handleRecipeOverride = (field: string, value: any) => {
    setRecipeOverrides(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Shared validation logic for both pipeline run and template saving
  const validateFormData = (data: PipelineFormData): { isValid: boolean; error?: string } => {
    // Validate required fields
    if (!data.platform_name) {
      return { isValid: false, error: 'Platform selection is required' };
    }
    
    if (selectedMode === 'easy_mode' && !data.prompt && !uploadedFile) {
      return { isValid: false, error: 'Easy mode requires either a prompt or an image' };
    }
    
    if (requiresTaskType && !data.task_type) {
      return { isValid: false, error: 'Task type is required for task-specific mode' };
    }

    return { isValid: true };
  };

  const onSubmit = async (data: PipelineFormData) => {
    setIsSubmitting(true);
    
    try {
      // Validate required fields using shared validation
      const validation = validateFormData(data);
      if (!validation.isValid) {
        throw new Error(validation.error);
      }

      // Add preset data if active - only send preset_id and overrides for STYLE_RECIPE
      const submitData = {
        ...data,
        preset_id: activePreset?.preset_type === 'STYLE_RECIPE' ? activePreset.id : undefined,
        preset_type: activePreset?.preset_type,
        overrides: (activePreset?.preset_type === 'STYLE_RECIPE' && isRecipeActive) ? recipeOverrides : undefined,
      };

      // Submit the run
      const response = await PipelineAPI.submitRun(submitData);
      
      toast.success('Pipeline run started successfully!');
      
      // Navigate FIRST to avoid disrupting WebSocket connection initialization
      onRunStarted(response);
      
      // Mark successful submission for form reset when user returns
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem('lastFormSubmission', Date.now().toString());
      }
      
    } catch (error: any) {
      console.error('Failed to submit run:', error);
      toast.error(error.message || 'Failed to start pipeline run');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Shared function to properly reset form to clean state
  const resetFormToDefaults = (clearPresets = true) => {
    reset({
      mode: 'easy_mode',
      platform_name: '',
      creativity_level: 1,
      num_variants: 3,
      prompt: '', // Clear prompt field with empty string
      task_type: '',
      task_description: '',
      branding_elements: '',
      image_instruction: '',
      render_text: false,
      apply_branding: false,
      marketing_audience: '',
      marketing_objective: '',
      marketing_voice: '',
      marketing_niche: '',
      language: 'en',
    });
    
    // Clear uploaded image
    removeImage();
    
    // Clear custom language state
    setShowCustomLanguage(false);
    
    // Only clear presets if requested (not when switching templates)
    if (clearPresets) {
      setActivePreset(null);
      setIsRecipeActive(false);
      setRecipeOverrides({});
    }
  };

  const handleReset = () => {
    resetFormToDefaults(true); // Clear presets when manually resetting
    toast.success('Form reset');
  };

  // Add save template dialog functions after the existing preset handling functions
  const openSaveTemplateDialog = () => {
    setSaveTemplateName('');
    setSaveTemplateDialogOpen(true);
  };

  const closeSaveTemplateDialog = () => {
    setSaveTemplateDialogOpen(false);
    setSaveTemplateName('');
    setSaveTemplateLoading(false);
  };

  const handleSaveTemplate = async () => {
    if (!saveTemplateName.trim()) return;

    setSaveTemplateLoading(true);
    try {
      // Get current form values
      const currentValues = watch();
      
      // Validate form data before saving template
      const validation = validateFormData(currentValues);
      if (!validation.isValid) {
        throw new Error(validation.error);
      }
      
      // Create input snapshot from current form state
      const inputSnapshot = {
        mode: currentValues.mode, // Include mode field
        prompt: currentValues.prompt || '',
        creativity_level: currentValues.creativity_level,
        platform_name: currentValues.platform_name,
        num_variants: currentValues.num_variants,
        render_text: currentValues.render_text,
        apply_branding: currentValues.apply_branding,
        language: currentValues.language || 'en',
        task_type: currentValues.task_type || null,
        task_description: currentValues.task_description || null,
        branding_elements: currentValues.branding_elements || null,
        image_instruction: currentValues.image_instruction || null,
        marketing_audience: currentValues.marketing_audience || null,
        marketing_objective: currentValues.marketing_objective || null,
        marketing_voice: currentValues.marketing_voice || null,
        marketing_niche: currentValues.marketing_niche || null,
      };

      // Save as INPUT_TEMPLATE preset
      await PipelineAPI.createBrandPreset({
        name: saveTemplateName.trim(),
        preset_type: 'INPUT_TEMPLATE',
        input_snapshot: inputSnapshot,
        model_id: 'current-pipeline',
        pipeline_version: '1.0.0',
      });
      
      toast.success('Template saved successfully!');
      closeSaveTemplateDialog();
    } catch (error: any) {
      console.error('Failed to save template:', error);
      toast.error(error.message || 'Failed to save template');
    } finally {
      setSaveTemplateLoading(false);
    }
  };

  // Check if user is returning from a successful submission when component mounts/becomes visible
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const lastSubmission = window.sessionStorage.getItem('lastFormSubmission');
      if (lastSubmission) {
        // User is returning from a results page, reset the form
        resetFormToDefaults(true);
        // Clear the session storage flag
        window.sessionStorage.removeItem('lastFormSubmission');
      }
    }
  }, []); // Only run on mount

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card elevation={1} sx={{ maxWidth: 1400, mx: 'auto' }}>
        <CardContent sx={{ p: 4 }}>
          {/* Header */}
          <Typography variant="h4" gutterBottom sx={{ fontWeight: 600, mb: 4, textAlign: 'center', letterSpacing: '-0.02em' }}>
            Create New Pipeline Run
          </Typography>

          {/* Preset Section */}
          <Box sx={{ mb: 4 }}>
            {!activePreset ? (
              // Simple load button when no preset is active
              <Box display="flex" justifyContent={{ xs: 'flex-start', md: 'flex-end' }} sx={{ mb: 2 }}>
                <Button
                  variant="outlined"
                  onClick={() => setPresetModalOpen(true)}
                  startIcon={<BookmarkAddIcon />}
                >
                  Load Preset
                </Button>
              </Box>
            ) : (
              // Full section when preset is active
              <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} md={6}>
                  <Typography variant="h6" gutterBottom>
                    Brand Presets & Style Memory
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Use saved templates or style recipes to speed up your creative process
                  </Typography>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Box display="flex" gap={2} justifyContent={{ xs: 'flex-start', md: 'flex-end' }}>
                    <Button
                      variant="outlined"
                      onClick={() => setPresetModalOpen(true)}
                      startIcon={<BookmarkAddIcon />}
                    >
                      Load Preset
                    </Button>
                  </Box>
                </Grid>
              </Grid>
            )}

            {/* Active Preset Display */}
            {activePreset && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Alert 
                  severity="info" 
                  sx={{ mt: 2 }}
                  action={
                    <Button size="small" onClick={clearPreset}>
                      Clear
                    </Button>
                  }
                >
                  <Box display="flex" alignItems="center" gap={1}>
                    {activePreset.preset_type === 'INPUT_TEMPLATE' ? <PaletteIcon /> : <StyleIcon />}
                    <Typography variant="body2">
                      <strong>{activePreset.preset_type === 'INPUT_TEMPLATE' ? 'Template' : 'Recipe'}</strong> 
                      &quot;{activePreset.name}&quot; is active
                    </Typography>
                  </Box>
                </Alert>
              </motion.div>
            )}

            {/* Recipe Active Mode */}
            {isRecipeActive && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Paper sx={{ p: 3, mt: 2, bgcolor: 'primary.50', border: 1, borderColor: 'primary.200' }}>
                  <Typography variant="h6" gutterBottom color="primary">
                    🎨 Recipe Active Mode
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    Choose how to use this style recipe:
                  </Typography>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Paper sx={{ p: 2, border: 1, borderColor: 'divider' }}>
                        <Typography variant="subtitle1" gutterBottom>
                          🖼️ Path A: Swap the Subject
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Upload a new image to apply this style recipe to a different subject
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={12} md={6}>
                      <Paper sx={{ p: 2, border: 1, borderColor: 'divider' }}>
                        <Typography variant="subtitle1" gutterBottom>
                          ✏️ Path B: Create with Style
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Write a new prompt to create something new with this style
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                </Paper>
              </motion.div>
            )}
          </Box>
          
          <form onSubmit={handleSubmit(onSubmit)}>
            {/* Main Content - Left/Right Split */}
            <Grid container spacing={4}>
              {/* LEFT SIDE - All Basic Components */}
              <Grid item xs={12} lg={7}>
                <Box sx={{ pr: { lg: 2 } }}>
                  {/* Mode & Platform & Language Row */}
                  <Grid container spacing={3} sx={{ mb: 4 }}>
                    <Grid item xs={12} md={4}>
                      <FormControl fullWidth>
                        <InputLabel>Mode</InputLabel>
                        <Controller
                          name="mode"
                          control={control}
                          render={({ field }) => (
                            <Select {...field} label="Mode">
                              <MenuItem value="easy_mode">Easy Mode</MenuItem>
                              <MenuItem value="custom_mode">Custom Mode</MenuItem>
                              <MenuItem value="task_specific_mode">Task-Specific Mode</MenuItem>
                            </Select>
                          )}
                        />
                      </FormControl>
                    </Grid>

                    <Grid item xs={12} md={4}>
                      <FormControl fullWidth required>
                        <InputLabel>Target Platform</InputLabel>
                        <Controller
                          name="platform_name"
                          control={control}
                          render={({ field }) => (
                            <Select {...field} label="Target Platform" error={!!errors.platform_name}>
                              {platforms.map((platform) => (
                                <MenuItem key={platform} value={platform}>
                                  {platform}
                                </MenuItem>
                              ))}
                            </Select>
                          )}
                        />
                      </FormControl>
                      {errors.platform_name && (
                        <Typography color="error" variant="caption" sx={{ mt: 0.5, display: 'block' }}>
                          {errors.platform_name.message}
                        </Typography>
                      )}
                    </Grid>

                    <Grid item xs={12} md={4}>
                      <FormControl fullWidth>
                        <InputLabel>Output Language</InputLabel>
                        <Controller
                          name="language"
                          control={control}
                          render={({ field }) => (
                            <Select 
                              {...field} 
                              label="Output Language"
                              onChange={(e) => {
                                const value = e.target.value;
                                if (value === 'other') {
                                  setShowCustomLanguage(true);
                                  field.onChange(''); // Clear the language field for custom input
                                } else {
                                  setShowCustomLanguage(false);
                                  field.onChange(value);
                                }
                              }}
                              value={showCustomLanguage ? 'other' : field.value}
                            >
                              <MenuItem value="en">
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography>English</Typography>
                                  <Chip label="Default" size="small" color="primary" sx={{ ml: 1 }} />
                                </Box>
                              </MenuItem>
                              <MenuItem value="zh">
                                <Typography>中文 | Chinese</Typography>
                              </MenuItem>
                              <MenuItem value="other">
                                <Typography>Other Language</Typography>
                              </MenuItem>
                            </Select>
                          )}
                        />
                      </FormControl>
                      <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5, display: 'block', fontSize: '0.75rem' }}>
                        Controls text on images & captions
                      </Typography>
                    </Grid>
                  </Grid>

                  {/* Conditional Fields Row - Task Type & Custom Language */}
                  {(requiresTaskType || showCustomLanguage) && (
                    <Grid container spacing={3} sx={{ mb: 4 }}>
                      {requiresTaskType && (
                        <Grid item xs={12} md={6}>
                          <FormControl fullWidth required>
                            <InputLabel>Task Type</InputLabel>
                            <Controller
                              name="task_type"
                              control={control}
                              render={({ field }) => (
                                <Select {...field} label="Task Type" error={!!errors.task_type}>
                                  {taskTypes.map((taskType) => (
                                    <MenuItem key={taskType} value={taskType}>
                                      {taskType}
                                    </MenuItem>
                                  ))}
                                </Select>
                              )}
                            />
                          </FormControl>
                          {errors.task_type && (
                            <Typography color="error" variant="caption" sx={{ mt: 0.5, display: 'block' }}>
                              {errors.task_type.message}
                            </Typography>
                          )}
                        </Grid>
                      )}

                      {showCustomLanguage && (
                        <Grid item xs={12} md={requiresTaskType ? 6 : 4}>
                          <Controller
                            name="language"
                            control={control}
                            render={({ field }) => (
                              <TextField
                                fullWidth
                                size="medium"
                                label="Custom Language Code"
                                placeholder="Enter ISO-639-1 code (e.g., es, fr, ja)"
                                value={field.value || ''}
                                onChange={(e) => field.onChange(e.target.value.toLowerCase())}
                                error={!!errors.language}
                                helperText={errors.language?.message || "Examples: es (Spanish), fr (French), ja (Japanese)"}
                                autoFocus
                              />
                            )}
                          />
                        </Grid>
                      )}
                    </Grid>
                  )}

                  {/* Generation Settings */}
                  <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 3 }}>
                      Generation Settings
                    </Typography>
                    <Grid container spacing={4}>
                      {/* Creativity Level */}
                      <Grid item xs={12} md={6}>
                        <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 500, mb: 2 }}>
                          Style: {creativityLabels[watch('creativity_level') as keyof typeof creativityLabels]}
                        </Typography>
                        <Controller
                          name="creativity_level"
                          control={control}
                          render={({ field }) => (
                            <Slider
                              {...field}
                              min={1}
                              max={3}
                              step={1}
                              marks={[
                                { value: 1, label: 'Focused' },
                                { value: 2, label: 'Stylized' },
                                { value: 3, label: 'Abstract' },
                              ]}
                              valueLabelDisplay="off"
                              sx={{ 
                                mx: 2,
                                '& .MuiSlider-mark': {
                                  backgroundColor: 'currentColor'
                                },
                                '& .MuiSlider-markLabel': {
                                  fontSize: '0.75rem',
                                  fontWeight: 500
                                }
                              }}
                            />
                          )}
                        />
                      </Grid>

                      {/* Number of Variants */}
                      <Grid item xs={12} md={6}>
                        <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 500, mb: 2 }}>
                          Variants: {watch('num_variants')}
                        </Typography>
                        <Controller
                          name="num_variants"
                          control={control}
                          render={({ field }) => (
                            <Slider
                              {...field}
                              min={1}
                              max={6}
                              step={1}
                              marks={[
                                { value: 1, label: '1' },
                                { value: 2, label: '2' },
                                { value: 3, label: '3' },
                                { value: 4, label: '4' },
                                { value: 5, label: '5' },
                                { value: 6, label: '6' },
                              ]}
                              valueLabelDisplay="off"
                              sx={{ 
                                mx: 2,
                                '& .MuiSlider-mark': {
                                  backgroundColor: 'currentColor'
                                },
                                '& .MuiSlider-markLabel': {
                                  fontSize: '0.75rem',
                                  fontWeight: 500
                                }
                              }}
                            />
                          )}
                        />
                      </Grid>
                    </Grid>
                    <Typography variant="body2" color="textSecondary" sx={{ mt: 1, fontSize: '0.875rem' }}>
                      Choose your creative style and how many different options to generate
                    </Typography>
                  </Box>

                  {/* Prompt */}
                  <Box sx={{ mb: 4 }}>
                    <Controller
                      name="prompt"
                      control={control}
                      render={({ field }) => (
                        <TextField
                          {...field}
                          key={`prompt-${activePreset?.id || 'default'}`} // Force re-render when preset changes
                          fullWidth
                          multiline
                          rows={4}
                          label="Prompt"
                          placeholder="Describe your product or what you want to generate... (e.g., 'roti canai, cartoon style')"
                          error={!!errors.prompt}
                          helperText={errors.prompt?.message}
                        />
                      )}
                    />
                  </Box>

                  {/* Image Upload */}
                  <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
                      Reference Image (Optional)
                    </Typography>
                    
                    {!uploadedFile ? (
                      <Paper
                        {...getRootProps()}
                        sx={{
                          p: 3,
                          border: 2,
                          borderStyle: 'dashed',
                          borderColor: isDragActive ? 'primary.main' : 'grey.300',
                          backgroundColor: isDragActive ? 'primary.50' : 'grey.50',
                          cursor: 'pointer',
                          textAlign: 'center',
                          minHeight: 160,
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'center',
                          alignItems: 'center',
                          borderRadius: 2,
                          transition: 'all 0.2s ease-in-out',
                          '&:hover': {
                            borderColor: 'primary.main',
                            backgroundColor: 'primary.50',
                          },
                        }}
                      >
                        <input {...getInputProps()} />
                        <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                        <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 500 }}>
                          {isDragActive ? 'Drop the image here' : 'Drag & drop an image here'}
                        </Typography>
                        <Typography color="textSecondary" variant="body2">
                          or click to select from your computer
                        </Typography>
                        <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
                          JPEG, PNG, GIF, WebP (max 10MB)
                        </Typography>
                      </Paper>
                    ) : (
                      <Box>
                        <Paper sx={{ p: 3, mb: 2, border: 1, borderColor: 'divider' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            {previewUrl && (
                              <Box
                                component="img"
                                src={previewUrl}
                                sx={{
                                  width: 80,
                                  height: 80,
                                  objectFit: 'cover',
                                  borderRadius: 1,
                                  border: 1,
                                  borderColor: 'divider'
                                }}
                              />
                            )}
                            <Box sx={{ flexGrow: 1 }}>
                              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                                {uploadedFile.name}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                {(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB
                              </Typography>
                            </Box>
                            <Button variant="outlined" color="error" onClick={removeImage} size="small">
                              Remove
                            </Button>
                          </Box>
                        </Paper>

                        <Controller
                          name="image_instruction"
                          control={control}
                          render={({ field }) => (
                            <TextField
                              {...field}
                              key={`image_instruction-${activePreset?.id || 'default'}`}
                              fullWidth
                              multiline
                              rows={2}
                              label="Image Instruction"
                              placeholder="e.g., 'Use the burger as the main subject', 'Enhance lighting'"
                            />
                          )}
                        />
                      </Box>
                    )}
                  </Box>

                  {/* Basic Options */}
                  <Box sx={{ mb: 4 }}>
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
                      Options
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      <Controller
                        name="render_text"
                        control={control}
                        render={({ field }) => (
                          <FormControlLabel
                            control={<Switch {...field} checked={field.value} />}
                            label="Render Text"
                          />
                        )}
                      />
                      <Controller
                        name="apply_branding"
                        control={control}
                        render={({ field }) => (
                          <FormControlLabel
                            control={<Switch {...field} checked={field.value} />}
                            label="Apply Branding"
                          />
                        )}
                      />
                    </Box>
                  </Box>
                </Box>
              </Grid>

              {/* RIGHT SIDE - Advanced Settings Only */}
              <Grid item xs={12} lg={5}>
                <Box sx={{ pl: { lg: 2 } }}>
                  {showAdvancedFields ? (
                    <Box>
                      <Typography variant="h5" gutterBottom sx={{ fontWeight: 600, mb: 3, letterSpacing: '-0.01em' }}>
                        Advanced Settings
                      </Typography>
                      
                      <Paper sx={{ p: 4, backgroundColor: 'grey.50', borderRadius: 3, border: 1, borderColor: 'grey.200' }}>
                        <Grid container spacing={3}>
                          {/* Task Description */}
                          <Grid item xs={12}>
                            <Controller
                              name="task_description"
                              control={control}
                              render={({ field }) => (
                                <TextField
                                  {...field}
                                  key={`task_description-${activePreset?.id || 'default'}`}
                                  fullWidth
                                  multiline
                                  rows={3}
                                  label="Task Content/Description"
                                  placeholder="e.g., 'Promo: 2-for-1 Coffee!', 'Menu: Signature Pasta'"
                                />
                              )}
                            />
                          </Grid>

                          {/* Branding Elements */}
                          <Grid item xs={12}>
                            <Controller
                              name="branding_elements"
                              control={control}
                              render={({ field }) => (
                                <TextField
                                  {...field}
                                  key={`branding_elements-${activePreset?.id || 'default'}`}
                                  fullWidth
                                  multiline
                                  rows={3}
                                  label="Branding Elements"
                                  placeholder="e.g., 'Logo Icon: indian mustache', 'Use #FFC107 for accents'"
                                />
                              )}
                            />
                          </Grid>

                          {/* Marketing Goals */}
                          <Grid item xs={12}>
                            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mt: 2, mb: 2 }}>
                              Marketing Goals
                            </Typography>
                            <Grid container spacing={2}>
                              <Grid item xs={12}>
                                <Controller
                                  name="marketing_audience"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_audience-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      label="Target Audience"
                                      placeholder="e.g., Young professionals, families"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12}>
                                <Controller
                                  name="marketing_objective"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_objective-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      label="Objective"
                                      placeholder="e.g., Increase engagement, drive sales"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12}>
                                <Controller
                                  name="marketing_voice"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_voice-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      label="Voice"
                                      placeholder="e.g., Playful, casual, professional"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12}>
                                <Controller
                                  name="marketing_niche"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_niche-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      label="Niche"
                                      placeholder="e.g., Fast food, fine dining, coffee shop"
                                    />
                                  )}
                                />
                              </Grid>
                            </Grid>
                          </Grid>
                        </Grid>
                      </Paper>
                    </Box>
                  ) : (
                    <Box sx={{ 
                      p: 4, 
                      textAlign: 'center', 
                      backgroundColor: 'grey.50', 
                      borderRadius: 3,
                      border: 1,
                      borderColor: 'grey.200',
                      borderStyle: 'dashed'
                    }}>
                      <Typography variant="h6" color="textSecondary" gutterBottom sx={{ fontWeight: 500 }}>
                        Advanced Settings
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Switch to Custom Mode or Task-Specific Mode to access advanced settings
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Grid>
            </Grid>

            {/* Actions Footer */}
            <Box sx={{ mt: 5 }}>
              <Divider sx={{ mb: 4 }} />
              <Box sx={{ display: 'flex', gap: 3, justifyContent: 'space-between', alignItems: 'center' }}>
                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={handleReset}
                  disabled={isSubmitting}
                  size="large"
                  sx={{ fontWeight: 500 }}
                >
                  Reset Form
                </Button>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                  {selectedMode === 'easy_mode' && !watch('prompt') && !uploadedFile && (
                    <Alert severity="info" sx={{ py: 1 }}>
                      Easy mode requires either a prompt or an image
                    </Alert>
                  )}
                  
                  <Tooltip 
                    title={!isFormValidForTemplate() ? getValidationErrorMessage() : "Save current form settings as a template"}
                    arrow
                  >
                    <span>
                      <Button
                        variant="outlined"
                        onClick={openSaveTemplateDialog}
                        startIcon={<PaletteIcon />}
                        size="large"
                        disabled={!isFormValidForTemplate()}
                        sx={{ 
                          px: 3, 
                          py: 1.5, 
                          fontSize: '1.1rem',
                          fontWeight: 600,
                          minWidth: 200
                        }}
                      >
                        Save as Template
                      </Button>
                    </span>
                  </Tooltip>
                  
                  <Button
                    type="submit"
                    variant="contained"
                    size="large"
                    startIcon={isSubmitting ? <CircularProgress size={20} /> : <SendIcon />}
                    disabled={isSubmitting}
                    sx={{ 
                      px: 4, 
                      py: 1.5, 
                      fontSize: '1.1rem',
                      fontWeight: 600,
                      minWidth: 220
                    }}
                  >
                    {isSubmitting ? 'Starting Pipeline...' : 'Start Pipeline Run'}
                  </Button>
                </Box>
              </Box>
            </Box>
          </form>
        </CardContent>
      </Card>

      {/* Save Template Dialog */}
      <Dialog open={saveTemplateDialogOpen} onClose={closeSaveTemplateDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Save as Template</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Save your current form settings as a reusable template for future projects.
            </Typography>
            {!isFormValidForTemplate() && (
              <Alert severity="warning" sx={{ mb: 2 }}>
                {getValidationErrorMessage()}
              </Alert>
            )}
            <TextField
              autoFocus
              fullWidth
              label="Template Name"
              value={saveTemplateName}
              onChange={(e) => setSaveTemplateName(e.target.value)}
              placeholder="e.g., Instagram Product Photography"
              helperText="Give your template a descriptive name"
              variant="outlined"
              sx={{ mt: 1 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeSaveTemplateDialog} disabled={saveTemplateLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleSaveTemplate}
            disabled={!saveTemplateName.trim() || saveTemplateLoading || !isFormValidForTemplate()}
            variant="contained"
            startIcon={saveTemplateLoading ? <CircularProgress size={16} /> : <PaletteIcon />}
          >
            {saveTemplateLoading ? 'Saving...' : 'Save Template'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Preset Management Modal */}
      <PresetManagementModal
        open={presetModalOpen}
        onClose={() => setPresetModalOpen(false)}
        onPresetSelected={handlePresetSelected}
      />
    </motion.div>
  );
} 