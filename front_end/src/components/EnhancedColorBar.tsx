'use client';

import React from 'react';
import {
  Box,
  Typography,
  Tooltip,
  useTheme,
} from '@mui/material';
import { BrandColor } from '../types/api';

// Enhanced color roles with priority ordering
const COLOR_ROLES = {
  primary: { 
    label: 'Primary', 
    priority: 1,
    gradientStops: ['rgba(255,255,255,0.1)', 'rgba(0,0,0,0.05)'],
    borderStyle: 'solid',
    borderWidth: 2
  },
  secondary: { 
    label: 'Secondary', 
    priority: 2,
    gradientStops: ['rgba(255,255,255,0.08)', 'rgba(0,0,0,0.03)'],
    borderStyle: 'solid',
    borderWidth: 1.5
  },
  accent: { 
    label: 'Accent', 
    priority: 3,
    gradientStops: ['rgba(255,255,255,0.15)', 'rgba(0,0,0,0.08)'],
    borderStyle: 'solid',
    borderWidth: 1
  },
  neutral_light: { 
    label: 'Light Neutral', 
    priority: 4,
    gradientStops: ['rgba(255,255,255,0.05)', 'rgba(0,0,0,0.02)'],
    borderStyle: 'dashed',
    borderWidth: 1
  },
  neutral_dark: { 
    label: 'Dark Neutral', 
    priority: 5,
    gradientStops: ['rgba(255,255,255,0.05)', 'rgba(0,0,0,0.02)'],
    borderStyle: 'dashed',
    borderWidth: 1
  },
};

const getContrastColor = (hexColor: string): string => {
  const r = parseInt(hexColor.slice(1, 3), 16);
  const g = parseInt(hexColor.slice(3, 5), 16);
  const b = parseInt(hexColor.slice(5, 7), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000000' : '#FFFFFF';
};

// Helper to darken/lighten color for subtle variations
const adjustColorBrightness = (hex: string, factor: number): string => {
  const r = Math.min(255, Math.max(0, parseInt(hex.slice(1, 3), 16) + factor));
  const g = Math.min(255, Math.max(0, parseInt(hex.slice(3, 5), 16) + factor));
  const b = Math.min(255, Math.max(0, parseInt(hex.slice(5, 7), 16) + factor));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
};

interface EnhancedColorBarProps {
  colors: BrandColor[];
  height?: number;
  onClick?: () => void;
  showLabels?: boolean;
  borderRadius?: number;
}

export default function EnhancedColorBar({
  colors,
  height = 48,
  onClick,
  showLabels = true,
  borderRadius = 8,
}: EnhancedColorBarProps) {
  const theme = useTheme();

  // Sort colors by role priority for logical visual ordering
  const sortedColors = [...colors].sort((a, b) => {
    const aPriority = COLOR_ROLES[a.role as keyof typeof COLOR_ROLES]?.priority || 999;
    const bPriority = COLOR_ROLES[b.role as keyof typeof COLOR_ROLES]?.priority || 999;
    return aPriority - bPriority;
  });

  if (colors.length === 0) {
    return (
      <Box
        sx={{
          height,
          borderRadius: borderRadius / 8,
          border: `2px dashed ${theme.palette.divider}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: theme.palette.action.hover,
          cursor: onClick ? 'pointer' : 'default',
          transition: 'all 0.3s ease',
          '&:hover': onClick ? {
            borderColor: theme.palette.primary.main,
            backgroundColor: theme.palette.action.selected,
          } : {},
        }}
        onClick={onClick}
      >
        <Typography variant="caption" color="text.secondary" fontWeight="medium">
          No colors selected
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        display: 'flex',
        height,
        borderRadius: borderRadius / 8,
        overflow: 'hidden',
        position: 'relative',
        cursor: onClick ? 'pointer' : 'default',
        boxShadow: `0 2px 8px rgba(0,0,0,0.1), 0 1px 3px rgba(0,0,0,0.08)`,
        border: `1px solid ${theme.palette.divider}`,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        '&:hover': onClick ? {
          transform: 'translateY(-1px)',
          boxShadow: `0 4px 16px rgba(0,0,0,0.15), 0 2px 6px rgba(0,0,0,0.1)`,
        } : {},
      }}
      onClick={onClick}
    >
      {sortedColors.map((color, index) => {
        const roleConfig = COLOR_ROLES[color.role as keyof typeof COLOR_ROLES];
        const roleAbbrev = roleConfig?.label?.slice(0, 3) || color.role.slice(0, 3).toUpperCase();
        const flexValue = color.ratio || (1 / colors.length);
        const isLargeSegment = flexValue > 0.12;
        
        // Create gradient overlay for depth
        const gradientOverlay = roleConfig ? 
          `linear-gradient(145deg, ${roleConfig.gradientStops[0]}, ${roleConfig.gradientStops[1]})` : 
          'linear-gradient(145deg, rgba(255,255,255,0.05), rgba(0,0,0,0.02))';

        return (
          <Tooltip 
            key={index}
            title={
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="body2" fontWeight="bold">
                  {roleConfig?.label || color.role}
                </Typography>
                <Typography variant="caption" color="inherit">
                  {color.hex} • {Math.round(flexValue * 100)}%
                </Typography>
                {color.label && (
                  <Typography variant="caption" sx={{ display: 'block', fontStyle: 'italic' }}>
                    "{color.label}"
                  </Typography>
                )}
              </Box>
            }
            placement="top"
            arrow
          >
            <Box
              sx={{
                flex: flexValue,
                background: `linear-gradient(180deg, ${color.hex} 0%, ${adjustColorBrightness(color.hex, -10)} 100%)`,
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRight: index < sortedColors.length - 1 ? `1px solid rgba(255,255,255,0.2)` : 'none',
                transition: 'all 0.2s ease',
                '&:hover': {
                  filter: 'brightness(1.1) saturate(1.1)',
                  zIndex: 1,
                },
                // Add subtle inner shadow for depth
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: gradientOverlay,
                  pointerEvents: 'none',
                },
                // Add role-specific visual indicators
                '&::after': roleConfig?.borderStyle === 'dashed' ? {
                  content: '""',
                  position: 'absolute',
                  top: 2,
                  left: 2,
                  right: 2,
                  bottom: 2,
                  border: `1px dashed rgba(255,255,255,0.4)`,
                  borderRadius: 2,
                  pointerEvents: 'none',
                } : {},
              }}
            >
              {/* Role abbreviation with enhanced styling */}
              {isLargeSegment && showLabels && (
                <Typography
                  variant="caption"
                  sx={{
                    color: getContrastColor(color.hex),
                    fontWeight: 800,
                    fontSize: '0.7rem',
                    textShadow: `0 1px 3px rgba(0,0,0,0.6), 0 1px 1px rgba(0,0,0,0.8)`,
                    letterSpacing: 0.8,
                    textTransform: 'uppercase',
                    position: 'relative',
                    zIndex: 2,
                    // Add subtle background for better readability
                    backgroundColor: `rgba(${getContrastColor(color.hex) === '#000000' ? '255,255,255' : '0,0,0'}, 0.1)`,
                    borderRadius: 2,
                    px: 0.5,
                    py: 0.2,
                    backdropFilter: 'blur(2px)',
                  }}
                >
                  {roleAbbrev}
                </Typography>
              )}
              
              {/* Percentage indicator for very large segments */}
              {flexValue > 0.25 && showLabels && (
                <Typography
                  variant="caption"
                  sx={{
                    position: 'absolute',
                    bottom: 2,
                    right: 4,
                    color: getContrastColor(color.hex),
                    fontSize: '0.6rem',
                    fontWeight: 600,
                    opacity: 0.8,
                    textShadow: '0 1px 2px rgba(0,0,0,0.5)',
                    zIndex: 2,
                  }}
                >
                  {Math.round(flexValue * 100)}%
                </Typography>
              )}
            </Box>
          </Tooltip>
        );
      })}
      
      {/* Subtle inner shadow overlay for the entire bar */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)',
          borderRadius: borderRadius / 8,
          pointerEvents: 'none',
        }}
      />
    </Box>
  );
}