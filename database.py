import sqlite3
import os
import re
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_name='chat_app.db'):
        self.db_name = db_name

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create models table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            is_available BOOLEAN DEFAULT 1
        )''')
        
        # Create routing_rules table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS routing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_provider TEXT NOT NULL,
            original_model TEXT NOT NULL,
            regex_pattern TEXT NOT NULL,
            redirect_provider TEXT NOT NULL,
            redirect_model TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_routing_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_type TEXT NOT NULL,
        redirect_provider TEXT NOT NULL,
        redirect_model TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        UNIQUE(file_type)
        )''')
        
        # Insert sample data
        self._insert_sample_data(cursor)
        
        conn.commit()
        conn.close()

    def _insert_sample_data(self, cursor):
        sample_models = [
            ('openai', 'gpt-3.5', 1),
            ('openai', 'gpt-4', 1),
            ('anthropic', 'claude-v1', 1),
            ('google', 'gemini-alpha', 1)
        ]
        
        cursor.executemany(
            "INSERT INTO models (provider, model_name, is_available) VALUES (?, ?, ?)",
            sample_models
        )
        
        sample_rules = [
            ('openai', 'gpt-4', r'(?i)(credit card)', 'google', 'gemini-alpha', 1),
            ('anthropic', 'claude-v1', r'(?i)(social security number|ssn)', 'openai', 'gpt-3.5', 1),
            ('google', 'gemini-pro', r'(?i)(bank account|routing number)', 'anthropic', 'claude-v1', 1)
        ]
        
        cursor.executemany(
            """INSERT INTO routing_rules 
               (original_provider, original_model, regex_pattern, 
                redirect_provider, redirect_model, is_active) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            sample_rules
        )

        sample_file_rules = [
        ('PDF', 'anthropic', 'claude-v1', 1),
        ('Word Document', 'google', 'gemini-alpha', 1),
        ('CSV', 'openai', 'gpt-4', 1)
        ]
    
        cursor.executemany(
        """INSERT INTO file_routing_rules 
           (file_type, redirect_provider, redirect_model, is_active)
           VALUES (?, ?, ?, ?)""",
        sample_file_rules
        )

    def get_all_models(self) -> List[str]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT provider, model_name FROM models WHERE is_available = 1")
        models_rows = cursor.fetchall()
        
        models = [f"{row['provider']}/{row['model_name']}" for row in models_rows]
        
        conn.close()
        return models

    def get_all_rules(self) -> List[dict]:
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM routing_rules WHERE is_active = 1
        """)
        
        rules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rules

    def add_rule(self, original_provider: str, original_model: str, 
                 regex_pattern: str, redirect_provider: str, 
                 redirect_model: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO routing_rules 
            (original_provider, original_model, regex_pattern, 
             redirect_provider, redirect_model, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (original_provider, original_model, regex_pattern, 
              redirect_provider, redirect_model))
        
        rule_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return rule_id

    def update_rule(self, rule_id: int, original_provider: str, 
                   original_model: str, regex_pattern: str, 
                   redirect_provider: str, redirect_model: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE routing_rules 
            SET original_provider = ?, 
                original_model = ?,
                regex_pattern = ?,
                redirect_provider = ?,
                redirect_model = ?
            WHERE id = ? AND is_active = 1
        """, (original_provider, original_model, regex_pattern, 
              redirect_provider, redirect_model, rule_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def delete_rule(self, rule_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE routing_rules 
            SET is_active = 0
            WHERE id = ?
        """, (rule_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def check_routing_rules(self, provider: str, model: str, 
                          prompt: str) -> Optional[Tuple[str, str, str]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT regex_pattern, redirect_provider, redirect_model 
            FROM routing_rules 
            WHERE original_provider = ? 
            AND original_model = ? 
            AND is_active = 1
        """, (provider, model))
        
        rules = cursor.fetchall()
        conn.close()
        
        for rule in rules:
            pattern, redirect_provider, redirect_model = rule
            if re.search(pattern, prompt):
                return redirect_provider, redirect_model, pattern
                
        return None
    
    def get_file_routing_rules(self):
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM file_routing_rules 
            WHERE is_active = 1
        """)
        
        rules = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rules

    def add_file_rule(self, file_type: str, redirect_provider: str, 
                    redirect_model: str) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO file_routing_rules 
                (file_type, redirect_provider, redirect_model, is_active)
                VALUES (?, ?, ?, 1)
            """, (file_type, redirect_provider, redirect_model))
            
            rule_id = cursor.lastrowid
            conn.commit()
            return rule_id
        except sqlite3.IntegrityError:
            # Update existing rule if file_type already exists
            cursor.execute("""
                UPDATE file_routing_rules 
                SET redirect_provider = ?,
                    redirect_model = ?,
                    is_active = 1
                WHERE file_type = ?
            """, (redirect_provider, redirect_model, file_type))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def delete_file_rule(self, rule_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE file_routing_rules 
            SET is_active = 0
            WHERE id = ?
        """, (rule_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success

    def get_file_routing(self, file_type: str) -> Optional[Tuple[str, str]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT redirect_provider, redirect_model 
            FROM file_routing_rules 
            WHERE file_type = ? 
            AND is_active = 1
        """, (file_type,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result if result else None