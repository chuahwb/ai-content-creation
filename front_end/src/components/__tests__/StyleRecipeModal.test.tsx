import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import StyleRecipeModal from '../StyleRecipeModal';
import { PipelineAPI } from '@/lib/api';
import { BrandPresetResponse } from '@/types/api';

// Mock the API module
jest.mock('@/lib/api');
const mockedPipelineAPI = PipelineAPI as jest.Mocked<typeof PipelineAPI>;

// Mock child components that are not relevant to the test
jest.mock('../ColorPaletteEditor', () => () => <div data-testid="color-palette-editor" />);
jest.mock('../LogoUploader', () => () => <div data-testid="logo-uploader" />);
jest.mock('../CompactLogoDisplay', () => () => <div data-testid="compact-logo-display" />);

const mockPreset: BrandPresetResponse = {
  id: 'preset-123',
  name: 'Test Preset',
  preset_type: 'STYLE_RECIPE',
  version: 1,
  model_id: 'dall-e-3',
  pipeline_version: '1.0',
  usage_count: 5,
  created_at: new Date().toISOString(),
  style_recipe: {
    recipe_data: {
      visual_concept: {},
      strategy: {},
      style_guidance: {},
    },
    render_text: true,
    apply_branding: true,
    source_platform: 'Instagram Story/Reel (9:16 Vertical)',
    language: 'fr',
  },
  brand_kit: {
    colors: ['#ff0000', '#00ff00'],
    brand_voice_description: 'Test voice',
    logo_file_base64: 'dGVzdGxvZ28=',
  },
};

describe('StyleRecipeModal', () => {
  const handleClose = jest.fn();
  const handleRunStarted = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders and pre-populates correctly with preset data', () => {
    render(
      <StyleRecipeModal
        open={true}
        onClose={handleClose}
        onRunStarted={handleRunStarted}
        preset={mockPreset}
      />
    );

    // Check title
    expect(screen.getByText('Adapt Style Recipe')).toBeInTheDocument();
    expect(screen.getByText('Using Style Recipe: "Test Preset"')).toBeInTheDocument();

    // Check switches are pre-populated
    expect(screen.getByLabelText('Render Text on Image')).toBeChecked();
    expect(screen.getByLabelText('Apply Brand Kit')).toBeChecked();

    // Check platform is selected
    expect(screen.getByLabelText('Output Platform')).toHaveTextContent('Instagram Story/Reel (9:16 Vertical)');
    
    // Check language is selected
    expect(screen.getByLabelText('Output Language')).toHaveTextContent('Other...');

    // Check Brand Kit editor is visible
    expect(screen.getByText('Brand Kit')).toBeVisible();
    expect(screen.getByTestId('color-palette-editor')).toBeInTheDocument();
  });

  it('shows and uses reset chip when a setting is overridden', () => {
    render(
      <StyleRecipeModal
        open={true}
        onClose={handleClose}
        onRunStarted={handleRunStarted}
        preset={mockPreset}
      />
    );
    
    const renderTextSwitch = screen.getByLabelText('Render Text on Image');
    expect(renderTextSwitch).toBeChecked();
    
    // Override the setting
    fireEvent.click(renderTextSwitch);
    expect(renderTextSwitch).not.toBeChecked();

    // Check that reset chip appears
    const resetChip = screen.getByText('Reset');
    expect(resetChip).toBeInTheDocument();

    // Click reset and verify the value is restored
    fireEvent.click(resetChip);
    expect(renderTextSwitch).toBeChecked();
  });

  it('toggles Brand Kit editor visibility', () => {
    render(
      <StyleRecipeModal
        open={true}
        onClose={handleClose}
        onRunStarted={handleRunStarted}
        preset={mockPreset}
      />
    );

    const applyBrandingSwitch = screen.getByLabelText('Apply Brand Kit');
    expect(screen.getByText('Brand Kit')).toBeVisible();

    // Turn off branding
    fireEvent.click(applyBrandingSwitch);
    expect(screen.queryByText('Brand Kit')).not.toBeInTheDocument();

    // Turn it back on
    fireEvent.click(applyBrandingSwitch);
    expect(screen.getByText('Brand Kit')).toBeVisible();
  });

  it('submits the form with correct overridden data', async () => {
    mockedPipelineAPI.submitRun.mockResolvedValueOnce({ id: 'new-run-456' } as any);

    render(
      <StyleRecipeModal
        open={true}
        onClose={handleClose}
        onRunStarted={handleRunStarted}
        preset={mockPreset}
      />
    );

    // 1. Override some settings
    fireEvent.click(screen.getByLabelText('Render Text on Image')); // Set to false
    fireEvent.change(screen.getByLabelText('Additional Instructions (Optional)'), {
      target: { value: 'New instructions' },
    });

    // 2. Upload a file
    const file = new File(['dummy content'], 'test.jpg', { type: 'image/jpeg' });
    const fileUploadInput = screen.getByLabelText('Drop image here or click to browse').querySelector('input');
    fireEvent.drop(fileUploadInput!, { dataTransfer: { files: [file] } });

    // 3. Submit the form
    await waitFor(() => {
      fireEvent.click(screen.getByText('Run Style Adaptation'));
    });

    // 4. Assert API was called with correct data
    await waitFor(() => {
        expect(mockedPipelineAPI.submitRun).toHaveBeenCalledTimes(1);
    });

    const submittedData = mockedPipelineAPI.submitRun.mock.calls[0][0];
    
    expect(submittedData.render_text).toBe(false); // Overridden value
    expect(submittedData.apply_branding).toBe(true); // Original value
    expect(submittedData.language).toBe('fr'); // Original value
    expect(submittedData.adaptation_prompt).toBe('New instructions');
    expect(submittedData.brand_kit?.brand_voice_description).toBe('Test voice');
  });
}); 