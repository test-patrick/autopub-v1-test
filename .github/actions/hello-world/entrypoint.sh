#!/bin/bash

set -e

# Get the input parameter
WHO_TO_GREET="$1"

# Print the greeting
echo "Hello $WHO_TO_GREET!"

# Get current time
current_time=$(date)

# Set the output
echo "time=$current_time" >> $GITHUB_OUTPUT

# Show a notice in the GitHub Actions UI
echo "::notice::Greeting completed at $current_time"

echo "Action completed successfully!" 