'use client';

import React from 'react';
import { Box, Typography, Tooltip, useTheme } from '@mui/material';
import { BrandColor } from '../../types/api';
import { getPaletteStyles } from '../../lib/palette-utils';

interface PromotionalAnnouncementPreviewProps {
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

export const PromotionalAnnouncementPreview: React.FC<PromotionalAnnouncementPreviewProps> = ({ 
  colors, 
}) => {
  const theme = useTheme();
  const { primary, secondary, accent, neutralLight, neutralDark, supporting } = getPaletteStyles(colors);

  const size = 120;

  return (
    <Tooltip title="Promotional Announcement Preview">
      <Box sx={{ width: size, height: size, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <Typography variant="caption" sx={{ fontSize: '0.6rem', mb: 0.5, textAlign: 'center' }}>
          Promotion
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
            <linearGradient id="promoBgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={primary} />
              <stop offset="100%" stopColor={secondary} />
            </linearGradient>
            <filter id="subtleShadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="1" dy="1" stdDeviation="1.5" floodColor="#000" floodOpacity="0.15"/>
            </filter>
          </defs>

          {/* Base background */}
          <rect x="0" y="0" width="120" height="120" fill="url(#promoBgGrad)" />

          {/* Dynamically generated supporting color shapes */}
          {supporting.map((color, index) => {
            const size = 80 - index * 10;
            const opacity = 0.5 - index * 0.1;
            return (
              <rect
                key={index}
                x={(120 - size) / 2}
                y={(120 - size) / 2}
                width={size}
                height={size}
                fill={color}
                opacity={opacity}
                transform={`rotate(${-15 + index * 10}, 60, 60)`}
                rx="10"
              />
            );
          })}
          
          {/* Text Content in a semi-transparent panel for readability */}
          <rect x="10" y="30" width="100" height="60" rx="8" fill={`${neutralLight}B3`} style={{ backdropFilter: 'blur(4px)' }} />
          
          <g style={{ fontFamily: 'Arial, sans-serif' }} textAnchor="middle">
            <text 
              x="60" 
              y="50" 
              fontSize="14" 
              fontWeight="900" 
              fill={neutralDark}
              filter="url(#subtleShadow)"
            >
              BIG SALE
            </text>
            <text 
              x="60" 
              y="75" 
              fontSize="22" 
              fontWeight="900" 
              fill={accent}
              filter="url(#subtleShadow)"
            >
              50% OFF
            </text>
          </g>
          
          {/* CTA Button is now inside the panel */}
          <g>
            <rect 
              x="25" 
              y="95" 
              width="70" 
              height="18" 
              rx="9" 
              fill={accent} 
              style={{ cursor: 'pointer' }}
              filter="url(#subtleShadow)"
            />
            <text 
              x="60" 
              y="108" 
              fontSize="8" 
              fontWeight="bold" 
              fill={getContrastColor(accent)} 
              textAnchor="middle" 
              style={{ pointerEvents: 'none' }}
            >
              SHOP NOW
            </text>
          </g>
        </svg>
      </Box>
    </Tooltip>
  );
};

export default PromotionalAnnouncementPreview;