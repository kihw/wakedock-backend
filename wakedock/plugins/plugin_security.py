"""
Plugin security and sandboxing for WakeDock
"""

import ast
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import subprocess
import tempfile
import os

logger = logging.getLogger(__name__)


class PluginSecurity:
    """
    Security manager for plugin validation and sandboxing
    """
    
    def __init__(self):
        self.blocked_imports = {
            'os', 'sys', 'subprocess', 'importlib', 'builtins',
            'exec', 'eval', 'compile', '__import__',
            'socket', 'urllib', 'requests', 'httpx',
            'pickle', 'marshal', 'shelve', 'dbm',
            'ctypes', 'cffi', 'gc', 'weakref',
            'threading', 'multiprocessing', 'asyncio.subprocess'
        }
        
        self.allowed_imports = {
            'json', 'datetime', 'typing', 'dataclasses', 'enum',
            'logging', 'pathlib', 'collections', 'itertools',
            'functools', 'operator', 'math', 'random', 'uuid',
            'hashlib', 'base64', 'binascii', 'struct',
            'asyncio', 'aiofiles', 'pydantic', 'fastapi'
        }
        
        self.dangerous_functions = {
            'exec', 'eval', 'compile', '__import__', 'open',
            'input', 'raw_input', 'file', 'execfile',
            'reload', 'vars', 'globals', 'locals', 'dir',
            'hasattr', 'getattr', 'setattr', 'delattr'
        }
        
        self.max_file_size = 1024 * 1024  # 1MB
        self.max_lines = 10000
        self.plugin_signatures = {}
    
    async def initialize(self) -> None:
        """Initialize security manager"""
        logger.info("Initializing plugin security manager")
    
    async def validate_plugin(self, plugin_path: Path) -> bool:
        """
        Validate plugin security
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if plugin is safe, False otherwise
        """
        try:
            # Check file sizes
            if not await self.check_file_sizes(plugin_path):
                return False
            
            # Validate Python files
            if not await self.validate_python_files(plugin_path):
                return False
            
            # Check for dangerous patterns
            if not await self.check_dangerous_patterns(plugin_path):
                return False
            
            # Validate imports
            if not await self.validate_imports(plugin_path):
                return False
            
            # Check file permissions
            if not await self.check_file_permissions(plugin_path):
                return False
            
            # Generate and store signature
            await self.generate_plugin_signature(plugin_path)
            
            logger.info(f"Plugin security validation passed: {plugin_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"Plugin security validation failed: {e}")
            return False
    
    async def check_file_sizes(self, plugin_path: Path) -> bool:
        """
        Check if plugin files are within size limits
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if all files are within limits, False otherwise
        """
        try:
            total_size = 0
            
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    
                    # Check individual file size
                    if file_size > self.max_file_size:
                        logger.error(f"File too large: {file_path} ({file_size} bytes)")
                        return False
            
            # Check total plugin size (10MB limit)
            if total_size > 10 * 1024 * 1024:
                logger.error(f"Plugin too large: {total_size} bytes")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check file sizes: {e}")
            return False
    
    async def validate_python_files(self, plugin_path: Path) -> bool:
        """
        Validate Python files for syntax and security
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if all Python files are valid, False otherwise
        """
        try:
            for py_file in plugin_path.rglob('*.py'):
                if not await self.validate_python_file(py_file):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate Python files: {e}")
            return False
    
    async def validate_python_file(self, file_path: Path) -> bool:
        """
        Validate a single Python file
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            True if file is valid, False otherwise
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check file size
            if len(content) > self.max_file_size:
                logger.error(f"Python file too large: {file_path}")
                return False
            
            # Check line count
            lines = content.split('\n')
            if len(lines) > self.max_lines:
                logger.error(f"Python file has too many lines: {file_path}")
                return False
            
            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                logger.error(f"Syntax error in {file_path}: {e}")
                return False
            
            # Analyze AST for security issues
            if not await self.analyze_ast(tree, file_path):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate Python file {file_path}: {e}")
            return False
    
    async def analyze_ast(self, tree: ast.AST, file_path: Path) -> bool:
        """
        Analyze AST for security issues
        
        Args:
            tree: AST tree
            file_path: Path to the file
            
        Returns:
            True if AST is safe, False otherwise
        """
        try:
            for node in ast.walk(tree):
                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in self.dangerous_functions:
                            logger.error(f"Dangerous function call '{node.func.id}' in {file_path}")
                            return False
                
                # Check for dangerous imports
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in self.blocked_imports:
                            logger.error(f"Blocked import '{alias.name}' in {file_path}")
                            return False
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module in self.blocked_imports:
                        logger.error(f"Blocked import from '{node.module}' in {file_path}")
                        return False
                
                # Check for exec/eval usage
                elif isinstance(node, ast.Expr):
                    if isinstance(node.value, ast.Call):
                        if isinstance(node.value.func, ast.Name):
                            if node.value.func.id in ['exec', 'eval']:
                                logger.error(f"Dangerous function '{node.value.func.id}' in {file_path}")
                                return False
                
                # Check for file operations
                elif isinstance(node, ast.With):
                    if isinstance(node.items[0].context_expr, ast.Call):
                        if isinstance(node.items[0].context_expr.func, ast.Name):
                            if node.items[0].context_expr.func.id == 'open':
                                # Check if it's trying to open system files
                                if len(node.items[0].context_expr.args) > 0:
                                    if isinstance(node.items[0].context_expr.args[0], ast.Str):
                                        file_name = node.items[0].context_expr.args[0].s
                                        if self.is_system_file(file_name):
                                            logger.error(f"Attempt to open system file '{file_name}' in {file_path}")
                                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to analyze AST: {e}")
            return False
    
    def is_system_file(self, file_path: str) -> bool:
        """
        Check if a file path is a system file
        
        Args:
            file_path: File path to check
            
        Returns:
            True if it's a system file, False otherwise
        """
        system_paths = [
            '/etc/', '/sys/', '/proc/', '/dev/', '/var/log/',
            '/boot/', '/root/', '/usr/bin/', '/usr/sbin/',
            '/bin/', '/sbin/', '/lib/', '/lib64/',
            'C:\\Windows\\', 'C:\\Program Files\\',
            'C:\\ProgramData\\', 'C:\\Users\\',
        ]
        
        for sys_path in system_paths:
            if file_path.startswith(sys_path):
                return True
        
        return False
    
    async def check_dangerous_patterns(self, plugin_path: Path) -> bool:
        """
        Check for dangerous patterns in plugin files
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if no dangerous patterns found, False otherwise
        """
        try:
            dangerous_patterns = [
                b'__import__', b'exec(', b'eval(', b'compile(',
                b'os.system', b'subprocess.', b'popen(',
                b'socket.', b'urllib.', b'requests.',
                b'pickle.', b'marshal.', b'shelve.',
                b'ctypes.', b'cffi.', b'gc.',
                b'threading.', b'multiprocessing.',
                b'/etc/passwd', b'/etc/shadow', b'/root/',
                b'C:\\Windows\\', b'C:\\Program Files\\',
                b'rm -rf', b'del /f', b'format c:',
            ]
            
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file() and file_path.suffix in ['.py', '.txt', '.json']:
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                        
                        for pattern in dangerous_patterns:
                            if pattern in content:
                                logger.error(f"Dangerous pattern '{pattern.decode()}' found in {file_path}")
                                return False
                    except Exception as e:
                        logger.warning(f"Could not read file {file_path}: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check dangerous patterns: {e}")
            return False
    
    async def validate_imports(self, plugin_path: Path) -> bool:
        """
        Validate that plugin only imports allowed modules
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if all imports are allowed, False otherwise
        """
        try:
            for py_file in plugin_path.rglob('*.py'):
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                try:
                    tree = ast.parse(content)
                except SyntaxError:
                    continue  # Skip files with syntax errors
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if not await self.is_import_allowed(alias.name):
                                logger.error(f"Unauthorized import '{alias.name}' in {py_file}")
                                return False
                    
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and not await self.is_import_allowed(node.module):
                            logger.error(f"Unauthorized import from '{node.module}' in {py_file}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate imports: {e}")
            return False
    
    async def is_import_allowed(self, module_name: str) -> bool:
        """
        Check if an import is allowed
        
        Args:
            module_name: Name of the module to import
            
        Returns:
            True if import is allowed, False otherwise
        """
        # Check if it's explicitly blocked
        if module_name in self.blocked_imports:
            return False
        
        # Check if it's explicitly allowed
        if module_name in self.allowed_imports:
            return True
        
        # Check if it's a standard library module
        if module_name.startswith('wakedock.'):
            return True
        
        # Check if it's a common safe module
        safe_prefixes = [
            'json', 'datetime', 'typing', 'dataclasses',
            'collections', 'itertools', 'functools',
            'math', 'random', 'uuid', 'hashlib',
            'base64', 'binascii', 'struct', 'time',
            'calendar', 'decimal', 'fractions',
            'statistics', 'string', 're', 'difflib',
            'textwrap', 'unicodedata', 'stringprep',
            'readline', 'rlcompleter', 'pydantic',
            'fastapi', 'starlette', 'uvicorn'
        ]
        
        for prefix in safe_prefixes:
            if module_name.startswith(prefix):
                return True
        
        # Default to not allowed
        return False
    
    async def check_file_permissions(self, plugin_path: Path) -> bool:
        """
        Check file permissions for security
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if permissions are safe, False otherwise
        """
        try:
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file():
                    stat = file_path.stat()
                    
                    # Check if file is executable (potential security risk)
                    if stat.st_mode & 0o111:
                        # Allow executable permissions only for specific file types
                        if file_path.suffix not in ['.py', '.sh', '.bat']:
                            logger.error(f"Executable file with suspicious extension: {file_path}")
                            return False
                    
                    # Check if file is world-writable (security risk)
                    if stat.st_mode & 0o002:
                        logger.error(f"World-writable file: {file_path}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check file permissions: {e}")
            return False
    
    async def generate_plugin_signature(self, plugin_path: Path) -> str:
        """
        Generate a security signature for the plugin
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            SHA256 signature of the plugin
        """
        try:
            hasher = hashlib.sha256()
            
            # Include all files in the signature
            for file_path in sorted(plugin_path.rglob('*')):
                if file_path.is_file():
                    with open(file_path, 'rb') as f:
                        hasher.update(f.read())
                    
                    # Also include file metadata
                    hasher.update(str(file_path.relative_to(plugin_path)).encode())
                    hasher.update(str(file_path.stat().st_size).encode())
            
            signature = hasher.hexdigest()
            self.plugin_signatures[plugin_path.name] = signature
            
            logger.info(f"Generated signature for plugin {plugin_path.name}: {signature[:16]}...")
            return signature
            
        except Exception as e:
            logger.error(f"Failed to generate plugin signature: {e}")
            return ""
    
    async def verify_plugin_signature(self, plugin_path: Path) -> bool:
        """
        Verify plugin signature hasn't changed
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            current_signature = await self.generate_plugin_signature(plugin_path)
            stored_signature = self.plugin_signatures.get(plugin_path.name)
            
            if stored_signature and current_signature != stored_signature:
                logger.error(f"Plugin signature mismatch for {plugin_path.name}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify plugin signature: {e}")
            return False
    
    async def create_sandbox(self, plugin_name: str) -> Dict[str, Any]:
        """
        Create a sandboxed environment for plugin execution
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Sandbox configuration
        """
        try:
            # Create temporary directory for plugin
            temp_dir = Path(tempfile.mkdtemp(prefix=f"wakedock_plugin_{plugin_name}_"))
            
            sandbox_config = {
                'temp_dir': str(temp_dir),
                'max_memory': 128 * 1024 * 1024,  # 128MB
                'max_cpu_time': 60,  # 60 seconds
                'network_access': False,
                'file_access': 'restricted',
                'allowed_syscalls': [
                    'read', 'write', 'open', 'close', 'stat', 'fstat',
                    'lstat', 'poll', 'lseek', 'mmap', 'munmap', 'brk',
                    'rt_sigaction', 'rt_sigprocmask', 'rt_sigreturn',
                    'ioctl', 'access', 'pipe', 'select', 'sched_yield',
                    'mremap', 'msync', 'mincore', 'madvise', 'shmget',
                    'shmat', 'shmctl', 'dup', 'dup2', 'getpid', 'gettid',
                    'time', 'times', 'gettimeofday', 'clock_gettime',
                    'nanosleep', 'getdents', 'chdir', 'fchdir', 'getcwd',
                    'futex', 'set_thread_area', 'get_thread_area',
                    'set_tid_address', 'clock_getres', 'exit_group'
                ]
            }
            
            logger.info(f"Created sandbox for plugin {plugin_name}")
            return sandbox_config
            
        except Exception as e:
            logger.error(f"Failed to create sandbox for plugin {plugin_name}: {e}")
            return {}
    
    async def cleanup_sandbox(self, sandbox_config: Dict[str, Any]) -> None:
        """
        Clean up sandbox environment
        
        Args:
            sandbox_config: Sandbox configuration
        """
        try:
            temp_dir = Path(sandbox_config.get('temp_dir', ''))
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up sandbox directory: {temp_dir}")
                
        except Exception as e:
            logger.error(f"Failed to cleanup sandbox: {e}")
    
    def get_security_report(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get security report for a plugin
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Security report
        """
        return {
            'plugin_name': plugin_name,
            'signature': self.plugin_signatures.get(plugin_name),
            'validated': plugin_name in self.plugin_signatures,
            'blocked_imports': list(self.blocked_imports),
            'allowed_imports': list(self.allowed_imports),
            'dangerous_functions': list(self.dangerous_functions),
            'max_file_size': self.max_file_size,
            'max_lines': self.max_lines,
        }