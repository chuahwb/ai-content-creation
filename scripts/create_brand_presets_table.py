#!/usr/bin/env python3
"""
Simple migration script to create the brand_presets table.
This script can be run independently without the full application context.
"""

import sqlite3
import os
import sys

def create_brand_presets_table():
    """Create the brand_presets table in the SQLite database."""
    
    # Ensure data directory exists
    os.makedirs("./data", exist_ok=True)
    
    # Connect to the database
    db_path = "./data/runs.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the brand_presets table
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS brand_presets (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        version INTEGER DEFAULT 1,
        model_id TEXT NOT NULL,
        pipeline_version TEXT NOT NULL,
        brand_colors TEXT,
        brand_voice_description TEXT,
        logo_asset_analysis TEXT,
        preset_type TEXT NOT NULL,
        input_snapshot TEXT,
        style_recipe TEXT,
        usage_count INTEGER DEFAULT 0,
        last_used_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """
    
    try:
        cursor.execute(create_table_sql)
        conn.commit()
        print("✅ brand_presets table created successfully")
        
        # Verify the table was created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brand_presets';")
        result = cursor.fetchone()
        if result:
            print("✅ Table verified in database")
        else:
            print("❌ Table not found after creation")
            
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    create_brand_presets_table() 