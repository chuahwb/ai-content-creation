'use client';

import React from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  Tooltip,
  Chip,
  Stack,
  Paper,
  useTheme,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Palette as PaletteIcon,
  Delete as DeleteIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { BrandColor } from '../types/api';
import EnhancedColorBar from './EnhancedColorBar';

// Enhanced color roles (copied from EnhancedColorPaletteEditor)
const COLOR_ROLES = {
  primary: { 
    label: 'Primary', 
    description: 'Main brand color, used for key elements', 
    tooltip: 'Primary: Dominant color for backgrounds and key elements (60% rule)',
    baseRatio: 0.6,
    priority: 1,
    maxCount: 2 
  },
  secondary: { 
    label: 'Secondary', 
    description: 'Supporting brand color', 
    tooltip: 'Secondary: Supporting brand color for complementary elements (30% rule)',
    baseRatio: 0.3,
    priority: 2,
    maxCount: 3 
  },
  accent: { 
    label: 'Accent', 
    description: 'Highlight color for calls-to-action', 
    tooltip: 'Accent: Highlight color for calls-to-action and emphasis (10% rule)',
    baseRatio: 0.1,
    priority: 3,
    maxCount: 2 
  },
  neutral_light: { 
    label: 'Light Neutral', 
    description: 'Light backgrounds and subtle elements', 
    tooltip: 'Light Neutral: For light backgrounds, cards, and subtle UI elements',
    baseRatio: 0,  // Functional, not part of 60-30-10 rule
    priority: 4,
    maxCount: 1 
  },
  neutral_dark: { 
    label: 'Dark Neutral', 
    description: 'Text and dark backgrounds', 
    tooltip: 'Dark Neutral: For text, dark backgrounds, and high-contrast elements',
    baseRatio: 0,  // Functional, not part of 60-30-10 rule
    priority: 5,
    maxCount: 1 
  },
};

const getContrastColor = (hexColor: string): string => {
  const r = parseInt(hexColor.slice(1, 3), 16);
  const g = parseInt(hexColor.slice(3, 5), 16);
  const b = parseInt(hexColor.slice(5, 7), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000000' : '#FFFFFF';
};

interface CompactColorPreviewProps {
  colors: BrandColor[];
  onEditClick: () => void;
  onRemove?: () => void;
  maxDisplayColors?: number;
  showRatios?: boolean;
}

export default function CompactColorPreview({
  colors,
  onEditClick,
  onRemove,
  maxDisplayColors = 6,
  showRatios = true,
}: CompactColorPreviewProps) {
  const theme = useTheme();

  const formatRatio = (ratio?: number): string => {
    if (!ratio) return '';
    return `${Math.round(ratio * 100)}%`;
  };

  if (colors.length === 0) {
    return (
      <Paper
        sx={{
          p: 2,
          border: 2,
          borderColor: 'divider',
          borderStyle: 'dashed',
          borderRadius: 2,
          textAlign: 'center',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          '&:hover': {
            borderColor: 'primary.main',
            backgroundColor: 'action.hover',
          },
        }}
        onClick={onEditClick}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <PaletteIcon sx={{ fontSize: 32, color: 'text.secondary' }} />
          <Typography variant="body2" color="text.secondary">
            Click to add brand colors
          </Typography>
        </Box>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{
        p: 1.5,
        border: 1,
        borderColor: 'divider',
        borderRadius: 2,
        transition: 'all 0.2s ease',
        '&:hover': {
          borderColor: 'primary.main',
          boxShadow: 1,
        },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
        <Typography variant="caption" fontWeight="medium" color="text.secondary">
          Brand Colors ({colors.length})
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          {onRemove && colors.length > 0 && (
            <Button
              size="small"
              variant="outlined"
              color="error"
              startIcon={<ClearIcon />}
              onClick={onRemove}
              sx={{
                fontSize: '0.7rem',
                py: 0.25,
                px: 1,
                minWidth: 'auto',
                minHeight: 24,
              }}
            >
              Reset
            </Button>
          )}
          <Button
            size="small"
            variant="outlined"
            startIcon={<EditIcon />}
            onClick={onEditClick}
            sx={{
              fontSize: '0.7rem',
              py: 0.25,
              px: 1,
              minWidth: 'auto',
              minHeight: 24,
            }}
          >
            Edit
          </Button>
        </Box>
      </Box>

      {/* Enhanced Color Bar Preview */}
      <EnhancedColorBar
        colors={colors}
        height={48}
        onClick={onEditClick}
        showLabels={true}
        borderRadius={8}
      />

      {/* Summary info */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
        <Stack direction="row" spacing={0.5}>
          {colors.some(c => c.isAuto) && (
            <Chip
              label="Auto Neutrals"
              size="small"
              variant="outlined"
              sx={{ fontSize: '0.6rem', height: 18 }}
            />
          )}
          {colors.some(c => c.isCustomRatio) && (
            <Chip
              label="Custom Ratios"
              size="small"
              variant="outlined"
              sx={{ fontSize: '0.6rem', height: 18 }}
            />
          )}
        </Stack>
        
        <Typography variant="caption" color="text.secondary">
          Click to edit
        </Typography>
      </Box>
    </Paper>
  );
}