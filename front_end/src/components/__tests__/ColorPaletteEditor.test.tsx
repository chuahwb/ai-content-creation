import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColorPaletteEditor from '../ColorPaletteEditor';

// Mock MUI components that aren't critical for testing
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  Box: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  Chip: ({ label, onDelete, ...props }: any) => (
    <div {...props}>
      <span>{label}</span>
      {onDelete && <button onClick={onDelete}>×</button>}
    </div>
  ),
  IconButton: ({ onClick, children, ...props }: any) => (
    <button onClick={onClick} {...props}>{children}</button>
  ),
  TextField: ({ value, onChange, ...props }: any) => (
    <input 
      value={value} 
      onChange={(e) => onChange?.(e)} 
      {...props}
    />
  ),
  Tooltip: ({ children, title }: any) => (
    <div title={title}>{children}</div>
  )
}));

// Mock icons
jest.mock('@mui/icons-material', () => ({
  Add: () => <span>+</span>,
  Palette: () => <span>🎨</span>
}));

describe('ColorPaletteEditor', () => {
  const mockOnChange = jest.fn();
  
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders with initial colors', () => {
    const initialColors = ['#FF6B35', '#004E89', '#F7931E'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Check that all colors are rendered
    expect(screen.getByText('#FF6B35')).toBeInTheDocument();
    expect(screen.getByText('#004E89')).toBeInTheDocument();
    expect(screen.getByText('#F7931E')).toBeInTheDocument();
  });

  it('renders empty state when no colors provided', () => {
    render(
      <ColorPaletteEditor 
        colors={[]} 
        onChange={mockOnChange} 
      />
    );
    
    expect(screen.getByText('Add Brand Colors')).toBeInTheDocument();
    expect(screen.getByText('No colors added yet')).toBeInTheDocument();
  });

  it('adds new color when add button is clicked', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={['#FF6B35']} 
        onChange={mockOnChange} 
      />
    );
    
    // Click add button
    const addButton = screen.getByRole('button', { name: /add color/i });
    await user.click(addButton);
    
    // Enter new color
    const colorInput = screen.getByRole('textbox');
    await user.clear(colorInput);
    await user.type(colorInput, '#004E89');
    
    // Press Enter or click confirm
    await user.keyboard('{Enter}');
    
    // Verify onChange was called with new color
    expect(mockOnChange).toHaveBeenCalledWith(['#FF6B35', '#004E89']);
  });

  it('removes color when delete button is clicked', async () => {
    const user = userEvent.setup();
    const initialColors = ['#FF6B35', '#004E89', '#F7931E'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Find and click delete button for first color
    const deleteButtons = screen.getAllByText('×');
    await user.click(deleteButtons[0]);
    
    // Verify onChange was called with color removed
    expect(mockOnChange).toHaveBeenCalledWith(['#004E89', '#F7931E']);
  });

  it('validates HEX color format', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={[]} 
        onChange={mockOnChange} 
      />
    );
    
    // Click add button
    const addButton = screen.getByRole('button', { name: /add color/i });
    await user.click(addButton);
    
    // Enter invalid color
    const colorInput = screen.getByRole('textbox');
    await user.type(colorInput, 'invalid-color');
    await user.keyboard('{Enter}');
    
    // Verify error message is shown
    await waitFor(() => {
      expect(screen.getByText(/invalid color format/i)).toBeInTheDocument();
    });
    
    // Verify onChange was not called
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('prevents duplicate colors', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={['#FF6B35']} 
        onChange={mockOnChange} 
      />
    );
    
    // Click add button
    const addButton = screen.getByRole('button', { name: /add color/i });
    await user.click(addButton);
    
    // Enter duplicate color
    const colorInput = screen.getByRole('textbox');
    await user.type(colorInput, '#FF6B35');
    await user.keyboard('{Enter}');
    
    // Verify error message is shown
    await waitFor(() => {
      expect(screen.getByText(/color already exists/i)).toBeInTheDocument();
    });
    
    // Verify onChange was not called
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('handles color editing', async () => {
    const user = userEvent.setup();
    const initialColors = ['#FF6B35', '#004E89'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Click on first color to edit
    const colorChip = screen.getByText('#FF6B35');
    await user.click(colorChip);
    
    // Color picker or input should appear
    await waitFor(() => {
      expect(screen.getByDisplayValue('#FF6B35')).toBeInTheDocument();
    });
    
    // Edit the color
    const colorInput = screen.getByDisplayValue('#FF6B35');
    await user.clear(colorInput);
    await user.type(colorInput, '#00FF00');
    await user.keyboard('{Enter}');
    
    // Verify onChange was called with edited color
    expect(mockOnChange).toHaveBeenCalledWith(['#00FF00', '#004E89']);
  });

  it('displays color previews correctly', () => {
    const initialColors = ['#FF6B35', '#004E89', '#F7931E'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Check that color previews are displayed
    const colorPreviews = screen.getAllByRole('button');
    expect(colorPreviews.length).toBeGreaterThan(0);
    
    // Check that colors are displayed as text
    expect(screen.getByText('#FF6B35')).toBeInTheDocument();
    expect(screen.getByText('#004E89')).toBeInTheDocument();
    expect(screen.getByText('#F7931E')).toBeInTheDocument();
  });

  it('limits maximum number of colors', async () => {
    const user = userEvent.setup();
    const maxColors = Array(10).fill(0).map((_, i) => `#${i.toString(16).padStart(6, '0')}`);
    
    render(
      <ColorPaletteEditor 
        colors={maxColors} 
        onChange={mockOnChange} 
        maxColors={10}
      />
    );
    
    // Try to add another color
    const addButton = screen.getByRole('button', { name: /add color/i });
    await user.click(addButton);
    
    // Verify error message is shown
    await waitFor(() => {
      expect(screen.getByText(/maximum.*colors/i)).toBeInTheDocument();
    });
  });

  it('handles empty color input gracefully', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={[]} 
        onChange={mockOnChange} 
      />
    );
    
    // Click add button
    const addButton = screen.getByRole('button', { name: /add color/i });
    await user.click(addButton);
    
    // Press Enter without typing anything
    await user.keyboard('{Enter}');
    
    // Verify no error and no onChange call
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('supports keyboard navigation', async () => {
    const user = userEvent.setup();
    const initialColors = ['#FF6B35', '#004E89'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Focus on first color chip
    const firstColorChip = screen.getByText('#FF6B35');
    await user.click(firstColorChip);
    
    // Use arrow keys to navigate
    await user.keyboard('{ArrowRight}');
    
    // Verify focus moved to next color
    expect(document.activeElement).toHaveAttribute('data-color', '#004E89');
  });

  it('displays tooltips with color information', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={['#FF6B35']} 
        onChange={mockOnChange} 
      />
    );
    
    // Hover over color chip
    const colorChip = screen.getByText('#FF6B35');
    await user.hover(colorChip);
    
    // Check for tooltip
    await waitFor(() => {
      expect(screen.getByTitle(/click to edit/i)).toBeInTheDocument();
    });
  });

  it('handles color picker integration', async () => {
    const user = userEvent.setup();
    
    render(
      <ColorPaletteEditor 
        colors={['#FF6B35']} 
        onChange={mockOnChange} 
      />
    );
    
    // Click on color to open picker
    const colorChip = screen.getByText('#FF6B35');
    await user.click(colorChip);
    
    // Verify color picker interface appears
    await waitFor(() => {
      expect(screen.getByDisplayValue('#FF6B35')).toBeInTheDocument();
    });
    
    // Test color picker interaction
    const colorInput = screen.getByDisplayValue('#FF6B35');
    await user.clear(colorInput);
    await user.type(colorInput, '#00FF00');
    
    // Confirm color change
    await user.keyboard('{Enter}');
    
    // Verify onChange was called
    expect(mockOnChange).toHaveBeenCalledWith(['#00FF00']);
  });

  it('preserves color order when editing', async () => {
    const user = userEvent.setup();
    const initialColors = ['#FF6B35', '#004E89', '#F7931E'];
    
    render(
      <ColorPaletteEditor 
        colors={initialColors} 
        onChange={mockOnChange} 
      />
    );
    
    // Edit middle color
    const middleColor = screen.getByText('#004E89');
    await user.click(middleColor);
    
    const colorInput = screen.getByDisplayValue('#004E89');
    await user.clear(colorInput);
    await user.type(colorInput, '#00FF00');
    await user.keyboard('{Enter}');
    
    // Verify order is preserved
    expect(mockOnChange).toHaveBeenCalledWith(['#FF6B35', '#00FF00', '#F7931E']);
  });
}); 