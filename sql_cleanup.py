#!/usr/bin/env python3
"""
Direct SQL operations for database cleanup and inspection.
Use this for advanced database operations.
"""

import sys
import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = "./data/runs.db"
RUNS_DIR = Path("./data/runs")


def connect_db():
    """Connect to SQLite database"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return None
    
    return sqlite3.connect(DB_PATH)


def inspect_database():
    """Show database structure and statistics"""
    conn = connect_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    print("🔍 Database Structure:")
    print("-" * 50)
    
    # Show tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {[table[0] for table in tables]}")
    
    # Show runs statistics
    cursor.execute("SELECT COUNT(*) FROM pipeline_runs")
    run_count = cursor.fetchone()[0]
    print(f"Total runs: {run_count}")
    
    if run_count > 0:
        cursor.execute("SELECT status, COUNT(*) FROM pipeline_runs GROUP BY status")
        status_counts = cursor.fetchall()
        print("Status breakdown:")
        for status, count in status_counts:
            print(f"  {status}: {count}")
        
        # Show date range
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM pipeline_runs")
        min_date, max_date = cursor.fetchone()
        print(f"Date range: {min_date} to {max_date}")
    
    # Show stages statistics
    cursor.execute("SELECT COUNT(*) FROM pipeline_stages")
    stage_count = cursor.fetchone()[0]
    print(f"Total stages: {stage_count}")
    
    conn.close()
    
    # File system statistics
    if RUNS_DIR.exists():
        run_dirs = [d for d in RUNS_DIR.iterdir() if d.is_dir()]
        total_size = sum(
            sum(f.stat().st_size for f in run_dir.rglob("*") if f.is_file())
            for run_dir in run_dirs
        )
        print(f"Run directories: {len(run_dirs)}")
        print(f"Total file size: {total_size/1024/1024:.1f}MB")


def list_runs_sql():
    """List runs using direct SQL"""
    conn = connect_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status, created_at, platform_name 
        FROM pipeline_runs 
        ORDER BY created_at DESC 
        LIMIT 20
    """)
    
    runs = cursor.fetchall()
    
    print(f"\n📋 Recent Runs (SQL):")
    print("-" * 100)
    print(f"{'ID':<40} {'Status':<12} {'Created':<20} {'Platform':<25}")
    print("-" * 100)
    
    for run_id, status, created_at, platform in runs:
        run_dir = RUNS_DIR / run_id
        file_count = len(list(run_dir.glob("*"))) if run_dir.exists() else 0
        
        # Format datetime
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            formatted_date = dt.strftime('%Y-%m-%d %H:%M')
        except:
            formatted_date = created_at[:16]
        
        print(f"{run_id:<40} {status:<12} {formatted_date:<20} {(platform or 'N/A'):<25}")
    
    conn.close()


def delete_run_sql(run_id: str):
    """Delete a run using direct SQL"""
    conn = connect_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    # Check if run exists
    cursor.execute("SELECT id, status, created_at FROM pipeline_runs WHERE id = ?", (run_id,))
    run = cursor.fetchone()
    
    if not run:
        print(f"❌ Run not found: {run_id}")
        conn.close()
        return False
    
    print(f"🔍 Found run: {run_id}")
    print(f"   Status: {run[1]}")
    print(f"   Created: {run[2]}")
    
    confirm = input(f"\n⚠️  Delete run {run_id[:8]}...? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Deletion cancelled")
        conn.close()
        return False
    
    try:
        # Delete stages first
        cursor.execute("DELETE FROM pipeline_stages WHERE run_id = ?", (run_id,))
        stages_deleted = cursor.rowcount
        
        # Delete run
        cursor.execute("DELETE FROM pipeline_runs WHERE id = ?", (run_id,))
        runs_deleted = cursor.rowcount
        
        conn.commit()
        
        print(f"✅ Deleted {runs_deleted} run and {stages_deleted} stages from database")
        
        # Delete files
        run_dir = RUNS_DIR / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
            print(f"✅ Deleted run directory: {run_dir}")
        
        print(f"🎉 Successfully deleted run: {run_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error deleting run: {e}")
        return False
    finally:
        conn.close()


def bulk_delete_by_status_sql(status: str):
    """Delete all runs with specific status using SQL"""
    conn = connect_db()
    if not conn:
        return False
    
    cursor = conn.cursor()
    
    # Find runs with status
    cursor.execute("SELECT id FROM pipeline_runs WHERE status = ?", (status.upper(),))
    runs = cursor.fetchall()
    
    if not runs:
        print(f"No runs found with status: {status}")
        conn.close()
        return True
    
    run_ids = [run[0] for run in runs]
    print(f"🔍 Found {len(run_ids)} runs with status '{status}'")
    
    confirm = input(f"\n⚠️  Delete all {len(run_ids)} runs? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Deletion cancelled")
        conn.close()
        return False
    
    try:
        # Delete stages for all runs
        placeholders = ','.join(['?' for _ in run_ids])
        cursor.execute(f"DELETE FROM pipeline_stages WHERE run_id IN ({placeholders})", run_ids)
        stages_deleted = cursor.rowcount
        
        # Delete runs
        cursor.execute(f"DELETE FROM pipeline_runs WHERE id IN ({placeholders})", run_ids)
        runs_deleted = cursor.rowcount
        
        conn.commit()
        
        print(f"✅ Deleted {runs_deleted} runs and {stages_deleted} stages from database")
        
        # Delete files
        deleted_dirs = 0
        for run_id in run_ids:
            run_dir = RUNS_DIR / run_id
            if run_dir.exists():
                shutil.rmtree(run_dir)
                deleted_dirs += 1
        
        print(f"✅ Deleted {deleted_dirs} run directories")
        print(f"🎉 Successfully deleted {len(run_ids)} runs")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error deleting runs: {e}")
        return False
    finally:
        conn.close()


def vacuum_database():
    """Optimize database after deletions"""
    conn = connect_db()
    if not conn:
        return
    
    print("🧹 Vacuuming database...")
    conn.execute("VACUUM")
    conn.close()
    print("✅ Database optimized")


def main():
    if len(sys.argv) < 2:
        print("SQL Cleanup Tool")
        print("Usage:")
        print(f"  {sys.argv[0]} inspect           # Show database statistics")
        print(f"  {sys.argv[0]} list              # List recent runs")
        print(f"  {sys.argv[0]} delete RUN_ID     # Delete specific run")
        print(f"  {sys.argv[0]} delete-status STATUS # Delete all runs with status")
        print(f"  {sys.argv[0]} vacuum            # Optimize database")
        return
    
    command = sys.argv[1].lower()
    
    if command == "inspect":
        inspect_database()
    elif command == "list":
        list_runs_sql()
    elif command == "delete" and len(sys.argv) > 2:
        delete_run_sql(sys.argv[2])
    elif command == "delete-status" and len(sys.argv) > 2:
        bulk_delete_by_status_sql(sys.argv[2])
    elif command == "vacuum":
        vacuum_database()
    else:
        print("❌ Unknown command or missing arguments")


if __name__ == "__main__":
    main() 