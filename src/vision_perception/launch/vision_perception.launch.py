"""Launch the Grove Vision AI perception node, optionally in mock mode."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    use_mock = LaunchConfiguration("use_mock")
    params_file = LaunchConfiguration("params_file")

    default_params = PathJoinSubstitution(
        [FindPackageShare("vision_perception"), "config", "params.yaml"]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_mock",
                default_value="false",
                description="If true, launch mock_vision_node instead of vision_ai_node.",
            ),
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
                condition=UnlessCondition(use_mock),
            ),
            Node(
                package="vision_perception",
                executable="mock_vision_node",
                name="mock_vision_node",
                output="screen",
                parameters=[params_file],
                condition=IfCondition(use_mock),
            ),
        ]
    )
