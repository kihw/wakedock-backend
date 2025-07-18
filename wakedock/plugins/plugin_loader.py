"""
Plugin loader for WakeDock
"""

import importlib.util
import sys
import json
import ast
from pathlib import Path
from typing import Optional, Type, Dict, Any
import logging

from .base_plugin import BasePlugin, PluginInfo, PluginType

logger = logging.getLogger(__name__)


class PluginLoader:
    """
    Loads and validates plugins from the filesystem
    """
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = plugin_dir
        self.loaded_modules = {}
    
    async def load_plugin_info(self, plugin_path: Path) -> Optional[PluginInfo]:
        """
        Load plugin information from plugin.json
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            PluginInfo if successful, None otherwise
        """
        try:
            info_file = plugin_path / "plugin.json"
            
            if not info_file.exists():
                logger.error(f"Plugin info file not found: {info_file}")
                return None
            
            with open(info_file, 'r') as f:
                info_data = json.load(f)
            
            # Validate required fields
            required_fields = ['name', 'version', 'description', 'author', 'plugin_type']
            for field in required_fields:
                if field not in info_data:
                    logger.error(f"Missing required field '{field}' in plugin info")
                    return None
            
            # Convert plugin_type to enum
            try:
                plugin_type = PluginType(info_data['plugin_type'])
            except ValueError:
                logger.error(f"Invalid plugin type: {info_data['plugin_type']}")
                return None
            
            # Create PluginInfo object
            plugin_info = PluginInfo(
                name=info_data['name'],
                version=info_data['version'],
                description=info_data['description'],
                author=info_data['author'],
                plugin_type=plugin_type,
                dependencies=info_data.get('dependencies', []),
                permissions=info_data.get('permissions', []),
                config_schema=info_data.get('config_schema'),
                api_version=info_data.get('api_version', '1.0.0'),
                tags=info_data.get('tags', []),
                homepage=info_data.get('homepage'),
                repository=info_data.get('repository'),
                license=info_data.get('license'),
                min_wakedock_version=info_data.get('min_wakedock_version'),
                max_wakedock_version=info_data.get('max_wakedock_version'),
            )
            
            logger.info(f"Loaded plugin info: {plugin_info.name} v{plugin_info.version}")
            return plugin_info
            
        except Exception as e:
            logger.error(f"Failed to load plugin info from {plugin_path}: {e}")
            return None
    
    async def load_plugin_class(self, plugin_path: Path) -> Optional[Type[BasePlugin]]:
        """
        Load plugin class from main.py
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            Plugin class if successful, None otherwise
        """
        try:
            main_file = plugin_path / "main.py"
            
            if not main_file.exists():
                logger.error(f"Plugin main file not found: {main_file}")
                return None
            
            # Read the main file and analyze it
            with open(main_file, 'r') as f:
                source_code = f.read()
            
            # Parse the source code to find plugin class
            tree = ast.parse(source_code)
            plugin_class_name = None
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class inherits from BasePlugin
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id.endswith('Plugin'):
                            plugin_class_name = node.name
                            break
                    if plugin_class_name:
                        break
            
            if not plugin_class_name:
                logger.error(f"No plugin class found in {main_file}")
                return None
            
            # Load the module
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_path.name}",
                main_file
            )
            
            if not spec or not spec.loader:
                logger.error(f"Failed to create module spec for {main_file}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            
            # Add plugin directory to Python path temporarily
            original_path = sys.path[:]
            sys.path.insert(0, str(plugin_path))
            
            try:
                spec.loader.exec_module(module)
                self.loaded_modules[plugin_path.name] = module
                
                # Get the plugin class
                plugin_class = getattr(module, plugin_class_name)
                
                # Validate that it's a BasePlugin subclass
                if not issubclass(plugin_class, BasePlugin):
                    logger.error(f"Plugin class {plugin_class_name} is not a BasePlugin subclass")
                    return None
                
                logger.info(f"Loaded plugin class: {plugin_class_name}")
                return plugin_class
                
            finally:
                # Restore original Python path
                sys.path[:] = original_path
                
        except Exception as e:
            logger.error(f"Failed to load plugin class from {plugin_path}: {e}")
            return None
    
    async def validate_plugin_structure(self, plugin_path: Path) -> bool:
        """
        Validate plugin directory structure
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            True if structure is valid, False otherwise
        """
        try:
            # Check required files
            required_files = ['plugin.json', 'main.py']
            
            for file_name in required_files:
                file_path = plugin_path / file_name
                if not file_path.exists():
                    logger.error(f"Required file missing: {file_path}")
                    return False
            
            # Check plugin.json syntax
            info_file = plugin_path / "plugin.json"
            try:
                with open(info_file, 'r') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {info_file}: {e}")
                return False
            
            # Check main.py syntax
            main_file = plugin_path / "main.py"
            try:
                with open(main_file, 'r') as f:
                    source_code = f.read()
                ast.parse(source_code)
            except SyntaxError as e:
                logger.error(f"Syntax error in {main_file}: {e}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate plugin structure: {e}")
            return False
    
    async def get_plugin_dependencies(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Get plugin dependencies from requirements.txt
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            Dictionary with dependency information
        """
        dependencies = {
            'python_packages': [],
            'system_packages': [],
            'wakedock_plugins': []
        }
        
        try:
            # Check requirements.txt
            requirements_file = plugin_path / "requirements.txt"
            if requirements_file.exists():
                with open(requirements_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            dependencies['python_packages'].append(line)
            
            # Check plugin.json for plugin dependencies
            info_file = plugin_path / "plugin.json"
            if info_file.exists():
                with open(info_file, 'r') as f:
                    info_data = json.load(f)
                dependencies['wakedock_plugins'] = info_data.get('dependencies', [])
            
            return dependencies
            
        except Exception as e:
            logger.error(f"Failed to get plugin dependencies: {e}")
            return dependencies
    
    async def check_api_compatibility(self, plugin_info: PluginInfo) -> bool:
        """
        Check if plugin API version is compatible
        
        Args:
            plugin_info: Plugin information
            
        Returns:
            True if compatible, False otherwise
        """
        try:
            # Simple version check - can be made more sophisticated
            supported_versions = ['1.0.0', '1.0.1', '1.0.2', '1.0.3']
            
            if plugin_info.api_version not in supported_versions:
                logger.warning(f"Plugin {plugin_info.name} uses unsupported API version: {plugin_info.api_version}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check API compatibility: {e}")
            return False
    
    async def get_plugin_metadata(self, plugin_path: Path) -> Dict[str, Any]:
        """
        Get comprehensive plugin metadata
        
        Args:
            plugin_path: Path to the plugin directory
            
        Returns:
            Dictionary with plugin metadata
        """
        metadata = {
            'path': str(plugin_path),
            'size': 0,
            'file_count': 0,
            'last_modified': None,
            'structure_valid': False,
            'dependencies': {},
            'info': None,
        }
        
        try:
            # Get directory size and file count
            total_size = 0
            file_count = 0
            last_modified = None
            
            for file_path in plugin_path.rglob('*'):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    file_count += 1
                    
                    file_modified = file_path.stat().st_mtime
                    if last_modified is None or file_modified > last_modified:
                        last_modified = file_modified
            
            metadata['size'] = total_size
            metadata['file_count'] = file_count
            metadata['last_modified'] = last_modified
            
            # Validate structure
            metadata['structure_valid'] = await self.validate_plugin_structure(plugin_path)
            
            # Get dependencies
            metadata['dependencies'] = await self.get_plugin_dependencies(plugin_path)
            
            # Get plugin info
            metadata['info'] = await self.load_plugin_info(plugin_path)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get plugin metadata: {e}")
            return metadata
    
    def unload_plugin_module(self, plugin_name: str) -> bool:
        """
        Unload plugin module from memory
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if plugin_name in self.loaded_modules:
                module = self.loaded_modules[plugin_name]
                
                # Remove from sys.modules if present
                modules_to_remove = []
                for module_name in sys.modules:
                    if module_name.startswith(f"plugin_{plugin_name}"):
                        modules_to_remove.append(module_name)
                
                for module_name in modules_to_remove:
                    del sys.modules[module_name]
                
                # Remove from loaded modules
                del self.loaded_modules[plugin_name]
                
                logger.info(f"Unloaded plugin module: {plugin_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to unload plugin module {plugin_name}: {e}")
            return False
    
    def get_loaded_modules(self) -> Dict[str, Any]:
        """
        Get information about loaded plugin modules
        
        Returns:
            Dictionary with loaded module information
        """
        return {
            name: {
                'module': str(module),
                'file': getattr(module, '__file__', None),
                'size': sys.getsizeof(module),
            }
            for name, module in self.loaded_modules.items()
        }