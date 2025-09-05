'use client';

import * as React from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Grid, 
  FormControl, 
  InputLabel, 
  Select, 
  MenuItem,
  Chip,
  Slider,
  Tooltip,
  IconButton,
  alpha,
  useTheme
} from '@mui/material';
import { motion, AnimatePresence } from 'framer-motion';
import { PipelineFormData, UnifiedBrief } from '@/types/api';
import { Control, UseFormWatch, UseFormSetValue, FieldErrors, Controller } from 'react-hook-form';
import CreativeBriefInput from '../CreativeBriefInput';
import EditModeSelector from '../EditModeSelector';
import TextOverlayComposer from '../TextOverlayComposer';
import ImageDropzone from '../ImageDropzone';
import TemplateGallery from './TemplateGallery';
import LensBrand from './LensBrand';
import LensText from './LensText';
import LensMarketing from './LensMarketing';
import CanvasHeader from './CanvasHeader';

import { PLATFORMS } from '@/lib/constants';
import { TOOLTIP_CONFIG, TOOLTIP_STRINGS, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { Info as InfoIcon } from '@mui/icons-material';

interface CreativeCanvasProps {
  control: Control<PipelineFormData>;
  watch: UseFormWatch<PipelineFormData>;
  setValue: UseFormSetValue<PipelineFormData>;
  errors: FieldErrors<PipelineFormData>;
  isSubmitting: boolean;
  uploadedFile: File | null;
  previewUrl: string | null;
  unifiedBrief: UnifiedBrief;
  setUnifiedBrief: (brief: UnifiedBrief) => void;
  // Brand kit related props
  applyBranding: boolean;
  renderText: boolean;
  onBrandKitPresetOpen: () => void;
  onColorPaletteOpen: () => void;
  onRecipeModalOpen: () => void;
  // Image handling props
  onFileSelect: (file: File) => void;
  onFileRemove: () => void;
  // Legacy brand kit actions
  onLoadBrandKitPreset: () => void;
  onSaveBrandKitPreset: () => void;
  hasBrandKitData: () => boolean;
}

export default function CreativeCanvas({
  control,
  watch,
  setValue,
  errors,
  isSubmitting,
  uploadedFile,
  previewUrl,
  unifiedBrief,
  setUnifiedBrief,
  applyBranding,
  renderText,
  onBrandKitPresetOpen,
  onColorPaletteOpen,
  onRecipeModalOpen,
  onFileSelect,
  onFileRemove,
  onLoadBrandKitPreset,
  onSaveBrandKitPreset,
  hasBrandKitData,
}: CreativeCanvasProps) {
  const theme = useTheme();
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <CanvasHeader />
          
          {/* Required Fields Legend */}
          <Box sx={{ mb: 3, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
              Fields marked * are required
            </Typography>
          </Box>
          
          {/* Primary Creative Input */}
          <Box sx={{ mb: 4 }}>
            <CreativeBriefInput
              value={unifiedBrief.generalBrief}
              onChange={(value) => {
                const updatedBrief = { ...unifiedBrief, generalBrief: value };
                setUnifiedBrief(updatedBrief);
                setValue('unifiedBrief', updatedBrief);
              }}
              disabled={isSubmitting}
              error={errors.unifiedBrief?.generalBrief?.message}
              placeholder="Describe the visual style, mood, composition, or specific imagery you want to create..."
              hasImage={!!uploadedFile}
            />
          </Box>

          {/* Smart validation guidance */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 4 }}>
            <Box sx={{ flexGrow: 1, height: 1, backgroundColor: 'divider' }} />
            <Chip 
              label={
                unifiedBrief.generalBrief && uploadedFile 
                  ? "Both provided ✓" 
                  : unifiedBrief.generalBrief || uploadedFile
                    ? "One provided ✓"
                    : "Provide brief or image"
              }
              size="small" 
              color={
                unifiedBrief.generalBrief || uploadedFile ? "success" : "warning"
              }
              sx={{ 
                mx: 2, 
                backgroundColor: 'background.paper',
                fontWeight: 500
              }}
            />
            <Box sx={{ flexGrow: 1, height: 1, backgroundColor: 'divider' }} />
          </Box>

          {/* Image Upload with Integrated Edit Mode */}
          <ImageDropzone
            uploadedFile={uploadedFile}
            previewUrl={previewUrl}
            onFileSelect={onFileSelect}
            onFileRemove={onFileRemove}
            disabled={isSubmitting}
            hasBrief={!!unifiedBrief.generalBrief?.trim()}
            showEditMode={!!uploadedFile}
            editMode={unifiedBrief.intentType as 'defaultEdit' | 'instructedEdit'}
            onEditModeChange={(mode) => {
              const updatedBrief = {
                ...unifiedBrief,
                intentType: mode,
                editInstruction: mode === 'defaultEdit' ? '' : unifiedBrief.editInstruction
              };
              setUnifiedBrief(updatedBrief);
              setValue('unifiedBrief', updatedBrief);
            }}
            editInstruction={unifiedBrief.editInstruction || ''}
            onEditInstructionChange={(instruction) => {
              const updatedBrief = { ...unifiedBrief, editInstruction: instruction };
              setUnifiedBrief(updatedBrief);
              setValue('unifiedBrief', updatedBrief);
            }}
          />

          {/* Template Gallery */}
          <Box sx={{ mb: 4 }}>
            <TemplateGallery
              selectedTaskType={watch('task_type') || ''}
              onTaskTypeSelect={(taskType) => setValue('task_type', taskType)}
              disabled={isSubmitting}
            />
          </Box>

          {/* Platform & Generation Settings */}
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                Platform & Generation Settings
              </Typography>
              <Tooltip title="Configure target platform and generation settings for your visual content" {...TOOLTIP_CONFIG}>
                <IconButton size="small" sx={{ p: 0.5 }}>
                  <InfoIcon sx={INFO_ICON_STYLE} />
                </IconButton>
              </Tooltip>
            </Box>
            
            <Grid container spacing={3}>
              {/* Platform Selection - Full Width */}
              <Grid item xs={12}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.primary' }}>
                      Target Platform
                    </Typography>
                    <Chip 
                      label="Required" 
                      size="small" 
                      color="error"
                      variant="outlined"
                      sx={{ height: 18, fontSize: '0.65rem', fontWeight: 600 }}
                    />
                  </Box>
                  <FormControl fullWidth required sx={{ maxWidth: 400 }}>
                    <InputLabel>Target Platform *</InputLabel>
                    <Controller
                      name="platform_name"
                      control={control}
                      render={({ field }) => (
                        <Select {...field} label="Target Platform" error={!!errors.platform_name}>
                          {PLATFORMS.map((platform) => (
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
                </Box>
              </Grid>

              {/* Language and Generation Settings Row */}
              <Grid item xs={12}>
                <Grid container spacing={4} alignItems="flex-start">
                  {/* Language Selection */}
                  <Grid item xs={12} md={4}>
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Output Language
                        </Typography>
                        <Tooltip title={TOOLTIP_STRINGS.language} {...TOOLTIP_CONFIG}>
                          <IconButton size="small" sx={{ p: 0.5 }}>
                            <InfoIcon sx={{ ...INFO_ICON_STYLE, fontSize: '0.9rem' }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                      <FormControl fullWidth>
                        <InputLabel>Language</InputLabel>
                        <Controller
                          name="language"
                          control={control}
                          render={({ field }) => (
                            <Select {...field} label="Language" size="small">
                              <MenuItem value="en">
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Typography>English</Typography>
                                  <Chip label="Default" size="small" color="primary" sx={{ height: 16, fontSize: '0.6rem' }} />
                                </Box>
                              </MenuItem>
                              <MenuItem value="zh">
                                <Typography>中文 | Chinese</Typography>
                              </MenuItem>
                            </Select>
                          )}
                        />
                      </FormControl>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                        Text on images & captions
                      </Typography>
                    </Box>
                  </Grid>

                  {/* Creativity Level */}
                  <Grid item xs={12} md={4}>
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Creativity Level
                        </Typography>
                        <Tooltip 
                          title={TOOLTIP_STRINGS.creativityLevel[watch('creativity_level') as 1 | 2 | 3]} 
                          {...TOOLTIP_CONFIG}
                        >
                          <IconButton size="small" sx={{ p: 0.5 }}>
                            <InfoIcon sx={{ ...INFO_ICON_STYLE, fontSize: '0.9rem' }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {watch('creativity_level') === 1 ? 'Focused & Realistic' : watch('creativity_level') === 2 ? 'Stylized & Artistic' : 'Abstract & Creative'}
                      </Typography>
                      <Box sx={{ px: 1 }}>
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
                                '& .MuiSlider-markLabel': {
                                  fontSize: '0.7rem'
                                }
                              }}
                            />
                          )}
                        />
                      </Box>
                    </Box>
                  </Grid>
                  
                  {/* Number of Variants */}
                  <Grid item xs={12} md={4}>
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Variants
                        </Typography>
                        <Tooltip title={TOOLTIP_STRINGS.variants} {...TOOLTIP_CONFIG}>
                          <IconButton size="small" sx={{ p: 0.5 }}>
                            <InfoIcon sx={{ ...INFO_ICON_STYLE, fontSize: '0.9rem' }} />
                          </IconButton>
                        </Tooltip>
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Generate {watch('num_variants')} different options
                      </Typography>
                      <Box sx={{ px: 1 }}>
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
                                '& .MuiSlider-markLabel': {
                                  fontSize: '0.7rem'
                                }
                              }}
                            />
                          )}
                        />
                      </Box>
                    </Box>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Box>

          {/* Progressive Disclosure Lenses */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {/* Brand Lens */}
            <LensBrand
              control={control}
              watch={watch}
              setValue={setValue}
              errors={errors}
              isSubmitting={isSubmitting}
              applyBranding={applyBranding}
              onBrandKitPresetOpen={onBrandKitPresetOpen}
              onColorPaletteOpen={onColorPaletteOpen}
              onRecipeModalOpen={onRecipeModalOpen}
              onLoadBrandKitPreset={onLoadBrandKitPreset}
              onSaveBrandKitPreset={onSaveBrandKitPreset}
              hasBrandKitData={hasBrandKitData}
            />

            {/* Text Lens */}
            <LensText
              control={control}
              watch={watch}
              setValue={setValue}
              isSubmitting={isSubmitting}
              renderText={renderText}
              unifiedBrief={unifiedBrief}
              setUnifiedBrief={setUnifiedBrief}
            />

            {/* Marketing Lens */}
            <LensMarketing
              control={control}
              watch={watch}
              setValue={setValue}
              errors={errors}
              isSubmitting={isSubmitting}
            />
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
}
