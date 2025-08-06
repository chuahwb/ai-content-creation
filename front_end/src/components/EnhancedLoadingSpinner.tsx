import React from 'react';
import { Box, CircularProgress, Typography, Paper } from '@mui/material';

interface EnhancedLoadingSpinnerProps {
  message?: string;
  size?: number;
  showPaper?: boolean;
}

const EnhancedLoadingSpinner: React.FC<EnhancedLoadingSpinnerProps> = ({
  message = "Loading...",
  size = 40,
  showPaper = true
}) => {
  const content = (
    <Box 
      sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        gap: 2,
        p: showPaper ? 4 : 2
      }}
    >
      <CircularProgress size={size} thickness={4} />
      <Typography variant="body1" color="text.secondary" textAlign="center">
        {message}
      </Typography>
    </Box>
  );

  return showPaper ? (
    <Paper elevation={1} sx={{ m: 2 }}>
      {content}
    </Paper>
  ) : content;
};

export default EnhancedLoadingSpinner;