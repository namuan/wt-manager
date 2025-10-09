# WorkTree Manager

A desktop application to manage multiple Git worktrees efficiently.
This tool provides a graphical interface for creating, removing, and monitoring Git worktrees with real-time status updates.

## Features

- **Worktree Management**: Create, remove, and list Git worktrees
- **Status Monitoring**: Track uncommitted changes, detached HEAD state, and branch information
- **Project Organization**: Organize worktrees by project
- **Real-time Updates**: Refresh worktree information automatically
- **Command Execution**: Run Git commands within the application
- **Error Handling**: Comprehensive error handling and user feedback

## Installation

To install from source:

1. **Clone the repository or download the ZIP file:**

   ```bash
   git clone https://github.com/namuan/dev-boost.git
   cd dev-boost
   ```

2. **Run the installation script (macOS):**

   ```bash
   ./install.command
   ```

   This script will:

   - Install `uv` (if not already installed)
   - Set up the virtual environment and dependencies
   - Install the application in your `~/Applications` folder

3. **Alternative manual installation:**
   ```bash
   make install  # Install dependencies and pre-commit hooks
   make run      # Run the application
   ```

## License

This project is licensed under the MIT License.
