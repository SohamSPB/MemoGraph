#!/bin/bash
# scan_all_trips.sh
#
# Runs the full MemoGraph pipeline on all trips with proper venv activation
# and resource monitoring.
#
# Usage:
#   ./scan_all_trips.sh                    # Process all trips
#   ./scan_all_trips.sh --reset            # Reset and reprocess all trips
#   ./scan_all_trips.sh data/trips/MyTrip  # Process single trip
#
# Resource monitoring is logged to each trip's MemoGraph/logs/resource_usage.csv

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "WARNING: No virtual environment found. Using system Python."
fi

# Check Python and GPU
echo "Python: $(which python3)"
echo "PyTorch CUDA available: $(python3 -c 'import torch; print(torch.cuda.is_available())')"

# Show GPU status
echo ""
echo "GPU Status:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used --format=csv
echo ""

# Parse arguments
RESET_FLAG=""
TRIP_FOLDER=""

for arg in "$@"; do
    case $arg in
        --reset)
            RESET_FLAG="--reset"
            ;;
        *)
            TRIP_FOLDER="$arg"
            ;;
    esac
done

# Enable parallel execution
export MEMOGRAPH_PARALLEL_EXECUTION=true

# Start time
START_TIME=$(date +%s)
echo "Starting MemoGraph pipeline at $(date)"
echo "========================================"

if [ -n "$TRIP_FOLDER" ]; then
    # Process single trip
    echo "Processing single trip: $TRIP_FOLDER"
    python3 run_all.py "$TRIP_FOLDER" $RESET_FLAG
else
    # Process all trips
    echo "Processing all trips in data/trips/"
    for trip_dir in data/trips/*/; do
        if [ -d "$trip_dir" ]; then
            trip_name=$(basename "$trip_dir")
            echo ""
            echo "========================================"
            echo "Processing: $trip_name"
            echo "========================================"
            python3 run_all.py "$trip_dir" $RESET_FLAG || echo "WARNING: Failed to process $trip_name"
        fi
    done
fi

# End time
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo "========================================"
echo "Pipeline complete!"
echo "Total time: ${MINUTES}m ${SECONDS}s"
echo "========================================"

# Show final GPU status
echo ""
echo "Final GPU Status:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used --format=csv
