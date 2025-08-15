'use client';

import React from 'react';
import { Box, Typography, Tooltip, useTheme } from '@mui/material';
import { BrandColor } from '../../types/api';
import { getPaletteStyles } from '../../lib/palette-utils';

interface LifestyleAtmospherePreviewProps {
  colors: BrandColor[];
}

const getContrastColor = (hexColor: string): string => {
  if (!hexColor) return '#000';
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substr(0, 2), 16);
  const g = parseInt(hex.substr(2, 2), 16);
  const b = parseInt(hex.substr(4, 2), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? '#000' : '#fff';
};

export const LifestyleAtmospherePreview: React.FC<LifestyleAtmospherePreviewProps> = ({ 
  colors, 
}) => {
  const theme = useTheme();
  const { primary, secondary, accent, neutralLight, neutralDark, supporting } = getPaletteStyles(colors);

  const size = 120;

  return (
    <Tooltip title="Lifestyle Atmosphere Preview">
      <Box sx={{ width: size, height: size, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <Typography variant="caption" sx={{ fontSize: '0.6rem', mb: 0.5, textAlign: 'center' }}>
          Lifestyle Scene
        </Typography>
        <svg 
          width="100%" 
          height="100%" 
          viewBox="0 0 120 120"
          style={{ 
            border: `1px solid ${theme.palette.divider}`, 
            borderRadius: '12px', 
            boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
            overflow: 'hidden'
          }}
        >
          <defs>
            <linearGradient id="lifeBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={primary} />
              {supporting.length > 0 && <stop offset="50%" stopColor={supporting[0]} />}
              <stop offset="100%" stopColor={secondary} />
            </linearGradient>
            <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur" />
            </filter>
            <pattern id="dotPattern" x="0" y="0" width="12" height="12" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="0.75" fill={neutralLight} opacity="0.1" />
            </pattern>
          </defs>

          <rect x="0" y="0" width="120" height="120" fill="url(#lifeBgGrad)" />
          <rect x="0" y="0" width="120" height="120" fill="url(#dotPattern)" />

          {/* Dynamically generated supporting color orbs */}
          <g filter="url(#softGlow)">
            {supporting.map((color, index) => {
              const orbSize = 40 - index * 5;
              const cx = 30 + (index % 3) * 30;
              const cy = 40 + Math.floor(index / 3) * 30;
              const opacity = 0.5 - index * 0.08;
              return (
                <circle
                  key={index}
                  cx={cx}
                  cy={cy}
                  r={orbSize}
                  fill={color}
                  opacity={opacity}
                />
              );
            })}
            <circle cx="90" cy="30" r="30" fill={accent} opacity="0.7" />
          </g>

          <g style={{ fontFamily: 'Arial, sans-serif', textAnchor: 'middle' }}>
            <text 
              x="60" 
              y="55" 
              fontSize="11" 
              fontWeight="bold" 
              fill={getContrastColor(primary)}
              letterSpacing="0.5"
            >
              Live Your
            </text>
            <text 
              x="60" 
              y="75" 
              fontSize="14" 
              fontWeight="900" 
              fill={getContrastColor(primary)}
            >
              Best Life
            </text>
          </g>
        </svg>
      </Box>
    </Tooltip>
  );
};

export default LifestyleAtmospherePreview;