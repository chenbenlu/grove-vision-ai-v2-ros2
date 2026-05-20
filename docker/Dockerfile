# syntax=docker/dockerfile:1.6
ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO}-ros-base

ARG DEBIAN_FRONTEND=noninteractive
ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3-colcon-common-extensions \
      python3-pip \
      python3-serial \
      python3-smbus \
      i2c-tools \
      build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir smbus2

WORKDIR /ros2_ws

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["ros2", "launch", "vision_perception", "vision_perception.launch.py"]
