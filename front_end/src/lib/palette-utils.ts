import { BrandColor } from '../types/api';

export interface PaletteStyles {
  primary: string;
  secondary: string;
  accent: string;
  neutralLight: string;
  neutralDark: string;
  supporting: string[];
}

export const getPaletteStyles = (colors: BrandColor[]): PaletteStyles => {
  const findColor = (role: string) => colors.find(c => c.role === role)?.hex;

  const primaryColors = colors.filter(c => c.role === 'primary');
  const secondaryColors = colors.filter(c => c.role === 'secondary');
  const accentColors = colors.filter(c => c.role === 'accent');

  const mainPrimary = primaryColors[0]?.hex || colors.find(c => !c.role.includes('neutral'))?.hex || '#2196F3';
  const mainSecondary = secondaryColors[0]?.hex || primaryColors[1]?.hex || '#FF9800';
  const mainAccent = accentColors[0]?.hex || secondaryColors[1]?.hex || primaryColors[2]?.hex || '#4CAF50';

  const neutralLight = findColor('neutral_light') || '#FFFFFF';
  const neutralDark = findColor('neutral_dark') || '#333333';

  // Collect all non-neutral colors
  const coreColors = colors.filter(c => !c.role.includes('neutral'));

  // Remove the main colors to get the remaining supporting colors
  const supportingColors = coreColors.filter(
    c => c.hex !== mainPrimary && c.hex !== mainSecondary && c.hex !== mainAccent
  );

  // Sort supporting colors to prioritize primaries, then secondaries, then accents
  supportingColors.sort((a, b) => {
    const rolePriority = (role: string) => {
      if (role === 'primary') return 1;
      if (role === 'secondary') return 2;
      if (role === 'accent') return 3;
      return 4;
    };
    return rolePriority(a.role) - rolePriority(b.role);
  });

  return {
    primary: mainPrimary,
    secondary: mainSecondary,
    accent: mainAccent,
    neutralLight,
    neutralDark,
    supporting: supportingColors.map(c => c.hex),
  };
};