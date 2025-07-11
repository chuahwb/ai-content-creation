'use client';

import React, { useState } from 'react';
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';
import { Box, Chip } from '@mui/material';
import { CompareArrows as CompareArrowsIcon } from '@mui/icons-material';

interface ImageCompareSliderProps {
  beforeImageUrl: string;
  afterImageUrl: string;
  height?: number;
  onImageClick?: (imageUrl: string) => void;
}

const ImageCompareSlider: React.FC<ImageCompareSliderProps> = ({ 
  beforeImageUrl, 
  afterImageUrl, 
  height = 200,
  onImageClick
}) => {
  const [isHovered, setIsHovered] = useState(false);

  const handleClick = () => {
    if (onImageClick) {
      onImageClick(afterImageUrl); // Default to showing the refined image in full view
    }
  };

  return (
    <Box 
      sx={{
        width: '100%',
        height: height,
        borderRadius: 1,
        overflow: 'hidden',
        position: 'relative',
        cursor: onImageClick ? 'pointer' : 'default',
        transition: 'all 0.2s ease-in-out',
        '&:hover': onImageClick ? {
          transform: 'scale(1.02)',
          boxShadow: 2,
        } : {},
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={handleClick}
    >
      <ReactCompareSlider
        itemOne={<ReactCompareSliderImage src={beforeImageUrl} alt="Before" />}
        itemTwo={<ReactCompareSliderImage src={afterImageUrl} alt="After" />}
        style={{
          width: '100%',
          height: '100%',
        }}
      />
      
      {/* Overlay labels */}
      <Box
        sx={{
          position: 'absolute',
          top: 8,
          left: 8,
          right: 8,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
          opacity: isHovered ? 1 : 0.7,
          transition: 'opacity 0.2s ease-in-out',
        }}
      >
        <Chip
          label="Before"
          size="small"
          sx={{
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            color: 'white',
            fontWeight: 500,
            fontSize: '0.7rem',
            height: 24,
          }}
        />
        <CompareArrowsIcon sx={{ color: 'white', fontSize: 20, filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.5))' }} />
        <Chip
          label="After"
          size="small"
          sx={{
            backgroundColor: 'rgba(33, 150, 243, 0.9)',
            color: 'white',
            fontWeight: 500,
            fontSize: '0.7rem',
            height: 24,
          }}
        />
      </Box>
      
      {/* Hover instruction */}
      {isHovered && onImageClick && (
        <Box
          sx={{
            position: 'absolute',
            bottom: 8,
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            color: 'white',
            px: 2,
            py: 0.5,
            borderRadius: 1,
            fontSize: '0.75rem',
            fontWeight: 500,
            pointerEvents: 'none',
            opacity: 0.9,
          }}
        >
          Click to view full size
        </Box>
      )}
    </Box>
  );
};

export default ImageCompareSlider; 