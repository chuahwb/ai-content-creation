'use client';

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Image as ImageIcon,
} from '@mui/icons-material';

interface LogoAnalysis {
  filename?: string;
  file_size_kb?: number;
  dimensions?: string;
  format?: string;
  preview_url?: string;
}

interface CompactLogoDisplayProps {
  logo: LogoAnalysis;
  onRemove?: () => void;
  showRemoveButton?: boolean;
}

const formatFileSize = (sizeKb: number): string => {
  if (sizeKb < 1024) {
    return `${Math.round(sizeKb)} KB`;
  }
  return `${(sizeKb / 1024).toFixed(1)} MB`;
};

const getFileTypeIcon = (format: string) => {
  switch (format?.toLowerCase()) {
    case 'svg':
    case 'png':
      return <CheckCircleIcon color="success" sx={{ fontSize: 14 }} />;
    default:
      return <ImageIcon color="info" sx={{ fontSize: 14 }} />;
  }
};

export default function CompactLogoDisplay({
  logo,
  onRemove,
  showRemoveButton = true,
}: CompactLogoDisplayProps) {
  const isOptimized = logo.file_size_kb ? logo.file_size_kb > 0 && logo.file_size_kb <= 200 : false;

  return (
    <Paper 
      sx={{ 
        p: 2, 
        border: 1, 
        borderColor: 'divider',
        backgroundColor: 'grey.50',
        borderRadius: 2
      }}
    >
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        {/* Logo Preview */}
        <Box sx={{ flexShrink: 0 }}>
          <Paper
            sx={{
              width: 60,
              height: 60,
              border: 1,
              borderColor: 'divider',
              borderRadius: 1,
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'background.paper',
            }}
          >
            {logo.preview_url ? (
              <Box
                component="img"
                src={logo.preview_url}
                alt="Logo"
                sx={{
                  maxWidth: '100%',
                  maxHeight: '100%',
                  objectFit: 'contain',
                }}
              />
            ) : (
              <ImageIcon sx={{ fontSize: 24, color: 'grey.400' }} />
            )}
          </Paper>
        </Box>

        {/* Logo Information */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" sx={{ 
            fontWeight: 600, 
            mb: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            {logo.filename || 'Brand Logo'}
          </Typography>
          
          <Stack direction="row" spacing={0.5} sx={{ mb: 1, flexWrap: 'wrap', gap: 0.5 }}>
            {logo.format && (
              <Chip
                icon={getFileTypeIcon(logo.format)}
                label={logo.format.toUpperCase()}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
            )}
            
            {logo.file_size_kb && logo.file_size_kb > 0 && (
              <Chip
                label={formatFileSize(logo.file_size_kb)}
                size="small"
                variant="outlined"
                color={isOptimized ? 'success' : 'warning'}
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
            )}
            
            {logo.dimensions && (
              <Chip
                label={logo.dimensions}
                size="small"
                variant="outlined"
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
            )}
          </Stack>

          {logo.file_size_kb && logo.file_size_kb > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {isOptimized ? (
                <CheckCircleIcon color="success" sx={{ fontSize: 14 }} />
              ) : (
                <WarningIcon color="warning" sx={{ fontSize: 14 }} />
              )}
              <Typography variant="caption" color={isOptimized ? 'success.main' : 'warning.main'}>
                {isOptimized ? 'Optimized' : 'Consider optimization'}
              </Typography>
            </Box>
          )}
        </Box>

        {/* Remove Button */}
        {showRemoveButton && onRemove && (
          <Box sx={{ flexShrink: 0 }}>
            <Tooltip title="Remove logo">
              <IconButton 
                onClick={onRemove} 
                size="small"
                color="error"
                sx={{ p: 0.5 }}
              >
                <DeleteIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        )}
      </Box>
    </Paper>
  );
} 