'use client';

import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  Paper,
  LinearProgress,
  Tooltip,
  Alert,
  Chip,
  Stack,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';

interface LogoUploaderProps {
  onLogoUpload: (file: File, analysis: LogoAnalysis) => void;
  onLogoRemove: () => void;
  currentLogo?: LogoAnalysis | null;
  maxFileSize?: number; // in MB
  showLabels?: boolean;
}

interface LogoAnalysis {
  filename: string;
  file_size_kb: number;
  dimensions?: string;
  format?: string;
  preview_url?: string;
  analysis_notes?: string;
  optimization_suggestions?: string[];
}

// Popular image formats supported by base64 encoding and browsers
const SUPPORTED_FORMATS = {
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'image/svg+xml': ['.svg'],
  'image/bmp': ['.bmp'],
  'image/tiff': ['.tif', '.tiff'],
  'image/ico': ['.ico'],
};

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

const getOptimizationSuggestions = (analysis: LogoAnalysis): string[] => {
  const suggestions: string[] = [];
  
  if (analysis.file_size_kb > 200) {
    suggestions.push('Consider compressing the logo to reduce file size');
  }
  
  // Format-specific optimization suggestions
  const format = analysis.format?.toLowerCase();
  if (format === 'bmp' || format === 'tiff') {
    suggestions.push('Consider converting to PNG or WebP for better compression');
  } else if (format === 'gif' && analysis.file_size_kb > 100) {
    suggestions.push('For static logos, PNG or WebP would provide better quality and smaller size');
  }
  
  if (analysis.dimensions && analysis.dimensions.includes('x')) {
    const [width, height] = analysis.dimensions.split('x').map(Number);
    if (width > 1000 || height > 1000) {
      suggestions.push('Consider using a smaller resolution for web use');
    }
  }
  
  return suggestions;
};

const getFileTypeIcon = (format: string) => {
  // Optimal formats for logos get green checkmark
  switch (format?.toLowerCase()) {
    case 'svg':
    case 'png':
      return <CheckCircleIcon color="success" />;
    case 'webp':
      return <CheckCircleIcon color="success" />;
    case 'jpeg':
    case 'jpg':
    case 'gif':
    case 'bmp':
    case 'tiff':
    case 'ico':
      return <InfoIcon color="info" />;
    default:
      return <InfoIcon color="info" />;
  }
};

export default function LogoUploader({
  onLogoUpload,
  onLogoRemove,
  currentLogo,
  maxFileSize = 50, // 50MB default
  showLabels = true,
}: LogoUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const analyzeFile = useCallback(async (file: File): Promise<LogoAnalysis> => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const analysis: LogoAnalysis = {
            filename: file.name,
            file_size_kb: Math.round(file.size / 1024),
            dimensions: `${img.width}x${img.height}`,
            format: file.type.split('/')[1]?.toUpperCase() || 'UNKNOWN',
            preview_url: e.target?.result as string,
          };
          
          analysis.optimization_suggestions = getOptimizationSuggestions(analysis);
          
          resolve(analysis);
        };
        img.onerror = () => {
          // For non-image files or SVG files that can't be loaded as images
          resolve({
            filename: file.name,
            file_size_kb: Math.round(file.size / 1024),
            format: file.type.split('/')[1]?.toUpperCase() || 'UNKNOWN',
            preview_url: e.target?.result as string,
            optimization_suggestions: [],
          });
        };
        img.src = e.target?.result as string;
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const onDrop = useCallback(async (acceptedFiles: File[], rejectedFiles: any[]) => {
    setDragActive(false);
    
    if (rejectedFiles.length > 0) {
      const error = rejectedFiles[0].errors[0];
      if (error.code === 'file-too-large') {
        toast.error(`File too large. Maximum size is ${maxFileSize}MB`);
      } else if (error.code === 'file-invalid-type') {
        toast.error('Unsupported file type. Please upload PNG, JPEG, GIF, WebP, SVG, BMP, TIFF, or ICO files.');
      } else {
        toast.error('Invalid file. Please try again.');
      }
      return;
    }

    const file = acceptedFiles[0];
    if (!file) return;

    setUploading(true);
    
    try {
      const analysis = await analyzeFile(file);
      onLogoUpload(file, analysis);
      toast.success('Logo uploaded successfully!');
    } catch (error) {
      toast.error('Failed to analyze logo file');
      console.error('Logo analysis error:', error);
    } finally {
      setUploading(false);
    }
  }, [analyzeFile, onLogoUpload, maxFileSize]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: SUPPORTED_FORMATS,
    multiple: false,
    maxSize: maxFileSize * 1024 * 1024, // Convert MB to bytes
    onDragEnter: () => setDragActive(true),
    onDragLeave: () => setDragActive(false),
  });

  const handleRemoveLogo = () => {
    onLogoRemove();
    toast.success('Logo removed');
  };

  return (
    <Box>
      {showLabels && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            Brand Logo
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Upload your brand logo or symbol to incorporate your visual identity into generated images.
          </Typography>
        </Box>
      )}

      {!currentLogo ? (
        <Paper
          {...getRootProps()}
          sx={{
            p: 3,
            border: 2,
            borderStyle: 'dashed',
            borderColor: isDragActive ? 'primary.main' : 'grey.300',
            backgroundColor: isDragActive ? 'primary.50' : 'grey.50',
            cursor: uploading ? 'not-allowed' : 'pointer',
            textAlign: 'center',
            minHeight: 160,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            borderRadius: 2,
            transition: 'all 0.2s ease-in-out',
            opacity: uploading ? 0.6 : 1,
            '&:hover': {
              borderColor: uploading ? 'grey.300' : 'primary.main',
              backgroundColor: uploading ? 'grey.50' : 'primary.50',
            },
          }}
        >
          <input {...getInputProps()} disabled={uploading} />
          <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 500 }}>
            {uploading ? 'Processing logo...' : isDragActive ? 'Drop the logo here' : 'Drag & drop your logo here'}
          </Typography>
          <Typography color="textSecondary" variant="body2">
            {uploading ? 'Please wait while we analyze your logo' : 'or click to select from your computer'}
          </Typography>
          <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
            PNG, JPEG, GIF, WebP, SVG, BMP, TIFF, ICO (max {maxFileSize}MB)
          </Typography>
          {uploading && (
            <Box sx={{ width: '100%', mt: 2 }}>
              <LinearProgress />
            </Box>
          )}
        </Paper>
      ) : (
        <Paper sx={{ p: 3, border: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', gap: 3, alignItems: 'flex-start' }}>
            {/* Logo Preview */}
            <Box sx={{ flexShrink: 0 }}>
              <Paper
                sx={{
                  width: 120,
                  height: 120,
                  border: 1,
                  borderColor: 'divider',
                  borderRadius: 1,
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: 'grey.50',
                }}
              >
                {currentLogo.preview_url ? (
                  <Box
                    component="img"
                    src={currentLogo.preview_url}
                    alt="Logo preview"
                    sx={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                    }}
                  />
                ) : (
                  <CloudUploadIcon sx={{ fontSize: 40, color: 'grey.400' }} />
                )}
              </Paper>
            </Box>

            {/* Logo Details */}
            <Box sx={{ flexGrow: 1 }}>
              <Stack spacing={2}>
                <Box>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {currentLogo.filename}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1, mt: 1, flexWrap: 'wrap' }}>
                    <Chip
                      icon={getFileTypeIcon(currentLogo.format || '')}
                      label={currentLogo.format || 'Unknown'}
                      size="small"
                      variant="outlined"
                    />
                    <Chip
                      label={formatFileSize(currentLogo.file_size_kb * 1024)}
                      size="small"
                      variant="outlined"
                    />
                    {currentLogo.dimensions && (
                      <Chip
                        label={currentLogo.dimensions}
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Box>
                </Box>

                {/* Optimization Suggestions */}
                {currentLogo.optimization_suggestions && currentLogo.optimization_suggestions.length > 0 && (
                  <Alert severity="info" sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Optimization Suggestions:
                    </Typography>
                    <ul style={{ margin: 0, paddingLeft: 20 }}>
                      {currentLogo.optimization_suggestions.map((suggestion, index) => (
                        <li key={index}>
                          <Typography variant="body2">{suggestion}</Typography>
                        </li>
                      ))}
                    </ul>
                  </Alert>
                )}

                {/* Quality Assessment */}
                <Box>
                  <Typography variant="body2" color="text.secondary">
                    {currentLogo.file_size_kb <= 200 ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'success.main' }}>
                        <CheckCircleIcon sx={{ fontSize: 16 }} />
                        Optimized for web use
                      </Box>
                    ) : (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'warning.main' }}>
                        <WarningIcon sx={{ fontSize: 16 }} />
                        Large file size - consider optimization
                      </Box>
                    )}
                  </Typography>
                </Box>
              </Stack>
            </Box>

            {/* Remove Button */}
            <Box sx={{ flexShrink: 0 }}>
              <Tooltip title="Remove logo">
                <IconButton onClick={handleRemoveLogo} color="error">
                  <DeleteIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
        </Paper>
      )}
    </Box>
  );
} 