// Platform options for social media targeting
export const PLATFORMS = [
  'Instagram Post (1:1 Square)',
  'Instagram Story/Reel (9:16 Vertical)',
  'Facebook Post (Mixed)',
  'Pinterest Pin (2:3 Vertical)',
  'Xiaohongshu (Red Note) (3:4 Vertical)',
];

// Task types for template selection
export const TASK_TYPES = [
  '1. Product Photography',
  '2. Promotional Graphics & Announcements',
  '3. Store Atmosphere & Decor',
  '4. Menu Spotlights',
  '5. Cultural & Community Content',
  '6. Recipes & Food Tips',
  '7. Brand Story & Milestones',
  '8. Behind the Scenes Imagery',
];

// Creativity level labels
export const CREATIVITY_LABELS = {
  1: 'Focused & Photorealistic',
  2: 'Impressionistic & Stylized',
  3: 'Abstract & Illustrative',
} as const;

// Common ISO-639-1 language codes for validation
export const VALID_LANGUAGE_CODES = [
  'en', 'zh', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'pt', 'ru', 
  'ar', 'hi', 'th', 'vi', 'nl', 'sv', 'no', 'da', 'fi', 'pl',
  'tr', 'he', 'cs', 'hu', 'ro', 'bg', 'hr', 'sk', 'sl', 'et',
  'lv', 'lt', 'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'is', 'fo'
];

// Template gallery options with visual metadata
export const TEMPLATE_OPTIONS = [
  {
    id: '1. Product Photography',
    title: 'Product Photography',
    description: 'Showcase products with professional styling',
    emoji: '📸',
    color: '#FF6B6B'
  },
  {
    id: '2. Promotional Graphics & Announcements',
    title: 'Promotional Graphics',
    description: 'Eye-catching announcements and offers',
    emoji: '📢',
    color: '#4ECDC4'
  },
  {
    id: '3. Store Atmosphere & Decor',
    title: 'Store Atmosphere',
    description: 'Capture your space and ambiance',
    emoji: '🏪',
    color: '#45B7D1'
  },
  {
    id: '4. Menu Spotlights',
    title: 'Menu Spotlights',
    description: 'Highlight signature dishes and specials',
    emoji: '🍽️',
    color: '#F9CA24'
  },
  {
    id: '5. Cultural & Community Content',
    title: 'Cultural Content',
    description: 'Celebrate community and traditions',
    emoji: '🎉',
    color: '#A55EEA'
  },
  {
    id: '6. Recipes & Food Tips',
    title: 'Recipes & Tips',
    description: 'Share culinary knowledge and techniques',
    emoji: '👨‍🍳',
    color: '#26D0CE'
  },
  {
    id: '7. Brand Story & Milestones',
    title: 'Brand Story',
    description: 'Tell your journey and achievements',
    emoji: '📖',
    color: '#FD79A8'
  },
  {
    id: '8. Behind the Scenes Imagery',
    title: 'Behind the Scenes',
    description: 'Show the people and process behind your brand',
    emoji: '🎬',
    color: '#6C5CE7'
  }
];
