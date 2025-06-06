#!/usr/bin/env python3
"""
Quick interactive script for basic database operations.
Run this script and follow the prompts to delete runs.
"""

import sys
import os
import shutil
from pathlib import Path

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from churns.api.database import PipelineRun, PipelineStage, engine


def show_recent_runs():
    """Show the 10 most recent runs"""
    with Session(engine) as session:
        runs = session.exec(
            select(PipelineRun)
            .order_by(PipelineRun.created_at.desc())
            .limit(10)
        ).all()
        
        if not runs:
            print("No runs found.")
            return []
        
        print("\n📋 Recent Pipeline Runs:")
        print("-" * 80)
        
        for i, run in enumerate(runs, 1):
            run_dir = Path(f"./data/runs/{run.id}")
            file_count = len(list(run_dir.glob("*"))) if run_dir.exists() else 0
            
            print(f"{i:2d}. {run.id[:8]}... - {run.status:<10} - {run.created_at.strftime('%Y-%m-%d %H:%M')} - {file_count} files")
        
        return runs


def delete_run_interactive(run):
    """Delete a run with confirmation"""
    print(f"\n🔍 Run Details:")
    print(f"   ID: {run.id}")
    print(f"   Status: {run.status}")
    print(f"   Created: {run.created_at}")
    print(f"   Platform: {run.platform_name or 'N/A'}")
    
    run_dir = Path(f"./data/runs/{run.id}")
    if run_dir.exists():
        files = list(run_dir.glob("*"))
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        print(f"   Files: {len(files)} files ({total_size/1024/1024:.1f}MB)")
        
        # Show file types
        extensions = {}
        for file in files:
            if file.is_file():
                ext = file.suffix.lower() or "no extension"
                extensions[ext] = extensions.get(ext, 0) + 1
        
        if extensions:
            ext_info = ", ".join([f"{count} {ext}" for ext, count in extensions.items()])
            print(f"   Types: {ext_info}")
    
    confirm = input(f"\n⚠️  Delete this run? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Deletion cancelled")
        return False
    
    try:
        with Session(engine) as session:
            # Delete stages first
            stages = session.exec(select(PipelineStage).where(PipelineStage.run_id == run.id)).all()
            for stage in stages:
                session.delete(stage)
            
            # Delete the run
            fresh_run = session.get(PipelineRun, run.id)
            if fresh_run:
                session.delete(fresh_run)
            session.commit()
            
            print("✅ Deleted from database")
            
            # Delete files
            if run_dir.exists():
                shutil.rmtree(run_dir)
                print("✅ Deleted files")
            
            print("🎉 Run deleted successfully!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    print("🗑️  Quick Delete - Pipeline Run Cleanup")
    print("=" * 50)
    
    while True:
        runs = show_recent_runs()
        
        if not runs:
            print("No runs to delete. Exiting.")
            break
        
        print(f"\nOptions:")
        print("1-{}: Delete specific run".format(len(runs)))
        print("q: Quit")
        
        choice = input("\nSelect option: ").strip().lower()
        
        if choice == 'q':
            print("👋 Goodbye!")
            break
        
        try:
            run_index = int(choice) - 1
            if 0 <= run_index < len(runs):
                selected_run = runs[run_index]
                if delete_run_interactive(selected_run):
                    print("\n" + "="*50)
                    input("Press Enter to continue...")
                    print("\n" * 2)  # Clear space
            else:
                print("❌ Invalid selection")
                
        except ValueError:
            print("❌ Please enter a number or 'q'")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break


if __name__ == "__main__":
    main() 