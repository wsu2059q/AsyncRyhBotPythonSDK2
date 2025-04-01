import os
import json
import sqlite3
import importlib.util
from pathlib import Path

class EnvManager:
    _instance = None
    db_path = "./config.db"

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            module_name TEXT PRIMARY KEY,
            status INTEGER NOT NULL,
            version TEXT,
            description TEXT,
            author TEXT,
            dependencies TEXT,
            optional_dependencies TEXT
        )
        """)
        conn.commit()
        conn.close()

    def get(self, key, default=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
                result = cursor.fetchone()
            if result:
                try:
                    return json.loads(result[0])
                except json.JSONDecodeError:
                    return result[0]
            return default
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                self._init_db()
                return self.get(key, default)
            else:
                raise

    def set(self, key, value):
        serialized_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, serialized_value))
        conn.commit()
        conn.close()

    def delete(self, key):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    
    def clear(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM config")
        conn.commit()
        conn.close()

    def load_env_file(self):
        env_file = Path("env.py")
        if env_file.exists():
            spec = importlib.util.spec_from_file_location("env_module", env_file)
            env_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(env_module)
            for key, value in vars(env_module).items():
                if not key.startswith("__") and isinstance(value, (dict, list, str, int, float, bool)):
                    self.set(key, value)
    def set_module_status(self, module_name, status):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE modules SET status = ? WHERE module_name = ?
            """, (int(status), module_name))
            conn.commit()
    
    def get_module_status(self, module_name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT status FROM modules WHERE module_name = ?
            """, (module_name,))
            result = cursor.fetchone()
            return bool(result[0]) if result else True
    
    def set_all_modules(self, modules_info):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for module_name, module_info in modules_info.items():
                cursor.execute("""
                INSERT OR REPLACE INTO modules (
                    module_name, status, version, description, author, dependencies, optional_dependencies
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    module_name,
                    int(module_info.get('status', True)),
                    module_info.get('info', {}).get('version', ''),
                    module_info.get('info', {}).get('description', ''),
                    module_info.get('info', {}).get('author', ''),
                    json.dumps(module_info.get('info', {}).get('dependencies', [])),
                    json.dumps(module_info.get('info', {}).get('optional_dependencies', []))
                ))
            conn.commit()

    def get_all_modules(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM modules")
            rows = cursor.fetchall()
            modules_info = {}
            for row in rows:
                module_name, status, version, description, author, dependencies, optional_dependencies = row
                modules_info[module_name] = {
                    'status': bool(status),
                    'info': {
                        'version': version,
                        'description': description,
                        'author': author,
                        'dependencies': json.loads(dependencies) if dependencies else [],
                        'optional_dependencies': json.loads(optional_dependencies) if optional_dependencies else []
                    }
                }
            return modules_info

    def get_module(self, module_name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM modules WHERE module_name = ?", (module_name,))
            row = cursor.fetchone()
            if row:
                module_name, status, version, description, author, dependencies, optional_dependencies = row
                return {
                    'status': bool(status),
                    'info': {
                        'version': version,
                        'description': description,
                        'author': author,
                        'dependencies': json.loads(dependencies) if dependencies else [],
                        'optional_dependencies': json.loads(optional_dependencies) if optional_dependencies else []
                    }
                }
            return None

    def set_module(self, module_name, module_info):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO modules (
                module_name, status, version, description, author, dependencies, optional_dependencies
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                module_name,
                int(module_info.get('status', True)),
                module_info.get('info', {}).get('version', ''),
                module_info.get('info', {}).get('description', ''),
                module_info.get('info', {}).get('author', ''),
                json.dumps(module_info.get('info', {}).get('dependencies', [])),
                json.dumps(module_info.get('info', {}).get('optional_dependencies', []))
            ))
            conn.commit()

    def update_module(self, module_name, module_info):
        self.set_module(module_name, module_info)

    def remove_module(self, module_name):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM modules WHERE module_name = ?", (module_name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def __getattr__(self, key):
        try:
            return self.get(key)
        except KeyError:
            raise AttributeError(f"配置项 {key} 不存在")

env = EnvManager()
