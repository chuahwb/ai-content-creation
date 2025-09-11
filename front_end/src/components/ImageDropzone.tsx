'use client';

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  Tooltip,
  IconButton,
  useTheme,
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { TOOLTIP_CONFIG, INFO_ICON_STYLE } from '@/lib/ui-tooltips';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import EditModeSelector from './EditModeSelector';

interface ImageDropzoneProps {
  uploadedFile: File | null;
  previewUrl: string | null;
  onFileSelect: (file: File) => void;
  onFileRemove: () => void;
  disabled?: boolean;
  title?: string;
  subtitle?: string;
  hasBrief?: boolean; // To show alternative completion state
  // Edit mode integration
  showEditMode?: boolean;
  editMode?: 'defaultEdit' | 'instructedEdit';
  onEditModeChange?: (mode: 'defaultEdit' | 'instructedEdit') => void;
  editInstruction?: string;
  onEditInstructionChange?: (instruction: string) => void;
}

export default function ImageDropzone({
  uploadedFile,
  previewUrl,
  onFileSelect,
  onFileRemove,
  disabled = false,
  title = "Reference Image",
  subtitle = "Upload an image to edit or use as reference",
  hasBrief = false,
  showEditMode = false,
  editMode = 'defaultEdit',
  onEditModeChange,
  editInstruction = '',
  onEditInstructionChange
}: ImageDropzoneProps) {
  const theme = useTheme();

  const onDrop = (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      onFileSelect(file);
    }
  };

  const onDropRejected = (rejectedFiles: any[]) => {
    if (rejectedFiles.length > 0) {
      const rejection = rejectedFiles[0];
      const file = rejection.file;
      const errors = rejection.errors || [];
      
      if (errors.some((e: any) => e.code === 'file-too-large')) {
        const fileSizeMB = file?.size ? (file.size / (1024 * 1024)).toFixed(1) : 'unknown';
        toast.error(
          `File "${file?.name}" is too large (${fileSizeMB}MB). Maximum size allowed is 50MB.`,
          { duration: 5000 }
        );
      } else if (errors.some((e: any) => e.code === 'file-invalid-type')) {
        toast.error(
          `File "${file?.name}" has an unsupported format (${file?.type}). Please use JPG, PNG, GIF, WebP, BMP, or TIFF files.`,
          { duration: 5000 }
        );
      } else {
        toast.error(
          `Failed to upload "${file?.name}". Please try again or check the file format and size.`,
          { duration: 4000 }
        );
      }
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.gif', '.webp', '.bmp', '.tiff']
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: false,
    disabled
  });

  return (
    <Box sx={{ mb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {title}
        </Typography>
        <Chip 
          label={uploadedFile ? "Provided ✓" : hasBrief ? "Optional (Brief provided)" : "Optional"} 
          size="small" 
          color={uploadedFile ? "success" : hasBrief ? "info" : "default"}
          variant="outlined" 
          sx={{ height: 20, fontSize: '0.7rem' }}
        />
        <Tooltip title="Upload a reference image to edit, adapt, or use as inspiration for your visual content" {...TOOLTIP_CONFIG}>
          <IconButton size="small" sx={{ p: 0.5 }}>
            <InfoIcon sx={INFO_ICON_STYLE} />
          </IconButton>
        </Tooltip>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {subtitle}
      </Typography>
    
      {!uploadedFile ? (
        <Paper
          {...getRootProps()}
          sx={{
            p: 3,
            border: 2,
            borderStyle: 'dashed',
            borderColor: isDragActive ? 'primary.main' : 'grey.300',
            backgroundColor: isDragActive ? 'primary.50' : 'grey.50',
            cursor: disabled ? 'not-allowed' : 'pointer',
            textAlign: 'center',
            minHeight: 160,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            borderRadius: 2,
            transition: 'all 0.2s ease-in-out',
            opacity: disabled ? 0.5 : 1,
            '&:hover': disabled ? {} : {
              borderColor: 'primary.main',
              backgroundColor: 'primary.50',
            },
          }}
        >
          <input {...getInputProps()} />
          <CloudUploadIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 500 }}>
            {isDragActive ? 'Drop the image here' : 'Drag & drop an image here'}
          </Typography>
          <Typography color="textSecondary" variant="body2">
            or click to select from your computer
          </Typography>
          <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
            JPG, PNG, GIF, WebP, BMP, TIFF • Maximum 50MB
          </Typography>
        </Paper>
      ) : (
        <Paper sx={{ p: 3, border: 1, borderColor: 'divider', borderRadius: 2 }}>
          {/* Image Preview Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: showEditMode ? 3 : 0 }}>
            {previewUrl && (
              <Box
                component="img"
                src={previewUrl}
                alt="Uploaded reference"
                sx={{
                  width: 80,
                  height: 80,
                  objectFit: 'cover',
                  borderRadius: 1,
                  border: 1,
                  borderColor: 'divider',
                }}
              />
            )}
            
            <Box sx={{ flexGrow: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {uploadedFile.name}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                {(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB
              </Typography>
            </Box>
            
            <Button 
              variant="outlined" 
              color="error" 
              onClick={onFileRemove} 
              size="small"
              startIcon={<DeleteIcon />}
              disabled={disabled}
            >
              Remove
            </Button>
          </Box>
          
          {/* Integrated Edit Mode Selector */}
          {showEditMode && onEditModeChange && onEditInstructionChange && (
            <Box sx={{ 
              pt: 3, 
              borderTop: 1, 
              borderColor: 'divider'
            }}>
              <EditModeSelector
                mode={editMode}
                onModeChange={onEditModeChange}
                editInstruction={editInstruction}
                onEditInstructionChange={onEditInstructionChange}
                disabled={disabled}
                visible={true}
                embedded={true}
              />
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}
