// Centralized tooltip strings and configuration for consistent UX

export const TOOLTIP_CONFIG = {
  placement: 'top' as const,
  arrow: true,
  enterDelay: 300,
  leaveDelay: 0,
  maxWidth: 280,
};

// Consistent info icon styling
export const INFO_ICON_STYLE = {
  fontSize: '1rem',
  color: 'text.secondary',
  opacity: 0.7,
  '&:hover': {
    opacity: 1,
    color: 'primary.main'
  }
} as const;

export const TOOLTIP_STRINGS = {
  // Switches and toggles
  applyBranding: 'Apply your brand colors, voice, and logo to maintain visual consistency',
  renderText: 'Add text overlays to your images with professional typography',
  
  // Sliders and controls
  creativityLevel: {
    1: 'Focused & Photorealistic: Clean, product-focused imagery with realistic details',
    2: 'Impressionistic & Stylized: Artistic interpretation with enhanced visual appeal',
    3: 'Abstract & Illustrative: Creative, artistic representation with bold stylization'
  },
  variants: 'Number of different creative approaches to generate (1-6 options)',
  
  // Language and platform
  language: 'Controls the language used in text overlays and generated captions',
  platform: 'Target social media platform determines optimal image dimensions and style',
  
  // Template actions
  saveTemplate: 'Save current form settings as a reusable template',
  saveTemplateDisabled: 'Complete required fields (platform + brief or image) to save template',
  
  // Brand kit actions
  loadKit: 'Load a previously saved brand kit with colors, voice, and logo',
  saveKit: 'Save current brand kit (colors, voice, logo) for future use',
  saveKitDisabled: 'Add brand colors, voice description, or logo to save a brand kit',
  editColors: 'Open advanced color palette editor with harmony suggestions',
  
  // Form actions
  generate: 'Start creating your visual content with current settings',
  generateDisabled: 'Provide a creative brief or upload an image to begin',
  reset: 'Clear all form data and return to default settings',
} as const;