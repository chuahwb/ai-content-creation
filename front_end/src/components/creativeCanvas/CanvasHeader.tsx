'use client';

import * as React from 'react';
import { Box, Typography } from '@mui/material';

function CanvasHeader() {
  return (
    <Box sx={{ mb: 3, textAlign: 'center' }}>
      <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 600, mx: 'auto' }}>
        Describe your idea or add a reference image; refine with lenses when needed.
      </Typography>
    </Box>
  );
}

export default CanvasHeader;
