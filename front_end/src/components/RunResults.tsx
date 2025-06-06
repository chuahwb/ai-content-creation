'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
  Alert,
  Button,
  Grid,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Skeleton,
  Tooltip,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
  PlayArrow as PlayArrowIcon,
  Stop as StopIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  AccessTime as AccessTimeIcon,
  Close as CloseIcon,
  Fullscreen as FullscreenIcon,
  ContentCopy as ContentCopyIcon,
  ZoomIn as ZoomInIcon,
} from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import dayjs from 'dayjs';
import Confetti from 'react-confetti';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { 
  PipelineRunDetail, 
  StageProgressUpdate,
  RunStatus,
  StageStatus,
  WebSocketMessage,
  GeneratedImageResult,
} from '@/types/api';
import { PipelineAPI, WebSocketManager } from '@/lib/api';
import { statusColors } from '@/lib/theme';

interface RunResultsProps {
  runId: string;
  onNewRun: () => void;
}

interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  stage?: string;
  message: string;
}

export default function RunResults({ runId, onNewRun }: RunResultsProps) {
  const [runDetails, setRunDetails] = useState<PipelineRunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [wsManager, setWsManager] = useState<WebSocketManager | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImageResult[]>([]);

  const addLog = useCallback((level: LogEntry['level'], message: string, stage?: string) => {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      stage,
      message,
    };
    setLogs(prev => [...prev, entry]);
  }, []);

  const fetchRunDetails = useCallback(async () => {
    try {
      setIsLoading(true);
      const details = await PipelineAPI.getRun(runId);
      setRunDetails(details);
      addLog('info', `Loaded run details for ${runId}`);
      
      // Fetch generated images from the results endpoint if the run is completed
      if (details.status === 'COMPLETED') {
        try {
          const results = await PipelineAPI.getResults(runId);
          if (results.generated_images) {
            setGeneratedImages(results.generated_images);
            addLog('info', `Loaded ${results.generated_images.length} generated images`);
          }
        } catch (resultsErr: any) {
          addLog('warning', `Could not load results: ${resultsErr.message}`);
          // Fallback to extracting from stage output data
          const images: GeneratedImageResult[] = [];
          details.stages.forEach(stage => {
            if (stage.output_data && stage.stage_name === 'image_generation') {
              const outputData = stage.output_data as any;
              if (outputData.generated_images) {
                images.push(...outputData.generated_images);
              }
            }
          });
          setGeneratedImages(images);
        }
      } else {
        // For non-completed runs, clear generated images
        setGeneratedImages([]);
      }
      
    } catch (err: any) {
      const errorMsg = err.message || 'Failed to fetch run details';
      setError(errorMsg);
      addLog('error', errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [runId, addLog]);

  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    addLog('info', `WebSocket message: ${message.type}`, message.data.stage_name);
    
    switch (message.type) {
      case 'stage_update':
        const stageUpdate = message.data as StageProgressUpdate;
        addLog(
          stageUpdate.status === 'FAILED' ? 'error' : 
          stageUpdate.status === 'COMPLETED' ? 'success' : 'info',
          `${stageUpdate.stage_name}: ${stageUpdate.message}`,
          stageUpdate.stage_name
        );
        
        // Update run details with new stage info
        setRunDetails(prev => {
          if (!prev) return prev;
          const updatedStages = [...prev.stages];
          const stageIndex = updatedStages.findIndex(s => s.stage_name === stageUpdate.stage_name);
          
          if (stageIndex >= 0) {
            updatedStages[stageIndex] = { ...updatedStages[stageIndex], ...stageUpdate };
          } else {
            updatedStages.push(stageUpdate);
          }
          
          return { ...prev, stages: updatedStages };
        });
        break;
        
      case 'run_complete':
        addLog('success', 'Pipeline run completed successfully! 🎉');
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 5000);
        fetchRunDetails(); // Refresh final details
        break;
        
      case 'run_error':
        addLog('error', `Pipeline run failed: ${message.data.error_message}`);
        fetchRunDetails(); // Refresh to get error details
        break;
    }
  }, [addLog, fetchRunDetails]);

  const initializeWebSocket = useCallback(() => {
    if (wsManager) {
      wsManager.disconnect();
    }

    const newWsManager = new WebSocketManager(
      runId,
      handleWebSocketMessage,
      (error) => {
        addLog('error', 'WebSocket connection error');
        console.error('WebSocket error:', error);
      },
      (event) => {
        if (event.code !== 1000) { // Not a normal closure
          addLog('warning', 'WebSocket connection lost. Attempting to reconnect...');
        }
      }
    );

    newWsManager.connect()
      .then(() => {
        addLog('success', 'Connected to real-time updates');
        setWsManager(newWsManager);
      })
      .catch((error) => {
        addLog('error', 'Failed to connect to real-time updates');
        console.error('WebSocket connection failed:', error);
      });

    return newWsManager;
  }, [runId, handleWebSocketMessage, addLog]);

  const handleCancelRun = async () => {
    try {
      await PipelineAPI.cancelRun(runId);
      addLog('warning', 'Run cancellation requested');
      toast.success('Run cancellation requested');
      fetchRunDetails();
    } catch (err: any) {
      const errorMsg = err.message || 'Failed to cancel run';
      addLog('error', errorMsg);
      toast.error(errorMsg);
    }
  };

  const downloadImage = async (imagePath: string, filename: string) => {
    try {
      const blob = await PipelineAPI.downloadFile(runId, filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      addLog('success', `Downloaded: ${filename}`);
      toast.success(`Downloaded: ${filename}`);
    } catch (err: any) {
      const errorMsg = `Failed to download ${filename}: ${err.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
    }
  };

  const copyRunIdToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(runId);
      toast.success('Run ID copied to clipboard!');
      addLog('info', 'Run ID copied to clipboard');
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = runId;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      toast.success('Run ID copied to clipboard!');
      addLog('info', 'Run ID copied to clipboard');
    }
  };

  const getStatusIcon = (status: RunStatus | StageStatus) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircleIcon color="success" />;
      case 'FAILED':
        return <ErrorIcon color="error" />;
      case 'RUNNING':
        return <PlayArrowIcon color="info" />;
      case 'CANCELLED':
        return <StopIcon color="warning" />;
      default:
        return <AccessTimeIcon color="disabled" />;
    }
  };

  const getProgressValue = () => {
    if (!runDetails?.stages.length) return 0;
    const TOTAL_STAGES = 6; // Fixed total: image_eval, strategy, style_guide, creative_expert, prompt_assembly, image_generation
    const completedStages = runDetails.stages.filter(s => s.status === 'COMPLETED').length;
    return (completedStages / TOTAL_STAGES) * 100;
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  useEffect(() => {
    fetchRunDetails();
    const ws = initializeWebSocket();
    
    return () => {
      if (ws) {
        ws.disconnect();
      }
    };
  }, [runId]);

  if (isLoading) {
    return (
      <Card elevation={1}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <Skeleton variant="circular" width={40} height={40} />
            <Skeleton variant="text" width={300} height={40} />
          </Box>
          <Skeleton variant="rectangular" height={8} sx={{ mb: 2 }} />
          <Grid container spacing={2}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Grid item xs={12} key={i}>
                <Skeleton variant="rectangular" height={60} />
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert severity="error" action={
        <Button color="inherit" size="small" onClick={fetchRunDetails}>
          Retry
        </Button>
      }>
        {error}
      </Alert>
    );
  }

  if (!runDetails) {
    return (
      <Alert severity="warning">
        No run details available
      </Alert>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {showConfetti && (
        <Confetti
          width={window.innerWidth}
          height={window.innerHeight}
          recycle={false}
          numberOfPieces={200}
        />
      )}

      <Card elevation={1}>
        <CardContent sx={{ p: 4 }}>
          {/* Header - Full Width */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {getStatusIcon(runDetails.status)}
              <Typography variant="h4" sx={{ fontWeight: 600, letterSpacing: '-0.02em' }}>
                Pipeline Run
              </Typography>
              <Chip 
                label={runDetails.status.toUpperCase()} 
                color={
                  runDetails.status === 'COMPLETED' ? 'success' :
                  runDetails.status === 'FAILED' ? 'error' :
                  runDetails.status === 'RUNNING' ? 'info' : 'default'
                }
                sx={{ fontWeight: 500 }}
              />
            </Box>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={fetchRunDetails}
                size="small"
                sx={{ fontWeight: 500 }}
              >
                Refresh
              </Button>
              
              {runDetails.status === 'RUNNING' && (
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<StopIcon />}
                  onClick={handleCancelRun}
                  size="small"
                  sx={{ fontWeight: 500 }}
                >
                  Cancel
                </Button>
              )}
              
              <Button
                variant="contained"
                onClick={onNewRun}
                size="small"
                sx={{ fontWeight: 500 }}
              >
                New Run
              </Button>
            </Box>
          </Box>

          {/* Main Content - Left/Right Split */}
          <Grid container spacing={4}>
            {/* LEFT SIDE - Main Results */}
            <Grid item xs={12} lg={8}>
              {/* Generated Images */}
              {generatedImages.length > 0 && (
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h5" gutterBottom sx={{ fontWeight: 600, mb: 3, letterSpacing: '-0.01em' }}>
                    Generated Images
                  </Typography>
                  <Grid container spacing={3}>
                    {generatedImages.map((result, index) => (
                      <Grid item xs={12} sm={6} md={6} key={index}>
                        <Paper sx={{ p: 3, height: '100%', border: 1, borderColor: 'divider' }}>
                          {result.status === 'success' && result.image_path ? (
                            <Box>
                              <Box sx={{ position: 'relative', mb: 2 }}>
                                <Box
                                  component="img"
                                  src={PipelineAPI.getFileUrl(runId, result.image_path)}
                                  sx={{
                                    width: '100%',
                                    maxHeight: 350,
                                    objectFit: 'contain',
                                    borderRadius: 2,
                                    cursor: 'pointer',
                                    border: 1,
                                    borderColor: 'divider',
                                    backgroundColor: 'grey.50',
                                    transition: 'all 0.2s ease-in-out',
                                    '&:hover': {
                                      transform: 'scale(1.02)',
                                      boxShadow: 2,
                                    }
                                  }}
                                  onClick={() => result.image_path && setSelectedImage(PipelineAPI.getFileUrl(runId, result.image_path))}
                                />
                              </Box>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.main' }}>
                                  Strategy {result.strategy_index + 1}
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                  <Tooltip title="View full size">
                                    <Button
                                      size="small"
                                      startIcon={<ZoomInIcon />}
                                      onClick={() => result.image_path && setSelectedImage(PipelineAPI.getFileUrl(runId, result.image_path))}
                                      color="primary"
                                      variant="outlined"
                                      sx={{ fontWeight: 500 }}
                                    >
                                      Enlarge
                                    </Button>
                                  </Tooltip>
                                  <Tooltip title="Download image">
                                    <Button
                                      size="small"
                                      startIcon={<DownloadIcon />}
                                      onClick={() => downloadImage(result.image_path!, result.image_path!)}
                                      color="primary"
                                      variant="contained"
                                      sx={{ fontWeight: 500 }}
                                    >
                                      Download
                                    </Button>
                                  </Tooltip>
                                </Box>
                              </Box>
                            </Box>
                          ) : (
                            <Box sx={{ textAlign: 'center', py: 6 }}>
                              <ErrorIcon color="error" sx={{ fontSize: 64, mb: 2 }} />
                              <Typography variant="h6" color="error" gutterBottom sx={{ fontWeight: 600 }}>
                                Generation Failed
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                {result.error_message || 'Unknown error occurred'}
                              </Typography>
                            </Box>
                          )}
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}

              {/* Progress */}
              <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Pipeline Progress
                  </Typography>
                  <Typography variant="body1" color="textSecondary" sx={{ fontWeight: 500 }}>
                    {runDetails.stages.filter(s => s.status === 'COMPLETED').length} / 6 stages completed
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={getProgressValue()} 
                  sx={{ 
                    height: 12, 
                    borderRadius: 6,
                    backgroundColor: 'grey.200',
                    '& .MuiLinearProgress-bar': {
                      borderRadius: 6,
                    }
                  }}
                />
              </Box>

              {/* Pipeline Stages */}
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Pipeline Stages
              </Typography>
              <Grid container spacing={2}>
                {runDetails.stages.map((stage, index) => (
                  <Grid item xs={12} key={stage.stage_name}>
                    <motion.div
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, delay: index * 0.1 }}
                    >
                      <Paper 
                        sx={{ 
                          p: 3, 
                          border: 1, 
                          borderColor: stage.status === 'RUNNING' ? 'primary.main' : 'divider',
                          backgroundColor: stage.status === 'RUNNING' ? 'primary.50' : 'background.paper',
                          borderRadius: 2,
                        }}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            {getStatusIcon(stage.status)}
                            <Typography variant="subtitle1" sx={{ fontWeight: 600, textTransform: 'capitalize' }}>
                              {stage.stage_name.replace('_', ' ')}
                            </Typography>
                            <Chip 
                              label={stage.status} 
                              size="small"
                              sx={{ 
                                backgroundColor: statusColors[stage.status as keyof typeof statusColors] || '#6b7280',
                                color: 'white',
                                fontWeight: 500 
                              }}
                            />
                          </Box>
                          
                          <Typography variant="body2" color="textSecondary" sx={{ fontWeight: 500 }}>
                            {formatDuration(stage.duration_seconds)}
                          </Typography>
                        </Box>
                        
                        <Typography 
                          variant="body2" 
                          color={stage.message?.includes('⚠️ IMPORTANT') ? 'warning.main' : 'textSecondary'} 
                          sx={{ 
                            mt: 1,
                            fontWeight: stage.message?.includes('⚠️ IMPORTANT') ? 600 : 400,
                            backgroundColor: stage.message?.includes('⚠️ IMPORTANT') ? 'warning.50' : 'transparent',
                            padding: stage.message?.includes('⚠️ IMPORTANT') ? 1 : 0,
                            borderRadius: stage.message?.includes('⚠️ IMPORTANT') ? 1 : 0,
                            border: stage.message?.includes('⚠️ IMPORTANT') ? '1px solid' : 'none',
                            borderColor: stage.message?.includes('⚠️ IMPORTANT') ? 'warning.main' : 'transparent'
                          }}
                        >
                          {stage.message}
                        </Typography>
                        
                        {stage.error_message && (
                          <Alert severity="error" sx={{ mt: 2 }}>
                            {stage.error_message}
                          </Alert>
                        )}
                        
                        {stage.message?.includes('⚠️ IMPORTANT') && (
                          <Alert severity="warning" sx={{ mt: 2 }}>
                            <strong>Image Processing Issue:</strong> Your uploaded image couldn't be analyzed. 
                            Results may be generic instead of tailored to your specific image.
                          </Alert>
                        )}
                      </Paper>
                    </motion.div>
                  </Grid>
                ))}
              </Grid>
            </Grid>

            {/* RIGHT SIDE - Details & Metadata */}
            <Grid item xs={12} lg={4}>
              {/* Run Info Card */}
              <Paper sx={{ p: 3, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                  Run Details
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">Run ID</Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', flexGrow: 1, fontSize: '0.8rem' }}>
                        {runDetails.id}
                      </Typography>
                      <Tooltip title="Copy to clipboard">
                        <IconButton
                          size="small"
                          onClick={copyRunIdToClipboard}
                          sx={{ p: 0.5 }}
                        >
                          <ContentCopyIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">Started</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 500 }}>
                      {dayjs(runDetails.created_at).format('MMM D, YYYY HH:mm')}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="textSecondary">Duration</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 500 }}>
                      {formatDuration(runDetails.total_duration_seconds)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption" color="textSecondary">Cost</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 500, color: 'success.main' }}>
                      ${runDetails.total_cost_usd?.toFixed(4) || '0.0000'}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              {/* Original Form Input */}
              <Paper sx={{ p: 3, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                  Form Input
                </Typography>
                <Grid container spacing={2}>
                  {/* Basic Parameters */}
                  <Grid item xs={6}>
                    <Typography variant="caption" color="textSecondary">Mode</Typography>
                    <Typography variant="body2" sx={{ textTransform: 'capitalize', fontWeight: 500, mt: 0.5 }}>
                      {runDetails.mode?.replace('_', ' ') || 'N/A'}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={6}>
                    <Typography variant="caption" color="textSecondary">Creativity</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                      Level {runDetails.creativity_level}/3
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">Platform</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                      {runDetails.platform_name || 'N/A'}
                    </Typography>
                  </Grid>
                  
                  {runDetails.task_type && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary">Task Type</Typography>
                      <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                        {runDetails.task_type}
                      </Typography>
                    </Grid>
                  )}
                  
                  {/* User Prompt */}
                  {runDetails.prompt && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary">User Prompt</Typography>
                      <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider' }}>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                          {runDetails.prompt}
                        </Typography>
                      </Paper>
                    </Grid>
                  )}
                  
                  {/* Task Description */}
                  {runDetails.task_description && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary">Task Description</Typography>
                      <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider' }}>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                          {runDetails.task_description}
                        </Typography>
                      </Paper>
                    </Grid>
                  )}
                  
                  {/* Image Reference */}
                  {runDetails.has_image_reference && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary">Reference Image</Typography>
                      <Box sx={{ mt: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {runDetails.image_filename || 'Uploaded image'}
                        </Typography>
                        {runDetails.image_instruction && (
                          <Typography variant="body2" color="textSecondary" sx={{ mt: 0.5, fontStyle: 'italic' }}>
                            "{runDetails.image_instruction}"
                          </Typography>
                        )}
                      </Box>
                    </Grid>
                  )}
                  
                  {/* Settings Flags */}
                  <Grid item xs={12}>
                    <Typography variant="caption" color="textSecondary">Settings</Typography>
                    <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Chip 
                        label={`Text: ${runDetails.render_text ? 'ON' : 'OFF'}`}
                        size="small"
                        color={runDetails.render_text ? 'success' : 'default'}
                        variant="outlined"
                      />
                      <Chip 
                        label={`Branding: ${runDetails.apply_branding ? 'ON' : 'OFF'}`}
                        size="small"
                        color={runDetails.apply_branding ? 'success' : 'default'}
                        variant="outlined"
                      />
                    </Box>
                  </Grid>
                  
                  {/* Branding Elements */}
                  {runDetails.branding_elements && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary">Branding Elements</Typography>
                      <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider' }}>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                          {runDetails.branding_elements}
                        </Typography>
                      </Paper>
                    </Grid>
                  )}
                  
                  {/* Marketing Goals */}
                  {(runDetails.marketing_audience || runDetails.marketing_objective || runDetails.marketing_voice || runDetails.marketing_niche) && (
                    <Grid item xs={12}>
                      <Typography variant="caption" color="textSecondary" sx={{ mb: 2, display: 'block' }}>
                        Marketing Goals
                      </Typography>
                      <Grid container spacing={1}>
                        {runDetails.marketing_audience && (
                          <Grid item xs={12}>
                            <Typography variant="caption" color="textSecondary">Target Audience</Typography>
                            <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                              {runDetails.marketing_audience}
                            </Typography>
                          </Grid>
                        )}
                        {runDetails.marketing_objective && (
                          <Grid item xs={12}>
                            <Typography variant="caption" color="textSecondary">Objective</Typography>
                            <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                              {runDetails.marketing_objective}
                            </Typography>
                          </Grid>
                        )}
                        {runDetails.marketing_voice && (
                          <Grid item xs={12}>
                            <Typography variant="caption" color="textSecondary">Voice</Typography>
                            <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                              {runDetails.marketing_voice}
                            </Typography>
                          </Grid>
                        )}
                        {runDetails.marketing_niche && (
                          <Grid item xs={12}>
                            <Typography variant="caption" color="textSecondary">Niche</Typography>
                            <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                              {runDetails.marketing_niche}
                            </Typography>
                          </Grid>
                        )}
                      </Grid>
                    </Grid>
                  )}
                </Grid>
              </Paper>

              {/* Stage Outputs */}
              <Paper sx={{ p: 2, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, px: 1 }}>
                  Stage Outputs
                </Typography>
                {runDetails.stages.map((stage) => (
                  stage.output_data && (
                    <Accordion key={`output-${stage.stage_name}`} sx={{ mb: 1 }}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, textTransform: 'capitalize' }}>
                          {stage.stage_name.replace('_', ' ')} Results
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Paper sx={{ p: 2, backgroundColor: 'grey.50' }}>
                          <pre style={{ 
                            whiteSpace: 'pre-wrap', 
                            fontSize: '0.75rem',
                            fontFamily: 'monospace',
                            margin: 0,
                            maxHeight: '300px',
                            overflow: 'auto'
                          }}>
                            {JSON.stringify(stage.output_data, null, 2)}
                          </pre>
                        </Paper>
                      </AccordionDetails>
                    </Accordion>
                  )
                ))}
              </Paper>

              {/* Logs */}
              <Paper sx={{ borderRadius: 2, border: 1, borderColor: 'divider' }}>
                <Accordion>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      Live Logs ({logs.length})
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails sx={{ p: 0 }}>
                    <Paper 
                      sx={{ 
                        p: 2, 
                        backgroundColor: 'grey.900', 
                        color: 'grey.100',
                        maxHeight: 300,
                        overflow: 'auto',
                        fontFamily: 'monospace',
                        borderRadius: 0,
                      }}
                    >
                      <AnimatePresence>
                        {logs.map((log, index) => (
                          <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                          >
                            <div 
                              style={{ 
                                marginBottom: '4px',
                                color: log.level === 'error' ? '#ffcdd2' :
                                       log.level === 'warning' ? '#fff3e0' :
                                       log.level === 'success' ? '#c8e6c9' : 'inherit',
                                fontSize: '0.7rem',
                                lineHeight: 1.3,
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                                backgroundColor: log.message?.includes('⚠️ IMPORTANT') ? '#ff9800' : 'transparent',
                                padding: log.message?.includes('⚠️ IMPORTANT') ? '4px 8px' : '0',
                                borderRadius: log.message?.includes('⚠️ IMPORTANT') ? '4px' : '0',
                                fontWeight: log.message?.includes('⚠️ IMPORTANT') ? 'bold' : 'normal'
                              }}
                            >
                              [{dayjs(log.timestamp).format('HH:mm:ss')}] 
                              {log.stage && ` [${log.stage}]`} 
                              {log.message}
                            </div>
                          </motion.div>
                        ))}
                      </AnimatePresence>
                    </Paper>
                  </AccordionDetails>
                </Accordion>
              </Paper>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Image Dialog */}
      <Dialog
        open={!!selectedImage}
        onClose={() => setSelectedImage(null)}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 2 }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
          <Typography variant="h6" component="div">
            Generated Image - Full Size
          </Typography>
          <IconButton onClick={() => setSelectedImage(null)} sx={{ color: 'grey.500' }}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
          {selectedImage && (
            <Box
              component="img"
              src={selectedImage}
              sx={{
                width: '100%',
                height: 'auto',
                maxHeight: '80vh',
                objectFit: 'contain',
                borderRadius: 1,
              }}
            />
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setSelectedImage(null)} variant="outlined">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </motion.div>
  );
} 