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
  Grid,
  TextField,
  Chip,
  Tooltip,
  IconButton,
  alpha,
  useTheme
} from '@mui/material';
import { 
  TrendingUp as TrendingUpIcon
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { Control, UseFormWatch, UseFormSetValue, FieldErrors, Controller } from 'react-hook-form';
import { PipelineFormData } from '@/types/api';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { Info as InfoIcon } from '@mui/icons-material';

interface LensMarketingProps {
  control: Control<PipelineFormData>;
  watch: UseFormWatch<PipelineFormData>;
  setValue: UseFormSetValue<PipelineFormData>;
  errors: FieldErrors<PipelineFormData>;
  isSubmitting: boolean;
}

function LensMarketing({
  control,
  watch,
  setValue,
  errors,
  isSubmitting,
}: LensMarketingProps) {
  const theme = useTheme();
  
  const marketingAudience = watch('marketing_audience');
  const marketingObjective = watch('marketing_objective');
  const marketingVoice = watch('marketing_voice');
  const marketingNiche = watch('marketing_niche');

  const hasMarketingData = Boolean(
    marketingAudience?.trim() || 
    marketingObjective?.trim() || 
    marketingVoice?.trim() || 
    marketingNiche?.trim()
  );

  // Local state to control marketing lens - starts as true if there's data, false otherwise
  const [enableMarketing, setEnableMarketing] = useState(hasMarketingData);
  // Track previous data state to detect external changes
  const [prevHasMarketingData, setPrevHasMarketingData] = useState(hasMarketingData);
  
  // Expansion is directly tied to enableMarketing state
  const isExpanded = enableMarketing;

  // Handle data changes (both template loading and form reset)
  React.useEffect(() => {
    // If data appeared (template loading), enable the lens
    if (hasMarketingData && !prevHasMarketingData) {
      setEnableMarketing(true);
    }
    // If data disappeared and lens was enabled (form reset), disable the lens
    else if (!hasMarketingData && prevHasMarketingData && enableMarketing) {
      setEnableMarketing(false);
    }
    // If user manually adds data while lens is disabled, enable it
    else if (hasMarketingData && !enableMarketing) {
      setEnableMarketing(true);
    }
    
    // Update previous state
    setPrevHasMarketingData(hasMarketingData);
  }, [hasMarketingData, prevHasMarketingData, enableMarketing]);

  const handleMarketingToggle = (enabled: boolean) => {
    setEnableMarketing(enabled);
    
    // Clear marketing data immediately when disabled
    if (!enabled) {
      setValue('marketing_audience', '');
      setValue('marketing_objective', '');
      setValue('marketing_voice', '');
      setValue('marketing_niche', '');
    }
  };

  return (
    <Card sx={{ 
      border: 1,
      borderColor: enableMarketing ? 'success.main' : alpha(theme.palette.primary.main, 0.08),
      backgroundColor: enableMarketing ? alpha(theme.palette.success.main, 0.02) : 'background.paper',
      transition: 'all 0.2s ease-in-out',
      elevation: 2
    }}>
      <CardContent sx={{ pb: isExpanded ? 2 : '16px !important' }}>
        <Box 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            mb: enableMarketing ? 2 : 0
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <TrendingUpIcon sx={{ mr: 1, color: enableMarketing ? 'success.main' : 'text.secondary' }} />
            <Typography 
              id="marketing-lens-title"
              variant="h6" 
              sx={{ fontWeight: 600, color: enableMarketing ? 'success.main' : 'text.primary' }}
            >
              Marketing Strategy
            </Typography>
            {hasMarketingData && (
              <Chip
                label="Configured"
                size="small"
                color="success"
                sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
              />
            )}
            <Tooltip title="Define your marketing strategy to create more targeted and effective content" {...TOOLTIP_CONFIG}>
              <IconButton size="small" sx={{ ml: 1, p: 0.5 }}>
                <InfoIcon sx={INFO_ICON_STYLE} />
              </IconButton>
            </Tooltip>
          </Box>
          
          <FormControlLabel
            control={
              <Switch
                checked={enableMarketing}
                disabled={isSubmitting}
                size="small"
                onChange={(e) => handleMarketingToggle(e.target.checked)}
                onClick={(e) => e.stopPropagation()} // Prevent double toggle
              />
            }
            label=""
            sx={{ m: 0 }}
          />
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
                <Box id="marketing-lens-content" role="region" aria-labelledby="marketing-lens-title">
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                    Define your marketing strategy to create more targeted and effective content
                  </Typography>

                  <Grid container spacing={3}>
                    <Grid item xs={12} md={6}>
                      <Controller
                        name="marketing_audience"
                        control={control}
                        render={({ field }) => (
                          <TextField
                            {...field}
                            fullWidth
                            label="Target Audience"
                            placeholder="e.g., Young professionals, Food enthusiasts, Local families"
                            variant="outlined"
                            size="small"
                            disabled={isSubmitting}
                            error={!!errors.marketing_audience}
                            helperText={errors.marketing_audience?.message}
                          />
                        )}
                      />
                    </Grid>

                    <Grid item xs={12} md={6}>
                      <Controller
                        name="marketing_objective"
                        control={control}
                        render={({ field }) => (
                          <TextField
                            {...field}
                            fullWidth
                            label="Marketing Objective"
                            placeholder="e.g., Increase brand awareness, Drive sales, Build community"
                            variant="outlined"
                            size="small"
                            disabled={isSubmitting}
                            error={!!errors.marketing_objective}
                            helperText={errors.marketing_objective?.message}
                          />
                        )}
                      />
                    </Grid>

                    <Grid item xs={12} md={6}>
                      <Controller
                        name="marketing_voice"
                        control={control}
                        render={({ field }) => (
                          <TextField
                            {...field}
                            fullWidth
                            label="Brand Voice"
                            placeholder="e.g., Friendly and approachable, Professional and trustworthy"
                            variant="outlined"
                            size="small"
                            disabled={isSubmitting}
                            error={!!errors.marketing_voice}
                            helperText={errors.marketing_voice?.message}
                          />
                        )}
                      />
                    </Grid>

                    <Grid item xs={12} md={6}>
                      <Controller
                        name="marketing_niche"
                        control={control}
                        render={({ field }) => (
                          <TextField
                            {...field}
                            fullWidth
                            label="Market Niche"
                            placeholder="e.g., Sustainable dining, Artisanal coffee, Asian fusion"
                            variant="outlined"
                            size="small"
                            disabled={isSubmitting}
                            error={!!errors.marketing_niche}
                            helperText={errors.marketing_niche?.message}
                          />
                        )}
                      />
                    </Grid>
                  </Grid>
                </Box>
              </Collapse>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

export default LensMarketing;
