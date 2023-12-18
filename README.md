# lio-sam-scout-databox 包的介绍

这个包是使用data_box，进行lio_sam建图的程序，所谓data_box是我们开发的数据采集装置，上面配置了组合导航、双目相机、激光雷达。Lio_sam所使用的激光雷达是rslidar helios 16p ，imu使用的是双目摄像头的imu。

# 环境依赖

## 1.最好使用docker ubuntu20.04，如果不使用docker，直接使用ubuntu 20.04也可以 . 使用dokcer注意，数据在主机上时需要使用ROS分布式节点的配置方法配置 .

## 2.这个包在Neotic上测试过，未在其他版本的ROS上测试过，依赖的包如下.

- 遇到问题参考这个链接，Refer to [#206](https://github.com/TixiaoShan/LIO-SAM/issues/206) for Noetic)
  ```
  sudo apt-get install -y ros-kinetic-navigation
  sudo apt-get install -y ros-kinetic-robot-localization
  sudo apt-get install -y ros-kinetic-robot-state-publisher
  ```
- [gtsam](https://gtsam.org/get_started/) (Georgia Tech Smoothing and Mapping library)
  ```
  sudo add-apt-repository ppa:borglab/gtsam-release-4.0
  sudo apt install libgtsam-dev libgtsam-unstable-dev
  ```
## 3.编译与运行 .

1. 先编译
   
1. 运行:
```
roslaunch lio_sam run.launch
```

2. 播放数据:
```
rosbag play your-bag.bag -r 3
```
