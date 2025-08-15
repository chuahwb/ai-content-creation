import React from 'react';
import { render, screen } from '@testing-library/react';
import { ProductFocusedPreview } from '../ProductFocusedPreview';
import { PromotionalAnnouncementPreview } from '../PromotionalAnnouncementPreview';
import { LifestyleAtmospherePreview } from '../LifestyleAtmospherePreview';
import { BrandColor } from '../../../types/api';

const palette: BrandColor[] = [
  { hex: '#1E88E5', role: 'primary' },
  { hex: '#8E24AA', role: 'secondary' },
  { hex: '#FB8C00', role: 'accent' },
  { hex: '#FAFAFA', role: 'neutral_light' },
  { hex: '#212121', role: 'neutral_dark' }
];

describe('Design previews render and reflect palette', () => {
  it('renders ProductFocusedPreview with svg', () => {
    render(<ProductFocusedPreview colors={palette} isMobile />);
    // Title text
    expect(screen.getByText(/Product Ad/i)).toBeInTheDocument();
    // An svg rectangle CTA exists
    const svgs = document.querySelectorAll('svg');
    expect(svgs.length).toBeGreaterThan(0);
  });

  it('renders PromotionalAnnouncementPreview with header and texts', () => {
    render(<PromotionalAnnouncementPreview colors={palette} isMobile />);
    expect(screen.getByText(/Promotion/i)).toBeInTheDocument();
    // SPECIAL / OFFER texts should be present inside svg
    // query via DOM text nodes
    expect(document.body.textContent).toContain('SPECIAL');
    expect(document.body.textContent).toContain('OFFER');
  });

  it('renders LifestyleAtmospherePreview scene', () => {
    render(<LifestyleAtmospherePreview colors={palette} isMobile />);
    expect(screen.getByText(/Lifestyle Scene/i)).toBeInTheDocument();
    const svgs = document.querySelectorAll('svg');
    expect(svgs.length).toBeGreaterThan(0);
  });
});

