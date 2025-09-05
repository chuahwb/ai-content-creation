import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import TemplateGallery from '../TemplateGallery';

describe('TemplateGallery', () => {
  const mockOnTaskTypeSelect = jest.fn();

  beforeEach(() => {
    mockOnTaskTypeSelect.mockClear();
  });

  it('renders all template options', () => {
    render(
      <TemplateGallery
        selectedTaskType=""
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Check that template options are rendered
    expect(screen.getByText('Product Photography')).toBeInTheDocument();
    expect(screen.getByText('Promotional Graphics')).toBeInTheDocument();
    expect(screen.getByText('Store Atmosphere')).toBeInTheDocument();
    expect(screen.getByText('Menu Spotlights')).toBeInTheDocument();
    expect(screen.getByText('Cultural Content')).toBeInTheDocument();
    expect(screen.getByText('Recipes & Tips')).toBeInTheDocument();
    expect(screen.getByText('Brand Story')).toBeInTheDocument();
    expect(screen.getByText('Behind the Scenes')).toBeInTheDocument();
  });

  it('shows selected state for chosen template', () => {
    render(
      <TemplateGallery
        selectedTaskType="1. Product Photography"
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Check that selected template shows "Selected" chip
    expect(screen.getByText('Selected')).toBeInTheDocument();
  });

  it('calls onTaskTypeSelect when template is clicked', () => {
    render(
      <TemplateGallery
        selectedTaskType=""
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Click on a template
    fireEvent.click(screen.getByText('Product Photography'));
    
    expect(mockOnTaskTypeSelect).toHaveBeenCalledWith('1. Product Photography');
  });

  it('deselects template when clicking on already selected template', () => {
    render(
      <TemplateGallery
        selectedTaskType="1. Product Photography"
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Click on the already selected template
    fireEvent.click(screen.getByText('Product Photography'));
    
    expect(mockOnTaskTypeSelect).toHaveBeenCalledWith('');
  });

  it('disables interaction when disabled prop is true', () => {
    render(
      <TemplateGallery
        selectedTaskType=""
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={true}
      />
    );

    // Try to click on a template
    fireEvent.click(screen.getByText('Product Photography'));
    
    // Should not call the callback when disabled
    expect(mockOnTaskTypeSelect).not.toHaveBeenCalled();
  });

  it('renders template descriptions', () => {
    render(
      <TemplateGallery
        selectedTaskType=""
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Check that descriptions are rendered
    expect(screen.getByText('Showcase products with professional styling')).toBeInTheDocument();
    expect(screen.getByText('Eye-catching announcements and offers')).toBeInTheDocument();
  });

  it('renders template emojis', () => {
    render(
      <TemplateGallery
        selectedTaskType=""
        onTaskTypeSelect={mockOnTaskTypeSelect}
        disabled={false}
      />
    );

    // Check that emojis are rendered (they should be in the document)
    expect(screen.getByText('📸')).toBeInTheDocument();
    expect(screen.getByText('📢')).toBeInTheDocument();
  });
});
