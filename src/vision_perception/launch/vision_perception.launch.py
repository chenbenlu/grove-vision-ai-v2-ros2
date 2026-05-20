"""Launch the Grove Vision AI perception node."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    params_file = LaunchConfiguration("params_file")

    default_params = PathJoinSubstitution(
        [FindPackageShare("vision_perception"), "config", "params.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=default_params,
                description="Path to a ROS 2 parameters YAML file.",
            ),
            Node(
                package="vision_perception",
                executable="vision_ai_node",
                name="vision_ai_node",
                output="screen",
                parameters=[params_file],
            ),
        ]
    )
