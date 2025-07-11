import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';
import { PipelineAPI } from '@/lib/api';

interface ImageWithAuthProps {
  runId: string;
  imagePath: string;
  sx?: React.CSSProperties | object;
  onClick?: () => void;
  alt?: string;
}

const ImageWithAuth: React.FC<ImageWithAuthProps> = ({ 
  runId, 
  imagePath, 
  sx, 
  onClick, 
  alt = 'Generated image' 
}) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    const loadImage = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const url = await PipelineAPI.getImageBlobUrl(runId, imagePath);
        if (isMounted) {
          setBlobUrl(url);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const errorMessage = err instanceof Error ? err.message : 'Failed to load image';
          setError(errorMessage);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    loadImage();

    return () => {
      isMounted = false;
      // Clean up blob URL when component unmounts
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [runId, imagePath]);

  // Clean up blob URL when component unmounts
  useEffect(() => {
    return () => {
      if (blobUrl) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, []);

  if (loading) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          minHeight: 200,
          backgroundColor: 'grey.50',
          borderRadius: 2,
          ...sx 
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ ...sx }}>
        <Alert severity="error" sx={{ borderRadius: 2 }}>
          Failed to load image: {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      component="img"
      src={blobUrl || undefined}
      alt={alt}
      sx={sx}
      onClick={onClick}
    />
  );
};

export default ImageWithAuth; 