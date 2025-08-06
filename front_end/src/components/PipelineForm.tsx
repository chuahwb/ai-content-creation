'use client';

import React, { useState, useEffect, useRef } from 'react';
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
import { motion, AnimatePresence } from 'framer-motion';
import { PipelineFormData, PipelineRunResponse, BrandPresetResponse, BrandKitInput } from '@/types/api';
import { PipelineAPI } from '@/lib/api';
import PresetManagementModal, { PresetManagementModalRef } from './PresetManagementModal';
import BrandKitPresetModal from './BrandKitPresetModal';
import StyleRecipeModal from './StyleRecipeModal';
import ColorPaletteEditor from './ColorPaletteEditor';
import LogoUploader from './LogoUploader';
import CompactLogoDisplay from './CompactLogoDisplay';

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
  brand_kit: z.object({
    colors: z.array(z.string()).optional(),
    brand_voice_description: z.string().nullable().optional(),
    logo_file_base64: z.string().nullable().optional(),
    saved_logo_path_in_run_dir: z.string().nullable().optional(),
  }).optional(),
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
}).refine((data) => {
  // Conditional validation: task_type is required when mode is task_specific_mode
  if (data.mode === 'task_specific_mode' && (!data.task_type || data.task_type.trim() === '')) {
    return false;
  }
  return true;
}, {
  message: 'Task type is required for task-specific mode',
  path: ['task_type'], // This will show the error on the task_type field
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
  const [isResetting, setIsResetting] = useState(false);
  
  // Preset-related state
  const [activePreset, setActivePreset] = useState<BrandPresetResponse | null>(null);
  const [presetModalOpen, setPresetModalOpen] = useState(false);
  const presetModalRef = useRef<PresetManagementModalRef>(null);

  // Add state for save template functionality after the existing state declarations
  // Save template dialog state
  const [saveTemplateDialogOpen, setSaveTemplateDialogOpen] = useState(false);
  const [saveTemplateName, setSaveTemplateName] = useState('');
  const [saveTemplateLoading, setSaveTemplateLoading] = useState(false);

  // Brand kit preset state
  const [brandKitPresetModalOpen, setBrandKitPresetModalOpen] = useState(false);
  
  // Style recipe modal state
  const [recipeModalOpen, setRecipeModalOpen] = useState(false);

  // Store original default values to ensure reset always goes back to true defaults
  const originalDefaultValues: PipelineFormData = {
    mode: 'easy_mode',
    platform_name: '',
    creativity_level: 1,
    num_variants: 3,
    prompt: '',
    task_type: '',
    task_description: '',
    brand_kit: undefined,
    image_instruction: '',
    render_text: false,
    apply_branding: false,
    marketing_audience: '',
    marketing_objective: '',
    marketing_voice: '',
    marketing_niche: '',
    language: 'en',
    image_file: undefined,
  };

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors },
  } = useForm<PipelineFormData>({
    resolver: zodResolver(formSchema),
    defaultValues: originalDefaultValues,
  });

  const selectedMode = watch('mode');
  const requiresTaskType = selectedMode === 'task_specific_mode';
  const showAdvancedFields = selectedMode !== 'easy_mode';
  const applyBranding = watch('apply_branding');
  
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
    // Detect potential conflicts before applying preset
    const conflicts = detectPresetConflicts(preset);
    
    // Check if this is a pure brand kit preset (brand kit data + minimal input_snapshot)
    const isBrandKitPreset = preset.preset_type === 'INPUT_TEMPLATE' && 
                            preset.brand_kit && 
                            (preset.brand_kit.colors?.length || preset.brand_kit.brand_voice_description || preset.brand_kit.logo_file_base64) &&
                            preset.preset_source_type === 'brand-kit' &&
                            preset.input_snapshot?.platform_name === 'Brand Kit (Universal)';
    
    if (isBrandKitPreset) {
      // Use the dedicated brand kit handler for brand kit presets
      handleApplyBrandKitPreset(preset);
      setPresetModalOpen(false);
      return;
    }
    
    if (preset.preset_type === 'STYLE_RECIPE') {
      // Style recipes use their own dedicated modal - no form integration needed
      setActivePreset(preset); // Keep track of the selected preset
      setRecipeModalOpen(true); // Open the style adaptation modal
      setPresetModalOpen(false); // Close the management modal
      // DON'T set isRecipeActive - style adaptations are handled entirely by StyleRecipeModal
      return;
    }
    
    setActivePreset(preset);
    applyPresetToForm(preset);
    setPresetModalOpen(false);
    // Note: applyPresetToForm handles its own success/validation messaging
  };

  const applyPresetToForm = (preset: BrandPresetResponse) => {
    if (preset.preset_type === 'INPUT_TEMPLATE') {
      // Apply Input Template: Smart handling of existing brand kit data
      const inputData = preset.input_snapshot;
      
      if (inputData) {
        // Check if user has existing brand kit data that would be overwritten
        const currentBrandKit = watch('brand_kit');
        const hasExistingBrandKit = Boolean(
          currentBrandKit?.colors?.length || 
          currentBrandKit?.brand_voice_description?.trim() || 
          currentBrandKit?.logo_file_base64
        );
        
        const templateHasBrandKit = Boolean(
          inputData.brand_kit?.colors?.length || 
          inputData.brand_kit?.brand_voice_description?.trim() || 
          inputData.brand_kit?.logo_file_base64
        );
        
        // Smart brand kit preservation logic
        let finalBrandKit = inputData.brand_kit;
        let brandKitMessage = '';
        if (hasExistingBrandKit && !templateHasBrandKit) {
          // Preserve user's brand kit if template doesn't have one
          finalBrandKit = currentBrandKit;
          brandKitMessage = ' (your brand kit preserved)';
        } else if (hasExistingBrandKit && templateHasBrandKit) {
          // Template overrides existing brand kit
          brandKitMessage = ' (template brand kit applied)';
        }
        
        // Preserve uploaded image when applying template
        const currentImageFile = watch('image_file');
        const hasUploadedImage = Boolean(uploadedFile && currentImageFile);
        let imageMessage = '';
        if (hasUploadedImage) {
          imageMessage = ' (uploaded image preserved)';
        }
        
        // Apply template data with smart brand kit handling
        reset({
          mode: (inputData.mode as 'easy_mode' | 'custom_mode' | 'task_specific_mode') || 'easy_mode',
          prompt: inputData.prompt || '',
          creativity_level: (inputData.creativity_level as 1 | 2 | 3) || 1,
          platform_name: inputData.platform_name || '',
          num_variants: inputData.num_variants || 3,
          task_type: inputData.task_type || '',
          task_description: inputData.task_description || '',
          brand_kit: finalBrandKit || undefined,
          render_text: inputData.render_text || false,
          apply_branding: inputData.apply_branding || false,
          language: inputData.language || 'en',
          marketing_audience: inputData.marketing_audience || '',
          marketing_objective: inputData.marketing_objective || '',
          marketing_voice: inputData.marketing_voice || '',
          marketing_niche: inputData.marketing_niche || '',
          image_instruction: inputData.image_instruction || '',
          // Preserve uploaded image
          image_file: hasUploadedImage ? currentImageFile : undefined,
        });
        
        // Single consolidated success message with validation check
        setTimeout(() => {
          const newFormData = watch();
          const validation = validateFormData(newFormData);
          
          if (validation.isValid) {
            // Success message with context about preservations
            const successMessage = `Template "${preset.name}" applied successfully!${brandKitMessage}${imageMessage}`;
            toast.success(successMessage);
          } else {
            // Warning message indicating template applied but needs attention
            toast.error(`Template "${preset.name}" applied, but ${validation.error}`);
          }
        }, 100); // Small delay to ensure form state is updated
      }
    } 
    // STYLE_RECIPE presets are no longer handled here - they use StyleRecipeModal exclusively
  };



  // Helper function to detect potential preset conflicts
  const detectPresetConflicts = (newPreset: BrandPresetResponse) => {
    const warnings: string[] = [];
    
    // Check for active template when applying brand kit
    if (newPreset.preset_source_type === 'brand-kit' && activePreset?.preset_type === 'INPUT_TEMPLATE') {
      warnings.push('Applying brand kit over template - template settings will be preserved');
    }
    
    // Check for existing brand kit when applying template
    const currentBrandKit = watch('brand_kit');
    const hasExistingBrandKit = Boolean(
      currentBrandKit?.colors?.length || 
      currentBrandKit?.brand_voice_description?.trim() || 
      currentBrandKit?.logo_file_base64
    );
    
    if (newPreset.preset_type === 'INPUT_TEMPLATE' && hasExistingBrandKit) {
      const templateHasBrandKit = Boolean(
        newPreset.input_snapshot?.brand_kit?.colors?.length || 
        newPreset.input_snapshot?.brand_kit?.brand_voice_description?.trim() || 
        newPreset.input_snapshot?.brand_kit?.logo_file_base64
      );
      
      if (!templateHasBrandKit) {
        warnings.push('Your existing brand kit will be preserved');
      } else {
        warnings.push('Template will replace your existing brand kit');
      }
    }
    
    return warnings;
  };

  // Shared validation logic for both pipeline run and template saving
  const validateFormData = (data: PipelineFormData): { isValid: boolean; error?: string } => {
    // Validate required fields
    if (!data.platform_name) {
      return { isValid: false, error: 'Platform selection is required' };
    }
    
    // Use the data's mode, not the current selectedMode, for accurate validation
    const modeToValidate = data.mode || selectedMode;
    const modeRequiresTaskType = modeToValidate === 'task_specific_mode';
    
    // Universal validation: All modes require either a prompt or an image
    const hasPrompt = data.prompt && data.prompt.trim().length > 0;
    const hasImage = data.image_file || uploadedFile;
    if (!hasPrompt && !hasImage) {
      const modeNames = {
        'easy_mode': 'Easy mode',
        'custom_mode': 'Custom mode', 
        'task_specific_mode': 'Task-specific mode'
      };
      const modeName = modeNames[modeToValidate] || 'This mode';
      return { isValid: false, error: `${modeName} requires either a prompt or an image` };
    }
    
    // Mode-specific validation
    if (modeRequiresTaskType && (!data.task_type || data.task_type.trim().length === 0)) {
      return { isValid: false, error: 'Task-specific mode requires a task type selection' };
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

      // Prepare submit data - don't overwrite form data with preset data
      const submitData = {
        ...data,
        // Exclude brand_kit from submission when apply_branding is false
        brand_kit: data.apply_branding ? data.brand_kit : undefined,
        // Add preset information if active (STYLE_RECIPE presets are handled by StyleRecipeModal)
        preset_id: activePreset?.preset_type === 'INPUT_TEMPLATE' ? activePreset?.id : undefined,
        preset_type: activePreset?.preset_type === 'INPUT_TEMPLATE' ? activePreset?.preset_type : undefined,
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
    // Set reset flag to prevent auto-application interference
    setIsResetting(true);
    
    // Reset form to original defaultValues (not template values)
    reset(originalDefaultValues);
    
    // Clear uploaded image and related state
    removeImage();
    
    // Clear custom language state
    setShowCustomLanguage(false);
    
    // Reset additional dialog states that aren't part of the form
    setSaveTemplateDialogOpen(false);
    setSaveTemplateName('');
    setSaveTemplateLoading(false);
    setBrandKitPresetModalOpen(false);
    setRecipeModalOpen(false);
    setPresetModalOpen(false);
    
    // Only clear presets if requested (not when switching templates)
    if (clearPresets) {
      setActivePreset(null);
    }
    
    // Clear reset flag after a short delay to allow form state to settle
    setTimeout(() => {
      setIsResetting(false);
    }, 100);
  };

  const handleReset = () => {
    resetFormToDefaults(true); // Clear presets when manually resetting
    toast.success('Form reset to default values');
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
        brand_kit: currentValues.brand_kit || null,
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
        preset_source_type: 'user-input',
        pipeline_version: '1.0.0',
      });
      
      toast.success('Template saved successfully!');
      closeSaveTemplateDialog();
      // Refresh preset modal if it's open
      presetModalRef.current?.refreshPresets();
    } catch (error: any) {
      console.error('Failed to save template:', error);
      toast.error(error.message || 'Failed to save template');
    } finally {
      setSaveTemplateLoading(false);
    }
  };

  // Brand Kit Preset handlers
  const hasBrandKitData = () => {
    const brandKit = watch('brand_kit');
    return Boolean(
      brandKit?.colors?.length || 
      brandKit?.brand_voice_description?.trim() ||
      brandKit?.logo_file_base64
    );
  };

  const handleLoadBrandKitPreset = () => {
    setBrandKitPresetModalOpen(true);
  };

  const handleSaveBrandKitPreset = async () => {
    const brandKit = watch('brand_kit');
    if (!hasBrandKitData()) {
      toast.error('No brand kit data to save');
      return;
    }

    // Validate character limits for brand voice
    if (brandKit?.brand_voice_description && brandKit.brand_voice_description.length > 250) {
      toast.error('Brand voice description must be 250 characters or less');
      return;
    }

    // Validate colors format (basic hex validation)
    if (brandKit?.colors) {
      for (const color of brandKit.colors) {
        const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
        if (!hexRegex.test(color)) {
          toast.error(`Invalid color format: ${color}. Please use valid hex colors (e.g., #FF0000)`);
          return;
        }
      }
    }

    const name = prompt('Enter a name for this brand kit:');
    if (!name?.trim()) return;

    try {
      await PipelineAPI.createBrandPreset({
        name: name.trim(),
        preset_type: 'INPUT_TEMPLATE',
        brand_kit: brandKit,
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
      });
      toast.success(`Brand kit "${name}" saved successfully!`);
      // Refresh preset modal if it's open
      presetModalRef.current?.refreshPresets();
    } catch (error: any) {
      console.error('Failed to save brand kit:', error);
      toast.error(error.message || 'Failed to save brand kit');
    }
  };

  const handleApplyBrandKitPreset = (preset: BrandPresetResponse) => {
    if (preset.brand_kit) {
      // Apply brand kit data without resetting entire form
      setValue('brand_kit', preset.brand_kit);
      
      // Only toggle apply_branding if it wasn't already enabled
      const currentApplyBranding = watch('apply_branding');
      const wasAlreadyEnabled = currentApplyBranding;
      if (!currentApplyBranding) {
        setValue('apply_branding', true);
      }
      
      // Keep the activePreset for brand kit presets so preset info is included in submission
      // This is important for backend processing and pipeline execution
      setActivePreset(preset);
      
      setBrandKitPresetModalOpen(false);
      
      // Single user-centric success message
      const brandingMessage = wasAlreadyEnabled 
        ? `Brand kit "${preset.name}" applied successfully!`
        : `Brand kit "${preset.name}" applied and branding enabled!`;
      toast.success(brandingMessage);
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

  // Smart Brand Kit Auto-Application: Auto-enable apply_branding when brand kit data is present
  // This handles cases where users manually add brand kit data (not via presets)
  useEffect(() => {
    const subscription = watch((value, { name }) => {
      // Only react to brand_kit changes, not other form changes
      // Skip during reset operations to prevent interference
      if (name === 'brand_kit' && !isResetting) {
        const brandKit = value.brand_kit;
        const hasKitData = Boolean(
          brandKit?.colors?.length || 
          brandKit?.brand_voice_description?.trim() || 
          brandKit?.logo_file_base64
        );
        
        const applyBrandingCurrentValue = value.apply_branding;
        
        // Only auto-enable if there's brand kit data and branding isn't already enabled
        // Skip auto-enable during form initialization or reset to avoid interfering
        // Note: No toast message here since preset application handles its own messaging
        if (hasKitData && !applyBrandingCurrentValue && brandKit) {
          // Add a small delay to avoid interfering with reset operations
          setTimeout(() => {
            // Double-check reset flag in case reset happened during timeout
            if (!isResetting) {
              setValue('apply_branding', true);
            }
          }, 50);
        }
      }
    });
    
    return () => subscription.unsubscribe();
  }, [watch, setValue, isResetting]);

  // Brand Kit Reset: Clear brand kit data when apply_branding is toggled off
  useEffect(() => {
    const subscription = watch((value, { name }) => {
      // Only react to apply_branding changes, not other form changes
      // Skip during reset operations to prevent interference
      if (name === 'apply_branding' && !isResetting) {
        const applyBrandingCurrentValue = value.apply_branding;
        const brandKit = value.brand_kit;
        
        // If branding is turned off and there's existing brand kit data, clear it
        if (!applyBrandingCurrentValue && brandKit) {
          const hasBrandKitData = Boolean(
            brandKit?.colors?.length || 
            brandKit?.brand_voice_description?.trim() || 
            brandKit?.logo_file_base64
          );
          
          if (hasBrandKitData) {
            // Clear brand kit data
            setValue('brand_kit', undefined);
            toast.success('Brand kit data cleared since branding is disabled');
          }
        }
      }
    });
    
    return () => subscription.unsubscribe();
  }, [watch, setValue, isResetting]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card elevation={1} sx={{ maxWidth: 1400, mx: 'auto' }}>
        <CardContent sx={{ p: 4 }}>
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
            <Typography variant="h4" sx={{ fontWeight: 600, textAlign: 'center', letterSpacing: '-0.02em', flexGrow: 1 }}>
              Create New Pipeline Run
            </Typography>

          </Box>

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



            {/* Recipe Active Mode - REMOVED: Style recipes now use dedicated StyleRecipeModal */}
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

                  {/* Global Options */}
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

              {/* RIGHT SIDE - Brand Kit & Advanced Settings */}
              <Grid item xs={12} lg={5}>
                <Box sx={{ pl: { lg: 2 } }}>
                  {/* Brand Kit - Available in all modes when toggle is ON */}
                  <AnimatePresence>
                    {applyBranding && (
                      <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        transition={{ duration: 0.3 }}
                      >
                        <Paper sx={{ p: 2.5, mb: 2.5, border: '1px solid', borderColor: 'divider' }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.1rem' }}>
                              <PaletteIcon sx={{ fontSize: '1.2rem' }} /> Brand Kit
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={handleLoadBrandKitPreset}
                                startIcon={<BookmarkAddIcon />}
                                sx={{ fontSize: '0.75rem', py: 0.5, px: 1 }}
                              >
                                Load Kit
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                onClick={handleSaveBrandKitPreset}
                                startIcon={<BookmarkAddIcon />}
                                disabled={!hasBrandKitData()}
                                sx={{ fontSize: '0.75rem', py: 0.5, px: 1 }}
                              >
                                Save Kit
                              </Button>
                            </Box>
                          </Box>
                          <Grid container spacing={2}>
                            {/* Color Palette Editor */}
                            <Grid item xs={12}>
                              <Controller
                                name="brand_kit"
                                control={control}
                                render={({ field }) => (
                                  <ColorPaletteEditor
                                    colors={field.value?.colors || []}
                                    onChange={(colors) => field.onChange({
                                      ...field.value,
                                      colors
                                    })}
                                  />
                                )}
                              />
                            </Grid>
                            
                            {/* Brand Voice */}
                            <Grid item xs={12}>
                              <Controller
                                name="brand_kit"
                                control={control}
                                render={({ field }) => {
                                  const currentValue = field.value?.brand_voice_description || '';
                                  const maxLength = 250;
                                  const isOverLimit = currentValue.length > maxLength;
                                  
                                  return (
                                    <TextField
                                      fullWidth
                                      size="small"
                                      label="Brand Voice"
                                      placeholder="e.g., 'Friendly and approachable'"
                                      value={currentValue}
                                      onChange={(e) => field.onChange({
                                        ...field.value,
                                        brand_voice_description: e.target.value
                                      })}
                                      inputProps={{ maxLength: maxLength + 50 }} // Allow some overflow for user feedback
                                      helperText={
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                          <span>Describe your brand's tone and personality</span>
                                          <span style={{ color: isOverLimit ? 'error.main' : 'text.secondary' }}>
                                            {currentValue.length}/{maxLength}
                                          </span>
                                        </Box>
                                      }
                                      error={isOverLimit}
                                    />
                                  );
                                }}
                              />
                            </Grid>
                            
                            {/* Logo Upload/Display */}
                            <Grid item xs={12}>
                              <Controller
                                name="brand_kit"
                                control={control}
                                render={({ field }) => {
                                  const hasLogo = field.value?.logo_file_base64;
                                  
                                  return hasLogo ? (
                                    <CompactLogoDisplay
                                      logo={field.value.logo_analysis || {
                                        preview_url: field.value.logo_file_base64,
                                        filename: 'Brand Logo'
                                      }}
                                      onRemove={() => field.onChange({
                                        ...field.value,
                                        logo_file_base64: undefined,
                                        logo_analysis: undefined
                                      })}
                                      showRemoveButton={true}
                                    />
                                  ) : (
                                    <LogoUploader
                                      onLogoUpload={(file, analysis) => {
                                        // Store both base64 data and analysis details
                                        field.onChange({
                                          ...field.value,
                                          logo_file_base64: analysis.preview_url, // Use analysis preview_url
                                          logo_analysis: analysis // Store full analysis for details display
                                        });
                                      }}
                                      onLogoRemove={() => field.onChange({
                                        ...field.value,
                                        logo_file_base64: undefined,
                                        logo_analysis: undefined
                                      })}
                                      currentLogo={null}
                                    />
                                  );
                                }}
                              />
                            </Grid>
                          </Grid>
                        </Paper>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Advanced Settings */}
                  {showAdvancedFields ? (
                    <Box>
                      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2, fontSize: '1.1rem' }}>
                        Advanced Settings
                      </Typography>
                      
                      <Paper sx={{ p: 2.5, backgroundColor: 'grey.50', borderRadius: 2, border: 1, borderColor: 'grey.200' }}>
                        <Grid container spacing={2.5}>
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
                                  rows={2}
                                  size="small"
                                  label="Task Content/Description"
                                  placeholder="e.g., 'Promo: 2-for-1 Coffee!', 'Menu: Signature Pasta'"
                                />
                              )}
                            />
                          </Grid>

                          {/* Marketing Goals */}
                          <Grid item xs={12}>
                            <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600, mb: 1.5, fontSize: '1rem' }}>
                              Marketing Goals
                            </Typography>
                            <Grid container spacing={1.5}>
                              <Grid item xs={12} sm={6}>
                                <Controller
                                  name="marketing_audience"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_audience-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      size="small"
                                      label="Target Audience"
                                      placeholder="e.g., Young professionals"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6}>
                                <Controller
                                  name="marketing_objective"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_objective-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      size="small"
                                      label="Objective"
                                      placeholder="e.g., Drive sales"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6}>
                                <Controller
                                  name="marketing_voice"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_voice-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      size="small"
                                      label="Voice"
                                      placeholder="e.g., Playful, casual"
                                    />
                                  )}
                                />
                              </Grid>
                              <Grid item xs={12} sm={6}>
                                <Controller
                                  name="marketing_niche"
                                  control={control}
                                  render={({ field }) => (
                                    <TextField
                                      {...field}
                                      key={`marketing_niche-${activePreset?.id || 'default'}`}
                                      fullWidth
                                      size="small"
                                      label="Niche"
                                      placeholder="e.g., Fast food, cafe"
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
        ref={presetModalRef}
        open={presetModalOpen}
        onClose={() => setPresetModalOpen(false)}
        onPresetSelected={handlePresetSelected}
      />

      {/* Brand Kit Preset Modal */}
      <BrandKitPresetModal
        open={brandKitPresetModalOpen}
        onClose={() => setBrandKitPresetModalOpen(false)}
        onPresetSelected={handleApplyBrandKitPreset}
      />

      {/* Style Recipe Modal */}
      {activePreset && (
        <StyleRecipeModal
          preset={activePreset}
          open={recipeModalOpen}
          onClose={() => {
            setRecipeModalOpen(false);
            // Clear the active preset when closing the style recipe modal
            // This ensures no lingering state from the style adaptation flow
            setActivePreset(null);
          }}
          onRunStarted={onRunStarted}
        />
      )}
    </motion.div>
  );
} 