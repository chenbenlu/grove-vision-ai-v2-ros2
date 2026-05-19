cmake_minimum_required(VERSION 3.8)
project(vision_perception)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Detection.msg"
  "msg/VisionAI.msg"
  DEPENDENCIES std_msgs
)

ament_export_dependencies(rosidl_default_runtime)

ament_python_install_package(vision_perception_nodes)

# Install node entry-points without the .py suffix so they match
# `ros2 run vision_perception vision_ai_node` exactly.
install(PROGRAMS
  vision_perception_nodes/vision_ai_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME vision_ai_node
)
install(PROGRAMS
  vision_perception_nodes/mock_vision_node.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME mock_vision_node
)

install(DIRECTORY launch config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_flake8 REQUIRED)
  find_package(ament_cmake_pep257 REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)

  # Restrict lint scope to the package's production Python; scripts/ holds
  # scratch utilities (USB serial probe, Flask dashboard) that aren't part of
  # the node contract.
  ament_flake8(
    MAX_LINE_LENGTH 100
    vision_perception_nodes
    test
  )
  ament_pep257(
    vision_perception_nodes
    test
  )
  ament_add_pytest_test(test_mock_node test/test_mock_node.py
    TIMEOUT 60
  )
endif()

ament_package()
