'use client';

import React from 'react';
import { Box, Typography, Tooltip, useTheme } from '@mui/material';
import { BrandColor } from '../../types/api';
import { getPaletteStyles } from '../../lib/palette-utils';

interface ProductFocusedPreviewProps {
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

export const ProductFocusedPreview: React.FC<ProductFocusedPreviewProps> = ({ 
  colors, 
}) => {
  const theme = useTheme();
  const { primary, secondary, accent, neutralLight, neutralDark, supporting } = getPaletteStyles(colors);

  const size = 120;

  return (
    <Tooltip title="Product-Focused Ad Preview">
      <Box sx={{ width: size, height: size, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <Typography variant="caption" sx={{ fontSize: '0.6rem', mb: 0.5, textAlign: 'center' }}>
          Product Ad
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
            <linearGradient id="productCardBg" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={neutralLight} />
              <stop offset="100%" stopColor={`${supporting.length > 0 ? supporting[0] : primary}1A`} />
            </linearGradient>
            <filter id="productShadow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="2" stdDeviation="3" floodColor="#000" floodOpacity="0.1"/>
            </filter>
          </defs>

          <rect x="0" y="0" width="120" height="120" fill="url(#productCardBg)" />

          <g>
            <rect x="10" y="10" width="100" height="70" rx="8" fill={secondary} opacity="0.1" />
            
            {/* Dynamically generated supporting color stripes */}
            {supporting.map((color, index) => {
              const stripeWidth = 12 - index * 2;
              const opacity = 0.6 - index * 0.1;
              return (
                <rect
                  key={index}
                  x={15 + index * 15}
                  y="10"
                  width={stripeWidth}
                  height="70"
                  fill={color}
                  opacity={opacity}
                  rx="2"
                />
              );
            })}

            <path 
              d="M60,30 C80,30 85,40 85,55 S80,80 60,80 35,70 35,55 40,30 60,30 Z"
              fill={primary}
              stroke={neutralLight}
              strokeWidth="2.5"
              filter="url(#productShadow)"
            />
            <circle cx="60" cy="55" r="6" fill={accent} />
          </g>

          <g style={{ fontFamily: 'Arial, sans-serif' }}>
            <text 
              x="15" 
              y="98" 
              fontSize="10" 
              fontWeight="bold" 
              fill={neutralDark}
            >
              Product Name
            </text>
            <text 
              x="15" 
              y="116" 
              fontSize="12" 
              fontWeight="900" 
              fill={primary}
            >
              $99
            </text>
          </g>
          
          <g style={{ cursor: 'pointer' }}>
            <rect 
              x="80" 
              y="92" 
              width="30" 
              height="20" 
              rx="10" 
              fill={accent} 
            />
            <text 
              x="95" 
              y="106" 
              fontSize="12" 
              fontWeight="bold" 
              fill={getContrastColor(accent)} 
              textAnchor="middle" 
              style={{ pointerEvents: 'none' }}
            >
              +
            </text>
          </g>
        </svg>
      </Box>
    </Tooltip>
  );
};

export default ProductFocusedPreview;