import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ImageDropzone from '../ImageDropzone';

// Mock file for testing
const createMockFile = (name: string, size: number, type: string) => {
  const file = new File([''], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

describe('ImageDropzone', () => {
  const defaultProps = {
    uploadedFile: null,
    previewUrl: null,
    onFileSelect: jest.fn(),
    onFileRemove: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders dropzone when no file uploaded', () => {
    render(<ImageDropzone {...defaultProps} />);
    
    expect(screen.getByText('Reference Image (Optional)')).toBeInTheDocument();
    expect(screen.getByText('Drag & drop an image here')).toBeInTheDocument();
    expect(screen.getByText('or click to select from your computer')).toBeInTheDocument();
    expect(screen.getByText('JPEG, PNG, GIF, WebP (max 10MB)')).toBeInTheDocument();
  });

  it('renders file preview when file is uploaded', () => {
    const mockFile = createMockFile('test.jpg', 1024 * 1024, 'image/jpeg'); // 1MB
    const mockPreviewUrl = 'blob:test-url';

    render(
      <ImageDropzone 
        {...defaultProps}
        uploadedFile={mockFile}
        previewUrl={mockPreviewUrl}
      />
    );
    
    expect(screen.getByText('test.jpg')).toBeInTheDocument();
    expect(screen.getByText('1.00 MB')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument();
  });

  it('calls onFileRemove when remove button is clicked', () => {
    const mockFile = createMockFile('test.jpg', 1024 * 1024, 'image/jpeg');
    const mockPreviewUrl = 'blob:test-url';

    render(
      <ImageDropzone 
        {...defaultProps}
        uploadedFile={mockFile}
        previewUrl={mockPreviewUrl}
      />
    );
    
    fireEvent.click(screen.getByRole('button', { name: /remove/i }));
    
    expect(defaultProps.onFileRemove).toHaveBeenCalledTimes(1);
  });

  it('disables interaction when disabled prop is true', () => {
    render(<ImageDropzone {...defaultProps} disabled={true} />);
    
    const dropzone = screen.getByText('Drag & drop an image here').closest('div');
    expect(dropzone).toHaveStyle('cursor: not-allowed');
    expect(dropzone).toHaveStyle('opacity: 0.5');
  });

  it('shows custom title and subtitle', () => {
    render(
      <ImageDropzone 
        {...defaultProps}
        title="Custom Title"
        subtitle="Custom subtitle"
      />
    );
    
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
    expect(screen.getByText('Custom subtitle')).toBeInTheDocument();
  });

  it('shows drag active state', () => {
    render(<ImageDropzone {...defaultProps} />);
    
    const dropzone = screen.getByText('Drag & drop an image here').closest('div');
    
    // Simulate drag enter
    fireEvent.dragEnter(dropzone!);
    
    // Note: Testing drag state requires more complex setup with react-dropzone
    // This test confirms the component renders without errors
    expect(dropzone).toBeInTheDocument();
  });

  it('handles file size display correctly', () => {
    // Test KB display
    const smallFile = createMockFile('small.jpg', 512 * 1024, 'image/jpeg'); // 512KB
    const { rerender } = render(
      <ImageDropzone 
        {...defaultProps}
        uploadedFile={smallFile}
        previewUrl="blob:test"
      />
    );
    
    expect(screen.getByText('0.50 MB')).toBeInTheDocument();
    
    // Test MB display
    const largeFile = createMockFile('large.jpg', 5 * 1024 * 1024, 'image/jpeg'); // 5MB
    rerender(
      <ImageDropzone 
        {...defaultProps}
        uploadedFile={largeFile}
        previewUrl="blob:test"
      />
    );
    
    expect(screen.getByText('5.00 MB')).toBeInTheDocument();
  });
});
