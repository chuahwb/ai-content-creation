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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  CloudUpload as CloudUploadIcon,
  Send as SendIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { PipelineFormData, PipelineRunResponse, Platform } from '@/types/api';
import { PipelineAPI } from '@/lib/api';

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
      creativity_level: 2,
      num_variants: 3,
      render_text: false,
      apply_branding: false,
    },
  });

  const selectedMode = watch('mode');
  const requiresTaskType = selectedMode === 'task_specific_mode';
  const showAdvancedFields = selectedMode !== 'easy_mode';

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

  const onSubmit = async (data: PipelineFormData) => {
    setIsSubmitting(true);
    
    try {
      // Validate required fields
      if (!data.platform_name) {
        throw new Error('Platform selection is required');
      }
      
      if (selectedMode === 'easy_mode' && !data.prompt && !uploadedFile) {
        throw new Error('Easy mode requires either a prompt or an image');
      }
      
      if (requiresTaskType && !data.task_type) {
        throw new Error('Task type is required for task-specific mode');
      }

      // Submit the run
      const response = await PipelineAPI.submitRun(data);
      
      toast.success('Pipeline run started successfully!');
      onRunStarted(response);
      
      // Reset form for next use
      reset();
      removeImage();
      
    } catch (error: any) {
      console.error('Failed to submit run:', error);
      toast.error(error.message || 'Failed to start pipeline run');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    reset();
    removeImage();
    toast.success('Form reset');
  };

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
          
          <form onSubmit={handleSubmit(onSubmit)}>
            {/* Main Content - Left/Right Split */}
            <Grid container spacing={4}>
              {/* LEFT SIDE - All Basic Components */}
              <Grid item xs={12} lg={7}>
                <Box sx={{ pr: { lg: 2 } }}>
                  {/* Mode & Platform Row */}
                  <Grid container spacing={3} sx={{ mb: 4 }}>
                    <Grid item xs={12} md={6}>
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

                    <Grid item xs={12} md={6}>
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
                  </Grid>

                  {/* Task Type (conditional) */}
                  {requiresTaskType && (
                    <Box sx={{ mb: 4 }}>
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
                    </Box>
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
    </motion.div>
  );
} 