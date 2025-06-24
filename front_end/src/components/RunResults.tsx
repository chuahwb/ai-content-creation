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
  Switch,
  FormControlLabel,
  TextField,
  CircularProgress,
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
  Code as CodeIcon,
  DeveloperMode as DeveloperModeIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Warning as WarningIcon,
  AutoFixHigh as AutoFixHighIcon,
  Edit as EditIcon,
  AutoAwesome as AutoAwesomeIcon,
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
  CaptionSettings,
  CaptionResult,
} from '@/types/api';
import { PipelineAPI, WebSocketManager } from '@/lib/api';
import { statusColors } from '@/lib/theme';
import RefinementModal from './RefinementModal';
import CaptionDialog from './CaptionDialog';
import CaptionDisplay from './CaptionDisplay';

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

// Define all pipeline stages
const PIPELINE_STAGES = [
  { name: 'image_eval', label: 'Image Analysis', description: 'Analyzing uploaded image' },
  { name: 'strategy', label: 'Strategy Generation', description: 'Creating marketing strategies' },
  { name: 'style_guide', label: 'Style Guide', description: 'Defining visual style' },
  { name: 'creative_expert', label: 'Creative Concepts', description: 'Developing visual concepts' },
  { name: 'prompt_assembly', label: 'Prompt Assembly', description: 'Building generation prompts' },
  { name: 'image_generation', label: 'Image Generation', description: 'Creating final images' },
  { name: 'image_assessment', label: 'Image Assessment', description: 'Evaluating generated images' },
];

// Component for visual pipeline stages display
interface PipelineStageBoxProps {
  stage: typeof PIPELINE_STAGES[0];
  status: StageStatus;
  message?: string;
  duration?: number;
  isActive: boolean;
}

const PipelineStageBox: React.FC<PipelineStageBoxProps> = ({ 
  stage, 
  status, 
  message, 
  duration, 
  isActive 
}) => {
  const getStatusColor = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED': return '#4caf50';
      case 'RUNNING': return '#2196f3';
      case 'FAILED': return '#f44336';
      default: return '#9e9e9e';
    }
  };

  const getStatusIcon = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED': return <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />;
      case 'RUNNING': return <PlayArrowIcon sx={{ color: '#2196f3', fontSize: 20 }} />;
      case 'FAILED': return <ErrorIcon sx={{ color: '#f44336', fontSize: 20 }} />;
      default: return <AccessTimeIcon sx={{ color: '#9e9e9e', fontSize: 20 }} />;
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  return (
    <motion.div
      initial={{ scale: 0.95, opacity: 0.7 }}
      animate={{ 
        scale: isActive ? 1.02 : 1, 
        opacity: 1
      }}
      transition={{ duration: 0.3 }}
      style={{ 
        borderRadius: '12px', 
        overflow: 'hidden',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <Paper
        elevation={0} // Remove default elevation to avoid conflicting shadows
        sx={{
          p: 2,
          minHeight: 170, // Updated height for better spacing
          maxHeight: 170, // Also set max height to force uniformity
          height: 170, // Explicit height to ensure consistency
          width: '100%', // Ensure full width consistency
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'flex-start', // Start from top to prevent overlapping
          textAlign: 'center',
          border: 2,
          borderColor: getStatusColor(status),
          borderRadius: 3, // Restored rounded corners
          backgroundColor: status === 'RUNNING' ? 'rgba(33, 150, 243, 0.08)' : '#ffffff',
          position: 'relative',
          overflow: 'hidden',
          transition: 'all 0.3s ease-in-out',
          // Ensure clean border radius rendering and shadows
          boxSizing: 'border-box',
          boxShadow: '0 2px 12px -4px rgba(0, 0, 0, 0.12)',
          '&:hover': {
            transform: 'translateY(-3px)',
            boxShadow: `0 12px 32px -8px ${getStatusColor(status)}25`,
            borderColor: getStatusColor(status),
          }
        }}
      >
        {/* Animated progress bar for running state */}
        {status === 'RUNNING' && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              height: 3,
              background: `linear-gradient(90deg, transparent, ${getStatusColor(status)}, transparent)`,
              animation: 'slide 2s infinite linear',
              '@keyframes slide': {
                '0%': { transform: 'translateX(-100%)' },
                '100%': { transform: 'translateX(100%)' }
              }
            }}
          />
        )}

        {/* Icon section - fixed height 36px */}
        <Box sx={{ 
          height: 36, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          mt: 1
        }}>
          {getStatusIcon(status)}
        </Box>

        {/* Title section - fixed height 50px (enough for 2 lines) */}
        <Box sx={{ 
          height: 100, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          px: 1
        }}>
          <Typography 
            variant="subtitle2" 
            sx={{ 
              fontWeight: 600, 
              fontSize: '0.9rem',
              color: status === 'RUNNING' ? 'primary.main' : 'text.primary',
              lineHeight: 1.3,
              textAlign: 'center',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden'
            }}
          >
            {stage.label}
          </Typography>
        </Box>

        {/* Status section - fixed height 32px (always at same position) */}
        <Box sx={{ 
          height: 32, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center'
        }}>
          <Chip
            label={status.toLowerCase()}
            size="small"
            sx={{
              backgroundColor: getStatusColor(status),
              color: 'white',
              fontWeight: 500,
              fontSize: '0.7rem',
              height: 22,
              borderRadius: 3,
              textTransform: 'capitalize'
            }}
          />
        </Box>

        {/* Duration section - fixed height 24px (always at same position) */}
        <Box sx={{ 
          height: 24, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center'
        }}>
          <Typography variant="caption" color="textSecondary" sx={{ 
            fontWeight: 500, 
            fontSize: '0.75rem',
            fontFamily: 'monospace'
          }}>
            {duration ? formatDuration(duration) : '\u00A0'}
          </Typography>
        </Box>

        {/* Message area - remaining space at bottom */}
        <Box sx={{ 
          flex: 1,
          minHeight: 20, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          width: '100%'
        }}>
          {message && !message.includes('stage') && !message.includes('COMPLETED') && !message.includes('completed') ? (
            <Tooltip title={message} placement="bottom">
              <Typography 
                variant="caption" 
                color="textSecondary" 
                sx={{ 
                  fontSize: '0.7rem',
                  display: '-webkit-box',
                  WebkitLineClamp: 1,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  lineHeight: 1.2,
                  textAlign: 'center',
                  px: 1,
                  opacity: 0.8
                }}
              >
                {message}
              </Typography>
            </Tooltip>
          ) : (
            <Typography 
              variant="caption" 
              color="transparent" 
              sx={{ fontSize: '0.7rem', lineHeight: 1.2 }}
            >
              &nbsp;
            </Typography>
          )}
        </Box>
      </Paper>
    </motion.div>
  );
};

// Assessment Indicators Component
interface ImageAssessmentIndicatorsProps {
  assessmentData: any;
  imageIndex: number;
  isExpanded: boolean;
  onToggleExpanded: () => void;
}

const ImageAssessmentIndicators: React.FC<ImageAssessmentIndicatorsProps> = ({
  assessmentData,
  imageIndex,
  isExpanded,
  onToggleExpanded
}) => {
  const renderScoreDots = (score: number) => {
    return Array.from({ length: 5 }, (_, i) => (
      <Box
        key={i}
        sx={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: i < score ? '#4caf50' : '#e0e0e0',
          display: 'inline-block',
          mr: 0.5
        }}
      />
    ));
  };

  const renderStatusIndicator = (needsAttention: boolean, label: string, description: string, score?: number) => {
    // Use backend flag as primary determination, score for visual enhancement only
    let status: 'good' | 'evaluate' | 'fix' = 'good';
    let statusText = 'Good';
    let backgroundColor = '#e8f5e8';
    let borderColor = '#c8e6c8';
    let textColor = '#2e7d32';
    let iconColor = '#4caf50';
    let icon = <CheckCircleIcon sx={{ color: iconColor, fontSize: 18 }} />;

    // Primary logic: Use backend flag
    if (needsAttention) {
      status = 'fix';
      statusText = 'Needs Fix';
      backgroundColor = '#ffebee';
      borderColor = '#ffcdd2';
      textColor = '#c62828';
      iconColor = '#f44336';
      icon = <WarningIcon sx={{ color: iconColor, fontSize: 18 }} />;
    } else {
      // Not flagged for attention - check if score=4 for "evaluate" status
      if (score !== undefined && score === 4) {
        status = 'evaluate';
        statusText = 'Evaluate';
        backgroundColor = '#fff8e1';
        borderColor = '#ffecb3';
        textColor = '#f57c00';
        iconColor = '#ff9800';
        icon = <WarningIcon sx={{ color: iconColor, fontSize: 18 }} />;
      } else {
        // Default good status (score 5 or no attention needed)
        status = 'good';
        statusText = score === 5 ? 'Excellent' : 'Good';
      }
    }

    return (
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        minWidth: 80,
        p: 1,
        borderRadius: 1,
        backgroundColor,
        border: 1,
        borderColor
      }}>
        {/* Status Icon */}
        <Box sx={{ mb: 0.5 }}>
          {icon}
        </Box>
        
        {/* Label */}
        <Typography 
          variant="caption" 
          sx={{ 
            fontWeight: 600,
            color: textColor,
            textAlign: 'center',
            lineHeight: 1.2,
            fontSize: '0.7rem'
          }}
        >
          {label}
        </Typography>
        
        {/* Status Text */}
        <Typography 
          variant="caption" 
          sx={{ 
            color: textColor,
            textAlign: 'center',
            lineHeight: 1.1,
            fontSize: '0.65rem',
            mt: 0.25
          }}
        >
          {statusText}
        </Typography>
        
        {/* Score if available */}
        {score !== undefined && (
          <Typography 
            variant="caption" 
            sx={{ 
              color: textColor,
              textAlign: 'center',
              lineHeight: 1.1,
              fontSize: '0.6rem',
              mt: 0.1,
              fontWeight: 500
            }}
          >
            ({score}/5)
          </Typography>
        )}
      </Box>
    );
  };

  return (
    <Box sx={{ mt: 2, p: 2, backgroundColor: 'grey.50', borderRadius: 2, border: 1, borderColor: 'divider' }}>
      {/* Header with Overall Score */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            Quality Assessment
          </Typography>
          <Chip 
            label={`${assessmentData.general_score?.toFixed(1) || '0.0'}/5.0`}
            size="small"
            color={assessmentData.general_score >= 4 ? 'success' : assessmentData.general_score >= 3 ? 'warning' : 'error'}
            variant="outlined"
          />
        </Box>
        
        {/* Dropdown Toggle */}
        <Button
          size="small"
          variant="outlined"
          onClick={onToggleExpanded}
          sx={{ minWidth: 'auto', px: 1, fontSize: '0.75rem' }}
        >
          {isExpanded ? '▲ Hide' : '▼ Details'}
        </Button>
      </Box>
      
      {/* Status Indicators Row */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, justifyContent: 'center', mb: isExpanded ? 2 : 0 }}>
        {/* Subject Preservation - only show if reference image was used */}
        {assessmentData.assessment_scores && 'subject_preservation' in assessmentData.assessment_scores && (
          renderStatusIndicator(
            assessmentData.needs_subject_repair,
            'Subject',
            'Subject preservation quality',
            assessmentData.assessment_scores.subject_preservation
          )
        )}
        
        {/* Overall Quality */}
        {renderStatusIndicator(
          assessmentData.needs_regeneration,
          'Overall',
          'Overall image quality',
          Math.round(assessmentData.general_score || 0)
        )}
        
        {/* Text Quality - only show if text rendering was enabled */}
        {assessmentData.assessment_scores && 'text_rendering_quality' in assessmentData.assessment_scores && (
          renderStatusIndicator(
            assessmentData.needs_text_repair,
            'Text',
            'Text rendering quality',
            assessmentData.assessment_scores.text_rendering_quality
          )
        )}
      </Box>
      
      {/* Expanded Details */}
      {isExpanded && (
        <Box sx={{ mt: 2 }}>          
          {/* Detailed Scores */}
          <Grid container spacing={2}>
            {assessmentData.assessment_scores && Object.entries(assessmentData.assessment_scores).map(([key, score]: [string, any]) => (
              <Grid item xs={6} key={key}>
                <Typography variant="caption" color="textSecondary" sx={{ textTransform: 'capitalize' }}>
                  {key.replace(/_/g, ' ')}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                  {renderScoreDots(score)}
                  <Typography variant="caption" color="textSecondary">
                    {score}/5
                  </Typography>
                </Box>
                {assessmentData.assessment_justification?.[key] && (
                  <Typography variant="caption" color="textSecondary" sx={{ mt: 0.5, display: 'block', fontStyle: 'italic' }}>
                    "{assessmentData.assessment_justification[key]}"
                  </Typography>
                )}
              </Grid>
            ))}
          </Grid>
        </Box>
      )}
    </Box>
  );
};

export default function RunResults({ runId, onNewRun }: RunResultsProps) {
  const [runDetails, setRunDetails] = useState<PipelineRunDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [wsManager, setWsManager] = useState<WebSocketManager | null>(null);
  const [showConfetti, setShowConfetti] = useState(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImageResult[]>([]);
  const [detailsDialog, setDetailsDialog] = useState<{open: boolean, optionIndex: number | null}>({open: false, optionIndex: null});
  const [optionDetails, setOptionDetails] = useState<{marketingGoals?: any, finalPrompt?: string, visualConcept?: any} | null>(null);
  // NEW: Assessment data state
  const [imageAssessments, setImageAssessments] = useState<any[]>([]);
  const [assessmentDropdownStates, setAssessmentDropdownStates] = useState<{[key: number]: boolean}>({});
  
  // Developer mode state
  const [isDeveloperMode, setIsDeveloperMode] = useState(false);
  const [developerDialog, setDeveloperDialog] = useState(false);
  const [developerCode, setDeveloperCode] = useState('');
  
  // Refinement state
  const [refinementModal, setRefinementModal] = useState<{
    open: boolean;
    imageIndex: number | null;
    imagePath: string | null;
  }>({ open: false, imageIndex: null, imagePath: null });
  const [refinements, setRefinements] = useState<any[]>([]);
  const [refinementProgress, setRefinementProgress] = useState<{ [key: string]: any }>({});
  
  // Caption state
  const [captionDialogOpen, setCaptionDialogOpen] = useState(false);
  const [captionImageIndex, setCaptionImageIndex] = useState<number>(0);
  const [captionInitialSettings, setCaptionInitialSettings] = useState<CaptionSettings | undefined>(undefined);
  const [captionGenerating, setCaptionGenerating] = useState<Record<number, boolean>>({});
  const [imageCaptions, setImageCaptions] = useState<Record<number, CaptionResult[]>>({});
  
  // Add caption error state management
  const [captionErrors, setCaptionErrors] = useState<Record<number, string>>({});
  
  const DEVELOPER_CODE = 'dev123'; // Simple code for prototype

  // Initialize developer mode from localStorage
  useEffect(() => {
    const savedDevMode = localStorage.getItem('churns_developer_mode');
    if (savedDevMode === 'true') {
      setIsDeveloperMode(true);
    }
  }, []);

  const handleDeveloperAccess = () => {
    if (developerCode === DEVELOPER_CODE) {
      setIsDeveloperMode(true);
      localStorage.setItem('churns_developer_mode', 'true');
      setDeveloperDialog(false);
      setDeveloperCode('');
      toast.success('Developer mode enabled!');
    } else {
      toast.error('Invalid developer code');
    }
  };

  const toggleDeveloperMode = () => {
    if (isDeveloperMode) {
      setIsDeveloperMode(false);
      localStorage.removeItem('churns_developer_mode');
      toast.success('Developer mode disabled');
    } else {
      setDeveloperDialog(true);
    }
  };

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
          if (results.image_assessments) {
            setImageAssessments(results.image_assessments);
            addLog('info', `Loaded ${results.image_assessments.length} image assessments`);
          }
          if (results.generated_images) {
            // Merge assessment data with generated images
            const mergedImages = results.generated_images.map((img: any) => {
              const assessment = results.image_assessments?.find(
                (a: any) => a.image_index === img.strategy_index
              );
              return { ...img, assessment };
            });
            setGeneratedImages(mergedImages);
            addLog('info', `Loaded ${results.generated_images.length} generated images`);
            

          }
          
          // Load refinements for completed runs
          await loadRefinements();
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
        
        // Special handling for image_assessment stage
        if (stageUpdate.stage_name === 'image_assessment') {
          // Extract assessment results from stage output
          if (stageUpdate.output_data && stageUpdate.output_data.image_assessments) {
            setImageAssessments(stageUpdate.output_data.image_assessments);
            addLog('info', `Loaded ${stageUpdate.output_data.image_assessments.length} image assessments`);
          }
        }
        
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
        addLog('success', 'Pipeline run completed successfully!');
        setShowConfetti(true);
        setTimeout(() => setShowConfetti(false), 5000);
        fetchRunDetails(); // Refresh final details
        break;
        
      case 'run_error':
        addLog('error', `Pipeline run failed: ${message.data.error_message}`);
        fetchRunDetails(); // Refresh to get error details
        break;
        
      case 'caption_complete':
        if (message.data?.image_id) {
          // Extract image index from image_id (format: "image_0", "image_1", etc.)
          const imageIndex = parseInt(message.data.image_id.split('_')[1]);
          addLog('success', `Caption generated for Option ${imageIndex + 1}`);
          // Load the updated captions for this image
          loadCaptions(imageIndex);
          // Stop the loading spinner and clear any error
          setCaptionGenerating(prev => ({ ...prev, [imageIndex]: false }));
          setCaptionErrors(prev => ({ ...prev, [imageIndex]: '' }));
          toast.success(`Caption generated for Option ${imageIndex + 1}!`);
        }
        break;
        
      case 'caption_update':
        if (message.data?.image_id) {
          const imageIndex = parseInt(message.data.image_id.split('_')[1]);
          addLog('info', `Caption generation progress: ${message.data.message}`);
        }
        break;
        
      case 'caption_error':
        if (message.data?.image_id) {
          const imageIndex = parseInt(message.data.image_id.split('_')[1]);
          const errorMessage = message.data.error_message || 'Caption generation failed';
          addLog('error', `Caption generation failed for Option ${imageIndex + 1}: ${errorMessage}`);
          // Stop the loading spinner and show error
          setCaptionGenerating(prev => ({ ...prev, [imageIndex]: false }));
          setCaptionErrors(prev => ({ ...prev, [imageIndex]: errorMessage }));
          toast.error(`Caption generation failed for Option ${imageIndex + 1}: ${errorMessage}`);
        }
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

  const copyPromptToClipboard = async (prompt: string) => {
    try {
      await navigator.clipboard.writeText(prompt);
      toast.success('Prompt copied to clipboard!');
      addLog('info', 'Prompt copied to clipboard');
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = prompt;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      toast.success('Prompt copied to clipboard!');
      addLog('info', 'Prompt copied to clipboard');
    }
  };

  const loadOptionDetails = async (optionIndex: number) => {
    try {
      const results = await PipelineAPI.getResults(runId);
      
      // Get marketing strategy for this option
      const marketingStrategy = results.marketing_strategies?.[optionIndex];
      
      // Get final prompt for this option
      const finalPrompt = results.final_prompts?.[optionIndex];
      
      // Get visual concept for this option
      const visualConcept = results.visual_concepts?.[optionIndex];
      
      setOptionDetails({
        marketingGoals: marketingStrategy,
        finalPrompt: finalPrompt?.prompt || 'No prompt available',
        visualConcept: visualConcept
      });
      
      setDetailsDialog({open: true, optionIndex});
      addLog('info', `Loaded details for Option ${optionIndex + 1}`);
    } catch (err: any) {
      const errorMsg = `Failed to load option details: ${err.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
    }
  };

  const closeDetailsDialog = () => {
    setDetailsDialog({open: false, optionIndex: null});
    setOptionDetails(null);
  };

  // Assessment dropdown toggle handler
  const toggleAssessmentDropdown = (imageIndex: number) => {
    setAssessmentDropdownStates(prev => ({
      ...prev,
      [imageIndex]: !prev[imageIndex]
    }));
  };

  // Refinement functions
  const openRefinementModal = (imageIndex: number, imagePath: string) => {
    if (runDetails?.status !== 'COMPLETED') {
      toast.error('Cannot refine images from incomplete runs');
      return;
    }
    
    setRefinementModal({
      open: true,
      imageIndex,
      imagePath
    });
  };

  const closeRefinementModal = () => {
    setRefinementModal({ open: false, imageIndex: null, imagePath: null });
  };

  const loadRefinements = async () => {
    try {
      const data = await PipelineAPI.getRefinements(runId);
      setRefinements(data.refinements || []);
    } catch (error) {
      console.error('Failed to load refinements:', error);
    }
  };

  // Caption functions
  const openCaptionDialog = (imageIndex: number) => {
    setCaptionImageIndex(imageIndex);
    setCaptionInitialSettings(undefined); // Clear any previous settings
    setCaptionDialogOpen(true);
  };

  const closeCaptionDialog = () => {
    setCaptionDialogOpen(false);
    setCaptionInitialSettings(undefined); // Clear settings when closing
  };

  const handleOpenCaptionSettingsDialog = (imageIndex: number, currentSettings: CaptionSettings) => {
    setCaptionImageIndex(imageIndex);
    setCaptionInitialSettings(currentSettings); // Pre-populate with current settings
    setCaptionDialogOpen(true);
  };

  const handleCaptionGenerate = async (settings: CaptionSettings) => {
    const imageId = `image_${captionImageIndex}`;
    
    try {
      setCaptionGenerating(prev => ({ ...prev, [captionImageIndex]: true }));
      setCaptionErrors(prev => ({ ...prev, [captionImageIndex]: '' })); // Clear any previous error
      closeCaptionDialog();
      
      const response = await PipelineAPI.generateCaption(runId, imageId, settings);
      addLog('info', `Caption generation started for Option ${captionImageIndex + 1}`);
      toast.success('Caption generation started! Check progress in real-time.');
      
      // Don't clear loading state here - let WebSocket handler do it when complete
      
    } catch (error: any) {
      const errorMsg = `Failed to generate caption: ${error.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
      // Only clear loading state on error and set error message
      setCaptionGenerating(prev => ({ ...prev, [captionImageIndex]: false }));
      setCaptionErrors(prev => ({ ...prev, [captionImageIndex]: errorMsg }));
    }
  };

  const handleCaptionRegenerate = async (imageIndex: number, version?: number, settings?: CaptionSettings) => {
    const imageId = `image_${imageIndex}`;
    
    try {
      setCaptionGenerating(prev => ({ ...prev, [imageIndex]: true }));
      setCaptionErrors(prev => ({ ...prev, [imageIndex]: '' })); // Clear any previous error
      
      let response;
      // Get the current highest version number for proper versioning
      const currentCaptions = imageCaptions[imageIndex] || [];
      const latestVersion = currentCaptions.length > 0 ? Math.max(...currentCaptions.map(c => c.version)) : -1;
      
      if (version !== undefined) {
        // Regenerate specific version - use the provided version
        response = await PipelineAPI.regenerateCaption(runId, imageId, version, settings);
      } else {
        // Generate new caption - use the latest version for incrementing
        response = await PipelineAPI.regenerateCaption(runId, imageId, latestVersion, settings);
      }
      
      addLog('info', `Caption regeneration started for Option ${imageIndex + 1}`);
      toast.success('Caption regeneration started!');
      
      // Don't clear loading state here - let WebSocket handler do it when complete
      
    } catch (error: any) {
      const errorMsg = `Failed to regenerate caption: ${error.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
      // Only clear loading state on error and set error message
      setCaptionGenerating(prev => ({ ...prev, [imageIndex]: false }));
      setCaptionErrors(prev => ({ ...prev, [imageIndex]: errorMsg }));
    }
  };

  const loadCaptions = async (imageIndex: number) => {
    try {
      const imageId = `image_${imageIndex}`;
      const response = await PipelineAPI.getCaptions(runId, imageId);
      
      if (response.captions && response.captions.length > 0) {
        setImageCaptions(prev => ({
          ...prev,
          [imageIndex]: response.captions
        }));
      }
    } catch (error) {
      // Silently fail - captions might not exist yet
      console.debug('No captions found for image', imageIndex);
    }
  };

  // Helper function to retry caption generation
  const retryCaptionGeneration = (imageIndex: number) => {
    setCaptionErrors(prev => ({ ...prev, [imageIndex]: '' })); // Clear error
    openCaptionDialog(imageIndex);
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
    const TOTAL_STAGES = 7; // Fixed total: image_eval, strategy, style_guide, creative_expert, prompt_assembly, image_generation, image_assessment
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

  // Helper function to get stage status for visual pipeline
  const getStageStatus = (stageName: string): StageStatus => {
    const stage = runDetails?.stages.find(s => s.stage_name === stageName);
    return stage?.status || 'PENDING' as StageStatus;
  };

  const getStageData = (stageName: string) => {
    return runDetails?.stages.find(s => s.stage_name === stageName);
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

  // Load captions whenever generatedImages changes
  useEffect(() => {
    const loadCaptionsForAllImages = async () => {
      if (generatedImages.length > 0 && runDetails?.status === 'COMPLETED') {
        for (const image of generatedImages) {
          await loadCaptions(image.strategy_index);
        }
      }
    };
    
    loadCaptionsForAllImages();
  }, [generatedImages, runDetails?.status]);

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
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                                <Typography variant="subtitle1" sx={{ fontWeight: 600, color: 'primary.main' }}>
                                  Option {result.strategy_index + 1}
                                </Typography>
                                <Chip 
                                  label="Success" 
                                  color="success" 
                                  size="small" 
                                  sx={{ fontWeight: 500 }} 
                                />
                              </Box>
                              
                              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                <Tooltip title="View marketing strategy & prompt">
                                  <Button
                                    size="small"
                                    startIcon={<ContentCopyIcon />}
                                    onClick={() => loadOptionDetails(result.strategy_index)}
                                    color="secondary"
                                    variant="outlined"
                                    sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                                  >
                                    Details
                                  </Button>
                                </Tooltip>
                                <Tooltip title="View full size">
                                  <Button
                                    size="small"
                                    startIcon={<ZoomInIcon />}
                                    onClick={() => result.image_path && setSelectedImage(PipelineAPI.getFileUrl(runId, result.image_path))}
                                    color="primary"
                                    variant="outlined"
                                    sx={{ fontWeight: 500, fontSize: '0.75rem' }}
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
                                    sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                                  >
                                    Download
                                  </Button>
                                </Tooltip>
                                <Tooltip title="Refine this image">
                                  <Button
                                    size="small"
                                    startIcon={<AutoFixHighIcon />}
                                    onClick={() => openRefinementModal(result.strategy_index, result.image_path!)}
                                    color="secondary"
                                    variant="contained"
                                    sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                                  >
                                    Refine
                                  </Button>
                                </Tooltip>
                                <Tooltip title="Generate social media caption">
                                  <Button
                                    size="small"
                                    startIcon={captionGenerating[result.strategy_index] ? <CircularProgress size={16} /> : <AutoAwesomeIcon />}
                                    onClick={() => openCaptionDialog(result.strategy_index)}
                                    color="primary"
                                    variant="outlined"
                                    disabled={captionGenerating[result.strategy_index]}
                                    sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                                  >
                                    {captionGenerating[result.strategy_index] ? 'Generating...' : 'Caption'}
                                  </Button>
                                </Tooltip>
                              </Box>
                              
                              {/* NEW: Assessment Indicators */}
                              {result.assessment ? (
                                <ImageAssessmentIndicators 
                                  assessmentData={result.assessment}
                                  imageIndex={result.strategy_index}
                                  isExpanded={assessmentDropdownStates[result.strategy_index] || false}
                                  onToggleExpanded={() => toggleAssessmentDropdown(result.strategy_index)}
                                />
                              ) : (
                                // Show "Assessment Unavailable" state when no assessment data
                                <Box sx={{ mt: 2, p: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Chip 
                                    label="Assessment Unavailable" 
                                    size="small" 
                                    variant="outlined" 
                                    color="default"
                                    sx={{ fontSize: '0.7rem' }}
                                  />
                                </Box>
                              )}

                              {/* Caption Loading Indicator */}
                              {captionGenerating[result.strategy_index] && (!imageCaptions[result.strategy_index] || imageCaptions[result.strategy_index].length === 0) && (
                                <Box sx={{ 
                                  mt: 2, 
                                  p: 2, 
                                  backgroundColor: 'grey.50', 
                                  borderRadius: 2, 
                                  border: 1, 
                                  borderColor: 'divider',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 2
                                }}>
                                  <CircularProgress size={20} />
                                  <Typography variant="body2" color="textSecondary">
                                    Generating caption... This may take a moment.
                                  </Typography>
                                </Box>
                              )}

                              {/* Caption Error Display */}
                              {captionErrors[result.strategy_index] && !captionGenerating[result.strategy_index] && (
                                <Alert 
                                  severity="error" 
                                  sx={{ mt: 2 }}
                                  action={
                                    <Button 
                                      color="inherit" 
                                      size="small" 
                                      onClick={() => {
                                        setCaptionErrors(prev => ({ ...prev, [result.strategy_index]: '' }));
                                        retryCaptionGeneration(result.strategy_index);
                                      }}
                                      startIcon={<AutoAwesomeIcon />}
                                    >
                                      Retry
                                    </Button>
                                  }
                                >
                                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                    Caption Generation Failed
                                  </Typography>
                                  <Typography variant="body2" color="textSecondary" sx={{ mt: 0.5 }}>
                                    {captionErrors[result.strategy_index]}
                                  </Typography>
                                </Alert>
                              )}

                              {/* Caption Display */}
                              {imageCaptions[result.strategy_index] && imageCaptions[result.strategy_index].length > 0 && (
                                <CaptionDisplay
                                  captions={imageCaptions[result.strategy_index]}
                                  onRegenerate={() => handleCaptionRegenerate(result.strategy_index)}
                                  onOpenSettingsDialog={(currentSettings) => handleOpenCaptionSettingsDialog(result.strategy_index, currentSettings)}
                                  isRegenerating={captionGenerating[result.strategy_index]}
                                />
                              )}
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

              {/* Visual Pipeline Progress */}
              <Box sx={{ mb: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                  <Typography variant="h5" sx={{ fontWeight: 600, letterSpacing: '-0.01em' }}>
                    Pipeline Progress
                  </Typography>
                  <Typography variant="body1" color="textSecondary" sx={{ fontWeight: 500 }}>
                    {runDetails.stages.filter(s => s.status === 'COMPLETED').length} / {PIPELINE_STAGES.length} stages
                  </Typography>
                </Box>
                
                                 {/* Visual Pipeline Stages Grid */}
                 <Grid container spacing={2} sx={{ mb: 3 }}>
                   {PIPELINE_STAGES.map((pipelineStage) => {
                     const stageData = getStageData(pipelineStage.name);
                     const status = getStageStatus(pipelineStage.name);
                     const isActive = status === 'RUNNING';
                     
                     return (
                       <Grid item xs={12} sm={6} md={4} lg={2} key={pipelineStage.name} sx={{ display: 'flex', flexDirection: 'column' }}>
                         <PipelineStageBox
                           stage={pipelineStage}
                           status={status}
                           message={stageData?.message}
                           duration={stageData?.duration_seconds}
                           isActive={isActive}
                         />
                       </Grid>
                     );
                   })}
                 </Grid>

                {/* Overall Progress Bar */}
                <LinearProgress 
                  variant="determinate" 
                  value={getProgressValue()} 
                  sx={{ 
                    height: 8, 
                    borderRadius: 4,
                    backgroundColor: 'grey.200',
                    '& .MuiLinearProgress-bar': {
                      borderRadius: 4,
                    }
                  }}
                />
              </Box>
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

              {/* Developer Mode Toggle */}
              <Paper sx={{ p: 2, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <DeveloperModeIcon color={isDeveloperMode ? 'primary' : 'disabled'} />
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      Developer Tools
                    </Typography>
                    {isDeveloperMode && (
                      <Chip label="Active" color="primary" size="small" sx={{ fontWeight: 500 }} />
                    )}
                  </Box>
                  <Button
                    variant={isDeveloperMode ? 'outlined' : 'contained'}
                    size="small"
                    startIcon={isDeveloperMode ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    onClick={toggleDeveloperMode}
                    sx={{ fontWeight: 500 }}
                  >
                    {isDeveloperMode ? 'Hide' : 'Show'} Dev Tools
                  </Button>
                </Box>
              </Paper>

              {/* Stage Outputs - Developer Only */}
              {isDeveloperMode && (
                <Paper sx={{ p: 2, mb: 3, borderRadius: 2, border: 1, borderColor: 'warning.main', backgroundColor: 'warning.50' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <CodeIcon color="warning" />
                    <Typography variant="h6" sx={{ fontWeight: 600, color: 'warning.dark' }}>
                      Stage Outputs (Developer)
                    </Typography>
                  </Box>
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
              )}

              {/* Logs - Developer Only */}
              {isDeveloperMode && (
                <Paper sx={{ borderRadius: 2, border: 1, borderColor: 'warning.main', backgroundColor: 'warning.50' }}>
                  <Accordion>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CodeIcon color="warning" />
                        <Typography variant="h6" sx={{ fontWeight: 600, color: 'warning.dark' }}>
                          Live Logs ({logs.length}) (Developer)
                        </Typography>
                      </Box>
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
                                                                  backgroundColor: log.message?.includes('IMPORTANT:') ? '#ff9800' : 'transparent',
                                padding: log.message?.includes('IMPORTANT:') ? '4px 8px' : '0',
                                borderRadius: log.message?.includes('IMPORTANT:') ? '4px' : '0',
                                fontWeight: log.message?.includes('IMPORTANT:') ? 'bold' : 'normal'
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
              )}
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Image Dialog */}
      <Dialog
        open={!!selectedImage}
        onClose={() => setSelectedImage(null)}
        maxWidth={false}
        fullWidth={false}
        sx={{
          '& .MuiDialog-paper': {
            maxHeight: '100vh',
            maxWidth: '100vw',
            margin: 0,
            borderRadius: 2,
            overflow: 'hidden'
          }
        }}
      >
        <DialogTitle sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          pb: 1,
          backgroundColor: 'white',
          borderBottom: 1,
          borderColor: 'divider'
        }}>
          <Typography variant="h6" component="div">
            Generated Image - Full Size
          </Typography>
          <IconButton onClick={() => setSelectedImage(null)} sx={{ color: 'grey.500' }}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ 
          p: 1,
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          backgroundColor: '#f5f5f5',
          overflow: 'auto',
          minHeight: 'calc(100vh - 140px)', // Account for title and actions
          maxHeight: 'calc(100vh - 140px)'
        }}>
          {selectedImage && (
            <Box
              component="img"
              src={selectedImage}
              sx={{
                maxWidth: 'calc(100vw - 32px)', // Account for padding
                maxHeight: 'calc(100vh - 160px)', // Account for title, actions, and padding
                width: 'auto',
                height: 'auto',
                objectFit: 'contain',
                borderRadius: 1,
                backgroundColor: 'white',
                boxShadow: 3,
                display: 'block'
              }}
              onLoad={(e) => {
                // Log dimensions for debugging
                const img = e.target as HTMLImageElement;
                console.log('Image loaded:', {
                  naturalWidth: img.naturalWidth,
                  naturalHeight: img.naturalHeight,
                  displayWidth: img.width,
                  displayHeight: img.height
                });
              }}
            />
          )}
        </DialogContent>
        <DialogActions sx={{ 
          px: 3, 
          py: 2,
          backgroundColor: 'white',
          borderTop: 1,
          borderColor: 'divider'
        }}>
          <Button onClick={() => setSelectedImage(null)} variant="outlined">
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Option Details Dialog */}
      <Dialog
        open={detailsDialog.open}
        onClose={closeDetailsDialog}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 2 }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 2 }}>
          <Typography variant="h5" component="div" sx={{ fontWeight: 600, color: 'primary.main' }}>
            Option {(detailsDialog.optionIndex ?? 0) + 1} Details
          </Typography>
          <IconButton onClick={closeDetailsDialog} sx={{ color: 'grey.500' }}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        
        <DialogContent sx={{ px: 3 }}>
          {optionDetails && (
            <Grid container spacing={3}>
              {/* Marketing Strategy */}
              {optionDetails.marketingGoals && (
                <Grid item xs={12}>
                  <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: 'secondary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
                    Marketing Strategy
                  </Typography>
                  <Paper sx={{ p: 3, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 2 }}>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                          Target Audience
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
                          {optionDetails.marketingGoals.target_audience || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                          Niche
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
                          {optionDetails.marketingGoals.target_niche || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                          Objective
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500, mb: 2 }}>
                          {optionDetails.marketingGoals.target_objective || 'N/A'}
                        </Typography>
                      </Grid>
                      <Grid item xs={12}>
                        <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                          Voice & Tone
                        </Typography>
                        <Typography variant="body1" sx={{ fontWeight: 500 }}>
                          {optionDetails.marketingGoals.target_voice || 'N/A'}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Grid>
              )}

              {/* Alt Text */}
              {optionDetails.visualConcept?.visual_concept?.suggested_alt_text && (
                <Grid item xs={12}>
                  <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: 'secondary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
                    SEO Alt Text
                  </Typography>
                  <Paper sx={{ p: 3, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 2, position: 'relative' }}>
                    <Typography 
                      variant="body1" 
                      sx={{ 
                        fontWeight: 500,
                        lineHeight: 1.6,
                        pr: 5 // Make room for copy button
                      }}
                    >
                      {optionDetails.visualConcept.visual_concept.suggested_alt_text}
                    </Typography>
                    
                    <Tooltip title="Copy alt text to clipboard">
                      <IconButton
                        onClick={() => {
                          navigator.clipboard.writeText(optionDetails.visualConcept.visual_concept.suggested_alt_text);
                          toast.success('Alt text copied to clipboard!');
                        }}
                        sx={{
                          position: 'absolute',
                          top: 8,
                          right: 8,
                          color: 'grey.600',
                          backgroundColor: 'rgba(255,255,255,0.8)',
                          '&:hover': {
                            backgroundColor: 'rgba(255,255,255,1)',
                            color: 'primary.main'
                          }
                        }}
                        size="small"
                      >
                        <ContentCopyIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Paper>
                </Grid>
              )}

              {/* Final Prompt */}
              <Grid item xs={12}>
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, color: 'secondary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
                  Image Generation Prompt
                </Typography>
                <Paper sx={{ p: 3, backgroundColor: 'grey.900', color: 'grey.100', borderRadius: 2, position: 'relative' }}>
                  <Typography 
                    variant="body2" 
                    sx={{ 
                      fontFamily: 'monospace',
                      whiteSpace: 'pre-wrap',
                      lineHeight: 1.5,
                      fontSize: '0.85rem',
                      maxHeight: '300px',
                      overflow: 'auto'
                    }}
                  >
                    {optionDetails.finalPrompt}
                  </Typography>
                  
                  <Tooltip title="Copy prompt to clipboard">
                    <IconButton
                      onClick={() => copyPromptToClipboard(optionDetails.finalPrompt || '')}
                      sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        color: 'grey.300',
                        backgroundColor: 'rgba(255,255,255,0.1)',
                        '&:hover': {
                          backgroundColor: 'rgba(255,255,255,0.2)',
                          color: 'white'
                        }
                      }}
                      size="small"
                    >
                      <ContentCopyIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Paper>
              </Grid>
            </Grid>
          )}
        </DialogContent>
        
        <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
          <Button 
            onClick={() => optionDetails?.finalPrompt && copyPromptToClipboard(optionDetails.finalPrompt)} 
            startIcon={<ContentCopyIcon />}
            variant="outlined"
            color="secondary"
          >
            Copy Prompt
          </Button>
          <Button onClick={closeDetailsDialog} variant="contained">
                      Close
        </Button>
      </DialogActions>
    </Dialog>

    {/* Developer Access Dialog */}
    <Dialog
      open={developerDialog}
      onClose={() => setDeveloperDialog(false)}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 2 }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 2, pb: 2 }}>
        <DeveloperModeIcon color="primary" />
        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
          Developer Access Required
        </Typography>
      </DialogTitle>
      
      <DialogContent sx={{ px: 3, pb: 2 }}>
        <Typography variant="body1" color="textSecondary" sx={{ mb: 3 }}>
          Enter the developer code to access stage outputs and system logs. This information is 
          intended for developers and contains technical details.
        </Typography>
        
        <TextField
          fullWidth
          label="Developer Code"
          type="password"
          value={developerCode}
          onChange={(e) => setDeveloperCode(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleDeveloperAccess();
            }
          }}
          placeholder="Enter developer access code"
          sx={{ mb: 2 }}
          autoFocus
        />
        
        <Alert severity="info" sx={{ fontSize: '0.85rem' }}>
          <strong>For Developers:</strong> This mode reveals internal pipeline data including 
          stage outputs, detailed logs, and debug information.
        </Alert>
      </DialogContent>
      
      <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
        <Button 
          onClick={() => {
            setDeveloperDialog(false);
            setDeveloperCode('');
          }} 
          variant="outlined"
        >
          Cancel
        </Button>
        <Button 
          onClick={handleDeveloperAccess}
          variant="contained"
          disabled={!developerCode.trim()}
        >
          Access Developer Tools
        </Button>
      </DialogActions>
    </Dialog>

    {/* Refinement Modal */}
    <RefinementModal
      open={refinementModal.open}
      onClose={closeRefinementModal}
      runId={runId}
      imageIndex={refinementModal.imageIndex}
      imagePath={refinementModal.imagePath}
      onRefinementSubmit={(result) => {
        addLog('info', `Refinement started: ${result.job_id}`);
        toast.success('Refinement job started successfully!');
        // Optionally refresh refinements or setup progress tracking
        setTimeout(() => loadRefinements(), 1000);
      }}
    />

    {/* Caption Dialog */}
    <CaptionDialog
      open={captionDialogOpen}
      onClose={closeCaptionDialog}
      onGenerate={handleCaptionGenerate}
      isGenerating={captionGenerating[captionImageIndex] || false}
      imageIndex={captionImageIndex}
      initialSettings={captionInitialSettings}
      error={captionErrors[captionImageIndex]} // Pass error for display
    />
  </motion.div>
);
} 