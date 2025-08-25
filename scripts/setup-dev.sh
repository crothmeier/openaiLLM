#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="3.10"
VENV_DIR="venv"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Change to project root
cd "$PROJECT_ROOT"

# Check Python version
check_python() {
    log_step "Checking Python installation..."
    
    # Try python3.10 explicitly first
    if command -v python3.10 &> /dev/null; then
        PYTHON_CMD="python3.10"
        log_info "Found python3.10"
    elif command -v python3 &> /dev/null; then
        # Check if python3 is 3.10
        PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if [[ "$PY_VERSION" == "3.10" ]]; then
            PYTHON_CMD="python3"
            log_info "Found Python 3.10 as python3"
        else
            log_error "Python 3.10 required, but found Python $PY_VERSION"
            log_info "Install Python 3.10: sudo apt-get install python3.10 python3.10-venv python3.10-dev"
            exit 1
        fi
    else
        log_error "Python 3.10 not found"
        exit 1
    fi
}

# Setup virtual environment
setup_venv() {
    log_step "Setting up virtual environment..."
    
    if [ -d "$VENV_DIR" ]; then
        log_warn "Virtual environment already exists at $VENV_DIR"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing virtual environment..."
            rm -rf "$VENV_DIR"
        else
            log_info "Using existing virtual environment"
            return 0
        fi
    fi
    
    log_info "Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    log_info "Virtual environment created successfully"
}

# Activate virtual environment
activate_venv() {
    log_step "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    log_info "Virtual environment activated"
    log_info "Python: $(which python)"
    log_info "Version: $(python --version)"
}

# Install dependencies
install_deps() {
    log_step "Installing dependencies..."
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip==24.2 setuptools wheel
    
    # Install dev dependencies first (lighter weight)
    if [ -f "requirements-dev.txt" ]; then
        log_info "Installing development dependencies..."
        pip install -r requirements-dev.txt
    else
        log_info "Installing core development tools..."
        pip install pytest pytest-cov pytest-asyncio pytest-mock httpx
        pip install black==24.4.2 isort==5.13.2 ruff
        pip install pre-commit detect-secrets hadolint
    fi
    
    # Install main dependencies with constraints
    if [ -f "requirements.txt" ]; then
        log_info "Installing production dependencies..."
        if [ -f "constraints.txt" ]; then
            # Try installing without heavy dependencies first
            pip install -r requirements.txt -c constraints.txt --no-deps || true
            # Install critical dependencies
            pip install fastapi uvicorn prometheus-client pydantic
        else
            pip install -r requirements.txt --no-deps || true
        fi
    fi
    
    log_info "Dependencies installed"
}

# Setup pre-commit
setup_precommit() {
    log_step "Setting up pre-commit hooks..."
    
    # Check if pre-commit is already installed globally
    if command -v pre-commit &> /dev/null; then
        log_warn "pre-commit is installed globally at $(which pre-commit)"
    fi
    
    # Ensure we use the venv pre-commit
    if [ -f "$VENV_DIR/bin/pre-commit" ]; then
        log_info "Installing pre-commit hooks..."
        "$VENV_DIR/bin/pre-commit" install
        
        # Clean any existing environments to ensure Python 3.10 is used
        log_info "Cleaning pre-commit environments..."
        "$VENV_DIR/bin/pre-commit" clean
        
        log_info "Running initial pre-commit checks..."
        "$VENV_DIR/bin/pre-commit" run --all-files || log_warn "Some pre-commit checks failed (this is normal on first run)"
    else
        log_warn "pre-commit not found in virtual environment"
    fi
}

# Create activation helper
create_helper() {
    log_step "Creating activation helper..."
    
    cat > activate.sh << 'EOF'
#!/bin/bash
# Quick activation script for T4DailyDriver development
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
echo "T4DailyDriver environment activated!"
echo "Python: $(which python)"
echo "Run 'deactivate' to exit the virtual environment"
EOF
    chmod +x activate.sh
    
    # Create .envrc for direnv users
    if command -v direnv &> /dev/null; then
        log_info "Creating .envrc for direnv..."
        echo 'source venv/bin/activate' > .envrc
        echo 'unset PS1' >> .envrc
        direnv allow . || true
    fi
}

# Main execution
main() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║   T4DailyDriver Development Setup          ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo
    
    check_python
    setup_venv
    activate_venv
    install_deps
    setup_precommit
    create_helper
    
    echo
    echo -e "${GREEN}✅ Setup complete!${NC}"
    echo
    echo "To activate the environment in the future, run:"
    echo -e "  ${BLUE}source venv/bin/activate${NC}"
    echo "Or use the helper script:"
    echo -e "  ${BLUE}source activate.sh${NC}"
    echo
    echo "Next steps:"
    echo "  1. Run tests: make test-unit"
    echo "  2. Check pre-commit: pre-commit run --all-files"
    echo "  3. Start development!"
}

# Run main
main "$@"
