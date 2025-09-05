'use client';

import * as React from 'react';
import { 
  Box, 
  Typography, 
  Grid, 
  Card, 
  CardContent, 
  CardActionArea,
  Chip,
  Tooltip,
  IconButton,
  useTheme,
  alpha
} from '@mui/material';
import { motion } from 'framer-motion';

import { TEMPLATE_OPTIONS } from '@/lib/constants';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { Info as InfoIcon } from '@mui/icons-material';

interface TemplateGalleryProps {
  selectedTaskType: string;
  onTaskTypeSelect: (taskType: string) => void;
  disabled?: boolean;
}

function TemplateGallery({ 
  selectedTaskType, 
  onTaskTypeSelect, 
  disabled = false 
}: TemplateGalleryProps) {
  const theme = useTheme();

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Choose a Template
        </Typography>
        <Chip 
          label="Optional" 
          size="small" 
          variant="outlined" 
          sx={{ height: 20, fontSize: '0.7rem' }}
        />
        <Tooltip title="Templates provide pre-configured settings for common content types. You can always customize further after selection." {...TOOLTIP_CONFIG}>
          <IconButton size="small" sx={{ p: 0.5 }}>
            <InfoIcon sx={INFO_ICON_STYLE} />
          </IconButton>
        </Tooltip>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Select a template to get started quickly, or skip to create from scratch
      </Typography>
      
      <Grid container spacing={2}>
        {TEMPLATE_OPTIONS.map((template, index) => (
          <Grid item xs={12} sm={6} md={3} key={template.id}>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.05 }}
              whileHover={{ y: -4, scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Card 
                sx={{ 
                  height: 200, // Fixed height for consistency
                  position: 'relative',
                  overflow: 'visible',
                  border: selectedTaskType === template.id ? 2 : 1,
                  borderColor: selectedTaskType === template.id 
                    ? template.color 
                    : alpha(theme.palette.divider, 0.12),
                  boxShadow: selectedTaskType === template.id
                    ? `0 8px 24px ${alpha(template.color, 0.25)}`
                    : theme.shadows[1],
                  transition: 'all 0.2s ease-in-out',
                  '&:hover': {
                    boxShadow: `0 8px 24px ${alpha(template.color, 0.15)}`,
                    borderColor: alpha(template.color, 0.5),
                  }
                }}
              >
                <CardActionArea
                  onClick={() => onTaskTypeSelect(selectedTaskType === template.id ? '' : template.id)}
                  disabled={disabled}
                  sx={{ height: '100%', p: 0, minHeight: 44 }}
                  aria-label={`${selectedTaskType === template.id ? 'Deselect' : 'Select'} ${template.title} template`}
                  role="button"
                  tabIndex={0}
                >
                  <CardContent sx={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: 'center',
                    textAlign: 'center',
                    p: 3,
                    position: 'relative'
                  }}>
                    {selectedTaskType === template.id && (
                      <Chip
                        label="Selected"
                        size="small"
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          backgroundColor: template.color,
                          color: 'white',
                          fontWeight: 600,
                          fontSize: '0.7rem'
                        }}
                      />
                    )}
                    
                    <Box
                      sx={{
                        width: 64,
                        height: 64,
                        borderRadius: '50%',
                        backgroundColor: alpha(template.color, 0.1),
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mb: 2,
                        fontSize: '2rem',
                        border: `2px solid ${alpha(template.color, 0.2)}`,
                      }}
                    >
                      {template.emoji}
                    </Box>
                    
                    <Typography 
                      variant="subtitle2" 
                      sx={{ 
                        fontWeight: 600, 
                        mb: 1,
                        color: selectedTaskType === template.id ? template.color : 'text.primary'
                      }}
                    >
                      {template.title}
                    </Typography>
                    
                    <Typography 
                      variant="body2" 
                      color="text.secondary"
                      sx={{ 
                        fontSize: '0.85rem',
                        lineHeight: 1.3,
                        opacity: 0.8
                      }}
                    >
                      {template.description}
                    </Typography>
                  </CardContent>
                </CardActionArea>
              </Card>
            </motion.div>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

export default TemplateGallery;
