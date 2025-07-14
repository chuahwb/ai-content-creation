'use client';

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Divider,
  CircularProgress,
  Alert,
  Grid,
  Card,
  CardContent,
  Paper,
} from '@mui/material';
import {
  Close as CloseIcon,
  AutoFixHigh as AutoFixHighIcon,
  Schedule as ScheduleIcon,
  AttachMoney as AttachMoneyIcon,
  Info as InfoIcon,
  Image as ImageIcon,
  Brush as BrushIcon,
  SmartToy as SmartToyIcon,
} from '@mui/icons-material';
import dayjs from 'dayjs';
import duration from 'dayjs/plugin/duration';
import relativeTime from 'dayjs/plugin/relativeTime';

dayjs.extend(duration);
dayjs.extend(relativeTime);

interface RefinementDetailsDialogProps {
  open: boolean;
  onClose: () => void;
  details: any | null;
  loading: boolean;
  jobId: string | null;
}

const RefinementDetailsDialog: React.FC<RefinementDetailsDialogProps> = ({
  open,
  onClose,
  details,
  loading,
  jobId,
}) => {
  const formatDuration = (seconds: number) => {
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    } else {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'success';
      case 'FAILED':
        return 'error';
      case 'RUNNING':
        return 'primary';
      case 'PENDING':
        return 'warning';
      case 'CANCELLED':
        return 'default';
      default:
        return 'default';
    }
  };

  const renderQuickRepairDetails = () => (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <AutoFixHighIcon color="primary" />
        Quick Repair Details
      </Typography>
      
      <Grid container spacing={2}>
        <Grid item xs={12}>
          <Card variant="outlined" sx={{ height: '160px' }}>
            <CardContent sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Typography variant="subtitle1" color="primary" gutterBottom sx={{ fontWeight: 600 }}>
                Process Overview
              </Typography>
              <Typography variant="body2" sx={{ mb: 2, lineHeight: 1.5, color: 'text.secondary', flex: 1 }}>
                {details.description || 'Automatic subject enhancement using original reference image'}
              </Typography>
              
              <Divider sx={{ my: 1 }} />
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 'auto', flexShrink: 0 }}>
                <ImageIcon color={details.reference_image_used ? 'primary' : 'disabled'} fontSize="small" />
                <Typography variant="body2">
                  <strong>Reference Image:</strong> {details.reference_image_used 
                    ? `${details.reference_image_filename || 'Original reference image'}` 
                    : 'Not available'}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  const renderCustomEnhancementDetails = () => (
    <Box>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <SmartToyIcon color="secondary" />
        Custom Enhancement Details
      </Typography>
      
      <Grid container spacing={2}>
        {/* Prompts Section */}
        <Grid item xs={12}>
          <Card variant="outlined" sx={{ height: '280px' }}>
            <CardContent sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column' }}>
              <Typography variant="subtitle1" color="secondary" gutterBottom sx={{ fontWeight: 600, flexShrink: 0 }}>
                Prompts & Instructions
              </Typography>
              
              {/* Prompts Container - side by side layout */}
              <Box sx={{ 
                height: '180px', 
                display: 'flex', 
                flexDirection: 'column',
                mb: 1 
              }}>
                <Grid container spacing={1.5} sx={{ height: '100%' }}>
                  {/* Original Prompt */}
                  <Grid item xs={details.ai_refined_prompt ? 6 : 12} sx={{ height: '100%' }}>
                    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                      <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ fontWeight: 500, fontSize: '0.8rem', flexShrink: 0 }}>
                        Your Original Prompt
                      </Typography>
                      <Paper 
                        elevation={0}
                        sx={{ 
                          p: 1.5, 
                          backgroundColor: 'grey.50', 
                          border: '1px solid',
                          borderColor: 'grey.200',
                          borderRadius: 1,
                          fontFamily: 'monospace',
                          fontSize: '0.8rem',
                          lineHeight: 1.4,
                          flex: 1,
                          overflow: 'auto'
                        }}
                      >
                        {details.user_prompt || details.original_prompt || 'No prompt provided'}
                      </Paper>
                    </Box>
                  </Grid>
                  
                  {/* Enhanced Prompt */}
                  {details.ai_refined_prompt && (
                    <Grid item xs={6} sx={{ height: '100%' }}>
                      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                        <Typography variant="subtitle2" color="textSecondary" gutterBottom sx={{ fontWeight: 500, fontSize: '0.8rem', flexShrink: 0 }}>
                          Enhanced Prompt
                        </Typography>
                        <Paper 
                          elevation={0}
                          sx={{ 
                            p: 1.5, 
                            backgroundColor: 'primary.50', 
                            border: '1px solid',
                            borderColor: 'primary.200',
                            borderRadius: 1,
                            fontFamily: 'monospace',
                            fontSize: '0.8rem',
                            lineHeight: 1.4,
                            flex: 1,
                            overflow: 'auto'
                          }}
                        >
                          {details.ai_refined_prompt}
                        </Paper>
                      </Box>
                    </Grid>
                  )}
                </Grid>
              </Box>
              
              <Divider sx={{ flexShrink: 0 }} />
              
              {/* Configuration Section - fixed at bottom */}
              <Box sx={{ flexShrink: 0, pt: 1 }}>
                <Grid container spacing={1}>
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <BrushIcon color={details.mask_used ? 'primary' : 'disabled'} fontSize="small" />
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        <strong>Mode:</strong> {details.mask_used ? 'Regional' : 'Global'}
                      </Typography>
                    </Box>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ImageIcon color={details.reference_image_used ? 'primary' : 'disabled'} fontSize="small" />
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        <strong>Reference:</strong> {details.reference_image_used ? 'Yes' : 'None'}
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  return (
    <Dialog 
      open={open} 
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          height: '650px',
          maxHeight: '650px',
          boxShadow: 3,
          display: 'flex',
          flexDirection: 'column',
        }
      }}
    >
      <DialogTitle sx={{ 
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        py: 2,
        flexShrink: 0
      }}>
        <Box>
          <Typography variant="h6">
            Refinement Details
          </Typography>
          {details && (
            <Typography variant="body2" sx={{ opacity: 0.9 }}>
              {details.refinement_type_display}
            </Typography>
          )}
        </Box>
        <Button
          onClick={onClose}
          sx={{ color: 'white', minWidth: 'auto', p: 1 }}
        >
          <CloseIcon />
        </Button>
      </DialogTitle>

      <DialogContent sx={{ p: 0, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
            <CircularProgress size={48} />
          </Box>
        ) : !details ? (
          <Box sx={{ p: 3, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Alert severity="error">
              Failed to load refinement details. Please try again.
            </Alert>
          </Box>
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Status and Basic Info */}
            <Box sx={{ p: 2.5, backgroundColor: 'grey.50', borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 1.5 }}>
                Overview
              </Typography>
              <Grid container spacing={1.5}>
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1.5, backgroundColor: 'white', borderRadius: 2, boxShadow: 1, height: '72px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <Chip 
                      label={details.status}
                      color={getStatusColor(details.status)}
                      sx={{ mb: 0.5, fontWeight: 600, fontSize: '0.7rem', height: '24px' }}
                      size="small"
                    />
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                      Status
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1.5, backgroundColor: 'white', borderRadius: 2, boxShadow: 1, height: '72px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.5 }}>
                      <AttachMoneyIcon fontSize="small" color="success" />
                      <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.85rem' }}>
                        ${details.cost_usd?.toFixed(4) || '0.0000'}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                      Cost
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1.5, backgroundColor: 'white', borderRadius: 2, boxShadow: 1, height: '72px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.5 }}>
                      <ScheduleIcon fontSize="small" color="info" />
                      <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.85rem' }}>
                        {details.duration_seconds ? formatDuration(details.duration_seconds) : 'N/A'}
                      </Typography>
                    </Box>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                      Duration
                    </Typography>
                  </Box>
                </Grid>
                
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1.5, backgroundColor: 'white', borderRadius: 2, boxShadow: 1, height: '72px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <Typography variant="body2" fontWeight="bold" sx={{ mb: 0.5, fontSize: '0.85rem' }}>
                      {details.created_at ? dayjs(details.created_at).format('MMM D, HH:mm') : 'N/A'}
                    </Typography>
                    <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 500, fontSize: '0.75rem' }}>
                      Created
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Box>

            {/* Type-specific Details */}
            <Box sx={{ p: 2.5, flex: 1, overflow: 'hidden' }}>
              {details.refinement_type === 'subject' && renderQuickRepairDetails()}
              {details.refinement_type === 'prompt' && renderCustomEnhancementDetails()}
            
              {/* Fallback for unknown refinement types or missing metadata */}
              {details.refinement_type && !['subject', 'prompt'].includes(details.refinement_type) && (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    <Typography variant="body2">
                      Detailed metadata is not available for this refinement type.
                    </Typography>
                  </Alert>
                  <Typography variant="body2" color="textSecondary">
                    Refinement ID: {details.job_id}
                  </Typography>
                </Box>
              )}
            </Box>

            {/* Error Message */}
            {details.error_message && (
              <Box sx={{ p: 2.5, backgroundColor: 'error.50', borderTop: 1, borderColor: 'divider', flexShrink: 0 }}>
                <Alert severity="error" sx={{ boxShadow: 1 }}>
                  <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600 }}>
                    Error Details
                  </Typography>
                  <Typography variant="body2">
                    {details.error_message}
                  </Typography>
                </Alert>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 2.5, py: 1.5, borderTop: 1, borderColor: 'divider', backgroundColor: 'grey.50', flexShrink: 0 }}>
        <Button 
          onClick={onClose} 
          variant="contained" 
          size="medium"
          sx={{ 
            minWidth: 100,
            fontWeight: 600,
            borderRadius: 2
          }}
        >
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default RefinementDetailsDialog; 