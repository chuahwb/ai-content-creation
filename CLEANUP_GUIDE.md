# Pipeline Run Cleanup Guide

This guide explains how to remove individual runs from your Churns pipeline history at the code/database level.

## Overview

The Churns pipeline stores data in two places:
- **Database**: SQLite database at `./data/runs.db` with tables `pipeline_runs` and `pipeline_stages`
- **Files**: Generated images and metadata in `./data/runs/{run_id}/` directories

## Cleanup Tools

We've created three scripts to help you manage pipeline runs:

### 1. 🎯 `delete_runs.py` - Comprehensive CLI Tool

**Features:**
- List all runs with detailed information
- Delete specific runs by ID
- Delete runs by status (FAILED, COMPLETED, etc.)
- Delete runs older than N days
- Bulk delete all runs
- Dry-run mode to preview deletions

**Usage:**
```bash
# List all runs
python delete_runs.py --list

# Delete a specific run
python delete_runs.py --delete <RUN_ID>

# Delete all failed runs
python delete_runs.py --delete-status FAILED

# Delete runs older than 30 days
python delete_runs.py --delete-old 30

# Delete ALL runs (dangerous!)
python delete_runs.py --clear-all

# Preview what would be deleted (dry run)
python delete_runs.py --delete-status FAILED --dry-run
```

### 2. 🚀 `quick_delete.py` - Interactive Tool

**Features:**
- Shows recent runs in a numbered list
- Interactive selection and deletion
- Detailed file information before deletion
- User-friendly prompts

**Usage:**
```bash
python quick_delete.py
```

Then follow the interactive prompts:
```
🗑️  Quick Delete - Pipeline Run Cleanup
==================================================

📋 Recent Pipeline Runs:
--------------------------------------------------------------------------------
 1. a1b2c3d4... - COMPLETED  - 2024-06-07 01:30 - 12 files
 2. e5f6g7h8... - FAILED     - 2024-06-07 01:25 - 0 files
 3. i9j0k1l2... - RUNNING    - 2024-06-07 01:20 - 8 files

Options:
1-3: Delete specific run
q: Quit

Select option: 2
```

### 3. ⚡ `sql_cleanup.py` - Direct SQL Operations

**Features:**
- Direct SQLite database operations
- Database inspection and statistics
- Bulk operations by SQL queries
- Database optimization (VACUUM)

**Usage:**
```bash
# Inspect database structure and stats
python sql_cleanup.py inspect

# List recent runs
python sql_cleanup.py list

# Delete specific run
python sql_cleanup.py delete <RUN_ID>

# Delete all runs with specific status
python sql_cleanup.py delete-status FAILED

# Optimize database after deletions
python sql_cleanup.py vacuum
```

## Manual Database Operations

### Using SQLite CLI

If you prefer direct SQL commands:

```bash
# Open database
sqlite3 ./data/runs.db

# List all runs
SELECT id, status, created_at, platform_name FROM pipeline_runs ORDER BY created_at DESC;

# Delete a specific run (replace with actual ID)
DELETE FROM pipeline_stages WHERE run_id = 'your-run-id-here';
DELETE FROM pipeline_runs WHERE id = 'your-run-id-here';

# Delete all failed runs
DELETE FROM pipeline_stages WHERE run_id IN (SELECT id FROM pipeline_runs WHERE status = 'FAILED');
DELETE FROM pipeline_runs WHERE status = 'FAILED';

# Optimize database
VACUUM;
```

### Manual File Cleanup

```bash
# List run directories
ls -la ./data/runs/

# Remove specific run directory
rm -rf ./data/runs/your-run-id-here

# Remove all run directories (keeps database)
rm -rf ./data/runs/*
```

## Database Schema

Understanding the database structure:

```sql
-- Main runs table
CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    platform_name TEXT,
    -- ... other fields
);

-- Stages linked to runs
CREATE TABLE pipeline_stages (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES pipeline_runs(id),
    stage_name TEXT,
    status TEXT,
    -- ... other fields
);
```

## File Structure

Each run creates a directory:
```
./data/runs/{run_id}/
├── pipeline_metadata.json    # Run configuration
├── image_001.png            # Generated images
├── image_002.png
└── ...
```

## Best Practices

1. **Always backup** before bulk deletions:
   ```bash
   cp ./data/runs.db ./data/runs.db.backup
   cp -r ./data/runs ./data/runs.backup
   ```

2. **Use dry-run mode** to preview deletions:
   ```bash
   python delete_runs.py --delete-status FAILED --dry-run
   ```

3. **Clean up regularly** to save space:
   ```bash
   # Weekly cleanup of failed runs
   python delete_runs.py --delete-status FAILED
   
   # Monthly cleanup of old runs
   python delete_runs.py --delete-old 30
   ```

4. **Optimize database** after large deletions:
   ```bash
   python sql_cleanup.py vacuum
   ```

## Troubleshooting

### Script Errors

If you get import errors:
```bash
# Make sure you're in the project root
cd /path/to/churns

# Activate virtual environment
source venv/bin/activate

# Check if the churns package is accessible
python -c "from churns.api.database import PipelineRun; print('✅ OK')"
```

### Database Locked

If you get "database is locked" errors:
```bash
# Stop the API server first
pkill -f "uvicorn"

# Then run cleanup scripts
python delete_runs.py --list
```

### File Permission Issues

```bash
# Make scripts executable
chmod +x delete_runs.py quick_delete.py sql_cleanup.py

# Check file ownership
ls -la ./data/runs/
```

## Examples

### Scenario 1: Clean up failed runs
```bash
# Check what failed runs exist
python delete_runs.py --delete-status FAILED --dry-run

# Delete them
python delete_runs.py --delete-status FAILED
```

### Scenario 2: Free up space by removing old runs
```bash
# See database statistics
python sql_cleanup.py inspect

# Remove runs older than 2 weeks
python delete_runs.py --delete-old 14
```

### Scenario 3: Interactive cleanup
```bash
# Use the interactive tool
python quick_delete.py

# Select runs to delete one by one
```

### Scenario 4: Complete reset
```bash
# ⚠️ WARNING: This deletes everything!
python delete_runs.py --clear-all
```

This guide should help you efficiently manage your pipeline run history! 