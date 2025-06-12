#!/usr/bin/env python3
"""
Script to delete pipeline runs from both database and filesystem.
Usage:
    python delete_runs.py --list                    # List all runs
    python delete_runs.py --delete RUN_ID           # Delete specific run
    python delete_runs.py --delete-old 30           # Delete runs older than 30 days
    python delete_runs.py --delete-status FAILED    # Delete all failed runs
    python delete_runs.py --clear-all               # Delete all runs (dangerous!)
"""

import argparse
import sys
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from churns.api.database import PipelineRun, PipelineStage, RunStatus, engine


def list_runs():
    """List all pipeline runs with basic info"""
    with Session(engine) as session:
        runs = session.exec(select(PipelineRun).order_by(PipelineRun.created_at.desc())).all()
        
        if not runs:
            print("No pipeline runs found.")
            return
        
        print(f"{'Run ID':<40} {'Status':<12} {'Created':<20} {'Platform':<25} {'Files'}")
        print("-" * 120)
        
        for run in runs:
            run_dir = Path(f"./data/runs/{run.id}")
            file_count = len(list(run_dir.glob("*"))) if run_dir.exists() else 0
            file_size = sum(f.stat().st_size for f in run_dir.glob("*") if f.is_file()) if run_dir.exists() else 0
            file_info = f"{file_count} files ({file_size/1024/1024:.1f}MB)" if file_count > 0 else "No files"
            
            print(f"{run.id:<40} {run.status:<12} {run.created_at.strftime('%Y-%m-%d %H:%M'):<20} {(run.platform_name or 'N/A'):<25} {file_info}")


def delete_run_by_id(run_id: str, dry_run: bool = False):
    """Delete a specific run by ID"""
    with Session(engine) as session:
        # Find the run
        run = session.get(PipelineRun, run_id)
        if not run:
            print(f"❌ Run not found: {run_id}")
            return False
        
        print(f"🔍 Found run: {run_id}")
        print(f"   Status: {run.status}")
        print(f"   Created: {run.created_at}")
        print(f"   Platform: {run.platform_name or 'N/A'}")
        
        # Check for associated files
        run_dir = Path(f"./data/runs/{run_id}")
        if run_dir.exists():
            files = list(run_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in files if f.is_file())
            print(f"   Files: {len(files)} files ({total_size/1024/1024:.1f}MB)")
        else:
            print("   Files: No directory found")
        
        if dry_run:
            print("🔍 DRY RUN - Would delete this run")
            return True
        
        # Confirm deletion
        confirm = input(f"\n⚠️  Delete run {run_id[:8]}...? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Deletion cancelled")
            return False
        
        try:
            # Delete stages first (foreign key constraint)
            stages = session.exec(select(PipelineStage).where(PipelineStage.run_id == run_id)).all()
            for stage in stages:
                session.delete(stage)
            
            # Delete the run
            session.delete(run)
            session.commit()
            print(f"✅ Deleted run from database")
            
            # Delete files
            if run_dir.exists():
                shutil.rmtree(run_dir)
                print(f"✅ Deleted run directory: {run_dir}")
            
            print(f"🎉 Successfully deleted run: {run_id}")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error deleting run: {e}")
            return False


def delete_runs_by_status(status: str, dry_run: bool = False):
    """Delete all runs with specific status"""
    try:
        status_enum = RunStatus(status.upper())
    except ValueError:
        print(f"❌ Invalid status: {status}. Valid options: {[s.value for s in RunStatus]}")
        return False
    
    with Session(engine) as session:
        runs = session.exec(select(PipelineRun).where(PipelineRun.status == status_enum)).all()
        
        if not runs:
            print(f"No runs found with status: {status}")
            return True
        
        print(f"🔍 Found {len(runs)} runs with status '{status}':")
        for run in runs:
            print(f"   {run.id} - {run.created_at} - {run.platform_name or 'N/A'}")
        
        if dry_run:
            print("🔍 DRY RUN - Would delete these runs")
            return True
        
        confirm = input(f"\n⚠️  Delete all {len(runs)} runs with status '{status}'? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Deletion cancelled")
            return False
        
        deleted_count = 0
        for run in runs:
            print(f"\nDeleting run {run.id[:8]}...")
            try:
                # Delete stages first
                stages = session.exec(select(PipelineStage).where(PipelineStage.run_id == run.id)).all()
                for stage in stages:
                    session.delete(stage)
                
                # Delete the run
                session.delete(run)
                session.commit()
                
                # Delete files
                run_dir = Path(f"./data/runs/{run.id}")
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                
                deleted_count += 1
                print(f"✅ Deleted run {run.id[:8]}")
                
            except Exception as e:
                session.rollback()
                print(f"❌ Error deleting run {run.id[:8]}: {e}")
        
        print(f"🎉 Deleted {deleted_count}/{len(runs)} runs")
        return True


def delete_old_runs(days: int, dry_run: bool = False):
    """Delete runs older than specified days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    with Session(engine) as session:
        runs = session.exec(
            select(PipelineRun).where(PipelineRun.created_at < cutoff_date)
        ).all()
        
        if not runs:
            print(f"No runs found older than {days} days")
            return True
        
        print(f"🔍 Found {len(runs)} runs older than {days} days:")
        for run in runs:
            age = datetime.utcnow() - run.created_at
            print(f"   {run.id} - {age.days} days old - {run.status}")
        
        if dry_run:
            print("🔍 DRY RUN - Would delete these runs")
            return True
        
        confirm = input(f"\n⚠️  Delete all {len(runs)} runs older than {days} days? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Deletion cancelled")
            return False
        
        deleted_count = 0
        for run in runs:
            print(f"\nDeleting old run {run.id[:8]}...")
            try:
                # Delete stages first
                stages = session.exec(select(PipelineStage).where(PipelineStage.run_id == run.id)).all()
                for stage in stages:
                    session.delete(stage)
                
                # Delete the run
                session.delete(run)
                session.commit()
                
                # Delete files
                run_dir = Path(f"./data/runs/{run.id}")
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                
                deleted_count += 1
                print(f"✅ Deleted run {run.id[:8]}")
                
            except Exception as e:
                session.rollback()
                print(f"❌ Error deleting run {run.id[:8]}: {e}")
        
        print(f"🎉 Deleted {deleted_count}/{len(runs)} runs")
        return True


def clear_all_runs(dry_run: bool = False):
    """Delete ALL runs (dangerous!)"""
    with Session(engine) as session:
        runs = session.exec(select(PipelineRun)).all()
        
        if not runs:
            print("No runs to delete")
            return True
        
        print(f"🔍 Found {len(runs)} total runs")
        
        if dry_run:
            print("🔍 DRY RUN - Would delete ALL runs")
            return True
        
        print("⚠️  ⚠️  ⚠️  DANGER: This will delete ALL pipeline runs! ⚠️  ⚠️  ⚠️")
        confirm = input("Type 'DELETE ALL' to confirm: ")
        if confirm != 'DELETE ALL':
            print("❌ Deletion cancelled")
            return False
        
        try:
            # Delete all stages first
            session.exec("DELETE FROM pipeline_stages")
            # Delete all runs
            session.exec("DELETE FROM pipeline_runs")
            session.commit()
            
            # Delete all run directories
            runs_dir = Path("./data/runs")
            if runs_dir.exists():
                shutil.rmtree(runs_dir)
                runs_dir.mkdir()
            
            print(f"🎉 Deleted all {len(runs)} runs")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error clearing runs: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Delete pipeline runs from database and filesystem")
    group = parser.add_mutually_exclusive_group(required=True)
    
    group.add_argument("--list", action="store_true", help="List all runs")
    group.add_argument("--delete", metavar="RUN_ID", help="Delete specific run by ID")
    group.add_argument("--delete-old", metavar="DAYS", type=int, help="Delete runs older than N days")
    group.add_argument("--delete-status", metavar="STATUS", help="Delete all runs with specific status")
    group.add_argument("--clear-all", action="store_true", help="Delete ALL runs (dangerous!)")
    
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    
    args = parser.parse_args()
    
    # Ensure database and directories exist
    os.makedirs("./data/runs", exist_ok=True)
    
    if args.list:
        list_runs()
    elif args.delete:
        delete_run_by_id(args.delete, args.dry_run)
    elif args.delete_old:
        delete_old_runs(args.delete_old, args.dry_run)
    elif args.delete_status:
        delete_runs_by_status(args.delete_status, args.dry_run)
    elif args.clear_all:
        clear_all_runs(args.dry_run)


if __name__ == "__main__":
    main()
