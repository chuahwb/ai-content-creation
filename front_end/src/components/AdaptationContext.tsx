import React from 'react';
import { Paper, Typography, Grid, Box, Chip } from '@mui/material';
import { AutoAwesome as AutoAwesomeIcon, Image as ImageIcon } from '@mui/icons-material';
import { PipelineRunDetail } from '@/types/api';
import ImageWithAuth from './ImageWithAuth';

interface AdaptationContextProps {
  run: PipelineRunDetail;
}

const AdaptationContext: React.FC<AdaptationContextProps> = ({ run }) => {
  if (!run.parent_preset) {
    return null;
  }

  // For style adaptations, the subject image is typically the uploaded image
  const subjectImagePath = run.base_image_url || (run.has_image_reference ? `input_${run.image_filename}` : null);

  // Calculate stage efficiency for informational note
  const skippedStages = run.stages?.filter(stage => stage.status === 'SKIPPED').length || 0;

  return (
    <Paper sx={{ p: 3, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <AutoAwesomeIcon color="primary" />
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Style Adaptation
        </Typography>
        <Chip 
          label="Recipe Applied" 
          size="small" 
          color="primary" 
          variant="outlined"
          sx={{ fontSize: '0.7rem', fontWeight: 500 }}
        />
      </Box>

      <Grid container spacing={3}>
        {/* Source Style Section */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
            Source Style Recipe
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* Reference Image Thumbnail */}
            {run.parent_preset?.image_url && run.parent_preset?.source_run_id ? (
              <ImageWithAuth
                runId={run.parent_preset.source_run_id}
                imagePath={run.parent_preset.image_url}
                sx={{
                  width: 48,
                  height: 48,
                  objectFit: 'cover',
                  borderRadius: 1,
                  border: 1,
                  borderColor: 'divider'
                }}
                alt={`Reference style: ${run.parent_preset.name}`}
              />
            ) : (
              <Box
                sx={{
                  width: 48,
                  height: 48,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: 'grey.200',
                  borderRadius: 1,
                  border: 1,
                  borderColor: 'divider',
                  color: 'grey.500'
                }}
              >
                <AutoAwesomeIcon fontSize="small" />
              </Box>
            )}
            
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {run.parent_preset.name}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                Style Recipe Template
              </Typography>
            </Box>
          </Box>
        </Grid>

        {/* New Inputs Section */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
            Adaptation Inputs
          </Typography>
          <Grid container spacing={2}>
            {/* Subject Image */}
            <Grid item xs={12} sm={6}>
              <Typography variant="caption" color="textSecondary">Subject Image</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 1 }}>
                {subjectImagePath ? (
                  <ImageWithAuth
                    runId={run.id}
                    imagePath={subjectImagePath}
                    sx={{
                      width: 48,
                      height: 48,
                      objectFit: 'cover',
                      borderRadius: 1,
                      border: 1,
                      borderColor: 'divider'
                    }}
                    alt="Subject image for adaptation"
                  />
                ) : (
                  <Box
                    sx={{
                      width: 48,
                      height: 48,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backgroundColor: 'grey.200',
                      borderRadius: 1,
                      border: 1,
                      borderColor: 'divider',
                      color: 'grey.500'
                    }}
                  >
                    <ImageIcon fontSize="small" />
                  </Box>
                )}
                
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {subjectImagePath ? 'New Subject' : 'No Image'}
                  </Typography>
                  <Typography variant="caption" color="textSecondary">
                    {subjectImagePath ? 'Uploaded for adaptation' : 'Not provided'}
                  </Typography>
                </Box>
              </Box>
            </Grid>

            {/* Prompt Override */}
            <Grid item xs={12} sm={6}>
              <Typography variant="caption" color="textSecondary">Prompt Override</Typography>
              <Box sx={{ mt: 1 }}>
                {run.adaptation_prompt ? (
                  <Paper sx={{ 
                    p: 2, 
                    backgroundColor: 'grey.50', 
                    border: 1, 
                    borderColor: 'divider', 
                    borderRadius: 1 
                  }}>
                    <Typography variant="body2" sx={{ 
                      whiteSpace: 'pre-wrap', 
                      fontSize: '0.9rem',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden'
                    }}>
                      {run.adaptation_prompt}
                    </Typography>
                  </Paper>
                ) : (
                  <Box sx={{ 
                    p: 2, 
                    backgroundColor: 'grey.50', 
                    border: 1, 
                    borderColor: 'divider', 
                    borderRadius: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minHeight: 56
                  }}>
                    <Typography variant="body2" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                      No custom prompt provided
                    </Typography>
                  </Box>
                )}
              </Box>
            </Grid>
          </Grid>
        </Grid>

        {/* Efficiency Note */}
        {skippedStages > 0 && (
          <Grid item xs={12}>
            <Box sx={{ p: 1.5, backgroundColor: 'primary.50', borderRadius: 1, border: 1, borderColor: 'primary.200' }}>
              <Typography variant="caption" color="primary.main" sx={{ fontWeight: 500 }}>
                <AutoAwesomeIcon sx={{ fontSize: '0.9rem', mr: 0.5, verticalAlign: 'middle' }} />
                Optimized Execution: {skippedStages} stages skipped by reusing saved recipe data
              </Typography>
            </Box>
          </Grid>
        )}
      </Grid>
    </Paper>
  );
};

export default AdaptationContext; 