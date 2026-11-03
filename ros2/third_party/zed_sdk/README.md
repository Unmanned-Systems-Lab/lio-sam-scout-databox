# ZED SDK binary prerequisite

The ZED ROS 2 wrapper source is included elsewhere in this repository, with its own open-source license. The ZED SDK is a separate vendor SDK. Its installed libraries, tools, neural models and optimized hardware caches are not mirrored here. Keep the SDK license distinct from the wrapper license.

This integration preserves the existing SDK-calibrated ZED 2i IMU data and orientation. It does not replace that backend with uncalibrated raw USB sensor capture.

## Supported binary

- ZED SDK **5.5.1**
- NVIDIA Jetson **aarch64**, L4T **36.5.x** / JetPack **6.2.2**, CUDA **12.6**
- Official installer: `ZED_SDK_Tegra_L4T36.5_v5.5.1.zstd.run`
- Size observed from the official download: `85716338` bytes
- SHA256: `a4564d9272724e523572403a0decc33169a849161c37bd1546373a17f4588a57`
- Official release selector: <https://download.stereolabs.com/zedsdk/5.5/l4t36.5/jetsons>
- Versioned download resolved from that selector: <https://stereolabs.sfo2.cdn.digitaloceanspaces.com/zedsdk/5.5/ZED_SDK_Tegra_L4T36.5_v5.5.1.zstd.run>

The versioned URL and checksum avoid silently switching to a later patch release if the vendor's `5.5` release selector changes.

## Install

From the ROS 2 workspace:

```bash
bash deploy/install_zed_sdk.bash
```

The default command opens the official interactive installer so that you can review its license and installation choices. It installs to the vendor's standard `/usr/local/zed` prefix and verifies version 5.5.1, the development headers, CMake configuration and shared library afterward. The installer can request administrator privileges as needed.

To explicitly accept the vendor license and request a minimal unattended SDK installation:

```bash
bash deploy/install_zed_sdk.bash --accept-license
```

That option uses the vendor's `silent skip_tools skip_python skip_od_module skip_drivers` flags after accepting the outer installer license. It skips optional tools, Python bindings, neural modules and the GMSL kernel drivers that this USB ZED 2i does not need. The script verifies that the development headers, CMake configuration and shared library required by the wrapper are present afterward. The current IMU configuration uses `DEPTH_MODE::NONE`, so neural depth, object detection and body-tracking models are not required.

An already installed, complete SDK 5.5.1 at `/usr/local/zed` is reused. Other SDK versions are not silently reported as compatible by this bootstrap.

## Offline staging or a supplied installer

```bash
# Download and verify without installing or accepting a license.
bash deploy/install_zed_sdk.bash --download-only

# Use a previously downloaded official installer on the target Jetson.
bash deploy/install_zed_sdk.bash --installer /path/to/ZED_SDK_Tegra_L4T36.5_v5.5.1.zstd.run
```

The download cache is `.deps/downloads/` inside this workspace and must remain ignored by Git. A custom HTTPS mirror can be selected with `--url`; the same pinned checksum is still required unless the caller explicitly supplies another trusted `--sha256`. Successful installation still requires SDK version 5.5.1.

Base OS, ROS 2, JetPack/NVIDIA drivers and the proprietary SDK are platform prerequisites, rather than source libraries taken from another machine's workspace. All open-source project dependencies should be built from the source included in the repository; no original machine path is needed for this installer.

## Vendor references

- [Software and Services License Agreement](https://www.stereolabs.com/SoftwareandServicesLicenseAgreement)
- [Official Linux installation options](https://docs.stereolabs.com/docs/development/zed-sdk/linux)
- [Jetson installation guide](https://docs.stereolabs.com/docs/development/zed-sdk/linux/work-with-nvidia-jetson)
- [Offline calibration/model deployment](https://docs.stereolabs.com/docs/development/zed-sdk/offline-deployment)

Optimized model caches are specific to matching GPU, JetPack, CUDA, TensorRT and SDK versions. They must not be treated as portable build dependencies for a different target. A camera may also need its own factory calibration file or an available calibration record in its EEPROM.
