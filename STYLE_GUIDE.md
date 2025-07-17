# WakeDock Code Style Guide

This document defines the coding standards and conventions for the WakeDock project.

## Python Code Standards

### Formatting
- Tool: black
- Line length: 88
- Target version: py39

### Import Organization
- Tool: isort
- Profile: black
- Multi-line output: 3

### Linting
- Tool: flake8
- Max line length: 88
- Ignored rules: E203, W503

### Naming Conventions
- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_CASE
- Variables: snake_case

### Docstrings
- Format: Google style
- Quote style: triple double quotes
- Required for: classes, functions, modules

## General Standards

- Indentation: 4 spaces
- Line endings: LF
- Encoding: UTF-8
- Max file length: 1000

## Enforcement

These standards are enforced through:
- Pre-commit hooks
- CI/CD pipeline checks
- Code review requirements
- Automated formatting tools
