#!/usr/bin/env bash
set -e

# shellcheck disable=SC1091
source "/opt/ros/${ROS_DISTRO}/setup.bash"

if [ -d /ros2_ws/src/vision_perception ]; then
  cd /ros2_ws
  colcon build --packages-select vision_perception --symlink-install
  # shellcheck disable=SC1091
  source install/setup.bash
fi

exec "$@"
