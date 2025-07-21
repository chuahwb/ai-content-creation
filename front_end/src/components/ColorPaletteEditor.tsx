'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  IconButton,
  Typography,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Tooltip,
  Stack,
  Chip,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Palette as PaletteIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { HexColorPicker } from 'react-colorful';
import toast from 'react-hot-toast';

interface ColorPaletteEditorProps {
  colors: string[];
  onChange: (colors: string[]) => void;
  maxColors?: number; // Default: 4 colors
  showLabels?: boolean;
}

interface ColorPickerDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (color: string) => void;
  initialColor?: string;
  title: string;
}

const ColorPickerDialog: React.FC<ColorPickerDialogProps> = ({
  open,
  onClose,
  onSave,
  initialColor = '#000000',
  title
}) => {
  const [color, setColor] = useState(initialColor);
  const [hexInput, setHexInput] = useState(initialColor);

  const handleSave = () => {
    // Validate hex color
    const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    if (!hexRegex.test(hexInput)) {
      toast.error('Please enter a valid hex color (e.g., #FF0000)');
      return;
    }
    onSave(hexInput);
    onClose();
  };

  const handleColorChange = (newColor: string) => {
    setColor(newColor);
    setHexInput(newColor);
  };

  const handleHexInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setHexInput(value);
    
    // Update color picker if valid hex
    const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    if (hexRegex.test(value)) {
      setColor(value);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Typography variant="h6">{title}</Typography>
          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ py: 2 }}>
          <Stack spacing={3} alignItems="center">
            <HexColorPicker color={color} onChange={handleColorChange} />
            
            <TextField
              label="Hex Color"
              value={hexInput}
              onChange={handleHexInputChange}
              placeholder="#000000"
              fullWidth
              sx={{ maxWidth: 200 }}
              inputProps={{ style: { fontFamily: 'monospace' } }}
            />
            
            <Paper
              sx={{
                width: 100,
                height: 60,
                backgroundColor: color,
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: getContrastColor(color),
                  fontWeight: 'bold',
                  textShadow: '0 0 3px rgba(0,0,0,0.5)',
                }}
              >
                Preview
              </Typography>
            </Paper>
          </Stack>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained">
          Save Color
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// Helper function to determine contrast color for text
const getContrastColor = (hexColor: string): string => {
  const hex = hexColor.replace('#', '');
  const r = parseInt(hex.substr(0, 2), 16);
  const g = parseInt(hex.substr(2, 2), 16);
  const b = parseInt(hex.substr(4, 2), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000000' : '#FFFFFF';
};

export default function ColorPaletteEditor({
  colors,
  onChange,
  maxColors = 4,
  showLabels = true,
}: ColorPaletteEditorProps) {
  const [colorPickerDialog, setColorPickerDialog] = useState<{
    open: boolean;
    mode: 'add' | 'edit';
    editIndex?: number;
    initialColor?: string;
  }>({
    open: false,
    mode: 'add',
  });

  const handleAddColor = () => {
    if (colors.length >= maxColors) {
      toast.error(`Maximum ${maxColors} colors allowed`);
      return;
    }
    setColorPickerDialog({
      open: true,
      mode: 'add',
      initialColor: '#000000',
    });
  };

  const handleEditColor = (index: number) => {
    setColorPickerDialog({
      open: true,
      mode: 'edit',
      editIndex: index,
      initialColor: colors[index],
    });
  };

  const handleRemoveColor = (index: number) => {
    const newColors = colors.filter((_, i) => i !== index);
    onChange(newColors);
    toast.success('Color removed');
  };

  const handleSaveColor = (color: string) => {
    if (colorPickerDialog.mode === 'add') {
      // Check for duplicate colors
      if (colors.includes(color)) {
        toast.error('This color is already in your palette');
        return;
      }
      const newColors = [...colors, color];
      onChange(newColors);
      toast.success('Color added to palette');
    } else if (colorPickerDialog.mode === 'edit' && colorPickerDialog.editIndex !== undefined) {
      // Check for duplicate colors (excluding the one being edited)
      const otherColors = colors.filter((_, i) => i !== colorPickerDialog.editIndex);
      if (otherColors.includes(color)) {
        toast.error('This color is already in your palette');
        return;
      }
      const newColors = [...colors];
      newColors[colorPickerDialog.editIndex] = color;
      onChange(newColors);
      toast.success('Color updated');
    }
  };

  const handleCloseColorPicker = () => {
    setColorPickerDialog({ open: false, mode: 'add' });
  };

  return (
    <Box>
      {showLabels && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
            Brand Color Palette
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Define your primary brand colors (hex codes) that will be applied to backgrounds, text, and design elements.
          </Typography>
        </Box>
      )}

      <Paper sx={{ p: 2, border: 1, borderColor: 'divider' }}>
        <Box sx={{ 
          display: 'grid',
          gridTemplateColumns: colors.length === 0 ? '1fr' : 
                              colors.length === 1 ? '1fr 1fr' :
                              colors.length === 2 ? '1fr 1fr 1fr' :
                              colors.length === 3 ? '1fr 1fr 1fr 1fr' :
                              '1fr 1fr 1fr 1fr', // 4 colors
          gap: 1.5, 
          mb: 2
        }}>
          {colors.map((color, index) => (
            <Tooltip key={index} title={`${color} - Click to edit`} arrow>
              <Box sx={{ position: 'relative' }}>
                <Paper
                  sx={{
                    width: '100%',
                    height: 70,
                    backgroundColor: color,
                    border: 1,
                    borderColor: 'divider',
                    borderRadius: 1.5,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    '&:hover': {
                      transform: 'scale(1.02)',
                      boxShadow: 3,
                    },
                  }}
                  onClick={() => handleEditColor(index)}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: getContrastColor(color),
                      fontWeight: 600,
                      fontSize: '0.7rem',
                      textAlign: 'center',
                      backgroundColor: 'rgba(0,0,0,0.1)',
                      backdropFilter: 'blur(4px)',
                      px: 1,
                      py: 0.25,
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      letterSpacing: '0.5px',
                    }}
                  >
                    {color.toUpperCase()}
                  </Typography>
                </Paper>
                <IconButton
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemoveColor(index);
                  }}
                  sx={{
                    position: 'absolute',
                    top: -6,
                    right: -6,
                    backgroundColor: 'error.main',
                    color: 'white',
                    width: 22,
                    height: 22,
                    '&:hover': {
                      backgroundColor: 'error.dark',
                    },
                  }}
                >
                  <DeleteIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Box>
            </Tooltip>
          ))}

          {colors.length < maxColors && (
            <Tooltip title="Add new brand color" arrow>
              <Box
                sx={{
                  width: '100%',
                  height: 70,
                  border: 2,
                  borderStyle: 'dashed',
                  borderColor: 'primary.main',
                  borderRadius: colors.length === 0 ? 2 : 1.5,
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: 'primary.50',
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    backgroundColor: 'primary.100',
                    transform: colors.length === 0 ? 'translateY(-2px)' : 'scale(1.02)',
                    borderColor: 'primary.dark',
                    boxShadow: 2,
                  },
                }}
                onClick={handleAddColor}
              >
                <AddIcon sx={{ 
                  color: 'primary.main', 
                  fontSize: colors.length === 0 ? 32 : 24,
                  mb: colors.length === 0 ? 0.5 : 0
                }} />
                {colors.length === 0 && (
                  <Typography variant="caption" sx={{ 
                    color: 'primary.main', 
                    fontWeight: 600,
                    textAlign: 'center'
                  }}>
                    Add First Color
                  </Typography>
                )}
              </Box>
            </Tooltip>
          )}
        </Box>

        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            {colors.length} of {maxColors} brand colors
            {colors.length === maxColors && ' (maximum reached)'}
          </Typography>
        </Box>
      </Paper>

      <ColorPickerDialog
        open={colorPickerDialog.open}
        onClose={handleCloseColorPicker}
        onSave={handleSaveColor}
        initialColor={colorPickerDialog.initialColor}
        title={colorPickerDialog.mode === 'add' ? 'Add Color' : 'Edit Color'}
      />
    </Box>
  );
} 