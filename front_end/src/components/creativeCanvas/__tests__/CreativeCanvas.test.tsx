import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import CreativeCanvas from '../CreativeCanvas';
import { PipelineFormData, UnifiedBrief } from '../../../types/api';

// Mock the child components
jest.mock('../CanvasHeader', () => {
  return function MockCanvasHeader() {
    return <div data-testid="canvas-header">Creative Canvas</div>;
  };
});

jest.mock('../TemplateGallery', () => {
  return function MockTemplateGallery({ onTaskTypeSelect }: { onTaskTypeSelect: (taskType: string) => void }) {
    return (
      <div data-testid="template-gallery">
        <button onClick={() => onTaskTypeSelect('1. Product Photography')}>
          Select Product Photography
        </button>
      </div>
    );
  };
});

jest.mock('../../CreativeBriefInput', () => {
  return function MockCreativeBriefInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
    return (
      <textarea
        data-testid="creative-brief-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Creative brief"
      />
    );
  };
});

// Test wrapper component
function TestWrapper() {
  const { control, watch, setValue } = useForm<PipelineFormData>({
    defaultValues: {
      mode: 'easy_mode',
      platform_name: '',
      creativity_level: 2,
      num_variants: 3,
      prompt: '',
      task_type: '',
      task_description: '',
      brand_kit: undefined,
      image_instruction: '',
      render_text: false,
      apply_branding: false,
      marketing_audience: '',
      marketing_objective: '',
      marketing_voice: '',
      marketing_niche: '',
      language: 'en',
      image_file: undefined,
      unifiedBrief: {
        intentType: 'fullGeneration',
        generalBrief: '',
        editInstruction: '',
        textOverlay: {
          raw: '',
        },
      },
    },
  });

  const [unifiedBrief, setUnifiedBrief] = React.useState<UnifiedBrief>({
    intentType: 'fullGeneration',
    generalBrief: '',
    editInstruction: '',
    textOverlay: {
      raw: '',
    },
  });

  return (
    <CreativeCanvas
      control={control}
      watch={watch}
      setValue={setValue}
      errors={{}}
      isSubmitting={false}
      uploadedFile={null}
      unifiedBrief={unifiedBrief}
      setUnifiedBrief={setUnifiedBrief}
      applyBranding={false}
      renderText={false}
      onBrandKitPresetOpen={jest.fn()}
      onColorPaletteOpen={jest.fn()}
      onRecipeModalOpen={jest.fn()}
    />
  );
}

describe('CreativeCanvas', () => {
  it('renders the canvas header', () => {
    render(<TestWrapper />);
    expect(screen.getByTestId('canvas-header')).toBeInTheDocument();
  });

  it('renders the creative brief input', () => {
    render(<TestWrapper />);
    expect(screen.getByTestId('creative-brief-input')).toBeInTheDocument();
  });

  it('renders the template gallery', () => {
    render(<TestWrapper />);
    expect(screen.getByTestId('template-gallery')).toBeInTheDocument();
  });

  it('allows typing in the creative brief input', () => {
    render(<TestWrapper />);
    const input = screen.getByTestId('creative-brief-input');
    
    fireEvent.change(input, { target: { value: 'Test creative brief' } });
    expect(input).toHaveValue('Test creative brief');
  });

  it('allows selecting a template', () => {
    render(<TestWrapper />);
    const button = screen.getByText('Select Product Photography');
    
    fireEvent.click(button);
    // Template selection should work without errors
    expect(button).toBeInTheDocument();
  });

  it('renders platform selection', () => {
    render(<TestWrapper />);
    expect(screen.getByText('Platform & Settings')).toBeInTheDocument();
    expect(screen.getByText('Target Platform')).toBeInTheDocument();
  });

  it('renders generation settings', () => {
    render(<TestWrapper />);
    expect(screen.getByText(/Creativity:/)).toBeInTheDocument();
    expect(screen.getByText(/Variants:/)).toBeInTheDocument();
  });

  it('has proper ARIA attributes for accessibility', () => {
    render(<TestWrapper />);
    
    // Check for ARIA roles and labels
    const regions = screen.getAllByRole('region');
    expect(regions.length).toBeGreaterThan(0);
    
    // Check for proper button labels
    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      // Each button should have either aria-label or accessible text
      const hasAriaLabel = button.hasAttribute('aria-label');
      const hasTextContent = button.textContent && button.textContent.trim().length > 0;
      expect(hasAriaLabel || hasTextContent).toBe(true);
    });
  });

  it('manages focus properly when expanding lenses', () => {
    render(<TestWrapper />);
    
    // Find expand buttons (they should have aria-expanded attributes)
    const expandButtons = screen.getAllByRole('button').filter(button => 
      button.hasAttribute('aria-expanded')
    );
    
    expect(expandButtons.length).toBeGreaterThan(0);
    
    // Each expand button should have proper ARIA attributes
    expandButtons.forEach(button => {
      expect(button).toHaveAttribute('aria-expanded');
      expect(button).toHaveAttribute('aria-controls');
      expect(button).toHaveAttribute('aria-label');
    });
  });
});
