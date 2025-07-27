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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Skeleton,
  Tooltip,
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
  ContentCopy as ContentCopyIcon,
  ZoomIn as ZoomInIcon,
  Code as CodeIcon,
  DeveloperMode as DeveloperModeIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Warning as WarningIcon,
  AutoFixHigh as AutoFixHighIcon,
  AutoAwesome as AutoAwesomeIcon,
  Image as ImageIcon,
  Info as InfoIcon,
  BookmarkAdd as BookmarkAddIcon,
} from '@mui/icons-material';

import toast from 'react-hot-toast';
import dayjs from 'dayjs';
import Confetti from 'react-confetti';
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
import RefinementModal from './RefinementModal';
import RefinementDetailsDialog from './RefinementDetailsDialog';
import CaptionDialog from './CaptionDialog';
import CaptionDisplay from './CaptionDisplay';
import ImageCompareSlider from './ImageCompareSlider';
import ImageWithAuth from './ImageWithAuth';
import AdaptationContext from './AdaptationContext';

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

// Pipeline stages are now dynamic based on backend response

// Component for visual pipeline stages display
interface PipelineStageBoxProps {
  stage: {
    name: string;
    label: string;
    description: string;
  };
  status: StageStatus;
  message?: string;
  duration?: number;
}

const PipelineStageBox: React.FC<PipelineStageBoxProps> = ({ 
  stage, 
  status, 
  message, 
  duration 
}) => {
  const getStatusColor = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED': return '#4caf50';
      case 'RUNNING': return '#2196f3';
      case 'FAILED': return '#f44336';
      case 'SKIPPED': return '#ff9800';
      default: return '#9e9e9e';
    }
  };

  const getStatusIcon = (status: StageStatus) => {
    switch (status) {
      case 'COMPLETED': return <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />;
      case 'RUNNING': return <PlayArrowIcon sx={{ color: '#2196f3', fontSize: 20 }} />;
      case 'FAILED': return <ErrorIcon sx={{ color: '#f44336', fontSize: 20 }} />;
      case 'SKIPPED': return <CheckCircleIcon sx={{ color: '#ff9800', fontSize: 20 }} />;
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
    <div
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
    </div>
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
    let statusText = 'Good';
    let backgroundColor = '#e8f5e8';
    let borderColor = '#c8e6c8';
    let textColor = '#2e7d32';
    let iconColor = '#4caf50';
    let icon = <CheckCircleIcon sx={{ color: iconColor, fontSize: 18 }} />;

    // Primary logic: Use backend flag
    if (needsAttention) {
      statusText = 'Needs Fix';
      backgroundColor = '#ffebee';
      borderColor = '#ffcdd2';
      textColor = '#c62828';
      iconColor = '#f44336';
      icon = <WarningIcon sx={{ color: iconColor, fontSize: 18 }} />;
    } else {
      // Not flagged for attention - check if score=4 for "evaluate" status
      if (score !== undefined && score === 4) {
        statusText = 'Evaluate';
        backgroundColor = '#fff8e1';
        borderColor = '#ffecb3';
        textColor = '#f57c00';
        iconColor = '#ff9800';
        icon = <WarningIcon sx={{ color: iconColor, fontSize: 18 }} />;
      } else {
        // Default good status (score 5 or no attention needed)
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
                    &quot;{assessmentData.assessment_justification[key]}&quot;
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
  const [selectedImageContext, setSelectedImageContext] = useState<{
    type: 'original' | 'refinement';
    refinementData?: any;
    parentImagePath?: string;
    parentImageBlobUrl?: string;
  } | null>(null);
  const [generatedImages, setGeneratedImages] = useState<GeneratedImageResult[]>([]);
  const [detailsDialog, setDetailsDialog] = useState<{open: boolean, optionIndex: number | null}>({open: false, optionIndex: null});
  const [optionDetails, setOptionDetails] = useState<{marketingGoals?: any, finalPrompt?: string, visualConcept?: any} | null>(null);
  // Assessment data state
  const [imageAssessments, setImageAssessments] = useState<any[]>([]);
  const [assessmentDropdownStates, setAssessmentDropdownStates] = useState<{[key: number]: boolean}>({});
  
  // Developer mode state
  const [isDeveloperMode, setIsDeveloperMode] = useState(false);
  const [developerDialog, setDeveloperDialog] = useState(false);
  const [developerCode, setDeveloperCode] = useState('');
  
  // Refinement state
  const [refinements, setRefinements] = useState<any[]>([]);
  const [refinementsLoading, setRefinementsLoading] = useState(false);
  const [refinementModal, setRefinementModal] = useState<{
    open: boolean;
    imageIndex: number | null;
    imagePath: string | null;
    parentRefinementJobId?: string;
  }>({ open: false, imageIndex: null, imagePath: null });
  
  // Refinement display controls
  const [refinementGroupsExpanded, setRefinementGroupsExpanded] = useState<Record<string, boolean>>({});
  const [showAllRefinementsInGroup, setShowAllRefinementsInGroup] = useState<Record<string, boolean>>({});
  const INITIAL_REFINEMENTS_PER_GROUP = 3;
  
  // Refinement details dialog state
  const [refinementDetailsDialog, setRefinementDetailsDialog] = useState<{
    open: boolean;
    jobId: string | null;
    details: any | null;
    loading: boolean;
  }>({ open: false, jobId: null, details: null, loading: false });

  // Use the existing PIPELINE_STAGES from the top of the file
  
  // Caption state
  const [captionDialogOpen, setCaptionDialogOpen] = useState(false);
  const [captionImageIndex, setCaptionImageIndex] = useState<number>(0);
  const [captionInitialSettings, setCaptionInitialSettings] = useState<CaptionSettings | undefined>(undefined);
  const [captionGenerating, setCaptionGenerating] = useState<Record<number, boolean>>({});
  const [imageCaptions, setImageCaptions] = useState<Record<number, CaptionResult[]>>({});
  
  // Add caption error state management
  const [captionErrors, setCaptionErrors] = useState<Record<number, string>>({});
  
  // Save preset dialog state
  const [savePresetDialogOpen, setSavePresetDialogOpen] = useState(false);
  const [savePresetImageIndex, setSavePresetImageIndex] = useState<number>(0);
  const [savePresetName, setSavePresetName] = useState('');
  const [savePresetLoading, setSavePresetLoading] = useState(false);
  
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
        
        // Always try to load refinements regardless of results status
        await loadRefinements();
      } else {
        // For non-completed runs, still try to load refinements
        setGeneratedImages([]);
        await loadRefinements();
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
    console.log('🔌 WebSocket message received:', {
      type: message.type,
      runId: message.run_id,
      stageName: message.data?.stage_name,
      status: message.data?.status,
      message: message.data?.message,
      timestamp: new Date().toISOString()
    });
    
    addLog('info', `WebSocket message: ${message.type}`, message.data.stage_name);
    
    switch (message.type) {
      case 'stage_update':
        const stageUpdate = message.data as StageProgressUpdate;
        console.log('📊 Stage update details:', stageUpdate);
        
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
          if (!prev) {
            console.log('⚠️ Cannot update stages - runDetails is null');
            return prev;
          }
          
          const updatedStages = [...prev.stages];
          const stageIndex = updatedStages.findIndex(s => s.stage_name === stageUpdate.stage_name);
          
          if (stageIndex >= 0) {
            console.log(`✅ Updating existing stage ${stageUpdate.stage_name} at index ${stageIndex}`);
            updatedStages[stageIndex] = { ...updatedStages[stageIndex], ...stageUpdate };
          } else {
            console.log(`➕ Adding new stage ${stageUpdate.stage_name}`);
            updatedStages.push(stageUpdate);
          }
          
          const newRunDetails = { ...prev, stages: updatedStages };
          console.log('🔄 Updated runDetails:', {
            totalStages: newRunDetails.stages.length,
            completedStages: newRunDetails.stages.filter(s => s.status === 'COMPLETED').length,
            stages: newRunDetails.stages.map(s => ({ name: s.stage_name, status: s.status }))
          });
          
          return newRunDetails;
        });
        break;
        
      case 'run_complete':
        // Check if this is a refinement completion (has job_id) or pipeline completion
        if (message.data?.job_id) {
          // This is a refinement completion
          addLog('success', `Image refinement completed: ${message.data.summary || 'Refinement successful'}`);
          toast.success('Image refinement completed! The refined image is now available.');
          // Refresh refinements list immediately
          setTimeout(() => loadRefinements(false), 500);
        } else {
          // This is a pipeline completion
          addLog('success', 'Pipeline run completed successfully!');
          setShowConfetti(true);
          setTimeout(() => setShowConfetti(false), 5000);
          fetchRunDetails(); // Refresh final details
        }
        break;
        
      case 'run_error':
        // Check if this is a refinement error or pipeline error
        if (message.data?.job_id) {
          // This is a refinement error
          const errorMessage = message.data.error_message || 'Refinement failed';
          addLog('error', `Image refinement failed: ${errorMessage}`);
          toast.error(`Image refinement failed: ${errorMessage}`);
          // Refresh refinements list to update status
          setTimeout(() => loadRefinements(false), 500);
        } else {
          // This is a pipeline error
          addLog('error', `Pipeline run failed: ${message.data.error_message}`);
          fetchRunDetails(); // Refresh to get error details
        }
        break;
        
      case 'caption_complete':
        if (message.data?.image_id) {
          // Extract image index from image_id (format: "image_0", "image_1", etc.)
          const imageIndex = parseInt(message.data.image_id.split('_')[1]);
          addLog('success', `Caption generated for Option ${imageIndex + 1}`);
          // Load the updated captions for this image
          setTimeout(() => {
            (async () => {
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
                console.debug('No captions found for image', imageIndex);
              }
            })();
          }, 500);
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
    // Prevent multiple connections for the same run ID
    if (wsManager && wsManager.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected for run:', runId);
      return;
    }

    // Clean up existing connection
    if (wsManager) {
      console.log('Closing existing WebSocket connection before creating new one');
      wsManager.disconnect();
      setWsManager(null);
    }

    console.log('🚀 Initializing new WebSocket connection for run:', runId);
    console.log('🌐 WebSocket URL will be:', `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}/api/v1/ws/${runId}`);

    const newWsManager = new WebSocketManager(
      runId,
      handleWebSocketMessage,
      (error) => {
        addLog('error', 'WebSocket connection error');
        console.error('❌ WebSocket error:', error);
      },
      (event) => {
        console.log('🔌 WebSocket closed:', { code: event.code, reason: event.reason, runId });
        if (event.code !== 1000) { // Not a normal closure
          addLog('warning', 'WebSocket connection lost. Attempting to reconnect...');
        }
      }
    );

    const connectionStart = Date.now();
    newWsManager.connect()
      .then(() => {
        const connectionTime = Date.now() - connectionStart;
        addLog('success', 'Connected to real-time updates');
        setWsManager(newWsManager);
        console.log(`✅ WebSocket connected successfully for run: ${runId} (took ${connectionTime}ms)`);
      })
      .catch((error) => {
        const connectionTime = Date.now() - connectionStart;
        addLog('error', 'Failed to connect to real-time updates');
        console.error(`❌ WebSocket connection failed for run: ${runId} (failed after ${connectionTime}ms):`, error);
        setWsManager(null);
      });
  }, [runId, handleWebSocketMessage, addLog]); // Removed wsManager from dependencies

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
  const openRefinementModal = (imageIndex: number, imagePath: string, parentRefinementJobId?: string) => {
    if (runDetails?.status !== 'COMPLETED') {
      toast.error('Cannot refine images from incomplete runs');
      return;
    }
    
    setRefinementModal({
      open: true,
      imageIndex,
      imagePath,
      parentRefinementJobId
    });
  };

  const closeRefinementModal = () => {
    setRefinementModal({ open: false, imageIndex: null, imagePath: null, parentRefinementJobId: undefined });
  };

  const openRefinementDetailsDialog = async (jobId: string) => {
    setRefinementDetailsDialog({ open: true, jobId, details: null, loading: true });
    
    try {
      const details = await PipelineAPI.getRefinementDetails(jobId);
      setRefinementDetailsDialog(prev => ({ ...prev, details, loading: false }));
    } catch (error: any) {
      console.error('Failed to load refinement details:', error);
      toast.error(`Failed to load refinement details: ${error.message}`);
      setRefinementDetailsDialog(prev => ({ ...prev, loading: false }));
    }
  };

  const closeRefinementDetailsDialog = () => {
    setRefinementDetailsDialog({ open: false, jobId: null, details: null, loading: false });
  };

  const loadRefinements = async (showToastOnError: boolean = false, retryCount: number = 0) => {
    try {
      setRefinementsLoading(true);
      addLog('info', 'Loading refinements...');
      const data = await PipelineAPI.getRefinements(runId);
      const refinementsList = data.refinements || [];
      
      setRefinements(refinementsList);
      
      if (refinementsList.length > 0) {
        addLog('info', `Loaded ${refinementsList.length} refinements`);
      } else {
        addLog('info', 'No refinements found');
      }
      
      return refinementsList;
    } catch (error: any) {
      const errorMsg = `Failed to load refinements: ${error.message}`;
      addLog('warning', errorMsg);
      console.error('Failed to load refinements:', error);
      
      // Retry logic for robustness
      if (retryCount < 2) {
        addLog('info', `Retrying refinements load (attempt ${retryCount + 2}/3)...`);
        setTimeout(() => {
          loadRefinements(showToastOnError, retryCount + 1);
        }, 2000 * (retryCount + 1)); // Exponential backoff: 2s, 4s
        return;
      }
      
      // Only show toast on final retry if requested
      if (showToastOnError) {
        toast.error(errorMsg);
      }
      
      // Set empty refinements on final failure to avoid stale state
      setRefinements([]);
      return [];
    } finally {
      setRefinementsLoading(false);
    }
  };

  // Caption functions
  const openCaptionDialog = (imageIndex: number) => {
    setCaptionImageIndex(imageIndex);
    setCaptionInitialSettings(undefined);
    setCaptionDialogOpen(true);
  };

  const closeCaptionDialog = () => {
    setCaptionDialogOpen(false);
    setCaptionInitialSettings(undefined);
  };

  // Save preset dialog functions
  const openSavePresetDialog = (imageIndex: number) => {
    setSavePresetImageIndex(imageIndex);
    setSavePresetName('');
    setSavePresetDialogOpen(true);
  };

  const closeSavePresetDialog = () => {
    setSavePresetDialogOpen(false);
    setSavePresetName('');
    setSavePresetLoading(false);
  };

  const handleSavePreset = async () => {
    if (!savePresetName.trim()) return;

    setSavePresetLoading(true);
    try {
      await PipelineAPI.savePresetFromResult(runId, {
        name: savePresetName.trim(),
        generation_index: savePresetImageIndex,
      });
      
      toast.success('Style saved as preset successfully!');
      closeSavePresetDialog();
    } catch (error: any) {
      console.error('Failed to save preset:', error);
      toast.error(error.message || 'Failed to save style as preset');
    } finally {
      setSavePresetLoading(false);
    }
  };

  const handleOpenCaptionSettingsDialog = (imageIndex: number, currentSettings: CaptionSettings, currentModelId?: string) => {
    setCaptionImageIndex(imageIndex);
    setCaptionInitialSettings(currentSettings);
    setCaptionDialogOpen(true);
  };

  const handleCaptionGenerate = async (settings: CaptionSettings, modelId?: string) => {
    const imageId = `image_${captionImageIndex}`;
    
    try {
      setCaptionGenerating(prev => ({ ...prev, [captionImageIndex]: true }));
      setCaptionErrors(prev => ({ ...prev, [captionImageIndex]: '' }));
      closeCaptionDialog();
      
      const request = { settings, model_id: modelId };
      const response = await PipelineAPI.generateCaption(runId, imageId, request);
      addLog('info', `Caption generation started for Option ${captionImageIndex + 1}`);
      toast.success('Caption generation started! Check progress in real-time.');
      
    } catch (error: any) {
      const errorMsg = `Failed to generate caption: ${error.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
      setCaptionGenerating(prev => ({ ...prev, [captionImageIndex]: false }));
      setCaptionErrors(prev => ({ ...prev, [captionImageIndex]: errorMsg }));
    }
  };

  const handleCaptionRegenerate = async (imageIndex: number, version?: number, settings?: CaptionSettings, modelId?: string) => {
    const imageId = `image_${imageIndex}`;
    
    try {
      setCaptionGenerating(prev => ({ ...prev, [imageIndex]: true }));
      setCaptionErrors(prev => ({ ...prev, [imageIndex]: '' }));
      
      let response;
      const currentCaptions = imageCaptions[imageIndex] || [];
      const latestVersion = currentCaptions.length > 0 ? Math.max(...currentCaptions.map(c => c.version)) : -1;
      
      const request = { settings, model_id: modelId };
      
      if (version !== undefined) {
        response = await PipelineAPI.regenerateCaption(runId, imageId, version, request);
      } else {
        response = await PipelineAPI.regenerateCaption(runId, imageId, latestVersion, request);
      }
      
      addLog('info', `Caption regeneration started for Option ${imageIndex + 1}`);
      toast.success('Caption regeneration started!');
      
    } catch (error: any) {
      const errorMsg = `Failed to regenerate caption: ${error.message}`;
      addLog('error', errorMsg);
      toast.error(errorMsg);
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
      console.debug('No captions found for image', imageIndex);
    }
  };

  // Helper function to retry caption generation
  const retryCaptionGeneration = (imageIndex: number) => {
    setCaptionErrors(prev => ({ ...prev, [imageIndex]: '' }));
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
    // Use actual number of stages from the backend instead of hardcoded value
    const totalStages = runDetails.stages.length;
    // Count both completed and skipped stages as "done" for progress calculation
    const completedStages = runDetails.stages.filter(s => 
      s.status === 'COMPLETED' || s.status === 'SKIPPED'
    ).length;
    return totalStages > 0 ? (completedStages / totalStages) * 100 : 0;
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getStageStatus = (stageName: string): StageStatus => {
    const stage = runDetails?.stages.find(s => s.stage_name === stageName);
    return stage?.status || 'PENDING' as StageStatus;
  };

  const getStageData = (stageName: string) => {
    return runDetails?.stages.find(s => s.stage_name === stageName);
  };

  // Get display information for any stage (including dynamic ones like style_adaptation)
  const getStageDisplayInfo = (stageName: string) => {
    // Define display info for known stages
    const stageDisplayMap: Record<string, { label: string; description: string }> = {
      'image_eval': { label: 'Image Analysis', description: 'Analyzing uploaded image' },
      'strategy': { label: 'Strategy Generation', description: 'Creating marketing strategies' },
      'style_guide': { label: 'Style Guide', description: 'Defining visual style' },
      'creative_expert': { label: 'Creative Concepts', description: 'Developing visual concepts' },
      'style_adaptation': { label: 'Style Adaptation', description: 'Adapting saved style to new concept' },
      'prompt_assembly': { label: 'Prompt Assembly', description: 'Building generation prompts' },
      'image_generation': { label: 'Image Generation', description: 'Creating final images' },
      'image_assessment': { label: 'Image Assessment', description: 'Evaluating generated images' },
    };

    return stageDisplayMap[stageName] || {
      label: stageName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      description: `Processing ${stageName.replace(/_/g, ' ')}`
    };
  };

  useEffect(() => {
    fetchRunDetails();
  }, [runId, fetchRunDetails]);

  // Separate effect for WebSocket initialization to avoid race conditions
  useEffect(() => {
    console.log('WebSocket effect triggered for run:', runId);
    // Always initialize WebSocket when runId changes or component mounts
    initializeWebSocket();
  }, [runId, initializeWebSocket]);

  // Cleanup effect for WebSocket
  useEffect(() => {
    return () => {
      if (wsManager) {
        console.log('Cleaning up WebSocket connection for run:', runId);
        wsManager.disconnect();
      }
    };
  }, [wsManager, runId]);

  // Additional effect to handle page visibility changes for robustness
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && runDetails) {
        addLog('info', 'Page became visible, refreshing refinements...');
        loadRefinements();
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [runDetails]);

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

  // Helper functions for refinements (removed unused getRefinementTitle function)

  // Helper function to group refinements by their ultimate parent image
  const getGroupedRefinements = () => {
    const groups: Record<string, Array<any>> = {};
    
    // Find ultimate parent for each refinement
    const getUltimateParent = (refinement: any): { parentImageId: string; parentImageType: string; generationIndex: number } => {
      if (refinement.parent_image_type === 'original') {
        return {
          parentImageId: refinement.parent_image_id || `original_${refinement.generation_index}`,
          parentImageType: 'original',
          generationIndex: refinement.generation_index ?? 0
        };
      } else {
        // Find the parent refinement
        const parentRefinement = refinements.find(r => r.job_id === refinement.parent_image_id);
        if (parentRefinement) {
          return getUltimateParent(parentRefinement);
        } else {
          // Fallback: try to extract from image path
          if (refinement.image_path && refinement.image_path.includes('_from_')) {
            const match = refinement.image_path.match(/_from_(\d+)_/);
            if (match) {
              return {
                parentImageId: `original_${match[1]}`,
                parentImageType: 'original',
                generationIndex: parseInt(match[1])
              };
            }
          }
          return {
            parentImageId: 'unknown',
            parentImageType: 'original',
            generationIndex: 0
          };
        }
      }
    };

    // Group refinements by ultimate parent
    refinements.forEach(refinement => {
      const ultimateParent = getUltimateParent(refinement);
      const groupKey = ultimateParent.parentImageId;
      
      if (!groups[groupKey]) {
        groups[groupKey] = [];
      }
      groups[groupKey].push({
        ...refinement,
        ultimateParent
      });
    });

    // Sort groups by generation index and refinements within each group by created_at
    const sortedGroups = Object.keys(groups)
      .sort((a, b) => {
        const aIndex = groups[a][0]?.ultimateParent?.generationIndex ?? 0;
        const bIndex = groups[b][0]?.ultimateParent?.generationIndex ?? 0;
        return aIndex - bIndex;
      })
      .reduce((acc, key) => {
        acc[key] = groups[key].sort((a, b) => 
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        return acc;
      }, {} as Record<string, Array<any>>);

    return sortedGroups;
  };

  // Helper function to check refinement status with clear failure distinction
  const getRefinementDisplayStatus = (refinement: any) => {
    const status = refinement.status;
    const summary = refinement.refinement_summary || '';
    const errorMessage = refinement.error_message || '';
    
    // Handle successful completion with output image
    if (status === 'COMPLETED' && refinement.image_path) {
      return { 
        type: 'success', 
        message: 'Refinement Completed',
        detail: null,
        suggestion: null
      };
    }
    
    // Handle legitimate "no changes needed" cases - check status field and summary
    if (status === 'no_changes_needed' ||
        (status === 'COMPLETED' && !refinement.image_path && summary.toLowerCase().includes('no changes needed')) ||
        summary.toLowerCase().includes('no changes needed') ||
        summary.toLowerCase().includes('no_changes_needed')) {
      return { 
        type: 'info', 
        message: 'No Changes Needed',
        detail: 'The AI determined that your image doesn\'t need the requested changes.',
        suggestion: null
      };
    }
    
    // Handle processing states
    if (status === 'RUNNING' || status === 'PENDING') {
      return { 
        type: 'processing', 
        message: 'Processing...',
        detail: 'Your refinement is being processed.',
        suggestion: null
      };
    }
    
    // All other cases are failures - provide specific error messages
    let errorDetail = 'The refinement process failed.';
    let errorSuggestion = 'Please try creating a new refinement with different settings.';
    
    if (summary.toLowerCase().includes('connection failed')) {
      errorDetail = 'Unable to connect to the AI service.';
      errorSuggestion = 'Check your internet connection and try creating a new refinement.';
    } else if (summary.toLowerCase().includes('rate limit')) {
      errorDetail = 'Too many requests have been made.';
      errorSuggestion = 'Please wait a moment before creating a new refinement.';
    } else if (summary.toLowerCase().includes('api error')) {
      errorDetail = 'The AI service encountered an error.';
      errorSuggestion = 'Please try creating a new refinement with different settings.';
    } else if (summary.toLowerCase().includes('authentication failed')) {
      errorDetail = 'There\'s an issue with the service credentials.';
      errorSuggestion = 'Please contact support.';
    } else if (errorMessage) {
      // Use detailed error message if available
      const parts = errorMessage.split('. ');
      errorDetail = parts[0] || 'The refinement process failed.';
      if (parts.length > 1) {
        errorSuggestion = parts.slice(1).join('. ');
      }
    }
    
    return { 
      type: 'error', 
      message: 'Refinement Failed',
      detail: errorDetail,
      suggestion: errorSuggestion
    };
  };

  const getRefinementTypeLabel = (refinementType: string): string => {
    switch (refinementType) {
      case 'subject':
        return 'Quick Repair';
      case 'text':
        return 'Text Enhancement';
      case 'prompt':
        return 'Custom Enhancement';
      default:
        return 'Image Enhancement';
    }
  };



  const getRefinementTypeColor = (refinementType: string) => {
    switch (refinementType) {
      case 'subject':
        return {
          chipColor: 'primary' as const,
          bgColor: '#e3f2fd',
          borderColor: '#2196f3',
          textColor: '#1565c0',
          chipBgColor: '#1976d2',
          chipTextColor: '#ffffff'
        };
      case 'text':
        return {
          chipColor: 'success' as const,
          bgColor: '#e8f5e8',
          borderColor: '#4caf50',
          textColor: '#2e7d32',
          chipBgColor: '#388e3c',
          chipTextColor: '#ffffff'
        };
      case 'prompt':
        return {
          chipColor: 'secondary' as const,
          bgColor: '#f3e5f5',
          borderColor: '#9c27b0',
          textColor: '#7b1fa2',
          chipBgColor: '#7b1fa2',
          chipTextColor: '#ffffff'
        };
      default:
        return {
          chipColor: 'default' as const,
          bgColor: '#f5f5f5',
          borderColor: '#9e9e9e',
          textColor: '#616161',
          chipBgColor: '#757575',
          chipTextColor: '#ffffff'
        };
    }
  };

  // Helper function to calculate refinement duration
  const calculateRefinementDuration = (refinement: any): string => {
    if (!refinement.created_at || !refinement.completed_at) {
      return 'N/A';
    }
    
    const start = new Date(refinement.created_at);
    const end = new Date(refinement.completed_at);
    const durationMs = end.getTime() - start.getTime();
    const durationSeconds = durationMs / 1000;
    
    if (durationSeconds < 60) {
      return `${durationSeconds.toFixed(1)}s`;
    } else {
      const minutes = Math.floor(durationSeconds / 60);
      const seconds = durationSeconds % 60;
      return `${minutes}m ${seconds.toFixed(0)}s`;
    }
  };

  // Helper function to get the correct immediate parent image path for comparison
  const getImmediateParentImagePath = (refinement: any): string => {
    try {
      if (refinement.parent_image_type === 'original') {
        // Parent is an original generated image
        // Find by strategy_index instead of assuming array index
        const originalImage = generatedImages.find(img => img.strategy_index === refinement.generation_index);
        if (originalImage?.image_path) {
          console.log(`Found parent image for refinement: ${originalImage.image_path}`);
          return originalImage.image_path;
        } else {
          console.warn(`Could not find original image for generation_index: ${refinement.generation_index}`);
          // Fallback to array index if strategy_index doesn't match
          const fallbackImage = generatedImages[refinement.generation_index || 0];
          return fallbackImage?.image_path || '';
        }
      } else {
        // Parent is another refinement - find it in the refinements list
        const parentRefinement = refinements.find(r => r.job_id === refinement.parent_image_id);
        if (parentRefinement && parentRefinement.image_path) {
          console.log(`Found parent refinement: ${parentRefinement.image_path}`);
          return parentRefinement.image_path;
        } else {
          console.warn(`Could not find parent refinement with job_id: ${refinement.parent_image_id}`);
          // Fallback: try to get from the ultimate parent
          const ultimateParent = refinement.ultimateParent;
          if (ultimateParent && ultimateParent.generationIndex !== undefined) {
            const originalImage = generatedImages.find(img => img.strategy_index === ultimateParent.generationIndex);
            return originalImage?.image_path || '';
          }
          return '';
        }
      }
    } catch (error) {
      console.error('Error getting immediate parent image path:', error);
      return '';
    }
  };

  // Helper function to set selected image with context
  const setSelectedImageWithContext = async (
    runId: string,
    imagePath: string,
    type: 'original' | 'refinement', 
    refinementData?: any
  ) => {
    try {
      console.log(`Loading image for modal: type=${type}, imagePath=${imagePath}`);
      
      // Get blob URL for the image
      const blobUrl = await PipelineAPI.getImageBlobUrl(runId, imagePath);
      setSelectedImage(blobUrl);
      
      if (type === 'refinement' && refinementData) {
        console.log('Refinement data:', refinementData);
        const parentImagePath = getImmediateParentImagePath(refinementData);
        console.log(`Parent image path: ${parentImagePath}`);
        
        // If we have a parent image path, also get its blob URL for the comparison slider
        let parentImageBlobUrl = '';
        if (parentImagePath) {
          try {
            parentImageBlobUrl = await PipelineAPI.getImageBlobUrl(runId, parentImagePath);
            console.log('Successfully loaded parent image blob URL for comparison');
          } catch (parentError) {
            console.error('Failed to load parent image blob URL:', parentError);
            // Fallback to direct URL
            parentImageBlobUrl = PipelineAPI.getFileUrl(runId, parentImagePath);
            console.log(`Using fallback URL for parent image: ${parentImageBlobUrl}`);
          }
        } else {
          console.warn('No parent image path found - comparison will not be available');
        }
        
        setSelectedImageContext({
          type: 'refinement',
          refinementData,
          parentImagePath,
          parentImageBlobUrl // Add blob URL for comparison slider
        });
        
        console.log(`Modal will show: ${parentImagePath ? 'comparison slider' : 'single image'}`);
      } else {
        setSelectedImageContext({
          type: 'original'
        });
      }
    } catch (error) {
      console.error('Failed to load image for modal:', error);
      toast.error(`Failed to load image: ${error.message}`);
      // Fallback to direct URL (might not work with ngrok but better than nothing)
      setSelectedImage(PipelineAPI.getFileUrl(runId, imagePath));
      setSelectedImageContext({
        type: type
      });
    }
  };

  // Helper function to clear selected image and context
  const clearSelectedImage = () => {
    setSelectedImage(null);
    setSelectedImageContext(null);
  };

  // Helper function to get chain refinement name
  const getChainRefinementName = (refinement: any, index: number, group: Array<any>): string => {
    if (refinement.parent_image_type === 'original') {
      return `Refinement #${index + 1}`;
    } else {
      // This is a chain refinement - find its immediate parent
      const parentRefinement = group.find(r => r.job_id === refinement.parent_image_id);
      if (parentRefinement) {
        const parentIndex = group.findIndex(r => r.job_id === refinement.parent_image_id);
        return `Refinement #${parentIndex + 1} → #${index + 1}`;
      } else {
        // Fallback if parent not found in same group
        return `Chain Refinement #${index + 1}`;
      }
    }
  };

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
    <div>
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

          {/* Style Adaptation Banner */}
          {runDetails.preset_type === 'STYLE_RECIPE' && runDetails.parent_preset && (
            <Alert severity="info" icon={<AutoAwesomeIcon />} sx={{ mb: 3 }}>
              Results adapted from Style Recipe: <strong>{runDetails.parent_preset.name}</strong>
            </Alert>
          )}

          {/* Main Content - Left/Right Split */}
          <Grid container spacing={4}>
            {/* LEFT SIDE - Main Results */}
            <Grid item xs={12} lg={8}>

          {/* Generated Images Section */}
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
                            <ImageWithAuth
                              runId={runId}
                              imagePath={result.image_path}
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
                              onClick={() => result.image_path && setSelectedImageWithContext(
                                runId,
                                result.image_path,
                                'original'
                              )}
                              alt={`Generated image option ${result.strategy_index + 1}`}
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
                                onClick={() => result.image_path && setSelectedImageWithContext(
                                  runId,
                                  result.image_path,
                                  'original'
                                )}
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
                            <Tooltip title="Save this style as a preset">
                              <Button
                                size="small"
                                startIcon={<BookmarkAddIcon />}
                                onClick={() => openSavePresetDialog(result.strategy_index)}
                                color="secondary"
                                variant="outlined"
                                sx={{ fontWeight: 500, fontSize: '0.75rem' }}
                              >
                                Save Style
                              </Button>
                            </Tooltip>
                          </Box>
                          
                          {/* Assessment Indicators */}
                          {result.assessment ? (
                            <ImageAssessmentIndicators 
                              assessmentData={result.assessment}
                              imageIndex={result.strategy_index}
                              isExpanded={assessmentDropdownStates[result.strategy_index] || false}
                              onToggleExpanded={() => toggleAssessmentDropdown(result.strategy_index)}
                            />
                          ) : (
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

                          {/* Consistency Metrics for Style Recipes */}
                          {result.assessment?.consistency_metrics && (
                            <Box sx={{ mt: 2, p: 2, backgroundColor: 'primary.50', borderRadius: 2, border: 1, borderColor: 'primary.200' }}>
                              <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main', mb: 1 }}>
                                🎯 Style Consistency
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                                {result.assessment.consistency_metrics.overall_consistency_score && (
                                  <Chip
                                    label={`Overall: ${Math.round(result.assessment.consistency_metrics.overall_consistency_score * 100)}%`}
                                    size="small"
                                    color={result.assessment.consistency_metrics.overall_consistency_score >= 0.8 ? 'success' : 
                                           result.assessment.consistency_metrics.overall_consistency_score >= 0.6 ? 'warning' : 'error'}
                                    variant="filled"
                                    sx={{ fontSize: '0.7rem', fontWeight: 500 }}
                                  />
                                )}
                                {result.assessment.consistency_metrics.clip_similarity && (
                                  <Chip
                                    label={`CLIP: ${Math.round(result.assessment.consistency_metrics.clip_similarity * 100)}%`}
                                    size="small"
                                    variant="outlined"
                                    sx={{ fontSize: '0.7rem' }}
                                  />
                                )}
                                {result.assessment.consistency_metrics.color_histogram_similarity && (
                                  <Chip
                                    label={`Color: ${Math.round(result.assessment.consistency_metrics.color_histogram_similarity * 100)}%`}
                                    size="small"
                                    variant="outlined"
                                    sx={{ fontSize: '0.7rem' }}
                                  />
                                )}
                              </Box>
                              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                Shows how closely this result matches your selected style recipe
                              </Typography>
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
                              onRegenerate={(settings, modelId) => handleCaptionRegenerate(result.strategy_index, undefined, settings, modelId)}
                              onOpenSettingsDialog={(currentSettings, currentModelId) => handleOpenCaptionSettingsDialog(result.strategy_index, currentSettings, currentModelId)}
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

          {/* Refined Images - Grouped by Parent Image */}
          {(refinements.length > 0 || (runDetails?.status === 'COMPLETED' && !refinementsLoading)) && (
            <Box sx={{ mb: 4 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
                <Typography variant="h5" sx={{ fontWeight: 600, letterSpacing: '-0.01em' }}>
                  Refined Images {refinements.length > 0 && `(${refinements.length})`}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    size="small"
                    startIcon={refinementsLoading ? <CircularProgress size={16} /> : <RefreshIcon />}
                    onClick={() => loadRefinements(true)}
                    variant="outlined"
                    disabled={refinementsLoading}
                    sx={{ fontWeight: 500 }}
                  >
                    {refinementsLoading ? 'Loading...' : 'Refresh'}
                  </Button>
                </Box>
              </Box>
              
              {refinements.length > 0 ? (
                (() => {
                  const groupedRefinements = getGroupedRefinements();
                  const groupKeys = Object.keys(groupedRefinements);
                  
                  return (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      {groupKeys.map((groupKey) => {
                        const group = groupedRefinements[groupKey];
                        const firstRefinement = group[0];
                        const originalImageIndex = firstRefinement.ultimateParent.generationIndex;
                        // Ensure we have a valid image - check both the index and that the image exists
                        const originalImage = generatedImages[originalImageIndex];
                        const isExpanded = refinementGroupsExpanded[groupKey] ?? true;
                        const showAllInGroup = showAllRefinementsInGroup[groupKey] ?? false;
                        const visibleRefinements = showAllInGroup ? group : group.slice(0, INITIAL_REFINEMENTS_PER_GROUP);
                        const hasMoreRefinements = group.length > INITIAL_REFINEMENTS_PER_GROUP;
                        
                        return (
                          <Paper key={groupKey} sx={{ border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
                            {/* Group Header */}
                            <Box 
                              sx={{ 
                                p: 2, 
                                backgroundColor: 'grey.50', 
                                borderBottom: isExpanded ? 1 : 0, 
                                borderColor: 'divider',
                                cursor: 'pointer',
                                '&:hover': { backgroundColor: 'grey.100' }
                              }}
                              onClick={() => setRefinementGroupsExpanded(prev => ({ 
                                ...prev, 
                                [groupKey]: !isExpanded 
                              }))}
                            >
                              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                  {/* Parent Image Thumbnail */}
                                  {originalImage?.image_path ? (
                                    <ImageWithAuth
                                      runId={runId}
                                      imagePath={originalImage.image_path}
                                      sx={{
                                        width: 48,
                                        height: 48,
                                        objectFit: 'cover',
                                        borderRadius: 1,
                                        border: 1,
                                        borderColor: 'divider'
                                      }}
                                      alt={`Original image option ${originalImageIndex + 1}`}
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
                                  
                                  <Box>
                                    <Typography variant="h6" sx={{ fontWeight: 600, color: 'primary.main' }}>
                                      Option {originalImageIndex + 1} Refinements
                                    </Typography>
                                    <Typography variant="body2" color="textSecondary">
                                      {group.length} refinement{group.length !== 1 ? 's' : ''}
                                    </Typography>
                                  </Box>
                                </Box>
                                
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                  <Chip 
                                    label={`${group.length} refinement${group.length !== 1 ? 's' : ''}`}
                                    size="small"
                                    color="primary"
                                    variant="outlined"
                                  />
                                  <ExpandMoreIcon 
                                    sx={{ 
                                      transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                                      transition: 'transform 0.2s ease'
                                    }} 
                                  />
                                </Box>
                              </Box>
                            </Box>
                            
                            {/* Group Content */}
                            {isExpanded && (
                              <Box sx={{ p: 2 }}>
                                <Grid container spacing={2}>
                                  {visibleRefinements.map((refinement, index) => {
                                    const displayStatus = getRefinementDisplayStatus(refinement);
                                    const typeColors = getRefinementTypeColor(refinement.refinement_type);
                                    const refinementName = getChainRefinementName(refinement, index, group);
                                    
                                    return (
                                      <Grid item xs={12} sm={6} md={4} key={refinement.job_id}>
                                        <Paper sx={{ p: 2, height: '100%', border: 1, borderColor: 'divider' }}>
                                          {refinement.image_path ? (
                                            <Box>
                                              <Box sx={{ position: 'relative', mb: 2 }}>
                                                <ImageWithAuth
                                                  runId={runId}
                                                  imagePath={refinement.image_path}
                                                  sx={{
                                                    width: '100%',
                                                    height: 200,
                                                    objectFit: 'cover',
                                                    borderRadius: 1,
                                                    cursor: 'pointer',
                                                    transition: 'all 0.2s ease-in-out',
                                                    '&:hover': {
                                                      transform: 'scale(1.02)',
                                                      boxShadow: 2,
                                                    }
                                                  }}
                                                  onClick={() => setSelectedImageWithContext(
                                                    runId,
                                                    refinement.image_path,
                                                    'refinement',
                                                    refinement
                                                  )}
                                                  alt={`Refined image - ${refinementName}`}
                                                />
                                                <Chip
                                                  label={getRefinementTypeLabel(refinement.refinement_type)}
                                                  size="small"
                                                  sx={{
                                                    position: 'absolute',
                                                    top: 8,
                                                    left: 8,
                                                    fontWeight: 600,
                                                    fontSize: '0.7rem',
                                                    backgroundColor: typeColors.chipBgColor,
                                                    color: typeColors.chipTextColor,
                                                    '&:hover': {
                                                      backgroundColor: typeColors.chipBgColor,
                                                    }
                                                  }}
                                                />
                                              </Box>
                                              
                                              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1, color: 'secondary.main' }}>
                                                {refinementName}
                                              </Typography>
                                              
                                              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                                                <Button
                                                  size="small"
                                                  startIcon={<ZoomInIcon />}
                                                  onClick={() => setSelectedImageWithContext(
                                                    runId,
                                                    refinement.image_path,
                                                    'refinement',
                                                    refinement
                                                  )}
                                                  color="primary"
                                                  variant="outlined"
                                                  sx={{ fontSize: '0.75rem' }}
                                                >
                                                  View
                                                </Button>
                                                <Button
                                                  size="small"
                                                  startIcon={<DownloadIcon />}
                                                  onClick={() => downloadImage(refinement.image_path, refinement.image_path)}
                                                  color="primary"
                                                  variant="contained"
                                                  sx={{ fontSize: '0.75rem' }}
                                                >
                                                  Download
                                                </Button>
                                                <Button
                                                  size="small"
                                                  startIcon={<InfoIcon />}
                                                  onClick={() => openRefinementDetailsDialog(refinement.job_id)}
                                                  color="info"
                                                  variant="outlined"
                                                  sx={{ fontSize: '0.75rem' }}
                                                >
                                                  Details
                                                </Button>
                                                <Button
                                                  size="small"
                                                  startIcon={<AutoFixHighIcon />}
                                                  onClick={() => openRefinementModal(-1, refinement.image_path, refinement.job_id)}
                                                  color="secondary"
                                                  variant="contained"
                                                  sx={{ fontSize: '0.75rem' }}
                                                >
                                                  Refine
                                                </Button>
                                              </Box>
                                              
                                              <Box sx={{ display: 'flex', justifyContent: 'space-between', color: 'textSecondary', fontSize: '0.8rem' }}>
                                                <span>Cost: ${refinement.cost_usd?.toFixed(4) || '0.0000'}</span>
                                                <span>Duration: {calculateRefinementDuration(refinement)}</span>
                                              </Box>
                                            </Box>
                                          ) : (
                                            <Box sx={{ textAlign: 'center', py: 4 }}>
                                              {(() => {
                                                switch (displayStatus.type) {
                                                  case 'success':
                                                    return (
                                                      <>
                                                        <CheckCircleIcon color="success" sx={{ fontSize: 48, mb: 1 }} />
                                                        <Typography variant="h6" color="success.main">{displayStatus.message}</Typography>
                                                      </>
                                                    );
                                                  case 'processing':
                                                    return (
                                                      <>
                                                        <CircularProgress sx={{ mb: 1 }} />
                                                        <Typography variant="h6" color="primary">{displayStatus.message}</Typography>
                                                      </>
                                                    );
                                                  case 'info':
                                                    return (
                                                      <>
                                                        <CheckCircleIcon color="info" sx={{ fontSize: 48, mb: 1 }} />
                                                        <Typography variant="h6" color="info.main">{displayStatus.message}</Typography>
                                                      </>
                                                    );
                                                  case 'warning':
                                                    return (
                                                      <>
                                                        <WarningIcon color="warning" sx={{ fontSize: 48, mb: 1 }} />
                                                        <Typography variant="h6" color="warning.main">{displayStatus.message}</Typography>
                                                        {displayStatus.detail && (
                                                          <Typography variant="body2" color="textSecondary" sx={{ mt: 1, mb: 1 }}>
                                                            {displayStatus.detail}
                                                          </Typography>
                                                        )}
                                                        {displayStatus.suggestion && (
                                                          <Alert severity="info" sx={{ mt: 1, textAlign: 'left' }}>
                                                            <Typography variant="body2">
                                                              <strong>Suggestion:</strong> {displayStatus.suggestion}
                                                            </Typography>
                                                          </Alert>
                                                        )}
                                                      </>
                                                    );
                                                  case 'error':
                                                  default:
                                                    return (
                                                      <>
                                                        <ErrorIcon color="error" sx={{ fontSize: 48, mb: 1 }} />
                                                        <Typography variant="h6" color="error">{displayStatus.message}</Typography>
                                                        {displayStatus.detail && (
                                                          <Typography variant="body2" color="textSecondary" sx={{ mt: 1, mb: 1 }}>
                                                            {displayStatus.detail}
                                                          </Typography>
                                                        )}
                                                        {displayStatus.suggestion && (
                                                          <Alert severity="warning" sx={{ mt: 1, textAlign: 'left' }}>
                                                            <Typography variant="body2">
                                                              <strong>Suggestion:</strong> {displayStatus.suggestion}
                                                            </Typography>
                                                          </Alert>
                                                        )}
                                                      </>
                                                    );
                                                }
                                              })()}
                                              
                                              {/* Additional information for failed refinements */}
                                              <Typography variant="subtitle2" sx={{ fontWeight: 600, mt: 2, color: 'secondary.main' }}>
                                                {getRefinementTypeLabel(refinement.refinement_type)} - {refinementName}
                                              </Typography>
                                              <Box sx={{ display: 'flex', justifyContent: 'center', color: 'textSecondary', fontSize: '0.8rem', mt: 1 }}>
                                                <span>Duration: {calculateRefinementDuration(refinement)}</span>
                                              </Box>
                                            </Box>
                                          )}
                                        </Paper>
                                      </Grid>
                                    );
                                  })}
                                </Grid>
                                
                                {/* Show More/Less Button */}
                                {hasMoreRefinements && (
                                  <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                                    <Button
                                      variant="outlined"
                                      size="small"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setShowAllRefinementsInGroup(prev => ({
                                          ...prev,
                                          [groupKey]: !showAllInGroup
                                        }));
                                      }}
                                      sx={{ fontWeight: 500 }}
                                    >
                                      {showAllInGroup 
                                        ? `Show Less (${INITIAL_REFINEMENTS_PER_GROUP} of ${group.length})`
                                        : `Show More (${group.length - INITIAL_REFINEMENTS_PER_GROUP} more)`
                                      }
                                    </Button>
                                  </Box>
                                )}
                              </Box>
                            )}
                          </Paper>
                        );
                      })}
                    </Box>
                  );
                })()
              ) : (
                runDetails?.status === 'COMPLETED' && generatedImages.length > 0 && (
                  <Paper sx={{ p: 4, textAlign: 'center', backgroundColor: 'grey.50', border: 1, borderColor: 'divider' }}>
                    <AutoAwesomeIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
                    <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                      Ready to Refine Your Images!
                    </Typography>
                                                        <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
                                      Choose which generated image you&apos;d like to enhance with AI-powered refinements
                                    </Typography>
                    
                    <Grid container spacing={2} sx={{ maxWidth: 600, mx: 'auto' }}>
                      {generatedImages.map((image, index) => (
                        <Grid item xs={12} sm={6} md={4} key={index}>
                          <Paper
                            sx={{
                              p: 2,
                              border: 1,
                              borderColor: 'divider',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              '&:hover': {
                                borderColor: 'primary.main',
                                boxShadow: 2,
                                transform: 'translateY(-2px)'
                              }
                            }}
                            onClick={() => openRefinementModal(index, image.image_path || '')}
                          >
                            <ImageWithAuth
                              runId={runId}
                              imagePath={image.image_path || ''}
                              sx={{
                                width: '100%',
                                height: 120,
                                objectFit: 'cover',
                                borderRadius: 1,
                                mb: 1
                              }}
                              alt={`Option ${index + 1} for refinement`}
                            />
                            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main', mb: 1 }}>
                              Option {index + 1}
                            </Typography>
                            <Button
                              fullWidth
                              variant="outlined"
                              startIcon={<AutoFixHighIcon />}
                              size="small"
                              sx={{ fontWeight: 500 }}
                            >
                              Refine This
                            </Button>
                          </Paper>
                        </Grid>
                      ))}
                    </Grid>
                  </Paper>
                )
              )}
            </Box>
          )}

          {/* Visual Pipeline Progress */}
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h5" sx={{ fontWeight: 600, letterSpacing: '-0.01em' }}>
                Pipeline Progress
              </Typography>
              <Typography variant="body1" color="textSecondary" sx={{ fontWeight: 500 }}>
                {runDetails.stages?.filter(s => s.status === 'COMPLETED' || s.status === 'SKIPPED').length || 0} / {runDetails.stages?.length || 0} stages
              </Typography>
            </Box>
            
            {/* Visual Pipeline Stages Grid - Dynamic based on actual stages */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
              {runDetails.stages && runDetails.stages.length > 0 ? (
                runDetails.stages
                  .sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0)) // Sort by stage order
                  .map((stage) => {
                    const displayInfo = getStageDisplayInfo(stage.stage_name);
                    
                    return (
                      <Grid 
                        item 
                        xs={12} 
                        sm={6} 
                        md={4} 
                        lg={2} 
                        key={stage.stage_name} 
                        sx={{ display: 'flex', flexDirection: 'column' }}
                      >
                        <PipelineStageBox
                          stage={{ 
                            name: stage.stage_name, 
                            label: displayInfo.label, 
                            description: displayInfo.description 
                          }}
                          status={stage.status}
                          message={stage.message}
                          duration={stage.duration_seconds}
                        />
                      </Grid>
                    );
                  })
              ) : (
                <Grid item xs={12}>
                  <Typography variant="body2" color="textSecondary" sx={{ textAlign: 'center', py: 2 }}>
                    Loading pipeline stages...
                  </Typography>
                </Grid>
              )}
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

              {/* Input Display - Conditional */}
              {runDetails.preset_type === 'STYLE_RECIPE' ? (
                <AdaptationContext run={runDetails} />
              ) : (
                <Paper sx={{ p: 3, mb: 3, borderRadius: 2, border: 1, borderColor: 'divider' }}>
                  <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                    Form Input
                  </Typography>
                <Grid container spacing={3}>
                  {/* Basic Configuration Section */}
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
                      Basic Configuration
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6} md={4}>
                        <Typography variant="caption" color="textSecondary">Mode</Typography>
                        <Typography variant="body2" sx={{ textTransform: 'capitalize', fontWeight: 500, mt: 0.5 }}>
                          {runDetails.mode?.replace('_', ' ') || 'N/A'}
                        </Typography>
                      </Grid>
                      
                      <Grid item xs={12} sm={6} md={4}>
                        <Typography variant="caption" color="textSecondary">Target Platform</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                          {runDetails.platform_name || 'N/A'}
                        </Typography>
                      </Grid>
                      
                      <Grid item xs={12} sm={6} md={4}>
                        <Typography variant="caption" color="textSecondary">Creativity Level</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                          Level {runDetails.creativity_level}/3
                        </Typography>
                      </Grid>

                      {runDetails.task_type && (
                        <Grid item xs={12} sm={6} md={4}>
                          <Typography variant="caption" color="textSecondary">Task Type</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                            {runDetails.task_type}
                          </Typography>
                        </Grid>
                      )}

                      {runDetails.language && (
                        <Grid item xs={12} sm={6} md={4}>
                          <Typography variant="caption" color="textSecondary">Language</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                            {runDetails.language}
                          </Typography>
                        </Grid>
                      )}
                    </Grid>
                  </Grid>

                  {/* Content Input Section */}
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
                      Content Input
                    </Typography>
                    <Grid container spacing={2}>
                      {runDetails.prompt && (
                        <Grid item xs={12}>
                          <Typography variant="caption" color="textSecondary">User Prompt</Typography>
                          <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 1 }}>
                            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                              {runDetails.prompt}
                            </Typography>
                          </Paper>
                        </Grid>
                      )}

                      {runDetails.task_description && (
                        <Grid item xs={12}>
                          <Typography variant="caption" color="textSecondary">Task Description</Typography>
                          <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 1 }}>
                            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem' }}>
                              {runDetails.task_description}
                            </Typography>
                          </Paper>
                        </Grid>
                      )}

                      {runDetails.has_image_reference && (
                        <Grid item xs={12}>
                          <Typography variant="caption" color="textSecondary">Image Reference</Typography>
                          <Box sx={{ mt: 1 }}>
                            <Grid container spacing={2} alignItems="center">
                              <Grid item xs={12} sm={6}>
                                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                  📎 {runDetails.image_filename || 'Uploaded image'}
                                </Typography>
                              </Grid>
                            </Grid>
                            {runDetails.image_instruction && (
                              <Paper sx={{ p: 2, mt: 1, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 1 }}>
                                <Typography variant="caption" color="textSecondary">Image Instruction:</Typography>
                                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.9rem', mt: 0.5 }}>
                                  {runDetails.image_instruction}
                                </Typography>
                              </Paper>
                            )}
                          </Box>
                        </Grid>
                      )}
                    </Grid>
                  </Grid>

                  {/* Processing Options Section */}
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
                      Processing Options
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6} md={4}>
                        <Typography variant="caption" color="textSecondary">Render Text</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5, color: runDetails.render_text ? 'success.main' : 'text.secondary' }}>
                          {runDetails.render_text ? '✓ Yes' : '✗ No'}
                        </Typography>
                      </Grid>

                      <Grid item xs={12} sm={6} md={4}>
                        <Typography variant="caption" color="textSecondary">Apply Branding</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5, color: runDetails.apply_branding ? 'success.main' : 'text.secondary' }}>
                          {runDetails.apply_branding ? '✓ Yes' : '✗ No'}
                        </Typography>
                      </Grid>


                    </Grid>
                  </Grid>

                  {/* Brand Kit Section */}
                  {runDetails.apply_branding && runDetails.brand_kit && (
                    <Grid item xs={12}>
                      <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
                        Brand Kit Applied
                      </Typography>
                      <Paper sx={{ p: 3, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 2 }}>
                        <Grid container spacing={3}>
                          {/* Brand Colors */}
                          {runDetails.brand_kit.colors && runDetails.brand_kit.colors.length > 0 && (
                            <Grid item xs={12}>
                              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
                                Brand Colors ({runDetails.brand_kit.colors.length})
                              </Typography>
                              <Box sx={{ 
                                display: 'flex', 
                                flexWrap: 'wrap',
                                gap: 1,
                                alignItems: 'center'
                              }}>
                                {runDetails.brand_kit.colors.map((color, index) => (
                                  <Box key={index} sx={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: 1,
                                    p: 1,
                                    backgroundColor: 'background.paper',
                                    borderRadius: 1,
                                    border: 1,
                                    borderColor: 'divider'
                                  }}>
                                    <Box
                                      sx={{
                                        width: 20,
                                        height: 20,
                                        backgroundColor: color,
                                        borderRadius: '50%',
                                        border: 1,
                                        borderColor: 'grey.300',
                                        boxShadow: 1,
                                        flexShrink: 0
                                      }}
                                    />
                                    <Typography variant="caption" sx={{ 
                                      fontFamily: 'monospace', 
                                      fontSize: '0.75rem',
                                      fontWeight: 500,
                                      color: 'text.primary'
                                    }}>
                                      {color.toUpperCase()}
                                    </Typography>
                                  </Box>
                                ))}
                              </Box>
                            </Grid>
                          )}
                          
                          {/* Brand Voice */}
                          {runDetails.brand_kit.brand_voice_description && (
                            <Grid item xs={12} md={runDetails.brand_kit.colors?.length ? 12 : 6}>
                              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
                                Brand Voice & Tone
                              </Typography>
                              <Box sx={{ 
                                p: 2, 
                                backgroundColor: 'background.paper', 
                                borderRadius: 1, 
                                border: 1, 
                                borderColor: 'divider' 
                              }}>
                                <Typography variant="body2" sx={{ 
                                  fontSize: '0.9rem', 
                                  lineHeight: 1.5,
                                  fontStyle: 'italic',
                                  color: 'text.primary'
                                }}>
                                  "{runDetails.brand_kit.brand_voice_description}"
                                </Typography>
                              </Box>
                            </Grid>
                          )}
                          
                          {/* Logo Information */}
                          {(runDetails.brand_kit.logo_analysis || runDetails.brand_kit.saved_logo_path_in_run_dir) && (
                            <Grid item xs={12} md={runDetails.brand_kit.brand_voice_description ? 12 : 6}>
                              <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 1, fontWeight: 600 }}>
                                Brand Logo
                              </Typography>
                              <Box sx={{ 
                                p: 2, 
                                backgroundColor: 'background.paper', 
                                borderRadius: 1, 
                                border: 1, 
                                borderColor: 'divider' 
                              }}>
                                {runDetails.brand_kit.saved_logo_path_in_run_dir && (
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                    <Box sx={{ 
                                      width: 40, 
                                      height: 40, 
                                      borderRadius: 1,
                                      overflow: 'hidden',
                                      border: 1,
                                      borderColor: 'divider',
                                      backgroundColor: 'background.default',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'center',
                                      padding: 0.5
                                    }}>
                                      <ImageWithAuth
                                        runId={runId}
                                        imagePath={runDetails.brand_kit.saved_logo_path_in_run_dir.split('/').pop() || 'logo.png'}
                                        alt="Brand logo"
                                        sx={{ 
                                          maxWidth: '100%', 
                                          maxHeight: '100%', 
                                          objectFit: 'contain',
                                          display: 'block'
                                        }}
                                      />
                                    </Box>
                                    <Typography variant="body2" sx={{ fontSize: '0.9rem', fontWeight: 500 }}>
                                      {runDetails.brand_kit.saved_logo_path_in_run_dir.split('/').pop() || 'Logo file'}
                                    </Typography>
                                  </Box>
                                )}
                                {runDetails.brand_kit.logo_analysis?.style_description && (
                                  <Typography variant="body2" sx={{ 
                                    fontSize: '0.85rem', 
                                    color: 'text.secondary',
                                    fontStyle: 'italic' 
                                  }}>
                                    Style: {runDetails.brand_kit.logo_analysis.style_description}
                                  </Typography>
                                )}
                              </Box>
                            </Grid>
                          )}
                          
                          {/* Empty state */}
                          {(!runDetails.brand_kit.colors || runDetails.brand_kit.colors.length === 0) && 
                           !runDetails.brand_kit.brand_voice_description && 
                           !runDetails.brand_kit.logo_analysis && 
                           !runDetails.brand_kit.saved_logo_path_in_run_dir && (
                            <Grid item xs={12}>
                              <Box sx={{ 
                                p: 3, 
                                textAlign: 'center',
                                backgroundColor: 'background.paper', 
                                borderRadius: 1, 
                                border: 1, 
                                borderColor: 'divider',
                                borderStyle: 'dashed'
                              }}>
                                <Typography variant="body2" color="textSecondary" sx={{ fontStyle: 'italic' }}>
                                  Brand kit was applied but no specific details are available for display
                                </Typography>
                              </Box>
                            </Grid>
                          )}
                        </Grid>
                      </Paper>
                    </Grid>
                  )}

                  {/* Marketing Goals Section */}
                  {(runDetails.marketing_audience || runDetails.marketing_objective || runDetails.marketing_voice || runDetails.marketing_niche) && (
                    <Grid item xs={12}>
                      <Typography variant="subtitle2" color="primary" sx={{ fontWeight: 600, mb: 2 }}>
                        Marketing Goals
                      </Typography>
                      <Paper sx={{ p: 3, backgroundColor: 'grey.50', border: 1, borderColor: 'divider', borderRadius: 2 }}>
                        <Grid container spacing={2}>
                          {runDetails.marketing_audience && (
                            <Grid item xs={12} sm={6}>
                              <Typography variant="caption" color="textSecondary">Target Audience</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                                {runDetails.marketing_audience}
                              </Typography>
                            </Grid>
                          )}
                          {runDetails.marketing_objective && (
                            <Grid item xs={12} sm={6}>
                              <Typography variant="caption" color="textSecondary">Objective</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                                {runDetails.marketing_objective}
                              </Typography>
                            </Grid>
                          )}
                          {runDetails.marketing_voice && (
                            <Grid item xs={12} sm={6}>
                              <Typography variant="caption" color="textSecondary">Voice & Tone</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                                {runDetails.marketing_voice}
                              </Typography>
                            </Grid>
                          )}
                          {runDetails.marketing_niche && (
                            <Grid item xs={12} sm={6}>
                              <Typography variant="caption" color="textSecondary">Target Niche</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 500, mt: 0.5 }}>
                                {runDetails.marketing_niche}
                              </Typography>
                            </Grid>
                          )}
                        </Grid>
                      </Paper>
                    </Grid>
                  )}
                </Grid>
              </Paper>
              )}

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
                    {runDetails.preset_type === 'STYLE_RECIPE' && (
                      <Chip 
                        label="Style Adaptation" 
                        size="small" 
                        color="primary" 
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    )}
                  </Box>
                  
                  {/* Run Type Context */}
                  <Box sx={{ mb: 2, p: 1.5, backgroundColor: 'warning.100', borderRadius: 1, border: 1, borderColor: 'warning.300' }}>
                    <Typography variant="caption" color="warning.dark" sx={{ fontWeight: 500 }}>
                      {runDetails.preset_type === 'STYLE_RECIPE' 
                        ? `Style Adaptation Run: ${runDetails.stages?.filter(s => s.status === 'COMPLETED').length || 0} stages completed, ${runDetails.stages?.filter(s => s.status === 'SKIPPED').length || 0} stages skipped`
                        : `Regular Pipeline Run: ${runDetails.stages?.filter(s => s.status === 'COMPLETED').length || 0} stages completed`
                      }
                    </Typography>
                  </Box>
                  
                  {runDetails.stages
                    .filter(stage => stage.output_data)
                    .sort((a, b) => (a.stage_order || 0) - (b.stage_order || 0))
                    .map((stage) => (
                      <Accordion key={`output-${stage.stage_name}`} sx={{ mb: 1 }}>
                        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 600, textTransform: 'capitalize' }}>
                              {stage.stage_name.replace('_', ' ')} Results
                            </Typography>
                            <Chip 
                              label={stage.status} 
                              size="small" 
                              color={stage.status === 'COMPLETED' ? 'success' : stage.status === 'SKIPPED' ? 'warning' : 'default'}
                              variant="outlined"
                              sx={{ fontSize: '0.7rem', ml: 1 }}
                            />
                          </Box>
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
                    ))}
                    
                  {runDetails.stages.filter(stage => stage.output_data).length === 0 && (
                    <Box sx={{ p: 2, textAlign: 'center', color: 'warning.dark' }}>
                      <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
                        No stage output data available for this run
                      </Typography>
                    </Box>
                  )}
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
                        <React.Fragment>
                          {logs.map((log, index) => (
                            <div
                              key={index}
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
                            </div>
                          ))}
                        </React.Fragment>
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
        onClose={clearSelectedImage}
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
            {selectedImageContext?.type === 'refinement' 
              ? `Refined Image - ${selectedImageContext.refinementData?.refinement_type} Enhancement` 
              : 'Generated Image - Full Size'}
          </Typography>
          <IconButton onClick={clearSelectedImage} sx={{ color: 'grey.500' }}>
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
          minHeight: 'calc(100vh - 140px)',
          maxHeight: 'calc(100vh - 140px)'
        }}>
          {selectedImage && (
            <>
              {selectedImageContext?.type === 'refinement' && selectedImageContext.parentImagePath && selectedImageContext.parentImageBlobUrl ? (
                // Show comparison slider for refined images when we have both images
                <Box sx={{ 
                  maxWidth: 'calc(100vw - 32px)',
                  maxHeight: 'calc(100vh - 160px)',
                  width: 'auto',
                  height: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <ImageCompareSlider
                    beforeImageUrl={selectedImageContext.parentImageBlobUrl}
                    afterImageUrl={selectedImage}
                    height={Math.min(window.innerHeight - 200, 800)}
                  />
                </Box>
              ) : selectedImageContext?.type === 'refinement' && selectedImageContext.parentImagePath ? (
                // Fallback: Try to show comparison with direct URL if blob URL failed
                <Box sx={{ 
                  maxWidth: 'calc(100vw - 32px)',
                  maxHeight: 'calc(100vh - 160px)',
                  width: 'auto',
                  height: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 2
                }}>
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    Comparison view unavailable. Showing refined image only.
                  </Alert>
                  <Box
                    component="img"
                    src={selectedImage}
                    sx={{
                      maxWidth: '100%',
                      maxHeight: 'calc(100vh - 220px)',
                      width: 'auto',
                      height: 'auto',
                      objectFit: 'contain',
                      borderRadius: 1,
                      backgroundColor: 'white',
                      boxShadow: 3,
                      display: 'block'
                    }}
                  />
                </Box>
              ) : (
                // Show regular image for original images or when parent path is not available
                <Box
                  component="img"
                  src={selectedImage}
                  sx={{
                    maxWidth: 'calc(100vw - 32px)',
                    maxHeight: 'calc(100vh - 160px)',
                    width: 'auto',
                    height: 'auto',
                    objectFit: 'contain',
                    borderRadius: 1,
                    backgroundColor: 'white',
                    boxShadow: 3,
                    display: 'block'
                  }}
                />
              )}
            </>
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
                    Alt Text
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
                      {optionDetails.visualConcept.visual_concept.suggested_alt_text}
                    </Typography>
                    
                    <Tooltip title="Copy alt text to clipboard">
                      <IconButton
                        onClick={() => copyPromptToClipboard(optionDetails.visualConcept.visual_concept.suggested_alt_text || '')}
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
        parentRefinementJobId={refinementModal.parentRefinementJobId}
        onRefinementSubmit={(result) => {
          addLog('info', `Refinement started: ${result.job_id}`);
          toast.success('Refinement job started successfully!');
          
          setTimeout(() => {
            loadRefinements().then(() => {
              addLog('info', 'Refinement job added to queue');
            });
          }, 2000);
        }}
      />

      {/* Refinement Details Dialog */}
      <RefinementDetailsDialog
        open={refinementDetailsDialog.open}
        onClose={closeRefinementDetailsDialog}
        details={refinementDetailsDialog.details}
        loading={refinementDetailsDialog.loading}
        jobId={refinementDetailsDialog.jobId}
      />

      {/* Caption Dialog */}
      <CaptionDialog
        open={captionDialogOpen}
        onClose={closeCaptionDialog}
        onGenerate={handleCaptionGenerate}
        isGenerating={captionGenerating[captionImageIndex] || false}
        imageIndex={captionImageIndex}
        initialSettings={captionInitialSettings}
        initialModelId={captionInitialSettings ? (imageCaptions[captionImageIndex]?.[imageCaptions[captionImageIndex].length - 1]?.model_id || undefined) : undefined}
        error={captionErrors[captionImageIndex]}
      />

      {/* Save Preset Dialog */}
      <Dialog open={savePresetDialogOpen} onClose={closeSavePresetDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Save Style as Preset</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Save the style from Option {savePresetImageIndex + 1} as a reusable preset that you can apply to future projects.
            </Typography>
            <TextField
              autoFocus
              fullWidth
              label="Preset Name"
              value={savePresetName}
              onChange={(e) => setSavePresetName(e.target.value)}
              placeholder="e.g., Modern Minimalist Style"
              helperText="Give your style preset a memorable name"
              variant="outlined"
              sx={{ mt: 1 }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeSavePresetDialog} disabled={savePresetLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleSavePreset}
            disabled={!savePresetName.trim() || savePresetLoading}
            variant="contained"
            startIcon={savePresetLoading ? <CircularProgress size={16} /> : <BookmarkAddIcon />}
          >
            {savePresetLoading ? 'Saving...' : 'Save Preset'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
} 