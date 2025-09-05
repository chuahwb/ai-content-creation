'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Alert,
  Divider,
  Card,
  CardContent,
  Fade,
  Collapse,
  Tabs,
  Tab,
  Switch,
  FormControlLabel,
  LinearProgress,
  Backdrop,
  CircularProgress,
  ButtonGroup,
  Checkbox,
  useTheme,
  useMediaQuery,
  Grow,
  Popover,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Palette as PaletteIcon,
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  AutoFixHigh as AutoFixHighIcon,
  Lightbulb as LightbulbIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Tune as TuneIcon,
  ColorLens as ColorLensIcon,
  Psychology as PsychologyIcon,
  ViewModule as ViewModuleIcon,
  ViewStream as ViewStreamIcon,
  Lock as LockIcon,
  LockOpen as LockOpenIcon,
  Restore as RestoreIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { HexColorPicker } from 'react-colorful';
import toast from 'react-hot-toast';
import { BrandColor } from '../types/api';
import EnhancedColorBar from './EnhancedColorBar';
import { apiCallWithRetry } from '../lib/api';
import { ProductFocusedPreview } from './design_previews/ProductFocusedPreview';
import { PromotionalAnnouncementPreview } from './design_previews/PromotionalAnnouncementPreview';
import { LifestyleAtmospherePreview } from './design_previews/LifestyleAtmospherePreview';

interface EnhancedColorPaletteEditorProps {
  colors: BrandColor[];
  onChange: (colors: BrandColor[]) => void;
  maxColors?: number;
  showLabels?: boolean;
  logoFile?: File | null; // For logo color extraction
}

interface ColorPickerDialogProps {
  open: boolean;
  onClose: () => void;
  onSave: (color: BrandColor) => void;
  initialColor?: BrandColor;
  title: string;
  availableRoles: string[];
}

// Enhanced color roles with intelligent ratio system
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

// Intelligent ratio calculation system
const calculateIntelligentRatios = (colors: BrandColor[]): BrandColor[] => {
  const coreColors = colors.filter(c => !c.role.includes('neutral'));
  const neutralColors = colors.filter(c => c.role.includes('neutral'));
  
  if (coreColors.length === 0) {
    return colors; // No core colors to calculate
  }

  // Group colors by role
  const colorsByRole = coreColors.reduce((acc, color, index) => {
    if (!acc[color.role]) {
      acc[color.role] = [];
    }
    acc[color.role].push({ ...color, originalIndex: colors.indexOf(color) });
    return acc;
  }, {} as Record<string, (BrandColor & { originalIndex: number })[]>);

  // Calculate ratios based on 60-30-10 rule and actual colors present
  let updatedColors = [...colors];
  
  // Single color scenario - gets 100%
  if (coreColors.length === 1) {
    const singleColorIndex = colors.indexOf(coreColors[0]);
    updatedColors[singleColorIndex] = {
      ...coreColors[0],
      ratio: 1.0,
      isCustomRatio: false
    };
    return updatedColors;
  }

  // Multiple colors - apply intelligent distribution
  const availableRoles = Object.keys(colorsByRole);
  const totalBaseRatio = availableRoles.reduce((sum, role) => {
    return sum + (COLOR_ROLES[role as keyof typeof COLOR_ROLES]?.baseRatio || 0);
  }, 0);

  // Distribute ratios intelligently
  availableRoles.forEach(role => {
    const roleColors = colorsByRole[role];
    const roleConfig = COLOR_ROLES[role as keyof typeof COLOR_ROLES];
    
    if (!roleConfig || roleColors.length === 0) return;

    let roleRatio = roleConfig.baseRatio;
    
    // Adjust for missing roles (redistribute their ratios)
    if (totalBaseRatio < 1) {
      const missingRatio = 1 - totalBaseRatio;
      const redistributionFactor = missingRatio / availableRoles.length;
      roleRatio += redistributionFactor;
    }

    // Distribute role ratio among colors of the same role
    const individualRatio = roleRatio / roleColors.length;
    
    roleColors.forEach(colorWithIndex => {
      const { originalIndex } = colorWithIndex;
      if (originalIndex >= 0 && originalIndex < updatedColors.length) {
        updatedColors[originalIndex] = {
          ...updatedColors[originalIndex],
          ratio: individualRatio,
          isCustomRatio: false
        };
      }
    });
  });

  return updatedColors;
};

// Smart normalization that preserves user intent while maintaining fluidity
const smartNormalizeRatios = (colors: BrandColor[], activeColorIndex?: number): BrandColor[] => {
  const coreColors = colors.filter(c => !c.role.includes('neutral'));
  const neutralColors = colors.filter(c => c.role.includes('neutral'));
  
  if (coreColors.length === 0) return colors;

  const totalCoreRatio = coreColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
  
  // If within acceptable range (0.95 - 1.05), no normalization needed
  if (totalCoreRatio >= 0.95 && totalCoreRatio <= 1.05) {
    return colors;
  }

  let normalizedColors = [...colors];
  
  // Get locked and unlocked colors
  const lockedColors = coreColors.filter(c => c.isLocked);
  const unlockedColors = coreColors.filter(c => !c.isLocked);
  
  const lockedTotal = lockedColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
  
  if (lockedTotal >= 1) {
    // Locked colors exceed 100%, proportionally reduce all locked colors
    const reductionFactor = 0.98 / lockedTotal; // Leave 2% buffer
    lockedColors.forEach(lockedColor => {
      const colorIndex = colors.indexOf(lockedColor);
      if (colorIndex >= 0) {
        normalizedColors[colorIndex] = {
          ...lockedColor,
          ratio: (lockedColor.ratio || 0) * reductionFactor
        };
      }
    });
    return normalizedColors;
  }

  const availableSpace = 1 - lockedTotal;
  
  if (unlockedColors.length === 0) return normalizedColors;

  // Smart redistribution based on priority and user intent
  if (activeColorIndex !== undefined && activeColorIndex >= 0) {
    // User is actively adjusting a color - preserve their intent
    const activeColor = colors[activeColorIndex];
    if (activeColor && !activeColor.isLocked && !activeColor.role.includes('neutral')) {
      const otherUnlocked = unlockedColors.filter(c => c !== activeColor);
      const otherTotal = otherUnlocked.reduce((sum, c) => sum + (c.ratio || 0), 0);
      const remainingSpace = availableSpace - (activeColor.ratio || 0);
      
      if (otherTotal > 0 && remainingSpace > 0) {
        const redistributionFactor = remainingSpace / otherTotal;
        otherUnlocked.forEach(color => {
          const colorIndex = colors.indexOf(color);
          if (colorIndex >= 0) {
            normalizedColors[colorIndex] = {
              ...color,
              ratio: (color.ratio || 0) * redistributionFactor
            };
          }
        });
      }
    }
  } else {
    // General normalization - maintain proportional relationships
    const unlockedTotal = unlockedColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
    if (unlockedTotal > 0) {
      const normalizationFactor = availableSpace / unlockedTotal;
      unlockedColors.forEach(color => {
        const colorIndex = colors.indexOf(color);
        if (colorIndex >= 0) {
          normalizedColors[colorIndex] = {
            ...color,
            ratio: (color.ratio || 0) * normalizationFactor
          };
        }
      });
    }
  }

  return normalizedColors;
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

// Helper function to calculate WCAG contrast ratio
const getContrastRatio = (color1: string, color2: string): number => {
  const getLuminance = (hex: string): number => {
    const rgb = hex.replace('#', '').match(/.{2}/g)?.map(x => parseInt(x, 16) / 255) || [0, 0, 0];
    const [r, g, b] = rgb.map(c => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };

  const lum1 = getLuminance(color1);
  const lum2 = getLuminance(color2);
  const brightest = Math.max(lum1, lum2);
  const darkest = Math.min(lum1, lum2);
  return (brightest + 0.05) / (darkest + 0.05);
};

// Helper functions for color conversion
const hexToRgb = (hex: string): { r: number; g: number; b: number } => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 0, g: 0, b: 0 };
};

const rgbToHex = (r: number, g: number, b: number): string => {
  return "#" + [r, g, b].map(x => {
    const hex = Math.round(x).toString(16);
    return hex.length === 1 ? "0" + hex : hex;
  }).join("");
};

const hexToHsl = (hex: string): { h: number; s: number; l: number } => {
  const { r, g, b } = hexToRgb(hex);
  const rNorm = r / 255;
  const gNorm = g / 255;
  const bNorm = b / 255;

  const max = Math.max(rNorm, gNorm, bNorm);
  const min = Math.min(rNorm, gNorm, bNorm);
  const diff = max - min;

  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (diff !== 0) {
    s = l > 0.5 ? diff / (2 - max - min) : diff / (max + min);
    
    switch (max) {
      case rNorm: h = (gNorm - bNorm) / diff + (gNorm < bNorm ? 6 : 0); break;
      case gNorm: h = (bNorm - rNorm) / diff + 2; break;
      case bNorm: h = (rNorm - gNorm) / diff + 4; break;
    }
    h /= 6;
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100)
  };
};

const hslToHex = (h: number, s: number, l: number): string => {
  const hNorm = h / 360;
  const sNorm = s / 100;
  const lNorm = l / 100;

  const c = (1 - Math.abs(2 * lNorm - 1)) * sNorm;
  const x = c * (1 - Math.abs((hNorm * 6) % 2 - 1));
  const m = lNorm - c / 2;

  let r = 0, g = 0, b = 0;

  if (hNorm < 1/6) { r = c; g = x; b = 0; }
  else if (hNorm < 2/6) { r = x; g = c; b = 0; }
  else if (hNorm < 3/6) { r = 0; g = c; b = x; }
  else if (hNorm < 4/6) { r = 0; g = x; b = c; }
  else if (hNorm < 5/6) { r = x; g = 0; b = c; }
  else { r = c; g = 0; b = x; }

  return rgbToHex((r + m) * 255, (g + m) * 255, (b + m) * 255);
};

// Auto-suggest color names based on hue
const suggestColorLabel = (hex: string): string => {
  const { h } = hexToHsl(hex);
  
  if (h >= 0 && h < 15) return 'Red';
  if (h >= 15 && h < 45) return 'Orange';
  if (h >= 45 && h < 75) return 'Yellow';
  if (h >= 75 && h < 105) return 'Lime';
  if (h >= 105 && h < 135) return 'Green';
  if (h >= 135 && h < 165) return 'Teal';
  if (h >= 165 && h < 195) return 'Cyan';
  if (h >= 195 && h < 225) return 'Light Blue';
  if (h >= 225 && h < 255) return 'Blue';
  if (h >= 255 && h < 285) return 'Purple';
  if (h >= 285 && h < 315) return 'Magenta';
  if (h >= 315 && h < 345) return 'Pink';
  if (h >= 345 && h <= 360) return 'Red';
  
  return 'Color';
};

// Helper function to check if two colors are visually similar
const areColorsSimilar = (hex1: string, hex2: string, threshold = 30): boolean => {
  const rgb1 = hexToRgb(hex1);
  const rgb2 = hexToRgb(hex2);
  
  // Calculate Euclidean distance in RGB space
  const distance = Math.sqrt(
    Math.pow(rgb2.r - rgb1.r, 2) +
    Math.pow(rgb2.g - rgb1.g, 2) +
    Math.pow(rgb2.b - rgb1.b, 2)
  );
  
  return distance < threshold;
};

// Generate automatic neutral colors based on primary color with enhanced contrast checks
const generateNeutrals = (primaryColor?: BrandColor, allColors: BrandColor[] = []): BrandColor[] => {
  // Fallback to default neutrals if no primary color
  if (!primaryColor) {
    return [
      { hex: '#F9F9F9', role: 'neutral_light', label: 'Auto Light', ratio: 0.1, isAuto: true },
      { hex: '#1A1A1A', role: 'neutral_dark', label: 'Auto Dark', ratio: 0.1, isAuto: true },
    ];
  }

  // Use the new HSL conversion helper
  const { h } = hexToHsl(primaryColor.hex);

  // Generate neutral colors with low saturation based on primary hue
  let lightNeutralHex = hslToHex(h, 8, 96);
  let darkNeutralHex = hslToHex(h, 15, 12);

  // Ensure minimum contrast with primary color (3:1 ratio)
  const ensureContrast = (neutralHex: string, targetContrast: number = 3.0): string => {
    let currentContrast = getContrastRatio(primaryColor.hex, neutralHex);
    let { h: nH, s: nS, l: nL } = hexToHsl(neutralHex);
    
    if (currentContrast < targetContrast) {
      // Adjust lightness to improve contrast
      const isLight = nL > 50;
      while (currentContrast < targetContrast && ((isLight && nL > 5) || (!isLight && nL < 95))) {
        nL = isLight ? nL - 2 : nL + 2;
        const adjustedHex = hslToHex(nH, nS, nL);
        currentContrast = getContrastRatio(primaryColor.hex, adjustedHex);
        if (currentContrast >= targetContrast) {
          return adjustedHex;
        }
      }
    }
    
    return neutralHex;
  };

  lightNeutralHex = ensureContrast(lightNeutralHex);
  darkNeutralHex = ensureContrast(darkNeutralHex);

  // Check contrast with other colors in palette
  const hasGoodContrastWithOthers = (neutralHex: string): boolean => {
    return allColors.every(color => {
      if (color.role === 'neutral_light' || color.role === 'neutral_dark') return true;
      return getContrastRatio(color.hex, neutralHex) >= 2.5; // Minimum for non-text elements
    });
  };

  // Adjust if poor contrast with other colors
  if (!hasGoodContrastWithOthers(lightNeutralHex)) {
    lightNeutralHex = hslToHex(h, 5, 98); // Even lighter
  }
  if (!hasGoodContrastWithOthers(darkNeutralHex)) {
    darkNeutralHex = hslToHex(h, 18, 8); // Even darker
  }

  return [
    { 
      hex: lightNeutralHex, 
      role: 'neutral_light', 
      label: 'Auto Light',
      ratio: 0.1,
      isAuto: true
    },
    { 
      hex: darkNeutralHex, 
      role: 'neutral_dark', 
      label: 'Auto Dark',
      ratio: 0.1,
      isAuto: true
    },
  ];
};

const ColorPickerDialog: React.FC<ColorPickerDialogProps> = ({
  open,
  onClose,
  onSave,
  initialColor,
  title,
  availableRoles
}) => {
  const theme = useTheme();
  const [color, setColor] = useState(initialColor?.hex || '#000000');
  const [hexInput, setHexInput] = useState(initialColor?.hex || '#000000');
  const [role, setRole] = useState(initialColor?.role || 'primary');
  const [label, setLabel] = useState(initialColor?.label || '');
  const [ratio, setRatio] = useState(initialColor?.ratio || undefined);
  const [inputMode, setInputMode] = useState<'hex' | 'rgb' | 'hsl'>('hex');
  const [rgbInput, setRgbInput] = useState({ r: 0, g: 0, b: 0 });
  const [hslInput, setHslInput] = useState({ h: 0, s: 0, l: 0 });

  useEffect(() => {
    if (initialColor) {
      const hex = initialColor.hex;
      setColor(hex);
      setHexInput(hex);
      setRole(initialColor.role);
      setLabel(initialColor.label || '');
      setRatio(initialColor.ratio || undefined);
      
      // Initialize RGB and HSL values
      const rgb = hexToRgb(hex);
      const hsl = hexToHsl(hex);
      setRgbInput(rgb);
      setHslInput(hsl);
    }
  }, [initialColor]);

  const handleSave = () => {
    // Validate hex color
    const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    if (!hexRegex.test(hexInput)) {
      toast.error('Please enter a valid hex color (e.g., #FF0000)');
      return;
    }

    const brandColor: BrandColor = {
      hex: hexInput,
      role,
      label: label || undefined,
      ratio: ratio || undefined,
    };

    onSave(brandColor);
    onClose();
  };

  const handleColorChange = (newColor: string) => {
    setColor(newColor);
    setHexInput(newColor);
    
    // Update RGB and HSL inputs
    const rgb = hexToRgb(newColor);
    const hsl = hexToHsl(newColor);
    setRgbInput(rgb);
    setHslInput(hsl);
    
    // Auto-suggest label if empty
    if (!label) {
      setLabel(suggestColorLabel(newColor));
    }
  };

  const handleHexInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setHexInput(value);
    
    // Update color picker if valid hex
    const hexRegex = /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/;
    if (hexRegex.test(value)) {
      setColor(value);
      const rgb = hexToRgb(value);
      const hsl = hexToHsl(value);
      setRgbInput(rgb);
      setHslInput(hsl);
      
      // Auto-suggest label if empty
      if (!label) {
        setLabel(suggestColorLabel(value));
      }
    }
  };

  const handleRgbInputChange = (channel: 'r' | 'g' | 'b', value: string) => {
    const numValue = Math.max(0, Math.min(255, parseInt(value) || 0));
    const newRgb = { ...rgbInput, [channel]: numValue };
    setRgbInput(newRgb);
    
    const newHex = rgbToHex(newRgb.r, newRgb.g, newRgb.b);
    setColor(newHex);
    setHexInput(newHex);
    
    const hsl = hexToHsl(newHex);
    setHslInput(hsl);
  };

  const handleHslInputChange = (channel: 'h' | 's' | 'l', value: string) => {
    const numValue = channel === 'h' 
      ? Math.max(0, Math.min(360, parseInt(value) || 0))
      : Math.max(0, Math.min(100, parseInt(value) || 0));
    const newHsl = { ...hslInput, [channel]: numValue };
    setHslInput(newHsl);
    
    const newHex = hslToHex(newHsl.h, newHsl.s, newHsl.l);
    setColor(newHex);
    setHexInput(newHex);
    
    const rgb = hexToRgb(newHex);
    setRgbInput(rgb);
  };

  return (
    <Dialog 
      open={open} 
      onClose={onClose} 
      maxWidth="xs" 
      fullWidth
      TransitionComponent={Grow}
      TransitionProps={{
        timeout: 400
      }}
      PaperProps={{
        sx: {
          borderRadius: 2,
          background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
        }
      }}
    >
      <DialogTitle sx={{ pb: 1, px: 2, py: 1.5 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={1}>
            <ColorLensIcon color="primary" sx={{ fontSize: 20 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>{title}</Typography>
          </Box>
          <IconButton 
            onClick={onClose}
            size="small"
            sx={{ 
              '&:hover': { 
                backgroundColor: 'action.hover',
                transform: 'rotate(90deg)',
                transition: 'transform 0.2s ease'
              } 
            }}
          >
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ px: 2, py: 1 }}>
        <Stack spacing={2} alignItems="center">
            {/* Compact Color Picker */}
            <Box
              sx={{
                p: 1.5,
                borderRadius: 2,
                background: 'linear-gradient(145deg, #f8f8f8, #ffffff)',
                border: `1px solid ${theme.palette.divider}`,
              }}
            >
              <HexColorPicker color={color} onChange={handleColorChange} style={{ width: 200, height: 150 }} />
            </Box>
            
            {/* Compact Preview and Controls */}
            <Card
              sx={{
                width: '100%',
                borderRadius: 1.5,
                background: `linear-gradient(135deg, ${color}10 0%, ${color}05 100%)`,
                border: `1px solid ${color}30`,
              }}
            >
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Box
                  sx={{
                    width: '100%',
                    height: 40,
                    backgroundColor: color,
                    borderRadius: 1.5,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mb: 1.5,
                    boxShadow: `0 2px 8px ${color}40`,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: getContrastColor(color),
                      fontWeight: 700,
                      fontSize: '0.7rem',
                      textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                    }}
                  >
                    {hexInput.toUpperCase()}
                  </Typography>
                </Box>
                
                <Stack spacing={1.5}>
                  {/* Color Input Tabs */}
                  <Box>
                    <Tabs 
                      value={inputMode} 
                      onChange={(_, newValue) => setInputMode(newValue)}
                      variant="fullWidth"
                      sx={{ 
                        minHeight: 32,
                        '& .MuiTab-root': { 
                          minHeight: 32, 
                          fontSize: '0.75rem',
                          textTransform: 'none',
                          fontWeight: 600
                        }
                      }}
                    >
                      <Tab label="Hex" value="hex" />
                      <Tab label="RGB" value="rgb" />
                      <Tab label="HSL" value="hsl" />
                    </Tabs>
                    
                    <Box sx={{ pt: 1.5 }}>
                      {inputMode === 'hex' && (
                        <TextField
                          label="Hex Color"
                          value={hexInput}
                          onChange={handleHexInputChange}
                          placeholder="#000000"
                          size="small"
                          fullWidth
                          inputProps={{ 
                            style: { 
                              fontFamily: 'monospace', 
                              fontSize: '0.8rem',
                              fontWeight: 600 
                            } 
                          }}
                          sx={{
                            '& .MuiOutlinedInput-root': {
                              borderRadius: 1.5,
                            }
                          }}
                        />
                      )}
                      
                      {inputMode === 'rgb' && (
                        <Stack direction="row" spacing={1}>
                          <TextField
                            label="R"
                            value={rgbInput.r}
                            onChange={(e) => handleRgbInputChange('r', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 255 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                          <TextField
                            label="G"
                            value={rgbInput.g}
                            onChange={(e) => handleRgbInputChange('g', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 255 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                          <TextField
                            label="B"
                            value={rgbInput.b}
                            onChange={(e) => handleRgbInputChange('b', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 255 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        </Stack>
                      )}
                      
                      {inputMode === 'hsl' && (
                        <Stack direction="row" spacing={1}>
                          <TextField
                            label="H"
                            value={hslInput.h}
                            onChange={(e) => handleHslInputChange('h', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 360 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                          <TextField
                            label="S%"
                            value={hslInput.s}
                            onChange={(e) => handleHslInputChange('s', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 100 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                          <TextField
                            label="L%"
                            value={hslInput.l}
                            onChange={(e) => handleHslInputChange('l', e.target.value)}
                            type="number"
                            inputProps={{ min: 0, max: 100 }}
                            size="small"
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1.5 } }}
                          />
                        </Stack>
                      )}
                    </Box>
                  </Box>
                  
                  <FormControl fullWidth size="small">
                    <InputLabel>Role</InputLabel>
                    <Select
                      value={role}
                      label="Role"
                      onChange={(e) => setRole(e.target.value)}
                      sx={{ borderRadius: 1.5 }}
                    >
                      {availableRoles.map((roleKey) => (
                        <MenuItem key={roleKey} value={roleKey}>
                          <Tooltip title={COLOR_ROLES[roleKey as keyof typeof COLOR_ROLES]?.tooltip || ''} placement="right">
                            <Box display="flex" alignItems="center" gap={1}>
                              <Box
                                sx={{
                                  width: 10,
                                  height: 10,
                                  borderRadius: '50%',
                                  backgroundColor: roleKey === 'primary' ? '#1976d2' : 
                                                  roleKey === 'secondary' ? '#9c27b0' :
                                                  roleKey === 'accent' ? '#ff9800' :
                                                  roleKey === 'neutral_light' ? '#f5f5f5' : '#424242',
                                  border: roleKey === 'neutral_light' ? '1px solid #ddd' : 'none'
                                }}
                              />
                              <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                                {COLOR_ROLES[roleKey as keyof typeof COLOR_ROLES]?.label || roleKey}
                              </Typography>
                            </Box>
                          </Tooltip>
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  <TextField
                    label="Label (Optional)"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder={`e.g., ${suggestColorLabel(color)}`}
                    size="small"
                    fullWidth
                    sx={{
                      '& .MuiOutlinedInput-root': {
                        borderRadius: 1.5,
                      }
                    }}
                  />
                  
                  {/* Basic contrast preview */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pt: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      Contrast preview:
                    </Typography>
                    <Box
                      sx={{
                        px: 1,
                        py: 0.5,
                        borderRadius: 0.5,
                        backgroundColor: '#ffffff',
                        color: color,
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        border: '1px solid #ddd'
                      }}
                    >
                      Sample
                    </Box>
                    <Box
                      sx={{
                        px: 1,
                        py: 0.5,
                        borderRadius: 0.5,
                        backgroundColor: '#000000',
                        color: color,
                        fontSize: '0.7rem',
                        fontWeight: 600
                      }}
                    >
                      Sample
                    </Box>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 2, pb: 2, pt: 1, gap: 1 }}>
        <Button 
          onClick={onClose}
          size="small"
          sx={{ 
            borderRadius: 1.5,
            px: 2,
            textTransform: 'none',
            fontWeight: 600,
            fontSize: '0.8rem'
          }}
        >
          Cancel
        </Button>
        <Button 
          onClick={handleSave} 
          variant="contained"
          size="small"
          sx={{ 
            borderRadius: 1.5,
            px: 2,
            textTransform: 'none',
            fontWeight: 600,
            fontSize: '0.8rem',
            background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
            '&:hover': {
              background: `linear-gradient(135deg, ${theme.palette.primary.dark} 0%, ${theme.palette.primary.main} 100%)`,
            }
          }}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default function EnhancedColorPaletteEditor({
  colors,
  onChange,
  maxColors = 7,
  showLabels = true,
  logoFile
}: EnhancedColorPaletteEditorProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));
  const [colorPickerDialog, setColorPickerDialog] = useState<{
    open: boolean;
    mode: 'add' | 'edit';
    editIndex?: number;
    initialColor?: BrandColor;
  }>({
    open: false,
    mode: 'add',
  });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [autoNeutralsEnabled, setAutoNeutralsEnabled] = useState(true);
  const [showPaletteSizeWarning, setShowPaletteSizeWarning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState('');
  const [suggestingForRole, setSuggestingForRole] = useState<string | null>(null);
  const [primarySelection, setPrimarySelection] = useState<{
    anchorEl: HTMLElement | null;
    targetRole: string;
  }>({ anchorEl: null, targetRole: '' });
  const [suggestionMode, setSuggestionMode] = useState<{
    mode: 'add' | 'replace';
    targetIndex?: number;
  }>({ mode: 'add' });
  const [previewModal, setPreviewModal] = useState<{
    open: boolean;
    title: string;
    colors: BrandColor[];
    type: 'logo' | 'harmony';
  }>({
    open: false,
    title: '',
    colors: [],
    type: 'logo'
  });
  const [selectedColors, setSelectedColors] = useState<boolean[]>([]);
  const [previewMode, setPreviewMode] = useState<'bar' | 'circles'>('bar');
  const [suggestions, setSuggestions] = useState<{
    anchorEl: HTMLElement | null;
    role: string;
    options: BrandColor[];
    offset: number;
  }>({ anchorEl: null, role: '', options: [], offset: 0 });
  const [expandedTooltips, setExpandedTooltips] = useState<Set<number>>(new Set());
  const [loadingMoreSuggestions, setLoadingMoreSuggestions] = useState(false);

  // Clean up debug logs when popover closes
  useEffect(() => {
    if (!suggestions.anchorEl) {
      setLoadingMoreSuggestions(false);
    }
  }, [suggestions.anchorEl]);

  // Get primary color for neutral generation
  const primaryColor = colors.find(c => c.role === 'primary');

  // Auto-apply intelligent ratios when colors are added/removed in auto mode
  useEffect(() => {
    const coreColors = colors.filter(c => !c.role.includes('neutral'));
    const hasCustomRatios = coreColors.some(c => c.isCustomRatio);
    
    // Only auto-apply if in auto mode and we have core colors without proper ratios
    if (!hasCustomRatios && coreColors.length > 0) {
      const needsRatioUpdate = coreColors.some(c => !c.ratio || c.ratio === 0);
      
      if (needsRatioUpdate) {
        const intelligentColors = calculateIntelligentRatios(colors);
        
        // Only update if ratios actually changed
        const ratiosChanged = intelligentColors.some((newColor, index) => {
          const oldColor = colors[index];
          return Math.abs((newColor.ratio || 0) - (oldColor?.ratio || 0)) > 0.01;
        });
        
        if (ratiosChanged) {
          onChange(intelligentColors);
        }
      }
    }
  }, [colors.length, colors.map(c => c.role).join(',')]); // Depend on color count and roles

  // Auto-generate neutrals if enabled and not manually set
  useEffect(() => {
    if (autoNeutralsEnabled && colors.length > 0) {
      const hasManualNeutrals = colors.some(c => 
        (c.role === 'neutral_light' || c.role === 'neutral_dark') && 
        !c.isAuto
      );
      
      if (!hasManualNeutrals) {
        const nonNeutralColors = colors.filter(c => 
          c.role !== 'neutral_light' && c.role !== 'neutral_dark'
        );
        const autoNeutrals = generateNeutrals(primaryColor, nonNeutralColors);
        
        // If auto-generated, tie their ratios to primary color
        if (primaryColor && primaryColor.ratio) {
          autoNeutrals.forEach(neutral => {
            neutral.ratio = primaryColor.ratio! * 0.2; // 20% of primary ratio
          });
        }
        
        const existingNonNeutrals = colors.filter(c => 
          c.role !== 'neutral_light' && c.role !== 'neutral_dark'
        );
        
        // Prevent over-adding auto-neutrals - limit to maxColors + 2 total
        let filteredAutoNeutrals = autoNeutrals;
        if (existingNonNeutrals.length + autoNeutrals.length > maxColors + 2) {
          const availableSlots = maxColors + 2 - existingNonNeutrals.length;
          filteredAutoNeutrals = autoNeutrals.slice(0, Math.max(0, availableSlots));
          if (filteredAutoNeutrals.length < autoNeutrals.length) {
            toast('Limited auto-neutrals due to palette size', {
              icon: 'ℹ️',
              duration: 2000
            });
          }
        }
        
        const existingAutoNeutrals = colors.filter(c => 
          (c.role === 'neutral_light' || c.role === 'neutral_dark') && 
          c.isAuto
        );

        // Only update if auto-neutrals have changed
        const needsUpdate = existingAutoNeutrals.length !== filteredAutoNeutrals.length ||
          existingAutoNeutrals.some((existing, index) => 
            existing.hex !== filteredAutoNeutrals[index]?.hex
          );

        if (needsUpdate) {
          onChange([...existingNonNeutrals, ...filteredAutoNeutrals]);
        }
      }
    }
  }, [primaryColor, autoNeutralsEnabled, colors, onChange]);

  // Group colors by role for display
  const colorsByRole = colors.reduce((acc, color, index) => {
    if (!acc[color.role]) {
      acc[color.role] = [];
    }
    acc[color.role].push({ ...color, index });
    return acc;
  }, {} as Record<string, (BrandColor & { index: number })[]>);

  // Get available roles for new colors with priority for underused roles
  const getAvailableRoles = () => {
    const availableRoles: string[] = [];
    const priorityRoles: string[] = [];
    const neutralRoles: string[] = [];
    
    // Define the natural order of roles
    const roleOrder = ['primary', 'secondary', 'accent', 'neutral_light', 'neutral_dark'];
    
    roleOrder.forEach(roleKey => {
      if (COLOR_ROLES[roleKey as keyof typeof COLOR_ROLES]) {
        const roleConfig = COLOR_ROLES[roleKey as keyof typeof COLOR_ROLES];
        const existingCount = colorsByRole[roleKey]?.length || 0;
        
        if (existingCount < roleConfig.maxCount) {
          // Separate neutral roles for special handling
          if (roleKey.includes('neutral')) {
            neutralRoles.push(roleKey);
          }
          // Always follow natural order, but prioritize missing secondary/accent after primary is filled
          else if ((roleKey === 'accent' || roleKey === 'secondary') && existingCount === 0 && colorsByRole['primary']?.length > 0) {
            priorityRoles.push(roleKey);
          } else {
            availableRoles.push(roleKey);
          }
        }
      }
    });
    
    // When auto neutrals are disabled and neutral roles are available, prioritize them
    // This helps users who turned off auto neutrals to manually add neutral colors
    if (!autoNeutralsEnabled && neutralRoles.length > 0) {
      return [...neutralRoles, ...priorityRoles, ...availableRoles];
    }
    
    // Return priority roles first, then others in natural order, then neutrals
    return [...priorityRoles, ...availableRoles, ...neutralRoles];
  };

  const handleAddColor = () => {
    const availableRoles = getAvailableRoles();
    if (availableRoles.length === 0) {
      toast.error(`Maximum ${maxColors} colors reached`);
      return;
    }

    // Show warning for palettes approaching the recommended limit
    if (colors.length >= 5 && !showPaletteSizeWarning) {
      setShowPaletteSizeWarning(true);
      return;
    }

    setColorPickerDialog({
      open: true,
      mode: 'add',
      initialColor: { hex: '#000000', role: availableRoles[0] },
    });
  };

  const handleProceedWithAddColor = () => {
    setShowPaletteSizeWarning(false);
    const availableRoles = getAvailableRoles();
    setColorPickerDialog({
      open: true,
      mode: 'add',
      initialColor: { hex: '#000000', role: availableRoles[0] },
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
    // Visual feedback is sufficient - no toast needed
  };

  const handleSaveColor = (brandColor: BrandColor) => {
    let newColors: BrandColor[] = [];

    if (colorPickerDialog.mode === 'add') {
      // Check for role-specific duplicate colors
      const roleColors = colors.filter(c => c.role === brandColor.role);
      if (roleColors.some(c => c.hex.toLowerCase() === brandColor.hex.toLowerCase())) {
        toast.error(`This color is already assigned to the ${brandColor.role} role`);
        return;
      }
      newColors = [...colors, brandColor];
    } else if (colorPickerDialog.mode === 'edit' && colorPickerDialog.editIndex !== undefined) {
      // Check for role-specific duplicate colors (excluding the one being edited)
      const otherColors = colors.filter((_, i) => i !== colorPickerDialog.editIndex);
      const roleColors = otherColors.filter(c => c.role === brandColor.role);
      if (roleColors.some(c => c.hex.toLowerCase() === brandColor.hex.toLowerCase())) {
        toast.error(`This color is already assigned to the ${brandColor.role} role`);
        return;
      }
      newColors = [...colors];
      newColors[colorPickerDialog.editIndex] = brandColor;
    }

    // Apply intelligent ratio calculation for automatic mode
    const hasCustomRatios = newColors.some(c => c.isCustomRatio && !c.role.includes('neutral'));
    
    if (!hasCustomRatios) {
      // Auto mode - apply intelligent 60-30-10 distribution
      newColors = calculateIntelligentRatios(newColors);
      // Visual feedback is sufficient - no toast needed
    } else {
      // Manual mode - enhanced logic for adding vs editing
      const isAddingNewColor = colorPickerDialog.mode === 'add';
      
      if (isAddingNewColor) {
        // Adding new color to manual ratios - auto-normalize
        newColors = smartNormalizeRatios(newColors);
        // Visual ratio updates provide sufficient feedback
      } else {
        // Editing existing color in manual mode
        newColors = smartNormalizeRatios(newColors);
        // Visual changes are sufficient feedback
      }
    }

    onChange(newColors);
  };

  const handleCloseColorPicker = () => {
    setColorPickerDialog({ open: false, mode: 'add' });
  };

  // Memoized accessibility warnings calculation
  const accessibilityWarnings = useMemo(() => {
    const warnings: string[] = [];
    const lightNeutral = colors.find(c => c.role === 'neutral_light');
    const darkNeutral = colors.find(c => c.role === 'neutral_dark');
    
    if (lightNeutral && darkNeutral) {
      const ratio = getContrastRatio(lightNeutral.hex, darkNeutral.hex);
      if (ratio < 4.5) {
        warnings.push('Light and dark neutrals may not have sufficient contrast for text');
      }
    }

    return warnings;
  }, [colors]);

  // Memoized status data for usage ratios section
  const statusData = useMemo(() => {
    const coreColors = colors.filter(c => !c.role.includes('neutral'));
    const coreTotal = coreColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
    const hasCustomRatios = coreColors.some(c => c.isCustomRatio);
    const lockedCount = coreColors.filter(c => c.isLocked).length;
    const totalDiff = Math.abs(coreTotal - 1);
    
    let statusColor = 'success.main';
    let statusIcon = '✅';
    let statusText = 'Perfect Balance';
    
    if (totalDiff >= 0.1) {
      statusColor = 'warning.main';
      statusIcon = '⚠️';
      statusText = 'Needs Balancing';
    } else if (totalDiff >= 0.05) {
      statusColor = 'info.main';
      statusIcon = '⚖️';
      statusText = 'Good Balance';
    }
    
    return { 
      coreColors, 
      coreTotal, 
      hasCustomRatios, 
      lockedCount, 
      totalDiff, 
      statusColor, 
      statusIcon, 
      statusText 
    };
  }, [colors]);

  // Memoized detailed accessibility analysis with caching
  const accessibilityPairs = useMemo(() => {
    const pairs: Array<{
      color1: BrandColor & { index: number };
      color2: BrandColor & { index: number };
      ratio: number;
      status: 'excellent' | 'good' | 'warning' | 'fail';
      level: 'AAA' | 'AA' | 'A' | 'Fail';
      recommendation?: string;
      harmonyIssue?: string;
    }> = [];

    colors.forEach((color1, i) => {
      colors.slice(i + 1).forEach((color2, j) => {
        const actualIndex = i + j + 1;
        const ratio = getContrastRatio(color1.hex, color2.hex);
        
        let status: 'excellent' | 'good' | 'warning' | 'fail';
        let level: 'AAA' | 'AA' | 'A' | 'Fail';
        let recommendation: string | undefined;
        
        if (ratio >= 7) {
          status = 'excellent';
          level = 'AAA';
        } else if (ratio >= 4.5) {
          status = 'good';
          level = 'AA';
        } else if (ratio >= 3) {
          status = 'warning';
          level = 'A';
          recommendation = 'Consider adjusting lightness for better readability';
        } else {
          status = 'fail';
          level = 'Fail';
          recommendation = 'Poor contrast - adjust colors significantly';
        }

        // Check for harmony issues
        let harmonyIssue: string | undefined;
        const { h: h1 } = hexToHsl(color1.hex);
        const { h: h2 } = hexToHsl(color2.hex);
        const hueDiff = Math.abs(h1 - h2);
        const normalizedDiff = Math.min(hueDiff, 360 - hueDiff);
        
        if (normalizedDiff > 120 && normalizedDiff < 150 && ratio < 4.5) {
          harmonyIssue = 'Clashing colors with poor contrast - consider analogous colors';
        } else if (normalizedDiff < 30 && ratio < 3) {
          harmonyIssue = 'Similar hues with insufficient contrast';
        }

        pairs.push({
          color1: { ...color1, index: i },
          color2: { ...color2, index: actualIndex },
          ratio,
          status,
          level,
          recommendation,
          harmonyIssue
        });
      });
    });

    return pairs;
  }, [colors]);

  // Critical contrast analysis for the most important pairings
  const criticalContrastPairs = useMemo(() => {
    const criticalPairs: Array<{
      bgColor: BrandColor & { index: number };
      textColor: BrandColor & { index: number };
      bgLabel: string;
      textLabel: string;
      ratio: number;
      status: 'pass' | 'fail';
    }> = [];

    // Get colors by role for easier access
    const backgroundColors = colors.filter(c => ['primary', 'secondary', 'accent'].includes(c.role));
    const textColors = colors.filter(c => ['neutral_light', 'neutral_dark'].includes(c.role));

    // If no specific text colors, use all colors as potential text
    const finalTextColors = textColors.length > 0 ? textColors : colors;

    backgroundColors.forEach((bgColor) => {
      finalTextColors.forEach((textColor) => {
        // Skip if same color
        if (bgColor.hex === textColor.hex) return;

        const bgIndex = colors.findIndex(c => c.hex === bgColor.hex);
        const textIndex = colors.findIndex(c => c.hex === textColor.hex);
        
        const ratio = getContrastRatio(bgColor.hex, textColor.hex);
        const status = ratio >= 4.5 ? 'pass' : 'fail';

        // Create readable labels
        const bgLabel = `${bgColor.role.charAt(0).toUpperCase() + bgColor.role.slice(1)} ${bgColor.label || bgColor.hex}`.replace('_', ' ');
        const textLabel = `${textColor.role.charAt(0).toUpperCase() + textColor.role.slice(1)} ${textColor.label || textColor.hex}`.replace('_', ' ');

        criticalPairs.push({
          bgColor: { ...bgColor, index: bgIndex },
          textColor: { ...textColor, index: textIndex },
          bgLabel,
          textLabel,
          ratio,
          status
        });
      });
    });

    // Sort by importance (failures first, then by ratio)
    return criticalPairs.sort((a, b) => {
      if (a.status !== b.status) {
        return a.status === 'fail' ? -1 : 1;
      }
      return a.ratio - b.ratio;
    });
  }, [colors]);

  // Memoized analogous color alternatives generator
  const generateAnalogousAlternatives = useCallback((baseHex: string, offset: number = 30): string[] => {
    const { h, s, l } = hexToHsl(baseHex);
    return [
      hslToHex((h + offset) % 360, s, l),
      hslToHex((h - offset + 360) % 360, s, l)
    ];
  }, []);

  const suggestHarmonyFix = useCallback((problematicColor: BrandColor, targetIndex: number) => {
    const alternatives = generateAnalogousAlternatives(problematicColor.hex);
    const bestAlternative = alternatives.find(alt => {
      // Test against all other colors for better contrast
      return colors.every((otherColor, idx) => {
        if (idx === targetIndex) return true;
        return getContrastRatio(alt, otherColor.hex) >= 3.0;
      });
    }) || alternatives[0];

    const newColors = [...colors];
    newColors[targetIndex] = {
      ...problematicColor,
      hex: bestAlternative,
      label: `${problematicColor.label || 'Color'} (Harmony Fixed)`
    };
    onChange(newColors);
    // Visual color change provides sufficient feedback
  }, [colors, onChange, generateAnalogousAlternatives]);

  // Memoized helper functions for intelligent ratio management
  const normalizeRatios = useCallback((colorsToNormalize: BrandColor[], activeIndex?: number): BrandColor[] => {
    return smartNormalizeRatios(colorsToNormalize, activeIndex);
  }, []);

  const resetRatiosToDefaults = useCallback((): void => {
    // Reset to intelligent auto mode
    const resetColors = colors.map(color => ({
      ...color,
      isCustomRatio: false,  // Clear custom flags
      isLocked: false  // Clear lock flags
    }));
    
    const intelligentColors = calculateIntelligentRatios(resetColors);
    onChange(intelligentColors);
    toast.success('Ratios reset to intelligent defaults (60-30-10 rule)', {
      icon: '🎯',
      duration: 2500
    });
  }, [colors, onChange]);





  // Handler for extracting colors from logo with enhanced error handling
  const handleExtractColorsFromLogo = async () => {
    if (!logoFile) {
      toast.error('No logo file available');
      return;
    }

    setIsLoading(true);
    setLoadingMessage('Extracting colors from logo...');

    try {
      const formData = new FormData();
      formData.append('image_file', logoFile);

      const response = await apiCallWithRetry(() => 
        fetch('/api/v1/brand-kit/extract-colors-from-image', {
          method: 'POST',
          body: formData,
        })
      );

      const data = await response.json();
      
      if (data.success && data.colors) {
        // Merge extracted colors with existing ones, avoiding duplicates
        const existingHexes = colors.map(c => c.hex.toLowerCase());
        const newColors = data.colors.filter((c: BrandColor) => 
          !existingHexes.includes(c.hex.toLowerCase())
        );

        if (newColors.length > 0) {
          // Show preview modal with extracted colors
          const availableRoles = getAvailableRoles();
          const colorsWithRoles = newColors.slice(0, availableRoles.length).map((color, index) => ({
            ...color,
            role: availableRoles[index] || 'accent'
          }));
          setPreviewModal({
            open: true,
            title: `Extracted ${newColors.length} Colors from Logo`,
            colors: colorsWithRoles,
            type: 'logo'
          });
          setSelectedColors(Array(colorsWithRoles.length).fill(true));
        } else {
          toast('No new colors found - all extracted colors are already in your palette', { icon: 'ℹ️' });
        }
      } else {
        // Provide offline fallback
        toast.error('Color extraction service unavailable. Try uploading a different image.', {
          duration: 4000,
        });
      }
    } catch (error) {
      console.error('Error extracting colors:', error);
      
      // Provide retry option
      toast((t) => (
        <Box>
          <Typography variant="caption" sx={{ display: 'block', mb: 1 }}>
            Failed to extract colors from logo
          </Typography>
          <Button
            size="small"
            variant="outlined"
            onClick={() => {
              toast.dismiss(t.id);
              handleExtractColorsFromLogo();
            }}
            sx={{ mr: 1 }}
          >
            Retry
          </Button>
          <Button
            size="small"
            onClick={() => toast.dismiss(t.id)}
          >
            Dismiss
          </Button>
        </Box>
      ), { duration: 6000 });
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  };

  // Handler for getting color harmony suggestions with enhanced error handling
  const handleGetColorHarmonies = async () => {
    if (!primaryColor) {
      toast.error('No primary color available');
      return;
    }

    setIsLoading(true);
    setLoadingMessage('Generating color harmonies...');

    try {
      const formData = new FormData();
      formData.append('base_color', primaryColor.hex);

      const response = await apiCallWithRetry(() =>
        fetch('/api/v1/brand-kit/color-harmonies', {
          method: 'POST',
          body: formData,
        })
      );

      const data = await response.json();
      
      if (data.success && data.harmonies) {
        // Show suggestions in a dialog or toast
        const suggestions = [
          ...data.harmonies.complementary,
          ...data.harmonies.analogous.slice(0, 1), // Take first analogous
          ...data.neutrals.slice(0, 1), // Take one neutral
        ];

        // Filter out colors that are too similar to existing ones
        const existingHexes = colors.map(c => c.hex.toLowerCase());
        const newSuggestions = suggestions.filter((c: BrandColor) => 
          !existingHexes.includes(c.hex.toLowerCase())
        );

        // Limit additions if approaching max colors
        const availableSlots = maxColors - colors.length;
        const suggestionsToAdd = newSuggestions.slice(0, Math.min(3, availableSlots));

        if (suggestionsToAdd.length > 0) {
          // Show preview modal with harmony suggestions
          const availableRoles = getAvailableRoles();
          const suggestionsWithRoles = suggestionsToAdd.slice(0, availableRoles.length).map((suggestion: BrandColor, index: number) => ({
            ...suggestion,
            role: availableRoles[index] || 'accent',
            label: `${suggestion.label} (Suggested)`,
          }));

          setPreviewModal({
            open: true,
            title: `Color Harmony Suggestions`,
            colors: suggestionsWithRoles,
            type: 'harmony'
          });
          setSelectedColors(Array(suggestionsWithRoles.length).fill(true));
        } else {
          toast('No new color suggestions available', { icon: 'ℹ️' });
        }
      } else {
        // Provide offline fallback with hardcoded harmonies
        const fallbackHarmonies = generateFallbackHarmonies(primaryColor.hex);
        const availableSlots = maxColors - colors.length;
        const suggestionsToAdd = fallbackHarmonies.slice(0, Math.min(2, availableSlots));
        
        if (suggestionsToAdd.length > 0) {
          setPreviewModal({
            open: true,
            title: `Basic Color Suggestions (Offline)`,
            colors: suggestionsToAdd,
            type: 'harmony'
          });
          setSelectedColors(Array(suggestionsToAdd.length).fill(true));
        } else {
          toast.error('Color harmony service unavailable');
        }
      }
    } catch (error) {
      console.error('Error getting color harmonies:', error);
      
      // Provide retry option and offline fallback
      toast((t) => (
        <Box>
          <Typography variant="caption" sx={{ display: 'block', mb: 1 }}>
            Failed to get color suggestions
          </Typography>
          <Button
            size="small"
            variant="outlined"
            onClick={() => {
              toast.dismiss(t.id);
              handleGetColorHarmonies();
            }}
            sx={{ mr: 1 }}
          >
            Retry
          </Button>
          <Button
            size="small"
            variant="outlined"
            onClick={() => {
              toast.dismiss(t.id);
              // Use offline fallback
              const fallbackHarmonies = generateFallbackHarmonies(primaryColor.hex);
              const availableSlots = maxColors - colors.length;
              const suggestionsToAdd = fallbackHarmonies.slice(0, Math.min(2, availableSlots));
              
              if (suggestionsToAdd.length > 0) {
                setPreviewModal({
                  open: true,
                  title: `Basic Color Suggestions`,
                  colors: suggestionsToAdd,
                  type: 'harmony'
                });
                setSelectedColors(Array(suggestionsToAdd.length).fill(true));
              }
            }}
            sx={{ mr: 1 }}
          >
            Use Basic
          </Button>
          <Button
            size="small"
            onClick={() => toast.dismiss(t.id)}
          >
            Dismiss
          </Button>
        </Box>
      ), { duration: 8000 });
    } finally {
      setIsLoading(false);
      setLoadingMessage('');
    }
  };

  // Helper function to fetch suggestions with a specific base color
  const fetchSuggestions = async (baseColor: BrandColor, targetRole: string, anchorEl: HTMLElement, offset = 0) => {
    setSuggestingForRole(targetRole);

    try {
      const formData = new FormData();
      formData.append('base_color', baseColor.hex);
      formData.append('target_role', targetRole);
      formData.append('offset', offset.toString());

      const response = await apiCallWithRetry(() =>
        fetch('/api/v1/brand-kit/color-harmonies', {
          method: 'POST',
          body: formData,
        })
      );

      const data = await response.json();
      
                // Process API response
      
      if (data.success && data.curated_suggestions && data.curated_suggestions.length > 0) {
        // Filter out colors that are too similar to existing ones
        const existingHexes = colors.map(c => c.hex.toLowerCase());
        
        let newSuggestions = data.curated_suggestions.filter((c: BrandColor) => 
          !colors.some(existingColor => areColorsSimilar(c.hex, existingColor.hex))
        );
        
        // Fallback: if filtering removed too many suggestions, relax the similarity threshold
        if (newSuggestions.length < 2 && data.curated_suggestions.length >= 2) {
          newSuggestions = data.curated_suggestions.filter((c: BrandColor) => 
            !colors.some(existingColor => areColorsSimilar(c.hex, existingColor.hex, 15)) // Stricter threshold
          );
        }
        
        // Final fallback: if still too few, take the first few unfiltered suggestions
        if (newSuggestions.length < 2 && data.curated_suggestions.length >= 2) {
          newSuggestions = data.curated_suggestions.slice(0, 4);
        }

        if (newSuggestions.length > 0) {
          // Force a layout recalculation before setting suggestions
          if (anchorEl) {
            anchorEl.getBoundingClientRect(); // Force layout
            // Small delay to ensure layout is complete
            setTimeout(() => {
              setSuggestions({
                anchorEl: anchorEl,
                role: targetRole,
                options: newSuggestions,
                offset: offset
              });
            }, 10);
          }
        } else {
          toast('No new color suggestions available for this role', { icon: 'ℹ️' });
        }
      } else {
        // Provide offline fallback
        const fallbackSuggestions = generateFallbackSuggestionsForRole(baseColor.hex, targetRole);
        
        if (fallbackSuggestions.length > 0) {
          setSuggestions({
            anchorEl: anchorEl,
            role: targetRole,
            options: fallbackSuggestions,
            offset: offset
          });
        } else {
          toast.error('Color suggestion service unavailable');
        }
      }
    } catch (error) {
      console.error('Error getting role suggestions:', error);
      
      // Provide offline fallback
      const fallbackSuggestions = generateFallbackSuggestionsForRole(baseColor.hex, targetRole);
      
      if (fallbackSuggestions.length > 0) {
        setSuggestions({
          anchorEl: anchorEl,
          role: targetRole,
          options: fallbackSuggestions,
          offset: offset
        });
      } else {
        toast.error('Failed to generate suggestions');
      }
    } finally {
      setSuggestingForRole(null);
    }
  };

  // Handler for getting role-specific color suggestions
  const handleGetRoleSuggestions = async (event: React.MouseEvent<HTMLElement>, targetRole: string) => {
    // Capture the event target before async operations
    const anchorElement = event.currentTarget;
    
    // Get all primary colors
    const primaryColors = colors.filter(c => c.role === 'primary');
    
    if (primaryColors.length === 0) {
      toast.error('No primary color available');
      return;
    }

    // Set suggestion mode to 'add' for new suggestions
    setSuggestionMode({ mode: 'add' });

    if (primaryColors.length === 1) {
      // Use the single primary color directly
      await fetchSuggestions(primaryColors[0], targetRole, anchorElement);
    } else {
      // Show primary color selection popover
      setPrimarySelection({
        anchorEl: anchorElement,
        targetRole: targetRole
      });
    }
  };

  // Handler for replacing existing colors with suggestions
  const handleReplaceColorSuggestions = async (event: React.MouseEvent<HTMLElement>, colorIndex: number, colorRole: string) => {
    // Capture the event target before async operations
    const anchorElement = event.currentTarget;
    
    // Get all primary colors
    const primaryColors = colors.filter(c => c.role === 'primary');
    
    if (primaryColors.length === 0) {
      toast.error('No primary color available');
      return;
    }

    // Set suggestion mode to 'replace'
    setSuggestionMode({ mode: 'replace', targetIndex: colorIndex });

    if (primaryColors.length === 1) {
      // Use the single primary color directly
      await fetchSuggestions(primaryColors[0], colorRole, anchorElement);
    } else {
      // Show primary color selection popover
      setPrimarySelection({
        anchorEl: anchorElement,
        targetRole: colorRole
      });
    }
  };

  // Memoized fallback harmony generation for offline mode
  const generateFallbackHarmonies = useCallback((baseHex: string): BrandColor[] => {
    const { h, s, l } = hexToHsl(baseHex);
    
    return [
      {
        hex: hslToHex((h + 180) % 360, s, l), // Complementary
        role: 'secondary',
        label: 'Complementary'
      },
      {
        hex: hslToHex(h, Math.max(10, s - 20), Math.min(90, l + 20)), // Lighter analog
        role: 'accent',
        label: 'Light Analog'
      }
    ];
  }, []);

  // Generate fallback suggestions for specific roles
  const generateFallbackSuggestionsForRole = useCallback((baseHex: string, targetRole: string): BrandColor[] => {
    const { h, s, l } = hexToHsl(baseHex);
    
    switch (targetRole) {
      case 'accent':
        return [
          {
            hex: hslToHex((h + 180) % 360, s, l), // Complementary
            role: 'accent',
            label: 'Complementary'
          },
          {
            hex: hslToHex((h + 120) % 360, s, l), // Triadic
            role: 'accent',
            label: 'Triadic'
          },
          {
            hex: hslToHex((h + 210) % 360, Math.max(10, s - 10), l), // Split complementary
            role: 'accent',
            label: 'Split Comp'
          }
        ];
      
      case 'secondary':
        return [
          {
            hex: hslToHex((h + 30) % 360, s, l), // Analogous
            role: 'secondary',
            label: 'Analogous'
          },
          {
            hex: hslToHex((h - 30 + 360) % 360, s, l), // Analogous opposite
            role: 'secondary',
            label: 'Analogous Alt'
          }
        ];
      
      case 'neutral_light':
        return [
          {
            hex: hslToHex(h, Math.max(5, s * 0.2), Math.min(95, l + 30)), // Light neutral
            role: 'neutral_light',
            label: 'Light Neutral'
          },
          {
            hex: hslToHex(h, Math.max(5, s * 0.3), Math.min(90, l + 25)), // Alt light
            role: 'neutral_light',
            label: 'Alt Light'
          }
        ];
      
      case 'neutral_dark':
        return [
          {
            hex: hslToHex(h, Math.max(5, s * 0.3), Math.max(5, l - 40)), // Dark neutral
            role: 'neutral_dark',
            label: 'Dark Neutral'
          },
          {
            hex: hslToHex(h, Math.max(5, s * 0.2), Math.max(10, l - 35)), // Alt dark
            role: 'neutral_dark',
            label: 'Alt Dark'
          }
        ];
      
      default:
        return [];
    }
  }, []);

  return (
    <Box>
      {showLabels && (
        <Box sx={{ 
          mb: 1.5,
          p: 1.5,
          background: `linear-gradient(135deg, ${theme.palette.primary.main}05 0%, ${theme.palette.secondary.main}05 100%)`,
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}30`,
        }}>
          <Box display="flex" alignItems="center" gap={1} mb={0.5}>
            <PaletteIcon color="primary" sx={{ fontSize: 18 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.main', fontSize: '0.95rem' }}>
              Brand Colors
            </Typography>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.4, fontSize: '0.75rem' }}>
            Define semantic color roles for AI-generated visuals
          </Typography>
        </Box>
      )}
        {/* Tier 1: Default View - Compact Design */}
        <Card sx={{ 
          borderRadius: 2, 
          mb: 1.5,
          background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
          border: `1px solid ${theme.palette.divider}`,
          overflow: 'visible',
          position: 'relative',
        }}>
        <CardContent sx={{ p: 2, position: 'relative' }}>
          {/* Semantic Role Sections */}
          {Object.entries(COLOR_ROLES).map(([roleKey, roleConfig], index) => {
            const roleColors = colorsByRole[roleKey] || [];
            const isAutoNeutral = roleKey.includes('neutral') && autoNeutralsEnabled;
            
            return (
              <Fade in={true} timeout={300 + index * 100} key={roleKey}>
                <Box sx={{ mb: index === Object.entries(COLOR_ROLES).length - 1 ? 1 : 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1, position: 'relative' }}>
                    <Box
                      sx={{
                        width: 3,
                        height: 16,
                        backgroundColor: roleKey === 'primary' ? 'primary.main' : 
                                        roleKey === 'secondary' ? 'secondary.main' :
                                        roleKey === 'accent' ? 'warning.main' : 'grey.400',
                        borderRadius: 1.5,
                        mr: 1,
                      }}
                    />
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mr: 1, fontSize: '0.85rem' }}>
                      {roleConfig.label}
                    </Typography>
                    {isAutoNeutral && (
                      <Chip
                        size="small"
                        label="Auto"
                        color="info"
                        variant="outlined"
                        sx={{ 
                          mr: 1,
                          borderRadius: 1,
                          fontSize: '0.65rem',
                          height: 18,
                          '& .MuiChip-label': { px: 0.5 }
                        }}
                      />
                    )}
                    <Typography variant="caption" color="text.secondary" sx={{ flex: 1, fontStyle: 'italic', fontSize: '0.7rem' }}>
                      {roleConfig.description}
                    </Typography>
                    {/* Suggestion button for applicable roles */}
                    {['secondary', 'accent', 'neutral_light', 'neutral_dark'].includes(roleKey) && (
                      <Box 
                        sx={{ 
                          position: 'relative',
                          display: 'inline-flex',
                          alignItems: 'center',
                          minHeight: 20, // Ensure minimum height for layout
                          minWidth: 60   // Ensure minimum width for layout
                        }}
                      >
                        {suggestingForRole === roleKey ? (
                          <CircularProgress size={16} sx={{ color: 'primary.main' }} />
                        ) : (
                          <Chip
                            label="✨ Suggest"
                            size="small"
                            variant="outlined"
                            color="primary"
                            disabled={!primaryColor || roleColors.length >= roleConfig.maxCount}
                            onClick={(e) => {
                              // Use the parent Box as the anchor element
                              const anchorElement = e.currentTarget.parentElement;
                              if (anchorElement) {
                                // Create a synthetic event with the parent as currentTarget
                                const syntheticEvent = {
                                  ...e,
                                  currentTarget: anchorElement
                                } as React.MouseEvent<HTMLElement>;
                                handleGetRoleSuggestions(syntheticEvent, roleKey);
                              }
                            }}
                            sx={{
                              fontSize: '0.65rem',
                              height: 18,
                              cursor: 'pointer',
                              '& .MuiChip-label': { px: 0.5 },
                              opacity: (!primaryColor || roleColors.length >= roleConfig.maxCount) ? 0.5 : 1,
                              transition: 'opacity 0.2s ease',
                            }}
                          />
                        )}
                      </Box>
                    )}
                  </Box>
                  
                  <Box sx={{ 
                    display: 'grid',
                    gridTemplateColumns: isMobile 
                      ? 'repeat(auto-fill, minmax(40px, 1fr))' 
                      : isTablet 
                        ? 'repeat(auto-fill, minmax(50px, 1fr))'
                        : 'repeat(auto-fill, minmax(60px, 1fr))',
                    gap: isMobile ? 0.5 : 1,
                    maxWidth: isMobile ? 300 : isTablet ? 350 : 400,
                  }}>
                    {roleColors.map((colorData) => (
                      <Box key={colorData.index} sx={{ position: 'relative' }}>
                        <Tooltip 
                          title={`${colorData.hex.toUpperCase()}${colorData.label ? ` - ${colorData.label}` : ''}`}
                          arrow
                          placement={isMobile ? "top" : "top-start"}
                          componentsProps={{
                            tooltip: {
                              sx: {
                                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                                backdropFilter: 'blur(4px)',
                                borderRadius: 1.5,
                                fontSize: isMobile ? '0.7rem' : '0.75rem',
                                fontWeight: 600,
                                maxWidth: isMobile ? 200 : 'none',
                              }
                            }
                          }}
                        >
                          <Card
                            sx={{
                              height: isMobile ? 40 : isTablet ? 45 : 50,
                              backgroundColor: colorData.hex,
                              borderRadius: 1.5,
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              position: 'relative',
                              overflow: 'hidden',
                              border: `1px solid ${theme.palette.divider}30`,
                              '&:hover': {
                                transform: 'translateY(-1px) scale(1.05)',
                                boxShadow: `0 4px 12px ${colorData.hex}60`,
                                border: `1px solid ${theme.palette.primary.main}`,
                              },
                            }}
                            onClick={() => handleEditColor(colorData.index)}
                          >
                            <CardContent sx={{ 
                              p: 0.5, 
                              height: '100%', 
                              display: 'flex', 
                              alignItems: 'flex-end',
                              justifyContent: 'center',
                              '&:last-child': { pb: 0.5 }
                            }}>
                              <Typography
                                variant="caption"
                                sx={{
                                  color: getContrastColor(colorData.hex),
                                  fontWeight: 600,
                                  fontSize: '0.6rem',
                                  fontFamily: 'monospace',
                                  textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                                  backgroundColor: 'rgba(0,0,0,0.15)',
                                  px: 0.5,
                                  py: 0.25,
                                  borderRadius: 0.5,
                                }}
                              >
                                {colorData.hex.slice(1).toUpperCase()}
                              </Typography>
                              
                              {/* Enhanced contrast indicator with detailed tooltip */}
                              {(() => {
                                const colorPairs = accessibilityPairs.filter(
                                  pair => pair.color1.index === colorData.index || pair.color2.index === colorData.index
                                );
                                
                                if (colorPairs.length === 0) return null;
                                
                                const worstPair = colorPairs.reduce((worst, current) => 
                                  current.ratio < worst.ratio ? current : worst
                                );
                                
                                const bestPair = colorPairs.reduce((best, current) => 
                                  current.ratio > best.ratio ? current : best
                                );
                                
                                const hasFailures = colorPairs.some(pair => pair.status === 'fail');
                                const hasWarnings = colorPairs.some(pair => pair.status === 'warning');
                                const allExcellent = colorPairs.every(pair => pair.status === 'excellent');
                                
                                let icon, color, tooltipContent;
                                
                                if (hasFailures) {
                                  icon = <WarningIcon sx={{ fontSize: 12 }} />;
                                  color = 'error.main';
                                  
                                  const isExpanded = expandedTooltips.has(colorData.index);
                                  
                                  tooltipContent = (
                                    <Box>
                                      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                        Accessibility Issues
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                                        Worst: {worstPair.ratio.toFixed(1)}:1 ({worstPair.level})
                                      </Typography>
                                      
                                      {!isExpanded ? (
                                        <Button
                                          size="small"
                                          variant="text"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setExpandedTooltips(prev => new Set([...Array.from(prev), colorData.index]));
                                          }}
                                          sx={{ 
                                            fontSize: '0.6rem',
                                            minWidth: 'auto',
                                            p: 0.5,
                                            textTransform: 'none'
                                          }}
                                        >
                                          Details & Fixes →
                                        </Button>
                                      ) : (
                                        <Box>
                                          {worstPair.recommendation && (
                                            <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem' }}>
                                              {worstPair.recommendation}
                                            </Typography>
                                          )}
                                          {worstPair.harmonyIssue && (
                                            <>
                                              <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem', mt: 0.5 }}>
                                                🎨 {worstPair.harmonyIssue}
                                              </Typography>
                                              {(() => {
                                                const alternatives = generateAnalogousAlternatives(colorData.hex);
                                                return (
                                                  <Box sx={{ mt: 0.5 }}>
                                                    <Typography variant="caption" sx={{ fontSize: '0.55rem', display: 'block' }}>
                                                      Suggested alternatives:
                                                    </Typography>
                                                    <Box sx={{ display: 'flex', gap: 0.5, mt: 0.25 }}>
                                                      {alternatives.slice(0, 2).map((altHex, altIndex) => (
                                                        <Box
                                                          key={altIndex}
                                                          sx={{
                                                            width: 16,
                                                            height: 16,
                                                            backgroundColor: altHex,
                                                            borderRadius: 0.5,
                                                            cursor: 'pointer',
                                                            border: '1px solid rgba(255,255,255,0.5)',
                                                            '&:hover': {
                                                              transform: 'scale(1.1)'
                                                            }
                                                          }}
                                                          onClick={(e) => {
                                                            e.stopPropagation();
                                                            suggestHarmonyFix(colorData, colorData.index);
                                                          }}
                                                          title={`Click to apply: ${altHex}`}
                                                        />
                                                      ))}
                                                    </Box>
                                                  </Box>
                                                );
                                              })()}
                                            </>
                                          )}
                                          <Button
                                            size="small"
                                            variant="text"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              setExpandedTooltips(prev => {
                                                const newSet = new Set(prev);
                                                newSet.delete(colorData.index);
                                                return newSet;
                                              });
                                            }}
                                            sx={{ 
                                              fontSize: '0.6rem',
                                              minWidth: 'auto',
                                              p: 0.5,
                                              textTransform: 'none',
                                              mt: 0.5
                                            }}
                                          >
                                            ← Collapse
                                          </Button>
                                        </Box>
                                      )}
                                    </Box>
                                  );
                                } else if (hasWarnings) {
                                  icon = <WarningIcon sx={{ fontSize: 12 }} />;
                                  color = 'warning.main';
                                  tooltipContent = (
                                    <Box>
                                      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                        Contrast Warning
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block' }}>
                                        Lowest: {worstPair.ratio.toFixed(1)}:1 ({worstPair.level})
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem' }}>
                                        Consider improving for better accessibility
                                      </Typography>
                                    </Box>
                                  );
                                } else if (allExcellent) {
                                  icon = <CheckCircleIcon sx={{ fontSize: 12 }} />;
                                  color = 'success.main';
                                  tooltipContent = (
                                    <Box>
                                      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                        Excellent Accessibility
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block' }}>
                                        All contrasts: AAA level
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block' }}>
                                        Best: {bestPair.ratio.toFixed(1)}:1
                                      </Typography>
                                    </Box>
                                  );
                                } else {
                                  icon = <CheckCircleIcon sx={{ fontSize: 12 }} />;
                                  color = 'info.main';
                                  tooltipContent = (
                                    <Box>
                                      <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                        Good Accessibility
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block' }}>
                                        Range: {worstPair.ratio.toFixed(1)}:1 - {bestPair.ratio.toFixed(1)}:1
                                      </Typography>
                                      <Typography variant="caption" sx={{ display: 'block' }}>
                                        Meets AA standards
                                      </Typography>
                                    </Box>
                                  );
                                }
                                
                                return (
                                  <Tooltip 
                                    title={tooltipContent} 
                                    placement={isMobile ? "bottom" : "bottom-end"} 
                                    arrow
                                    componentsProps={{
                                      tooltip: {
                                        sx: {
                                          maxWidth: isMobile ? 240 : 280,
                                          backgroundColor: 'rgba(0, 0, 0, 0.9)',
                                          backdropFilter: 'blur(8px)',
                                          border: `1px solid ${color}40`,
                                          borderRadius: 2,
                                          boxShadow: `0 4px 20px rgba(0,0,0,0.3), 0 0 0 1px ${color}20`,
                                          fontSize: isMobile ? '0.7rem' : '0.75rem',
                                        }
                                      },
                                      arrow: {
                                        sx: {
                                          color: 'rgba(0, 0, 0, 0.9)',
                                          '&::before': {
                                            border: `1px solid ${color}40`,
                                          }
                                        }
                                      }
                                    }}
                                  >
                                    <Box
                                      sx={{
                                        position: 'absolute',
                                        top: 2,
                                        right: 2,
                                        color,
                                        backgroundColor: 'rgba(255,255,255,0.95)',
                                        borderRadius: '50%',
                                        p: 0.25,
                                        cursor: 'help',
                                        border: `1px solid ${color}30`,
                                        boxShadow: `0 2px 8px rgba(0,0,0,0.15)`,
                                        transition: 'all 0.2s ease',
                                        '&:hover': {
                                          backgroundColor: 'rgba(255,255,255,1)',
                                          transform: 'scale(1.1)',
                                          boxShadow: `0 4px 12px rgba(0,0,0,0.25)`,
                                        }
                                      }}
                                    >
                                      {icon}
                                    </Box>
                                  </Tooltip>
                                );
                              })()}
                            </CardContent>
                          </Card>
                        </Tooltip>
                        
                        {/* Replace button for non-primary, non-auto colors */}
                        {!isAutoNeutral && roleKey !== 'primary' && (
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleReplaceColorSuggestions(e, colorData.index, roleKey);
                            }}
                            sx={{
                              position: 'absolute',
                              top: -4,
                              right: 14,
                              backgroundColor: 'primary.main',
                              color: 'white',
                              width: 16,
                              height: 16,
                              minWidth: 16,
                              '&:hover': {
                                backgroundColor: 'primary.dark',
                                transform: 'scale(1.1)',
                              },
                              transition: 'all 0.2s ease',
                            }}
                          >
                            <AutoFixHighIcon sx={{ fontSize: 10 }} />
                          </IconButton>
                        )}
                        
                        {/* Delete button for non-auto colors */}
                        {!isAutoNeutral && (
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleRemoveColor(colorData.index);
                            }}
                            sx={{
                              position: 'absolute',
                              top: -4,
                              right: -4,
                              backgroundColor: 'error.main',
                              color: 'white',
                              width: 16,
                              height: 16,
                              minWidth: 16,
                              '&:hover': {
                                backgroundColor: 'error.dark',
                                transform: 'scale(1.1)',
                              },
                              transition: 'all 0.2s ease',
                            }}
                          >
                            <DeleteIcon sx={{ fontSize: 10 }} />
                          </IconButton>
                        )}
                      </Box>
                    ))}
                    
                    {/* Add Color Button - Compact Design */}
                    {roleColors.length < roleConfig.maxCount && !isAutoNeutral && (
                      <Tooltip title={`Add ${roleConfig.label.toLowerCase()}`} arrow>
                        <Card
                          sx={{
                            height: 50,
                            border: `1px dashed ${theme.palette.primary.main}`,
                            borderRadius: 1.5,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            backgroundColor: `${theme.palette.primary.main}08`,
                            transition: 'all 0.2s ease',
                            '&:hover': {
                              backgroundColor: `${theme.palette.primary.main}15`,
                              transform: 'translateY(-1px)',
                              borderColor: theme.palette.primary.dark,
                            },
                          }}
                          onClick={handleAddColor}
                        >
                          <AddIcon 
                            sx={{ 
                              color: 'primary.main', 
                              fontSize: 18,
                            }} 
                          />
                        </Card>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              </Fade>
            );
          })}

          {/* Live Preview - Enhanced with Role Labels */}
          {colors.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center" gap={0.5}>
                  <ColorLensIcon color="primary" sx={{ fontSize: 14 }} />
                  <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                    Preview
                  </Typography>
                  <Tooltip title="Preview AI application (e.g., primary dominant)" placement="top">
                    <LightbulbIcon color="action" sx={{ fontSize: 12 }} />
                  </Tooltip>
                </Box>
                
                {/* Preview Mode Toggle */}
                <Tooltip title={`Switch to ${previewMode === 'bar' ? 'circle' : 'bar'} view`}>
                  <IconButton
                    size="small"
                    onClick={() => setPreviewMode(previewMode === 'bar' ? 'circles' : 'bar')}
                    sx={{ 
                      p: 0.25,
                      color: 'text.secondary',
                      '&:hover': {
                        color: 'primary.main',
                        backgroundColor: `${theme.palette.primary.main}10`,
                      }
                    }}
                  >
                    {previewMode === 'bar' ? <ViewModuleIcon sx={{ fontSize: 14 }} /> : <ViewStreamIcon sx={{ fontSize: 14 }} />}
                  </IconButton>
                </Tooltip>
              </Box>
              {previewMode === 'bar' ? (
                // Enhanced Bar Preview
                <EnhancedColorBar
                  colors={colors}
                  height={40}
                  showLabels={true}
                  borderRadius={6}
                />
              ) : (
                // Circle Grid Preview
                <Box sx={{ 
                  display: 'flex', 
                  flexWrap: 'wrap',
                  gap: 1,
                  p: 1,
                  borderRadius: 1,
                  border: `1px solid ${theme.palette.divider}`,
                  backgroundColor: theme.palette.background.paper,
                  justifyContent: 'center',
                  minHeight: 60
                }}>
                  {colors.map((color, index) => {
                    const roleAbbrev = COLOR_ROLES[color.role as keyof typeof COLOR_ROLES]?.label?.slice(0, 3) || 
                                     color.role.slice(0, 3).toUpperCase();
                    const ratio = color.ratio || (1 / colors.length);
                    const size = Math.max(24, Math.min(48, 24 + (ratio * 40))); // Dynamic size based on ratio
                    
                    return (
                      <Tooltip 
                        key={index}
                        title={`${COLOR_ROLES[color.role as keyof typeof COLOR_ROLES]?.label || color.role}: ${color.hex} (${Math.round(ratio * 100)}%)`}
                        placement="top"
                      >
                        <Box
                          sx={{
                            width: size,
                            height: size,
                            borderRadius: '50%',
                            backgroundColor: color.hex,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            position: 'relative',
                            border: `2px solid ${theme.palette.background.paper}`,
                            boxShadow: `0 2px 8px ${color.hex}40`,
                            transition: 'all 0.2s ease',
                            '&:hover': {
                              transform: 'scale(1.1)',
                              boxShadow: `0 4px 16px ${color.hex}60`,
                            }
                          }}
                        >
                          <Typography
                            variant="caption"
                            sx={{
                              color: getContrastColor(color.hex),
                              fontWeight: 700,
                              fontSize: size > 32 ? '0.65rem' : '0.55rem',
                              textShadow: '0 1px 2px rgba(0,0,0,0.5)',
                              letterSpacing: 0.5,
                            }}
                          >
                            {roleAbbrev}
                          </Typography>
                          
                          {/* Size indicator for ratio */}
                          {ratio > 0.3 && (
                            <Box
                              sx={{
                                position: 'absolute',
                                top: -2,
                                right: -2,
                                width: 8,
                                height: 8,
                                borderRadius: '50%',
                                backgroundColor: theme.palette.warning.main,
                                border: `1px solid ${theme.palette.background.paper}`,
                              }}
                            />
                          )}
                        </Box>
                      </Tooltip>
                    );
                  })}
                </Box>
              )}
            </Box>
          )}

          {/* Enhanced Accessibility Alert with Critical Pairings */}
          {(accessibilityWarnings.length > 0 || criticalContrastPairs.some(p => p.status === 'fail')) && (
            <Alert 
              severity="warning" 
              sx={{ 
                mt: 1.5,
                borderRadius: 1,
                py: 1,
                '& .MuiAlert-message': { py: 0 }
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem', display: 'block', mb: 0.5 }}>
                Accessibility Issues
              </Typography>
              
              {/* Critical Contrast Checks */}
              {criticalContrastPairs.length > 0 && (
                <Box sx={{ mb: accessibilityWarnings.length > 0 ? 1 : 0 }}>
                  <Typography variant="caption" sx={{ fontSize: '0.7rem', color: 'text.secondary', display: 'block', mb: 0.5 }}>
                    Critical Contrast Checks:
                  </Typography>
                  {criticalContrastPairs.slice(0, 3).map((pair, index) => (
                    <Typography key={index} variant="caption" sx={{ 
                      fontSize: '0.65rem', 
                      display: 'block',
                      fontFamily: 'monospace',
                      color: pair.status === 'fail' ? 'error.main' : 'success.main'
                    }}>
                      {pair.bgLabel} on {pair.textLabel}: {pair.ratio.toFixed(1)}:1 {pair.status === 'pass' ? '✓' : '!'}
                    </Typography>
                  ))}
                  {criticalContrastPairs.length > 3 && (
                    <Typography variant="caption" sx={{ 
                      fontSize: '0.65rem', 
                      color: 'text.disabled',
                      fontStyle: 'italic'
                    }}>
                      +{criticalContrastPairs.length - 3} more pairs...
                    </Typography>
                  )}
                </Box>
              )}
              
              {/* General Accessibility Warnings */}
              {accessibilityWarnings.length > 0 && (
                <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
                  {accessibilityWarnings.join('; ')}
                </Typography>
              )}
            </Alert>
          )}

          {/* Status Bar - Enhanced with Progress */}
          <Box sx={{ mt: 1.5 }}>
            {(() => {
              const coreColors = colors.filter(c => !c.isAuto);  // Exclude auto-neutrals
              const autoNeutralsCount = colors.filter(c => c.isAuto).length;
              
              return (
                <>
                  <Box sx={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'center', 
                    mb: 0.5,
                  }}>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                      Palette Progress
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                        <Box component="span" sx={{ fontWeight: 700, color: 'primary.main' }}>
                          {coreColors.length}
                        </Box>
                        /{maxColors} core colors
                        {coreColors.length >= 5 && (
                          <Chip 
                            label={coreColors.length === maxColors ? "Max" : "Full"} 
                            size="small" 
                            color={coreColors.length === maxColors ? "warning" : "success"} 
                            variant="outlined"
                            sx={{ ml: 0.5, fontSize: '0.6rem', height: 16 }}
                          />
                        )}
                      </Typography>
                      {autoNeutralsCount > 0 && (
                        <Chip 
                          label={`+${autoNeutralsCount} Auto Neutrals`} 
                          size="small" 
                          color="info" 
                          variant="outlined" 
                          sx={{ ml: 0.5, height: 18, fontSize: '0.6rem' }} 
                        />
                      )}
                    </Box>
                  </Box>
                  
                  <LinearProgress
                    variant="determinate"
                    value={(coreColors.length / maxColors) * 100}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      backgroundColor: `${theme.palette.primary.main}10`,
                      '& .MuiLinearProgress-bar': {
                        borderRadius: 3,
                        background: coreColors.length >= 5 
                          ? `linear-gradient(90deg, ${theme.palette.success.main}, ${theme.palette.warning.main})`
                          : `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                      },
                    }}
                  />
                  
                  {/* Role completion indicators */}
                  <Box sx={{ 
                    display: 'flex', 
                    justifyContent: 'center', 
                    gap: isMobile ? 0.5 : 1, 
                    mt: 1,
                    flexWrap: 'wrap',
                    flexDirection: isMobile ? 'column' : 'row',
                    alignItems: isMobile ? 'center' : 'flex-start'
                  }}>
                    {Object.entries(COLOR_ROLES).map(([roleKey, roleConfig]) => {
                      const hasRole = colors.some(c => c.role === roleKey);
                      return (
                        <Tooltip 
                          key={roleKey} 
                          title={`${roleConfig.label}: ${hasRole ? 'Added' : 'Missing'}`}
                          placement="top"
                        >
                          <Chip
                            label={roleConfig.label.slice(0, 3)}
                            size="small"
                            variant={hasRole ? "filled" : "outlined"}
                            color={hasRole ? "primary" : "default"}
                            sx={{ 
                              fontSize: '0.6rem', 
                              height: 18,
                              minWidth: 40,
                              '& .MuiChip-label': { px: 0.5 }
                            }}
                          />
                        </Tooltip>
                      );
                    })}
                  </Box>
                </>
              );
            })()}
          </Box>
        </CardContent>
      </Card>

      {/* Tier 2: Advanced Settings */}
      <Collapse in={showAdvanced}>
        <Card sx={{ 
          mb: 1.5,
          borderRadius: 2,
          background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
          border: `1px solid ${theme.palette.divider}`,
        }}>
          <CardContent sx={{ p: 1.5 }}>
            <Box display="flex" alignItems="center" gap={1} mb={1.5}>
              <TuneIcon color="primary" sx={{ fontSize: 16 }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main', fontSize: '0.85rem' }}>
                Advanced Controls
              </Typography>
            </Box>
            
            <Stack spacing={2}>
              {/* Auto Neutrals Toggle - Horizontal Layout */}
              <Box sx={{ 
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                p: 1.5,
                backgroundColor: `${theme.palette.info.main}08`,
                border: `1px solid ${theme.palette.info.main}20`,
                borderRadius: 1.5,
              }}>
                <Box display="flex" alignItems="center" gap={1}>
                  <PsychologyIcon color="info" sx={{ fontSize: 16 }} />
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', fontSize: '0.75rem' }}>
                      Auto Neutrals
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                      Generate light/dark colors
                    </Typography>
                  </Box>
                </Box>
                <Button
                  variant={autoNeutralsEnabled ? "contained" : "outlined"}
                  onClick={() => {
                    const newEnabled = !autoNeutralsEnabled;
                    setAutoNeutralsEnabled(newEnabled);
                    
                    // If turning off auto-neutrals, remove existing auto-generated ones
                    if (!newEnabled) {
                      const nonAutoColors = colors.filter(c => !c.isAuto);
                      if (nonAutoColors.length !== colors.length) {
                        if (nonAutoColors.length === 0) {
                          // Prevent completely empty palette - show warning
                          toast.error('Cannot remove all colors. Add manual colors before disabling auto-neutrals.', {
                            duration: 4000
                          });
                          return; // Don't disable auto-neutrals if it would result in empty palette
                        }
                        onChange(nonAutoColors);
                        toast('Auto-generated neutral colors removed', {
                          icon: '🎨',
                          duration: 2000
                        });
                      }
                    }
                  }}
                  size="small"
                  sx={{ 
                    borderRadius: 1.5,
                    textTransform: 'none',
                    fontWeight: 600,
                    px: 1.5,
                    py: 0.5,
                    fontSize: '0.7rem',
                    minWidth: 'auto',
                    ...(autoNeutralsEnabled && {
                      background: `linear-gradient(135deg, ${theme.palette.success.main} 0%, ${theme.palette.success.dark} 100%)`,
                    })
                  }}
                >
                  {autoNeutralsEnabled ? 'ON' : 'OFF'}
                </Button>
              </Box>

              {/* Mock Thumbnail Previews */}
              {colors.length >= 3 && (
                <Box sx={{ 
                  p: 1.5,
                  backgroundColor: `${theme.palette.primary.main}08`,
                  border: `1px solid ${theme.palette.primary.main}20`,
                  borderRadius: 1.5,
                }}>
                  <Box display="flex" alignItems="center" gap={1} mb={1.5}>
                    <ColorLensIcon color="primary" sx={{ fontSize: 16 }} />
                    <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                      Design Previews
                    </Typography>
                    <Tooltip title="Mock designs showing how your palette might be applied">
                      <LightbulbIcon color="action" sx={{ fontSize: 12 }} />
                    </Tooltip>
                  </Box>
                  
                  <Box sx={{ 
                    display: 'flex', 
                    gap: 1.5, 
                    overflowX: 'auto',
                    p: 1,
                    m: -1,
                    WebkitOverflowScrolling: 'touch',
                    '&::-webkit-scrollbar': {
                      height: '4px',
                    },
                    '&::-webkit-scrollbar-thumb': {
                      backgroundColor: theme.palette.divider,
                      borderRadius: '2px',
                    },
                  }}>
                    {/* Product-Focused Preview */}
                    <ProductFocusedPreview colors={colors} />

                    {/* Promotional Announcement Preview */}
                    <PromotionalAnnouncementPreview colors={colors} />

                    {/* Lifestyle Atmosphere Preview */}
                    <LifestyleAtmospherePreview colors={colors} />
                  </Box>
                </Box>
              )}

              {/* Color Ratios - Compact Layout */}
              <Box sx={{ 
                p: 1.5,
                backgroundColor: `${theme.palette.secondary.main}08`,
                border: `1px solid ${theme.palette.secondary.main}20`,
                borderRadius: 1.5,
              }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <TuneIcon color="secondary" sx={{ fontSize: 16 }} />
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                      Usage Ratios
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.65rem', fontStyle: 'italic' }}>
                      Core brand colors only • Neutrals used functionally
                    </Typography>
                  </Box>
                </Box>
                
                {(() => {
                  const coreColors = colors.filter(c => !c.role.includes('neutral'));
                  if (coreColors.length === 0) {
                    return (
                      <Typography variant="caption" color="text.secondary" sx={{ 
                        fontSize: '0.7rem',
                        textAlign: 'center',
                        display: 'block',
                        py: 1
                      }}>
                        Add core colors (primary, secondary, accent) to configure usage ratios
                      </Typography>
                    );
                  }

                  const roleOrder = ['primary', 'secondary', 'accent'];
                  const sortedCoreColors = coreColors.sort((a, b) => {
                    const aIndex = roleOrder.indexOf(a.role);
                    const bIndex = roleOrder.indexOf(b.role);
                    const aOrder = aIndex === -1 ? 999 : aIndex;
                    const bOrder = bIndex === -1 ? 999 : bIndex;
                    return aOrder - bOrder;
                  });

                  const coreTotal = coreColors.reduce((sum, c) => sum + (c.ratio || 0.2), 0);
                  const neutralColors = colors.filter(c => c.role.includes('neutral'));

                  return (
                    <Stack spacing={1}>
                      {sortedCoreColors.map((color) => {
                        const colorIndex = colors.findIndex(c => c === color);
                        return (
                          <Box key={colorIndex} sx={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: 1,
                            p: 1,
                            backgroundColor: `${color.hex}08`,
                            border: `1px solid ${color.hex}20`,
                            borderRadius: 1,
                          }}>
                            <Box
                              sx={{
                                width: 16,
                                height: 16,
                                backgroundColor: color.hex,
                                borderRadius: 1,
                                flexShrink: 0,
                              }}
                            />
                            <Typography variant="caption" sx={{ 
                              minWidth: 60,
                              fontWeight: 500,
                              fontSize: '0.7rem'
                            }}>
                              {COLOR_ROLES[color.role as keyof typeof COLOR_ROLES]?.label || color.role}
                            </Typography>
                            <Box sx={{ flex: 1, mx: 1 }}>
                              {(() => {
                                // Calculate if this slider should be disabled
                                const lockedColors = coreColors.filter(c => c.isLocked);
                                const unlockedColors = coreColors.filter(c => !c.isLocked);
                                const otherLockedColors = coreColors.filter(c => c.isLocked && c !== color);
                                const otherLockedTotal = otherLockedColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
                                
                                // Auto-lock logic: if N-1 colors are locked, the last one should be auto-locked
                                const isLastUnlocked = !color.isLocked && unlockedColors.length === 1 && lockedColors.length > 0;
                                const isDisabledByLocks = otherLockedTotal >= 0.99; // 99% threshold for floating point precision
                                const isDisabled = color.isLocked || isDisabledByLocks || isLastUnlocked;
                                const maxAllowedValue = color.isLocked ? (color.ratio || 0) * 100 : Math.max(1, (1 - otherLockedTotal) * 100);
                                
                                return (
                                  <Slider
                                    value={color.ratio ? Math.round(color.ratio * 100) : 20}
                                    onChange={(_, value) => {
                                      if (isDisabled) return;
                                      
                                      // Real-time adjustment - only update the active color, no normalization
                                      const newColors = [...colors];
                                      newColors[colorIndex] = { 
                                        ...color, 
                                        ratio: (value as number) / 100,
                                        isCustomRatio: true
                                      };
                                      
                                      // Just update without normalization to prevent flickering
                                      onChange(newColors);
                                    }}
                                    onChangeCommitted={(_, value) => {
                                      if (isDisabled) return;
                                      
                                      // Final adjustment with smart normalization
                                      const newColors = [...colors];
                                      newColors[colorIndex] = { 
                                        ...color, 
                                        ratio: (value as number) / 100,
                                        isCustomRatio: true
                                      };
                                      
                                      const finalColors = smartNormalizeRatios(newColors, colorIndex);
                                      const totalRatio = finalColors.filter(c => !c.role.includes('neutral'))
                                        .reduce((sum, c) => sum + (c.ratio || 0), 0);
                                      
                                      // Visual ratio updates provide sufficient feedback
                                      
                                      onChange(finalColors);
                                    }}
                                    min={1}
                                    max={Math.min(95, Math.round(maxAllowedValue))}
                                    step={1}
                                    size="small"
                                    disabled={isDisabled}
                                    sx={{
                                      color: color.hex,
                                      height: 6,
                                      opacity: isDisabled ? 0.4 : 1,
                                  '& .MuiSlider-thumb': {
                                    width: 16,
                                    height: 16,
                                    backgroundColor: color.hex,
                                    border: `2px solid ${theme.palette.background.paper}`,
                                    boxShadow: `0 2px 8px ${color.hex}60`,
                                    '&:hover': {
                                      boxShadow: `0 4px 12px ${color.hex}80`,
                                      transform: 'scale(1.1)',
                                    },
                                    '&.Mui-active': {
                                      boxShadow: `0 4px 16px ${color.hex}90`,
                                      transform: 'scale(1.2)',
                                    },
                                  },
                                  '& .MuiSlider-track': {
                                    backgroundColor: color.hex,
                                    border: 'none',
                                    height: 6,
                                    borderRadius: 3,
                                  },
                                  '& .MuiSlider-rail': {
                                    backgroundColor: `${color.hex}20`,
                                    height: 6,
                                    borderRadius: 3,
                                  }
                                }}
                              />
                                );
                              })()}
                              {(() => {
                                // Show tooltip for disabled sliders
                                const lockedColors = coreColors.filter(c => c.isLocked);
                                const unlockedColors = coreColors.filter(c => !c.isLocked);
                                const otherLockedColors = coreColors.filter(c => c.isLocked && c !== color);
                                const otherLockedTotal = otherLockedColors.reduce((sum, c) => sum + (c.ratio || 0), 0);
                                const isDisabledByLocks = otherLockedTotal >= 0.99;
                                const isLastUnlocked = !color.isLocked && unlockedColors.length === 1 && lockedColors.length > 0;
                                
                                if (isLastUnlocked) {
                                  return (
                                    <Tooltip title="Auto-locked: Last unlocked color maintains 100% total" placement="top">
                                      <InfoIcon sx={{ fontSize: 14, color: 'info.main', ml: 0.5 }} />
                                    </Tooltip>
                                  );
                                } else if (isDisabledByLocks && !color.isLocked) {
                                  return (
                                    <Tooltip title="Slider disabled: Other locked colors total 100%" placement="top">
                                      <Box sx={{ 
                                        position: 'absolute',
                                        right: 0,
                                        top: -2,
                                        width: 16,
                                        height: 16,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        backgroundColor: 'warning.main',
                                        borderRadius: '50%',
                                        fontSize: '0.6rem',
                                        color: 'white',
                                        fontWeight: 'bold'
                                      }}>
                                        !
                                      </Box>
                                    </Tooltip>
                                  );
                                }
                                return null;
                              })()}
                            </Box>
                            <Typography variant="caption" sx={{ 
                              minWidth: 28,
                              fontWeight: 600,
                              fontSize: '0.7rem',
                              textAlign: 'center'
                            }}>
                              {color.ratio ? `${Math.round(color.ratio * 100)}%` : '20%'}
                            </Typography>
                            
                            <Tooltip title={color.isLocked ? "Unlock ratio (will be affected by normalization)" : "Lock ratio (protected from normalization)"}>
                              <IconButton
                                size="small"
                                onClick={() => {
                                  const newColors = [...colors];
                                  newColors[colorIndex] = { 
                                    ...color, 
                                    isLocked: !color.isLocked 
                                  };
                                  onChange(newColors);
                                  toast(color.isLocked ? 'Ratio unlocked' : 'Ratio locked', {
                                    icon: color.isLocked ? '🔓' : '🔒',
                                    duration: 1500
                                  });
                                }}
                                sx={{ 
                                  width: 20,
                                  height: 20,
                                  ml: 0.5,
                                  color: color.isLocked ? color.hex : 'text.secondary',
                                  backgroundColor: color.isLocked ? `${color.hex}20` : 'transparent',
                                  '&:hover': {
                                    color: color.hex,
                                    backgroundColor: `${color.hex}20`,
                                  }
                                }}
                              >
                                {color.isLocked ? <LockIcon sx={{ fontSize: 12 }} /> : <LockOpenIcon sx={{ fontSize: 12 }} />}
                              </IconButton>
                            </Tooltip>
                          </Box>
                        );
                      })}
                      
                      {statusData.coreColors.some(c => c.ratio) && (
                          <>
                            {/* Enhanced Status Display */}
                            <Card sx={{ 
                              mt: 1.5,
                              p: 1.5,
                              background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
                              border: `1px solid ${theme.palette.divider}30`,
                              borderRadius: 2,
                            }}>
                              {(() => {
                                const { coreColors, coreTotal, hasCustomRatios, lockedCount, totalDiff, statusColor, statusIcon, statusText } = statusData;
                                
                                return (
                                <>
                                  {/* Status Header */}
                                  <Box sx={{ 
                                    display: 'flex', 
                                    justifyContent: 'space-between', 
                                    alignItems: 'center',
                                    mb: 1
                                  }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                      <Chip
                                        size="small"
                                        icon={hasCustomRatios ? <TuneIcon /> : <AutoFixHighIcon />}
                                        label={hasCustomRatios ? 'Manual' : 'Auto (60-30-10)'}
                                        color={hasCustomRatios ? 'secondary' : 'primary'}
                                        variant="filled"
                                        sx={{ 
                                          fontSize: '0.65rem',
                                          height: 22,
                                          '& .MuiChip-icon': { fontSize: 12 }
                                        }}
                                      />
                                      {lockedCount > 0 && (
                                        <Chip
                                          size="small"
                                          icon={<LockIcon />}
                                          label={`${lockedCount} Locked`}
                                          color="default"
                                          variant="outlined"
                                          sx={{ 
                                            fontSize: '0.6rem',
                                            height: 20,
                                            '& .MuiChip-icon': { fontSize: 10 }
                                          }}
                                        />
                                      )}
                                    </Box>
                                    
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                      <Typography variant="caption" sx={{ 
                                        color: statusColor,
                                        fontWeight: 600,
                                        fontSize: '0.65rem'
                                      }}>
                                        {statusIcon} {statusText}
                                      </Typography>
                                    </Box>
                                  </Box>
                                  
                                  {/* Progress Bar */}
                                  <Box sx={{ mb: 1 }}>
                                    <LinearProgress
                                      variant="determinate"
                                      value={Math.min(100, coreTotal * 100)}
                                      sx={{
                                        height: 8,
                                        borderRadius: 4,
                                        backgroundColor: `${theme.palette.grey[300]}30`,
                                        '& .MuiLinearProgress-bar': {
                                          borderRadius: 4,
                                          backgroundColor: statusColor,
                                          background: coreTotal > 1 
                                            ? `linear-gradient(90deg, ${statusColor}, ${theme.palette.error.main})`
                                            : statusColor,
                                        },
                                      }}
                                    />
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>
                                        Core Colors: {Math.round(coreTotal * 100)}%
                                      </Typography>
                                      {neutralColors.length > 0 && (
                                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.6rem' }}>
                                          +{neutralColors.length} neutral{neutralColors.length > 1 ? 's' : ''}
                                        </Typography>
                                      )}
                                    </Box>
                                  </Box>
                                  
                                  {/* Action Button */}
                                  <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                                    {hasCustomRatios ? (
                                      // Manual Mode: Show only Reset button
                                      <Button
                                          startIcon={<RestoreIcon />}
                                          onClick={() => {
                                            // Reset and return to auto mode
                                            const autoColors = calculateIntelligentRatios(colors.map(c => ({
                                              ...c,
                                              isCustomRatio: false,
                                              isLocked: false
                                            })));
                                            onChange(autoColors);
                                            toast.success('Reset to Auto Mode', {
                                              icon: '🎯',
                                              duration: 1500
                                            });
                                          }}
                                          size="small"
                                          variant="outlined"
                                          color="secondary"
                                          sx={{ 
                                            fontSize: '0.65rem',
                                            textTransform: 'none',
                                            borderRadius: 1.5,
                                            px: 2
                                          }}
                                        >
                                          Reset
                                        </Button>
                                    ) : (
                                      // Auto Mode: Show Switch to Manual button  
                                      <Button
                                        startIcon={<TuneIcon />}
                                        onClick={() => {
                                          // Switch to manual mode
                                          const manualColors = colors.map(c => ({
                                            ...c,
                                            isCustomRatio: !c.role.includes('neutral')
                                          }));
                                          onChange(manualColors);
                                          // Visual mode change provides sufficient feedback
                                        }}
                                        size="small"
                                        variant="outlined"
                                        sx={{ 
                                          fontSize: '0.65rem',
                                          textTransform: 'none',
                                          borderRadius: 1.5,
                                          px: 2
                                        }}
                                      >
                                        Switch to Manual
                                      </Button>
                                    )}
                                  </Box>
                                </>
                              );
                            })()}
                          </Card>
                        </>
                      )}
                    </Stack>
                  );
                })()}
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Collapse>

      {/* Tier 3: AI Helpers - Compact */}
      <Collapse in={showAdvanced}>
        <Card sx={{ 
          mb: 1.5,
          borderRadius: 2,
          background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
          border: `1px solid ${theme.palette.divider}`,
        }}>
          <CardContent sx={{ p: 1.5 }}>
            <Box display="flex" alignItems="center" gap={1} mb={1.5}>
              <PsychologyIcon color="primary" sx={{ fontSize: 16 }} />
              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main', fontSize: '0.85rem' }}>
                AI Helpers
              </Typography>
            </Box>
            
            <Stack spacing={1.5}>
              {/* Extract from Logo - Compact */}
              <Box sx={{ 
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                p: 1.5,
                backgroundColor: `${theme.palette.warning.main}08`,
                border: `1px solid ${theme.palette.warning.main}20`,
                borderRadius: 1.5,
              }}>
                <Box display="flex" alignItems="center" gap={1}>
                  <PaletteIcon color="warning" sx={{ fontSize: 16 }} />
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', fontSize: '0.75rem' }}>
                      Logo Colors
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>
                      Extract from uploaded logo
                    </Typography>
                  </Box>
                </Box>
                <Button
                  variant={logoFile ? "contained" : "outlined"}
                  disabled={!logoFile}
                  onClick={() => handleExtractColorsFromLogo()}
                  size="small"
                  sx={{ 
                    borderRadius: 1.5,
                    textTransform: 'none',
                    fontWeight: 600,
                    px: 1.5,
                    py: 0.5,
                    fontSize: '0.7rem',
                    minWidth: 'auto',
                    ...(logoFile && {
                      background: `linear-gradient(135deg, ${theme.palette.warning.main} 0%, ${theme.palette.warning.dark} 100%)`,
                    })
                  }}
                >
                  Extract
                </Button>
              </Box>



              {/* Accessibility Checker - Ultra Compact */}
              <Box sx={{ 
                p: 1.5,
                backgroundColor: `${theme.palette.info.main}08`,
                border: `1px solid ${theme.palette.info.main}20`,
                borderRadius: 1.5,
              }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <CheckCircleIcon color="info" sx={{ fontSize: 16 }} />
                  <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.75rem' }}>
                    Accessibility
                  </Typography>
                </Box>
                
                {colors.length >= 2 ? (
                  <Box>
                    {(() => {
                      // Compute accessibility stats
                      const stats = {
                        excellent: accessibilityPairs.filter(p => p.status === 'excellent').length,
                        good: accessibilityPairs.filter(p => p.status === 'good').length,
                        warning: accessibilityPairs.filter(p => p.status === 'warning').length,
                        fail: accessibilityPairs.filter(p => p.status === 'fail').length,
                      };
                      
                      // Get problematic pairs (sorted by worst ratio first)
                      const problematicPairs = accessibilityPairs
                        .filter(p => p.status === 'warning' || p.status === 'fail')
                        .sort((a, b) => a.ratio - b.ratio)  // Sort by ratio ascending (worst first)
                        .slice(0, 7);  // Limit display
                      
                      return (
                        <>
                          {/* Summary Bar */}
                          <Box sx={{ mb: 1, display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                            <Chip label={`🌟 ${stats.excellent}`} color="success" size="small" />
                            <Chip label={`✓ ${stats.good}`} color="info" size="small" />
                            <Chip label={`⚠ ${stats.warning}`} color="warning" size="small" />
                            <Chip label={`✗ ${stats.fail}`} color="error" size="small" />
                          </Box>
                          
                          {/* Show only problematic pairs */}
                          {problematicPairs.length > 0 && (
                            <>
                              <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 600 }}>
                                Issues:
                              </Typography>
                              {problematicPairs.map((pair, index) => {
                      const statusColors = {
                        excellent: theme.palette.success.main,
                        good: theme.palette.info.main,
                        warning: theme.palette.warning.main,
                        fail: theme.palette.error.main
                      };
                      
                      const statusIcons = {
                        excellent: '🌟',
                        good: '✓',
                        warning: '⚠',
                        fail: '✗'
                      };

                      const suggestFix = (pairToFix: typeof pair) => {
                        if (pairToFix.status === 'fail' || pairToFix.status === 'warning') {
                          const { h, s, l } = hexToHsl(pairToFix.color2.hex);
                          const newL = l > 50 ? Math.max(10, l - 20) : Math.min(90, l + 20);
                          const suggestedHex = hslToHex(h, s, newL);
                          
                          const newColors = [...colors];
                          newColors[pairToFix.color2.index] = {
                            ...pairToFix.color2,
                            hex: suggestedHex
                          };
                          onChange(newColors);
                                                                // Visual contrast improvement provides sufficient feedback
                        }
                      };
                        
                      return (
                        <Tooltip
                          key={`${pair.color1.index}-${pair.color2.index}`}
                          title={
                            <Box>
                              <Typography variant="caption" sx={{ fontWeight: 600, display: 'block' }}>
                                {pair.level} Level - {pair.ratio.toFixed(1)}:1
                              </Typography>
                              {pair.recommendation && (
                                <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem', mt: 0.5 }}>
                                  💡 {pair.recommendation}
                                </Typography>
                              )}
                              {pair.harmonyIssue && (
                                <>
                                  <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem', mt: 0.5 }}>
                                    🎨 {pair.harmonyIssue}
                                  </Typography>
                                  <Button
                                    size="small"
                                    variant="outlined"
                                    sx={{ 
                                      fontSize: '0.55rem',
                                      mt: 0.5,
                                      py: 0.25,
                                      px: 0.75,
                                      minWidth: 'auto'
                                    }}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      const alternatives = generateAnalogousAlternatives(pair.color2.hex);
                                      suggestHarmonyFix(pair.color2, pair.color2.index);
                                    }}
                                  >
                                    Fix Harmony
                                  </Button>
                                </>
                              )}
                              {(pair.status === 'fail' || pair.status === 'warning') && (
                                <Typography variant="caption" sx={{ display: 'block', fontSize: '0.6rem', mt: 0.5 }}>
                                  Click to auto-fix
                                </Typography>
                              )}
                            </Box>
                          }
                          placement="top"
                          arrow
                        >
                          <Box 
                            sx={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'space-between',
                              p: 0.5,
                              mb: 0.5,
                              backgroundColor: `${statusColors[pair.status]}08`,
                              borderRadius: 1,
                              cursor: (pair.status === 'fail' || pair.status === 'warning') ? 'pointer' : 'default',
                              '&:hover': (pair.status === 'fail' || pair.status === 'warning') ? {
                                backgroundColor: `${statusColors[pair.status]}15`,
                              } : {}
                            }}
                            onClick={() => suggestFix(pair)}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <Box
                                sx={{
                                  width: 12,
                                  height: 12,
                                  backgroundColor: pair.color1.hex,
                                  borderRadius: 0.5,
                                }}
                              />
                              <Box
                                sx={{
                                  width: 12,
                                  height: 12,
                                  backgroundColor: pair.color2.hex,
                                  borderRadius: 0.5,
                                }}
                              />
                              <Typography variant="caption" sx={{ fontSize: '0.65rem', ml: 0.5 }}>
                                {COLOR_ROLES[pair.color1.role as keyof typeof COLOR_ROLES]?.label?.slice(0, 3) || pair.color1.role.slice(0, 3)} vs{' '}
                                {COLOR_ROLES[pair.color2.role as keyof typeof COLOR_ROLES]?.label?.slice(0, 3) || pair.color2.role.slice(0, 3)}
                              </Typography>
                            </Box>
                            <Typography variant="caption" sx={{ 
                              fontWeight: 600,
                              fontSize: '0.65rem',
                              color: statusColors[pair.status],
                            }}>
                              {pair.ratio.toFixed(1)}:1 {statusIcons[pair.status]}
                            </Typography>
                          </Box>
                        </Tooltip>
                      );
                    })}
                              
                              {/* Show More and Bulk Fix buttons */}
                              <Box sx={{ mt: 1, display: 'flex', gap: 1, justifyContent: 'center' }}>
                                {accessibilityPairs.filter(p => p.status !== 'excellent').length > 7 && (
                                  <Button 
                                    size="small" 
                                    variant="outlined"
                                    sx={{ fontSize: '0.65rem', py: 0.25, px: 1 }}
                                    onClick={() => {
                                      // Could implement show more functionality
                                      toast('All pairs shown in accordion below', { icon: 'ℹ️' });
                                    }}
                                  >
                                    Show More
                                  </Button>
                                )}
                                {problematicPairs.length > 0 && (
                                  <Button 
                                    size="small" 
                                    variant="outlined" 
                                    color="warning"
                                    sx={{ fontSize: '0.65rem', py: 0.25, px: 1 }}
                                    onClick={() => {
                                      // Bulk fix worst 3-5 pairs
                                      const pairsToFix = problematicPairs.slice(0, Math.min(5, problematicPairs.length));
                                      const newColors = [...colors];
                                      let fixCount = 0;
                                      
                                      pairsToFix.forEach(pair => {
                                        if (pair.status === 'fail' || pair.status === 'warning') {
                                          const { h, s, l } = hexToHsl(pair.color2.hex);
                                          const newL = l > 50 ? Math.max(10, l - 20) : Math.min(90, l + 20);
                                          const suggestedHex = hslToHex(h, s, newL);
                                          
                                          if (pair.color2.index < newColors.length) {
                                            newColors[pair.color2.index] = {
                                              ...pair.color2,
                                              hex: suggestedHex
                                            };
                                            fixCount++;
                                          }
                                        }
                                      });
                                      
                                      if (fixCount > 0) {
                                        onChange(newColors);
                                        toast.success(`Fixed ${fixCount} accessibility issues`);
                                      }
                                    }}
                                  >
                                    Fix All Warnings
                                  </Button>
                                )}
                              </Box>
                            </>
                          )}
                          
                          {/* Accordion for all pairs */}
                          <Accordion sx={{ mt: 1 }}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Typography variant="caption">
                                All Pairs ({accessibilityPairs.length})
                              </Typography>
                            </AccordionSummary>
                            <AccordionDetails>
                              <Box sx={{ maxHeight: 200, overflowY: 'auto' }}>
                                {accessibilityPairs.map((pair, index) => {
                                  const statusColors = {
                                    excellent: theme.palette.success.main,
                                    good: theme.palette.info.main,
                                    warning: theme.palette.warning.main,
                                    fail: theme.palette.error.main
                                  };
                                  
                                  const statusIcons = {
                                    excellent: '🌟',
                                    good: '✓',
                                    warning: '⚠',
                                    fail: '✗'
                                  };

                                  return (
                                    <Box 
                                      key={`all-${pair.color1.index}-${pair.color2.index}`}
                                      sx={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        justifyContent: 'space-between',
                                        p: 0.5,
                                        mb: 0.5,
                                        backgroundColor: `${statusColors[pair.status]}08`,
                                        borderRadius: 1,
                                      }}
                                    >
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <Box
                                          sx={{
                                            width: 12,
                                            height: 12,
                                            backgroundColor: pair.color1.hex,
                                            borderRadius: 0.5,
                                          }}
                                        />
                                        <Box
                                          sx={{
                                            width: 12,
                                            height: 12,
                                            backgroundColor: pair.color2.hex,
                                            borderRadius: 0.5,
                                          }}
                                        />
                                        <Typography variant="caption" sx={{ fontSize: '0.65rem', ml: 0.5 }}>
                                          {COLOR_ROLES[pair.color1.role as keyof typeof COLOR_ROLES]?.label?.slice(0, 3) || pair.color1.role.slice(0, 3)} vs{' '}
                                          {COLOR_ROLES[pair.color2.role as keyof typeof COLOR_ROLES]?.label?.slice(0, 3) || pair.color2.role.slice(0, 3)}
                                        </Typography>
                                      </Box>
                                      <Typography variant="caption" sx={{ 
                                        fontWeight: 600,
                                        fontSize: '0.65rem',
                                        color: statusColors[pair.status],
                                      }}>
                                        {pair.ratio.toFixed(1)}:1 {statusIcons[pair.status]}
                                      </Typography>
                                    </Box>
                                  );
                                })}
                              </Box>
                            </AccordionDetails>
                          </Accordion>
                        </>
                      );
                    })()}
                  </Box>
                ) : (
                  <Typography variant="caption" color="text.secondary" sx={{ 
                    fontSize: '0.7rem',
                    display: 'block',
                    textAlign: 'center',
                    py: 0.5
                  }}>
                    Add 2+ colors to check
                  </Typography>
                )}
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Collapse>

      {/* Advanced Settings Toggle - Compact Design */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1.5 }}>
        <Button
          onClick={() => setShowAdvanced(!showAdvanced)}
          startIcon={showAdvanced ? <ExpandMoreIcon sx={{ transform: 'rotate(180deg)', fontSize: 16 }} /> : <AutoFixHighIcon sx={{ fontSize: 16 }} />}
          variant={showAdvanced ? "contained" : "outlined"}
          size="small"
          sx={{ 
            borderRadius: 2,
            textTransform: 'none',
            fontWeight: 600,
            px: 2,
            py: 0.75,
            fontSize: '0.8rem',
            transition: 'all 0.2s ease',
            ...(showAdvanced ? {
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
              '&:hover': {
                background: `linear-gradient(135deg, ${theme.palette.secondary.main} 0%, ${theme.palette.primary.main} 100%)`,
              }
            } : {
              borderColor: theme.palette.primary.main,
              color: theme.palette.primary.main,
              backgroundColor: `${theme.palette.primary.main}05`,
              '&:hover': {
                backgroundColor: `${theme.palette.primary.main}10`,
              }
            })
          }}
        >
          {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
        </Button>
      </Box>

      <ColorPickerDialog
        open={colorPickerDialog.open}
        onClose={handleCloseColorPicker}
        onSave={handleSaveColor}
        initialColor={colorPickerDialog.initialColor}
        title={colorPickerDialog.mode === 'add' ? 'Add Color' : 'Edit Color'}
        availableRoles={getAvailableRoles()}
      />

      {/* Palette Size Warning Dialog */}
      <Dialog
        open={showPaletteSizeWarning}
        onClose={() => setShowPaletteSizeWarning(false)}
        maxWidth="sm"
        fullWidth
        TransitionComponent={Grow}
        TransitionProps={{
          timeout: 300
        }}
        PaperProps={{
          sx: {
            borderRadius: 2,
            background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
          }
        }}
      >
        <DialogTitle sx={{ pb: 1, px: 2, py: 1.5 }}>
          <Box display="flex" alignItems="center" gap={1}>
            <WarningIcon color="warning" sx={{ fontSize: 20 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
              Palette Size Recommendation
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ px: 2, py: 1 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Palettes with more than 5 colors may dilute brand focus and reduce visual cohesion. 
              Consider simplifying your palette for better design restraint.
            </Typography>
          </Alert>
          <Typography variant="body2" color="text.secondary">
            Current palette size: {colors.length} colors
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button
            onClick={() => setShowPaletteSizeWarning(false)}
            variant="outlined"
            size="small"
          >
            Review Palette
          </Button>
          <Button
            onClick={handleProceedWithAddColor}
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
          >
            Proceed Anyway
          </Button>
        </DialogActions>
      </Dialog>

      {/* Loading Backdrop */}
      <Backdrop
        sx={{ 
          color: '#fff', 
          zIndex: (theme) => theme.zIndex.drawer + 1,
          flexDirection: 'column',
          gap: 2
        }}
        open={isLoading}
      >
        <CircularProgress color="inherit" />
        <Typography variant="body2" sx={{ textAlign: 'center' }}>
          {loadingMessage}
        </Typography>
      </Backdrop>

      {/* Color Preview Modal */}
      <Dialog
        open={previewModal.open}
        onClose={() => setPreviewModal({ ...previewModal, open: false })}
        maxWidth="md"
        fullWidth
        TransitionComponent={Grow}
        TransitionProps={{
          timeout: 500
        }}
        PaperProps={{
          sx: {
            borderRadius: 2,
            background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${theme.palette.background.default} 100%)`,
          }
        }}
      >
        <DialogTitle sx={{ pb: 1, px: 2, py: 1.5 }}>
          <Box display="flex" alignItems="center" gap={1}>
            <PaletteIcon color="primary" sx={{ fontSize: 20 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
              {previewModal.title}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ px: 2, py: 1 }}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Select colors to add to your palette:
            </Typography>
            
            <Box sx={{ 
              display: 'grid', 
              gridTemplateColumns: isMobile 
                ? 'repeat(auto-fit, minmax(80px, 1fr))' 
                : isTablet 
                  ? 'repeat(auto-fit, minmax(100px, 1fr))'
                  : 'repeat(auto-fit, minmax(120px, 1fr))', 
              gap: isMobile ? 1 : 1.5 
            }}>
              {previewModal.colors.map((color, index) => {
                const selected = selectedColors[index] || false;
                
                return (
                  <Grow
                    key={index}
                    in={previewModal.open}
                    timeout={300 + (index * 100)}
                    style={{ transformOrigin: 'center center' }}
                  >
                    <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      p: 1,
                      borderRadius: 1.5,
                      border: `1px solid ${theme.palette.divider}`,
                      backgroundColor: selected ? `${color.hex}10` : 'transparent',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      '&:hover': {
                        backgroundColor: `${color.hex}15`,
                      }
                    }}
                    onClick={() => {
                      const newSelected = [...selectedColors];
                      newSelected[index] = !selected;
                      setSelectedColors(newSelected);
                    }}
                  >
                    <Box
                      sx={{
                        width: 60,
                        height: 40,
                        backgroundColor: color.hex,
                        borderRadius: 1,
                        mb: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        position: 'relative'
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: getContrastColor(color.hex),
                          fontFamily: 'monospace',
                          fontSize: '0.6rem',
                          fontWeight: 600
                        }}
                      >
                        {color.hex.slice(1).toUpperCase()}
                      </Typography>
                      
                      <Checkbox
                        checked={selected}
                        sx={{
                          position: 'absolute',
                          top: -8,
                          right: -8,
                          backgroundColor: 'rgba(255,255,255,0.9)',
                          borderRadius: '50%',
                          p: 0.25,
                          '& .MuiSvgIcon-root': {
                            fontSize: 14
                          }
                        }}
                      />
                    </Box>
                    
                    <Typography variant="caption" sx={{ 
                      fontWeight: 600, 
                      textAlign: 'center',
                      fontSize: '0.7rem' 
                    }}>
                      {COLOR_ROLES[color.role as keyof typeof COLOR_ROLES]?.label || color.role}
                    </Typography>
                    
                    {color.label && (
                      <Typography variant="caption" sx={{ 
                        color: 'text.secondary',
                        textAlign: 'center',
                        fontSize: '0.65rem' 
                      }}>
                        {color.label}
                      </Typography>
                    )}
                  </Box>
                  </Grow>
                );
              })}
            </Box>
          </Box>
          
          {/* Preview of selected colors */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" sx={{ fontWeight: 600, display: 'block', mb: 1 }}>
              Preview with current palette:
            </Typography>
            <Box sx={{ 
              display: 'flex', 
              height: 24,
              borderRadius: 1,
              overflow: 'hidden',
              border: `1px solid ${theme.palette.divider}`,
            }}>
              {[...colors, ...previewModal.colors.filter((_, index) => selectedColors[index])].map((color, index) => (
                <Box
                  key={index}
                  sx={{
                    flex: 1,
                    backgroundColor: color.hex,
                    opacity: index >= colors.length ? 0.7 : 1
                  }}
                />
              ))}
            </Box>
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button
            onClick={() => setPreviewModal({ ...previewModal, open: false })}
            variant="outlined"
            size="small"
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              // Add only selected colors
              const selectedColorsList = previewModal.colors.filter((_, index) => selectedColors[index]);
              const availableSlots = maxColors - colors.length;
              const colorsToAdd = selectedColorsList.slice(0, availableSlots);
              
              if (colorsToAdd.length > 0) {
                onChange([...colors, ...colorsToAdd]);
                toast.success(`Added ${colorsToAdd.length} selected colors to palette`);
                
                if (selectedColorsList.length > colorsToAdd.length) {
                  toast(`${selectedColorsList.length - colorsToAdd.length} colors were trimmed due to palette size limit`, { 
                    icon: 'ℹ️' 
                  });
                }
              } else {
                toast('No colors selected or palette is full', { icon: 'ℹ️' });
              }
              
              setPreviewModal({ ...previewModal, open: false });
              setSelectedColors([]);
            }}
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
          >
            Add Selected
          </Button>
        </DialogActions>
      </Dialog>

      {/* Primary Color Selection Popover */}
      <Popover
        open={Boolean(primarySelection.anchorEl)}
        anchorEl={primarySelection.anchorEl}
        onClose={() => setPrimarySelection({ anchorEl: null, targetRole: '' })}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            p: 2,
            maxWidth: 250,
            borderRadius: 2,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.shadows[8]
          }
        }}
      >
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 600 }}>
          Select Primary Color
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2, fontSize: '0.85rem' }}>
          Choose which primary color to use as the base for generating {primarySelection.targetRole.replace('_', ' ')} suggestions:
        </Typography>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {colors.filter(c => c.role === 'primary').map((primaryColor, index) => (
            <Box
              key={index}
              onClick={async () => {
                // Store the anchor element before clearing the primary selection
                const anchorEl = primarySelection.anchorEl;
                const targetRole = primarySelection.targetRole;
                setPrimarySelection({ anchorEl: null, targetRole: '' });
                
                if (anchorEl) {
                  await fetchSuggestions(primaryColor, targetRole, anchorEl, 0);
                }
              }}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
                p: 1,
                borderRadius: 1,
                cursor: 'pointer',
                transition: 'background-color 0.2s ease',
                '&:hover': {
                  bgcolor: 'action.hover'
                }
              }}
            >
              <Box
                sx={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  bgcolor: primaryColor.hex,
                  border: `2px solid ${theme.palette.divider}`,
                  flexShrink: 0
                }}
              />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.85rem' }}>
                  {primaryColor.label || 'Primary Color'}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                  {primaryColor.hex.toUpperCase()}
                </Typography>
              </Box>
            </Box>
          ))}
        </Box>
      </Popover>

      {/* Color Suggestions Popover */}
      <Popover
        open={Boolean(suggestions.anchorEl && suggestions.options.length > 0)}
        anchorEl={suggestions.anchorEl}
        disablePortal={false}
        onClose={() => setSuggestions({ anchorEl: null, role: '', options: [], offset: 0 })}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            p: 2,
            width: 280, // Fixed width instead of maxWidth
            borderRadius: 2,
            border: `1px solid ${theme.palette.divider}`,
            boxShadow: theme.shadows[8]
          }
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            {suggestions.role.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} Suggestions
          </Typography>
          <IconButton
            size="small"
            onClick={() => setSuggestions({ anchorEl: null, role: '', options: [], offset: 0 })}
            sx={{
              width: 24,
              height: 24,
              color: 'text.secondary',
              '&:hover': {
                color: 'text.primary',
                backgroundColor: 'action.hover'
              }
            }}
          >
            <CloseIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>
        <Box sx={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(2, minmax(120px, 1fr))', // Minimum column width
          gap: 1,
          width: '100%' // Ensure full width usage
        }}>
          {suggestions.options.map((suggestion, index) => (
            <Box
              key={index}
              onClick={() => {
                // Check suggestion mode
                if (suggestionMode.mode === 'replace' && suggestionMode.targetIndex !== undefined) {
                  // Replace existing color
                  const newColors = [...colors];
                  newColors[suggestionMode.targetIndex] = {
                    ...suggestion,
                    role: suggestions.role,
                    ratio: suggestion.ratio || undefined // Convert null to undefined
                  };
                  onChange(newColors);
                  
                  // Reset suggestion mode
                  setSuggestionMode({ mode: 'add' });
                } else {
                  // Add new color (existing behavior)
                  setColorPickerDialog({
                    open: false,
                    mode: 'add'
                  });
                  
                  handleSaveColor({
                    ...suggestion,
                    role: suggestions.role,
                    ratio: suggestion.ratio || undefined // Convert null to undefined
                  });
                }
                
                setSuggestions({ anchorEl: null, role: '', options: [], offset: 0 });
              }}
              sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                p: 1,
                height: 90, // Fixed height for consistency
                borderRadius: 1.5,
                cursor: 'pointer',
                border: `1px solid ${theme.palette.divider}`,
                transition: 'all 0.2s ease',
                '&:hover': {
                  borderColor: theme.palette.primary.main,
                  backgroundColor: `${theme.palette.primary.main}08`,
                  transform: 'translateY(-1px)',
                  boxShadow: theme.shadows[2]
                }
              }}
            >
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  backgroundColor: suggestion.hex,
                  borderRadius: 1,
                  mb: 0.5,
                  border: `1px solid ${theme.palette.divider}`,
                  boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)'
                }}
              />
              <Typography variant="caption" sx={{ 
                fontSize: '0.65rem',
                textAlign: 'center',
                fontWeight: 500,
                color: 'text.secondary',
                width: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                px: 0.5 // Small padding to prevent text from touching edges
              }}>
                {suggestion.label}
              </Typography>
              <Typography variant="caption" sx={{ 
                fontSize: '0.6rem',
                color: 'text.disabled',
                fontFamily: 'monospace',
                width: '100%',
                textAlign: 'center',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {suggestion.hex.toUpperCase()}
              </Typography>
            </Box>
          ))}
        </Box>
        <Typography variant="caption" sx={{ 
          display: 'block',
          mt: 1,
          color: 'text.secondary',
          fontSize: '0.7rem',
          textAlign: 'center',
          fontStyle: 'italic'
        }}>
          Click any color to add it to your palette
        </Typography>
        
        {/* More ideas button */}
        <Box sx={{ mt: 1.5, display: 'flex', justifyContent: 'center' }}>
          <Button
            size="small"
            variant="outlined"
            disabled={loadingMoreSuggestions}
            startIcon={loadingMoreSuggestions ? <CircularProgress size={14} /> : null}
            onClick={async () => {
              const newOffset = suggestions.offset + 1;
              const primaryColors = colors.filter(c => c.role === 'primary');
              if (primaryColors.length > 0 && suggestions.anchorEl) {
                setLoadingMoreSuggestions(true);
                // Update suggestions in place without closing the popover
                try {
                  const formData = new FormData();
                  formData.append('base_color', primaryColors[0].hex);
                  formData.append('target_role', suggestions.role);
                  formData.append('offset', newOffset.toString());

                  const response = await apiCallWithRetry(() =>
                    fetch('/api/v1/brand-kit/color-harmonies', {
                      method: 'POST',
                      body: formData,
                    })
                  );

                  const data = await response.json();
                  
                  if (data.success && data.curated_suggestions && data.curated_suggestions.length > 0) {
                    // Filter suggestions without closing popover
                    let newSuggestions = data.curated_suggestions.filter((c: BrandColor) => 
                      !colors.some(existingColor => areColorsSimilar(c.hex, existingColor.hex))
                    );
                    
                    // Apply fallback logic if needed
                    if (newSuggestions.length < 2 && data.curated_suggestions.length >= 2) {
                      newSuggestions = data.curated_suggestions.filter((c: BrandColor) => 
                        !colors.some(existingColor => areColorsSimilar(c.hex, existingColor.hex, 15))
                      );
                    }
                    
                    if (newSuggestions.length < 2 && data.curated_suggestions.length >= 2) {
                      newSuggestions = data.curated_suggestions.slice(0, 4);
                    }

                    // Update suggestions smoothly without closing
                    setSuggestions(prev => ({
                      ...prev,
                      options: newSuggestions,
                      offset: newOffset
                    }));
                  }
                } catch (error) {
                  console.error('Error getting more suggestions:', error);
                  toast.error('Failed to get more suggestions');
                } finally {
                  setLoadingMoreSuggestions(false);
                }
              }
            }}
            sx={{
              fontSize: '0.7rem',
              textTransform: 'none',
              borderRadius: 1.5
            }}
          >
            ✨ More ideas
          </Button>
        </Box>
      </Popover>
    </Box>
  );
}