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
  Chip,
  Tooltip,
  IconButton,
  alpha,
  useTheme
} from '@mui/material';
import { 
  TextFields as TextFieldsIcon
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import { Control, UseFormWatch, UseFormSetValue, Controller } from 'react-hook-form';
import { PipelineFormData, UnifiedBrief } from '@/types/api';
import TextOverlayComposer from '../TextOverlayComposer';
import { TOOLTIP_CONFIG, TOOLTIP_STRINGS, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { Info as InfoIcon } from '@mui/icons-material';

interface LensTextProps {
  control: Control<PipelineFormData>;
  watch: UseFormWatch<PipelineFormData>;
  setValue: UseFormSetValue<PipelineFormData>;
  isSubmitting: boolean;
  renderText: boolean;
  unifiedBrief: UnifiedBrief;
  setUnifiedBrief: (brief: UnifiedBrief) => void;
}

function LensText({
  control,
  watch,
  setValue,
  isSubmitting,
  renderText,
  unifiedBrief,
  setUnifiedBrief,
}: LensTextProps) {
  const theme = useTheme();
  const [isExpanded, setIsExpanded] = useState(renderText);

  const hasTextContent = Boolean(unifiedBrief.textOverlay?.raw?.trim());

  // Drive expansion directly from switch state
  React.useEffect(() => {
    setIsExpanded(renderText);
  }, [renderText]);

  // Clear text overlay data when render_text is turned off
  React.useEffect(() => {
    if (!renderText && hasTextContent) {
      const clearedBrief = {
        ...unifiedBrief,
        textOverlay: { raw: '' }
      };
      setUnifiedBrief(clearedBrief);
      setValue('unifiedBrief', clearedBrief);
    }
  }, [renderText, hasTextContent, unifiedBrief, setUnifiedBrief, setValue]);

  return (
    <Card sx={{ 
      border: 1,
      borderColor: renderText ? 'secondary.main' : alpha(theme.palette.primary.main, 0.08),
      backgroundColor: renderText ? alpha(theme.palette.secondary.main, 0.02) : 'background.paper',
      transition: 'all 0.2s ease-in-out',
      elevation: 2
    }}>
      <CardContent sx={{ pb: isExpanded ? 2 : '16px !important' }}>
        <Box 
          sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            mb: renderText ? 2 : 0
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <TextFieldsIcon sx={{ mr: 1, color: renderText ? 'secondary.main' : 'text.secondary' }} />
            <Typography 
              id="text-lens-title"
              variant="h6" 
              sx={{ fontWeight: 600, color: renderText ? 'secondary.main' : 'text.primary' }}
            >
              Text Overlay
            </Typography>
            {hasTextContent && (
              <Chip
                label="Has Content"
                size="small"
                color="info"
                sx={{ ml: 1, height: 20, fontSize: '0.7rem' }}
              />
            )}
            <Tooltip title="Add text overlays to your images with professional typography and styling" {...TOOLTIP_CONFIG}>
              <IconButton size="small" sx={{ ml: 1, p: 0.5 }}>
                <InfoIcon sx={INFO_ICON_STYLE} />
              </IconButton>
            </Tooltip>
          </Box>
          
          <Tooltip title={TOOLTIP_STRINGS.renderText} {...TOOLTIP_CONFIG}>
            <Controller
              name="render_text"
              control={control}
              render={({ field }) => (
                <Switch
                  {...field}
                  checked={field.value}
                  disabled={isSubmitting}
                  size="small"
                  onClick={(e) => e.stopPropagation()} // Prevent double toggle
                />
              )}
            />
          </Tooltip>
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
                                        <Box id="text-lens-content" role="region" aria-labelledby="text-lens-title">
                          <Controller
                            name="unifiedBrief"
                            control={control}
                            render={({ field }) => (
                              <TextOverlayComposer
                                value={unifiedBrief.textOverlay?.raw || ''}
                                onChange={(text) => {
                                  const updatedBrief = {
                                    ...unifiedBrief,
                                    textOverlay: { ...unifiedBrief.textOverlay, raw: text }
                                  };
                                  setUnifiedBrief(updatedBrief);
                                  field.onChange(updatedBrief);
                                }}
                                disabled={isSubmitting}
                                visible={true}
                                embedded={true}
                              />
                            )}
                          />
                        </Box>
              </Collapse>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}

export default LensText;
