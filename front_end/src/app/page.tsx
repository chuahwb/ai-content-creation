'use client';

import React, { useState } from 'react';
import {
  Container,
  Typography,
  Box,
  AppBar,
  Toolbar,
  Chip,
} from '@mui/material';
import { motion } from 'framer-motion';
import PipelineForm from '@/components/PipelineForm';
import RunResults from '@/components/RunResults';
import RunHistory from '@/components/RunHistory';
import { PipelineRunResponse } from '@/types/api';

export default function HomePage() {
  const [currentRun, setCurrentRun] = useState<PipelineRunResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'form' | 'results' | 'history'>('form');

  const handleRunStarted = (run: PipelineRunResponse) => {
    console.log('Pipeline run started, redirecting to results:', run.id);
    setCurrentRun(run);
    setActiveTab('results');
    // Force a small delay to ensure state updates are processed
    setTimeout(() => {
      console.log('Redirect complete, active tab:', 'results');
    }, 50);
  };

  const handleViewRun = (run: PipelineRunResponse) => {
    setCurrentRun(run);
    setActiveTab('results');
  };

  const handleNewRun = () => {
    setCurrentRun(null);
    setActiveTab('form');
  };

  return (
    <>
      {/* Header */}
      <AppBar position="static" elevation={0} sx={{ backgroundColor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar sx={{ py: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, flexGrow: 1 }}>
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: 'primary.main', letterSpacing: '-0.02em' }}>
                Churns
              </Typography>
            </motion.div>
            <Chip 
              label="Beta" 
              color="primary" 
              size="small" 
              variant="outlined"
              sx={{ fontWeight: 500, fontSize: '0.75rem' }}
            />
          </Box>
          
          {/* Navigation */}
          <Box sx={{ display: 'flex', gap: 1 }}>
            {(['form', 'results', 'history'] as const).map((tab) => (
              <Chip
                key={tab}
                label={tab === 'form' ? 'New Run' : tab === 'results' ? 'Results' : 'History'}
                variant={activeTab === tab ? 'filled' : 'outlined'}
                color={activeTab === tab ? 'primary' : 'default'}
                clickable
                onClick={() => setActiveTab(tab)}
                sx={{ 
                  fontWeight: 500,
                  textTransform: 'capitalize',
                  fontSize: '0.875rem',
                  '&:hover': { 
                    backgroundColor: activeTab === tab ? undefined : 'action.hover',
                    borderColor: activeTab === tab ? undefined : 'primary.main'
                  }
                }}
              />
            ))}
          </Box>
        </Toolbar>
      </AppBar>

      {/* Main Content */}
      <Container maxWidth="xl" sx={{ py: 4, minHeight: 'calc(100vh - 80px)' }}>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          {activeTab === 'form' && (
            <PipelineForm onRunStarted={handleRunStarted} />
          )}
          
          {activeTab === 'results' && currentRun && (
            <RunResults 
              runId={currentRun.id} 
              onNewRun={handleNewRun}
            />
          )}
          
          {activeTab === 'history' && (
            <RunHistory onViewRun={handleViewRun} />
          )}
        </motion.div>
      </Container>
    </>
  );
} 