#!/bin/bash

# HiveTraceRed Documentation Build Script
# Enhanced version with improved error handling and features

set -e

# Color output for better visibility
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BUILD_DIR="public"
DOCS_DIR="docs"
DOCTREES_DIR="${DOCS_DIR}/_build/doctrees"

# Help function
show_help() {
    echo "HiveTraceRed Documentation Build Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -c, --clean    Clean build directories only (no build)"
    echo "  -f, --fast     Fast build (skip license generation)"
    echo "  -w, --watch    Build and watch for changes (requires sphinx-autobuild)"
    echo "  -s, --serve    Build and serve locally on port 8000"
    echo "  -v, --verbose  Verbose output"
    echo
    echo "Examples:"
    echo "  $0              # Standard build"
    echo "  $0 --clean     # Clean build directories"
    echo "  $0 --fast      # Quick build without license generation"
    echo "  $0 --watch     # Live reload development server"
    echo "  $0 --serve     # Build and serve on localhost:8000"
}

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check if sphinx-build is available
    if ! command -v sphinx-build &> /dev/null; then
        log_error "sphinx-build not found. Please install Sphinx:"
        echo "  pip install sphinx"
        exit 1
    fi
    
    # Check if pip-licenses is available (for license generation)
    if ! command -v pip-licenses &> /dev/null && [ "$FAST_BUILD" != "true" ]; then
        log_warning "pip-licenses not found. Install it for license table generation:"
        echo "  pip install pip-licenses"
        echo "  Or use --fast flag to skip license generation"
    fi
    
    log_success "Dependencies check completed"
}

# Clean build directories
clean_build() {
    log_info "Cleaning previous builds..."
    
    rm -rf "${BUILD_DIR}/"
    rm -rf "${DOCTREES_DIR}/"
    
    # Clean any Python cache files in docs
    find "${DOCS_DIR}" -name "*.pyc" -delete 2>/dev/null || true
    find "${DOCS_DIR}" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    log_success "Build directories cleaned"
}

# Activate virtual environment
activate_venv() {
    if [ -d "venv" ]; then
        log_info "Activating virtual environment (venv)..."
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        log_info "Activating virtual environment (.venv)..."
        source .venv/bin/activate
    else
        log_warning "No virtual environment found, using system Python"
    fi
}

# Generate license table
generate_licenses() {
    if [ "$FAST_BUILD" = "true" ]; then
        log_info "Skipping license generation (fast build mode)"
        return
    fi
    
    if command -v pip-licenses &> /dev/null; then
        log_info "Generating license information..."
        
        # Generate license table
        pip-licenses --format=rst --output-file="${DOCS_DIR}/licenses_table.rst"
        
        # Add proper RST title so Sphinx can link it in toctree
        {
            echo "Third-Party Licenses"
            echo "===================="
            echo
            cat "${DOCS_DIR}/licenses_table.rst"
        } > "${DOCS_DIR}/licenses_table.rst.tmp" && mv "${DOCS_DIR}/licenses_table.rst.tmp" "${DOCS_DIR}/licenses_table.rst"
        
        log_success "License table generated"
    else
        log_warning "pip-licenses not available, skipping license generation"
    fi
}

# Build documentation
build_docs() {
    log_info "Building Sphinx documentation..."
    
    # Create build directory if it doesn't exist
    mkdir -p "${BUILD_DIR}"
    
    # Build with appropriate verbosity
    if [ "$VERBOSE" = "true" ]; then
        sphinx-build -b html "${DOCS_DIR}/" "${BUILD_DIR}/" -d "${DOCTREES_DIR}" -v
    else
        sphinx-build -b html "${DOCS_DIR}/" "${BUILD_DIR}/" -d "${DOCTREES_DIR}" -q
    fi
    
    log_success "Documentation build completed successfully!"
}

# Serve documentation locally
serve_docs() {
    if [ ! -d "${BUILD_DIR}" ]; then
        log_error "Build directory '${BUILD_DIR}' not found. Run build first."
        exit 1
    fi
    
    log_info "Starting local server on http://localhost:8000"
    log_info "Press Ctrl+C to stop the server"
    echo
    
    cd "${BUILD_DIR}" && python -m http.server 8000
}

# Watch for changes and rebuild
watch_docs() {
    if ! command -v sphinx-autobuild &> /dev/null; then
        log_error "sphinx-autobuild not found. Please install it:"
        echo "  pip install sphinx-autobuild"
        exit 1
    fi
    
    log_info "Starting live reload server..."
    log_info "Documentation will be available at http://localhost:8000"
    log_info "Press Ctrl+C to stop the server"
    echo
    
    sphinx-autobuild "${DOCS_DIR}/" "${BUILD_DIR}/" \
        --host 0.0.0.0 \
        --port 8000 \
        --ignore "${DOCS_DIR}/_build/*" \
        --ignore "${DOCS_DIR}/*.tmp"
}

# Print final instructions
print_instructions() {
    echo
    log_success "Documentation is available in the '${BUILD_DIR}/' directory"
    echo
    echo "To view locally:"
    echo "  • Open ${BUILD_DIR}/index.html in your browser"
    echo "  • Or run: python -m http.server 8000 --directory ${BUILD_DIR}"
    echo "  • Then visit: http://localhost:8000"
    echo
    echo "For live development:"
    echo "  • Run: $0 --watch"
    echo "  • Or install: pip install sphinx-autobuild"
    echo
}

# Parse command line arguments
FAST_BUILD=false
CLEAN_ONLY=false
WATCH_MODE=false
SERVE_MODE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--clean)
            CLEAN_ONLY=true
            shift
            ;;
        -f|--fast)
            FAST_BUILD=true
            shift
            ;;
        -w|--watch)
            WATCH_MODE=true
            shift
            ;;
        -s|--serve)
            SERVE_MODE=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "🔨 HiveTraceRed Documentation Builder"
    echo "======================================"
    echo
    
    # Check if we're in the right directory
    if [ ! -f "${DOCS_DIR}/conf.py" ]; then
        log_error "This script must be run from the project root directory"
        log_error "Make sure ${DOCS_DIR}/conf.py exists"
        exit 1
    fi
    
    # Clean only mode
    if [ "$CLEAN_ONLY" = "true" ]; then
        clean_build
        log_success "Clean completed"
        exit 0
    fi
    
    # Watch mode
    if [ "$WATCH_MODE" = "true" ]; then
        activate_venv
        check_dependencies
        clean_build
        generate_licenses
        watch_docs
        exit 0
    fi
    
    # Regular build process
    activate_venv
    check_dependencies
    clean_build
    generate_licenses
    build_docs
    
    # Serve mode
    if [ "$SERVE_MODE" = "true" ]; then
        serve_docs
    else
        print_instructions
    fi
}

# Run main function
main "$@"