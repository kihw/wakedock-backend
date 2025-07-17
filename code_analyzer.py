#!/usr/bin/env python3
"""
WakeDock v0.6.1 Code Analysis Tool
Analyzes the current codebase to identify refactoring opportunities
"""
import os
import sys
import ast
import json
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict

class CodeAnalyzer:
    """Analyzes Python code for refactoring opportunities"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.analysis_results = {
            'code_quality': {},
            'architecture_issues': [],
            'performance_issues': [],
            'refactoring_opportunities': [],
            'technical_debt': []
        }
    
    def analyze_project(self) -> Dict[str, Any]:
        """Analyze the entire project for refactoring opportunities"""
        
        print("🔍 WakeDock v0.6.1 Code Analysis")
        print("=" * 50)
        
        # Analyze Python files
        python_files = list(self.project_root.rglob("*.py"))
        print(f"📊 Analyzing {len(python_files)} Python files...")
        
        for file_path in python_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                self._analyze_file(file_path)
            except Exception as e:
                print(f"⚠️  Error analyzing {file_path}: {e}")
        
        # Generate refactoring recommendations
        self._generate_recommendations()
        
        return self.analysis_results
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped during analysis"""
        skip_patterns = [
            '__pycache__',
            '.pyc',
            'venv',
            'node_modules',
            '.git',
            'alembic/versions',
            'migrations'
        ]
        
        return any(pattern in str(file_path) for pattern in skip_patterns)
    
    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse AST
            tree = ast.parse(content)
            
            # Analyze different aspects
            self._analyze_imports(tree, file_path)
            self._analyze_functions(tree, file_path)
            self._analyze_classes(tree, file_path)
            self._analyze_complexity(tree, file_path)
            
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
    
    def _analyze_imports(self, tree: ast.AST, file_path: Path) -> None:
        """Analyze import statements for optimization opportunities"""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        # Check for unused imports (basic heuristic)
        if len(imports) > 20:  # Arbitrary threshold
            self.analysis_results['refactoring_opportunities'].append({
                'file': str(file_path),
                'type': 'too_many_imports',
                'count': len(imports),
                'description': f"File has {len(imports)} imports, consider refactoring"
            })
    
    def _analyze_functions(self, tree: ast.AST, file_path: Path) -> None:
        """Analyze functions for complexity and refactoring opportunities"""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count lines in function
                lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                
                functions.append({
                    'name': node.name,
                    'lines': lines,
                    'args': len(node.args.args)
                })
                
                # Check for long functions
                if lines > 50:  # Arbitrary threshold
                    self.analysis_results['refactoring_opportunities'].append({
                        'file': str(file_path),
                        'type': 'long_function',
                        'function': node.name,
                        'lines': lines,
                        'description': f"Function '{node.name}' has {lines} lines, consider breaking it down"
                    })
                
                # Check for too many parameters
                if len(node.args.args) > 5:  # Arbitrary threshold
                    self.analysis_results['refactoring_opportunities'].append({
                        'file': str(file_path),
                        'type': 'too_many_parameters',
                        'function': node.name,
                        'params': len(node.args.args),
                        'description': f"Function '{node.name}' has {len(node.args.args)} parameters, consider refactoring"
                    })
    
    def _analyze_classes(self, tree: ast.AST, file_path: Path) -> None:
        """Analyze classes for design issues"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Count methods
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                
                if len(methods) > 20:  # Arbitrary threshold
                    self.analysis_results['refactoring_opportunities'].append({
                        'file': str(file_path),
                        'type': 'large_class',
                        'class': node.name,
                        'methods': len(methods),
                        'description': f"Class '{node.name}' has {len(methods)} methods, consider splitting"
                    })
    
    def _analyze_complexity(self, tree: ast.AST, file_path: Path) -> None:
        """Analyze code complexity"""
        # Simple complexity metrics
        complexity_indicators = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.Try)):
                complexity_indicators += 1
        
        if complexity_indicators > 50:  # Arbitrary threshold
            self.analysis_results['architecture_issues'].append({
                'file': str(file_path),
                'type': 'high_complexity',
                'complexity': complexity_indicators,
                'description': f"File has high complexity ({complexity_indicators} control structures)"
            })
    
    def _generate_recommendations(self) -> None:
        """Generate refactoring recommendations based on analysis"""
        recommendations = []
        
        # Analyze refactoring opportunities
        if self.analysis_results['refactoring_opportunities']:
            recommendations.append({
                'priority': 'high',
                'category': 'code_quality',
                'title': 'Refactor long functions and classes',
                'description': 'Several functions and classes are too large and should be broken down',
                'count': len(self.analysis_results['refactoring_opportunities'])
            })
        
        # Analyze architecture issues
        if self.analysis_results['architecture_issues']:
            recommendations.append({
                'priority': 'medium',
                'category': 'architecture',
                'title': 'Reduce code complexity',
                'description': 'Some files have high complexity and should be refactored',
                'count': len(self.analysis_results['architecture_issues'])
            })
        
        self.analysis_results['recommendations'] = recommendations
    
    def generate_report(self) -> str:
        """Generate a human-readable report"""
        report = []
        report.append("🔍 WakeDock v0.6.1 Code Analysis Report")
        report.append("=" * 50)
        
        # Summary
        total_issues = (
            len(self.analysis_results['refactoring_opportunities']) +
            len(self.analysis_results['architecture_issues']) +
            len(self.analysis_results['performance_issues'])
        )
        
        report.append(f"\n📊 Summary:")
        report.append(f"   • Total issues found: {total_issues}")
        report.append(f"   • Refactoring opportunities: {len(self.analysis_results['refactoring_opportunities'])}")
        report.append(f"   • Architecture issues: {len(self.analysis_results['architecture_issues'])}")
        report.append(f"   • Performance issues: {len(self.analysis_results['performance_issues'])}")
        
        # Recommendations
        if self.analysis_results.get('recommendations'):
            report.append(f"\n🎯 Recommendations:")
            for rec in self.analysis_results['recommendations']:
                report.append(f"   • [{rec['priority'].upper()}] {rec['title']}")
                report.append(f"     {rec['description']} ({rec['count']} items)")
        
        # Detailed issues
        if self.analysis_results['refactoring_opportunities']:
            report.append(f"\n🔄 Refactoring Opportunities:")
            for issue in self.analysis_results['refactoring_opportunities'][:10]:  # Show top 10
                report.append(f"   • {issue['type']}: {issue['description']}")
                report.append(f"     File: {issue['file']}")
        
        if self.analysis_results['architecture_issues']:
            report.append(f"\n🏗️  Architecture Issues:")
            for issue in self.analysis_results['architecture_issues'][:5]:  # Show top 5
                report.append(f"   • {issue['type']}: {issue['description']}")
                report.append(f"     File: {issue['file']}")
        
        report.append(f"\n✅ Analysis complete! Ready for v0.6.1 refactoring.")
        
        return "\\n".join(report)

def main():
    """Main function to run the analysis"""
    project_root = Path(__file__).parent
    
    analyzer = CodeAnalyzer(str(project_root))
    results = analyzer.analyze_project()
    
    # Generate and display report
    report = analyzer.generate_report()
    print(report)
    
    # Save results to file
    with open(project_root / "code_analysis_v0.6.1.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Analysis results saved to: code_analysis_v0.6.1.json")
    
    return len(results['refactoring_opportunities']) + len(results['architecture_issues'])

if __name__ == "__main__":
    issues_found = main()
    sys.exit(0 if issues_found < 20 else 1)  # Exit with error if too many issues
