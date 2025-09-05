'use client';

import * as React from 'react';
import { useState } from 'react';
import { 
  Box, 
  Card, 
  CardContent, 
  Typography, 
  Switch, 
  FormControlLabel,
  Collapse,
  Button,
  Grid,
  Divider,
  Chip,
  TextField,
  Tooltip,
  IconButton,
  alpha,
  useTheme
} from '@mui/material';
import { 
  Palette as PaletteIcon,
  Brush as BrushIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { Control, UseFormWatch, UseFormSetValue, FieldErrors, Controller } from 'react-hook-form';
import { PipelineFormData } from '@/types/api';
import CompactColorPreview from '../CompactColorPreview';
import CompactLogoDisplay from '../CompactLogoDisplay';
import LogoUploader from '../LogoUploader';
import { TOOLTIP_CONFIG, TOOLTIP_STRINGS, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { Info as InfoIcon } from '@mui/icons-material';

interface LensBrandProps {
  control: Control<PipelineFormData>;
  watch: UseFormWatch<PipelineFormData>;
  setValue: UseFormSetValue<PipelineFormData>;
  errors: FieldErrors<PipelineFormData>;
  isSubmitting: boolean;
  applyBranding: boolean;
  onBrandKitPresetOpen: () => void;
  onColorPaletteOpen: () => void;
  onRecipeModalOpen: () => void;
  // Legacy brand kit actions
  onLoadBrandKitPreset: () => void;
  onSaveBrandKitPreset: () => void;
  hasBrandKitData: () => boolean;
}

function LensBrand({
  control,
  watch,
  setValue,
  errors,
  isSubmitting,
  applyBranding,
  onBrandKitPresetOpen,
  onColorPaletteOpen,
  onRecipeModalOpen,
  onLoadBrandKitPreset,
  onSaveBrandKitPreset,
  hasBrandKitData,
}: LensBrandProps) {
  const theme = useTheme();
  const [isExpanded, setIsExpanded] = useState(applyBranding);
  const brandKit = watch('brand_kit');

  // Drive expansion directly from switch state
  React.useEffect(() => {
    setIsExpanded(applyBranding);
  }, [applyBranding]);

  const hasLocalBrandKitData = Boolean(
    brandKit?.colors?.length || 
    brandKit?.brand_voice_description?.trim() ||
    brandKit?.logo_file_base64
  );

  return (
    <Card sx={{ 
      border: 1,
      borderColor: applyBranding ? 'primary.main' : alpha(theme.palette.primary.main, 0.08),
      backgroundColor: applyBranding ? alpha(theme.palette.primary.main, 0.02) : 'background.paper',
      transition: 'all 0.2s ease-in-out',
      elevation: 2
    }}>
      <CardContent sx={{ pb: isExpanded ? 2 : '16px !important' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: isExpanded ? 2 : 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <PaletteIcon sx={{ mr: 1, color: applyBranding ? 'primary.main' : 'text.secondary' }} />
            <Typography 
              id="brand-lens-title"
              variant="h6" 
              sx={{ fontWeight: 600, color: applyBranding ? 'primary.main' : 'text.primary' }}
            >
              Brand & Colors
            </Typography>
            {hasLocalBrandKitData && (
              <Chip
                label="Configured"
                size="small"
                color="success"
                sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
              />
            )}
            <Tooltip title="Apply your brand colors, voice, and logo to maintain consistency across all content" {...TOOLTIP_CONFIG}>
              <IconButton size="small" sx={{ ml: 1, p: 0.5 }}>
                <InfoIcon sx={INFO_ICON_STYLE} />
              </IconButton>
            </Tooltip>
          </Box>
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Controller
              name="apply_branding"
              control={control}
              render={({ field }) => (
                <FormControlLabel
                  control={
                    <Switch
                      {...field}
                      checked={field.value}
                      disabled={isSubmitting}
                      size="small"
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
              )}
            />
          </Box>
        </Box>

        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.15, ease: 'easeInOut' }}
            >
              <Collapse in={isExpanded}>
                <Box id="brand-lens-content" role="region" aria-labelledby="brand-lens-title">
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Apply your brand colors, voice, and logo to maintain consistency across all content
                  </Typography>

                  <Grid container spacing={3}>
                    {/* Brand Colors */}
                    <Grid item xs={12} md={4}>
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                          Brand Colors
                        </Typography>
                        <CompactColorPreview
                          colors={brandKit?.colors || []}
                          onEditClick={onColorPaletteOpen}
                        />
                      </Box>
                    </Grid>

                    {/* Brand Voice */}
                    <Grid item xs={12} md={4}>
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                          Brand Voice
                        </Typography>
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
                                inputProps={{ maxLength: maxLength + 50 }}
                                helperText={
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <span>Describe your brand&apos;s tone and personality</span>
                                    <span style={{ color: isOverLimit ? theme.palette.error.main : theme.palette.text.secondary }}>
                                      {currentValue.length}/{maxLength}
                                    </span>
                                  </div>
                                }
                                error={isOverLimit}
                                disabled={isSubmitting}
                              />
                            );
                          }}
                        />
                      </Box>
                    </Grid>

                    {/* Logo */}
                    <Grid item xs={12} md={4}>
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
                          Brand Logo
                        </Typography>
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
                                showRemoveButton={true}
                                onRemove={() => {
                                  field.onChange({
                                    ...field.value,
                                    logo_file_base64: undefined,
                                    logo_analysis: undefined
                                  });
                                }}
                              />
                            ) : (
                              <LogoUploader
                                onLogoUpload={(file, analysis) => {
                                  field.onChange({
                                    ...field.value,
                                    logo_file_base64: analysis.preview_url,
                                    logo_analysis: analysis
                                  });
                                }}
                                onLogoRemove={() => {
                                  field.onChange({
                                    ...field.value,
                                    logo_file_base64: undefined,
                                    logo_analysis: undefined
                                  });
                                }}
                                currentLogo={null}
                                showLabels={false}
                              />
                            );
                          }}
                        />
                      </Box>
                    </Grid>
                  </Grid>

                  <Divider sx={{ my: 3 }} />

                  {/* Action Buttons - Legacy Parity */}
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                    <Button
                      variant="outlined"
                      startIcon={<SettingsIcon />}
                      onClick={onLoadBrandKitPreset}
                      disabled={isSubmitting}
                      size="small"
                    >
                      Load Kit
                    </Button>
                    
                    <Button
                      variant="outlined"
                      startIcon={<SettingsIcon />}
                      onClick={onSaveBrandKitPreset}
                      disabled={isSubmitting || !hasBrandKitData()}
                      size="small"
                    >
                      Save Kit
                    </Button>
                    
                    <Button
                      variant="outlined"
                      startIcon={<BrushIcon />}
                      onClick={onColorPaletteOpen}
                      disabled={isSubmitting}
                      size="small"
                    >
                      Edit Colors
                    </Button>
                  </Box>
                </Box>
              </Collapse>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

export default LensBrand;
