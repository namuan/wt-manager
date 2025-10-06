# Design Document

## Overview

The Git Worktree Manager is architected as a modern PyQt6 desktop application using the Model-View-Controller (MVC) pattern with a clean separation of concerns. The application manages multiple Git projects, each containing one or more worktrees, through a dual-pane interface that provides intuitive project navigation and worktree management.

The core design principles include:

- **Separation of Concerns**: Clear boundaries between UI, business logic, and data access
- **Asynchronous Operations**: Non-blocking Git operations with progress feedback
- **Extensible Architecture**: Plugin-ready design for future enhancements
- **Robust Error Handling**: Comprehensive validation and user-friendly error messages
- **Persistent State**: Reliable project configuration storage and recovery

## Architecture

### High-Level Architecture

```mermaid
graph TB
    UI[PyQt6 UI Layer]
    Controller[Controller Layer]
    Service[Service Layer]
    Model[Model Layer]
    Storage[Storage Layer]
    Git[Git Operations]

    UI --> Controller
    Controller --> Service
    Service --> Model
    Service --> Git
    Model --> Storage

    subgraph "UI Components"
        MainWindow[Main Window]
        ProjectPanel[Project Panel]
        WorktreePanel[Worktree Panel]
        Dialogs[Dialogs & Forms]
    end

    subgraph "Services"
        ProjectService[Project Service]
        WorktreeService[Worktree Service]
        GitService[Git Service]
        ValidationService[Validation Service]
    end

    subgraph "Models"
        ProjectModel[Project Model]
        WorktreeModel[Worktree Model]
        ConfigModel[Config Model]
    end
```

### Application Structure

The application follows a layered architecture:

1. **UI Layer**: PyQt6 widgets and windows
2. **Controller Layer**: Event handling and UI coordination
3. **Service Layer**: Business logic and Git operations
4. **Model Layer**: Data structures and state management
5. **Storage Layer**: Configuration persistence and data access

## Components and Interfaces

### Core Components

#### 1. Main Application (`MainApplication`)

- **Purpose**: Application entry point and lifecycle management
- **Responsibilities**:
  - Initialize PyQt6 application
  - Load configuration and restore window state
  - Coordinate application shutdown
  - Handle global error recovery

#### 2. Main Window (`MainWindow`)

- **Purpose**: Primary application window and layout management
- **Key Features**:
  - Dual-pane layout (Projects | Worktrees)
  - Menu bar with application actions
  - Status bar with operation feedback
  - Toolbar with common actions
- **Layout Structure**:
  ```
  ┌─────────────────────────────────────┐
  │ Menu Bar                            │
  ├─────────────────────────────────────┤
  │ Toolbar                             │
  ├─────────────┬───────────────────────┤
  │ Projects    │ Worktrees             │
  │ Panel       │ Panel                 │
  │             │                       │
  │ [Project 1] │ [Worktree 1] [main]   │
  │ [Project 2] │ [Worktree 2] [dev]    │
  │ [+ Add]     │ [+ New Worktree]      │
  ├─────────────┴───────────────────────┤
  │ Status Bar                          │
  └─────────────────────────────────────┘
  ```

#### 3. Project Panel (`ProjectPanel`)

- **Purpose**: Display and manage Git projects
- **Features**:
  - Project list with status indicators
  - Add/remove project actions
  - Project validation and health checks
  - Context menu for project operations

#### 4. Worktree Panel (`WorktreePanel`)

- **Purpose**: Display and manage worktrees for selected project
- **Features**:
  - Worktree list with branch and status information
  - Create/remove worktree actions
  - Context menu for worktree operations
  - Detailed worktree information display

### Service Layer

#### 1. Project Service (`ProjectService`)

- **Interface**:
  ```python
  class ProjectService:
      def add_project(self, path: str) -> Project
      def remove_project(self, project_id: str) -> bool
      def validate_project(self, path: str) -> ValidationResult
      def get_projects(self) -> List[Project]
      def refresh_project(self, project_id: str) -> Project
  ```

#### 2. Worktree Service (`WorktreeService`)

- **Interface**:
  ```python
  class WorktreeService:
      def get_worktrees(self, project: Project) -> List[Worktree]
      def create_worktree(self, project: Project, path: str, branch: str) -> Worktree
      def remove_worktree(self, worktree: Worktree, force: bool = False) -> bool
      def validate_worktree_creation(self, path: str, branch: str) -> ValidationResult
  ```

#### 3. Git Service (`GitService`)

- **Interface**:
  ```python
  class GitService:
      def execute_command(self, command: List[str], cwd: str) -> CommandResult
      def get_worktree_list(self, repo_path: str) -> List[Dict]
      def create_worktree(self, repo_path: str, worktree_path: str, branch: str) -> CommandResult
      def remove_worktree(self, worktree_path: str, force: bool = False) -> CommandResult
      def fetch_remote(self, repo_path: str) -> CommandResult
      def get_branch_list(self, repo_path: str) -> List[str]
  ```

#### 4. Validation Service (`ValidationService`)

- **Interface**:
  ```python
  class ValidationService:
      def validate_git_repository(self, path: str) -> ValidationResult
      def validate_worktree_path(self, path: str) -> ValidationResult
      def validate_branch_name(self, branch: str) -> ValidationResult
      def check_uncommitted_changes(self, worktree_path: str) -> ValidationResult
  ```

## Data Models

### Core Data Structures

#### 1. Project Model

```python
@dataclass
class Project:
    id: str
    name: str
    path: str
    status: ProjectStatus
    last_accessed: datetime
    worktrees: List[Worktree] = field(default_factory=list)

    def is_valid(self) -> bool
    def get_display_name(self) -> str
    def refresh_worktrees(self) -> None
```

#### 2. Worktree Model

```python
@dataclass
class Worktree:
    path: str
    branch: str
    commit_hash: str
    is_bare: bool
    is_detached: bool
    has_uncommitted_changes: bool
    last_modified: datetime

    def get_status_display(self) -> str
    def is_current_directory(self) -> bool
    def get_relative_path(self, base_path: str) -> str
```

#### 3. Configuration Model

```python
@dataclass
class AppConfig:
    projects: List[ProjectConfig]
    window_geometry: Dict[str, int]
    preferences: UserPreferences

    def save(self) -> None
    def load(self) -> 'AppConfig'
    def add_project(self, project: ProjectConfig) -> None
    def remove_project(self, project_id: str) -> None
```

### State Management

The application uses a centralized state management approach:

- **Project State**: Managed by `ProjectManager` singleton
- **UI State**: Managed by individual controllers
- **Configuration State**: Managed by `ConfigManager`
- **Operation State**: Managed by `OperationManager` for async operations

## Error Handling

### Error Categories

1. **Git Operation Errors**

   - Repository not found
   - Invalid Git commands
   - Network connectivity issues
   - Permission errors

2. **File System Errors**

   - Path not accessible
   - Insufficient permissions
   - Disk space issues
   - Path conflicts

3. **Validation Errors**
   - Invalid repository structure
   - Branch name conflicts
   - Worktree path conflicts
   - Configuration errors

### Error Handling Strategy

```python
class ErrorHandler:
    def handle_git_error(self, error: GitError) -> UserAction
    def handle_filesystem_error(self, error: FileSystemError) -> UserAction
    def handle_validation_error(self, error: ValidationError) -> UserAction
    def show_error_dialog(self, error: AppError) -> None
    def log_error(self, error: Exception) -> None
```

### User Feedback Mechanisms

- **Progress Dialogs**: For long-running operations
- **Status Bar Messages**: For quick feedback
- **Error Dialogs**: For detailed error information
- **Validation Tooltips**: For inline validation feedback
- **Success Notifications**: For operation confirmations

## Testing Strategy

### Testing Pyramid

1. **Unit Tests** (70%)

   - Service layer logic
   - Model validation
   - Utility functions
   - Git command parsing

2. **Integration Tests** (20%)

   - Service interactions
   - File system operations
   - Git command execution
   - Configuration persistence

3. **UI Tests** (10%)
   - Critical user workflows
   - Dialog interactions
   - Error handling flows
   - Keyboard shortcuts

### Test Structure

```
tests/
├── unit/
│   ├── services/
│   ├── models/
│   └── utils/
├── integration/
│   ├── git_operations/
│   ├── file_system/
│   └── configuration/
└── ui/
    ├── workflows/
    └── dialogs/
```

### Mock Strategy

- **Git Operations**: Mock `GitService` for predictable testing
- **File System**: Use temporary directories for isolation
- **UI Components**: Mock heavy UI components for unit tests
- **External Dependencies**: Mock system calls and external processes

### Test Data Management

- **Test Repositories**: Pre-configured Git repositories for testing
- **Configuration Fixtures**: Sample configuration files
- **Mock Data**: Realistic project and worktree data
- **Error Scenarios**: Predefined error conditions for testing

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**: Load worktree information on demand
2. **Caching**: Cache Git command results with TTL
3. **Background Operations**: Use QThread for Git operations
4. **Debouncing**: Debounce rapid UI updates
5. **Memory Management**: Proper cleanup of Qt objects

### Scalability Limits

- **Projects**: Designed to handle 50+ projects efficiently
- **Worktrees**: Up to 100 worktrees per project
- **UI Responsiveness**: Sub-100ms response for UI interactions
- **Git Operations**: Timeout after 30 seconds for Git commands

## Security Considerations

### Input Validation

- **Path Sanitization**: Prevent directory traversal attacks
- **Command Injection**: Sanitize all Git command parameters
- **File Permissions**: Validate file system permissions before operations
- **Branch Names**: Validate branch names against Git standards

### Data Protection

- **Configuration Security**: Store sensitive data securely
- **Temporary Files**: Clean up temporary files after operations
- **Process Isolation**: Isolate Git operations from main process
- **Error Information**: Sanitize error messages to prevent information leakage
