'use client';

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Skeleton,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
  FilterList as FilterListIcon,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import dayjs from 'dayjs';
import toast from 'react-hot-toast';
import { RunListItem, RunListResponse, PipelineRunResponse, RunStatus } from '@/types/api';
import { PipelineAPI } from '@/lib/api';
import { statusColors } from '@/lib/theme';

interface RunHistoryProps {
  onViewRun: (run: PipelineRunResponse) => void;
}

export default function RunHistory({ onViewRun }: RunHistoryProps) {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<RunStatus | ''>('');

  const fetchRuns = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response = await PipelineAPI.getRuns(
        page + 1, // API uses 1-based pagination
        pageSize,
        statusFilter || undefined
      );
      
      setRuns(Array.isArray(response?.runs) ? response.runs : []);
      setTotal(response?.total || 0);
      
    } catch (err: any) {
      const errorMsg = err.message || 'Failed to fetch runs';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePageChange = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handlePageSizeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setPageSize(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleStatusFilterChange = (event: any) => {
    setStatusFilter(event.target.value);
    setPage(0);
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(1)}s`;
  };

  const getStatusColor = (status: RunStatus) => {
    switch (status) {
      case 'COMPLETED':
        return 'success';
      case 'FAILED':
        return 'error';
      case 'RUNNING':
        return 'info';
      case 'CANCELLED':
        return 'warning';
      default:
        return 'default';
    }
  };

  useEffect(() => {
    fetchRuns();
  }, [page, pageSize, statusFilter]);

  if (error && !runs.length) {
    return (
      <Card elevation={1}>
        <CardContent sx={{ p: 4 }}>
          <Alert 
            severity="error" 
            action={
              <Button color="inherit" size="small" onClick={fetchRuns}>
                Retry
              </Button>
            }
          >
            {error}
          </Alert>
        </CardContent>
      </Card>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <Card elevation={1}>
        <CardContent sx={{ p: 4 }}>


          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              Pipeline Run History
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              {/* Status Filter */}
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  value={statusFilter}
                  label="Status"
                  onChange={handleStatusFilterChange}
                >
                  <MenuItem value="">All</MenuItem>
                  <MenuItem value="PENDING">Pending</MenuItem>
                  <MenuItem value="RUNNING">Running</MenuItem>
                  <MenuItem value="COMPLETED">Completed</MenuItem>
                  <MenuItem value="FAILED">Failed</MenuItem>
                  <MenuItem value="CANCELLED">Cancelled</MenuItem>
                </Select>
              </FormControl>
              
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={fetchRuns}
                disabled={isLoading}
                size="small"
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {/* Table */}
          <TableContainer component={Paper} elevation={0} sx={{ border: 1, borderColor: 'divider' }}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Run ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Mode</TableCell>
                  <TableCell>Platform</TableCell>
                  <TableCell>Task Type</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Duration</TableCell>
                  <TableCell>Cost</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isLoading ? (
                  // Loading skeletons
                  [...Array(pageSize)].map((_, index) => (
                    <TableRow key={index}>
                      <TableCell><Skeleton variant="text" width={120} /></TableCell>
                      <TableCell><Skeleton variant="rectangular" width={80} height={24} /></TableCell>
                      <TableCell><Skeleton variant="text" width={100} /></TableCell>
                      <TableCell><Skeleton variant="text" width={120} /></TableCell>
                      <TableCell><Skeleton variant="text" width={100} /></TableCell>
                      <TableCell><Skeleton variant="text" width={120} /></TableCell>
                      <TableCell><Skeleton variant="text" width={60} /></TableCell>
                      <TableCell><Skeleton variant="text" width={60} /></TableCell>
                      <TableCell><Skeleton variant="circular" width={40} height={40} /></TableCell>
                    </TableRow>
                  ))
                ) : runs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} sx={{ textAlign: 'center', py: 4 }}>
                      <Typography variant="body2" color="textSecondary">
                        No pipeline runs found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  runs.map((run) => (
                    <TableRow key={run.id}>
                      <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.3 }}
                        style={{ display: 'contents' }}
                      >
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                          {run.id.slice(0, 8)}...
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Chip
                          label={run.status.toUpperCase()}
                          color={getStatusColor(run.status) as any}
                          size="small"
                          sx={{ fontWeight: 600 }}
                        />
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                          {run.mode.replace('_', ' ')}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2">
                          {run.platform_name || 'N/A'}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2">
                          {run.task_type || 'N/A'}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Tooltip title={dayjs(run.created_at).format('YYYY-MM-DD HH:mm:ss')}>
                          <Typography variant="body2">
                            {dayjs(run.created_at).format('MMM D, HH:mm')}
                          </Typography>
                        </Tooltip>
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2">
                          {run.completed_at 
                            ? formatDuration(dayjs(run.completed_at).diff(dayjs(run.created_at), 'second'))
                            : run.status === 'RUNNING' ? 'Running...' : 'N/A'
                          }
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Typography variant="body2">
                          ${run.total_cost_usd?.toFixed(4) || '0.0000'}
                        </Typography>
                      </TableCell>
                      
                      <TableCell>
                        <Tooltip title="View Details">
                          <IconButton
                            size="small"
                            onClick={() => onViewRun(run as PipelineRunResponse)}
                            color="primary"
                          >
                            <VisibilityIcon />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </motion.div>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>

          {/* Pagination */}
          {!isLoading && runs.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <TablePagination
                component="div"
                count={total}
                page={page}
                onPageChange={handlePageChange}
                rowsPerPage={pageSize}
                onRowsPerPageChange={handlePageSizeChange}
                rowsPerPageOptions={[10, 20, 50, 100]}
                showFirstButton
                showLastButton
              />
            </Box>
          )}

          {/* Summary Stats */}
          {!isLoading && runs.length > 0 && (
            <Box sx={{ mt: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
              <Typography variant="caption" color="textSecondary">
                Showing {runs.length} of {total} runs
                {statusFilter && ` (filtered by ${statusFilter})`}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
} 